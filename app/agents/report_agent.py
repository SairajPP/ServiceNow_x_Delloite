"""
Agent 4: Inspection Report Agent — ai-agent-specs.md Section 2, Agent 4.
Transforms raw inspector notes into a structured professional report.
"""
import time
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings
from app.logging_utils import get_logger
from app.models import AgentLogEntry
from app.servicenow_client import image_to_data_url

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)

SYSTEM_PROMPT = """You are the EcoSentinel Inspection Report Agent. You transform an inspector's raw 
field notes and evidence findings into a structured, professional inspection report 
suitable for regulatory filing.

TASK: Given the inspector's raw notes and a list of individual findings (with types, 
descriptions, measurements, and severity assessments), produce a structured report 
with the following sections:

1. EXECUTIVE SUMMARY (2-3 sentences summarising the inspection outcome)
2. SITE DESCRIPTION (location, facility type, conditions observed on arrival)
3. FINDINGS (numbered list, each with: finding type, description, measurement if 
   applicable, and severity assessment)
4. EVIDENCE SUMMARY (count of photos, measurements, samples collected)
5. CONCLUSION (violation confirmed or dismissed, with brief justification)
6. RECOMMENDATIONS (suggested next steps: monitoring, remediation, penalty, etc.)

CONSTRAINTS:
- Use formal, regulatory language suitable for legal proceedings.
- Do NOT add information not present in the inspector's notes or findings.
- Do NOT speculate about causes beyond what the inspector documented.
- Do NOT change the inspector's severity assessments on individual findings.
- Preserve all measurement values exactly as recorded.
- Output as formatted plain text with clear section headers (not JSON, not Markdown).
"""


async def run(raw_notes: str, image_bytes: Optional[bytes] = None, content_type: Optional[str] = None) -> tuple[str, AgentLogEntry]:
    start = time.monotonic()

    if not raw_notes or len(raw_notes.strip()) < 5:
        output = "Insufficient raw notes provided. Manual report generation required."
        log = _log_entry(raw_notes, output, "error", start, error="Notes too short")
        return output, log

    user_prompt = f"Inspector Raw Notes:\n{raw_notes}"

    if image_bytes and content_type:
        data_url = image_to_data_url(image_bytes, content_type)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]
        model_to_use = settings.groq_vision_model
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        model_to_use = settings.groq_model

    try:
        resp = await _client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            max_tokens=1500,
        )
        output = resp.choices[0].message.content.strip()
        log = _log_entry(raw_notes, output, "success", start)
        return output, log

    except Exception as exc:  
        logger.error("Inspection Report Agent failed: %s", exc)
        output = f"AI report generation failed. Raw notes:\n\n{raw_notes}"
        log = _log_entry(raw_notes, output, "error", start, error=str(exc))
        return output, log


def _log_entry(raw_notes, output, status, start, error=None) -> AgentLogEntry:
    return AgentLogEntry(
        agent_name="inspection_report_agent",
        agent_type="external", # Running outside SN
        linked_table="x_snc_ecosentine_0_inspection",
        linked_record="",  
        input_summary=f"raw_notes={raw_notes[:200]!r}",
        output_summary=f"Generated report of {len(output)} chars",
        status=status,
        error_details=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
