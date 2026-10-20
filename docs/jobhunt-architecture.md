# JobHunt architecture baseline

Audit date: 2026-10-19

## Current application

- Runtime: Python standard library; no framework, package manifest, or third-party app dependencies.
- UI: single-page HTML/CSS/JavaScript served by `app/server.py`.
- API: routes in the same local HTTP server, bound to `127.0.0.1`; SQLite work is in `app/core.py`.
- Persistence: SQLite at `app/data/jobhunt.db`; `app/data/.gitignore` keeps local records out of Git.
- Discovery: `core.run_discovery` calls the existing Freehire search/classify/dedupe helpers. Other sources are not connected.
- Existing persisted state at audit: 244 jobs, one application, saved searches and discovery runs. No description, resume-library, tailoring-request, contacts, or outreach tables.
- Candidate data: a resume exists under `documents/cv/`; the audit did not extract or reproduce its private contents.
- Integrations: no Resume Matcher API details or credentials are present. Notion and Gmail commands are separate repository workflows, not JobHunt integrations.
- Repository: branch `master`, `origin` points to the public GitHub fork. No commit, push, deployment, or remote change was made.

## Data flow

Saved search -> Freehire adapter functions -> source classification and deduplication -> SQLite jobs -> profile-based rule score -> dashboard and job detail -> separately persisted application status/events.

Search-run errors are recorded. Discovery does not mark jobs as applied. Application statuses that assert an external action require confirmation. Full descriptions are not fetched; existing score evidence is limited to titles and source skill tags.

## Baseline verification

- `python -m unittest tests.test_app_core tests.test_app_server -v`: 15 passed after the latest application changes.
- The full repository suite ran 669 tests: 12 reset-related failures/errors and 24 skips. The reset tests could not invoke WSL `/bin/bash` on this Windows host; failures are outside the JobHunt app.
- Local dashboard returned HTTP 200 at `http://127.0.0.1:8787`.

## First implementation increment

The initial audit was followed by an additive `job_description_snapshots` table. Existing 244 jobs remained present after the server restart/migration. Manual descriptions preserve original and normalized text, source URL, timestamp, method, SHA-256, status, and history; repeat pastes of unchanged text do not create duplicate snapshots. This path is user-supplied and always uses status `manual`. It does not fetch external URLs or alter the existing fit score.

The job list now supports source and description-state filters plus server-side pagination. The dashboard shows counts from the latest snapshot per job. JSON export includes description history. App-specific verification now runs 20 tests, all passing; the extracted dashboard JavaScript passes `node --check`.

The next increment added application-stage and follow-up filters, persisted application metrics, and a Resume Matcher adapter contract with a not-configured implementation. Tailoring requests are idempotent and local; manual packets include a resume reference but not resume bytes. A returned file can be linked only after an explicit confirmation and only when an existing PDF/DOCX is inside `documents/applications/`. Latest app-specific verification: 24 tests passed.

## Final regression run for this increment

`python -m unittest discover -s tests -v` ran 681 tests: 12 reset-test failures/errors caused by WSL being unable to start `/bin/bash`, with 24 skips. The app-specific suite passed all 24 tests. `node --check` passed for the dashboard script, and the local HTTP server is running on loopback.

## Persistence and compatibility

Use additive SQLite migrations (`CREATE TABLE IF NOT EXISTS`, inspect `PRAGMA table_info`, add nullable columns/tables) and leave existing job keys, JSON files, CSV files, and application records intact. Take a file copy before any destructive or format migration. Do not expose the single-user local server on a public interface without adding authentication and private-document access controls.

## Resume Matcher boundary

No service URL, API contract, or credential is configured. JobHunt can prepare and persist a local request and report `not_configured`; it must not report remote success. The future adapter belongs in an integration module and must use server-side credentials, timeouts, idempotency, and validated result references.
