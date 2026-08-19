"""
Agent 2: OpenAI Vision Agent (External) — ai-agent-specs.md Section 2, Agent 2.
Registered conceptually via AI Agent Fabric; here it runs as a Groq
vision model call, per integration-contract.md Section 2.4.
"""
import time
import re
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings
from app.logging_utils import get_logger
from app.models import AgentLogEntry, VisionOutput
from app.servicenow_client import image_to_data_url

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=settings.nvidia_api_key, base_url=settings.nvidia_base_url)

SYSTEM_PROMPT = """You are an incident image analyst. Analyse the provided photo 
and produce a concise, factual description of any environmental violation, pollution, 
or infrastructure damage (such as potholes or broken roads) visible in the image.

TASK: Output ONLY a single sentence describing what you see. Focus on:
- Type of issue (smoke, effluent, waste, spill, pothole, road damage, etc.)
- Characteristics like colour, size, or extent of the visible issue
- Any identifiable context (chimney, pipe, road surface, etc.)

CONSTRAINTS:
- Do NOT speculate about health impacts, safety risks, or legal consequences.
- Do NOT reference the location or suggest actions.
- If no issue is visible, output exactly: 
  "No visible environmental or infrastructure issue detected in the image."
- Keep output under 4000 words."""

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
            model=settings.nvidia_vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=1500,
        )
        raw_caption = resp.choices[0].message.content.strip()
        
        # Remove <think>...</think> blocks which some models generate
        caption = re.sub(r'<think>.*?</think>', '', raw_caption, flags=re.DOTALL).strip()
        if not caption:
            caption = raw_caption # Fallback if regex stripped everything

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
        linked_table="x_snc_ecosentine_0_complaint",
        linked_record="",
        input_summary=input_desc,
        output_summary=f"caption={output.caption}",
        status=status,
        error_details=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
