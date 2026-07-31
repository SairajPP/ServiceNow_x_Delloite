# EcoSentinel AI — Now Mobile Inspector Experience

This document configures the field experience for EcoSentinel inspectors. It is optimized for on-site, fast data capture without paperwork, fully integrated into the ServiceNow **Now Mobile** app.

---

## Section 1: Experience Overview

- **App**: Standard **Now Mobile** app (using ServiceNow Mobile Studio / Mobile App Builder to configure the `x_eco` scope experience).
- **Primary User**: Field Inspector (requires the `x_eco.inspector` role).
- **Important Boundary Note**: Now Mobile is strictly for authenticated internal field staff. The citizen-facing public form is handled entirely via the Service Portal (`service-portal-pages-widgets.md`). Citizens do not download an app or log in; inspectors do.

---

## Section 2: List/Landing Experience

When an inspector opens the Now Mobile app, their primary workspace is their assigned queue.

- **List Name**: "My Assigned Inspections"
- **Source Table**: `x_eco_inspection`
- **Filter Condition**: `[Assigned to] [is (dynamic)] [Me]` AND `[State] [is one of] [Scheduled, En Route, On Site]`
- **Sort Order**: Sorted by SLA Due Date (ascending) so the most urgent inspections are automatically surfaced at the top.
- **Card/List Item Fields Shown**:
  - Initial Complaint Category / Short Description
  - AI Severity Badge (e.g., High, Medium)
  - Location/Address
  - SLA Countdown / Due Date
- **Tap Behavior**: Tapping a card opens the **Inspection Detail Form** for that specific record.

---

## Section 3: Inspection Detail Form Config

The form is designed to be completed entirely with a thumb while on-site.

| Field (Internal Name) | Mobile UI Component | Mandatory Before Submit? | Client-Side Behavior / Notes |
|---|---|---|---|
| `parent_complaint` | Read-only Reference | No | Displays context from the original citizen report (Initial Photo, Description). |
| `inspected_facility`| Reference | No | Auto-populated if known, but inspector can select/change the facility on-site. |
| `inspection_notes` | Text Area | Yes | Free text captured by the inspector. **Crucial**: This text is automatically ingested by the Inspection Report Agent (`ai-agent-specs.md`) to draft formal violation notices. |
| `evidence_photo` | Photo Capture Button | Yes (if Violation Confirmed) | Triggers the native device camera. Supports multiple photos. Distinct from the citizen's original photo, representing the *verified* on-site reality. |
| `gps_coordinates` | Location Auto-Tag | Yes | Auto-captured on form load. Editable text field provided as a fallback if the GPS is wildly inaccurate due to rural/industrial interference. |
| `violation_confirmed` | Boolean Toggle | Yes | "Is there an actionable environmental violation?" Toggle changes UI logic below. |
| `violation_type` | Choice List | Conditional | Hidden by default. If `violation_confirmed` is True, this becomes visible and Mandatory. |
| `state` | Status Tracker | Yes | Inspector sets this to "Completed - Violation" (6) or "Completed - Dismissed" (7) when finishing. |

### Submit Action
When the inspector taps "Submit", the inspection record is saved. 
- Changing the `state` to a closed state triggers **Flow Designer Flow `FL-05`**. 
- `FL-05` calls `EcoInspectionWorkflow` (`SI-05`), which acts idempotently to generate the Legal Case (if violation confirmed), increment facility risk scores, and close out the parent citizen complaint.

---

## Section 4: Offline/Connectivity Considerations

**Hackathon Scope vs Roadmap**
Field inspections frequently occur in industrial zones or rural areas with poor 4G/5G connectivity. ServiceNow Mobile does support robust Offline Mode (caching records and syncing upon reconnection). 

However, configuring and testing offline data synchronization profiles takes significant build and QA time. **For the 8-day hackathon, Offline Mode is OUT OF SCOPE.** The demo assumes standard connectivity. Offline capability is officially logged as an immediate post-hackathon roadmap feature to ensure the app is production-ready for deep-field operations.

---

## Section 5: Notifications on Mobile

Inspectors receive native Push Notifications directly to their device (configured in `notifications.md`):

1. **New Assignment (`FL-03`)**: "You have been assigned a High Severity inspection at [Location]." Tapping the push notification deep-links directly to the Inspection Detail Form.
2. **SLA Warning (`FL-04`)**: "Warning: SLA 75% elapsed for Inspection [Number]." Triggered by the underlying Task SLA workflow.

---

## Section 6: Field Mapping Table

*Developer Reference for Mobile Studio Data Items:*

| Mobile Form Field | Mapped Table | Internal Field Name | Type |
|---|---|---|---|
| Parent Complaint | `x_eco_inspection` | `parent_complaint` | Reference |
| Inspected Facility | `x_eco_inspection` | `inspected_facility` | Reference |
| Findings / Notes | `x_eco_inspection` | `inspection_notes` | String (Multi-line) |
| Evidence Photo | `sys_attachment` | N/A | File |
| GPS Location | `x_eco_inspection` | `gps_coordinates` | String |
| Violation Confirmed | `x_eco_inspection` | `violation_confirmed` | Boolean |
| Violation Type | `x_eco_inspection` | `violation_type` | Choice |
| Inspection State | `x_eco_inspection` | `state` | Integer (Choice) |

---

## Section 7: Role/ACL Cross-Check

The entire Now Mobile experience is gated by the `x_eco.inspector` role.

**What an Inspector CAN do:**
- Read their *assigned* `x_eco_inspection` records.
- Read the parent `x_eco_complaint` linked to their assignment.
- Create attachments and update their assigned inspection notes/state.

**What an Inspector explicitly CANNOT see on mobile (ACL Restricted):**
- Unassigned complaints or inspections assigned to others.
- The overarching `risk_score` calculation logic or historical financials of a Facility (to prevent bias during the inspection).
- `x_eco_legal_case` records (handling fines/litigation is strictly for Legal Handlers/Compliance Officers). 
- `x_eco_agent_log` records (AI Control Tower auditing is restricted to Admins/Officers).
