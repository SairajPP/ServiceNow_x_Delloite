"""
Agent 6: Leadership Insights Agent — ai-agent-specs.md Section 2, Agent 6.
Transforms a JSON payload of weekly metrics into an executive narrative summary.
"""
import time

from openai import AsyncOpenAI

from app.config import settings
from app.logging_utils import get_logger
from app.models import AgentLogEntry

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)

SYSTEM_PROMPT = """You are the EcoSentinel Leadership Insights Agent. You analyze 
weekly environmental platform metrics and produce an executive-level plain language 
summary for directors.

TASK: Given a JSON payload of weekly platform metrics, produce a 3-5 paragraph 
summary covering:
1. Volume headline (total complaints)
2. Severity distribution (how many High/Medium/Low — flag any spike)
3. Facility risk alerts (which facilities crossed the 80+ critical threshold)
4. Enforcement activity (inspections completed, violations confirmed, legal cases)
5. Operational flags (SLA breaches, inspector capacity concerns, zone hotspots)

TONE: Authoritative but accessible. Write as a senior analyst briefing a director. 
Use specific numbers, not vague qualifiers ("12 complaints" not "several complaints").

CONSTRAINTS:
- Keep to 3-5 paragraphs maximum.
- Do NOT include raw data tables — this is a narrative summary.
- Do NOT make policy recommendations beyond operational suggestions.
- Output as plain text paragraphs only.
"""

async def run(metrics_json: str) -> tuple[str, AgentLogEntry]:
    start = time.monotonic()

    if not metrics_json or len(metrics_json.strip()) < 5:
        output = "Insufficient data provided for weekly insights generation."
        log = _log_entry(metrics_json, output, "error", start, error="Empty metrics JSON")
        return output, log

    user_prompt = f"Weekly Metrics JSON:\n{metrics_json}"

    try:
        resp = await _client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1000,
        )
        output = resp.choices[0].message.content.strip()
        log = _log_entry(metrics_json, output, "success", start)
        return output, log

    except Exception as exc:
        logger.error("Leadership Insights Agent failed: %s", exc)
        output = f"AI summary generation failed. Raw metrics:\n\n{metrics_json}"
        log = _log_entry(metrics_json, output, "error", start, error=str(exc))
        return output, log

def _log_entry(inputs, output, status, start, error=None) -> AgentLogEntry:
    return AgentLogEntry(
        agent_name="leadership_insights_agent",
        agent_type="external",
        linked_table="", # Not linking to a specific record since this is a global summary
        linked_record="",
        input_summary=f"metrics_json={inputs[:200]!r}",
        output_summary=f"Generated summary of {len(output)} chars",
        status=status,
        error_details=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
