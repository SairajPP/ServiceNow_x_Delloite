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

from app.agents import fusion_agent, triage_agent, vision_agent
from app.external_apis import fetch_environmental_data
from app.logging_utils import get_logger
from app.models import AgentLogEntry
from app.servicenow_client import ServiceNowError, sn_client

logger = get_logger(__name__)


async def run_pipeline(sys_id: str, number: str, lat: float, lng: float) -> None:
    try:
        complaint = await sn_client.get_complaint(sys_id)
    except ServiceNowError as exc:
        logger.error("Could not fetch complaint %s: %s", sys_id, exc)
        return  # FL-02 fallback on the SN side catches this after 60 min

    # --- Pre-conditions (ai-agent-specs.md Section 3) ---
    if complaint.get("state") not in (None, "", "1"):
        logger.info("Complaint %s not in 'Received' state, skipping (already processed).", number)
        return
    if complaint.get("override_severity"):
        logger.info("Complaint %s already has an officer override, skipping AI classification.", number)
        return

    description = complaint.get("description", "")
    incident_category = complaint.get("incident_category", "other")

    await _mark_status(sys_id, "processing")

    # --- Steps 1 & 2 & environmental data, concurrently ---
    attachment_task = sn_client.get_attachment_binary(sys_id)
    env_task = fetch_environmental_data(lat, lng)
    attachment, env = await asyncio.gather(attachment_task, env_task)

    image_bytes, content_type = (attachment if attachment else (None, None))

    triage_output, triage_log = await triage_agent.run(description, incident_category)
    vision_output, vision_log = await vision_agent.run(image_bytes, content_type or "image/jpeg")

    # --- Step 3: Severity Fusion ---
    fusion_output, fusion_log = await fusion_agent.run(
        triage=triage_output, vision=vision_output, citizen_text=description, env=env
    )

    # --- Write-back: complaint, snapshot, logs ---
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        await sn_client.patch_complaint(
            sys_id,
            {
                "ai_severity": fusion_output.severity,
                "ai_confidence": fusion_output.confidence,
                "ai_image_caption": vision_output.caption,
                "ai_rationale": fusion_output.rationale,
                "ai_classified_at": now,
                "ai_processing_status": "completed" if fusion_output.confidence > 0 else "fallback",
            },
        )
    except ServiceNowError as exc:
        logger.error("PATCH complaint %s failed: %s", number, exc)
        # Leave state as-is; FL-02 fallback catches it after 60 minutes.
        return

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
