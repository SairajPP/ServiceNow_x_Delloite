# EcoSentinel AI — PDI Setup & Prerequisites Checklist

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_snc_ecosentine_0_`  
> **Platform**: ServiceNow PDI (Washington DC / Xanadu release — AI Agent Heavy)  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

## Section 1: PDI Instance Requirements

### 1.1 Platform Release
- **Minimum Release**: Washington DC / Xanadu
- **Required Features**: AI Agent Studio, AI Agent Fabric, AI Control Tower, Integration Hub, Now Mobile support
- **Instance Type**: PDI (Personal Developer Instance) with AI Agent Heavy configuration

### 1.2 Required Plugins

| Plugin Name | Plugin ID | Purpose | Installation Method |
|---|---|---|---|
| **AI Agent Studio** | `com.snc.ai_agent_studio` | Native Now Assist agent creation (Inspection Report Agent, Legal Case Summary Agent, Leadership Insights Agent) | Pre-activated on AI Agent Heavy PDI |
| **AI Agent Fabric** | `com.snc.ai_agent_fabric` | External agent registration and governance (OpenAI Vision, Severity Fusion) | Pre-activated on AI Agent Heavy PDI |
| **AI Control Tower** | `com.snc.ai_control_tower` | AI decision audit dashboard | Pre-activated on AI Agent Heavy PDI |
| **Integration Hub** | `com.snc.integration.sn_ih` | REST Message and webhook dispatch (FL-01) | Pre-activated on most PDIs |
| **Integrated Risk Management (IRM)** | `com.snc.grc` | Optional: Facility risk indicators and GRC entity linkage | Activate via Plugin Activation if not present |
| **Legal Service Delivery** | `com.snc.legal_service_delivery` | Optional: Legal Case table extension and workspace | Activate via Plugin Activation if not present |

**Note**: IRM and Legal Service Delivery are optional. If not activated, extend `task` instead of `sn_legal_case`, and use standalone `x_snc_ecosentine_0_facility` without GRC profile linkage.

---

## Section 2: Scoped Application Setup

### 2.1 Create Scoped Application
1. Navigate to **System Applications → Studio**
2. Click **Create Application**
3. Enter:
   - **Name**: `EcoSentinel AI`
   - **Scope**: Auto-generated (e.g., `x_snc_ecosentine_0_` or `x_12345_ecosentinel`)
   - **Version**: `1.0.0`
4. Record the actual scope prefix generated — substitute this throughout all table and field definitions

### 2.2 Application Roles
Create custom application roles via **System Security → Roles**:
- `x_snc_ecosentine_0.inspector`
- `x_snc_ecosentine_0.officer`
- `x_snc_ecosentine_0.legal_handler`
- `x_snc_ecosentine_0.executive`
- `x_snc_ecosentine_0.admin`
- `x_snc_ecosentine_0.integration_user`

### 2.3 Assignment Groups
Create assignment groups via **User Administration → Groups**:
- `EcoSentinel — North Zone Inspectors`
- `EcoSentinel — South Zone Inspectors`
- `EcoSentinel — East Zone Inspectors`
- `EcoSentinel — West Zone Inspectors`
- `EcoSentinel — Central Zone Inspectors`
- `EcoSentinel — Compliance Officers`
- `EcoSentinel — Legal Prosecution Team`
- `EcoSentinel — Executive Leadership`
- `EcoSentinel — System Administrators`

Assign appropriate roles to each group.

---

## Section 3: External API Keys & Credentials

### 3.1 OpenAI API Key
- **Service**: OpenAI GPT-4o Vision
- **Obtain From**: https://platform.openai.com/api-keys
- **Purpose**: Image analysis for citizen-uploaded photos
- **Storage**: Store in ServiceNow Credential alias or FastAPI `.env` file
- **Required Permissions**: Access to `gpt-4o` model

### 3.2 Weather API Key
- **Service**: OpenWeatherMap API
- **Obtain From**: https://openweathermap.org/api
- **Purpose**: Real-time weather data for complaint GPS coordinates
- **Storage**: FastAPI `.env` file
- **Plan**: Free tier acceptable for hackathon (60 calls/min limit)

### 3.3 Air Quality Index (AQI) API Key
- **Service**: World Air Quality Index (WAQI)
- **Obtain From**: https://aqicn.org/data-platform/token/
- **Purpose**: Real-time AQI data for complaint GPS coordinates
- **Storage**: FastAPI `.env` file
- **Plan**: Free tier acceptable for hackathon (1000 requests/day limit)

### 3.4 ServiceNow Integration User
1. Create user: `ecosentinel.api`
2. Set `Web service access only = true`
3. Assign role: `x_snc_ecosentine_0.integration_user`
4. Generate strong password (or configure OAuth 2.0 client)
5. Grant Table API access to: `x_snc_ecosentine_0_complaint`, `x_snc_ecosentine_0_env_snapshot`, `x_snc_ecosentine_0_agent_decisi`

---

## Section 4: FastAPI Backend Setup

### 4.1 Environment Requirements
- **Python Version**: 3.9+
- **Virtual Environment**: Recommended (`python -m venv venv`)
- **Dependencies**: `fastapi`, `uvicorn`, `httpx`, `openai`, `python-dotenv`, `pydantic`

### 4.2 Configuration File (`.env`)
```env
SERVICENOW_INSTANCE_URL=https://devXXXXX.service-now.com
SERVICENOW_USER=ecosentinel.api
SERVICENOW_PASSWORD=YourSecurePassword
OPENAI_API_KEY=sk-proj-YOUR_OPENAI_KEY
WEATHER_API_KEY=YOUR_OPENWEATHERMAP_KEY
AQI_API_KEY=YOUR_WAQI_KEY
FASTAPI_WEBHOOK_BEARER_TOKEN=SecureTokenCheckedByFastAPI
```

### 4.3 Idempotency Store
- **Implementation**: SQLite database or Redis cache
- **Purpose**: Track processed `sys_id` values to prevent duplicate AI analysis on duplicate webhook pings
- **Schema**: `processed_complaints (sys_id TEXT PRIMARY KEY, processed_at TIMESTAMP)`

### 4.4 Deployment
- **Development**: Run locally with `uvicorn main:app --reload`
- **Hackathon Demo**: Use ngrok or similar tunnel to expose local FastAPI to ServiceNow PDI
  - `ngrok http 8000`
  - Copy the HTTPS URL to ServiceNow REST Message endpoint configuration
- **Production**: Deploy to cloud service (AWS Lambda, Azure Functions, GCP Cloud Run, or dedicated server)

---

## Section 5: ServiceNow Configuration Tasks

### 5.1 Outbound REST Message
1. Navigate to **System Web Services → Outbound → REST Messages**
2. Create new: `x_snc_ecosentine_0.EcoSentinel_Webhook`
3. Endpoint: `https://[FASTAPI_BACKEND_URL]/webhook/complaint`
4. HTTP Method: `POST`
5. Authentication: Create Connection & Credential Alias with Bearer Token
6. HTTP Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer ${credential}`

### 5.2 Number Maintenance
1. Navigate to **System Definition → Number Maintenance**
2. Create new number format:
   - **Table**: `x_snc_ecosentine_0_complaint`
   - **Prefix**: `ES`
   - **Number Format**: `ES-YYYYMMDD-####` (configured via Script Include `EcoComplaintNumberGenerator`)

### 5.3 SLA Definitions
1. Navigate to **Service Level Management → SLA Definitions**
2. Create three SLA definitions (per `sla-definitions.md`):
   - `EcoSentinel Inspection - High Severity` (24 hours on `x_snc_ecosentine_0_inspection`)
   - `EcoSentinel Inspection - Medium Severity` (72 hours on `x_snc_ecosentine_0_inspection`)
   - `EcoSentinel Inspection - Low Severity` (7 days on `x_snc_ecosentine_0_inspection`)

### 5.4 Service Portal Configuration
1. Navigate to **Service Portal → Portals**
2. Create portal: `eco_portal`
3. Theme: Mobile-first, high-contrast
4. Pages: `eco_home`, `eco_report`, `eco_track`, `eco_success`
5. Configure public (unauthenticated) access
6. Add rate limiting and CAPTCHA (roadmap item for production)

### 5.5 Now Mobile Configuration
1. Navigate to **Now Mobile → Mobile Studio**
2. Configure `x_eco` scope experience for inspectors
3. Create list view: "My Assigned Inspections"
4. Create form view: Inspection Detail Form
5. Test on Now Mobile app (iOS/Android) or mobile browser

---

## Section 6: AI Agent Configuration

### 6.1 AI Agent Studio (Native Agents)
1. Navigate to **Now Assist → AI Agent Studio**
2. Create agents (per `ai-agent-specs.md`):
   - Inspection Report Agent
   - Legal Case Summary Agent
   - Leadership Insights Agent (Phase 3)
3. Configure system prompts, inputs, outputs
4. Test agents individually before integrating with flows

### 6.2 AI Agent Fabric (External Agents)
1. Navigate to **Now Assist → AI Agent Fabric**
2. Register external agents:
   - OpenAI Vision Agent (REST API connection to OpenAI)
   - Severity Fusion Agent (REST API connection to FastAPI backend)
3. Define input/output schemas
4. Configure governance policies (audit logging, permission scopes)

### 6.3 AI Control Tower
1. Navigate to **Now Assist → AI Control Tower**
2. Configure dashboard to display `x_snc_ecosentine_0_agent_decisi` records
3. Set up filters: by agent name, status, confidence score, date range
4. Test audit trail by triggering agent decisions

---

## Section 7: Data Import & Update Sets

### 7.1 Demo Data
- Import demo data from `demo-data-seeding.md` (facilities, complaints, users)
- Use Data Source Import or manual record creation
- Ensure realistic data distribution across severity levels, zones, and facility types

### 7.2 Update Set Export
1. Navigate to **System Update Sets → Local Update Sets**
2. Create update set: `EcoSentinel AI - Complete Application`
3. Capture all configuration changes:
   - Tables, fields, business rules
   - Flows, subflows
   - UI actions, UI policies
   - ACLs, roles
   - REST messages
4. Complete and export update set as XML
5. Store in version control (Git repository)

### 7.3 Update Set Import (Team Collaboration)
- Team members import the update set in their PDIs
- Resolve conflicts (if any)
- Preview and commit
- Verify configuration after import

---

## Section 8: Testing Checklist

### 8.1 Smoke Tests
- [ ] Citizen submits complaint via portal (photo + GPS required)
- [ ] FL-01 webhook fires and reaches FastAPI backend
- [ ] FastAPI downloads attachment and calls OpenAI/Weather/AQI
- [ ] FastAPI PATCHes `ai_severity` back to ServiceNow
- [ ] BR-C03 advances complaint to "AI Verified" state
- [ ] FL-03 creates inspection and assigns to zone group
- [ ] SLA starts counting down
- [ ] Inspector views inspection on Now Mobile
- [ ] Inspector captures finding with photo
- [ ] Inspector completes inspection
- [ ] FL-05 creates legal case (if violation confirmed)
- [ ] FL-08 generates AI inspection report
- [ ] FL-07 generates AI legal case narrative
- [ ] FL-11 closes complaint when legal case resolved
- [ ] Citizen receives email notifications at each stage

### 8.2 Fallback Tests
- [ ] Simulate FastAPI down → FL-02 applies medium severity after 60 min
- [ ] Simulate OpenAI timeout → FastAPI proceeds without image analysis
- [ ] Simulate duplicate webhook → FastAPI returns 409 Conflict
- [ ] Simulate missing attachment → FastAPI skips image analysis

### 8.3 ACL Tests
- [ ] Inspector cannot see unassigned inspections
- [ ] Inspector cannot see legal cases
- [ ] Officer can override AI severity
- [ ] Legal handler can manage legal cases
- [ ] Integration user can only access API-level operations

---

## Section 9: Break-Glass Procedures

### 9.1 AI Agent Log Immutability Exception
- **Scenario**: Incorrect data logged due to agent bug; must be corrected
- **Procedure**:
  1. Admin creates new correcting entry in `x_snc_ecosentine_0_agent_decisi` with `status = "correction"`
  2. Original incorrect entry remains untouched (append-only)
  3. Correction entry references original via `linked_record_number` and explains the correction

### 9.2 SLA Reset
- **Scenario**: SLA started incorrectly or breached unfairly
- **Procedure**:
  1. Admin can manually reset SLA via SLA context menu
  2. Add work note explaining reason for reset
  3. Log as incident for pattern analysis

### 9.3 Manual Severity Override
- **Scenario**: AI consistently misclassifies a specific pollution type
- **Procedure**:
  1. Officer uses `override_severity` field with mandatory `override_reason`
  2. Pattern of overrides triggers review of AI model
  3. Retrain or adjust agent prompts as needed

---

## Section 10: Deployment Readiness Checklist

### Pre-Demo
- [ ] All plugins activated
- [ ] All tables created with correct scope prefix
- [ ] All roles and groups configured
- [ ] Demo users created and assigned to groups
- [ ] Demo facilities and complaints seeded
- [ ] FastAPI backend running and accessible
- [ ] All external API keys valid and tested
- [ ] ServiceNow REST message endpoint points to correct FastAPI URL
- [ ] All flows tested end-to-end
- [ ] All AI agents tested individually
- [ ] Mobile app tested on physical device
- [ ] Service Portal tested on mobile browser
- [ ] AI Control Tower dashboard configured

### Day-of-Demo
- [ ] PDI instance online and responsive
- [ ] FastAPI backend running (ngrok tunnel active if using local)
- [ ] Demo data loaded and visible
- [ ] Test submission workflow once before judges arrive
- [ ] Screenshots/screen recording ready as backup

### Post-Demo
- [ ] Export final update set
- [ ] Document lessons learned
- [ ] Archive demo data
- [ ] Plan production deployment roadmap

---

## Section 11: Production Deployment Considerations (Roadmap)

These items are **out of scope** for the 8-day hackathon but should be addressed before production deployment:

1. **CAPTCHA Implementation**: Add Google reCAPTCHA v3 to Service Portal
2. **Rate Limiting**: Implement IP-based or user-based rate limiting
3. **OAuth 2.0**: Replace Basic Auth with OAuth for integration user
4. **Push Notifications**: Configure native mobile push for inspector alerts
5. **Offline Mobile Support**: Configure Now Mobile offline sync profiles
6. **Data Retention Policy**: Define PII retention and cleanup schedules
   - `x_snc_ecosentine_0_complaint` citizen contact fields (`citizen_name`, `citizen_email`, `citizen_phone`) are retained for the lifecycle of the PDI/demo only and manually purged post-hackathon.
   - `sys_attachment` citizen and finding photos are retained for the lifecycle of the PDI/demo only and manually purged post-hackathon.
   - `x_snc_ecosentine_0_agent_decisi` AI decision audit records are retained for the lifecycle of the PDI/demo only and manually purged post-hackathon unless exported for judging evidence.
7. **High Availability**: Deploy FastAPI backend on redundant infrastructure
8. **API Key Rotation**: Implement automated rotation for external API keys
9. **Performance Testing**: Load test with realistic complaint volumes
10. **Security Audit**: Third-party penetration testing before production launch

---

**Document Version**: 1.0  
**Last Updated**: Post-remediation pass  
**Owner**: Team VertexNow
