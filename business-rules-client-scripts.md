# EcoSentinel AI — Business Rules & Client Scripts

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_snc_ecosentine_0_`  
> **Reference**: [tables.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/tables.md) — all table and field names follow that schema  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

# Section 1: Business Rules

## 1.1 — Complaint Table (`x_snc_ecosentine_0_complaint`)

---

### BR-C01: Set Complaint Defaults on Insert

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_complaint` |
| **When** | Before |
| **Trigger** | Insert |
| **Order** | 100 |
| **Purpose** | Initialise every new complaint with correct defaults so downstream logic never encounters null states. |

**Why needed**: Without this, a complaint created by the Record Producer or REST API could land in the system with a blank state, no short description, or no timestamps — breaking every downstream flow and SLA.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    // Generate unique complaint number
    var generator = new x_snc_ecosentine_0.EcoComplaintNumberGenerator();
    current.number = generator.generateNumber();

    // State defaults to "Received" (1)
    current.state = 1;

    // Build short_description from category + address for quick scanning
    var cat = current.incident_category.getDisplayValue();
    var addr = current.incident_address || 'Unknown location';
    current.short_description = cat + ' reported at ' + addr;

    // Stamp the "Received" timestamp
    current.setValue('opened_at', new GlideDateTime());

})(current, previous);
```

---

### BR-C02: Trigger AI Analysis Webhook (Fallback Pattern Only)

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_complaint` |
| **When** | Async |
| **Trigger** | Insert |
| **Order** | 200 |
| **Active?** | **No, disabled by default** |
| **Purpose** | Fallback implementation for teams that cannot use Integration Hub / Flow Designer REST steps. In the standard architecture, FL-01 owns the webhook trigger. |

**Why needed**: This documents the server-side alternative, but it must not run at the same time as FL-01. Running both will send duplicate webhook pings for the same complaint, creating duplicate FastAPI jobs and inconsistent audit history.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    try {
        var r = new sn_ws.RESTMessageV2('x_snc_ecosentine_0.EcoSentinel_Webhook', 'POST');
        var body = {
            sys_id: current.sys_id.toString(),
            number: current.number.toString(),
            table: 'x_snc_ecosentine_0_complaint'
        };
        r.setRequestBody(JSON.stringify(body));
        r.setRequestHeader('Content-Type', 'application/json');
        var response = r.execute();
        var httpStatus = response.getStatusCode();

        if (httpStatus != 200 && httpStatus != 202) {
            gs.error('EcoSentinel Webhook failed. HTTP ' + httpStatus +
                     ' for complaint ' + current.number);
        }
    } catch (ex) {
        gs.error('EcoSentinel Webhook exception for ' + current.number + ': ' + ex.message);
    }
})(current, previous);
```

---

### BR-C03: Handle AI Write-Back (Severity Fusion Result)

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_complaint` |
| **When** | Before |
| **Trigger** | Update |
| **Condition** | `current.ai_severity.changes() && !current.ai_severity.nil()` |
| **Order** | 100 |
| **Purpose** | When the FastAPI backend PATCHes severity/confidence/rationale onto the complaint, validate the payload, advance state to "AI Verified", and set derived fields in the same database transaction. Agent logging is handled by FL-03/SF-03 or by the backend's explicit `x_snc_ecosentine_0_agent_decisi` POST. |

**Why needed**: The AI write-back is the single most critical integration point. Without validation, a malformed PATCH could write garbage severity values. Without the state advance, SLAs never start. Keeping this as a before rule avoids recursive updates inside an after rule.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    // --- 1. Validate payload ---
    var severity = current.ai_severity.toString();
    if (['low', 'medium', 'high'].indexOf(severity) === -1) {
        gs.error('Invalid AI severity value: ' + severity + ' on ' + current.number);
        return;
    }
    var confidence = parseInt(current.ai_confidence);
    if (isNaN(confidence) || confidence < 0 || confidence > 100) {
        gs.error('Invalid AI confidence: ' + current.ai_confidence + ' on ' + current.number);
        return;
    }

    // --- 2. Advance state to "AI Verified" (2) if still at "Received" ---
    if (current.state == 1) {
        current.state = 2;
    }

    // --- 3. Set priority from severity ---
    // High -> Priority 1 (Critical), Medium -> Priority 2 (High), Low -> Priority 3 (Moderate)
    var priorityMap = { 'high': 1, 'medium': 2, 'low': 3 };
    if (priorityMap[severity] !== undefined) {
        current.priority = priorityMap[severity];
    }

    // --- 4. Stamp classification timestamp ---
    if (current.ai_classified_at.nil()) {
        current.ai_classified_at = new GlideDateTime();
    }

})(current, previous);
```

---

### BR-C04: Prevent State Regression

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_complaint` |
| **When** | Before |
| **Trigger** | Update |
| **Condition** | `current.state.changes()` |
| **Order** | 50 |
| **Purpose** | Block backward state transitions (e.g., moving from "Inspector Assigned" back to "Received") to maintain process integrity. |

**Why needed**: Without this guard, any user with write access could rewind a complaint to an earlier state, re-triggering SLAs, duplicating notifications, and corrupting the audit trail.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    var newState = parseInt(current.state);
    var oldState = parseInt(previous.state);

    // Note for Hackathon: "Reopened" state is out of scope. 
    // Moving from closed states (like Dismissed) to Action Taken is intentionally blocked.

    // Allow only forward movement OR admin override
    if (newState < oldState) {
        var hasAdminRole = gs.hasRole('x_snc_ecosentine_0.admin');
        if (!hasAdminRole) {
            current.state = previous.state; // revert
            gs.addErrorMessage('State regression is not permitted. ' +
                'Contact an EcoSentinel Admin if you need to revert this complaint.');
            current.setAbortAction(true);
        }
    }
})(current, previous);
```

---

### BR-C05: Timestamp Status Transitions

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_complaint` |
| **When** | Before |
| **Trigger** | Update |
| **Condition** | `current.state.changes()` |
| **Order** | 110 |
| **Purpose** | Stamp the `ai_classified_at` timestamp when entering "AI Verified" state; use the inherited `closed_at` for closed states. Provides granular timing data for Performance Analytics. |

**Why needed**: SLA reports and Performance Analytics require precise timestamps for each transition. Without explicit stamping, the only timestamp available is the generic `sys_updated_on`, which changes on every field update and is useless for cycle-time analysis.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    var newState = parseInt(current.state);
    var now = new GlideDateTime();

    if (newState == 2 && current.ai_classified_at.nil()) {
        // Entering "AI Verified"
        current.ai_classified_at = now;
    }
    // States 6, 7, 8 are closed stages — task framework handles closed_at automatically

    // Write a work_note for auditability
    var stateLabel = current.state.getDisplayValue();
    current.work_notes = 'Status changed to: ' + stateLabel + ' at ' + now.getDisplayValue();

})(current, previous);
```

---

### BR-C06: Citizen Notification on Status Change

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_complaint` |
| **Active** | False |
| **When** | After |
| **Trigger** | Update |
| **Condition** | `current.state.changes() && !current.citizen_email.nil()` |
| **Order** | 500 |
| **Purpose** | Disabled fallback only. Citizen-facing email is sent by Flow `SF-01` Send Email actions called from `FL-01`, `FL-05`, `FL-09`, and `FL-11`; this rule must not fire email in the canonical build. |

**Why retained**: Keep this disabled server-side pattern only as an emergency fallback reference. The canonical build sends citizen-facing email through `SF-01`, not through events or this Business Rule.

**Logic / Pseudocode**:
```javascript
// (function executeRule(current, previous) {
//     DEPRECATED: Notification logic is now handled exclusively by Flow Designer SF-01.
//     This business rule is disabled to prevent duplicate webhook/email events.
// })(current, previous);
```

**Canonical owner**: `SF-01` sends the actual citizen-facing email. Do not register `x_snc_ecosentine_0.citizen_status_update` as an active email event in the hackathon build.

---

### BR-FN01: Auto-Increment Finding Number

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_finding` |
| **When** | Before |
| **Trigger** | Insert |
| **Order** | 100 |
| **Purpose** | Auto-generate sequential `finding_number` within each inspection (1, 2, 3, …) to track individual evidence items. |

**Why needed**: Each photo, measurement, or observation captured on Now Mobile creates a distinct finding record. Without auto-numbering, the inspector would have to manually count findings, which is error-prone and slows field data entry.

**Caution**: Count-based numbering can produce duplicate or reused `finding_number` values if findings are deleted or inserted concurrently; use a GlideRecord-safe auto-number field / Number Maintenance record if time allows. This is acceptable risk for a hackathon demo where deletions are unlikely.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    if (!current.parent_inspection.nil()) {
        // Count existing findings for this inspection
        var ga = new GlideAggregate('x_snc_ecosentine_0_finding');
        ga.addQuery('parent_inspection', current.parent_inspection);
        ga.addAggregate('COUNT');
        ga.query();
        
        var currentMax = 0;
        if (ga.next()) {
            currentMax = parseInt(ga.getAggregate('COUNT')) || 0;
        }
        
        current.finding_number = currentMax + 1;
    }
})(current, previous);
```

---

### BR-C07: Update Facility Complaint Count on Insert

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_complaint` |
| **When** | After |
| **Trigger** | Insert |
| **Condition** | `!current.linked_facility.nil()` |
| **Order** | 300 |
| **Purpose** | Increment the linked facility's `complaints_90d` counter and trigger risk score recalculation. |

**Why needed**: The Facility Risk Score formula includes complaint frequency (3 points per complaint in 90 days, capped at 30). Without real-time counter updates, the risk score would only be current on the next scheduled job run — potentially hours or days stale.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    var facilityId = current.linked_facility.toString();
    // Call Script Include for risk recalculation
    var riskCalc = new x_snc_ecosentine_0.EcoRiskCalculator();
    riskCalc.recalculate(facilityId);

})(current, previous);
```

---

## 1.2 — Facility Table (`x_snc_ecosentine_0_facility`)

---

### BR-F01: Recalculate Risk Score

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_facility` |
| **When** | Before |
| **Trigger** | Update |
| **Condition** | `current.violations_12m.changes() || current.complaints_90d.changes() || current.report_overdue.changes()` |
| **Order** | 100 |
| **Purpose** | Apply the transparent weighted formula to compute the Compliance Risk Score whenever its input fields change. |

**Why needed**: The risk score is the central metric that drives proactive inspection. It must be recalculated deterministically every time any contributing factor changes — not left to manual entry or periodic batch jobs.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    // Formula from project_context.md
    var score = 50; // Base

    // +25 per violation in 12 months, capped at +40
    var violationPoints = Math.min(parseInt(current.violations_12m) * 25, 40);
    score += violationPoints;

    // +20 if high-risk sector
    var sector = current.sector.toString();
    if (sector === 'chemical' || sector === 'mining') {
        score += 20;
    }

    // +15 if compliance report is overdue
    if (current.report_overdue == true) {
        score += 15;
    }

    // +3 per complaint in 90 days, capped at +30
    var complaintPoints = Math.min(parseInt(current.complaints_90d) * 3, 30);
    score += complaintPoints;

    // Cap at 100
    score = Math.min(score, 100);

    current.risk_score = score;

    // Derive risk tier
    if (score >= 80) {
        current.risk_tier = 'critical';
        current.high_risk = true;
    } else if (score >= 65) {
        current.risk_tier = 'elevated';
        current.high_risk = false;
    } else if (score >= 40) {
        current.risk_tier = 'standard';
        current.high_risk = false;
    } else {
        current.risk_tier = 'low';
        current.high_risk = false;
    }

})(current, previous);
```

---

### BR-F02: High-Risk Facility Alert

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_facility` |
| **When** | After |
| **Trigger** | Update |
| **Condition** | `current.high_risk.changes() && current.high_risk == true` |
| **Order** | 200 |
| **Active?** | **No, disabled by default** |
| **Purpose** | (Deprecated) Notify the Compliance Officers group when a facility crosses the critical threshold (80+). Replaced by `SF-02` to prevent duplicate alerts. |

**Why needed**: A facility breaching the critical threshold is the single strongest signal for proactive enforcement. The Flow `SF-02` is the single active owner of this alert. This Business Rule is disabled or converted to logging-only to avoid duplicate notification.

**Logic / Pseudocode**:
```javascript
// (function executeRule(current, previous) {
//     DEPRECATED: High-risk alert is now handled exclusively by Subflow SF-02.
//     This business rule is disabled to prevent duplicate alert notifications.
// })(current, previous);
```

**Paired Notification**: Email to "EcoSentinel — Compliance Officers" group with facility name, score breakdown, and a link to the facility record (now sent by SF-02 only).

---

### BR-F03: Check Report Overdue (Scheduled Job)

| Property | Value |
|---|---|
| **Type** | Scheduled Script Execution (not a table Business Rule) |
| **Schedule** | Daily at 02:00 |
| **Purpose** | Scan all active facilities and set `report_overdue = true` for any whose `report_due_date` has passed. Triggers risk score recalculation. |

**Why needed**: The `report_overdue` flag contributes +15 to the risk score. Since due dates are static dates, a daily scheduled job is the correct mechanism (not a business rule on the Facility table, which would only fire on manual edits).

**Logic / Pseudocode**:
```javascript
// Scheduled Script Execution — "EcoSentinel: Check Overdue Reports"
var today = new GlideDateTime();
var gr = new GlideRecord('x_snc_ecosentine_0_facility');
gr.addQuery('status', 'active');
gr.addNotNullQuery('report_due_date');
gr.query();

while (gr.next()) {
    var dueDate = new GlideDateTime(gr.report_due_date);
    var isOverdue = dueDate.compareTo(today) < 0;

    if (isOverdue && gr.report_overdue != true) {
        gr.report_overdue = true;
        gr.update(); // This triggers BR-F01 to recalculate risk score
    } else if (!isOverdue && gr.report_overdue == true) {
        gr.report_overdue = false;
        gr.update();
    }
}
```

---

### BR-F04: Refresh 90-Day Complaint Count (Scheduled Job)

| Property | Value |
|---|---|
| **Type** | Scheduled Script Execution |
| **Schedule** | Daily at 03:00 |
| **Purpose** | Recount complaints against each facility in the trailing 90-day window and update `complaints_90d`. Ensures old complaints age out of the count. |

**Why needed**: BR-C07 increments the count in real time when new complaints arrive, but complaints older than 90 days must be subtracted. A daily recount is the simplest correct approach.

**Logic / Pseudocode**:
```javascript
// Scheduled Script Execution — "EcoSentinel: Refresh 90-Day Complaint Counts"
var cutoff = new GlideDateTime();
cutoff.addDaysUTC(-90);

var facilities = new GlideRecord('x_snc_ecosentine_0_facility');
facilities.addQuery('status', 'active');
facilities.query();

while (facilities.next()) {
    var ga = new GlideAggregate('x_snc_ecosentine_0_complaint');
    ga.addQuery('linked_facility', facilities.sys_id);
    ga.addQuery('opened_at', '>=', cutoff);
    ga.addAggregate('COUNT');
    ga.query();

    var count = 0;
    if (ga.next()) {
        count = parseInt(ga.getAggregate('COUNT'));
    }

    if (facilities.complaints_90d != count) {
        facilities.complaints_90d = count;
        facilities.update(); // Triggers BR-F01 risk recalculation
    }
}
```

---

## 1.3 — Inspection Table (`x_snc_ecosentine_0_inspection`)

---

### BR-I01: Prevent Orphan Inspection

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_inspection` |
| **When** | Before |
| **Trigger** | Insert |
| **Order** | 50 |
| **Purpose** | Abort creation of any Inspection record that does not reference a valid parent Complaint. |

**Why needed**: An orphan inspection (no linked complaint) breaks the evidence chain, makes the inspection invisible to the citizen tracker, and prevents legal case creation downstream. This guard ensures data integrity at the point of entry.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    if (current.parent_complaint.nil()) {
        gs.addErrorMessage('An Inspection must be linked to a Complaint. Cannot create orphan inspection.');
        current.setAbortAction(true);
    }
})(current, previous);
```

---

### BR-I02: Inherit Facility from Complaint

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_inspection` |
| **When** | Before |
| **Trigger** | Insert |
| **Order** | 100 |
| **Purpose** | Auto-populate the `inspected_facility` from the parent complaint's `linked_facility` so the inspector doesn't have to look it up manually. |

**Why needed**: Reduces data entry for the inspector on mobile and ensures consistency between the complaint and inspection records.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    if (current.inspected_facility.nil() && !current.parent_complaint.nil()) {
        var complaint = new GlideRecord('x_snc_ecosentine_0_complaint');
        if (complaint.get(current.parent_complaint)) {
            if (!complaint.linked_facility.nil()) {
                current.inspected_facility = complaint.linked_facility;
            }
        }
    }
})(current, previous);
```

---

### BR-I03: Update Parent Complaint State on Inspection Progress

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_inspection` |
| **When** | After |
| **Trigger** | Update |
| **Condition** | `current.state.changes()` |
| **Order** | 200 |
| **Purpose** | Keep the parent complaint's state in sync with the inspection lifecycle so the citizen tracker reflects real-time progress. |

**Why needed**: The citizen sees complaint state, not inspection state. Without this sync, the citizen tracker would show "Inspector Assigned" even after the inspection is completed.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    var inspState = parseInt(current.state);
    var complaint = new GlideRecord('x_snc_ecosentine_0_complaint');
    if (!complaint.get(current.parent_complaint)) return;

    // Map inspection states → complaint states
    // Inspection "On Site" (3) → Complaint "Inspection In Progress" (4)
    // Inspection "Completed — Violation Confirmed" (6) or "Completed — Dismissed" (7)
    //   → Complaint "Inspection Completed" (5)
    var stateMap = {
        2: 4, // En Route → Inspection In Progress
        3: 4, // On Site → Inspection In Progress
        4: 4, // Findings Submitted → Inspection In Progress
        5: 4, // Report Drafted → Inspection In Progress
        6: 5, // Completed — Violation Confirmed → Inspection Completed
        7: 5  // Completed — Dismissed → Inspection Completed
    };

    if (stateMap[inspState] !== undefined) {
        complaint.state = stateMap[inspState];
        complaint.setWorkflow(false);
        complaint.update();
    }
})(current, previous);
```

---

### BR-I04: On Violation Confirmed — Create Legal Case

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_inspection` |
| **When** | After |
| **Trigger** | Update |
| **Condition** | `current.violation_confirmed.changes() && current.violation_confirmed == true` |
| **Order** | 300 |
| **Active?** | **No, disabled by default** |
| **Purpose** | Fallback server-side pattern for environments that do not use FL-05. In the standard architecture, FL-05 creates and links the Legal Case. |

**Why needed**: This is the "enforcement follow-through" differentiator, but it must not run at the same time as FL-05. Running both can create duplicate legal cases and duplicate facility risk recalculations.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    // --- 1. Prevent duplicate: check if a legal case already exists for this inspection ---
    var existing = new GlideRecord('x_snc_ecosentine_0_legal_case');
    existing.addQuery('source_inspection', current.sys_id);
    existing.query();
    if (existing.hasNext()) {
        gs.info('Legal case already exists for inspection ' + current.number + '. Skipping.');
        return;
    }

    // --- 2. Validate mandatory evidence ---
    var findingCount = new GlideAggregate('x_snc_ecosentine_0_finding');
    findingCount.addQuery('parent_inspection', current.sys_id);
    findingCount.addAggregate('COUNT');
    findingCount.query();
    var hasFindings = false;
    if (findingCount.next()) {
        hasFindings = parseInt(findingCount.getAggregate('COUNT')) > 0;
    }
    if (!hasFindings) {
        gs.addErrorMessage('Cannot confirm violation without at least one Inspection Finding.');
        // Note: cannot setAbortAction in after-rule. This is a soft warning.
        // Hard enforcement is done via BR-I05 (before rule).
    }

    // --- 3. Get parent complaint ---
    var complaint = new GlideRecord('x_snc_ecosentine_0_complaint');
    complaint.get(current.parent_complaint);

    // --- 4. Create Legal Case ---
    var lc = new GlideRecord('x_snc_ecosentine_0_legal_case');
    lc.initialize();
    lc.setValue('source_complaint', current.parent_complaint.toString());
    lc.setValue('source_inspection', current.sys_id.toString());
    lc.setValue('violating_facility', current.inspected_facility.toString());
    lc.setValue('violation_type', current.violation_type.toString());
    lc.setValue('state', 1); // "Case Opened"
    lc.setValue('short_description',
        'Violation: ' + current.violation_type.getDisplayValue() +
        ' — ' + complaint.short_description);
    // Case narrative will be populated by the Legal Case Summary Agent later
    var lcSysId = lc.insert();

    // --- 5. Link Legal Case back to Inspection ---
    current.linked_legal_case = lcSysId;
    current.setWorkflow(false);
    current.update();

    // --- 6. Update parent complaint ---
    complaint.violation_confirmed = true;
    complaint.state = 6; // "Action Taken"
    complaint.setWorkflow(false);
    complaint.update();

    // --- 7. Update facility violation count ---
    if (!current.inspected_facility.nil()) {
        var facility = new GlideRecord('x_snc_ecosentine_0_facility');
        if (facility.get(current.inspected_facility)) {
            facility.violations_12m = parseInt(facility.violations_12m) + 1;
            facility.last_inspection_date = new GlideDateTime();
            facility.update(); // Triggers BR-F01 risk recalculation
        }
    }

    // --- 8. Log to Agent Decision Log (placeholder for Legal Case Summary Agent) ---
    // The actual agent log will be written when the Legal Case Summary Agent runs
    // and populates the case_narrative field.

})(current, previous);
```

---

### BR-I05: Enforce Evidence Before Violation Confirmation

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_inspection` |
| **When** | Before |
| **Trigger** | Update |
| **Condition** | `current.violation_confirmed.changes() && current.violation_confirmed == true` |
| **Order** | 100 |
| **Purpose** | Block violation confirmation if no Inspection Findings have been submitted. |

**Why needed**: A confirmed violation without evidence is legally indefensible. This rule ensures the inspector has logged at least one finding (photo, observation, or measurement) before they can confirm.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    var ga = new GlideAggregate('x_snc_ecosentine_0_finding');
    ga.addQuery('parent_inspection', current.sys_id);
    ga.addAggregate('COUNT');
    ga.query();

    var count = 0;
    if (ga.next()) {
        count = parseInt(ga.getAggregate('COUNT'));
    }

    if (count === 0) {
        gs.addErrorMessage('You must submit at least one Inspection Finding before confirming a violation.');
        current.violation_confirmed = false;
        current.setAbortAction(true);
    }

    // Also enforce violation_type is set
    if (current.violation_type.nil()) {
        gs.addErrorMessage('Violation Type is required when confirming a violation.');
        current.violation_confirmed = false;
        current.setAbortAction(true);
    }
})(current, previous);
```

---

### BR-I06: Update Facility on Inspection Close (Dismissed)

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_inspection` |
| **When** | After |
| **Trigger** | Update |
| **Condition** | `current.state.changes() && current.state == 7` (Completed — Dismissed) |
| **Order** | 300 |
| **Active?** | **No, disabled by default** |
| **Purpose** | Fallback server-side pattern for environments that do not use FL-05. In the standard architecture, FL-05 closes dismissed complaints and updates the facility. |

**Why needed**: Even a dismissed inspection is a data point, but this rule must not run with FL-05 because both update the same complaint and facility records.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    // Update complaint state to "Dismissed" (7)
    var complaint = new GlideRecord('x_snc_ecosentine_0_complaint');
    if (complaint.get(current.parent_complaint)) {
        complaint.state = 7; // Dismissed
        complaint.setWorkflow(false);
        complaint.update();
    }

    // Update facility last inspection date
    if (!current.inspected_facility.nil()) {
        var facility = new GlideRecord('x_snc_ecosentine_0_facility');
        if (facility.get(current.inspected_facility)) {
            facility.last_inspection_date = new GlideDateTime();
            facility.setWorkflow(false);
            facility.update();
        }
    }
})(current, previous);
```

---

### BR-I07: Inspector Assignment Notification

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_inspection` |
| **When** | After |
| **Trigger** | Insert, Update |
| **Condition** | `current.assigned_to.changes() && !current.assigned_to.nil()` |
| **Order** | 400 |
| **Purpose** | Notify the assigned inspector via push notification/email so they see the new task on Now Mobile immediately. |

**Why needed**: SLA timers start when the inspector is assigned. If the inspector doesn't know about the assignment, they can't act, and the SLA breaches silently.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    gs.eventQueue('x_snc_ecosentine_0.inspector_assigned', current,
        current.assigned_to.toString(),
        'Inspection ' + current.number + ' assigned. Severity: ' +
        current.parent_complaint.ai_severity.getDisplayValue());
})(current, previous);
```

---

## 1.4 — Legal Case Table (`x_snc_ecosentine_0_legal_case`)

---

### BR-L01: Prevent Duplicate Legal Case

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_legal_case` |
| **When** | Before |
| **Trigger** | Insert |
| **Order** | 50 |
| **Purpose** | Block creation of a second Legal Case for the same source complaint. |

**Why needed**: Since FL-05 creates legal cases on violation confirmation, and fallback/server-side paths may also attempt creation, a race condition could produce duplicates. This guard is the last line of defence.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    if (!current.source_complaint.nil()) {
        var existing = new GlideRecord('x_snc_ecosentine_0_legal_case');
        existing.addQuery('source_complaint', current.source_complaint);
        existing.query();
        if (existing.hasNext()) {
            gs.addErrorMessage('A Legal Case already exists for complaint ' +
                current.source_complaint.getDisplayValue() + '. Duplicate blocked.');
            current.setAbortAction(true);
        }
    }
})(current, previous);
```

---

### BR-L02: Prevent Case Without Evidence Chain

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_legal_case` |
| **When** | Before |
| **Trigger** | Insert |
| **Order** | 100 |
| **Purpose** | Block creation of a Legal Case that has no linked complaint or inspection. |

**Why needed**: A legal case without an evidence chain (complaint → inspection → findings) is legally useless and would undermine the platform's credibility during the demo.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    if (current.source_complaint.nil()) {
        gs.addErrorMessage('A Legal Case must be linked to a source Complaint.');
        current.setAbortAction(true);
        return;
    }
    if (current.source_inspection.nil()) {
        gs.addErrorMessage('A Legal Case must be linked to a source Inspection.');
        current.setAbortAction(true);
        return;
    }
})(current, previous);
```

---

## 1.5 — Agent Decision Log Table (`x_snc_ecosentine_0_agent_decisi`)

---

### BR-A01: Enforce Append-Only (Block Updates & Deletes)

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_agent_decisi` |
| **When** | Before |
| **Trigger** | Update, Delete |
| **Order** | 1 |
| **Purpose** | Make the Agent Decision Log immutable. No record can be modified or deleted once created. |

**Why needed**: AI Control Tower auditability requires a tamper-proof log. If anyone could edit or delete agent decision records, the governance story collapses. Even admins should not modify past decisions — they can only add new correction entries.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    gs.addErrorMessage('Agent Decision Log records are immutable. ' +
        'Updates and deletes are not permitted for audit compliance.');
    current.setAbortAction(true);
})(current, previous);
```

---

## 1.6 — Environmental Snapshot Table (`x_snc_ecosentine_0_env_snapshot`)

---

### BR-E01: Prevent Orphan Snapshot

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_env_snapshot` |
| **When** | Before |
| **Trigger** | Insert |
| **Order** | 50 |
| **Purpose** | Block creation of a snapshot not linked to any complaint. |

**Why needed**: A snapshot without a parent complaint is meaningless data. This also prevents accidental API misconfiguration from polluting the snapshot table.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    if (current.parent_complaint.nil()) {
        gs.addErrorMessage('Environmental Snapshot must reference a Complaint.');
        current.setAbortAction(true);
    }
})(current, previous);
```

---

### BR-E02: Prevent Duplicate Snapshot per Complaint

| Property | Value |
|---|---|
| **Table** | `x_snc_ecosentine_0_env_snapshot` |
| **When** | Before |
| **Trigger** | Insert |
| **Order** | 60 |
| **Purpose** | Enforce the 1:1 relationship — only one snapshot per complaint is allowed. |

**Why needed**: The snapshot captures the environmental conditions at the moment of AI classification. Multiple snapshots for the same complaint would create ambiguity about which data was actually used for the decision.

**Logic / Pseudocode**:
```javascript
(function executeRule(current, previous) {
    var existing = new GlideRecord('x_snc_ecosentine_0_env_snapshot');
    existing.addQuery('parent_complaint', current.parent_complaint);
    existing.query();
    if (existing.hasNext()) {
        gs.addErrorMessage('An Environmental Snapshot already exists for this complaint. ' +
            'Only one snapshot per complaint is permitted.');
        current.setAbortAction(true);
    }
})(current, previous);
```

---

## 1.7 — Script Includes (Server-Side Reusable Logic)

These are called by business rules, flows, and GlideAjax client scripts.

---

### SI-01: EcoRiskCalculator

| Property | Value |
|---|---|
| **Name** | `EcoRiskCalculator` |
| **Client Callable** | false |
| **Purpose** | Centralized risk score recalculation logic for a facility. Called by BR-C07, FL-05 / EcoInspectionWorkflow, BR-I04 fallback, BR-F03, BR-F04, and Flow Designer. |

> **Canonical Source**: The full implementation with the weighted risk formula lives in [script-includes.md § 2.1](file:///c:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/script-includes.md). The implementation below matches the canonical version exactly.
>
> **Architecture Note**: `EcoRiskCalculator.recalculate()` computes the full risk score, risk tier, and high-risk flag internally, then calls `facility.update()`. This triggers BR-F01, which **also** recalculates the score from the input fields as a safety net. Both paths use the same formula, so the result is deterministic and idempotent. BR-F01 exists as a guard to ensure the score is always correct even if a facility record is updated without going through `EcoRiskCalculator`.

**Logic / Pseudocode**:
```javascript
var EcoRiskCalculator = Class.create();
EcoRiskCalculator.prototype = {
    initialize: function() {},

    recalculate: function(facilitySysId) {
        if (!facilitySysId) return;

        var facility = new GlideRecord('x_snc_ecosentine_0_facility');
        if (!facility.get(facilitySysId)) return;

        var score = 50; // Base score

        // 1. Violation History: +25 per violation in last 12 months (capped at +40)
        var cutoff12m = new GlideDateTime();
        cutoff12m.addDaysUTC(-365);
        var violations = new GlideAggregate('x_snc_ecosentine_0_inspection');
        violations.addQuery('inspected_facility', facilitySysId);
        violations.addQuery('violation_confirmed', true);
        violations.addQuery('sys_created_on', '>=', cutoff12m);
        violations.addAggregate('COUNT');
        violations.query();
        var violationCount = 0;
        if (violations.next()) {
            violationCount = parseInt(violations.getAggregate('COUNT')) || 0;
        }
        facility.setValue('violations_12m', violationCount);
        score += Math.min(violationCount * 25, 40);

        // 2. Sector Risk: +20 points if high-risk sector (chemical/mining)
        var sector = facility.getValue('sector');
        if (sector === 'chemical' || sector === 'mining') {
            score += 20;
        }

        // 3. Overdue Reports: +15 points if last compliance report is overdue
        var reportOverdue = false;
        if (!facility.report_due_date.nil()) {
            var today = new GlideDateTime();
            var dueDate = new GlideDateTime(facility.report_due_date);
            if (dueDate.compareTo(today) < 0) {
                reportOverdue = true;
            }
        }
        facility.setValue('report_overdue', reportOverdue);
        if (reportOverdue) {
            score += 15;
        }

        // 4. Complaint Frequency: +3 points per complaint in last 90 days (capped at +30)
        var cutoff90d = new GlideDateTime();
        cutoff90d.addDaysUTC(-90);
        var complaints = new GlideAggregate('x_snc_ecosentine_0_complaint');
        complaints.addQuery('linked_facility', facilitySysId);
        complaints.addQuery('opened_at', '>=', cutoff90d);
        complaints.addAggregate('COUNT');
        complaints.query();
        var complaintCount = 0;
        if (complaints.next()) {
            complaintCount = parseInt(complaints.getAggregate('COUNT')) || 0;
        }
        facility.setValue('complaints_90d', complaintCount);
        score += Math.min(complaintCount * 3, 30);

        // Final constraints: cap score between 0 and 100
        score = Math.max(0, Math.min(score, 100));
        facility.setValue('risk_score', score);

        // Derive Risk Tier and High-Risk Flag
        var riskTier = 'low';
        var highRisk = false;
        if (score >= 80) {
            riskTier = 'critical';
            highRisk = true;
        } else if (score >= 65) {
            riskTier = 'elevated';
        } else if (score >= 40) {
            riskTier = 'standard';
        }
        facility.setValue('risk_tier', riskTier);
        facility.setValue('high_risk', highRisk);

        // Update triggers BR-F01 which validates the same formula as a safety net
        facility.update();
    },

    type: 'EcoRiskCalculator'
};
```

---

### SI-02: EcoComplaintUtils (GlideAjax-Callable)

| Property | Value |
|---|---|
| **Name** | `EcoComplaintUtils` |
| **Client Callable** | **true** (extends `AbstractAjaxProcessor`) |
| **Purpose** | Server-side utility called from client scripts via GlideAjax. Provides complaint lookup for citizen tracker and role-checking for UI conditional logic. |

**Logic / Pseudocode**:
```javascript
var EcoComplaintUtils = Class.create();
EcoComplaintUtils.prototype = Object.extendsObject(AbstractAjaxProcessor, {

    // Called from Citizen Tracker portal widget (GlideAjax) or Virtual Agent (server-side object)
    lookupComplaint: function(params) {
        params = params || {};
        var number = params.number || this.getParameter('sysparm_number');
        var email = params.email || this.getParameter('sysparm_email');
        var result = { found: false };

        if (!number || !email) {
            return JSON.stringify(result);
        }

        var gr = new GlideRecord('x_snc_ecosentine_0_complaint');
        gr.addQuery('number', number);
        gr.addQuery('citizen_email', email);
        gr.query();

        if (gr.next()) {
            result.found = true;
            result.number = gr.getValue('number');
            result.state = gr.state.getDisplayValue();
            result.category = gr.incident_category.getDisplayValue();
            result.ai_severity = gr.ai_severity.getDisplayValue();
            result.opened_at = gr.opened_at.getDisplayValue();
            result.short_description = gr.getValue('short_description');
        }

        return JSON.stringify(result);
    },

    // Called from officer complaint form to check role
    hasOfficerRole: function() {
        return gs.hasRole('x_snc_ecosentine_0.officer') || gs.hasRole('x_snc_ecosentine_0.admin');
    },

    type: 'EcoComplaintUtils'
});
```

---

### SI-03: EcoAgentLogger

| Property | Value |
|---|---|
| **Name** | `EcoAgentLogger` |
| **Client Callable** | false |
| **Purpose** | Centralized utility to write Agent Decision Log entries. Called by any business rule or flow action that involves an AI agent decision. |

**Logic / Pseudocode**:
```javascript
var EcoAgentLogger = Class.create();
EcoAgentLogger.prototype = {
    initialize: function() {},

    log: function(params) {
        // params: agentName, agentType, linkedTable, linkedRecord, linkedNumber,
        //         inputSummary, outputSummary, confidence, status, durationMs, errorDetails
        var logGr = new GlideRecord('x_snc_ecosentine_0_agent_decisi');
        logGr.initialize();
        logGr.setValue('agent_name', params.agentName);
        logGr.setValue('agent_type', params.agentType || 'native');
        logGr.setValue('linked_table', params.linkedTable);
        logGr.setValue('linked_record', params.linkedRecord);
        logGr.setValue('linked_record_number', params.linkedNumber || '');
        logGr.setValue('input_summary', params.inputSummary);
        logGr.setValue('output_summary', params.outputSummary);
        logGr.setValue('confidence', params.confidence || 0);
        logGr.setValue('decision_at', new GlideDateTime());
        logGr.setValue('duration_ms', params.durationMs || 0);
        logGr.setValue('status', params.status || 'success');
        logGr.setValue('error_details', params.errorDetails || '');
        return logGr.insert();
    },

    type: 'EcoAgentLogger'
};
```

---

### SI-04: EcoConstants

| Property | Value |
|---|---|
| **Name** | `EcoConstants` |
| **Client Callable** | false |
| **Purpose** | Centralizes state values, choice values, and table names so Business Rules, Script Includes, and Flow Designer script steps do not duplicate magic numbers. |

**Logic / Pseudocode**:
```javascript
var EcoConstants = Class.create();
EcoConstants.prototype = {
    initialize: function() {},

    tables: {
        complaint: 'x_snc_ecosentine_0_complaint',
        facility: 'x_snc_ecosentine_0_facility',
        inspection: 'x_snc_ecosentine_0_inspection',
        finding: 'x_snc_ecosentine_0_finding',
        legalCase: 'x_snc_ecosentine_0_legal_case',
        agentLog: 'x_snc_ecosentine_0_agent_decisi',
        envSnapshot: 'x_snc_ecosentine_0_env_snapshot'
    },

    complaintState: {
        received: 1,
        aiVerified: 2,
        inspectorAssigned: 3,
        inspectionInProgress: 4,
        inspectionCompleted: 5,
        actionTaken: 6,
        dismissed: 7,
        closed: 8
    },

    inspectionState: {
        scheduled: 1,
        enRoute: 2,
        onSite: 3,
        findingsSubmitted: 4,
        reportDrafted: 5,
        completedViolation: 6,
        completedDismissed: 7,
        cancelled: 8
    },

    validSeverity: function(value) {
        return ['low', 'medium', 'high'].indexOf(String(value)) >= 0;
    },

    priorityForSeverity: function(value) {
        var map = { high: 1, medium: 2, low: 3 };
        return map[String(value)] || 3;
    },

    type: 'EcoConstants'
};
```

---

### SI-05: EcoInspectionWorkflow

| Property | Value |
|---|---|
| **Name** | `EcoInspectionWorkflow` |
| **Client Callable** | false |
| **Purpose** | Server-side helper for FL-05. Provides idempotent functions to handle completed inspections without duplicating legal cases, complaint updates, or facility risk recalculation logic. |

**Logic / Pseudocode**:
```javascript
var EcoInspectionWorkflow = Class.create();
EcoInspectionWorkflow.prototype = {
    initialize: function() {
        this.C = new EcoConstants();
    },

    confirmViolation: function(inspectionSysId) {
        var insp = new GlideRecord(this.C.tables.inspection);
        if (!insp.get(inspectionSysId)) {
            return { ok: false, message: 'Inspection not found' };
        }

        var existing = new GlideRecord(this.C.tables.legalCase);
        existing.addQuery('source_inspection', insp.getUniqueValue());
        existing.setLimit(1);
        existing.query();
        if (existing.next()) {
            this._linkInspectionToCase(insp, existing.getUniqueValue());
            return { ok: true, legal_case: existing.getUniqueValue(), duplicate: true };
        }

        var complaint = new GlideRecord(this.C.tables.complaint);
        if (!complaint.get(insp.getValue('parent_complaint'))) {
            return { ok: false, message: 'Parent complaint not found' };
        }

        var lc = new GlideRecord(this.C.tables.legalCase);
        lc.initialize();
        lc.setValue('source_complaint', complaint.getUniqueValue());
        lc.setValue('source_inspection', insp.getUniqueValue());
        lc.setValue('violating_facility', insp.getValue('inspected_facility'));
        lc.setValue('violation_type', insp.getValue('violation_type'));
        lc.setValue('state', 1);
        lc.setValue('short_description', 'Violation: ' + insp.violation_type.getDisplayValue() + ' - ' + complaint.getValue('short_description'));
        var legalCaseId = lc.insert();

        this._linkInspectionToCase(insp, legalCaseId);

        complaint.setValue('violation_confirmed', true);
        complaint.setValue('state', this.C.complaintState.actionTaken);
        complaint.update();

        if (!insp.inspected_facility.nil()) {
            var riskCalc = new EcoRiskCalculator();
            riskCalc.recalculate(insp.getValue('inspected_facility'));
        }

        return { ok: true, legal_case: legalCaseId, duplicate: false };
    },

    dismissInspection: function(inspectionSysId) {
        var insp = new GlideRecord(this.C.tables.inspection);
        if (!insp.get(inspectionSysId)) {
            return { ok: false, message: 'Inspection not found' };
        }

        var complaint = new GlideRecord(this.C.tables.complaint);
        if (complaint.get(insp.getValue('parent_complaint'))) {
            complaint.setValue('state', this.C.complaintState.dismissed);
            complaint.update();
        }

        if (!insp.inspected_facility.nil()) {
            var facility = new GlideRecord(this.C.tables.facility);
            if (facility.get(insp.getValue('inspected_facility'))) {
                facility.setValue('last_inspection_date', new GlideDateTime());
                facility.update();
            }
        }

        return { ok: true };
    },

    _linkInspectionToCase: function(insp, legalCaseId) {
        if (insp.getValue('linked_legal_case') !== legalCaseId) {
            insp.setValue('linked_legal_case', legalCaseId);
            insp.update();
        }
    },

    type: 'EcoInspectionWorkflow'
};
```

---

### Additional Script Includes

> **Note**: The following Script Includes are fully defined in their canonical location in [script-includes.md](file:///c:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/script-includes.md). They are listed here for completeness.

* **SI-06: EcoComplaintNumberGenerator** — Generates sequential `ES-YYYYMMDD-####` tracking numbers.
* **SI-07: EcoUrgencyScoreCalculator** — Advanced time-based decay logic for backlog prioritization.
* **SI-08: EcoSLADueDateCalculator** — Custom SLA duration calculation honoring non-business hours.

---

## 1.8 — Business Rule Summary Matrix

| ID | Name | Table | When | Trigger | Condition Summary |
|---|---|---|---|---|---|
| BR-C01 | Set Complaint Defaults | `x_snc_ecosentine_0_complaint` | Before | Insert | Always on insert |
| BR-C02 | Trigger AI Webhook | `x_snc_ecosentine_0_complaint` | Async | Insert | **Disabled by default; fallback only if FL-01 is not used** |
| BR-C03 | Handle AI Write-Back | `x_snc_ecosentine_0_complaint` | Before | Update | `ai_severity` changes and is not empty |
| BR-C04 | Prevent State Regression | `x_snc_ecosentine_0_complaint` | Before | Update | `state` changes |
| BR-C05 | Timestamp Status Transitions | `x_snc_ecosentine_0_complaint` | Before | Update | `state` changes |
| BR-C06 | Citizen Notification | `x_snc_ecosentine_0_complaint` | After | Update | **Disabled by default; fallback only. `SF-01` owns citizen-facing email** |
| BR-C07 | Update Facility Complaint Count | `x_snc_ecosentine_0_complaint` | After | Insert | `linked_facility` not empty |
| BR-F01 | Recalculate Risk Score | `x_snc_ecosentine_0_facility` | Before | Update | `violations_12m`, `complaints_90d`, or `report_overdue` changes |
| BR-F02 | High-Risk Facility Alert | `x_snc_ecosentine_0_facility` | After | Update | **Disabled by default; `SF-02` owns high-risk alerts** |
| BR-F03 | Check Report Overdue | Scheduled Job | Daily 02:00 | — | Scans all active facilities |
| BR-F04 | Refresh 90-Day Count | Scheduled Job | Daily 03:00 | — | Scans all active facilities |
| BR-I01 | Prevent Orphan Inspection | `x_snc_ecosentine_0_inspection` | Before | Insert | `parent_complaint` is empty |
| BR-I02 | Inherit Facility from Complaint | `x_snc_ecosentine_0_inspection` | Before | Insert | `inspected_facility` is empty |
| BR-I03 | Update Parent Complaint State | `x_snc_ecosentine_0_inspection` | After | Update | `state` changes |
| BR-I04 | Create Legal Case on Violation | `x_snc_ecosentine_0_inspection` | After | Update | **Disabled by default; fallback only if FL-05 is not used** |
| BR-I05 | Enforce Evidence Before Confirm | `x_snc_ecosentine_0_inspection` | Before | Update | `violation_confirmed` changes to true |
| BR-I06 | Update Facility on Dismissed | `x_snc_ecosentine_0_inspection` | After | Update | **Disabled by default; fallback only if FL-05 is not used** |
| BR-I07 | Inspector Assignment Notification | `x_snc_ecosentine_0_inspection` | After | Insert/Update | `assigned_to` changes |
| BR-L01 | Prevent Duplicate Legal Case | `x_snc_ecosentine_0_legal_case` | Before | Insert | `source_complaint` already has a legal case |
| BR-L02 | Prevent Case Without Evidence | `x_snc_ecosentine_0_legal_case` | Before | Insert | `source_complaint` or `source_inspection` empty |
| BR-A01 | Enforce Append-Only Log | `x_snc_ecosentine_0_agent_decisi` | Before | Update/Delete | Always |
| BR-E01 | Prevent Orphan Snapshot | `x_snc_ecosentine_0_env_snapshot` | Before | Insert | `parent_complaint` is empty |
| BR-E02 | Prevent Duplicate Snapshot | `x_snc_ecosentine_0_env_snapshot` | Before | Insert | Snapshot already exists for complaint |

---

# Section 2: Client Scripts

## 2.1 — Service Portal: Complaint Submission Form (Record Producer)

---

### CS-P01: Auto-Capture GPS Location on Load

| Property | Value |
|---|---|
| **Table / View** | Record Producer: "Report Environmental Incident" |
| **Type** | onLoad |
| **Purpose** | Silently capture the citizen's GPS coordinates via HTML5 Geolocation API and populate `incident_lat` and `incident_lng` fields. |

**Why needed**: The AI pipeline requires coordinates to fetch AQI and weather data. If the citizen has to manually type coordinates (or worse, the fields are empty), the Severity Fusion Agent cannot function.

**Logic / Pseudocode**:
```javascript
function onLoad() {
    // Hide lat/lng fields from the citizen — they are populated silently
    g_form.setDisplay('incident_lat', false);
    g_form.setDisplay('incident_lng', false);

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                g_form.setValue('incident_lat', position.coords.latitude.toFixed(6));
                g_form.setValue('incident_lng', position.coords.longitude.toFixed(6));
                // Optionally reverse-geocode for display
                g_form.addInfoMessage('Location captured successfully.');
            },
            function(error) {
                g_form.addErrorMessage(
                    'Unable to capture your location. Please allow location access ' +
                    'or manually enter the address in the Address field.');
                // Show address field as mandatory fallback
                g_form.setMandatory('incident_address', true);
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    } else {
        g_form.addErrorMessage('Geolocation is not supported by your browser. ' +
            'Please enter the address manually.');
        g_form.setMandatory('incident_address', true);
    }
}
```

---

### CS-P02: Validate Before Submit

| Property | Value |
|---|---|
| **Table / View** | Record Producer: "Report Environmental Incident" |
| **Type** | onSubmit |
| **Purpose** | Block submission if mandatory evidence is missing: description must be ≥ 20 characters, GPS must be captured (or address provided), and category must be selected. |

**Why needed**: The AI pipeline needs meaningful input. A one-word description like "bad" gives OpenAI nothing to work with. Missing location means no AQI/weather lookup. These guards ensure every submission is AI-ready.

**Logic / Pseudocode**:
```javascript
function onSubmit() {
    var desc = g_form.getValue('description');
    var lat = g_form.getValue('incident_lat');
    var lng = g_form.getValue('incident_lng');
    var addr = g_form.getValue('incident_address');
    var category = g_form.getValue('incident_category');

    // Validate description length
    if (!desc || desc.length < 20) {
        g_form.addErrorMessage(
            'Please provide a description of at least 20 characters ' +
            'so our AI can accurately assess the issue.');
        g_form.flash('description', '#ff6b6b', 0);
        return false;
    }

    // Validate location
    if ((!lat || !lng) && !addr) {
        g_form.addErrorMessage(
            'Location is required. Please allow GPS access or enter an address.');
        return false;
    }

    // Validate category
    if (!category) {
        g_form.addErrorMessage('Please select an incident category.');
        return false;
    }

    return true;
}
```

---

### CS-P03: Category Change — Show/Hide Contextual Fields

| Property | Value |
|---|---|
| **Table / View** | Record Producer: "Report Environmental Incident" |
| **Type** | onChange |
| **Field** | `incident_category` |
| **Purpose** | Show a contextual info message based on the selected category to guide the citizen on what to photograph. |

**Why needed**: Better photos = better AI analysis. Guiding the citizen improves the quality of input data for the entire downstream pipeline.

**Logic / Pseudocode**:
```javascript
function onChange(control, oldValue, newValue, isLoading) {
    if (isLoading) return;

    g_form.hideAllFieldMsgs();

    var tips = {
        'air_pollution': 'Tip: Photograph the smoke/emission source from a safe distance.',
        'water_pollution': 'Tip: Photograph the water discoloration or discharge point.',
        'illegal_dumping': 'Tip: Photograph the dumped materials and surrounding area.',
        'chemical_spill': 'Tip: Stay at a safe distance. Photograph warning signs and the spill area.',
        'noise_pollution': 'Tip: Note the time and duration in your description.',
        'land_contamination': 'Tip: Photograph any discolored soil, dead vegetation, or barrels.',
        'other': 'Tip: Provide as much detail and photographic evidence as possible.'
    };

    if (tips[newValue]) {
        g_form.showFieldMsg('description', tips[newValue], 'info');
    }
}
```

---

## 2.2 — Complaint Form (Officer / Agent View — Standard UI)

---

### CS-C01: Display AI Rationale Info Box

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_complaint` — Default view |
| **Type** | onLoad |
| **Purpose** | Render the AI rationale, severity, and confidence prominently in a styled info message at the top of the form so any officer reviewing the complaint immediately sees the AI's reasoning. |

**Why needed**: The AI rationale is the core differentiator — explainable decisions, not black-box labels. If it's buried in a text field, no one reads it. An info box makes it the first thing the officer sees.

**Logic / Pseudocode**:
```javascript
function onLoad() {
    var severity = g_form.getValue('ai_severity');
    var confidence = g_form.getValue('ai_confidence');
    var rationale = g_form.getValue('ai_rationale');

    if (severity && rationale) {
        var severityLabel = g_form.getDisplayBox('ai_severity').value || severity;
        var color = { 'high': '🔴', 'medium': '🟡', 'low': '🟢' };
        var icon = color[severity] || '⚪';

        var msg = icon + ' <strong>AI Classification: ' + severityLabel.toUpperCase() +
                  '</strong> (Confidence: ' + confidence + '%)<br/>' +
                  '<em>' + rationale + '</em>';

        g_form.addInfoMessage(msg);
    }

    // Make AI fields read-only — only the backend can write these
    g_form.setReadOnly('ai_severity', true);
    g_form.setReadOnly('ai_confidence', true);
    g_form.setReadOnly('ai_rationale', true);
    g_form.setReadOnly('ai_image_caption', true);
    g_form.setReadOnly('ai_classified_at', true);
}
```

---

### CS-C02: Officer Override Severity — Role-Gated

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_complaint` — Default view |
| **Type** | onLoad |
| **Field** | — |
| **Purpose** | Hide the manual severity override fields unless the user has the `x_snc_ecosentine_0.officer` or `x_snc_ecosentine_0.admin` role. |

**Why needed**: Inspectors should not be able to override the AI's severity — that's an officer-level decision. Without this gate, any user with write access could change the severity, undermining the AI classification and SLA assignment.

**Logic / Pseudocode**:
```javascript
function onLoad() {
    // GlideAjax call to check role (cannot reliably check roles client-side in scoped apps)
    var ga = new GlideAjax('x_snc_ecosentine_0.EcoComplaintUtils');
    ga.addParam('sysparm_name', 'hasOfficerRole');
    ga.getXMLAnswer(function(answer) {
        var isOfficer = (answer === 'true');
        g_form.setDisplay('override_severity', isOfficer);
        g_form.setDisplay('override_reason', isOfficer);
    });
}
```

---

### CS-C03: Override Reason Mandatory When Override Severity Set

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_complaint` — Default view |
| **Type** | onChange |
| **Field** | `override_severity` |
| **Purpose** | Make `override_reason` mandatory when an officer sets an override severity, and clear it when the override is removed. |

**Why needed**: An override without a reason is unauditable. Judges and compliance reviewers need to see why a human disagreed with the AI.

**Logic / Pseudocode**:
```javascript
function onChange(control, oldValue, newValue, isLoading) {
    if (isLoading) return;

    if (newValue) {
        g_form.setMandatory('override_reason', true);
        g_form.showFieldMsg('override_reason',
            'Please explain why you are overriding the AI classification.', 'info');
    } else {
        g_form.setMandatory('override_reason', false);
        g_form.setValue('override_reason', '');
        g_form.hideFieldMsg('override_reason');
    }
}
```

---

## 2.3 — Inspection Form (Inspector — Now Mobile / Standard UI)

---

### CS-I01: Violation Toggle — Show/Hide Fields

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_inspection` — Default view |
| **Type** | onChange |
| **Field** | `violation_confirmed` |
| **Purpose** | When the inspector toggles "Violation Confirmed" to true, show and make mandatory the `violation_type` field. When false, hide it. |

**Why needed**: Showing violation type for non-violations is confusing and leads to dirty data. This keeps the form clean and context-sensitive.

**Logic / Pseudocode**:
```javascript
function onChange(control, oldValue, newValue, isLoading) {
    var isViolation = (newValue === 'true' || newValue === true);

    g_form.setDisplay('violation_type', isViolation);
    g_form.setMandatory('violation_type', isViolation);

    if (!isViolation) {
        g_form.setValue('violation_type', '');
    }
}
```

---

### CS-I02: Violation Toggle — Initial State on Load

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_inspection` — Default view |
| **Type** | onLoad |
| **Purpose** | Set the initial visibility of violation-dependent fields when the form first loads. Also auto-populate GPS if available. |

**Why needed**: Without an onLoad script, the violation_type field is always visible on a fresh load, regardless of the violation_confirmed value.

**Logic / Pseudocode**:
```javascript
function onLoad() {
    var isViolation = g_form.getValue('violation_confirmed') === 'true';
    g_form.setDisplay('violation_type', isViolation);
    g_form.setMandatory('violation_type', isViolation);

    // Make linked fields read-only
    g_form.setReadOnly('parent_complaint', true);
    g_form.setReadOnly('inspected_facility', true);
    g_form.setReadOnly('linked_legal_case', true);
    g_form.setReadOnly('ai_report', true);

    // Auto-capture GPS for mobile inspectors
    if (navigator.geolocation && !g_form.getValue('inspector_lat')) {
        navigator.geolocation.getCurrentPosition(function(pos) {
            g_form.setValue('inspector_lat', pos.coords.latitude.toFixed(6));
            g_form.setValue('inspector_lng', pos.coords.longitude.toFixed(6));
        });
    }
}
```

---

### CS-I03: Validate Before Submitting Violation

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_inspection` — Default view |
| **Type** | onSubmit |
| **Purpose** | If the inspector is confirming a violation, require that raw_notes are filled and GPS is captured. |

**Why needed**: Server-side BR-I05 enforces findings exist, but client-side validation gives immediate feedback before the round-trip, improving the mobile experience.

**Logic / Pseudocode**:
```javascript
function onSubmit() {
    var isViolation = g_form.getValue('violation_confirmed') === 'true';

    if (isViolation) {
        var rawNotes = g_form.getValue('raw_notes');
        if (!rawNotes || rawNotes.length < 10) {
            g_form.addErrorMessage(
                'Please provide inspector notes describing the violation before confirming.');
            return false;
        }

        var lat = g_form.getValue('inspector_lat');
        var lng = g_form.getValue('inspector_lng');
        if (!lat || !lng) {
            g_form.addErrorMessage(
                'GPS coordinates are required to confirm a violation. ' +
                'Please allow location access on your device.');
            return false;
        }
    }

    return true;
}
```

---

## 2.4 — Facility Form (Officer / Admin View)

---

### CS-F01: Risk Score Visual Indicator

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_facility` — Default view |
| **Type** | onLoad |
| **Purpose** | Make the risk score and related fields read-only (they are system-calculated), and display a color-coded info message based on the risk tier. |

**Why needed**: Officers need to instantly recognise a facility's risk level without reading a number. A red banner for critical-risk facilities is far more effective than a plain integer field.

**Logic / Pseudocode**:
```javascript
function onLoad() {
    // Make calculated fields read-only
    g_form.setReadOnly('risk_score', true);
    g_form.setReadOnly('risk_tier', true);
    g_form.setReadOnly('high_risk', true);
    g_form.setReadOnly('violations_12m', true);
    g_form.setReadOnly('complaints_90d', true);
    g_form.setReadOnly('report_overdue', true);

    var score = parseInt(g_form.getValue('risk_score'));
    var tier = g_form.getValue('risk_tier');

    var msgs = {
        'critical': '🔴 CRITICAL RISK (Score: ' + score + '/100) — This facility requires immediate priority inspection.',
        'elevated': '🟠 ELEVATED RISK (Score: ' + score + '/100) — This facility should be monitored closely.',
        'standard': '🟡 STANDARD RISK (Score: ' + score + '/100) — Routine monitoring schedule.',
        'low':      '🟢 LOW RISK (Score: ' + score + '/100) — No immediate concerns.'
    };

    if (msgs[tier]) {
        g_form.addInfoMessage(msgs[tier]);
    }
}
```

---

### CS-F02: Sector Change — Info Message

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_facility` — Default view |
| **Type** | onChange |
| **Field** | `sector` |
| **Purpose** | Warn the admin that changing sector to Chemical or Mining will add +20 to the risk score on the next recalculation. |

**Why needed**: The risk score formula treats chemical and mining as high-risk sectors. An admin changing the sector should understand the downstream impact before saving.

**Logic / Pseudocode**:
```javascript
function onChange(control, oldValue, newValue, isLoading) {
    if (isLoading) return;

    g_form.hideAllFieldMsgs('sector');

    if (newValue === 'chemical' || newValue === 'mining') {
        g_form.showFieldMsg('sector',
            'High-risk sector: +20 points will be added to the Compliance Risk Score on next recalculation.',
            'warning');
    }
}
```

---

## 2.5 — Legal Case Form

---

### CS-L01: Validate Evidence Chain on Load

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_legal_case` — Default view |
| **Type** | onLoad |
| **Purpose** | Make the source complaint, source inspection, and violating facility fields read-only (they should never be changed after creation) and display a warning if the case narrative is empty (indicating the Legal Case Summary Agent hasn't run yet). |

**Why needed**: Legal cases are auto-created by FL-05 / EcoInspectionWorkflow. Their source references are the evidence chain and must not be editable. The narrative warning prompts the officer to trigger the AI agent if it hasn't run.

**Logic / Pseudocode**:
```javascript
function onLoad() {
    // Lock source references
    g_form.setReadOnly('source_complaint', true);
    g_form.setReadOnly('source_inspection', true);
    g_form.setReadOnly('violating_facility', true);

    // Check if narrative exists
    var narrative = g_form.getValue('case_narrative');
    if (!narrative) {
        g_form.addWarningMessage(
            'Case narrative has not been generated yet. ' +
            'The Legal Case Summary Agent will populate this field automatically. ' +
            'If it remains empty, contact an admin to trigger the agent manually.');
    }
}
```

---

### CS-L02: Penalty Amount — Show/Hide Based on Type

| Property | Value |
|---|---|
| **Table / View** | `x_snc_ecosentine_0_legal_case` — Default view |
| **Type** | onChange |
| **Field** | `penalty_type` |
| **Purpose** | Only show the `penalty_amount` field when `penalty_type` = "fine". Hide for all other penalty types. |

**Why needed**: Showing a dollar amount field for a "Written Warning" or "Criminal Referral" is confusing and invites incorrect data entry.

**Logic / Pseudocode**:
```javascript
function onChange(control, oldValue, newValue, isLoading) {
    if (isLoading) return;

    var showAmount = (newValue === 'fine');
    g_form.setDisplay('penalty_amount', showAmount);
    g_form.setMandatory('penalty_amount', showAmount);

    if (!showAmount) {
        g_form.setValue('penalty_amount', '');
    }
}
```

---

## 2.6 — Client Script Summary Matrix

| ID | Name | Table / Context | Type | Field | Purpose |
|---|---|---|---|---|---|
| CS-P01 | Auto-Capture GPS | Record Producer (Service Portal) | onLoad | — | Capture citizen GPS silently |
| CS-P02 | Validate Before Submit | Record Producer (Service Portal) | onSubmit | — | Block submission without description/location/category |
| CS-P03 | Category Tips | Record Producer (Service Portal) | onChange | `incident_category` | Show photo tips per category |
| CS-C01 | AI Rationale Info Box | `x_snc_ecosentine_0_complaint` | onLoad | — | Display AI reasoning prominently |
| CS-C02 | Officer Override Gate | `x_snc_ecosentine_0_complaint` | onLoad | — | Hide override fields for non-officers |
| CS-C03 | Override Reason Mandatory | `x_snc_ecosentine_0_complaint` | onChange | `override_severity` | Require reason when overriding AI |
| CS-I01 | Violation Toggle Fields | `x_snc_ecosentine_0_inspection` | onChange | `violation_confirmed` | Show/hide violation type |
| CS-I02 | Inspection Form Init | `x_snc_ecosentine_0_inspection` | onLoad | — | Set initial visibility + GPS capture |
| CS-I03 | Validate Violation Submit | `x_snc_ecosentine_0_inspection` | onSubmit | — | Require notes and GPS for violations |
| CS-F01 | Risk Score Indicator | `x_snc_ecosentine_0_facility` | onLoad | — | Color-coded risk display |
| CS-F02 | Sector Change Warning | `x_snc_ecosentine_0_facility` | onChange | `sector` | Warn about risk score impact |
| CS-L01 | Evidence Chain Lock | `x_snc_ecosentine_0_legal_case` | onLoad | — | Lock source refs + narrative warning |
| CS-L02 | Penalty Amount Toggle | `x_snc_ecosentine_0_legal_case` | onChange | `penalty_type` | Show amount only for fines |

---

## GlideAjax ↔ Script Include Pairing Reference

| Client Script | GlideAjax Call | Script Include | Method | Purpose |
|---|---|---|---|---|
| CS-C02 | `EcoComplaintUtils` → `hasOfficerRole` | `EcoComplaintUtils` (SI-02) | `hasOfficerRole()` | Check if current user has officer/admin role |
| Citizen Tracker Widget | `EcoComplaintUtils` → `lookupComplaint` | `EcoComplaintUtils` (SI-02) | `lookupComplaint()` | Look up complaint by number + email |
| BR-C07, FL-05, BR-I04 fallback | Direct server-side call | `EcoRiskCalculator` (SI-01) | `recalculate(facilitySysId)` | Recalculate facility risk score |
| BR-C03, FL-05, BR-I04 fallback | Direct server-side call | `EcoAgentLogger` (SI-03) | `log(params)` | Write to Agent Decision Log |
| FL-05 | Flow Designer Script Step | `EcoInspectionWorkflow` (SI-05) | `confirmViolation()` / `dismissInspection()` | Idempotently route completed inspection outcomes |
