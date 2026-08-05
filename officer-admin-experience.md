# EcoSentinel AI — Officer & Admin Experience

This document explicitly defines how internal personas—Compliance Officers, Legal Case Handlers, and System Administrators—interact with EcoSentinel AI. It ensures that the internal UI configuration is completely aligned with the underlying data model, security roles, and AI integrations defined in previous specifications.

---

## 1. Architecture Decision

The EcoSentinel interface for Compliance Officers, Legal Case Handlers, and System Administrators relies entirely on the **standard ServiceNow backend UI** (native forms, lists, related lists, and UI Actions)—*not* the Service Portal (which is citizen-only, as per `service-portal-pages-widgets.md`), and *not* a custom UI Builder Workspace.

**Strategic Justification (Hackathon Context):**
Building within the standard backend UI is the fastest path to a fully-featured, secure, role-scoped internal experience within an 8-day build. It demonstrates the core strength of the ServiceNow platform—leveraging out-of-the-box ACLs, related lists, UI Policies, and automated workflows—rather than spending precious build time recreating UI elements that the platform already provides natively. 

This is a deliberate architecture choice to ensure 100% functional completeness and auditability for day-one deployment. A custom UI Builder Workspace is officially documented as a post-hackathon roadmap item for future polish.

---

## 2. Officer Experience Walkthrough

Compliance Officers (`x_snc_ecosentine_0.officer`) manage the triage, dispatch, and escalation of environmental incidents. Their daily workflow is executed through specific native views.

### 2.1 Complaint List View
- **View Name**: `EcoSentinel Officer View` (Table: `x_snc_ecosentine_0_complaint`)
- **Default Filter**: `Active is true` OR `State is not Closed/Dismissed`, sorted by `priority` (Urgency Score) ascending, then `sys_created_on` descending.
- **Columns Shown**: Number, Priority, AI Severity, State, Linked Facility, Location, Created.
- **Experience**: The officer starts their day here, pulling the highest priority items (automatically scored by `EcoUrgencyScoreCalculator`) from the top of the queue.

### 2.2 Complaint Form View
- **View Name**: `EcoSentinel Officer View` (Table: `x_snc_ecosentine_0_complaint`)
- **Key Sections**:
  - **Incident Details**: Citizen description, location, attachments (photos).
  - **AI Fusion Output (Read-Only)**: Displays `ai_severity`, `ai_confidence`, `ai_rationale`, and `ai_image_caption` (populated by the AI Agents).
  - **AI Override Control**: The `ai_severity` field has a UI Policy/ACL allowing *only* users with the `x_snc_ecosentine_0.officer` or `x_snc_ecosentine_0.admin` role to manually override the AI's classification if they disagree with the AI's assessment.
- **Related Lists Included**:
  - Inspections (`x_snc_ecosentine_0_inspection`)
  - Legal Cases (`x_snc_ecosentine_0_legal_case`)
  - Agent Decision Logs (`x_snc_ecosentine_0_agent_decisi`)

### 2.3 Facility List & Form View
- **View Name**: `Default view` (Table: `x_snc_ecosentine_0_facility`)
- **Form Display**: Prominently shows the Facility Name, IRM Entity linkage (per `irm-legal-config.md`), and the dynamically calculated `risk_score`.
- **Related Lists**: Complaint History, Inspection History.
- **Experience**: Officers use this view to assess the historical non-compliance of a facility when deciding whether to escalate an inspection to a legal case.

### 2.4 Agent Decision Log Review
- **View Name**: `Default view` (Table: `x_snc_ecosentine_0_agent_decisi` as a related list on Complaint)
- **Experience**: Officers review this append-only log to audit exactly what the AI Control Tower logged during the Severity Fusion Agent's execution. This guarantees 100% explainability for regulatory audits.

### 2.5 High-Risk Facility Alert Handling
- **Experience**: When a facility crosses the high-risk threshold, `SF-02` sends an email/notification to the Compliance Officers group. The notification contains a deep-link URI directly to the `x_snc_ecosentine_0_facility` form view, allowing the officer to immediately review the facility's risk breakdown and trigger manual re-inspections if necessary.

---

## 3. Legal Case Handler Experience

Legal Case Handlers (`x_snc_ecosentine_0.legal_handler`, optionally mapped to `sn_grc.business_user` / `sn_grc.manager` for IRM/LSD plugin compatibility) operate within the ServiceNow Legal Service Delivery / IRM ecosystem.

### 3.1 Legal Case List View
- **View Name**: `EcoSentinel Legal View` (Table: `x_snc_ecosentine_0_legal_case`)
- **Default Filter**: `Active is true`, sorted by `sys_created_on` descending.
- **Columns Shown**: Number, State, Violating Facility, Violation Type, Source Inspection.

### 3.2 Legal Case Form View
- **View Name**: `EcoSentinel Legal View` (Table: `x_snc_ecosentine_0_legal_case`)
- **Form Display**:
  - **Read-Only Context**: Details synced from the `x_snc_ecosentine_0_inspection` and `x_snc_ecosentine_0_complaint` (Facility, Violation Type, Initial AI Severity).
  - **Editable Fields**: Case State, Legal Notes, Resolution SLA tracking.
- **Related Lists Included**:
  - Source Complaint (`x_snc_ecosentine_0_complaint` - single record list)
  - Source Inspection (`x_snc_ecosentine_0_inspection` - single record list)
- **Experience**: Legal handlers work the case through to resolution (fines, remediation). Closing the legal case triggers `FL-11: Legal Case Resolution Sync`, which closes the parent complaint and updates the IRM Risk/Compliance posture for the facility as configured in `irm-legal-config.md`.

---

## 4. System Administrator Experience

System Administrators (`x_snc_ecosentine_0.admin` and `admin`) configure the underlying AI engines and platform routing. All administrative tasks are performed in standard ServiceNow admin navigation modules. No custom UI is required.

- **AI Agent Fabric Config**: Accessed via `Now Assist > AI Agent Fabric` to configure the connection to external endpoints (OpenAI).
- **AI Agent Orchestrator**: Accessed via `Now Assist > AI Agent Studio` to sequence the Native Now Assist skills and external agents.
- **AI Control Tower**: Accessed via the native `Now Assist > AI Control Tower` dashboard to monitor token usage, agent success rates, and system health.
- **Scoped App Config**: General properties, SLA definitions, and flow management are handled in standard App Engine Studio / Studio environments.

---

## 5. List View & Related List Configuration Table

*A reference for developers to configure these views directly in Studio / List Editor.*

| Base Table | View Name | Type | Columns/Fields Shown | Default Filter | Default Sort |
|---|---|---|---|---|---|
| `x_snc_ecosentine_0_complaint` | EcoSentinel Officer View | List | Number, Priority, AI Severity, State, Linked Facility, Location, Created | `Active = true` | `priority` (asc), `sys_created_on` (desc) |
| `x_snc_ecosentine_0_complaint` | EcoSentinel Officer View | Related List | (Inspections) Number, State, Assigned to, Violation Type | None | `sys_created_on` (desc) |
| `x_snc_ecosentine_0_complaint` | EcoSentinel Officer View | Related List | (Legal Cases) Number, State, Violation Type | None | `sys_created_on` (desc) |
| `x_snc_ecosentine_0_complaint` | EcoSentinel Officer View | Related List | (Agent Logs) Step, Action Taken, Confidence, Created | None | `sys_created_on` (desc) |
| `x_snc_ecosentine_0_facility` | Default view | List | Name, Risk Score, Complaints (90d), Last Inspection, IRM Entity | `Active = true` | `risk_score` (desc) |
| `x_snc_ecosentine_0_facility` | Default view | Related List | (Complaints) Number, State, AI Severity, Created | None | `sys_created_on` (desc) |
| `x_snc_ecosentine_0_legal_case`| EcoSentinel Legal View | List | Number, State, Violating Facility, Violation Type, Source Inspection | `Active = true` | `sys_created_on` (desc) |

---

## 6. Judge Q&A Prep Note

During a hackathon pitch, judges frequently ask why certain personas use specific interfaces. Use these crisp, 2-3 sentence answers to defend the architecture:

* **Q: Why aren't citizens using the Now Mobile app?**
  * **A:** "Citizens need a frictionless, immediate way to report pollution without downloading an app or creating an account. A public-facing Service Portal Record Producer with a responsive mobile-web design removes all adoption barriers while maintaining security via CAPTCHA and rate limiting."

* **Q: Why aren't Compliance Officers using the Service Portal?**
  * **A:** "The Service Portal is optimized for simple, guided intake. Officers need dense, data-rich interfaces with relational context—like related lists for inspections and audit logs, and complex list filtering. The native ServiceNow backend provides this relational power out-of-the-box."

* **Q: Why didn't you build a custom UI Builder Workspace for the Officers?**
  * **A:** "Our priority for this 8-day build was demonstrating a robust, end-to-end AI workflow and strict data security. The native UI gives us a fully functional, role-scoped, and auditable experience instantly. A custom Workspace is on our immediate post-hackathon roadmap for UI polish, but it wasn't required to prove the core platform value."
