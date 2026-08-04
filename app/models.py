"""
Schemas mirroring integration-contract.md Section 2 and Section 3
(field mapping table). Keep field names identical to the contract so
the ServiceNow side never needs a translation layer.
"""
from typing import Optional

from pydantic import BaseModel, Field


class WebhookPing(BaseModel):
    """Section 2.1 — inbound payload from FL-01."""
    sys_id: str
    number: str
    table: str = "x_eco_complaint"
    lat: float
    lng: float


class WebhookAck(BaseModel):
    status: str = "accepted"
    message: str = "Complaint analysis queued"
    sys_id: str


class TriageOutput(BaseModel):
    pollution_keywords: list[str] = Field(default_factory=list)
    urgency_signals: list[str] = Field(default_factory=list)
    initial_urgency: str = "MEDIUM"  # LOW | MEDIUM | HIGH
    summary: str = ""


class VisionOutput(BaseModel):
    caption: str


class EnvironmentalData(BaseModel):
    aqi_value: Optional[int] = None
    aqi_category: Optional[str] = None
    primary_pollutant: Optional[str] = None
    wind_speed: Optional[float] = None  # km/h
    wind_direction: Optional[str] = None
    temperature: Optional[float] = None  # Celsius
    weather_condition: Optional[str] = None
    humidity: Optional[int] = None
    data_source: str = "success"  # success | partial | error
    aqi_source: str = "WAQI API"
    weather_source: str = "OpenWeatherMap API"


class FusionOutput(BaseModel):
    severity: str  # low | medium | high
    confidence: int
    rationale: str


class AgentLogEntry(BaseModel):
    agent_name: str
    agent_type: str  # native | external
    linked_table: str
    linked_record: str
    linked_record_number: Optional[str] = None
    input_summary: str
    output_summary: str
    confidence: Optional[int] = None
    status: str  # success | error | timeout | fallback
    error_details: Optional[str] = None
    duration_ms: Optional[int] = None
