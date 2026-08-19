"""
Agent 5: Legal Case Summary Agent — ai-agent-specs.md Section 2, Agent 5.
Compiles evidence from complaint, inspection, findings, and facility history
into a prosecution-ready legal case narrative.
"""
import time

from openai import AsyncOpenAI

from app.config import settings
from app.logging_utils import get_logger
from app.models import AgentLogEntry

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)

SYSTEM_PROMPT = """You are the EcoSentinel Legal Case Summary Agent. You compile environmental 
compliance evidence into a structured, prosecution-ready case narrative suitable 
for regulatory enforcement proceedings.

TASK: Given a compiled evidence package containing complaint details, inspection 
findings, environmental data, and facility history, produce a structured legal 
case narrative with the following sections:

1. CASE OVERVIEW — 2-3 sentences identifying the respondent facility, the nature 
   of the alleged violation, and the regulatory framework involved.
2. CHAIN OF EVENTS — A chronological timeline from the citizen complaint through 
   the inspection, referencing dates and key actions taken.
3. EVIDENCE SUMMARY — A structured summary of all physical evidence, measurements, 
   inspector observations, and AI-assisted analysis (severity score, confidence, 
   image analysis).
4. ENVIRONMENTAL IMPACT ASSESSMENT — Analysis of the environmental conditions at 
   the time (AQI, weather, wind) and how they may have affected the spread or 
   severity of the pollution event.
5. FACILITY RISK PROFILE — Summary of the facility's compliance history, risk 
   tier, and any pattern of repeat violations.
6. RECOMMENDED ENFORCEMENT ACTION — Based on the severity of findings, facility 
   history, and environmental impact, recommend an appropriate enforcement response 
   (warning, fine, remediation order, license suspension, criminal referral).

CONSTRAINTS:
- Use formal legal language suitable for regulatory proceedings.
- Reference specific evidence items by number or type.
- Do NOT fabricate evidence or add details not present in the input.
- Do NOT make legal conclusions — frame findings as "alleged" violations.
- Preserve all measurement values and dates exactly as provided.
- Output as formatted plain text with clear section headers.
"""


async def run(evidence_package: str) -> tuple[str, AgentLogEntry]:
    start = time.monotonic()

    if not evidence_package or len(evidence_package.strip()) < 10:
        output = "Insufficient evidence provided. Manual case narrative required."
        log = _log_entry(evidence_package, output, "error", start, error="Evidence too short")
        return output, log

    user_prompt = f"Evidence Package:\n{evidence_package}"

    try:
        resp = await _client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
        )
        output = resp.choices[0].message.content.strip()
        log = _log_entry(evidence_package, output, "success", start)
        return output, log

    except Exception as exc:
        logger.error("Legal Case Summary Agent failed: %s", exc)
        # Fallback: use raw evidence package as the narrative
        output = f"AI narrative generation failed. Raw evidence package:\n\n{evidence_package}"
        log = _log_entry(evidence_package, output, "error", start, error=str(exc))
        return output, log


def _log_entry(evidence, output, status, start, error=None) -> AgentLogEntry:
    return AgentLogEntry(
        agent_name="legal_case_summary_agent",
        agent_type="external",
        linked_table="x_snc_ecosentine_0_legal_case",
        linked_record="",
        input_summary=f"evidence_package={evidence[:200]!r}",
        output_summary=f"Generated narrative of {len(output)} chars",
        status=status,
        error_details=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
