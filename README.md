# EcoSentinel AI — FastAPI Backend

This is the part of the EcoSentinel architecture that lives **outside**
ServiceNow — the Severity Fusion runtime that Now Assist can't do natively
because it needs to call OpenAI Vision, OpenWeatherMap, and WAQI, then fuse
all three with the citizen's text before writing back. Built from
`architecture-improvement-plan.md`, `integration-contract.md`,
`ai-agent-specs.md`, and `tables.md`.

## What it does

1. `POST /webhook/complaint` — FL-01 pings this when a citizen submits a
   complaint. Checks the bearer token, checks idempotency (SQLite, 5-min
   window), returns `202 Accepted` immediately, and kicks off the pipeline
   as a background task.
2. Background pipeline (`TASK-ECO-CLASSIFY`):
   - GETs the complaint + photo attachment from ServiceNow
   - Runs Triage Agent (text) + Vision Agent (photo) + Weather/AQI lookups concurrently
   - Runs the Severity Fusion Agent over all four signals
   - PATCHes `ai_severity` / `ai_confidence` / `ai_rationale` / `ai_image_caption` back to the complaint
   - POSTs an Environmental Snapshot record
   - POSTs one Agent Decision Log entry per agent (triage, vision, fusion)

Every failure mode from `integration-contract.md` Section 6 (OpenAI timeout,
weather/AQI down, missing photo, SN auth failure, duplicate webhook) degrades
gracefully instead of crashing — worst case, ServiceNow's own `FL-02`
60-minute scheduled flow catches a stuck complaint.

## Setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # fill in your real keys
uvicorn app.main:app --reload --port 8000
```

Check it's alive: `curl http://localhost:8000/health`

## Wiring it to your PDI

In ServiceNow, per `integration-contract.md` Section 4:
- Create the `ecosentinel.api` integration user (web-service-only, least-privilege role)
- Create the Outbound REST Message `x_eco.EcoSentinel_Webhook` pointing `FL-01` at
  `https://<your-fastapi-host>/webhook/complaint` with header
  `Authorization: Bearer <FASTAPI_WEBHOOK_BEARER_TOKEN>`

For local dev without a public URL, tunnel it (ngrok, Cloudflare Tunnel, etc.)
so your PDI can actually reach `POST /webhook/complaint`.

## Project layout

```
app/
  main.py              FastAPI app, webhook route, auth
  config.py            .env-driven settings
  models.py            Pydantic schemas matching the integration contract
  servicenow_client.py Table API + Attachment API client
  external_apis.py     OpenWeatherMap + WAQI, unit conversion
  idempotency.py        SQLite dedup store (swap for Redis at scale)
  pipeline.py           TASK-ECO-CLASSIFY orchestrator
  agents/
    triage_agent.py     Agent 1 — text triage
    vision_agent.py      Agent 2 — GPT-4o Vision captioning
    fusion_agent.py       Agent 3 — severity fusion reasoning
```

## Notes / what's intentionally out of scope here

- **Auth to ServiceNow** uses HTTP Basic, which the contract says is fine
  for a PDI demo but should move to OAuth 2.0 before anything real
  (`architecture-improvement-plan.md`, P1 item). Swap `ServiceNowClient._auth`
  for an OAuth client-credentials flow when you get there.
- **Idempotency store is SQLite**, i.e. single-process. Fine for a demo;
  move to Redis if you run multiple uvicorn workers.
- **Inspection Report Agent, Legal Case Summary Agent, and Leadership
  Insights Agent** (Agents 4-6 in `ai-agent-specs.md`) are native
  Now Assist agents triggered by Flow Designer inside ServiceNow itself —
  they don't need to live in this backend, so they're not implemented here.
- No email alerting is wired up for the "ServiceNow Authentication Failure"
  failure mode — currently just logs. Add an SMTP/SendGrid call in
  `pipeline.py` if you want that for the demo.
