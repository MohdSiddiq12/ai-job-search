# JobHunt implementation backlog

Status recorded 2026-10-19; prioritize end-to-end usefulness while preserving the current local SQLite data.

## Phase 0 — audit (complete)

- Confirmed Python stdlib, local HTTP server, static UI, SQLite, Freehire-only discovery, current tables and repository entry points.
- Ran app tests and full-suite baseline; see `jobhunt-architecture.md`.

## Phase 1 — application foundation (in place, partial)

- [x] Local server, persisted dashboard, job list/detail, saved searches, profile scoring, application state, run history, JSON export.
- [x] Host/Origin checks and private SQLite data folder.
- [x] Additive migration for manual job-description snapshots without rewriting existing records.
- [x] Dedicated applications list, follow-up-date editing, filtering and dashboard counts.
- [ ] Show explicit loading, empty, error, and unavailable integration states consistently.
- [ ] Add functional Applications and Settings views with real persisted data.

## Phase 2 — job workflow (in progress)

- [x] Persist original and normalized job-description snapshots with source, retrieval method, content hash, timestamps, and extraction status.
- [x] Add user-initiated manual description paste/correction; keep it marked `manual`, never claim it was fetched or fully extracted.
- [ ] Add source adapter contract and document each source's access method, supported filters, rate limits, and limits.
- [x] Add description-state and source filters with server-side pagination. (Age/application filters already existed; other requested filters remain.)
- [ ] Expand explainable fit evidence from descriptions without conflating fit, eligibility, ATS alignment, or hiring probability.
- [ ] Add stale/reposting evidence and application follow-up views.

## Phase 3 — document and Resume Matcher readiness

- [x] Define and test the Resume Matcher adapter contract, idempotent tailoring records, unavailable state, and manual export/import boundary.
- [ ] Add private resume metadata/library and safe local download/upload only after access validation and storage rules are implemented.
- [ ] Associate selected resumes and tailored-document references with jobs and applications.

## Phase 4 — automation and integrations

- [ ] Make scheduler behavior observable and reliable for Windows Task Scheduler.
- [ ] Retry/report transient source failures without exceeding documented access limits.
- [ ] Implement only integrations for which actual credentials/contracts are supplied.

## Phase 5 — hardening

- [ ] Add migration backup/recovery checks, request limits, structured operational errors, and end-to-end UI coverage.
- [ ] Keep the app loopback-only until authentication and document authorization are designed.
- [ ] Re-run the full suite in an environment with supported WSL or port the affected reset tests to PowerShell.

## Increment delivered 2026-10-19

- Added versioned manual-description snapshots and profile-skill mention evidence without claiming verified extraction or changing fit scores.
- Added dashboard description counts, description/source filters, pagination, and description export.
- Added migration, validation, deduplication, persistence, filtering, export, and HTTP security tests.
- Latest app-specific suite: 20 passed. Browser control was unavailable; HTTP and JavaScript syntax were checked.
- Added a local Resume Matcher packet flow and secure reference checks; the current adapter makes no network request.
- Added application-stage/follow-up filters and persisted dashboard metrics. Latest suite: 24 app tests passed.
- Repository regression run: 681 tests, 12 reset-test failures/errors from unavailable WSL /bin/bash, 24 skipped; no JobHunt test failures.
