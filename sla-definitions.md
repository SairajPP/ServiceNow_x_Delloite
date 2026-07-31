# EcoSentinel AI — SLA Definitions

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_eco_`  
> **Reference Documents**: [tables.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/tables.md) · [business-rules-client-scripts.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/business-rules-client-scripts.md) · [flow-designer-flows.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/flow-designer-flows.md)  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

# Section 1: SLA Architecture Summary

SLA definitions are configured in ServiceNow under **Service Level Management ➔ SLA Definitions**. For EcoSentinel AI, response SLAs are assigned to the **Inspection** (`x_eco_inspection`) table to track and enforce field response metrics.

| SLA Name | Applies to Table | Start Condition | Duration | Pause Condition | Stop Condition | Breach Action |
|---|---|---|---|---|---|---|
| **EcoSentinel Inspection - High Severity** | `x_eco_inspection` | Parent Complaint `ai_severity` = `high` AND `state` = `1` (Scheduled) | **24 Hours** (24/7) | None | `state` IN (`6` Completed-Violation Confirmed, `7` Completed-Dismissed, `8` Cancelled) | Trigger `FL-04` SLA Breach Escalation |
| **EcoSentinel Inspection - Medium Severity** | `x_eco_inspection` | Parent Complaint `ai_severity` = `medium` AND `state` = `1` (Scheduled) | **72 Hours** (24/7) | None | `state` IN (`6` Completed-Violation Confirmed, `7` Completed-Dismissed, `8` Cancelled) | Trigger `FL-04` SLA Breach Escalation |
| **EcoSentinel Inspection - Low Severity** | `x_eco_inspection` | Parent Complaint `ai_severity` = `low` AND `state` = `1` (Scheduled) | **7 Days** (24/7) | None | `state` IN (`6` Completed-Violation Confirmed, `7` Completed-Dismissed, `8` Cancelled) | Trigger `FL-04` SLA Breach Escalation |

---

# Section 2: Detailed SLA Definitions

---

## 2.1 — EcoSentinel Inspection - High Severity

| Configuration Property | Value / Condition |
|---|---|
| **Name** | EcoSentinel Inspection - High Severity |
| **Type** | SLA |
| **Target Table** | Inspection (`x_eco_inspection`) |
| **Retroactive Start** | True (Set to: `sys_created_on` to capture exact intake time) |
| **Duration Type** | User Specified Duration |
| **Duration** | 1 Day (24 Hours) |
| **Schedule** | 24 x 7 (No business hours exclusions for emergency high-severity incidents) |
| **Timezone Source** | The caller's timezone |
| **Start Condition** | `parent_complaint.ai_severity = high` AND `state = 1` (Scheduled) AND `assigned_to IS NOT EMPTY` |
| **Pause Condition** | None (Hackathon scope: inspector field assignments cannot be paused once assigned to prevent SLA manipulation) |
| **Stop Condition** | `state` is one of: `6` (Completed - Violation Confirmed), `7` (Completed - Dismissed), `8` (Cancelled) |
| **Reset Condition** | `assigned_to` changes |

### Breach Behaviour & Timeline Visibility
- **Field Impact**: If the duration passes without reaching a stop condition, the platform sets `task_sla.has_breached = true`, which flags the task index list and updates the `sla_breached` flag on the originating `x_eco_complaint` table.
- **Automation Trigger**: Fired via SLA workflow transitions. At 75% elapsed duration, notifies the assignee. At 100% elapsed (breached), invokes `FL-04` (SLA Breach Escalation Flow) which sends urgent email alerts to the `EcoSentinel — Compliance Officers` group.
- **Timeline UI visibility**: The SLA engine automatically displays the **SLA Timeline / Task SLA List** formatter at the bottom of the Inspection form view. Visible to both the assigned inspector (on Now Mobile) and compliance officers (on Desktop UI).

---

## 2.2 — EcoSentinel Inspection - Medium Severity

| Configuration Property | Value / Condition |
|---|---|
| **Name** | EcoSentinel Inspection - Medium Severity |
| **Type** | SLA |
| **Target Table** | Inspection (`x_eco_inspection`) |
| **Retroactive Start** | True (Set to: `sys_created_on`) |
| **Duration Type** | User Specified Duration |
| **Duration** | 3 Days (72 Hours) |
| **Schedule** | 24 x 7 |
| **Start Condition** | `parent_complaint.ai_severity = medium` AND `state = 1` (Scheduled) AND `assigned_to IS NOT EMPTY` |
| **Pause Condition** | None |
| **Stop Condition** | `state` is one of: `6` (Completed - Violation Confirmed), `7` (Completed - Dismissed), `8` (Cancelled) |
| **Reset Condition** | `assigned_to` changes |

---

## 2.3 — EcoSentinel Inspection - Low Severity

| Configuration Property | Value / Condition |
|---|---|
| **Name** | EcoSentinel Inspection - Low Severity |
| **Type** | SLA |
| **Target Table** | Inspection (`x_eco_inspection`) |
| **Retroactive Start** | True (Set to: `sys_created_on`) |
| **Duration Type** | User Specified Duration |
| **Duration** | 7 Days |
| **Schedule** | 24 x 7 |
| **Start Condition** | `parent_complaint.ai_severity = low` AND `state = 1` (Scheduled) AND `assigned_to IS NOT EMPTY` |
| **Pause Condition** | None |
| **Stop Condition** | `state` is one of: `6` (Completed - Violation Confirmed), `7` (Completed - Dismissed), `8` (Cancelled) |
| **Reset Condition** | `assigned_to` changes |
