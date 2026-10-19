# Stage C.1 — Read-only Job Browsing Pilot Results

Date: 2026-10-19. Pilot implementation only; no broad migration, commit, push, or deployment.

## Workspaces

- Integration plan/docs: `D:\AI-Job\ai-job-search-integration`, branch `integration/resume-matcher-foundation`.
- Host application code: `D:\Resume-Matcher\Resume-Matcher`, branch `deployment-hardening` (modified locally, uncommitted; branch not switched).
- JobHunt remains the source of job records. Its checkout/branch and application data were not modified by this pilot.

## Snapshot and source integrity

A snapshot was made with Python's SQLite `Connection.backup()` API from a `mode=ro` source connection. It is outside both repositories:

`D:\AI-Job\stage-c-pilot\jobhunt_snapshot.sqlite`

The containing folder, snapshot, SQLite sidecar files, and separate Matcher test-data folder have protected Windows ACLs granting full control only to the current Windows user, SYSTEM, and local Administrators. The app read only the snapshot path. A separate empty Resume Matcher data directory was used; no existing Matcher database/configuration was opened for writes.

| Check | Source | Snapshot |
|---|---:|---:|
| Jobs | 244 | 244 |
| Applications (not returned by the adapter) | 2 | 2 |
| Description snapshots | 0 | 0 |
| SQLite integrity | n/a | `ok` |
| SHA-256 | `56d7b8620bfe12133d749cf6219cc508d746c3d2ae458ccc9a9c6d222d23b3f0` | `1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b` |

The original source hash matched immediately before and after snapshot creation and again after API/UI verification. The snapshot hash and row counts remained stable after live browsing. The backup operation used SQLite's online backup API, so it did not raw-copy a live WAL database.

## Implementation

The Resume Matcher backend now has a `JobHuntSnapshotCatalog` adapter and GET-only API routes:

- `GET /api/v1/discovery/jobs` — bounded page (maximum 20), optional title/company query and location filter.
- `GET /api/v1/discovery/jobs/{job_key}` — read-only detail lookup by JobHunt's canonical key.

The adapter requires the explicit `JOBHUNT_SNAPSHOT_PATH`; it never defaults to JobHunt's live DB. It opens SQLite with `mode=ro&immutable=1`, sets `PRAGMA query_only=ON`, uses bound query values, and caps its scan at 10,000 matches. It returns only job key, title, company, location, source URL/source, posting/first-seen dates and description status/availability. It does not return application records/statuses, resume data, description body, score/profile evidence, or any write capability. Missing optional data is `null` or `missing`; malformed required records and duplicate key/URL candidates are skipped. Schema, path, or DB errors return a generic 503 without a filesystem path.

The Resume Matcher Next.js UI now provides `/discover/jobs` and `/discover/jobs/[jobKey]`, linked from the existing SwissGrid dashboard footer. It has loading, retryable error, empty, search, pagination, job detail and explicit external source-link states. It uses the existing Swiss design components and same-origin API proxy. No application, resume, authentication, tailoring, or discovery-state workflow was added or changed.

## Exact repository files changed

### Resume Matcher (`deployment-hardening`, uncommitted)

- `apps/backend/app/main.py`
- `apps/backend/app/routers/__init__.py`
- `apps/backend/app/routers/jobhunt_discovery.py` (new)
- `apps/backend/app/schemas/jobhunt_discovery.py` (new)
- `apps/backend/app/services/jobhunt_snapshot.py` (new)
- `apps/backend/tests/integration/test_jobhunt_discovery_api.py` (new)
- `apps/backend/tests/unit/test_jobhunt_snapshot.py` (new)
- `apps/frontend/app/(default)/discover/jobs/page.tsx` (new)
- `apps/frontend/app/(default)/discover/jobs/[jobKey]/page.tsx` (new)
- `apps/frontend/components/discovery/job-list-page.tsx` (new)
- `apps/frontend/components/discovery/job-detail-page.tsx` (new)
- `apps/frontend/components/home/swiss-grid.tsx`
- `apps/frontend/lib/api/jobhunt-discovery.ts` (new)
- `apps/frontend/messages/en.json`, `es.json`, `fr.json`, `ja.json`, `ko.json`, `pt-BR.json`, `zh.json`
- `apps/frontend/tests/jobhunt-discovery.test.tsx` (new)
- `apps/frontend/tests/swiss-grid.test.tsx`

### Integration documentation (`integration/resume-matcher-foundation`)

- `docs/integration/stage-c-first-slice.md`
- `docs/integration/stage-c-readiness-report.md`
- `docs/integration/stage-c-pilot-report.md` (this report)

No source code, database, test, dependency, or configuration file in the original JobHunt checkout was changed. No Resume Matcher `.env` or user data directory was edited. Next.js created its ignored `apps/frontend/AGENTS.md` and updated the existing ignored `.next` development cache while the local UI was running; these are runtime artifacts, not committed changes.

## Verification results

- New adapter and API tests plus existing Resume Matcher jobs/health API tests: **29 passed** (`uv run pytest tests/unit/test_jobhunt_snapshot.py tests/integration/test_jobhunt_discovery_api.py tests/integration/test_jobs_api.py tests/integration/test_health_api.py -q --tb=short`).
- Focused frontend tests: **11 passed** (`npm run test -- tests/jobhunt-discovery.test.tsx tests/swiss-grid.test.tsx --run`).
- Existing JobHunt app/core/server/adapter tests: **24 passed** (`python -m unittest tests.test_app_core tests.test_app_server tests.test_resume_matcher_adapter -v`).
- Targeted Python lint: `uv run ruff check ...` — passed. The changed frontend files pass scoped `oxlint` and `oxfmt --check`.
- Live API on loopback: list `200`, 244 total / 20 returned, detail `200`, POST `405`.
- Live headless Chrome: `/discover/jobs` returned `200`; 20 listings rendered; navigation opened a detail route; one external source link had `target="_blank"` and `rel="noopener noreferrer"`; missing-description state appeared; **0 browser JavaScript errors**.

The repository-wide `npm run lint` reached `oxfmt --check` and failed because it reports formatting issues in 340 files across the existing frontend tree (after formatting the changed files). It did not report changed-file lint errors; changed files pass scoped checks. `npm run typecheck` was started but had emitted no output after more than two minutes, so it was stopped; TypeScript validation remains unverified. Full backend and full frontend suites were not run in this slice; the Stage B.1 baseline issues remain as documented.

The live browser check used headless Chrome at a desktop viewport only. Mobile/responsive layout, another browser engine, and a manually stored description were not browser-verified; empty/error states are covered by UI component tests, and description availability is covered by adapter/API tests.

## Local pilot currently running

The backend and frontend dev servers are still running on loopback:

- `http://127.0.0.1:3013/discover/jobs`
- Backend: `http://127.0.0.1:8013`

They were started with `APP_ENV=development`, `DATA_DIR=D:\AI-Job\stage-c-pilot\matcher-data`, `DATABASE_URL` blank, and `JOBHUNT_SNAPSHOT_PATH` set to the snapshot above. They are bound to `127.0.0.1`. A pre-existing malformed line in the local Resume Matcher `.env` causes python-dotenv warnings at startup; the explicit isolated environment overrides took effect and the app started normally. No `.env` content was copied into the report.

## Readiness and remaining limits

The **read-only browsing pilot is working against the disposable snapshot**. It is not a complete integration and no record migration occurred. All 244 current jobs display with description unavailable because this snapshot has no description snapshots. An end-to-end view with a stored description is covered by adapter tests, not live data.

Keep this pilot isolated. Do not point `JOBHUNT_SNAPSHOT_PATH` at `D:\AI-Job\ai-job-search\app\data\jobhunt.db`. Before a larger migration, resolve the stopped TypeScript check and previously documented PDF/Playwright/full-suite baseline limitations, then review a separate migration plan and backup/rollback gate.


## Stage C.2 — discovery improvements

Date: 2026-10-19. Implemented on the existing Resume Matcher `deployment-hardening` checkout; integration plans remain on `integration/resume-matcher-foundation`. Existing uncommitted Stage C.1 files were preserved. No commit, push, deployment, migration, or database write was performed.

### Supported read-only contract

- `GET /api/v1/discovery/jobs`: `page` (1–501), `page_size` (1–20), `offset` (0–10,000), `q` (title/company/location substring, case-insensitive), `location` (substring), `source` (case-insensitive exact), `description_available` (boolean), `posted_after` / `posted_before` (inclusive ISO dates), `sort` (`first_seen`, `posted_date`, `title`, `company`, `location`, `source`), and `direction` (`asc`, `desc`). Values are bound parameters; sort fields/direction use explicit allowlists. Stable job-key tie-breaking is applied.
- `GET /api/v1/discovery/jobs/{job_key}` returns the same validated summary fields.
- Both endpoints return only `job_key`, `title`, `company`, `location`, `source_url`, `source`, `posted_date`, `first_seen`, `description_status`, and `description_available`. Tests assert the exact key set. No application, resume, arbitrary column, or description-body data is returned.
- The UI exposes these filters/sorts, reflects applied state in the URL, carries it back from details, displays missing/failed/unknown description status distinctly, and preserves the explicit safe external link. Descriptions remain unavailable to the UI under the approved Stage C.1 contract. The snapshot has 244 jobs and zero description snapshots.

### Stage C.2 files

Resume Matcher code (all uncommitted in `D:\Resume-Matcher\Resume-Matcher`):

- `apps/backend/app/services/jobhunt_snapshot.py`
- `apps/backend/app/routers/jobhunt_discovery.py`
- `apps/backend/app/schemas/jobhunt_discovery.py`
- `apps/backend/tests/unit/test_jobhunt_snapshot.py`
- `apps/backend/tests/integration/test_jobhunt_discovery_api.py`
- `apps/frontend/components/discovery/job-list-page.tsx`
- `apps/frontend/components/discovery/job-detail-page.tsx`
- `apps/frontend/app/(default)/discover/jobs/[jobKey]/page.tsx`
- `apps/frontend/lib/api/jobhunt-discovery.ts`
- `apps/frontend/tests/jobhunt-discovery.test.tsx`

Integration documentation (`D:\AI-Job\ai-job-search-integration`):

- `docs/integration/stage-c-first-slice.md`
- `docs/integration/stage-c-readiness-report.md`
- `docs/integration/stage-c-pilot-report.md`

### Verification

- Backend discovery adapter/API plus existing jobs/health tests: **31 passed** — `uv run pytest tests/unit/test_jobhunt_snapshot.py tests/integration/test_jobhunt_discovery_api.py tests/integration/test_jobs_api.py tests/integration/test_health_api.py -q --tb=short`.
- Exact response contract and core adapter/API subset: **17 passed** — `uv run pytest tests/unit/test_jobhunt_snapshot.py tests/integration/test_jobhunt_discovery_api.py -q --tb=short`.
- Focused frontend: **12 passed** — `npm run test -- tests/jobhunt-discovery.test.tsx tests/swiss-grid.test.tsx --run --pool=threads --maxWorkers=1`.
- Existing JobHunt application suite: **24 passed** — `python -m unittest tests.test_app_core tests.test_app_server tests.test_resume_matcher_adapter -v`.
- Scoped backend Ruff passed; scoped frontend Oxlint and Oxfmt checks passed. Formatting was limited to changed discovery components and their focused test.
- Snapshot SHA-256 before/after: `1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b` / `1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b` (unchanged). Original JobHunt database SHA-256 after verification is `56d7b8620bfe12133d749cf6219cc508d746c3d2ae458ccc9a9c6d222d23b3f0`, matching the pre-pilot value.
- C.2 live loopback check: `GET /api/v1/discovery/jobs?q=engineer&location=Dubai&sort=title&direction=asc&offset=0&page_size=20` returned 20 rows / 87 matches; an injected sort value returned 422; the frontend `/discover/jobs` and API root each returned HTTP 200. No headless browser check was repeated for C.2; UI state interactions are covered by focused frontend tests. Current code is running at `127.0.0.1:3013` and `127.0.0.1:8013`.
- Full backend/frontend regression suites remain out of scope. `npm run typecheck` produced no output after approximately 40 seconds and was stopped; TypeScript remains unverified.

No additional stage is authorized by this report; Stage C.2 stops at read-only discovery.


