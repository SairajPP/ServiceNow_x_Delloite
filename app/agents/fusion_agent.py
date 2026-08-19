"""
Agent 3: Severity Fusion Agent — ai-agent-specs.md Section 2, Agent 3.
This is the piece that MUST live outside ServiceNow: it needs to reason
over Weather + AQI + Vision + Triage together, which native Now Assist
agents can't do (they can't call multiple external APIs and fuse the
results in one step). Registered conceptually with AI Agent Fabric for
governance; this module is the actual runtime.
"""
import json
import time

from openai import AsyncOpenAI

from app.config import settings
from app.logging_utils import get_logger
from app.models import AgentLogEntry, EnvironmentalData, FusionOutput, TriageOutput, VisionOutput

logger = get_logger(__name__)

_client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)

SYSTEM_PROMPT = """You are the EcoSentinel Severity Fusion Agent, the core reasoning engine for an
environmental regulatory compliance platform. Your job is to combine four separate
data signals into a single, explainable severity classification.

ROLE: Environmental severity classifier. You produce the FINAL severity label that
determines how quickly an inspector is dispatched and which SLA applies.

INPUTS YOU WILL RECEIVE:
1. TRIAGE OUTPUT: Keywords and urgency signals extracted from the citizen's text.
2. IMAGE CAPTION: A one-sentence description of the citizen's photo (may say
   "Image analysis unavailable" if the photo could not be analysed).
3. CITIZEN TEXT: The original free-text description submitted by the citizen.
4. ENVIRONMENTAL DATA: Live AQI reading, wind speed, wind direction, and weather
   conditions at the complaint's GPS coordinates.

REASONING RULES (you MUST follow these):

Rule 1 — Cross-reference visual and environmental signals:
  - If the image shows dense smoke/emissions AND AQI is > 150 (Unhealthy+),
    this is a STRONG signal for HIGH severity.
  - If the image shows pollution BUT AQI is < 50 (Good), the visual evidence
    may be stale or misleading — classify as MEDIUM unless other signals agree.

Rule 2 — Wind speed amplification:
  - Wind speed < 5 km/h means pollutants ACCUMULATE rather than disperse.
    This INCREASES severity by one level (Low->Medium, Medium->High).
  - Wind speed > 20 km/h means rapid dispersal. This does NOT decrease severity
    (pollution still happened) but reduces the "accumulation" rationale.

Rule 3 — Urgency signal boosting:
  - If triage detected urgency signals like "children nearby", "hospital nearby",
    "drinking water source", or "spreading fast", boost confidence by +10 and
    consider upgrading severity by one level.

Rule 4 — No image fallback:
  - If the image caption says "Image analysis unavailable" or "No visible
    environmental violation", rely on citizen text + environmental data only.
    Reduce confidence by -15 to reflect the missing visual signal.

Rule 5 — Confidence calculation:
  - Output a realistic confidence score between 0 and 95 based on the strength of the combined evidence.
  - Very strong, aligned evidence (e.g., clear image + corroborating AQI + detailed text): 85-95%
  - Strong visual evidence but unrelated AQI (e.g., a pothole where AQI is irrelevant): 75-85%
  - Mixed or weak evidence (e.g., vague text, minor issue): 50-70%
  - Image unavailable: Cap confidence at 75%.
  - Final confidence must be an integer between 0 and 95.

OUTPUT FORMAT (strict JSON):
{
  "severity": "LOW | MEDIUM | HIGH",
  "confidence": 0-100,
  "rationale": "One paragraph explaining the reasoning, referencing each input signal."
}

CONSTRAINTS:
- You MUST output valid JSON and nothing else.
- You MUST reference specific data values (AQI number, wind speed, image caption)
  in your rationale - never say "based on the data" without citing the data.
- You MUST NOT auto-close the complaint or trigger any downstream action.
- You MUST NOT override a previous officer override if one exists.
- If confidence < 50, append to rationale: "LOW CONFIDENCE - recommend manual
  officer review before dispatch."
- You MUST never output confidence above 95."""

FALLBACK_RATIONALE = (
    "FALLBACK: Severity Fusion Agent returned invalid output. "
    "Default MEDIUM applied for manual review."
)


async def run(
    triage: TriageOutput,
    vision: VisionOutput,
    citizen_text: str,
    env: EnvironmentalData,
) -> tuple[FusionOutput, AgentLogEntry]:
    start = time.monotonic()

    user_prompt = _build_user_prompt(triage, vision, citizen_text, env)

    try:
        resp = await _client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
        )
        raw = resp.choices[0].message.content
        parsed = json.loads(raw)

        severity = str(parsed["severity"]).lower()
        if severity not in ("low", "medium", "high"):
            raise ValueError(f"Unexpected severity value: {severity}")

        confidence = max(0, min(95, int(parsed["confidence"])))
        rationale = parsed["rationale"]

        output = FusionOutput(severity=severity, confidence=confidence, rationale=rationale)
        log = _log_entry(user_prompt, output, "success", start)
        return output, log

    except Exception as exc:
        logger.error("Severity Fusion Agent failed: %s", exc)
        output = FusionOutput(severity="medium", confidence=0, rationale=FALLBACK_RATIONALE)
        log = _log_entry(user_prompt, output, "fallback", start, error=str(exc))
        return output, log


def _build_user_prompt(
    triage: TriageOutput, vision: VisionOutput, citizen_text: str, env: EnvironmentalData
) -> str:
    return f"""TRIAGE OUTPUT:
{json.dumps(triage.model_dump(), indent=2)}

IMAGE CAPTION: {vision.caption}

CITIZEN TEXT: {citizen_text}

ENVIRONMENTAL DATA:
- AQI: {env.aqi_value} ({env.aqi_category})
- Primary pollutant: {env.primary_pollutant}
- Wind speed: {env.wind_speed} km/h, direction {env.wind_direction}
- Weather: {env.weather_condition}, temp {env.temperature} C, humidity {env.humidity}%
- Data source status: {env.data_source}"""


def _log_entry(input_summary, output, status, start, error=None) -> AgentLogEntry:
    return AgentLogEntry(
        agent_name="severity_fusion",
        agent_type="external",
        linked_table="x_snc_ecosentine_0_complaint",
        linked_record="",
        input_summary=input_summary[:2000],
        output_summary=(
            f"severity={output.severity} confidence={output.confidence} "
            f"rationale={output.rationale[:500]}"
        ),
        confidence=output.confidence,
        status=status,
        error_details=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )
