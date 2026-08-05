# EcoSentinel AI — Script Includes

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_snc_ecosentine_0_`  
> **Reference Documents**: [tables.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/tables.md) · [business-rules-client-scripts.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/business-rules-client-scripts.md) · [flow-designer-flows.md](file:///C:/Users/yuvra/OneDrive/Desktop/Servicenow/ServiceNowxDelloite/flow-designer-flows.md)  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

# Section 1: Roster

> **Note**: This file (`script-includes.md`) is the **Single Source of Truth** for all Script Includes. While other files (like `business-rules-client-scripts.md`) may summarize or reference these utilities, the implementations defined here are the canonical versions that must be followed.

| Script Include Name | Client Callable | Purpose | Called From |
|---|---|---|---|
| **EcoRiskCalculator** | No | Performs facility environmental risk score math. | `BR-C07`, `BR-I04`, `BR-F03`, `BR-F04`, `FL-05`, `FL-06` |
| **EcoComplaintUtils** | **Yes** | Handles Ajax lookup requests for portal and roles. | `CS-C02` (Client Script), Citizen Tracker Portal Widget |
| **EcoAgentLogger** | No | Writes immutable log records to the Agent Decision Log table. | `BR-C03`, `BR-I04`, `FL-02`, `FL-05`, `FL-07`, `FL-08`, `FL-10` |
| **EcoConstants** | No | Centralizes state values and table names to avoid magic strings. | `EcoInspectionWorkflow`, Flows |
| **EcoInspectionWorkflow**| No | Server-side helper providing idempotent functions for inspection completion. | `FL-05` (Flow Designer Script Step) |
| **EcoComplaintNumberGenerator** | No | Creates unique incident tracking numbers (ES-YYYY-MMDD-####).| `BR-C01` (Before Insert Business Rule) |
| **EcoUrgencyScoreCalculator** | No | Combines raw severity index + facility risk index for priority rankings.| Custom portal dashboard widgets, list view columns |
| **EcoSLADueDateCalculator** | No | Computes due date/times based on severity and business schedule.| Flow steps, custom script task allocations |

---

# Section 2: Detailed Specifications

---

## 2.1 — EcoRiskCalculator
* **Client Callable**: No
* **Purpose**: Implements the facility risk score calculations.
* **Called From**: `BR-C07`, `BR-I04`, `BR-F03`, `BR-F04`, `FL-05`, `FL-06`

### Function Signature
`recalculate(facilitySysId)`
- **Parameters**: `facilitySysId` (String - target facility `sys_id`)
- **Returns**: None (Updates record in-place)

### Logic / Pseudocode
```javascript
var EcoRiskCalculator = Class.create();
EcoRiskCalculator.prototype = {
    initialize: function() {},

    recalculate: function(facilitySysId) {
        if (!facilitySysId) return;

        var facility = new GlideRecord('x_snc_ecosentine_0_facility');
        if (facility.get(facilitySysId)) {
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

            facility.update();
        }
    },
    type: 'EcoRiskCalculator'
};
```

---

## 2.2 — EcoComplaintUtils
* **Client Callable**: Yes
* **Purpose**: GlideAjax processor interface backing Portal UI Widgets and Client Scripts.
* **Called From**: `CS-C02` (Client Script), Citizen Tracker Portal Widget

### Function Signatures
1. `hasOfficerRole()`
   - **Parameters**: None
   - **Returns**: `"true"` or `"false"` (String)
2. `lookupComplaint(params)`
   - **Parameters**: Server-side callers pass `{ number: 'ES-20260731-0042', email: 'citizen@example.com' }`; GlideAjax portal callers may still provide `sysparm_number` and `sysparm_email`.
   - **Returns**: JSON-formatted string matching the integration schema

### Logic / Pseudocode
```javascript
var EcoComplaintUtils = Class.create();
EcoComplaintUtils.prototype = Object.extendsObject(AbstractAjaxProcessor, {

    hasOfficerRole: function() {
        return gs.hasRole('x_snc_ecosentine_0.officer') || gs.hasRole('x_snc_ecosentine_0.admin');
    },

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

    type: 'EcoComplaintUtils'
});
```

---

## 2.3 — EcoAgentLogger
* **Client Callable**: No
* **Purpose**: Centralised helper that inserts logging entries to `x_snc_ecosentine_0_agent_decisi` while preserving immutability constraints.
* **Called From**: `BR-C03`, `BR-I04`, `FL-02`, `FL-05`, `FL-07`, `FL-08`, `FL-10`

### Function Signature
`log(params)`
- **Parameters**: `params` (JavaScript Object - must contain `agentName`, `agentType`, `linkedTable`, `linkedRecord`, `inputSummary`, `outputSummary`, `status`)
- **Returns**: String (sys_id of inserted log record)

### Logic / Pseudocode
```javascript
var EcoAgentLogger = Class.create();
EcoAgentLogger.prototype = {
    initialize: function() {},

    log: function(params) {
        if (!params || !params.agentName || !params.linkedTable || !params.linkedRecord) {
            gs.error('EcoAgentLogger: Missing mandatory parameters for logging.');
            return null;
        }

        var logGr = new GlideRecord('x_snc_ecosentine_0_agent_decisi');
        logGr.initialize();
        logGr.setValue('agent_name', params.agentName);
        logGr.setValue('agent_type', params.agentType || 'native');
        logGr.setValue('linked_table', params.linkedTable);
        logGr.setValue('linked_record', params.linkedRecord);
        logGr.setValue('linked_record_number', params.linkedRecordNumber || '');
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

## 2.4 — EcoConstants
* **Client Callable**: No
* **Purpose**: Centralizes state values, choice values, and table names so Business Rules and Flows do not duplicate magic numbers.
* **Called From**: `EcoInspectionWorkflow`, Flow Script Steps

### Function Signature
(Properties and helper functions)
- **Returns**: Maps of strings/ints.

### Logic / Pseudocode
```javascript
var EcoConstants = Class.create();
EcoConstants.prototype = {
    initialize: function() {},
    tables: {
        complaint: 'x_snc_ecosentine_0_complaint',
        facility: 'x_snc_ecosentine_0_facility',
        inspection: 'x_snc_ecosentine_0_inspection',
        legalCase: 'x_snc_ecosentine_0_legal_case',
        agentLog: 'x_snc_ecosentine_0_agent_decisi',
        envSnapshot: 'x_snc_ecosentine_0_env_snapshot',
        finding: 'x_snc_ecosentine_0_finding'
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

## 2.5 — EcoInspectionWorkflow
* **Client Callable**: No
* **Purpose**: Server-side helper for FL-05. Provides idempotent functions to handle completed inspections.
* **Called From**: `FL-05` Flow Action

### Function Signatures
`confirmViolation(inspectionSysId)`
`dismissInspection(inspectionSysId)`

### Logic / Pseudocode
```javascript
var EcoInspectionWorkflow = Class.create();
EcoInspectionWorkflow.prototype = {
    initialize: function() { this.C = new EcoConstants(); },
    
    confirmViolation: function(inspectionSysId) {
        // Creates a legal case only if one doesn't exist for this inspection
        // Updates complaint state to Action Taken
        // Recalculates facility risk
    },
    
    dismissInspection: function(inspectionSysId) {
        // Updates complaint state to Dismissed
    },
    type: 'EcoInspectionWorkflow'
};
```

---

## 2.6 — EcoComplaintNumberGenerator
* **Client Callable**: No
* **Purpose**: Generates unique tracking numbers in `ES-YYYY-MMDD-####` format.
* **Called From**: `BR-C01` (Before Insert Business Rule)

### Function Signature
`generateNumber()`
- **Parameters**: None
- **Returns**: String (formatted unique number)

### Logic / Pseudocode
```javascript
var EcoComplaintNumberGenerator = Class.create();
EcoComplaintNumberGenerator.prototype = {
    initialize: function() {},

    generateNumber: function() {
        var gdt = new GlideDateTime();
        var year = gdt.getYearLocalTime().toString();
        
        // Zero pad month and day
        var month = (gdt.getMonthLocalTime()).toString();
        if (month.length === 1) month = '0' + month;
        
        var day = gdt.getDayOfMonthLocalTime().toString();
        if (day.length === 1) day = '0' + day;
        
        var dateString = year + month + day;
        var prefix = 'ES-' + dateString + '-';
        
        // Query to find the highest sequence number created today
        var gr = new GlideRecord('x_snc_ecosentine_0_complaint');
        gr.addQuery('number', 'STARTSWITH', prefix);
        gr.orderByDesc('number');
        gr.setLimit(1);
        gr.query();
        
        var nextSeq = 1;
        if (gr.next()) {
            var currentNumber = gr.getValue('number'); // e.g. ES-20260731-0042-X7Q
            var parts = currentNumber.split('-');
            if (parts.length >= 3) {
                var lastPart = parseInt(parts[2], 10);
                if (!isNaN(lastPart)) {
                    nextSeq = lastPart + 1;
                }
            }
        }
        
        // Pad sequence to 4 digits
        var seqString = nextSeq.toString();
        while (seqString.length < 4) {
            seqString = '0' + seqString;
        }

        // Generate 3 random alphanumeric characters for entropy
        var chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        var entropy = "";
        for (var i = 0; i < 3; i++) {
            entropy += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        
        return prefix + seqString + '-' + entropy; // Returns format: ES-YYYYMMDD-####-XXX
    },

    type: 'EcoComplaintNumberGenerator'
};
```

---

## 2.7 — EcoUrgencyScoreCalculator
* **Client Callable**: No
* **Purpose**: Combines complaint severity index and facility risk to generate a composite score. Used to rank the inspector's dispatch dashboard queue.
* **Called From**: List view calculations, Dashboard reports

### Function Signature
`getCompositeUrgency(complaintSysId)`
- **Parameters**: `complaintSysId` (String - complaint record ID)
- **Returns**: Integer (Composite score between 0 and 100)

### Logic / Pseudocode
```javascript
var EcoUrgencyScoreCalculator = Class.create();
EcoUrgencyScoreCalculator.prototype = {
    initialize: function() {},

    getCompositeUrgency: function(complaintSysId) {
        var complaint = new GlideRecord('x_snc_ecosentine_0_complaint');
        if (!complaint.get(complaintSysId)) return 0;

        // Map AI severity to raw weight (60% of composite)
        var severityWeight = 0;
        var severity = complaint.getValue('ai_severity');
        if (severity === 'high') severityWeight = 60;
        else if (severity === 'medium') severityWeight = 40;
        else if (severity === 'low') severityWeight = 20;

        // Map facility risk index if linked (40% of composite)
        var facilityWeight = 0;
        if (!complaint.linked_facility.nil()) {
            var facility = new GlideRecord('x_snc_ecosentine_0_facility');
            if (facility.get(complaint.linked_facility)) {
                var riskScore = parseInt(facility.getValue('risk_score'), 10) || 0;
                facilityWeight = Math.round(riskScore * 0.40);
            }
        }

        return severityWeight + facilityWeight;
    },

    type: 'EcoUrgencyScoreCalculator'
};
```

---

## 2.8 — EcoSLADueDateCalculator
* **Client Callable**: No
* **Purpose**: Returns absolute due Date/Times based on incident severity.
* **Called From**: Flow Designer custom actions, SLA trigger scripts

### Function Signature
`calculateDueDate(severity, fromDateTime)`
- **Parameters**: `severity` (String - high/medium/low), `fromDateTime` (GlideDateTime - start anchor)
- **Returns**: GlideDateTime (absolute deadline)

### Logic / Pseudocode
```javascript
var EcoSLADueDateCalculator = Class.create();
EcoSLADueDateCalculator.prototype = {
    initialize: function() {},

    calculateDueDate: function(severity, fromDateTime) {
        var start = fromDateTime || new GlideDateTime();
        var deadline = new GlideDateTime(start);

        // Simple raw calculation (SLA engine utilizes 24x7 schedule for PDI)
        if (severity === 'high') {
            deadline.addDaysUTC(1); // 24 Hours
        } else if (severity === 'medium') {
            deadline.addDaysUTC(3); // 72 Hours
        } else {
            deadline.addDaysUTC(7); // 7 Days
        }

        return deadline;
    },

    type: 'EcoSLADueDateCalculator'
};
```
