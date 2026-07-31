# EcoSentinel Architecture Improvement Plan

This document captures the changes needed to move the current architecture from a strong hackathon design to a cleaner implementation-ready design.

## Target Rating

Current architecture rating: **7.5 / 10**

Target after these improvements: **8.5 / 10**

The main improvement is not adding more features. It is clarifying ownership, reducing duplicate execution paths, and making the ServiceNow implementation safer.

## Architecture Decisions

| Decision | Final Choice | Reason |
|---|---|---|
| Complaint webhook owner | `FL-01` Flow Designer flow | Keeps orchestration visible, retryable, and easier to demo. |
| BR-C02 status | Disabled fallback only | Prevents duplicate webhook pings and duplicate AI analysis jobs. |
| Inspection outcome owner | `FL-05` Flow Designer flow using `EcoInspectionWorkflow` | Prevents Business Rules and Flow Designer from both creating legal cases or closing complaints. |
| AI write-back rule timing | Before-update Business Rule | Derived fields can be set in the same transaction without recursive `current.update()` calls. |
| Agent logging owner | FastAPI explicit POST plus `SF-03` for native agents | Avoids double-logging the same external decision. |
| Integration auth | OAuth preferred; Basic Auth acceptable for PDI only | Improves production posture while preserving hackathon practicality. |
| Audit immutability | ACL denial plus before-rule abort | More realistic than relying on "Nobody" as an implementation detail. |

## Clean Runtime Flow

1. Citizen submits complaint through Service Portal Record Producer.
2. `BR-C01` sets insert defaults before the record is committed.
3. `FL-01` sends exactly one webhook ping to FastAPI and stores `webhook_sent_at`.
4. FastAPI validates idempotency by `sys_id`, returns `202 Accepted`, and processes analysis asynchronously.
5. FastAPI fetches complaint data and attachments from ServiceNow.
6. FastAPI calls OpenAI, Weather, and AQI services in parallel where possible.
7. FastAPI PATCHes `ai_severity`, `ai_confidence`, `ai_rationale`, `ai_image_caption`, and `ai_classified_at`.
8. `BR-C03` validates the write-back and sets `state = AI Verified` plus derived `priority`.
9. `FL-03` creates/assigns the inspection and starts downstream SLA/notification handling.
10. FastAPI creates an `x_eco_env_snapshot` and `x_eco_agent_log` record for auditability.
11. `FL-05` calls `EcoInspectionWorkflow` when the inspection completes, either creating/linking a legal case or dismissing the complaint.
12. If FastAPI never writes back, `FL-02` applies a medium-severity fallback after 60 minutes.

## Implementation Checklist

| Priority | Item | Done When |
|---|---|---|
| P0 | Add `webhook_sent_at` Date/Time field to `x_eco_complaint` | FL-01 no longer relies on `sys_updated_on`. |
| P0 | Add `ai_processing_status` choice field to `x_eco_complaint` | Queued, completed, failed, and fallback AI states are visible. |
| P0 | Keep BR-C02 inactive | Only one webhook is emitted per complaint insert. |
| P0 | Keep BR-I04 and BR-I06 inactive when FL-05 is active | Only one legal case and one complaint closure path exists. |
| P0 | Convert BR-C03 to before-update | No `current.update()` or secondary GlideRecord update is used on the same complaint. |
| P0 | Create Script Includes SI-01 through SI-08 | Shared calculations and outcome routing are reusable and testable. |
| P0 | Add CAPTCHA and rate limiting to portal widget | Prevents automated spam from exhausting external API limits. |
| P0 | Add FastAPI idempotency table/cache | Duplicate `sys_id` jobs return `409` or no-op safely. |
| P1 | Replace Basic Auth with OAuth for non-demo environments | ServiceNow credentials can be rotated and scoped cleanly. |
| P1 | Add break-glass admin repair procedure | Immutable logs remain defensible without blocking emergency recovery. |
| P1 | Add sample data pack | Demo users, facilities, complaints, inspections, and legal cases can be loaded repeatably. |
| P2 | Add sequence diagram to final pitch deck | Judges can understand the full flow in one slide. |
| P2 | Add update set/export checklist | Build can be recreated in a fresh PDI. |

## Remaining Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Flow and Business Rule overlap | Duplicate backend calls and inconsistent audit records | FL-01 is the only active webhook owner; BR-C02 remains disabled. |
| AI write-back recursion | Extra updates, unexpected BR execution, audit noise | BR-C03 runs before update and mutates only `current`. |
| Public complaint intake abuse | Spam or high external API usage | **Addressed**: CAPTCHA and rate limiting required at portal layer + FastAPI idempotency checks. |
| PDI credential exposure | Backend can be abused if Basic Auth leaks | Use web-service-only account, least-privilege ACLs, and OAuth when moving beyond demo. |
| Audit record edits | Governance story weakens | ACL denial plus before-rule abort; corrections are append-only records. |

## Revised Rating

After applying the above decisions, the architecture is closer to **8.5 / 10**:

- Data model: **8.5**
- Workflow ownership: **8.5**
- Integration design: **8**
- Security model: **8**
- Implementation readiness: **8**

The remaining gap to 9+ is mostly proof: actual update sets, test records, backend code, automated smoke tests, and a repeatable deployment path.
