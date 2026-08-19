"""
EcoSentinel AI — FastAPI backend.
This is the piece of the architecture that lives outside ServiceNow —
see architecture-improvement-plan.md ("Severity Fusion runtime: FastAPI
backend") and integration-contract.md Section 1.

Run:
    uvicorn app.main:app --reload --port 8000

Endpoints:
    POST /webhook/complaint   <- called by FL-01 when a complaint is inserted
    GET  /health              <- liveness check
"""
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, status

from app.config import settings
from app.idempotency import check_and_mark, init_db
from app.logging_utils import get_logger
from app.models import WebhookAck, WebhookPing, InspectionWebhook, LegalCaseWebhook, LeadershipWebhook, LeadershipResponse
from app.pipeline import run_pipeline, run_inspection_pipeline, run_legal_pipeline, run_leadership_pipeline

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("EcoSentinel FastAPI backend starting up.")
    yield
    logger.info("EcoSentinel FastAPI backend shutting down.")


app = FastAPI(title="EcoSentinel AI Backend", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/complaint", response_model=WebhookAck, status_code=status.HTTP_202_ACCEPTED)
async def webhook_complaint(
    payload: WebhookPing,
    background_tasks: BackgroundTasks,
    authorization: str = Header(default=""),
):
    """
    Section 2.1 of integration-contract.md.
    Validates the bearer token, checks idempotency, returns 202 immediately,
    and runs the classification pipeline (TASK-ECO-CLASSIFY) in the background.
    """
    _check_auth(authorization)

    if not check_and_mark(payload.sys_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Complaint {payload.sys_id} already queued/processed in the last "
                   f"{settings.idempotency_window_seconds}s.",
        )

    background_tasks.add_task(
        run_pipeline, payload.sys_id, payload.number, payload.lat, payload.lng
    )

    logger.info("Queued classification for %s (%s)", payload.number, payload.sys_id)
    return WebhookAck(sys_id=payload.sys_id)


def _check_auth(authorization: str) -> None:
    expected = f"Bearer {settings.fastapi_webhook_bearer_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing bearer token")

@app.post("/webhook/inspection", response_model=WebhookAck, status_code=status.HTTP_202_ACCEPTED)
async def webhook_inspection(
    payload: InspectionWebhook,
    background_tasks: BackgroundTasks,
    authorization: str = Header(default=""),
):
    """
    Triggered by FL-08 when an inspector submits their raw notes.
    """
    _check_auth(authorization)

    background_tasks.add_task(
        run_inspection_pipeline, payload.sys_id, payload.number, payload.raw_notes
    )

    logger.info("Queued inspection report for %s (%s)", payload.number, payload.sys_id)
    return WebhookAck(sys_id=payload.sys_id, message="Inspection report generation queued")


@app.post("/webhook/legal-case", response_model=WebhookAck, status_code=status.HTTP_202_ACCEPTED)
async def webhook_legal_case(
    payload: LegalCaseWebhook,
    background_tasks: BackgroundTasks,
    authorization: str = Header(default=""),
):
    """
    Triggered by FL-07 when a new legal case is created.
    Receives compiled evidence and generates a prosecution-ready narrative.
    """
    _check_auth(authorization)

    background_tasks.add_task(
        run_legal_pipeline, payload.record_sys_id, payload.number, payload.evidence_package
    )

    logger.info("Queued legal case narrative for %s (%s)", payload.number, payload.record_sys_id)
    return WebhookAck(sys_id=payload.record_sys_id, message="Legal case narrative generation queued")

@app.post("/webhook/leadership", response_model=LeadershipResponse, status_code=status.HTTP_200_OK)
async def webhook_leadership(
    payload: LeadershipWebhook,
    authorization: str = Header(None)
):
    """
    Triggered by FL-10 to generate a weekly leadership insights summary.
    This is synchronous because the ServiceNow scheduled job needs the summary
    immediately to send it out in an email.
    """
    _check_auth(authorization)

    import json
    metrics_json = json.dumps(payload.metrics, indent=2)
    summary = await run_leadership_pipeline(metrics_json)
    
    return LeadershipResponse(summary=summary)
