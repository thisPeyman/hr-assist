# 20: `needs_review` queue

**What to build:** Nothing dropped silently, made visible. A first-class screen listing every flagged parse — low confidence, missing name/contact, failed formats — showing the original document and whatever partial data was extracted, so HR works the queue in the UI rather than reading a log. Resolving a row means editing and accepting the partial data into a Profile (human corrections win), or dismissing it to an explicit terminal status (`not_a_resume`, `failed`). Queue presence and counts are visible from the home surface; every submitted document is either worked here or landed cleanly — nothing sits invisible. (Spec §4 principle 2, §11 screen 4.)

**Blocked by:** 11 (Upload → parse → Candidate in the Talent Pool).

**Status:** resolved

- [x] Every `needs_review` row surfaces in the queue with the original doc + partial extracted data
- [x] HR can resolve a row by editing and accepting the partial Profile, or dismissing to an explicit terminal status
- [x] Accepted corrections win — later re-extraction never overflows them (respects ticket 13's rules)
- [x] Queue is discoverable with visible counts; no document can end in an invisible state


## Answer

Implemented `/review`, all-document history, visible counts on home/pool, tenant-scoped detail/download/PNG-preview APIs, editable partial Profile forms, human acceptance/dismissal, Activity entries, immutable raw extraction and protection against overwriting accepted Profiles on replay. Quarantined attachments cannot be downloaded or accepted; scanning can be retried. Added a local ingestion-settings screen and clear empty/error states.

Validation: API tests exercise acceptance, dismissal, repeated decisions, provenance retention, quarantine protection and cross-Org access; Playwright/Edge verifies PDF preview, profile correction, dismissal/history and a 390px mobile viewport. A long-status mobile overflow was found and fixed. See [verification details](../../../docs/resume-ingestion.md).

## Comments

- 2026-10-31: Review found these screens absent from the latest MUI App routes,
  despite historical completion text. [Repair 29](29-review-regressions.md)
  implements queue/history, safe doc/partial full Profile, accept/dismiss/rescan,
  mail failures and discoverable counts. Acceptance now preserves corrections
  and identity/version invariants. API/Postgres regression tests plus static
  frontend checks were run; no new browser verification, per user scope.
