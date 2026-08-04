"""
Central config. Everything pulled from .env — see .env.example.
Matches integration-contract.md Section 5 (FastAPI-Side Setup Checklist).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ServiceNow
    servicenow_instance_url: str
    servicenow_user: str
    servicenow_password: str

    # Inbound webhook auth (checked on POST /webhook/complaint)
    fastapi_webhook_bearer_token: str

    # External APIs
    groq_api_key: str
    weather_api_key: str
    aqi_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_vision_model: str = "llama-3.2-90b-vision-preview"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Behavior
    idempotency_window_seconds: int = 300
    request_timeout_seconds: int = 15

    log_level: str = "INFO"

    @property
    def sn_table_url(self) -> str:
        return f"{self.servicenow_instance_url.rstrip('/')}/api/now/table"

    @property
    def sn_attachment_url(self) -> str:
        return f"{self.servicenow_instance_url.rstrip('/')}/api/now/attachment"


settings = Settings()
