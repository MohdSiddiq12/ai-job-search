# Stage C readiness report

Date: 2026-10-19.

## Stage C.1 pilot

The minimal read-only JobHunt browsing slice is implemented in the Resume Matcher host on the existing `deployment-hardening` branch. It reads a restricted disposable SQLite snapshot outside both repositories through a mode-ro/query-only adapter, serves bounded GET-only list/detail endpoints, and displays list/detail pages in the existing Next.js Swiss UI. The original JobHunt DB was not used by the app and its SHA-256 remained unchanged before/after snapshot and after live browsing. There was no migration of application history, resumes, authentication, or tailoring state.

Evidence and exact files are in `stage-c-pilot-report.md`. New/related backend tests and existing JobHunt app tests pass; the actual loopback UI was opened in headless Chrome and had no JS errors.

## Readiness decision

**The isolated browsing pilot is ready for local review on its disposable copy. The broader integration is not complete or ready for cutover.** Keep the original JobHunt app/data authoritative and leave `JOBHUNT_SNAPSHOT_PATH` pointing only to the restricted pilot snapshot.

## Stage C.2 discovery improvements

The read-only adapter now supports title/company/location search; location, source, description-availability, and inclusive posting-date filters; and stable sorting by first seen, posting date, title, company, location, or source. Results remain bounded to 20 per page and offset 10,000. Description text remains excluded under the Stage C.1 response contract; the current snapshot has zero description rows. Stage C.2 verification details and remaining limitations are in `stage-c-pilot-report.md`.

Before any larger migration:

1. Resolve the stalled/unverified frontend TypeScript check.
2. Continue from the existing Stage B.1 full backend/frontend test baseline; do not claim those full suites pass.
3. Investigate real Playwright/PDF startup and lifecycle failures before relying on PDF/export workflows.
4. Design and separately review any move of applications, statuses/events, resumes, authentication, or tailoring workflows. This pilot does not authorize those migrations.

The current pilot has no unresolved blocker to read-only local review. Its limitations are the absent live descriptions in this snapshot, full-suite baseline, and TypeScript check. No commit, push, or deployment was made.
