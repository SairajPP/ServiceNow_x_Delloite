"""
Agent 2: OpenAI Vision Agent (External) — ai-agent-specs.md Section 2, Agent 2.
Registered conceptually via AI Agent Fabric; here it's the actual
GPT-4o Vision call, per integration-contract.md Section 2.4.
"""
import time
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings
from app.logging_utils import get_logger
from app.models import AgentLogEntry, VisionOutput
from app.servicenow_client import image_to_data_url

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)

SYSTEM_PROMPT = """You are an environmental incident image analyst. Analyse the provided photo
and produce a concise, factual description of any environmental violation or
pollution visible in the image.

TASK: Output ONLY a single sentence describing what you see. Focus on:
- Type of pollution (smoke, effluent, waste, spill, noise source, etc.)
- Colour, density, and extent of the visible issue
- Any identifiable source (chimney, pipe, vehicle, construction site, etc.)

CONSTRAINTS:
- Do NOT speculate about health impacts or legal consequences.
- Do NOT reference the location or suggest actions.
- If no environmental issue is visible, output exactly:
  "No visible environmental violation detected in the image."
- Keep output under 100 words."""

FALLBACK_CAPTION = "Image analysis unavailable"


async def run(image_bytes: Optional[bytes], content_type: str) -> tuple[VisionOutput, AgentLogEntry]:
    start = time.monotonic()

    if image_bytes is None:
        output = VisionOutput(caption=FALLBACK_CAPTION)
        log = _log_entry("no attachment", output, "error", start, error="No photo attached")
        return output, log

    data_url = image_to_data_url(image_bytes, content_type)

    try:
        resp = await _client.chat.completions.create(
            model=settings.groq_vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=100,
        )
        caption = resp.choices[0].message.content.strip()
        # Output adapter: raw OpenAI text -> { "caption": "..." } schema,
        # per integration-contract.md Section 2.4 field mapping note.
        output = VisionOutput(caption=caption)
        log = _log_entry("photo attached", output, "success", start)
        return output, log

    except Exception as exc:
        logger.error("Vision Agent failed: %s", exc)
        output = VisionOutput(caption=FALLBACK_CAPTION)
        log = _log_entry("photo attached", output, "error", start, error=str(exc))
        return output, log


def _log_entry(input_desc, output, status, start, error=None) -> AgentLogEntry:
    return AgentLogEntry(
        agent_name="openai_vision",
        agent_type="external",
        linked_table="x_eco_complaint",
        linked_record="",
        input_summary=input_desc,
        output_summary=f"caption={output.caption}",
        status=status,
        error_details=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
