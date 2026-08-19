"""
Agent 1: Triage Agent — ai-agent-specs.md Section 2, Agent 1.
Spec says "Native — AI Agent Studio" in the target architecture; here it
runs as an LLM call inside FastAPI so the whole pipeline is runnable
standalone. Swap `run()` for a Now Assist Agent Studio call later without
touching pipeline.py.
"""
import json
import time

from openai import AsyncOpenAI

from app.config import settings
from app.logging_utils import get_logger
from app.models import AgentLogEntry, TriageOutput

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)

SYSTEM_PROMPT = """You are the EcoSentinel Triage Agent, an environmental compliance assistant
for a regulatory agency.

ROLE: You perform initial text-based triage of citizen-submitted environmental
complaints. You analyse the citizen's free-text description to extract structured
signals before the full severity classification runs.

TASK: Given the citizen's description and their selected incident category, produce
a structured triage output containing:
1. Extracted pollution type keywords (e.g., "smoke", "effluent", "chemical smell",
   "noise", "dust", "dumped waste").
2. Urgency signals detected in the text (e.g., "children nearby", "spreading fast",
   "ongoing for weeks", "health impact", "fire risk").
3. An initial urgency flag: LOW, MEDIUM, or HIGH — based solely on the text.
   This is a preliminary signal, NOT the final severity classification.
4. A one-sentence summary of the complaint suitable for a work note.

CONSTRAINTS:
- Do NOT assign a final severity. That is done by the Severity Fusion Agent
  after combining your output with image analysis and environmental data.
- Do NOT attempt to verify or dispute the citizen's claims.
- Do NOT generate any response addressed to the citizen.
- Output ONLY the structured JSON format below.

OUTPUT FORMAT (strict JSON):
{
  "pollution_keywords": ["keyword1", "keyword2"],
  "urgency_signals": ["signal1", "signal2"],
  "initial_urgency": "LOW | MEDIUM | HIGH",
  "summary": "One-sentence summary of the complaint."
}"""


async def run(description: str, incident_category: str) -> tuple[TriageOutput, AgentLogEntry]:
    start = time.monotonic()

    if not description or len(description.strip()) < 5:
        output = TriageOutput(
            initial_urgency="MEDIUM",
            summary="Insufficient description provided. Manual review recommended.",
        )
        log = _log_entry(description, incident_category, output, "success", start)
        return output, log

    user_prompt = f"Citizen description: {description}\nIncident category: {incident_category}"

    try:
        resp = await _client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        raw = resp.choices[0].message.content
        parsed = json.loads(raw)
        output = TriageOutput(**parsed)
        log = _log_entry(description, incident_category, output, "success", start)
        return output, log

    except Exception as exc:  # malformed JSON, timeout, API error, etc.
        logger.error("Triage Agent failed: %s", exc)
        # Fail-open per spec: forward raw description, don't block the pipeline.
        output = TriageOutput(initial_urgency="MEDIUM", summary=description[:200])
        log = _log_entry(description, incident_category, output, "error", start, error=str(exc))
        return output, log


def _log_entry(description, incident_category, output, status, start, error=None) -> AgentLogEntry:
    return AgentLogEntry(
        agent_name="triage_agent",
        agent_type="native",
        linked_table="x_snc_ecosentine_0_complaint",
        linked_record="",  # filled in by pipeline once sys_id is known
        input_summary=f"description={description[:200]!r} category={incident_category}",
        output_summary=f"initial_urgency={output.initial_urgency}; summary={output.summary}",
        status=status,
        error_details=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
