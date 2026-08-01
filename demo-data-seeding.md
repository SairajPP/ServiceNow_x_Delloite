# EcoSentinel AI — Demo Data Seeding Plan

> **Scoped Application**: EcoSentinel AI  
> **Scope Prefix**: `x_eco_`  
> **Purpose**: Provides a realistic, believable dataset spanning the full severity spectrum for hackathon demonstration and judge evaluation  
> **Hackathon**: ServiceNow × Deloitte 2026 — Team VertexNow

---

## Section 1: Demo User Accounts

### 1.1 Team Members (Real Accounts)

| Name | Username | Email | Groups | Roles | Purpose |
|---|---|---|---|---|---|
| Kuchipudi Lakshmi Venkatesh | `venkatesh.k` | `venkatesh.k@vertexnow.com` | EcoSentinel — System Administrators | `x_eco.admin`, `admin` | System admin demo persona |
| Kasireddy Lokesh Reddy | `lokesh.k` | `lokesh.k@vertexnow.com` | EcoSentinel — Compliance Officers | `x_eco.officer` | Compliance officer demo persona |
| Kopparapu Nikhil Lokesh | `nikhil.k` | `nikhil.k@vertexnow.com` | EcoSentinel — North Zone Inspectors | `x_eco.inspector` | North zone inspector demo persona |
| Sairaj Pawar | `sairaj.p` | `sairaj.p@vertexnow.com` | EcoSentinel — South Zone Inspectors | `x_eco.inspector` | South zone inspector demo persona |
| Yuvra Zende | `yuvra.z` | `yuvra.z@vertexnow.com` | EcoSentinel — Legal Prosecution Team | `x_eco.legal_handler` | Legal handler demo persona |

### 1.2 Fictional Personas

| Name | Username | Email | Groups | Roles | Purpose |
|---|---|---|---|---|---|
| Sarah Jenkins | `sjenkins.director` | `sjenkins@agency.gov` | EcoSentinel — Executive Leadership | `x_eco.executive` | Executive leadership dashboard viewer |
| Mike Rodriguez | `mrodriguez.inspector` | `mrodriguez@agency.gov` | EcoSentinel — Central Zone Inspectors | `x_eco.inspector` | Central zone inspector |
| Priya Sharma | `psharma.officer` | `psharma@agency.gov` | EcoSentinel — Compliance Officers | `x_eco.officer` | Additional compliance officer |
| John Lee | `jlee.legal` | `jlee@agency.gov` | EcoSentinel — Legal Prosecution Team | `x_eco.legal_handler` | Additional legal handler |
| FastAPI Service Account | `ecosentinel.api` | `api@ecosentinel.system` | None | `x_eco.integration_user` | Non-interactive API account |

---

## Section 2: Demo Facilities

### 2.1 High-Risk Facilities (Risk Score 80+)

| Facility Name | Facility ID | Sector | Zone | Address | Lat | Lng | Risk Score | Risk Tier | Violations (12mo) | Complaints (90d) | Report Overdue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Greenfield Chemical Works | FC-2021-0042 | chemical | north | 123 Industrial Parkway, North District | 18.9750 | 72.8258 | 95 | critical | 3 | 8 | true |
| Doshi Mining Corp | FM-2019-0156 | mining | east | 789 Quarry Road, East District | 19.0176 | 72.8561 | 85 | critical | 2 | 5 | false |

### 2.2 Elevated-Risk Facilities (Risk Score 65-79)

| Facility Name | Facility ID | Sector | Zone | Address | Lat | Lng | Risk Score | Risk Tier | Violations (12mo) | Complaints (90d) | Report Overdue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Apex Manufacturing Ltd | FF-2020-0089 | manufacturing | south | 456 Factory Lane, South District | 18.9220 | 72.8347 | 70 | elevated | 1 | 4 | false |
| Central Power Plant | FE-2018-0234 | energy | central | 321 Power Station Rd, Central District | 18.9647 | 72.8194 | 68 | elevated | 1 | 3 | true |

### 2.3 Standard-Risk Facilities (Risk Score 40-64)

| Facility Name | Facility ID | Sector | Zone | Address | Lat | Lng | Risk Score | Risk Tier | Violations (12mo) | Complaints (90d) | Report Overdue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Metro Construction Co | FC-2022-0371 | construction | west | 555 Builder Ave, West District | 18.9389 | 72.8353 | 55 | standard | 0 | 2 | false |
| Riverside Waste Management | FW-2021-0199 | waste_management | north | 777 Disposal Drive, North District | 19.0015 | 72.8450 | 50 | standard | 0 | 1 | false |

### 2.4 Low-Risk Facilities (Risk Score 0-39)

| Facility Name | Facility ID | Sector | Zone | Address | Lat | Lng | Risk Score | Risk Tier | Violations (12mo) | Complaints (90d) | Report Overdue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GreenTech Solar Farm | FE-2023-0512 | energy | south | 999 Solar Park Rd, South District | 18.9103 | 72.8217 | 30 | low | 0 | 0 | false |

---

## Section 3: Demo Complaints

### 3.1 High-Severity Complaints (Demonstrating Critical Path)

| Number | Category | Citizen Name | Citizen Email | Description | Address | Lat | Lng | Linked Facility | AI Severity | AI Confidence | State | Violation Confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ES-20260725-0001 | air_pollution | Anonymous Citizen | citizen1@email.com | "Thick black smoke from factory chimney, chemical smell, children's playground nearby" | 123 Industrial Parkway, North District | 18.9750 | 72.8258 | Greenfield Chemical Works | high | 92 | Inspection Completed | true |
| ES-20260728-0002 | illegal_dumping | Maria Garcia | maria.g@email.com | "Large drums leaking chemical liquid into creek behind facility" | 789 Quarry Road, East District | 19.0176 | 72.8561 | Doshi Mining Corp | high | 88 | Legal Case Opened | true |
| ES-20260730-0003 | water_pollution | Anonymous Citizen | citizen3@email.com | "Factory discharge pipe releasing brown wastewater directly into river" | 456 Factory Lane, South District | 18.9220 | 72.8347 | Apex Manufacturing Ltd | high | 85 | Inspector Assigned | null |

### 3.2 Medium-Severity Complaints

| Number | Category | Citizen Name | Citizen Email | Description | Address | Lat | Lng | Linked Facility | AI Severity | AI Confidence | State | Violation Confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ES-20260726-0004 | noise_pollution | Rajesh Kumar | rajesh.k@email.com | "Construction site running heavy machinery at night, exceeds permitted hours" | 555 Builder Ave, West District | 18.9389 | 72.8353 | Metro Construction Co | medium | 75 | Inspection In Progress | null |
| ES-20260729-0005 | air_pollution | Anonymous Citizen | citizen5@email.com | "Dust clouds from power plant coal storage, visible from residential area" | 321 Power Station Rd, Central District | 18.9647 | 72.8194 | Central Power Plant | medium | 72 | AI Verified | null |

### 3.3 Low-Severity Complaints

| Number | Category | Citizen Name | Citizen Email | Description | Address | Lat | Lng | Linked Facility | AI Severity | AI Confidence | State | Violation Confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ES-20260727-0006 | other | Priya Mehta | priya.m@email.com | "Occasional odor from waste facility on windy days, not constant" | 777 Disposal Drive, North District | 19.0015 | 72.8450 | Riverside Waste Management | low | 68 | Received | null |
| ES-20260731-0007 | noise_pollution | John Doe | john.d@email.com | "Minor noise from solar panel cleaning equipment, one-time event" | 999 Solar Park Rd, South District | 18.9103 | 72.8217 | GreenTech Solar Farm | low | 60 | Dismissed | false |

---

## Section 4: Demo Inspections

### 4.1 Completed Inspections (Violation Confirmed)

| Number | Parent Complaint | Inspected Facility | Assigned Inspector | State | Violation Confirmed | Violation Type | Raw Notes | Arrival Time | Departure Time |
|---|---|---|---|---|---|---|---|---|---|
| INS0001001 | ES-20260725-0001 | Greenfield Chemical Works | Kopparapu Nikhil Lokesh | Completed — Violation Confirmed | true | emission_breach | "Boiler exhaust filter bypassed. Stack emissions visible dark smoke. SO2 smell confirmed. No active scrubber. Facility manager admitted filter 'temporarily removed for maintenance' 3 weeks ago. Non-compliant with permit." | 2026-07-26 09:15 | 2026-07-26 11:30 |
| INS0001002 | ES-20260728-0002 | Doshi Mining Corp | Mike Rodriguez | Completed — Violation Confirmed | true | illegal_dumping | "Found 12 drums labeled 'hazardous waste' behind eastern fence line. 3 drums actively leaking into tributary creek. Photos captured. Water sample collected. Facility has no waste disposal permit on file. Clear violation." | 2026-07-29 10:00 | 2026-07-29 12:45 |

### 4.2 Completed Inspections (Dismissed)

| Number | Parent Complaint | Inspected Facility | Assigned Inspector | State | Violation Confirmed | Violation Type | Raw Notes | Arrival Time | Departure Time |
|---|---|---|---|---|---|---|---|---|---|
| INS0001003 | ES-20260731-0007 | GreenTech Solar Farm | Sairaj Pawar | Completed — Dismissed | false | null | "Inspected solar panel cleaning equipment. One-time maintenance event. Noise levels within permitted daytime limits. No ongoing violation. Facility provided noise assessment report from certified consultant dated 2026-07-25. Dismissed." | 2026-08-01 08:00 | 2026-08-01 09:15 |

### 4.3 In-Progress Inspections

| Number | Parent Complaint | Inspected Facility | Assigned Inspector | State | Violation Confirmed | Violation Type | Raw Notes | Scheduled Date |
|---|---|---|---|---|---|---|---|---|
| INS0001004 | ES-20260730-0003 | Apex Manufacturing Ltd | Kopparapu Nikhil Lokesh | Scheduled | null | null | null | 2026-08-02 10:00 |
| INS0001005 | ES-20260729-0005 | Central Power Plant | Mike Rodriguez | En Route | null | null | null | 2026-08-01 14:00 |

---

## Section 5: Demo Inspection Findings

### 5.1 Findings for INS0001001 (Greenfield Chemical Works)

| Finding Number | Finding Type | Description | Photo | Measurement Value | Finding Severity | Captured At |
|---|---|---|---|---|---|---|
| 1 | photo_evidence | "Boiler stack emitting dense black smoke" | Yes (attachment) | null | critical | 2026-07-26 09:30 |
| 2 | observation | "Exhaust filter housing open, filter element removed" | Yes (attachment) | null | critical | 2026-07-26 09:45 |
| 3 | measurement | "SO2 concentration reading at fence line" | No | "450 ppm (permit limit: 150 ppm)" | critical | 2026-07-26 10:15 |
| 4 | document | "Permit on file - last scrubber inspection required 2026-06-01, not performed" | Yes (scan) | null | moderate | 2026-07-26 11:00 |

### 5.2 Findings for INS0001002 (Doshi Mining Corp)

| Finding Number | Finding Type | Description | Photo | Measurement Value | Finding Severity | Captured At |
|---|---|---|---|---|---|---|
| 1 | photo_evidence | "Hazardous waste drums with visible corrosion and leakage" | Yes (attachment) | null | critical | 2026-07-29 10:30 |
| 2 | photo_evidence | "Chemical discharge entering creek water" | Yes (attachment) | null | critical | 2026-07-29 10:45 |
| 3 | sample_collected | "Water sample collected 50m downstream of discharge point" | No | "pH 3.2 (highly acidic)" | critical | 2026-07-29 11:15 |

---

## Section 6: Demo Legal Cases

### 6.1 Active Legal Cases

| Number | Source Complaint | Source Inspection | Violating Facility | Violation Type | State | Penalty Type | Penalty Amount | Case Narrative (AI-generated excerpt) |
|---|---|---|---|---|---|---|---|---|
| LGL0001001 | ES-20260725-0001 | INS0001001 | Greenfield Chemical Works | emission_breach | Evidence Compiled | fine | $75,000 | "On July 26, 2026, Field Inspector Kopparapu Nikhil Lokesh conducted a physical inspection of Greenfield Chemical Works in response to citizen complaint ES-20260725-0001. The AI Severity Fusion Agent classified this complaint as HIGH severity (92% confidence) based on dense smoke visible in citizen photo, AQI reading of 210 (Very Unhealthy), and low wind speed (2 km/h) indicating pollutant accumulation. Inspector findings confirmed: (1) Boiler exhaust filter bypass, (2) SO2 emissions 3x permit limit, (3) Failure to perform required scrubber maintenance. Facility has 2 prior violations in last 12 months and current risk score of 95/100 (Critical). Recommend monetary fine and mandatory corrective action plan within 30 days." |
| LGL0001002 | ES-20260728-0002 | INS0001002 | Doshi Mining Corp | illegal_dumping | Case Opened | suspension | null | "On July 29, 2026, Field Inspector Mike Rodriguez discovered 12 drums of hazardous waste illegally stored and leaking into a tributary creek at Doshi Mining Corp. AI classified the initial complaint as HIGH severity (88% confidence). Water sample analysis revealed pH 3.2, indicating severe environmental contamination. Facility lacks required waste disposal permit. This is the 2nd confirmed violation in 12 months. Given the severity and repeat nature, recommend temporary operations suspension pending environmental remediation and permit compliance." |

---

## Section 7: Demo Environmental Snapshots

| Parent Complaint | Snapshot Timestamp | AQI Value | AQI Category | Primary Pollutant | Wind Speed (km/h) | Wind Direction | Temperature (C) | Weather Condition | Humidity (%) | Data Source |
|---|---|---|---|---|---|---|---|---|---|---|
| ES-20260725-0001 | 2026-07-25 14:23 | 210 | very_unhealthy | PM2.5 | 2.0 | WSW | 32 | scattered clouds | 75 | success |
| ES-20260728-0002 | 2026-07-28 11:15 | 165 | unhealthy | PM10 | 8.5 | NE | 29 | clear sky | 68 | success |
| ES-20260730-0003 | 2026-07-30 16:42 | 185 | unhealthy | PM2.5 | 3.2 | SW | 31 | partly cloudy | 72 | success |
| ES-20260729-0005 | 2026-07-29 09:30 | 95 | moderate | PM2.5 | 12.0 | NW | 28 | light rain | 82 | success |
| ES-20260731-0007 | 2026-07-31 10:05 | 45 | good | O3 | 15.5 | N | 26 | clear sky | 60 | success |

---

## Section 8: Demo Agent Decision Logs

| Log ID | Agent Name | Agent Type | Linked Table | Linked Record Number | Input Summary | Output Summary | Confidence | Status | Decision Timestamp |
|---|---|---|---|---|---|---|---|---|---|
| ADL0001001 | severity_fusion | external | x_eco_complaint | ES-20260725-0001 | "Image: 'dense black smoke from chimney'. Citizen: 'chemical smell, children nearby'. AQI: 210. Wind: 2 km/h." | "Severity: HIGH. Confidence: 92%. Rationale: Dense smoke + Very Unhealthy AQI + low wind = pollutant accumulation near residential." | 92 | success | 2026-07-25 14:25 |
| ADL0001002 | severity_fusion | external | x_eco_complaint | ES-20260728-0002 | "Image: 'leaking drums near creek'. Citizen: 'chemical liquid'. AQI: 165. Wind: 8.5 km/h." | "Severity: HIGH. Confidence: 88%. Rationale: Visual confirmation of hazmat + water contamination risk + unhealthy AQI." | 88 | success | 2026-07-28 11:17 |
| ADL0001003 | inspection_report | native | x_eco_inspection | INS0001001 | "Raw notes: 'Boiler exhaust filter bypassed…' Findings: 4 items (2 photos, 1 measurement, 1 document)." | "Structured report generated with Executive Summary, Site Description, Findings list, Evidence Summary, Conclusion, Recommendations." | 85 | success | 2026-07-26 12:00 |
| ADL0001004 | legal_case_summary | native | x_eco_legal_case | LGL0001001 | "Complaint ES-20260725-0001, Inspection INS0001001, Facility risk: 95/100, 2 prior violations." | "Legal narrative compiled: Case Overview, AI Classification, Environmental Conditions, Inspection Findings, Compliance History, Violation Determination, Recommended Action." | 90 | success | 2026-07-27 09:00 |

---

## Section 9: Seeding Instructions

### 9.1 Manual Seeding (via ServiceNow UI)
1. Log in as admin user
2. Navigate to each table (Facilities, Complaints, Inspections, etc.)
3. Create records manually using data from tables above
4. Upload sample photos for attachment fields (use stock images or mockups)
5. Verify relationships (complaint → facility, inspection → complaint, etc.)

### 9.2 Import Set Seeding (Recommended for Large Datasets)
1. Create Excel/CSV files for each table using column names from tables above
2. Navigate to **System Import Sets → Load Data**
3. Upload CSV for each table
4. Map columns to target table fields
5. Transform and load data
6. Verify relationships and field mappings

### 9.3 Scripted Seeding (Advanced)
Create a Fix Script or Background Script to generate demo data programmatically:
```javascript
// Example: Create demo facility
var facility = new GlideRecord('x_eco_facility');
facility.initialize();
facility.setValue('name', 'Greenfield Chemical Works');
facility.setValue('facility_id', 'FC-2021-0042');
facility.setValue('sector', 'chemical');
facility.setValue('zone', 'north');
facility.setValue('address', '123 Industrial Parkway, North District');
facility.setValue('latitude', 18.9750);
facility.setValue('longitude', 72.8258);
facility.setValue('risk_score', 95);
facility.setValue('risk_tier', 'critical');
facility.setValue('violations_12m', 3);
facility.setValue('complaints_90d', 8);
facility.setValue('report_overdue', true);
facility.insert();
```

---

## Section 10: Demo Narrative Flow

For the hackathon presentation, walk judges through this narrative using the seeded data:

1. **Opening**: Show citizen portal → Submit complaint ES-20260725-0001 (Greenfield Chemical Works)
2. **AI Classification**: Show AI Severity Fusion Agent log → High severity, 92% confidence
3. **Risk Assessment**: Show Greenfield facility record → Risk score 95/100, 3 prior violations
4. **Inspector Dispatch**: Show FL-03 auto-assignment → INS0001001 assigned to Nikhil
5. **Field Inspection**: Show Now Mobile → Inspector captures 4 findings with photos
6. **AI Report Generation**: Show INS0001001 → AI-generated structured report
7. **Legal Case Creation**: Show LGL0001001 → Auto-generated legal narrative
8. **AI Audit Trail**: Show AI Control Tower → All agent decisions logged
9. **Executive Dashboard**: Show Sarah Jenkins' view → Risk heat map, SLA compliance, weekly insights

This narrative demonstrates the complete end-to-end flow from citizen submission to legal enforcement.

---

**Document Version**: 1.0  
**Last Updated**: Post-remediation pass  
**Owner**: Team VertexNow
