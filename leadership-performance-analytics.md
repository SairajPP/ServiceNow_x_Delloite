# EcoSentinel AI — Leadership Performance Analytics Dashboard

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_eco_`  
> **Reference Documents**: [tables.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/tables.md) · [roles-groups-users.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/roles-groups-users.md) · [sla-definitions.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/sla-definitions.md) · [irm-legal-config.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/irm-legal-config.md) · [ai-agent-specs.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/ai-agent-specs.md)  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

# Section 1: Dashboard Overview

* **Dashboard Name**: EcoSentinel Executive Compliance Workbench  
* **Access Roles**: `x_eco.executive` (Read-only access), `x_eco.admin` (Full CRUD/config)  
* **Purpose**: Serves as the primary operational and compliance intelligence portal for agency directors and executive sponsors. It provides real-time, aggregated data on regional pollution volume, inspection cycle times, facility compliance distributions, SLA compliance, and legal prosecution outcomes.  
* **Refresh Frequency**: 
  * **Real-time**: Custom interactive reports (complaints, facilities, open inspections).
  * **Daily (Performance Analytics Jobs)**: Indicator scores and historical trend tables compiled nightly at 00:00.

---

# Section 2: KPIs / Indicators

The dashboard measures performance using the following primary key performance indicators.

---

### KPI-01: Total Complaints Received
* **Calculation**: Count of `x_eco_complaint` records created within the selected time window (Weekly/Monthly).
* **Source Table**: Complaint (`x_eco_complaint`)
* **Target / Threshold**: Warning threshold fires if weekly intake increases by >25% compared to the 4-week trailing average (indicating a regional environmental incident cluster).
* **Leadership Value**: Helps align staff resources to regions experiencing a surge in complaints.

---

### KPI-02: Complaint Volume Trend
* **Calculation**: Daily running count of new complaints, grouped by `incident_category`.
* **Source Table**: Complaint (`x_eco_complaint`)
* **Leadership Value**: Visualises seasonal or recurring environmental problems (e.g. increase in water pollution reports during monsoon season, or air pollution in dry winters).

---

### KPI-03: Average Time-to-Inspector-Assignment
* **Calculation**: Average difference between `opened_at` (intake) and `assigned_to` assignment timestamp for complaints matching `state` $\ge$ 3.
* **Source Table**: Complaint (`x_eco_complaint`)
* **Target / Threshold**: Target < 2 hours from intake to inspector dispatch.
* **Leadership Value**: Tracks dispatch efficiency. Long delays point to routing or staff availability issues.

---

### KPI-04: Average Time-to-Resolution by Severity
* **Calculation**: Average elapsed duration from complaint creation to closure (`state` = `8` Closed), grouped by `ai_severity` (High/Medium/Low).
* **Source Table**: Complaint (`x_eco_complaint`)
* **Target / Threshold**: High: < 24 Hours | Medium: < 72 Hours | Low: < 7 Days.
* **Leadership Value**: Validates that critical issues are prioritized and resolved within target SLA constraints.

---

### KPI-05: Inspection Backlog
* **Calculation**: Count of open inspections (`x_eco_inspection` where `state` < 6) where `sys_created_on` is older than 5 days.
* **Source Table**: Inspection (`x_eco_inspection`)
* **Target / Threshold**: Target backlog = 0. Warning flag triggers if backlog > 15 open tasks.
* **Leadership Value**: Identifies bottlenecks in the inspection workforce.

---

### KPI-06: Facility Risk Distribution
* **Calculation**: Count of active facilities grouped by risk score bands:
  * **Low**: 0–39
  * **Standard**: 40–64
  * **Elevated**: 65–79
  * **Critical (High Risk)**: 80–100 (from `irm-legal-config.md`)
* **Source Table**: Facility (`x_eco_facility`)
* **Leadership Value**: Key prevention metric. Tracks systemic corporate compliance across the industrial base.

---

### KPI-07: Enforcement Case Throughput
* **Calculation**: Side-by-side count of Legal Cases opened vs. Legal Cases resolved (`state = 6`) within the selected period.
* **Source Table**: Legal Case (`x_eco_legal_case`)
* **Leadership Value**: Measures legal follow-through. Low case closure rates indicate bottlenecks in the prosecution process.

---

### KPI-08: SLA Breach Rate
* **Calculation**: `(Number of breached task_sla records / Total task_sla records) * 100` for task_sla records linked to `x_eco_inspection`.
* **Source Table**: Task SLA (`task_sla`)
* **Target / Threshold**: Target SLA compliance: $\ge$ 95% (Breach rate $\le$ 5%).
* **Leadership Value**: Evaluates operational commitment to regulatory response times.

---

### KPI-09: Top High-Risk Facilities
* **Calculation**: Sorted list of facilities where `risk_score` $\ge$ 80, ordered desc by score.
* **Source Table**: Facility (`x_eco_facility`)
* **Leadership Value**: Target list for proactive audits. Pinpoints the worst polluters for leadership awareness.

---

# Section 3: Widgets Layout

The Executive Dashboard is structured as a 3-row grid in App Engine Studio's dashboard designer.

```
+---------------------------------------------------------------------------------------+
|  ROW 1: OPERATIONAL HIGHLIGHTS (Single Scores & Alerts)                                |
|  [ W1: Active Complaints ]  [ W2: Backlog ]  [ W3: SLA Compliance ]  [ W4: Insights Alert] |
+---------------------------------------------------------------------------------------+
|  ROW 2: TRENDS & THROUGHPUT (Line & Bar Charts)                                       |
|  [ W5: Intake Volume Trends (Line) ]       | [ W6: Legal Throughput (Bar) ]          |
+---------------------------------------------------------------------------------------+
|  ROW 3: ENVIRONMENTAL RISK (Pie & List)                                               |
|  [ W7: Facility Risk Distribution (Donut) ]| [ W8: Critical Risk Facilities (List) ]  |
+---------------------------------------------------------------------------------------+
```

### Row 1: Operational Highlights

* **Widget W1: Active Complaints**
  * **Type**: Single Score
  * **KPI**: Count of open complaints (`state` < 8)
  * **Position**: Row 1, Left
* **Widget W2: Inspection Backlog**
  * **Type**: Single Score (Color-coded: Red if > 15, Orange if 5–15, Green if < 5)
  * **KPI**: `KPI-05` (Inspections open > 5 days)
  * **Position**: Row 1, Center-Left
* **Widget W3: SLA Compliance Rate**
  * **Type**: Dial/Gauge (Target 95%+)
  * **KPI**: Derived from `KPI-08` (`100 - Breach Rate`)
  * **Position**: Row 1, Center-Right
* **Widget W4: Leadership AI Insights Banner**
  * **Type**: Rich Text / HTML Widget (Populated weekly by the AI Insights Agent)
  * **KPI**: `FL-10` AI Rationale Output
  * **Position**: Row 1, Right

### Row 2: Trends & Throughput

* **Widget W5: Intake Volume Trends**
  * **Type**: Trend Line Chart
  * **KPI**: `KPI-01` & `KPI-02` (Grouped by Category, mapped weekly)
  * **Position**: Row 2, Left
* **Widget W6: Legal Case Throughput**
  * **Type**: Column Bar Chart (Grouped by State)
  * **KPI**: `KPI-07` (Opened vs. Closed Legal Cases)
  * **Position**: Row 2, Right

### Row 3: Environmental Risk

* **Widget W7: Industrial Base Risk Profile**
  * **Type**: Donut Chart
  * **KPI**: `KPI-06` (Low / Standard / Elevated / Critical)
  * **Position**: Row 3, Left
* **Widget W8: Priority Facilities Action Registry**
  * **Type**: Table List (Columns: Facility Name, Sector, Risk Score, Last Inspected Date)
  * **KPI**: `KPI-09` (Active facilities with score $\ge$ 80, sorted desc)
  * **Position**: Row 3, Right

---

# Section 4: Leadership Insights Agent Integration

The **Leadership Insights Agent** (spec'd in `ai-agent-specs.md`) translates this dashboard's charts and indicators into a weekly plain-language report.

1. **Extraction Pipeline**: Every Monday at 08:00, Flow `FL-10` executes a script step that calls Performance Analytics APIs to collect current scores for `KPI-01` through `KPI-09`.
2. **AI Processing**: The compiled metric snapshot is sent to the Leadership Insights Agent prompt.
3. **Display & Notification**:
   * The text brief is saved to the properties of **Widget W4 (Leadership AI Insights Banner)**, updating the Dashboard view for executives.
   * In parallel, the report is emailed to the `EcoSentinel — Executive Leadership` Group (via Notification: *Leadership: Weekly Insights* from `notifications.md`).

### Example AI Output Brief
```text
Weekly Executive Summary — Compiled August 3, 2026:

Operational Volume: 
14 new complaints were received this week (15% decrease from last week). Air pollution remains the dominant concern (62% of reports), centered near the industrial corridor.

Critical Compliance Risks:
Three industrial facilities crossed the high-risk threshold (score >= 80) this week:
1. Greenfield Chemical Works (Risk: 88) - Driven by a confirmed illegal discharge incident on July 30.
2. Doshi Mining Corp (Risk: 82) - Overdue on their quarterly emission compliance report.
3. Apex Metallurgy (Risk: 80) - Risk score increased due to 4 citizen complaints registered in the last 90 days.
These facilities are priority targets for immediate proactive inspection.

Operations & Performance:
Inspection SLA compliance remained stable at 96%, with only 1 breach reported in the South zone. However, our inspection backlog has grown to 8 open cases. This indicates that while urgent high-severity issues are resolved within 24 hours, lower-priority routine inspections are beginning to accumulate. Recommend adjusting inspector routing schedules to balance backlog resolution.
```

---

# Section 5: Data Source Mapping Table

| Widget / KPI ID | KPI Label | ServiceNow Source Table | Target Fields & Conditions |
|---|---|---|---|
| **KPI-01 / W1** | Active Complaints | `x_eco_complaint` | `state` < `8` (Closed) |
| **KPI-02 / W5** | Intake Trends | `x_eco_complaint` | Grouped by `incident_category`, graphed against `sys_created_on` (trend: daily/weekly) |
| **KPI-03** | Time-to-Assignment | `x_eco_complaint` | Average of: (`assigned_to` pop timestamp - `opened_at`) |
| **KPI-04** | Resolution Time | `x_eco_complaint` | Average of: (`closed_at` - `opened_at`) where `state` = `8` |
| **KPI-05 / W2** | Inspection Backlog | `x_eco_inspection` | `state` < `6` AND `sys_created_on` < `javascript:gs.daysAgo(5)` |
| **KPI-06 / W7** | Risk Profile | `x_eco_facility` | Grouped by `risk_tier` (Low/Standard/Elevated/Critical) |
| **KPI-07 / W6** | Legal Throughput | `x_eco_legal_case` | Count of records created (`sys_created_on`) vs closed (`closed_at` / state `6`) |
| **KPI-08 / W3** | SLA Breach Rate | `task_sla` | `task_sla.has_breached = true` where `task.sys_class_name = x_eco_inspection` |
| **KPI-09 / W8** | Top Risk Facilities | `x_eco_facility` | `risk_score` $\ge$ `80` (Order by `risk_score` DESC) |
| **W4** | AI Insights Banner | `sys_properties` (or custom table) | Custom HTML component updated by `FL-10` |
