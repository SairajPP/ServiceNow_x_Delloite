# EcoSentinel AI — Flow Designer Flows

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_eco_`  
> **Reference Documents**: [tables.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/tables.md) · [business-rules-client-scripts.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/business-rules-client-scripts.md) · [roles-groups-users.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/roles-groups-users.md)  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

## Flow vs. Subflow Decision Guide

| Use a **Flow** when… | Use a **Subflow** when… |
|---|---|
| It has a unique trigger (record created, updated, scheduled). | The logic is reusable across ≥ 2 parent flows. |
| It represents a distinct business process step. | It has no trigger of its own — it is called by a parent flow. |

---

# Subflows (Reusable Components)

Build these **first** — they are called by multiple parent flows.

---

## SF-01: Send Citizen Notification

| Property | Value |
|---|---|
| **Type** | Subflow |
| **Purpose** | Sends an email/SMS notification to the citizen at each complaint status transition so they never lose visibility. |
| **Called By** | FL-01, FL-03, FL-05, FL-09 |
| **Run As** | System |

### Inputs

| Variable | Type | Description |
|---|---|---|
| `complaint_record` | Reference → `x_eco_complaint` | The complaint record driving the notification. |
| `status_label` | String | Human-readable status label (e.g. "Inspector Assigned"). |
| `custom_message` | String (optional) | Additional detail for the email body (e.g. "Your inspector is en route"). |

### Steps

1. **Check if citizen email exists** — If `complaint_record.citizen_email` is empty, **End** (no notification possible; log a work note instead).
2. **Build notification payload**:
   - Subject: `"EcoSentinel Update: Your report ${complaint_record.number} is now ${status_label}"`
   - Body: Include complaint number, status, category, date submitted, and a link to the public tracker URL: `https://[instance].service-now.com/ecosentinel?id=track&number=${complaint_record.number}`
   - Append `custom_message` if provided.
3. **Action: Send Email** — Email Notification action using the built-in Flow Designer "Send Email" step.
   - To: `complaint_record.citizen_email`
   - Template: `x_eco.citizen_status_update_template`
4. **Action: Add Comment** — Write a customer-visible comment on the complaint record: `"Status update sent to citizen: ${status_label}"`. This ensures the activity stream reflects every outbound communication.

### Error Handling

- If the email action fails (invalid address, SMTP error), log an error work note on the complaint: `"Failed to send citizen notification: ${error_message}"`. Do not abort the parent flow.

---

## SF-02: Recalculate Facility Risk Score

| Property | Value |
|---|---|
| **Type** | Subflow |
| **Purpose** | Recalculates the Compliance Risk Score (0–100) for a given facility using the transparent weighted formula and flags it for priority inspection if ≥ 80. |
| **Called By** | FL-05, FL-06, FL-07 |
| **Run As** | System |

### Inputs

| Variable | Type | Description |
|---|---|---|
| `facility_sys_id` | String | sys_id of the `x_eco_facility` record to recalculate. |

### Steps

1. **Action: Look Up Record** — Get the `x_eco_facility` record by `facility_sys_id`.
2. **Action: Look Up Records (Aggregate)** — Count confirmed violations in the last 12 months:
   - Table: `x_eco_inspection`
   - Filter: `inspected_facility = facility_sys_id` AND `violation_confirmed = true` AND `sys_created_on >= (today - 365 days)`
   - Store result in flow variable `violations_12m`.
3. **Action: Look Up Records (Aggregate)** — Count complaints in the last 90 days:
   - Table: `x_eco_complaint`
   - Filter: `linked_facility = facility_sys_id` AND `opened_at >= (today - 90 days)`
   - Store result in flow variable `complaints_90d`.
4. **Flow Logic: Script Step** — Calculate the score:
   ```
   score = 50
   score += min(violations_12m * 25, 40)
   if sector in ['chemical', 'mining']: score += 20
   if report_overdue == true: score += 15
   score += min(complaints_90d * 3, 30)
   score = min(score, 100)
   ```
5. **Flow Logic: Derive Risk Tier**:
   - 80–100 → `critical`, `high_risk = true`
   - 65–79 → `elevated`
   - 40–64 → `standard`
   - 0–39 → `low`
6. **Action: Update Record** — Write `risk_score`, `risk_tier`, `high_risk`, `violations_12m`, `complaints_90d` back to the facility record.
7. **Flow Logic: If** `high_risk` changed from `false` → `true`:
   - **Action: Send Email** — Notify the "EcoSentinel — Compliance Officers" group with facility name, score breakdown, and a direct link to the facility record.
   - Subject: `"⚠️ HIGH RISK: ${facility.name} has reached a Critical compliance risk score of ${score}/100"`

### Error Handling

- If the facility record is not found, log an error and abort: `"Facility sys_id ${facility_sys_id} not found. Risk recalculation aborted."`.

---

## SF-03: Log Agent Decision

| Property | Value |
|---|---|
| **Type** | Subflow |
| **Purpose** | Creates an immutable entry in the Agent Decision Log for AI Control Tower auditability. |
| **Called By** | FL-02, FL-05, FL-07, FL-10 |
| **Run As** | System |

### Inputs

| Variable | Type | Description |
|---|---|---|
| `agent_name` | Choice | The agent identifier (e.g. `severity_fusion`, `inspection_report`, `legal_case_summary`). |
| `agent_type` | Choice | `native` or `external`. |
| `linked_table` | String | Table name of the source record. |
| `linked_record_id` | String | sys_id of the source record. |
| `linked_record_number` | String | Human-readable number (e.g. `ES-20260731-0042`). |
| `input_summary` | String | What the agent received. |
| `output_summary` | String | What the agent decided. |
| `confidence` | Integer | 0–100. |
| `status` | Choice | `success`, `error`, `timeout`, `fallback`. |
| `duration_ms` | Integer | Execution time in milliseconds. |
| `error_details` | String (optional) | Error message if status ≠ success. |

### Steps

1. **Action: Create Record** on `x_eco_agent_log` — Map all inputs to fields. Set `decision_at` to `Now`.

---

# Flows (Triggered Processes)

---

## FL-01: Complaint Intake & AI Webhook Trigger

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Record Created on `x_eco_complaint` |
| **Trigger Condition** | Always (every new complaint record) |
| **Purpose** | Owns complaint intake orchestration: sends the outbound webhook ping to the FastAPI backend for AI classification, notifies the citizen, and leaves fallback recovery to FL-02. |
| **Run As** | System |
| **Architecture Decision** | **FL-01 is the only active webhook trigger.** Keep BR-C01 for before-insert defaults, but do not activate BR-C02 in the same environment. This prevents duplicate FastAPI jobs, duplicate external API cost, and inconsistent audit logs. |

### Inputs (from Trigger Record)

| Field | Usage |
|---|---|
| `sys_id` | Passed to FastAPI webhook body. |
| `number` | Passed to FastAPI webhook body and citizen notification. |
| `citizen_email` | For citizen notification subflow. |
| `incident_lat`, `incident_lng` | Passed to FastAPI so it can query Weather/AQI APIs. |

### Steps

1. **Action: Validate Intake State** — Confirm `state = 1` (Received). If blank, update to `1` and add a work note. This is defensive only; BR-C01 remains the primary owner of insert defaults.
2. **Action: Integration Hub → REST Step** — Send outbound POST to FastAPI backend.
   - **REST Message**: `x_eco.EcoSentinel_Webhook`
   - **HTTP Method**: `POST`
   - **Endpoint**: `https://[FASTAPI_URL]/webhook/complaint`
   - **Headers**: `Content-Type: application/json`, `Authorization: Bearer ${api_key}`
   - **Body**:
     ```json
     {
       "sys_id": "${trigger_record.sys_id}",
       "number": "${trigger_record.number}",
       "table": "x_eco_complaint",
       "lat": "${trigger_record.incident_lat}",
       "lng": "${trigger_record.incident_lng}"
     }
     ```
   - **Expected Response**: HTTP `200` or `202` (Accepted).
3. **Flow Logic: If** REST response status ≠ 200/202:
   - **Action: Add Work Note** — `"AI webhook failed with HTTP ${status}. Complaint will be processed by fallback timer FL-02."`
4. **Subflow Call: SF-01 (Send Citizen Notification)** — Notify citizen: status = `"Received"`, message = `"Your environmental report has been received and is being analysed by our AI system. You will receive updates at each stage."`.
5. **Action: Persist Dispatch Marker** — Store `webhook_sent_at = Now()` and `ai_processing_status = queued` on the complaint record. Do not rely on `sys_updated_on`, because unrelated updates can overwrite that signal.

### Error Handling

- REST timeout (> 10 seconds): Log work note, proceed to step 4 (citizen still gets notified). FL-02 will catch the unclassified complaint.
- Malformed response: Same as timeout handling.

---

## FL-02: AI Verification Fallback (1-Hour Safety Net)

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Scheduled — Runs every **15 minutes** |
| **Purpose** | Catches any complaint still in "Received" state after 1 hour — ensures no complaint is stuck indefinitely waiting for the FastAPI backend to respond. |
| **Run As** | System |

### Trigger Condition (Scheduled Query)

Query `x_eco_complaint` where:
- `state = 1` (Received)
- `ai_severity IS EMPTY`
- `opened_at < (Now - 60 minutes)`

### Steps

1. **Flow Logic: For Each** complaint matching the query:
   2. **Action: Update Record** on the complaint:
      - `ai_severity = 'medium'` (safe default — not low enough to ignore, not high enough to panic)
      - `ai_confidence = 0`
      - `ai_rationale = 'FALLBACK: AI classification did not respond within the 1-hour window. Default medium severity applied for manual review.'`
      - `ai_processing_status = 'fallback'`
      - `state = 2` (AI Verified)
   3. **Subflow Call: SF-03 (Log Agent Decision)** — agent_name = `severity_fusion`, status = `fallback`, input_summary = `"Complaint ${number}: No AI response within 60 minutes"`, output_summary = `"Default MEDIUM severity applied"`.
   4. **Action: Send Email** — Notify "EcoSentinel — Compliance Officers" group: `"⚠️ Complaint ${number} was not classified by the AI pipeline within 60 minutes. A default MEDIUM severity has been applied. Please review manually."`.
   5. **Action: Add Work Note** — `"FALLBACK APPLIED: AI did not respond within SLA. Default severity = MEDIUM. Manual officer review recommended."`.

### Error Handling

- If the for-each loop encounters a record that has been classified in the meantime (race condition), the `ai_severity IS EMPTY` filter naturally excludes it. No additional guard needed.

---

## FL-03: Inspector Auto-Dispatch

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Record Updated on `x_eco_complaint` |
| **Trigger Condition** | `ai_severity` changes AND `ai_severity` is not empty AND `state = 2` (AI Verified) |
| **Purpose** | Auto-assigns an inspector by zone, creates the Inspection record, attaches the severity-based SLA, and notifies the inspector. |
| **Run As** | System |

### Inputs (from Trigger Record)

| Field | Usage |
|---|---|
| `ai_severity` | Determines SLA duration. |
| `linked_facility` | Used to determine zone for inspector routing. |
| `incident_lat`, `incident_lng` | Fallback zone determination if no facility linked. |
| `sys_id`, `number` | For linking and notifications. |

### Steps

1. **Flow Logic: Determine Zone** —
   - **If** `linked_facility` is not empty:
     - **Action: Look Up Record** — Get the facility record → read `zone` field.
     - Set flow variable `dispatch_zone = facility.zone`.
   - **Else**:
     - **Flow Logic: Script Step** — Determine zone from GPS coordinates using a simple bounding-box lookup or default to `central`.
     - Set flow variable `dispatch_zone = calculated_zone`.

2. **Flow Logic: Map Zone → Assignment Group** —
   | Zone Value | Group Name |
   |---|---|
   | `north` | EcoSentinel — North Zone Inspectors |
   | `south` | EcoSentinel — South Zone Inspectors |
   | `east` | EcoSentinel — East Zone Inspectors |
   | `west` | EcoSentinel — West Zone Inspectors |
   | `central` | EcoSentinel — Central Zone Inspectors |
   - Set flow variable `target_group` = the resolved group sys_id.

3. **Action: Look Up Records** — Find available inspectors in `target_group`:
   - Table: `sys_user_grmember`
   - Filter: `group = target_group` AND `user.active = true`
   - Order by: Least assigned open inspections (round-robin load balancing via GlideAggregate count of `x_eco_inspection` where `assigned_to = user` AND `state < 6`).
   - Set flow variable `assigned_inspector` = first result.

4. **Flow Logic: If** no inspector found (empty group or all inactive):
   - **Subflow Call: SF-04 (Zone Fallback Escalation)** — see below.
   - **End** (SF-04 handles the rest).

5. **Action: Create Record** on `x_eco_inspection`:
   - `parent_complaint = trigger_record.sys_id`
   - `inspected_facility = trigger_record.linked_facility`
   - `assigned_to = assigned_inspector`
   - `inspector = assigned_inspector`
   - `assignment_group = target_group`
   - `state = 1` (Scheduled)
   - `short_description = "Inspection for " + trigger_record.number`
   - Store the new inspection sys_id in flow variable `new_inspection_id`.

6. **Action: Update Record** on the complaint:
   - `assigned_to = assigned_inspector`
   - `assignment_group = target_group`
   - `state = 3` (Inspector Assigned)

7. **Flow Logic: Set SLA** — Based on `ai_severity`:
   - **If** `ai_severity = high`:
     - The OOB Task SLA engine automatically attaches `EcoSentinel Inspection - High Severity` on the created `x_eco_inspection` record.
   - **If** `ai_severity = medium`:
     - The OOB Task SLA engine automatically attaches `EcoSentinel Inspection - Medium Severity` on the created `x_eco_inspection` record.
   - **If** `ai_severity = low`:
     - The OOB Task SLA engine automatically attaches `EcoSentinel Inspection - Low Severity` on the created `x_eco_inspection` record.
   - *Note*: SLA attachment is handled by the OOB SLA engine using the canonical inspection-level definitions in `sla-definitions.md`. No manual flow step is needed.

8. **Action: Send Email** — Notify the assigned inspector:
   - To: `assigned_inspector`
   - Subject: `"🔔 New Inspection Assigned: ${trigger_record.number} — Severity: ${ai_severity}"`
   - Body: Include complaint category, location, AI rationale, and a link to the Inspection record in Now Mobile.

9. **Subflow Call: SF-01 (Send Citizen Notification)** — status = `"Inspector Assigned"`, message = `"An inspector has been assigned and will visit the reported location."`.

---

## SF-04: Zone Fallback Escalation (Subflow)

| Property | Value |
|---|---|
| **Type** | Subflow |
| **Purpose** | Handles the case where no inspector is available in the target zone — escalates to adjacent zones, then to the Compliance Officers group if all zones are exhausted. |
| **Called By** | FL-03 |
| **Run As** | System |

### Inputs

| Variable | Type | Description |
|---|---|---|
| `complaint_record` | Reference → `x_eco_complaint` | The complaint needing an inspector. |
| `original_zone` | String | The zone where no inspector was found. |

### Steps

1. **Flow Logic: Define Adjacent Zone Order** —
   | Original Zone | Escalation Order |
   |---|---|
   | `north` | `central` → `east` → `west` → `south` |
   | `south` | `central` → `east` → `west` → `north` |
   | `east` | `central` → `north` → `south` → `west` |
   | `west` | `central` → `north` → `south` → `east` |
   | `central` | `north` → `south` → `east` → `west` |

2. **Flow Logic: For Each** adjacent zone in escalation order:
   - **Action: Look Up Records** — Check for active inspectors in the zone group.
   - **If** inspector found:
     - Assign the inspector (same logic as FL-03 steps 5–9).
     - **Action: Add Work Note** — `"No inspector available in ${original_zone}. Escalated to ${adjacent_zone}."`
     - **End** subflow (success).

3. **If** all zones exhausted with no inspectors:
   - **Action: Send Email** — Notify "EcoSentinel — Compliance Officers" group:
     - Subject: `"🚨 URGENT: No inspector available for complaint ${complaint_record.number}"`
     - Body: `"All zone groups are exhausted. Manual assignment required immediately."`
   - **Action: Add Work Note** — `"ESCALATION: No inspector available in any zone. Compliance Officers notified for manual assignment."`.
   - **Action: Update Record** — Set complaint work note but do NOT change state (it stays at "AI Verified" until someone manually assigns).

---

## FL-04: SLA Breach Escalation

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | SLA reaches **75% of duration** (OOB SLA engine sends an event) OR SLA **breached** |
| **Purpose** | Sends escalation alerts when inspection response SLAs are approaching breach or have breached. |
| **Run As** | System |

### Trigger Configuration

Configure via **SLA Definition → Workflow/Flow** settings:
- At **75%** of elapsed time: Trigger flow with `escalation_level = warning`.
- At **100%** (breached): Trigger flow with `escalation_level = breached`.

### Steps

1. **Action: Look Up Record** — Get the complaint record linked to the Task SLA.
2. **Flow Logic: If** `escalation_level = warning`:
   - **Action: Send Email** — Notify the assigned inspector:
     - Subject: `"⏰ SLA Warning: Inspection for ${complaint.number} is due in ${remaining_hours} hours"`
     - Body: Include severity, location, and SLA deadline.
   - **Action: Send Email** — Notify the inspector's assignment group manager.
   - **Action: Add Work Note** — `"SLA WARNING: 75% of response time elapsed. Inspector notified."`.

3. **Flow Logic: If** `escalation_level = breached`:
   - **Action: Update Record** on complaint — Set `sla_breached = true`.
   - **Action: Send Email** — Notify "EcoSentinel — Compliance Officers" group:
     - Subject: `"🚨 SLA BREACHED: Complaint ${complaint.number} — Severity: ${ai_severity}"`
     - Body: `"The ${sla_duration} SLA has been breached. Inspector: ${assigned_to}. Immediate action required."`.
   - **Action: Add Work Note** — `"SLA BREACHED: Response SLA exceeded. Compliance Officers escalated."`.

---

## FL-05: Inspection Completed — Violation Routing

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Record Updated on `x_eco_inspection` |
| **Trigger Condition** | `state` changes to `6` (Completed — Violation Confirmed) OR `state` changes to `7` (Completed — Dismissed) |
| **Purpose** | Primary owner for inspection outcome orchestration: if a violation is confirmed, creates/links the Legal Case and recalculates risk; if dismissed, closes the complaint. |
| **Run As** | System |
| **Architecture Decision** | **FL-05 is the only active inspection outcome orchestrator.** Keep BR-I04 and BR-I06 disabled as fallback server-side patterns only. This prevents duplicate legal cases, duplicate complaint updates, and double risk recalculation. |

### Steps

1. **Action: Look Up Record** — Get the parent complaint (`inspection.parent_complaint`).
2. **Action: Look Up Record** — Get the facility (`inspection.inspected_facility`).

3. **Flow Logic: If** `state = 6` (Violation Confirmed):
   - 3a. **Action: Script Step** — Call `new EcoInspectionWorkflow().confirmViolation(inspection.sys_id)`.
   - 3b. **Flow Logic: If** result `ok = false`, add a work note to the inspection and notify the Compliance Officers group.
   - 3c. **Subflow Call: SF-01 (Send Citizen Notification)** — status = `"Action Taken"`, message = `"A violation has been confirmed and enforcement action is underway."`.
   - 3d. **Action: Send Email** — Notify "EcoSentinel — Legal Prosecution Team": `"New Legal Case created or confirmed from complaint ${complaint.number}."`.

4. **Flow Logic: Else If** `state = 7` (Dismissed):
   - 4a. **Action: Script Step** — Call `new EcoInspectionWorkflow().dismissInspection(inspection.sys_id)`.
   - 4b. **Flow Logic: If** result `ok = false`, add a work note to the inspection and notify the Compliance Officers group.
   - 4c. **Subflow Call: SF-01 (Send Citizen Notification)** — status = `"Dismissed"`, message = `"After on-site investigation, no violation was found at this time. If you believe this is incorrect, you may file a new report."`.

---

## FL-06: Facility Risk Score Recalculation (Event-Driven)

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Record Updated on `x_eco_facility` |
| **Trigger Condition** | `violations_12m` changes OR `complaints_90d` changes OR `report_overdue` changes |
| **Purpose** | Wrapper flow that calls the risk recalculation subflow whenever a facility's input metrics change. |
| **Run As** | System |

### Steps

1. **Subflow Call: SF-02 (Recalculate Facility Risk Score)** — `facility_sys_id = trigger_record.sys_id`.

### Note

This flow exists so that **any update path** (business rule, scheduled job, manual edit, or another flow) that changes the facility's violation count, complaint count, or overdue flag will automatically trigger recalculation — even if the update didn't go through FL-05. It provides a catch-all safety net.

---

## FL-07: Legal Case Auto-Build (Agent Narrative)

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Record Created on `x_eco_legal_case` |
| **Trigger Condition** | Always (every new legal case) |
| **Purpose** | Compiles complaint details, inspection evidence, facility history, and AI rationale into a structured case narrative. Calls the native Legal Case Summary Agent (Now Assist) to generate the narrative. |
| **Run As** | System |

### Steps

1. **Action: Look Up Record** — Get source complaint (`legal_case.source_complaint`).
2. **Action: Look Up Record** — Get source inspection (`legal_case.source_inspection`).
3. **Action: Look Up Records** — Get all findings for the inspection:
   - Table: `x_eco_finding`, Filter: `parent_inspection = inspection.sys_id`, Order by `finding_number ASC`.
4. **Action: Look Up Record** — Get the violating facility (`legal_case.violating_facility`).
5. **Action: Look Up Record** — Get the environmental snapshot:
   - Table: `x_eco_env_snapshot`, Filter: `parent_complaint = complaint.sys_id`.

6. **Flow Logic: Script Step** — Compile the raw evidence package into a structured text block:
   ```
   === COMPLAINT ===
   Number: ${complaint.number}
   Category: ${complaint.incident_category}
   Description: ${complaint.description}
   AI Severity: ${complaint.ai_severity} (Confidence: ${complaint.ai_confidence}%)
   AI Rationale: ${complaint.ai_rationale}

   === ENVIRONMENTAL CONDITIONS AT TIME OF REPORT ===
   AQI: ${snapshot.aqi_value} (${snapshot.aqi_category})
   Wind: ${snapshot.wind_speed} km/h ${snapshot.wind_direction}
   Weather: ${snapshot.weather_condition}

   === INSPECTION ===
   Inspector: ${inspection.inspector.name}
   Date: ${inspection.arrival_time}
   Violation Type: ${inspection.violation_type}
   Inspector Notes: ${inspection.raw_notes}

   === FINDINGS (${findings.length}) ===
   [For each finding: type, description, measurement, severity]

   === FACILITY HISTORY ===
   Name: ${facility.name}
   Sector: ${facility.sector}
   Risk Score: ${facility.risk_score}/100 (${facility.risk_tier})
   Violations in last 12 months: ${facility.violations_12m}
   Complaints in last 90 days: ${facility.complaints_90d}
   ```
   Store as flow variable `evidence_package`.

7. **Action: Now Assist / AI Agent Studio** — Call the native **Legal Case Summary Agent**:
   - Input: `evidence_package`
   - Expected Output: A structured legal narrative (2–4 paragraphs) summarizing the case for prosecution.
   - Store output as flow variable `ai_narrative`.

8. **Flow Logic: If** AI agent returns a valid narrative:
   - **Action: Update Record** on the legal case — `case_narrative = ai_narrative`.
   - **Subflow Call: SF-03 (Log Agent Decision)** — agent_name = `legal_case_summary`, status = `success`, input = truncated evidence_package, output = truncated ai_narrative.

9. **Flow Logic: Else** (AI agent fails):
   - **Action: Update Record** on the legal case — `case_narrative = evidence_package` (use the raw compiled text as fallback).
   - **Subflow Call: SF-03 (Log Agent Decision)** — status = `error`, error_details = `"Legal Case Summary Agent failed. Raw evidence package used as fallback."`.
   - **Action: Add Work Note** — `"AI narrative generation failed. Raw evidence has been inserted. Legal handler should review and edit."`.

---

## FL-08: Inspection Report Agent (AI-Drafted Report)

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Record Updated on `x_eco_inspection` |
| **Trigger Condition** | `state` changes to `4` (Findings Submitted) AND `raw_notes` is not empty |
| **Purpose** | Calls the native Now Assist Inspection Report Agent to transform the inspector's free-form field notes into a structured professional report. |
| **Run As** | System |

### Steps

1. **Action: Look Up Records** — Get all findings for this inspection.
2. **Flow Logic: Script Step** — Compile inputs:
   ```
   Inspector Raw Notes: ${inspection.raw_notes}
   Findings Summary: [list each finding's type, description, severity, measurement]
   Complaint Category: ${parent_complaint.incident_category}
   Location: ${parent_complaint.incident_address}
   ```
3. **Action: Now Assist / AI Agent Studio** — Call the **Inspection Report Agent**:
   - Input: compiled notes.
   - Output: structured report with sections (Summary, Observations, Measurements, Conclusion, Recommendations).
4. **Flow Logic: If** agent succeeds:
   - **Action: Update Record** on inspection — `ai_report = agent_output`.
   - **Action: Update Record** — `state = 5` (Report Drafted).
   - **Subflow Call: SF-03 (Log Agent Decision)** — agent_name = `inspection_report`, status = `success`.
5. **Flow Logic: Else**:
   - **Action: Add Work Note** — `"AI report generation failed. Inspector raw notes will be used as the report."`.
   - **Action: Update Record** — `ai_report = raw_notes`, `state = 5` (Report Drafted).
   - **Subflow Call: SF-03 (Log Agent Decision)** — status = `error`.

---

## FL-09: Citizen Status Update (Lifecycle Notifier)

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Record Updated on `x_eco_complaint` |
| **Trigger Condition** | `state` changes |
| **Purpose** | Master notification flow — fires on every complaint state change and delegates to the citizen notification subflow with the appropriate message. |
| **Run As** | System |

### Steps

1. **Flow Logic: Switch** on `current.state`:

   | State Value | Status Label | Custom Message |
   |---|---|---|
   | 1 (Received) | Received | "Your report has been received and is being processed." |
   | 2 (AI Verified) | AI Verified | "Our AI system has analysed your report and classified it." |
   | 3 (Inspector Assigned) | Inspector Assigned | "An inspector has been assigned to investigate your report." |
   | 4 (Inspection In Progress) | Inspection In Progress | "The inspector is currently on-site investigating." |
   | 5 (Inspection Completed) | Inspection Completed | "The inspection is complete. The findings are under review." |
   | 6 (Action Taken) | Action Taken | "Enforcement action has been initiated based on the findings." |
   | 7 (Dismissed) | Dismissed | "After investigation, no violation was confirmed at this time." |
   | 8 (Closed) | Closed | "This case has been closed. Thank you for your report." |

2. **Subflow Call: SF-01 (Send Citizen Notification)** — Pass `complaint_record`, `status_label`, and `custom_message`.

### Note

This flow ensures **every** state transition results in a citizen notification, regardless of which upstream flow or business rule caused the transition. FL-01, FL-03, and FL-05 may also call SF-01 directly for richer contextual messages — FL-09 serves as the catch-all to guarantee no transition is missed.

**Deduplication**: SF-01 should be idempotent — if a notification for the same state was already sent (check `comments` journal for the status label), skip the duplicate.

---

## FL-10: Leadership Weekly Insights (Phase 3 / Stretch)

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Scheduled — Every Monday at 08:00 |
| **Purpose** | Generates a plain-language weekly summary of platform activity and distributes it to the Executive Leadership group. |
| **Run As** | System |

### Steps

1. **Flow Logic: Script Step** — Aggregate last 7 days of data:
   - Total new complaints
   - Complaints by severity (High / Medium / Low)
   - Complaints by category
   - Number of inspections completed
   - Number of violations confirmed
   - Number of legal cases opened
   - Facilities that crossed the 80+ risk threshold
   - SLA breach count

2. **Action: Now Assist / AI Agent Studio** — Call the **Leadership Insights Agent**:
   - Input: JSON payload with all aggregated metrics.
   - Output: Plain-language summary (e.g. "This week, 3 facilities crossed the high-risk threshold. 12 new complaints were filed, with 4 classified as High severity. 2 SLAs were breached in the South zone — consider adding inspector capacity.").

3. **Flow Logic: If** agent succeeds:
   - **Action: Send Email** — To "EcoSentinel — Executive Leadership" group:
     - Subject: `"📊 EcoSentinel Weekly Insights — Week of ${date}"`
     - Body: AI-generated summary.
   - **Subflow Call: SF-03 (Log Agent Decision)** — agent_name = `leadership_insights`, status = `success`.

4. **Flow Logic: Else**:
   - **Action: Send Email** — Send raw metric tables (from step 1) as a fallback report.
   - **Subflow Call: SF-03 (Log Agent Decision)** — status = `error`.

---

## FL-11: Legal Case Resolution Sync

| Property | Value |
|---|---|
| **Type** | Flow |
| **Trigger** | Record Updated on `x_eco_legal_case` |
| **Trigger Condition** | `state` changes to `6` (Resolved) OR `state` changes to `7` (Withdrawn) |
| **Purpose** | When a Legal Case reaches final resolution, updates the linked parent Complaint to its final closed state and notifies the citizen of the outcome. |
| **Run As** | System |

### Steps

1. **Action: Look Up Record** — Get the source complaint (`legal_case.source_complaint`).

2. **Flow Logic: If** `legal_case.state = 6` (Resolved):
   - **Action: Update Record** on complaint:
     - `state = 8` (Closed)
     - Add to `comments` (citizen-visible): `"Legal enforcement action has been completed. Resolution: ${legal_case.resolution_notes}"`
   - **Subflow Call: SF-01 (Send Citizen Notification)** — status = `"Closed"`, message = `"Legal action has been resolved. Thank you for your report."`

3. **Flow Logic: Else If** `legal_case.state = 7` (Withdrawn):
   - **Action: Update Record** on complaint:
     - `state = 8` (Closed)
     - Add to `comments` (citizen-visible): `"Legal case was withdrawn. The matter has been closed."`
   - **Subflow Call: SF-01 (Send Citizen Notification)** — status = `"Closed"`, message = `"This matter has been closed. Thank you for reporting."`

4. **Action: Add Work Note** to legal case — `"Complaint ${complaint.number} automatically closed due to legal case resolution."`

---

# Flow Summary Matrix

| ID | Name | Type | Trigger | Key Output |
|---|---|---|---|---|
| SF-01 | Send Citizen Notification | Subflow | Called by flows | Email to citizen |
| SF-02 | Recalculate Facility Risk Score | Subflow | Called by flows | Updated `risk_score` on facility |
| SF-03 | Log Agent Decision | Subflow | Called by flows | New `x_eco_agent_log` record |
| SF-04 | Zone Fallback Escalation | Subflow | Called by FL-03 | Escalated inspector assignment |
| FL-01 | Complaint Intake & AI Webhook | Flow | Complaint created | Webhook sent, citizen notified |
| FL-02 | AI Verification Fallback | Flow | Scheduled (15 min) | Unclassified complaints get default severity |
| FL-03 | Inspector Auto-Dispatch | Flow | Complaint `ai_severity` set | Inspection created, inspector assigned, SLA started |
| FL-04 | SLA Breach Escalation | Flow | SLA 75% / breached | Escalation notifications to officers |
| FL-05 | Inspection Completed — Violation Routing | Flow | Inspection state → 6 or 7 | Legal Case created or complaint dismissed |
| FL-06 | Facility Risk Recalculation | Flow | Facility metrics change | Risk score recalculated |
| FL-07 | Legal Case Auto-Build | Flow | Legal Case created | AI-drafted case narrative |
| FL-08 | Inspection Report Agent | Flow | Inspection findings submitted | AI-drafted inspection report |
| FL-09 | Citizen Status Update | Flow | Complaint state changes | Citizen notification at every transition |
| FL-10 | Leadership Weekly Insights | Flow | Scheduled (weekly) | Executive summary email |
| FL-11 | Legal Case Resolution Sync | Flow | Legal Case state → 6 or 7 | Parent complaint closed and citizen notified |

---

# Flow Dependency Map

The following shows the **trigger chain** across the full EcoSentinel pipeline. Each arrow (`→`) means "triggers the next flow/subflow."

```
CITIZEN SUBMITS COMPLAINT
  │
  ▼
FL-01: Complaint Intake & AI Webhook ──────► SF-01: Citizen Notification ("Received")
  │
  │  (webhook sent to FastAPI backend)
  │
  ├──► [FastAPI PATCHes back severity within 60 min]
  │       │
  │       ▼
  │     BR-C03 (AI Write-Back Handler) updates complaint
  │       │
  │       ▼
  │     FL-03: Inspector Auto-Dispatch ──────► SF-01: Citizen Notification ("Inspector Assigned")
  │       │
  │       ├──► [Inspector available in zone]
  │       │       └── Creates Inspection, assigns inspector, SLA starts
  │       │
  │       └──► [No inspector available]
  │               └── SF-04: Zone Fallback Escalation
  │                       ├── Try adjacent zones
  │                       └── Notify Compliance Officers if all zones exhausted
  │
  └──► [FastAPI does NOT respond within 60 min]
          │
          ▼
        FL-02: AI Verification Fallback (scheduled, every 15 min)
          │  Sets default MEDIUM severity
          ▼
        FL-03: Inspector Auto-Dispatch (triggered by severity set)
          └── (same as above)


INSPECTOR COMPLETES INVESTIGATION
  │
  ├── Submits findings → state = "Findings Submitted"
  │       │
  │       ▼
  │     FL-08: Inspection Report Agent ──── AI drafts structured report
  │       │
  │       ▼
  │     Inspector reviews AI report → confirms or dismisses violation
  │
  ├── state = "Completed — Violation Confirmed" (6)
  │       │
  │       ▼
  │     FL-05: Inspection Completed (Violation branch)
  │       ├── Creates Legal Case ──────────► FL-07: Legal Case Auto-Build (AI narrative)
  │       ├── SF-02: Recalculate Facility Risk Score
  │       │       └── If score ≥ 80 → Notify Compliance Officers
  │       └── SF-01: Citizen Notification ("Action Taken")
  │
  └── state = "Completed — Dismissed" (7)
          │
          ▼
        FL-05: Inspection Completed (Dismissed branch)
          ├── Closes complaint
          └── SF-01: Citizen Notification ("Dismissed")


SLA MONITORING (runs in parallel throughout)
  │
  ▼
FL-04: SLA Breach Escalation
  ├── 75% warning → notify inspector + zone lead
  └── 100% breached → notify Compliance Officers, flag complaint


WEEKLY (Phase 3 / Stretch)
  │
  ▼
FL-10: Leadership Weekly Insights
  └── AI-generated plain-language summary → Executive Leadership group


CATCH-ALL
  │
  ▼
FL-06: Facility Risk Recalculation
  └── Fires whenever violations_12m, complaints_90d, or report_overdue
      changes on any facility (from any source)

FL-09: Citizen Status Update
  └── Fires on EVERY complaint state change (catch-all notification)
```

---

# Integration Hub REST Endpoints Reference

| Flow | Direction | HTTP Method | Endpoint | Payload | Auth |
|---|---|---|---|---|---|
| FL-01 | ServiceNow → FastAPI | `POST` | `https://[FASTAPI_URL]/webhook/complaint` | `{ sys_id, number, table, lat, lng }` | Bearer Token |
| FastAPI → ServiceNow | FastAPI → ServiceNow Table API | `GET` | `https://[INSTANCE].service-now.com/api/now/table/x_eco_complaint/{sys_id}` | — | OAuth preferred; Basic Auth only for PDI demo |
| FastAPI → ServiceNow | FastAPI → ServiceNow Table API | `GET` | `https://[INSTANCE].service-now.com/api/now/attachment/{sys_id}/file` | — | OAuth preferred; Basic Auth only for PDI demo |
| FastAPI → ServiceNow | FastAPI → ServiceNow Table API | `PATCH` | `https://[INSTANCE].service-now.com/api/now/table/x_eco_complaint/{sys_id}` | `{ ai_severity, ai_confidence, ai_rationale, ai_image_caption, ai_classified_at, ai_processing_status }` | OAuth preferred; Basic Auth only for PDI demo |
| FastAPI → ServiceNow | FastAPI → ServiceNow Table API | `POST` | `https://[INSTANCE].service-now.com/api/now/table/x_eco_env_snapshot` | `{ parent_complaint, aqi_value, aqi_category, data_source, wind_speed, ... }` | OAuth preferred; Basic Auth only for PDI demo |
| FastAPI → ServiceNow | FastAPI → ServiceNow Table API | `POST` | `https://[INSTANCE].service-now.com/api/now/table/x_eco_agent_log` | `{ agent_name, linked_table, linked_record, input_summary, output_summary, ... }` | OAuth preferred; Basic Auth only for PDI demo |

> **Build Order**: SF-01 → SF-02 → SF-03 → SF-04 → BR-C01 → FL-01 → FL-02 → FL-03 → FL-04 → FL-05 → FL-06 → FL-07 → FL-08 → FL-09 → FL-10. Leave BR-C02 inactive unless FL-01 is intentionally disabled.
