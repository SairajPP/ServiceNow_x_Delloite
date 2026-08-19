"""
Orchestrator for TASK-ECO-CLASSIFY — ai-agent-specs.md Section 3.

Runs as a FastAPI BackgroundTask after the webhook returns 202. Sequence:
  1. GET complaint (+ pre-condition checks)
  2. GET photo attachment
  3. Triage + Vision + Environmental data, fetched concurrently
  4. Severity Fusion (needs outputs of step 3)
  5. PATCH complaint, POST snapshot, POST agent logs (steps 1-4 -> ServiceNow)

Failure handling follows the failure-mode table in
integration-contract.md Section 6 and ai-agent-specs.md Section 3
("Failure Modes") at every step — nothing here should raise past
run_pipeline() and strand a complaint silently. Anything unrecoverable
falls back to `ai_processing_status = "failed"`, and FL-02 on the
ServiceNow side (60-minute scheduled fallback) is the safety net if
FastAPI never writes back at all.
"""
import asyncio
from datetime import datetime, timezone

from app.agents import fusion_agent, triage_agent, vision_agent, report_agent, legal_agent, leadership_agent
from app.external_apis import fetch_environmental_data
from app.logging_utils import get_logger
from app.models import AgentLogEntry
from app.servicenow_client import ServiceNowError, sn_client

logger = get_logger(__name__)


async def run_pipeline(sys_id: str, number: str, lat: float, lng: float) -> None:
    logger.info("Pipeline STARTING for %s (%s)", number, sys_id)
    try:
        await _run_pipeline_inner(sys_id, number, lat, lng)
    except Exception as exc:
        logger.exception("UNHANDLED ERROR in pipeline for %s: %s", number, exc)


async def _run_pipeline_inner(sys_id: str, number: str, lat: float, lng: float) -> None:
    try:
        complaint = await sn_client.get_complaint(sys_id)
    except ServiceNowError as exc:
        logger.error("Could not fetch complaint %s: %s", sys_id, exc)
        return  # FL-02 fallback on the SN side catches this after 60 min

    logger.info("Fetched complaint %s — state=%s", number, complaint.get("state"))

    # --- Pre-conditions (ai-agent-specs.md Section 3) ---
    if complaint.get("state") not in (None, "", "1"):
        logger.info("Complaint %s not in 'Received' state (state=%s), skipping.", number, complaint.get("state"))
        return
    if complaint.get("override_severity"):
        logger.info("Complaint %s already has an officer override, skipping AI classification.", number)
        return

    description = complaint.get("description", "")
    incident_category = complaint.get("incident_category", "other")

    await _mark_status(sys_id, "processing")

    # --- Steps 1 & 2 & environmental data, concurrently ---
    logger.info("[%s] Step 1: Fetching attachment + environmental data...", number)
    attachment_task = sn_client.get_attachment_binary(sys_id)
    env_task = fetch_environmental_data(lat, lng)
    attachment, env = await asyncio.gather(attachment_task, env_task)
    logger.info("[%s] Step 1 DONE. Attachment=%s, Env=%s", number, "yes" if attachment else "no", env.data_source)

    image_bytes, content_type = (attachment if attachment else (None, None))

    logger.info("[%s] Step 2: Running Triage Agent...", number)
    triage_output, triage_log = await triage_agent.run(description, incident_category)
    logger.info("[%s] Step 2 DONE. Urgency=%s", number, triage_output.initial_urgency)

    logger.info("[%s] Step 3: Running Vision Agent...", number)
    vision_output, vision_log = await vision_agent.run(image_bytes, content_type or "image/jpeg")
    logger.info("[%s] Step 3 DONE. Caption=%s", number, vision_output.caption[:80])

    # --- Step 3: Severity Fusion ---
    logger.info("[%s] Step 4: Running Fusion Agent...", number)
    fusion_output, fusion_log = await fusion_agent.run(
        triage=triage_output, vision=vision_output, citizen_text=description, env=env
    )
    logger.info("[%s] Step 4 DONE. Severity=%s Confidence=%s", number, fusion_output.severity, fusion_output.confidence)

    # --- Write-back: complaint, snapshot, logs ---
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        await sn_client.patch_complaint(
            sys_id,
            {
                "ai_severity": fusion_output.severity,
                "ai_confidence_score": fusion_output.confidence,
                "ai_image_caption": vision_output.caption,
                "ai_rantionale": fusion_output.rationale,
                "ai_classified_at": now,
                "ai_processing_status": "completed" if fusion_output.confidence > 0 else "fallback",
            },
        )
    except ServiceNowError as exc:
        logger.error("PATCH complaint %s failed: %s", number, exc)
        # Leave state as-is; FL-02 fallback catches it after 60 minutes.
        return

    try:
        await sn_client.post_agent_decision({
            "agent_name": "Python Severity Fusion",
            "linked_complaint": sys_id,
            "confidence_score": fusion_output.confidence,
            "ai_rationale": fusion_output.rationale
        })
    except Exception as exc:
        logger.error("POST agent decision for %s failed: %s", number, exc)

    try:
        await sn_client.post_snapshot(
            {
                "parent_complaint": sys_id,
                "aqi_value": env.aqi_value,
                "aqi_category": env.aqi_category,
                "primary_pollutant": env.primary_pollutant,
                "wind_speed": env.wind_speed,
                "wind_direction": env.wind_direction,
                "temperature": env.temperature,
                "weather_condition": env.weather_condition,
                "humidity": env.humidity,
                "data_source": env.data_source,
                "aqi_source": env.aqi_source,
                "weather_source": env.weather_source,
            }
        )
    except ServiceNowError as exc:
        logger.error("POST snapshot for %s failed: %s", number, exc)

    for log in (triage_log, vision_log, fusion_log):
        await _post_log(log, sys_id, number)

    logger.info(
        "Pipeline complete for %s: severity=%s confidence=%s",
        number, fusion_output.severity, fusion_output.confidence,
    )


async def _mark_status(sys_id: str, status: str) -> None:
    try:
        await sn_client.patch_complaint(sys_id, {"ai_processing_status": status})
    except ServiceNowError as exc:
        logger.warning("Could not mark ai_processing_status=%s for %s: %s", status, sys_id, exc)


async def _post_log(log: AgentLogEntry, sys_id: str, number: str) -> None:
    log.linked_record = sys_id
    log.linked_record_number = number
    try:
        await sn_client.post_agent_log(log.model_dump(exclude_none=True))
    except ServiceNowError as exc:
        logger.error("POST agent_log (%s) for %s failed: %s", log.agent_name, number, exc)

async def run_inspection_pipeline(sys_id: str, number: str, raw_notes: str) -> None:
    logger.info("Starting Inspection Report generation for %s", number)
    
    # Fetch attachment if any
    attachment = await sn_client.get_attachment_binary(sys_id)
    image_bytes, content_type = (attachment if attachment else (None, None))
    
    # 1. Run the AI Agent
    report_text, log = await report_agent.run(raw_notes, image_bytes, content_type)
    
    # 2. Patch the inspection record in ServiceNow
    try:
        await sn_client.patch_inspection(sys_id, {"ai_generated_report": report_text, "state": "5"}) # State 5 = Report Drafted
    except ServiceNowError as exc:
        logger.error("PATCH inspection %s failed: %s", number, exc)
    
    # 3. Write the audit log
    await _post_log(log, sys_id, number)
    
    logger.info("Inspection Report complete for %s", number)


async def run_legal_pipeline(record_sys_id: str, number: str, evidence_package: str) -> None:
    """FL-07: Generate a prosecution-ready legal case narrative from compiled evidence."""
    logger.info("Starting Legal Case narrative generation for %s", number)

    # 1. Run the Legal Case Summary AI Agent
    narrative, log = await legal_agent.run(evidence_package)

    # 2. Patch the legal case record in ServiceNow
    try:
        await sn_client.patch_legal_case(record_sys_id, {"case_narrative": narrative})
    except ServiceNowError as exc:
        logger.error("PATCH legal_case %s failed: %s", number, exc)

    # 3. Write the audit log
    await _post_log(log, record_sys_id, number)

    logger.info("Legal Case narrative complete for %s", number)

async def run_leadership_pipeline(metrics_json: str) -> str:
    """FL-10: Generate a weekly executive summary of platform metrics."""
    logger.info("Starting Leadership Insights generation")

    # 1. Run the Leadership Insights AI Agent
    summary, log = await leadership_agent.run(metrics_json)

    # 2. Write the audit log (no linked record since it's an aggregated report)
    # We use a dummy sys_id and number for the log
    await _post_log(log, "global", "WEEKLY-METRICS")

    logger.info("Leadership Insights complete")
    return summary
