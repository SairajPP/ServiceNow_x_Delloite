# EcoSentinel Integrated Application Runbook

This is the implementation source of truth for building the app in ServiceNow without duplicate logic.

## Active Architecture

| Process | Active Owner | Disabled Fallbacks |
|---|---|---|
| Complaint insert defaults | `BR-C01` | None |
| Complaint webhook dispatch | `FL-01` | `BR-C02` |
| AI write-back validation | `BR-C03` | None |
| AI fallback after timeout | `FL-02` | None |
| Inspector dispatch | `FL-03` | None |
| Inspection outcome routing | `FL-05` + `EcoInspectionWorkflow` | `BR-I04`, `BR-I06` |
| Facility risk calculation | `EcoRiskCalculator` via Flow/BR callers | Duplicate inline formulas |
| Citizen notifications | `SF-01` and lifecycle catch-all `FL-09` | Ad hoc notification rules |
| Agent decision logging | FastAPI POST for external agents, `SF-03` / `EcoAgentLogger` for native agents | Logging inside unrelated update rules |

## Required Script Includes

Create these in the `x_eco` application scope:

1. `EcoRiskCalculator`
2. `EcoComplaintUtils`
3. `EcoAgentLogger`
4. `EcoConstants`
5. `EcoInspectionWorkflow`

`EcoInspectionWorkflow` is the key integration helper for FL-05. It makes legal case creation idempotent and prevents duplicate complaint/facility updates.

## Required New Fields

Add these fields before wiring the flows:

| Table | Field | Type | Purpose |
|---|---|---|---|
| `x_eco_complaint` | `webhook_sent_at` | Date/Time | Records when FL-01 dispatched the FastAPI webhook. |
| `x_eco_complaint` | `ai_processing_status` | Choice | Tracks `not_started`, `queued`, `processing`, `completed`, `failed`, `fallback`. |
| `x_eco_env_snapshot` | `data_source` | Choice | Tracks `success`, `partial`, or `error` for external environmental data. |

## Build Order

1. Create tables and fields from `tables.md`.
2. Create roles, groups, users, and ACLs from `roles-groups-users.md`.
3. Create Script Includes SI-01 through SI-05 from `business-rules-client-scripts.md`.
4. Create active Business Rules: `BR-C01`, `BR-C03`, `BR-C04`, `BR-C05`, `BR-C07`, `BR-F01`, `BR-F02`, `BR-F03`, `BR-F04`, `BR-I01`, `BR-I02`, `BR-I03`, `BR-I05`, `BR-I07`, `BR-L01`, `BR-L02`, `BR-A01`, `BR-E01`, `BR-E02`.
5. Create but keep inactive: `BR-C02`, `BR-I04`, `BR-I06`.
6. Create subflows: `SF-01`, `SF-02`, `SF-03`, `SF-04`.
7. Create flows: `FL-01` through `FL-10`.
8. Configure the FastAPI integration from `integration-contract.md`.
9. Create demo records and run the smoke tests below.

## Smoke Tests

| Test | Steps | Expected Result |
|---|---|---|
| Complaint intake | Submit a portal complaint with email, category, location, and photo. | Complaint state is `Received`; `webhook_sent_at` is populated; `ai_processing_status = queued`; citizen receives received notification. |
| AI write-back | PATCH severity fields from FastAPI. | `BR-C03` validates values, sets `state = AI Verified`, sets priority, and does not recursively update the same record. |
| AI timeout fallback | Create a complaint and do not PATCH it for 60 minutes. | `FL-02` sets medium severity, confidence 0, `ai_processing_status = fallback`, and state `AI Verified`. |
| Inspector dispatch | Set a complaint to AI Verified with severity. | `FL-03` creates one inspection and assigns the correct zone group/user. |
| Evidence enforcement | Try confirming violation before adding findings. | `BR-I05` blocks the update. |
| Legal case routing | Add finding, complete inspection as violation confirmed. | `FL-05` calls `EcoInspectionWorkflow.confirmViolation()`, creates exactly one legal case, links it to inspection, sets complaint to `Action Taken`, and recalculates risk. |
| Dismissal routing | Complete inspection as dismissed. | `FL-05` calls `EcoInspectionWorkflow.dismissInspection()`, sets complaint to `Dismissed`, and updates facility last inspection date. |
| Duplicate protection | Re-run FL-05 or update same completed inspection again. | No second legal case is created. |
| Agent log immutability | Try editing/deleting `x_eco_agent_log`. | `BR-A01` aborts update/delete. |
| Snapshot uniqueness | Try creating second snapshot for same complaint. | `BR-E02` blocks duplicate snapshot. |

## Known Boundaries

This repository contains the architecture and implementation specifications, not a ServiceNow update set or live PDI deployment. The app becomes fully working after the above components are created in the ServiceNow instance and the smoke tests pass.
