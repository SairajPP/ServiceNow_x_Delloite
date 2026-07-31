# EcoSentinel AI — Citizen PWA & Inspector Dashboard

This document extends the Service Portal specifications (`service-portal-pages-widgets.md`) to define the Progressive Web App (PWA) configuration for citizens, and introduces the Performance Analytics dashboard used by inspectors for triage and prioritization.

---

## Section 1: Citizen Service Portal as a PWA (Progressive Web App)

To deliver a native app-like experience without the overhead of app store submissions or a separate React Native/Swift codebase, the existing Citizen Service Portal is configured as a Progressive Web App (PWA) using standard web capabilities natively supported in ServiceNow.

### PWA Manifest Config
The Service Portal is configured with a Web App Manifest (`manifest.json`) injected via the portal theme header:
- **App Name**: EcoSentinel Report
- **Short Name**: EcoSentinel
- **Icons**: 192x192 and 512x512 maskable PNGs.
- **Theme Color**: #0056b3 (EcoSentinel Primary Blue)
- **Display**: `standalone` — This ensures the portal opens full-screen without the Safari/Chrome browser URL bar or navigation chrome once added to the home screen.

### "Add to Home Screen" Prompt
The standard browser installation prompt (A2HS) is triggered proactively:
- **Trigger Point**: Shown as a sticky banner on the `eco_home` landing page, and prominently displayed on the `eco_success` confirmation page after a user successfully submits their first complaint.

### Mobile-First Layout Adjustments
- **Viewport**: `<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">` applied to prevent awkward zooming.
- **Navigation**: Instead of a traditional top header, the PWA utilizes a **Bottom Navigation Bar** (Report | Track | Home) fixed to the bottom of the screen, mimicking native iOS/Android tabs. Touch targets are scaled to a minimum of 44x44px.
- **Camera-First UI**: On the `eco_report` page, the attachment widget is styled as a massive "Take Photo" button using `<input type="file" accept="image/*" capture="environment">` so it skips the generic file picker and immediately opens the device's rear camera.

### AI Analysis Result Screen
Instead of just a generic "Thank You", the post-submit confirmation screen (`eco_success`) features an app-like feedback loop:
- **Display**: Shows the AI's severity classification and confidence score dynamically (polled via GlideAjax until `ai_processing_status` completes).
- **Citizen-Safe Language**: The raw `ai_rationale` (which may contain internal technical or legal jargon) is filtered. The screen shows a simplified mapping (e.g., *Analysis Complete / Severity Level: High / Confidence Score: 92% / "Thank you. Our AI indicates this is a severe spill requiring immediate dispatch."*).

### Offline & Slow-Connection Handling
- **Service Worker**: A simple service worker caches the App Shell (HTML, CSS, Logos). If a user opens the PWA with no cellular service, the UI loads instantly rather than showing a browser dinosaur. 
- **Graceful Degradation**: While the actual submission POST requires connectivity, the user can fill out the form offline and hit submit when they regain signal.

### Performance Notes
- **Image Compression**: Client-side canvas compression reduces 5MB raw camera photos to <1MB JPEGs *before* uploading to ServiceNow. This saves mobile data limits and drastically speeds up the Hugging Face/OpenAI Vision pipeline inference time.
- **Loading States**: Shimmer skeleton loaders are used during the AI analysis wait time to keep the citizen engaged.

---

## Section 2: Inspector Ranked Dashboard (Performance Analytics)

While Now Mobile is used for *capturing data on-site*, inspectors need a way to know *which site to go to first*. This is handled by a Performance Analytics (PA) dashboard.

- **Dashboard Name**: Inspector Triage & Dispatch
- **Access**: Scoped strictly to the `x_eco.inspector` role (per `roles-groups-users.md`). Dynamic filtering ensures each inspector sees only their own assigned queue, not a global view.
- **Data Source**: A database view joining `x_eco_complaint` and `x_eco_inspection`, leveraging the `EcoUrgencyScoreCalculator` (SI-07).

### Widgets on the Dashboard
1. **Ranked Issue List**: A list widget sorted strictly by the **Composite Urgency Score** (descending). It answers "how deep is the issue" by surfacing High Severity pollution that occurs at High Risk facilities.
2. **SLA Countdown**: A visual indicator column in the list view (Red/Amber/Green) showing time remaining based on the SLA definitions mapped in `sla-definitions.md` (e.g., 24h for High Severity).
3. **Zone / Heat Summary**: A bar chart or pie chart showing the count of open assigned issues by geographic zone (e.g., North District vs South District) to help the inspector optimize driving routes.
4. **Quick-Open Action**: Clicking a row on the desktop/portal dashboard provides a deep-link URI (e.g., `snapp://nowmobile/instance/nav/view...`) that pushes the record directly to their Now Mobile app to begin the on-site workflow.

### Composite Urgency Score Definition
Rather than relying purely on severity, the triage queue is ranked by a calculated 0–100 score. 
- **Formula**: `(AI Severity Numeric Weight * 0.6) + (Facility Risk Score * 0.4)`
- **Execution**: This is executed via the **`EcoUrgencyScoreCalculator` (SI-07)** Script Include.
- **Refresh Frequency**: Because facility risk changes infrequently and AI severity is set once on insert, the Urgency Score is written to a physical integer field (`urgency_score`) on the `x_eco_inspection` table upon creation, allowing the dashboard to query it in **real-time** without heavy on-the-fly math.

---

## Section 3: Cross-Reference Note

**The Inspector UI Split:**
To prevent duplicate build effort during the hackathon, the inspector experience is explicitly split by phase:
1. **Triage Phase (Desktop/Portal)**: The **Inspector Ranked Dashboard** (defined above) is where the inspector starts their shift. They use it to visualize their workload, see SLAs, and decide *which* location to drive to first based on the Composite Urgency Score.
2. **Execution Phase (Now Mobile)**: Once the inspector arrives on-site, they open the **Now Mobile App** (`now-mobile-inspector-experience.md`) to actually capture the evidence photo, GPS, and confirm the violation. 

Do not attempt to build data-entry forms into the PA dashboard, and do not attempt to build complex PA charts into the Now Mobile app.
