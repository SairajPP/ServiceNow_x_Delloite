# EcoSentinel AI — Master End-to-End System Walkthrough

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_eco_`  
> **Platform**: ServiceNow PDI (Xanadu release)  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow  
> **Purpose**: This document serves as the master narrative tying together all 16 technical specification files. It does not redefine any architecture; rather, it tells the continuous, plain-English story of how a single environmental incident flows through the entire system from discovery to prosecution and executive reporting.

---

## The Vision: What is EcoSentinel AI?

EcoSentinel AI is an end-to-end environmental compliance platform. It bridges the gap between public citizens reporting pollution and the regulatory agencies responsible for enforcing environmental law. By fusing ServiceNow's workflow automation with a multi-agent AI architecture, EcoSentinel reduces the time it takes to triage a report, dispatch an inspector, and prosecute a violating facility from weeks to hours.

Here is the story of how the system behaves, step by step.

---

## Phase 1: The Citizen Intake (Reporting the Incident)

The journey begins with a citizen in the community. Let's say a resident spots thick black smoke billowing from an industrial smokestack. 

**The Portal Experience:**
The citizen navigates to the public-facing **EcoSentinel Citizen Portal** (or uses the Citizen PWA installed on their phone). Because friction discourages reporting, they do not need to create an account or log in. 

They open the **Report Incident Record Producer** and provide:
1. The **Incident Category** (Air Pollution).
2. Their **Location** (captured automatically via HTML5 Geolocation into `incident_lat` and `incident_lng`).
3. An **Incident Photo** of the smoke (attached to the form).
4. A brief description of what they see.
5. *(Optional)* Their email address, so they can receive updates.

**Submission and Confirmation:**
Upon submitting the form, a new record is created in the `x_eco_complaint` table. The citizen is immediately shown a confirmation page with a unique tracking number (e.g., `ES-20260731-0042`). 

Simultaneously, a Flow Designer flow (`FL-01`) sends a **"Complaint Received" email** to the citizen. If the citizen wants to check the status later, they can return to the portal and use the **Virtual Agent** (or the Status Tracker widget), entering their tracking number and email to receive a plain-English, citizen-safe status update like *"Our system has validated the report details."*

---

## Phase 2: AI Triage & Severity Fusion (The Brains)

As soon as the `x_eco_complaint` record is created, the system must decide how urgent this incident is. Normally, a human dispatcher would read the report. In EcoSentinel, this is handled by the **Severity Fusion Agent**.

**The Webhook Dispatch:**
Flow `FL-01` triggers an asynchronous REST webhook to our external **FastAPI Orchestration Backend**. This webhook payload includes the complaint details, GPS coordinates, and a secure download link for the citizen's photo.

**The Multi-Agent Assessment:**
Outside of ServiceNow, the FastAPI backend orchestrates several steps:
1. It downloads the photo and sends it to the **OpenAI Vision model** to analyze the image (e.g., confirming the presence of heavy black smoke).
2. It calls external weather and Air Quality Index (AQI) APIs using the GPS coordinates to get real-time environmental context.
3. The **Severity Fusion Agent** takes the citizen's text, the Vision model's image caption, and the live weather/AQI data, and synthesizes a final decision: Is this a `Low`, `Medium`, or `High` severity incident?

**Writing Back to ServiceNow:**
Within seconds, the FastAPI backend sends a `PATCH` request back to ServiceNow using the `x_eco.integration_user` account. It updates the complaint with the **AI Severity**, a confidence score, and a human-readable **AI Rationale**.

To ensure total auditability, the backend also `POST`s:
* An **Environmental Snapshot** (`x_eco_env_snapshot`) freezing the exact AQI and weather data used at that moment.
* An **Agent Decision Log** (`x_eco_agent_log`) recording exactly what the AI was fed and what it concluded.

**The Fallback Safety Net:**
What if the FastAPI server is down? A scheduled Flow (`FL-02`) checks every hour for complaints stuck in the "Received" state. If the AI hasn't responded, it applies a default "Medium" severity and assigns a human officer to manually triage it, ensuring no community report is ever lost to a technical glitch.

---

## Phase 3: Back-Office Triage & Risk Assessment

Now the complaint is enriched with AI intelligence and moves to the **Compliance Officers**.

**Officer Review:**
An officer logs into the **EcoSentinel Officer Workspace** (Desktop UI). They see the new complaint flagged as "High" severity. They read the AI Rationale and look at the attached photo. If the AI made a mistake, the officer can use the **Override Severity** field, which requires them to enter a justification. (This override is gated by strict ACLs so only officers can do it).

**Facility Matching & Risk Calculation:**
The officer (or the Triage Agent) maps the GPS coordinates to a known regulated factory in the `x_eco_facility` table. Once linked, the facility's **Compliance Risk Score** dynamically recalculates (`SF-02` / `BR-F02`). If this new complaint pushes the facility's risk score over 80, the facility is flagged as a "Critical Risk," and an email alert is blasted to the compliance team.

**SLA Initiation:**
Because this is a High Severity issue, the SLA engine immediately starts a **24-hour response countdown**. If an inspector doesn't resolve this within 24 hours, the SLA breaches, and an escalation flow (`FL-04`) notifies management.

---

## Phase 4: Field Inspection (Now Mobile)

The complaint is verified. It's time to send someone into the field.

**Automated Dispatch:**
Based on the facility's geographic zone (e.g., "North"), Flow Designer (`FL-03`) automatically creates an **Inspection record** (`x_eco_inspection`) and assigns it to the `EcoSentinel — North Zone Inspectors` group. 

**The Inspector's Experience:**
An inspector on the North team receives a push notification on their phone. They open the **Now Mobile App**. The app shows them the inspection details, the citizen's original photo, and the AI's rationale.

1. They tap **"En Route"**, which updates the status (and automatically emails the citizen that an inspector is on the way via `FL-09`).
2. Upon arrival, they tap **"Arrived."** A Client Script forces the Now Mobile app to capture their current GPS coordinates (`inspector_lat`/`lng`), proving they are actually at the facility.
3. While walking the site, they use the app to create **Inspection Findings** (`x_eco_finding`). They snap photos of the smokestack and type rough, shorthand notes (e.g., "Burner valve broken. Heavy SO2 smell. Filter bypassed.").

**AI Inspection Report Generation:**
When the inspector finishes, they don't have to spend hours typing a formal report. When they mark the inspection as "Completed", the **Inspection Report Agent** (using native Now Assist) reads their shorthand notes and findings, and instantly generates a structured, professional **AI Generated Report** summarizing the regulatory violations.

---

## Phase 5: Legal Enforcement (Closing the Loop)

The inspector confirmed a violation. The system must now penalize the facility.

**Creating the Legal Case:**
Because the inspection was closed with `violation_confirmed = true`, Flow Designer (`FL-05`) automatically generates a **Legal Case** (`x_eco_legal_case`), assigning it to the `EcoSentinel — Legal Prosecution Team`.

**AI Legal Narrative:**
Before the legal handler even opens the case, the **Legal Case Summary Agent** (`FL-07`) has already gone to work. It reads the original citizen complaint, the AI severity rationale, the inspector's findings, and the facility's historical risk profile. It drafts a comprehensive **Case Narrative** — a legally sound brief summarizing the entire chain of evidence.

**Prosecution & Resolution:**
The legal handler reviews the AI-generated narrative, determines the appropriate penalty (e.g., a $50,000 fine), and issues a formal notice to the facility. 

Once the legal case is marked as "Resolved," Flow `FL-11` (Legal Case Resolution Sync) automatically updates the original citizen's `x_eco_complaint` to "Closed" and sends the citizen a **Final Resolution Notice** email, thanking them for keeping their community safe.

---

## Phase 6: Platform Governance & Insights

While all this operational work is happening, EcoSentinel provides high-level oversight for administrators and executives.

**The AI Control Tower (For Admins):**
How do we trust the AI? Administrators have access to the AI Control Tower dashboard, which is built on top of the immutable `x_eco_agent_log` table. Every single time an AI agent makes a decision—whether it's the external FastAPI Severity Fusion or the native Now Assist Report generator—a permanent record is logged here. Admins can audit confidence scores, execution times, and exact prompt inputs/outputs.

**Leadership Insights (For Executives):**
Agency directors don't want to look at individual tables. They look at the **Performance Analytics Dashboard**, tracking average SLA resolution times, total fines assessed, and a heat map of high-risk facilities.

Furthermore, every Monday morning at 8:00 AM, the **Leadership Insights Agent** (`FL-10`) scans the week's data and drafts a plain-English executive summary email (e.g., *"This week, we saw a 15% spike in air quality complaints in the North Zone, largely driven by Greenfield Chemical Works..."*), sending it directly to the Executive Leadership group.

---

## Summary: The Data & Security Backbone

Throughout this journey, strict data security and role-based access control (RBAC) ensure the integrity of the system:
* **Citizens** (No Role) can only submit data and check their specific tracking number.
* **Inspectors** (`x_eco.inspector`) can only see inspections assigned to them via the Now Mobile app. They cannot alter the AI's severity or view legal proceedings.
* **Compliance Officers** (`x_eco.officer`) triage the complaints and manage facility risk.
* **Legal Handlers** (`x_eco.legal_handler`) exclusively manage the penalties and prosecutions.
* **Integration Users** (`x_eco.integration_user`) are restricted to API-only access to securely handle the FastAPI webhook payloads.

By linking **Complaints $\rightarrow$ Facilities $\rightarrow$ Inspections $\rightarrow$ Legal Cases**, EcoSentinel AI maintains a continuous, unbreakable chain of custody from a citizen's smartphone photo to a court-ready environmental prosecution.
