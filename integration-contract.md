# EcoSentinel AI — Integration Contract Specification

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_eco_`  
> **Reference Documents**: [tables.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/tables.md) · [business-rules-client-scripts.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/business-rules-client-scripts.md) · [roles-groups-users.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/roles-groups-users.md) · [flow-designer-flows.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/flow-designer-flows.md)  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

# Section 1: Architecture Overview

The EcoSentinel AI integration establishes a secure, asynchronous bi-directional pipeline between the ServiceNow PDI and the external FastAPI backend. The runtime flow is designed as follows:

1. **ServiceNow → FastAPI**: When a citizen submits a complaint via the Service Portal, Flow Designer `FL-01` sends a lightweight HTTP POST "webhook ping" containing only the record's metadata (`sys_id`, `number`) to the FastAPI backend. `BR-C02` is documented only as a disabled fallback pattern.
2. **FastAPI → ServiceNow (Data Fetch)**: FastAPI receives the ping and asynchronously calls the ServiceNow Table API and Attachment API using OAuth 2.0 where available, or a tightly restricted Basic Auth service account for PDI demos. FastAPI pulls the full complaint details (coordinates, description) and downloads the raw photo binary.
3. **FastAPI → External AI & Environment APIs**: FastAPI orchestrates parallel requests to **OpenAI** (GPT-4o Vision for image analysis), the **Weather API** (for wind speed/conditions), and the **AQI API** (for air quality index).
4. **FastAPI → ServiceNow (Write-Back)**: The Severity Fusion Agent on FastAPI fuses these inputs, computes the final severity/confidence/rationale, and performs a PATCH request back to ServiceNow to update the Complaint record. Additionally, it POSTs the environmental snapshot data to the Snapshot table and log records to the Agent Decision Log.

### Authentication Design
- **ServiceNow Outbound to FastAPI**: Authenticates using a static `Authorization: Bearer <API_TOKEN>` header managed in ServiceNow Credentials.
- **FastAPI Outbound to ServiceNow**: Prefer OAuth 2.0 with a dedicated integration user and scoped API permissions. For a PDI / hackathon demo, Basic Auth is acceptable only if the `ecosentinel.api` account has `Web service access only = True`, strong rotated credentials, and ACL access limited to the tables specified in `roles-groups-users.md`.

```
 ServiceNow (PDI)                                         FastAPI Backend
+--------------------+                                   +-------------------+
|                    | ---- (1) POST Webhook Ping -----> |                   |
|                    |      (sys_id, Bearer Token)       |                   |
|                    |                                   |                   |
|                    | <--- (2) GET Complaint & Photo -- |                   |
|                    |      (Table & Attachment API)     |                   |
|                    |                                   |                   |
|                    |                                   | -- (3) Call APIs: |
|                    |                                   |    * OpenAI GPT-4o|
|                    |                                   |    * Weather API  |
|                    |                                   |    * AQI API      |
|                    |                                   |                   |
|                    | <--- (4) PATCH AI Results ------- |                   |
|                    |      (Table API & logs)           |                   |
+--------------------+                                   +-------------------+
```

---

# Section 2: Endpoint-by-Endpoint Contract

---

## 2.1 — Webhook Ping

| Property | Value |
|---|---|
| **Direction** | ServiceNow → FastAPI |
| **Endpoint / Method** | `POST /webhook/complaint` |
| **Trigger** | Insert of `x_eco_complaint` record via `FL-01` |
| **Auth Method** | `Authorization: Bearer <API_TOKEN>` header |

### Request Payload

```json
{
  "sys_id": "8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
  "number": "ES20260731-0042",
  "table": "x_eco_complaint",
  "lat": 18.9629,
  "lng": 72.8277
}
```

### Response Payload (HTTP 202 Accepted)

```json
{
  "status": "accepted",
  "message": "Complaint analysis queued",
  "sys_id": "8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d"
}
```

### Timeout & Retry Behavior
- **Timeout**: 10 seconds.
- **Retry**: Flow Designer will attempt 3 retries with exponential backoff (15s, 60s, 300s).
- **Final Failure**: If the FastAPI backend is completely unreachable, the webhook transaction is logged as failed in ServiceNow. The complaint remains in "Received" state, and the scheduled fallback flow (`FL-02`) will catch it after 60 minutes, applying a default Medium severity.

---

## 2.2 — GET Complaint Record

| Property | Value |
|---|---|
| **Direction** | FastAPI → ServiceNow |
| **Endpoint / Method** | `GET /api/now/table/x_eco_complaint/{sys_id}` |
| **Trigger** | Receipt of Webhook Ping |
| **Auth Method** | OAuth 2.0 preferred. PDI demo may use HTTP Basic Auth (User: `ecosentinel.api`) with web-service-only and least-privilege ACLs. |

### Request URL
`https://[INSTANCE].service-now.com/api/now/table/x_eco_complaint/8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d`

### Response Payload (HTTP 200 OK)

```json
{
  "result": {
    "sys_id": "8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
    "number": "ES20260731-0042",
    "description": "Thick black smoke emitting from the factory boiler chimney since morning. It has a chemical smell.",
    "incident_category": "air_pollution",
    "incident_lat": "18.962900",
    "incident_lng": "72.827700",
    "incident_address": "Chhatrapati Shivaji Terminus Area, Mumbai",
    "sys_created_on": "2026-07-31 10:40:00"
  }
}
```

---

## 2.3 — GET Photo Attachment

| Property | Value |
|---|---|
| **Direction** | FastAPI → ServiceNow |
| **Endpoint / Method** | `GET /api/now/attachment?sysparm_query=table_sys_id={sys_id}` (Query Metadata) then `GET /api/now/attachment/{attachment_sys_id}/file` (Download Stream) |
| **Trigger** | Processing complaint data in FastAPI |
| **Auth Method** | OAuth 2.0 preferred. PDI demo may use HTTP Basic Auth (User: `ecosentinel.api`) with web-service-only and least-privilege ACLs. |

### Step 1: Look up Attachment Metadata
FastAPI calls `GET https://[INSTANCE].service-now.com/api/now/attachment?sysparm_query=table_name=x_eco_complaint^table_sys_id=8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d`

**Response:**
```json
{
  "result": [
    {
      "sys_id": "0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
      "file_name": "smoke_plume.jpg",
      "content_type": "image/jpeg",
      "size_bytes": "204850"
    }
  ]
}
```

### Step 2: Download Attachment Binary
FastAPI calls `GET https://[INSTANCE].service-now.com/api/now/attachment/0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d/file`

**Response:** Raw binary image stream (`image/jpeg`). FastAPI reads this into memory or a temp file to pass to OpenAI.

---

## 2.4 — OpenAI GPT-4o Vision API (Internal Downstream)

| Property | Value |
|---|---|
| **Direction** | FastAPI → OpenAI API |
| **Endpoint / Method** | `POST https://api.openai.com/v1/chat/completions` |
| **Auth Method** | `Authorization: Bearer $OPENAI_API_KEY` header |

### Request Payload

```json
{
  "model": "gpt-4o",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Describe this environmental incident photo. Output ONLY a concise 1-sentence caption identifying the type of pollution or violation detected (e.g. 'Dense smoke discharging from an industrial stack' or 'Liquid effluent leaking into a creek'). If no violation is seen, say 'No visible environmental violation'."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
          }
        }
      ]
    }
  ],
  "max_tokens": 100
}
```

### Response Payload

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Dense black smoke plume discharging from an active industrial boiler chimney stack."
      }
    }
  ]
}
```

---

## 2.5 — Weather API Call (Internal Downstream)

| Property | Value |
|---|---|
| **Direction** | FastAPI → OpenWeatherMap API |
| **Endpoint / Method** | `GET https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={API_KEY}` |
| **Auth Method** | Query parameter API Key |

### Response Payload (Excerpt)

```json
{
  "weather": [{ "main": "Clouds", "description": "scattered clouds" }],
  "main": { "temp": 302.15, "humidity": 78 },
  "wind": { "speed": 1.5, "deg": 240 }
}
```

---

## 2.6 — AQI API Call (Internal Downstream)

| Property | Value |
|---|---|
| **Direction** | FastAPI → World Air Quality Index (WAQI) API |
| **Endpoint / Method** | `GET https://api.waqi.info/feed/geo:{lat};{lng}/?token={API_TOKEN}` |
| **Auth Method** | Query parameter API Key |

### Response Payload (Excerpt)

```json
{
  "status": "ok",
  "data": {
    "aqi": 210,
    "dominentpol": "pm25",
    "city": { "name": "Mumbai, India" }
  }
}
```

---

## 2.7 — PATCH Severity Result Back

| Property | Value |
|---|---|
| **Direction** | FastAPI → ServiceNow |
| **Endpoint / Method** | `PATCH /api/now/table/x_eco_complaint/{sys_id}` |
| **Trigger** | Completion of Severity Fusion reasoning engine |
| **Auth Method** | OAuth 2.0 preferred. PDI demo may use HTTP Basic Auth (User: `ecosentinel.api`) with web-service-only and least-privilege ACLs. |

### Request Payload

```json
{
  "ai_severity": "high",
  "ai_confidence": 91,
  "ai_image_caption": "Dense black smoke plume discharging from an active industrial boiler chimney stack.",
  "ai_rationale": "Image shows dense smoke. AQI at this location is 210 (Very Unhealthy). Wind speed is 1.5 km/h - pollutant likely accumulating rather than dispersing. Classified: HIGH severity, industrial air pollution.",
  "ai_classified_at": "2026-07-31 10:41:15",
  "ai_processing_status": "completed"
}
```

### Response Payload (HTTP 200 OK)

```json
{
  "result": {
    "sys_id": "8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
    "number": "ES20260731-0042",
    "ai_severity": "high",
    "state": "2"
  }
}
```

---

## 2.8 — POST Environmental Snapshot

| Property | Value |
|---|---|
| **Direction** | FastAPI → ServiceNow |
| **Endpoint / Method** | `POST /api/now/table/x_eco_env_snapshot` |
| **Trigger** | Bundled in the write-back pipeline (fired after PATCHing complaint) |
| **Auth Method** | OAuth 2.0 preferred. PDI demo may use HTTP Basic Auth (User: `ecosentinel.api`) with web-service-only and least-privilege ACLs. |

### Request Payload

```json
{
  "parent_complaint": "8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
  "aqi_value": 210,
  "aqi_category": "very_unhealthy",
  "primary_pollutant": "PM2.5",
  "wind_speed": 1.5,
  "wind_direction": "WSW",
  "temperature": 29.0,
  "weather_condition": "scattered clouds",
  "humidity": 78,
  "data_source": "success",
  "aqi_source": "WAQI API",
  "weather_source": "OpenWeatherMap API"
}
```

### Response Payload (HTTP 201 Created)

```json
{
  "result": {
    "sys_id": "5f6e7d8c9b0a1f2e3d4c5b6a7f8e9d0c",
    "parent_complaint": "8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d"
  }
}
```

---

## 2.9 — POST Agent Decision Log

| Property | Value |
|---|---|
| **Direction** | FastAPI → ServiceNow |
| **Endpoint / Method** | `POST /api/now/table/x_eco_agent_log` |
| **Trigger** | Bundled in the write-back pipeline (fired after snapshot POST) |
| **Auth Method** | OAuth 2.0 preferred. PDI demo may use HTTP Basic Auth (User: `ecosentinel.api`) with web-service-only and least-privilege ACLs. |

### Request Payload

```json
{
  "agent_name": "severity_fusion",
  "agent_type": "external",
  "linked_table": "x_eco_complaint",
  "linked_record": "8a9b2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
  "linked_record_number": "ES20260731-0042",
  "input_summary": "Image: 'dense black smoke stack'. Citizen text: 'Thick black smoke from boiler chimney'. AQI: 210. Wind speed: 1.5 km/h.",
  "output_summary": "Severity: HIGH. Confidence: 91%. Rationale: Pollutants accumulating due to low wind speed under high AQI conditions.",
  "confidence": 91,
  "status": "success"
}
```

### Response Payload (HTTP 201 Created)

```json
{
  "result": {
    "sys_id": "abc123xyz789",
    "log_id": "ADL0001042"
  }
}
```

### Architectural Note: Logging Strategy
We log the agent decision as a **separate POST call** to the Table API rather than bundling it inside the Complaint PATCH. This ensures the logging table (`x_eco_agent_log`) remains write-once/append-only via standard Table ACLs, whereas a custom bundled API could bypass these security boundary controls.

---

# Section 3: Field Mapping Table

| FastAPI Response Field | ServiceNow Table | ServiceNow Target Field | Type | Description / Format |
|---|---|---|---|---|
| `ai_severity` | `x_eco_complaint` | `ai_severity` | Choice | `low`, `medium`, `high` |
| `ai_confidence` | `x_eco_complaint` | `ai_confidence` | Integer | 0 to 100 |
| `ai_image_caption` | `x_eco_complaint` | `ai_image_caption` | String | Output from OpenAI Vision |
| `ai_rationale` | `x_eco_complaint` | `ai_rationale` | String | Human-readable reasoning string |
| `ai_classified_at` | `x_eco_complaint` | `ai_classified_at` | Date/Time | `yyyy-MM-dd HH:mm:ss` |
| `ai_processing_status` | `x_eco_complaint` | `ai_processing_status` | Choice | `completed`, `failed`, or `fallback` |
| `sys_id` | `x_eco_env_snapshot` | `parent_complaint` | Reference | sys_id of Complaint record |
| `aqi_value` | `x_eco_env_snapshot` | `aqi_value` | Integer | Numeric air quality index |
| `aqi_category` | `x_eco_env_snapshot` | `aqi_category` | Choice | Map to bands: `good`, `moderate`, `very_unhealthy`, etc. |
| `wind_speed` | `x_eco_env_snapshot` | `wind_speed` | Decimal | Metric wind speed in km/h |
| `wind_direction` | `x_eco_env_snapshot` | `wind_direction` | String | Cardinal direction (e.g. "WSW") |
| `temperature` | `x_eco_env_snapshot` | `temperature` | Decimal | Degrees Celsius |
| `weather_condition`| `x_eco_env_snapshot` | `weather_condition` | String | Descriptive weather |
| `humidity` | `x_eco_env_snapshot` | `humidity` | Integer | Humidity percentage (0-100) |
| `data_source` | `x_eco_env_snapshot` | `data_source` | Choice | `success`, `partial`, or `error` |
| `agent_name` | `x_eco_agent_log` | `agent_name` | Choice | `severity_fusion` |
| `input_summary` | `x_eco_agent_log` | `input_summary` | String | Summary of values queried |
| `output_summary` | `x_eco_agent_log` | `output_summary` | String | Summary of calculations |

---

# Section 4: ServiceNow-Side Setup Checklist

1. **scoped Application Config**: Verify the application namespace scope is correctly established.
2. **Outbound REST Message**:
   - Navigate to **System Web Services → Outbound → REST Messages**.
   - Create a new record: Name: `x_eco.EcoSentinel_Webhook`.
   - Configure HTTP Method: `POST` with endpoint `https://[FASTAPI_BACKEND_URL]/webhook/complaint`.
   - Setup Http Header: `Authorization` pointing to a Scoped Connection/Credential Alias.
3. **Integration User Account**:
   - Create user `ecosentinel.api` with `Web service access only` marked `true`.
   - Assign the user to the `EcoSentinel - System Administrators` group (or directly grant the `x_eco.integration_user` role).
4. **Table API Endpoint Verification**:
   - Ensure the endpoints `/api/now/table/x_eco_complaint`, `/api/now/table/x_eco_env_snapshot`, and `/api/now/table/x_eco_agent_log` are active in the application's configuration settings.
5. **Cross-Scope Privilege Records**:
   - Verify App Engine Studio has generated read/write privileges for the `ecosentinel.api` user on target custom tables.

---

# Section 5: FastAPI-Side Setup Checklist

1. **Virtual Environment Setup**: Establish a clean python virtual environment and verify `requirements.txt` includes: `fastapi`, `uvicorn`, `httpx`, `openai`, `python-dotenv`, `pydantic`.
2. **Configuration Variables (`.env`)**:
   ```env
   SERVICENOW_INSTANCE_URL=https://devXXXXX.service-now.com
   SERVICENOW_USER=ecosentinel.api
   SERVICENOW_PASSWORD=YourSecurePassword
   OPENAI_API_KEY=sk-proj-YOUR_OPENAI_KEY
   WEATHER_API_KEY=YOUR_OPENWEATHERMAP_KEY
   AQI_API_KEY=YOUR_WAQI_KEY
   FASTAPI_WEBHOOK_BEARER_TOKEN=SecureTokenCheckedByFastAPI
   ```
3. **Idempotency & Processing Logic**:
   - Create a local SQLite DB or Redis cache key repository to track processed `sys_id` values.
   - If a duplicate `sys_id` webhook is received within 5 minutes, reject it with `409 Conflict` to prevent double-billing of external API credits.
4. **Async Task Worker**:
   - The main route `POST /webhook/complaint` should validate the payload, immediately return `202 Accepted`, and spawn a background task (using FastAPI's `BackgroundTasks` helper) to carry out the slow API requests asynchronously.

---

# Section 6: Failure Mode Table

| Failure Scenario | Impact | FastAPI Mitigation | ServiceNow Fallback |
|---|---|---|---|
| **OpenAI GPT-4o Timeout** | Image description is empty. | FastAPI retries the OpenAI request once. If it still fails, it writes `"Image analysis unavailable"` as the caption. | Complaint proceeds with environmental data and description analysis only. |
| **Weather / AQI API Down** | Weather/AQI metrics return null. | FastAPI handles `HTTPError`, skips adding weather coordinates, and processes the analysis using ONLY OpenAI's image description and the citizen text. | Snapshot is created with `data_source = error`. Rationale reflects missing weather context. |
| **Malformed / Missing Photo** | No image attachment is found. | FastAPI detects empty array in attachment query, skips the OpenAI Vision payload, and skips image analysis. | The Severity Fusion Agent evaluates using coordinates + text description only. |
| **ServiceNow Authentication Failure** | FastAPI fails to fetch details or write back. | FastAPI logs a `401 Unauthorized` error and sends alert email notification to the sys admin. | The complaint remains in "Received" state. After 60 minutes, `FL-02` triggers the fallback to "Medium" severity. |
| **Duplicate Webhook Fire** | Webhook ping fires multiple times. | FastAPI checks SQLite/Redis cache for duplicate `sys_id` processing. Returns `409 Conflict` immediately if already running. | The duplicate flow run terminates cleanly without spawning secondary analysis. |
