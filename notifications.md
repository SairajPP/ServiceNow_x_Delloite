# EcoSentinel AI — Notifications Specification

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_eco_`  
> **Reference Documents**: [tables.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/tables.md) · [roles-groups-users.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/roles-groups-users.md) · [flow-designer-flows.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/flow-designer-flows.md)  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

# Section 1: Notification Roster

| Notification Name | Trigger Event / Table Action | Recipient | Channel | Fired From |
|---|---|---|---|---|
| **Citizen: Complaint Received** | Event: `x_eco.citizen_status_update` (State = 1) | Citizen Email field | Email | `FL-01` (Flow) |
| **Citizen: Status Transition** | Event: `x_eco.citizen_status_update` (State 2–5) | Citizen Email field | Email | `FL-09` (Flow) |
| **Citizen: Final Resolution** | Event: `x_eco.citizen_status_update` (State 6–8) | Citizen Email field | Email | `FL-05` (Flow) |
| **Inspector: New Assignment** | Table: `x_eco_inspection` (Assigned to changes) | `assigned_to` User | Email & Mobile Push | `FL-03` (Flow) |
| **Inspector: SLA Warning (75%)** | Task SLA SLA Workflow (75% Elapsed) | `assigned_to` User | Email & Mobile Push | `FL-04` (Flow) |
| **Compliance Officer: High-Risk Alert**| Event: `x_eco.facility_high_risk` | `EcoSentinel — Compliance Officers` Group | Email | `SF-02` (Subflow) |
| **Compliance Officer: SLA Breach** | Task SLA SLA Workflow (100% Breached) | `EcoSentinel — Compliance Officers` Group | Email | `FL-04` (Flow) |
| **Legal Handler: Case Assignment** | Table: `x_eco_legal_case` (Insert/Assignment) | `assigned_officer` User | Email | `FL-05` / `FL-07` (Flows) |
| **Leadership: Weekly Insights** | Scheduled Job / Script Execution (Weekly) | `EcoSentinel — Executive Leadership` Group | Email | `FL-10` (Flow) |

---

# Section 2: Detailed Notifications Spec

---

## 2.1 — Citizen Notifications (Email)

### Notification 1: Complaint Received Confirmation
* **Trigger Event**: `x_eco.citizen_status_update` where event parameter 2 = `"Received"`
* **Fired From**: Flow `FL-01`
* **Recipient**: Citizen Email (`current.citizen_email`)
* **Subject**: `EcoSentinel: Environmental Incident Report Received - ${number}`
* **Message Template Body**:
```text
Dear Resident,

Thank you for reporting this environmental concern. We have received your report and registered it under reference number ${number}.

Incident Details:
- Category: ${incident_category}
- Reported Location: ${incident_address}
- Description: ${description}

What Happens Next:
Our AI Severity Fusion Agent is currently evaluating your report using real-time atmospheric data, wind vectors, and image analysis (if a photo was uploaded). You will receive another notification as soon as the initial assessment completes.

You can track the status of this report at any time by visiting the public tracking portal and entering your report number along with this email address:
https://[instance].service-now.com/ecosentinel?id=track&number=${number}

Thank you,
EcoSentinel Regulatory Compliance Team
```

### Notification 2: Status Transition
* **Trigger Event**: `x_eco.citizen_status_update` where event parameter 2 IN (`"AI Verified"`, `"Inspector Assigned"`, `"Inspection In Progress"`, `"Inspection Completed"`)
* **Fired From**: Flow `FL-09`
* **Recipient**: Citizen Email (`current.citizen_email`)
* **Subject**: `EcoSentinel: Update on Report ${number} - Current Status: ${state}`
* **Message Template Body**:
```text
Dear Resident,

We are writing to update you on the status of your environmental incident report, ${number}.

Current Status: ${state} (Updated: ${sys_updated_on})

Details & Actions:
- Incident Category: ${incident_category}
- Action Taken: An update was posted to your report case file.

To see full tracking details, history, and notes, please check the status tracker page:
https://[instance].service-now.com/ecosentinel?id=track&number=${number}

Thank you,
EcoSentinel Regulatory Compliance Team
```

### Notification 3: Final Resolution Notice
* **Trigger Event**: `x_eco.citizen_status_update` where event parameter 2 IN (`"Action Taken"`, `"Dismissed"`, `"Closed"`)
* **Fired From**: Flow `FL-05`
* **Recipient**: Citizen Email (`current.citizen_email`)
* **Subject**: `EcoSentinel: RESOLUTION Notification - Report ${number}`
* **Message Template Body**:
```text
Dear Resident,

Your environmental report, ${number}, has been resolved.

Final Outcome: ${state}
Resolution Note:
${comments}

Summary:
- If a violation was confirmed, a formal Legal enforcement case has been initiated against the facility responsible.
- If dismissed, our inspectors investigated the location and confirmed no violation or ongoing threat was detected.

Thank you for helping keep our community clean. If you observe any further issues, please do not hesitate to submit a new report.

Sincerely,
EcoSentinel Regulatory Compliance Team
```

### Citizen Spam Prevention Condition
To prevent spamming the citizen (e.g. if the status changes from "Received" $\rightarrow$ "AI Verified" $\rightarrow$ "Inspector Assigned" in under a minute), the Script Include `EcoComplaintUtils` checks the timestamp of the last sent event. If an event was sent within the last 15 seconds, the trigger waits 15 seconds (using async execution) and coalesces multiple steps into the latest current status.

---

## 2.2 — Inspector Notifications (Email & Mobile Push)

### Notification 1: New Inspection Assignment
* **Trigger Table**: `x_eco_inspection` (When `assigned_to` is populated)
* **Recipient**: `current.assigned_to`
* **Subject**: `🚨 NEW ASSIGNMENT: Inspection ${number} - Severity: ${parent_complaint.ai_severity}`
* **Message Template Body**:
```text
Attention Inspector,

A new environmental field inspection has been assigned to you.

Inspection Details:
- Number: ${number}
- Severity: ${parent_complaint.ai_severity}
- Facility: ${inspected_facility.name} (Address: ${inspected_facility.address})
- Geographic Zone: ${inspected_facility.zone}

Intake Description:
${parent_complaint.description}

AI Rationale Summary:
${parent_complaint.ai_rationale}

Please update your status on the Now Mobile app to "En Route" when heading to the location. You must log findings and capture GPS-tagged photos on-site before completing the ticket.

Open in ServiceNow Mobile:
[App link to x_eco_inspection record]
```

### Notification 2: SLA Approaching Breach (75% Warning)
* **Trigger**: SLA Workflow event (At 75% elapsed SLA time)
* **Recipient**: `current.assigned_to`
* **Subject**: `⏰ URGENT SLA WARNING: ${number} is due in ${sla_remaining_time}`
* **Message Template Body**:
```text
Inspector,

The response SLA for Inspection ${number} is at 75% capacity.

- Time Remaining: ${sla_remaining_time}
- Due Date: ${sla_due_time}
- Assigned Facility: ${inspected_facility.name}

To prevent a formal SLA breach, you must proceed to the site, submit findings, and log the inspection.

If you are delayed due to weather, traffic, or access constraints, please document it immediately in the Work Notes.
```

---

## 2.3 — Compliance Officer Notifications (Email)

### Notification 1: High-Risk Facility Alert (Risk Score $\ge$ 80)
* **Trigger Event**: `x_eco.facility_high_risk`
* **Fired From**: Subflow `SF-02` (Risk recalculation) or BR `BR-F02`
* **Recipient**: `EcoSentinel — Compliance Officers` Group
* **Subject**: `⚠️ CRITICAL RISK ALERT: ${name} (Score: ${risk_score})`
* **Message Template Body**:
```text
Compliance Team,

The dynamic risk engine has recalculated compliance parameters for the following facility:

Facility: ${name}
Sector: ${sector}
Current Risk Score: ${risk_score} / 100
Risk Tier: CRITICAL RISK

Recalculation Drivers:
- Confirmed Violations (12 mo): ${violations_12m}
- Complaints Registered (90 days): ${complaints_90d}
- Compliance Report Overdue: ${report_overdue}

This facility has been flagged for priority inspection. Future complaints linked to this facility will bypass standard prioritization loops and be routed for immediate physical audit.

Review Facility File:
https://[instance].service-now.com/nav_to.do?uri=x_eco_facility.do?sys_id=${sys_id}
```

### Notification 2: SLA Breached Escalation
* **Trigger**: SLA Workflow event (100% Breached)
* **Recipient**: `EcoSentinel — Compliance Officers` Group (Escalated to Group Lead)
* **Subject**: `🚨 SLA BREACH: Inspection ${number} has breached its deadline`
* **Message Template Body**:
```text
Escalation Alert,

The response SLA for Inspection ${number} has breached.

Incident Details:
- Parent Complaint: ${parent_complaint.number}
- Assigned Inspector: ${assigned_to.name} (Group: ${assignment_group.name})
- Violation Severity: ${parent_complaint.ai_severity}
- Breached SLA Duration: ${sla_duration}
- Opened At: ${opened_at}
- Breached At: ${sla_breached_time}

A formal breach has been logged against the field zone group. The Compliance Officers group has been assigned to investigate the delay.

Review SLA Breakdown:
https://[instance].service-now.com/nav_to.do?uri=x_eco_inspection.do?sys_id=${sys_id}
```

---

## 2.4 — Legal Case Handler Notifications (Email)

### Notification: Legal Case Assigned
* **Trigger Table**: `x_eco_legal_case` (When assigned to case handler)
* **Recipient**: `current.assigned_officer`
* **Subject**: `⚖️ LEGAL CASE ASSIGNED: ${number} - ${violating_facility.name}`
* **Message Template Body**:
```text
Legal Case Handler,

A new environmental enforcement case has been assigned to you.

Enforcement Details:
- Case Number: ${number}
- Target Facility: ${violating_facility.name} (Sector: ${violating_facility.sector})
- Violation Confirmed: ${violation_type}
- Source Inspection: ${source_inspection.number}

AI Legal Narrative Brief:
${case_narrative}

You are required to compile the formal notice of violation, set penalty recommendations, and issue the compliance notice to the facility's registered contact within the legal workflow timeline.

Review Case File:
https://[instance].service-now.com/nav_to.do?uri=x_eco_legal_case.do?sys_id=${sys_id}
```

---

## 2.5 — Leadership Weekly Insights (Email)

* **Trigger**: Scheduled script weekly run (`FL-10`)
* **Recipient**: `EcoSentinel — Executive Leadership` Group
* **Subject**: `📊 EcoSentinel Weekly Environmental Intelligence Briefing`
* **Message Template Body**:
```text
Executive Leadership Team,

Below is the weekly AI-generated executive briefing from the EcoSentinel compliance dashboard, generated on ${date}.

WEEKLY PLATFORM HIGHLIGHTS:
${ai_narrative_brief}

Operational Health:
- Total Open Complaints: ${open_complaints_count}
- Inspections Completed: ${inspections_completed_count}
- Violations Confirmed: ${violations_confirmed_count}
- Fines Assessed (YTD): $${fines_ytd_amount}
- SLA Compliance Rate: ${sla_compliance_rate_percent}%

This report was auto-compiled by the Leadership Insights Agent using platform telemetry. No action is required. For real-time drilldowns, please open the EcoSentinel Leadership Workbench:
https://[instance].service-now.com/ecosentinel?id=leadership_dashboard
```
