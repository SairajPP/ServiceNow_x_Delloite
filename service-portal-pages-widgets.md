# EcoSentinel AI — Service Portal Pages & Widgets Spec

This document details the Service Portal layer of the EcoSentinel application. This portal is the primary public-facing interface where citizens report environmental incidents and track their resolutions without requiring an account.

---

## Section 1: Portal & Page Structure

The Service Portal (`eco_portal`) is designed with a mobile-first, high-contrast theme, given that citizens will primarily access it from their phones while in the field observing pollution. All pages below are flagged as **Public** (unauthenticated access).

### 1. Home / Landing Page
- **Page Name/URL Suffix**: `eco_home`
- **Purpose**: Welcomes the citizen, explains the app, and provides clear paths to report or track.
- **Access Level**: Public
- **Widgets Placed**: Navigation/Header, Hero Intro Widget, Virtual Agent Embed.
- **Page Layout**: Single column on mobile, 2-column on desktop (Left: Report CTA, Right: Track CTA). Fixed header.

### 2. Report Incident Page
- **Page Name/URL Suffix**: `eco_report`
- **Purpose**: The complaint submission form for reporting a new incident.
- **Access Level**: Public
- **Widgets Placed**: Navigation/Header, Complaint Submission Form widget.
- **Page Layout**: Single column, centered, max-width container for readable forms on desktop; full width on mobile.

### 3. Track Status Page
- **Page Name/URL Suffix**: `eco_track`
- **Purpose**: Allows citizens to look up their complaint using their tracking number and email, viewing a live status timeline.
- **Access Level**: Public
- **Widgets Placed**: Navigation/Header, Complaint Tracker widget.
- **Page Layout**: Single column, centered form. Once loaded, expands into a vertical timeline (mobile) or horizontal stepper (desktop).

### 4. Confirmation Page
- **Page Name/URL Suffix**: `eco_success`
- **Purpose**: Shown immediately post-submission to display the tracking number.
- **Access Level**: Public
- **Widgets Placed**: Navigation/Header, Confirmation Display widget.
- **Page Layout**: Single column, centered success banner.

---

## Section 2: Widget-by-Widget Spec

### 2.1 Complaint Submission Form Widget
- **Purpose**: Captures the incident details, photo, and location, creating the Complaint record.
- **HTML Structure**: 
  - Location input group (Read-only text field + "Use My Location" button + manual override toggle).
  - Multi-line text area for description.
  - File input for photo upload.
  - Contact info section (Email, Phone - optional unless they want updates).
  - Submit button.
- **Client Controller**:
  - **On Load**: Prompts for browser geolocation.
  - **On Submit**: Validates mandatory fields (Description, Location). Validates that a photo is attached (required for AI). Disables submit button and shows loading spinner.
  - **On Success**: Redirects to `eco_success` page with the new `sys_id` in the URL parameters.
- **Server Script**: 
  - Inserts a new record into `x_eco_complaint`. Returns the `sys_id` and `number` to the client.
- **Dependencies**: Relies on Attachment API for the photo.
- **Error States**: spUtil error messages shown for missing mandatory fields or denied GPS permissions.

### 2.2 Complaint Tracker Widget
- **Purpose**: Securely looks up a complaint and displays its live status and AI severity.
- **HTML Structure**:
  - **State 1 (Search)**: Inputs for Tracking Number and Email. "Track" button.
  - **State 2 (Timeline)**: A visual stepper indicator (Received → AI Verified → Inspector Assigned → Inspection Completed → Action Taken). Text displaying AI Severity (e.g., "High Severity") and Estimated Response Time (from `sla-definitions.md`).
- **Client Controller**:
  - Calls server with number + email. Toggles from State 1 to State 2 on success.
- **Server Script**:
  - Calls `x_eco.EcoComplaintUtils().lookupComplaint(number, email)` (SI-02). Does **not** perform raw GlideRecord queries in the widget to prevent data leakage. Returns state, severity, and SLA details.
- **Dependencies**: `EcoComplaintUtils` (SI-02).
- **Error States**: "No matching complaint found" if the number/email pair is incorrect.

### 2.3 Confirmation / Tracking Number Display Widget
- **Purpose**: Prominently displays the generated tracking number post-submission.
- **HTML Structure**: Large bold text for the Tracking Number. A "Copy to Clipboard" button. A link to the Tracker page.
- **Client Controller**: Reads `sys_id` from the URL, calls server to fetch the `number`. Implements clipboard copy.
- **Server Script**: Simple GlideRecord get on `x_eco_complaint` to return the `number`.
- **Error States**: "Invalid Request" if URL is malformed.

### 2.4 Virtual Agent Embed Widget
- **Purpose**: Provides conversational status checks natively on the portal.
- **HTML Structure**: Floating chat icon in the bottom right corner (ServiceNow standard VA client).
- **Client Controller**: Initializes the VA client with the specific `EcoSentinel Citizen Status Topic` (documented in `virtual-agent-status-topic.md`).
- **Trigger**: Independent of the manual tracker form; citizens can choose either UX path.

### 2.5 Navigation / Header Widget
- **Purpose**: Consistent branding and routing.
- **HTML Structure**: Logo left, responsive hamburger menu right (Report, Track, Home).
- **Client Controller**: Standard portal routing `$location.search(id=...)`.

---

## Section 3: Photo & GPS Capture Handling

Because the AI Severity Fusion Agent (Hugging Face / OpenAI Vision) strictly requires visual context, photo handling is critical.

### GPS Capture
- **Client-Side**: The widget uses the HTML5 `navigator.geolocation.getCurrentPosition()` API.
- **Fallback**: If the user denies permission or it fails (timeout), the UI reveals a manual text input field for the citizen to type the nearest cross-street or landmark.

### Photo Capture
- **Client-Side**: The `<input type="file" accept="image/*" capture="environment">` tag forces mobile devices to open the rear-facing camera directly, minimizing friction.
- **Attachment Sequence**: 
  1. The widget creates the `x_eco_complaint` record via the widget's server script first to generate the `sys_id`.
  2. The widget immediately uploads the photo to the new `sys_id` using the ServiceNow Attachment API.
  3. The `FL-01` webhook trigger fires on complaint insert, but includes a mandatory 5-second wait step to allow the attachment upload to complete before dispatching the payload to FastAPI.
  4. This guarantees the photo is available in ServiceNow when the FastAPI backend queries for it.

---

## Section 4: Field Mapping Table

| Portal Form Field | Mapped Table | Internal Field Name | Type | Notes |
|---|---|---|---|---|
| Incident Location | `x_eco_complaint` | `incident_address` | String | Reverse-geocoded address or manually entered location description. Also captured: `incident_lat` and `incident_lng` for GPS coordinates via HTML5 Geolocation. |
| Description | `x_eco_complaint` | `description` | Multi-line text | Full citizen narrative of the environmental incident. The `short_description` field is auto-derived by BR-C01 from category + location for list view display. |
| Photo | `sys_attachment` | N/A | File | Attached to the complaint `sys_id`. Portal must upload photo first, then create/update complaint record only after attachment success to avoid race condition with FL-01 webhook. |
| Email Address | `x_eco_complaint` | `citizen_email` | String | Used for tracker authentication. **Requires strict Regex validation** client-side (AngularJS) and server-side to block malicious payloads. |
| Phone Number | `x_eco_complaint` | `citizen_phone` | String | Optional |

---

## Section 5: Anonymous Access & Security Notes

Opening a public-facing portal requires strict data security to protect PII and prevent API exhaustion.

1. **Write-Only ACLs**: Unauthenticated users (the `public` role) are granted Create access to `x_eco_complaint` and `sys_attachment`, but **no Read access** globally. This means a citizen cannot query the table via REST or list views to see other complaints.
2. **Secure Lookup**: The Tracker Widget requires a composite key (`number` + `citizen_email`). The server script delegates this to a secure Script Include (`SI-02`) running with system privileges to fetch only the requested status string, exposing absolutely no internal data.
3. **Abuse Prevention**: 
   - **CAPTCHA**: Planned for production. For the hackathon build, CAPTCHA is noted as a stated roadmap item. Add one-line note: "Intended approach: Google reCAPTCHA v3 for invisible bot detection, configurable threshold."
   - **Rate Limiting**: An IP-based rate limiter (Before-Insert Business Rule) caps submissions to 5 per hour per IP to protect the external FastAPI/AI budgets.
4. **Input Validation (SEC-08)**: The `citizen_email` field must undergo strict regex format validation (`^[^\s@]+@[^\s@]+\.[^\s@]+$`) on both the client (AngularJS `$parsers`) and server (`EcoComplaintUtils` lookup step) to prevent injection of malicious payloads into the system.

---

## Section 6: Now Mobile Cross-Reference Note

**Important Boundary:** This Service Portal design is strictly for **Citizen (Public)** interactions. 

The Field Inspector experience (dispatch, mapping, closing out inspections, and logging findings) is handled entirely on the **Now Mobile** app. Compliance Officers and Admins use the native ServiceNow backend UI (`officer-admin-experience.md`). Do not combine these personas into the Service Portal; keeping them separate preserves the security model and takes advantage of native offline capabilities for inspectors.
