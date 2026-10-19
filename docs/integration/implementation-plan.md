# Integration implementation plan

Status: Stage A audit completed. No source integration started. The attached engineering brief explicitly limits its final instruction to Stage A; implementation below is therefore a plan, not a claim of completion.

## Stage B — establish a safe workspace

1. Preserve JobHunt `master` and Resume Matcher `deployment-hardening`; do not switch, merge, commit or push either repository.
2. Add a JobHunt integration branch/worktree only after user confirms the architecture. The current JobHunt untracked files are active work and must be included/preserved.
3. Create protected copies of both ignored data directories with no secrets in logs. Validate backup sizes/hashes without dumping content.
4. Record reproducible backend/frontend test commands and dependency availability. No dependency installation until an isolated environment is approved by the repo owner (packages are pinned and substantial).

## Stage C — incremental implementation proposal

1. **Runtime shell spike:** run Next.js + FastAPI in a JobHunt integration worktree using existing Resume Matcher manifests; retain the old JobHunt server and database unchanged. Establish same-origin proxy and auth behavior.
2. **JobHunt domain extraction:** port discovery, saved search, job list/detail, status/history, follow-up and exports behind typed FastAPI service/routes; migrate data transactionally and compare record counts/keys/events against backup.
3. **Unified navigation:** adapt Resume Matcher default layout with Overview, Discover and Applications while preserving its design tokens/components and all existing routes. Add navigation tests and responsive checks.
4. **Resume workflows:** retain parser/upload, library, builder/templates, enrichment/wizard, ATS analysis, tailoring/queue, cover letter/outreach/interview prep, preview/export. Verify one workflow at a time against source behavior and tests.
5. **Job-to-resume association:** add idempotent association table/migration and flow using selected JobHunt description snapshot and existing matcher services. Keep application state independent; validate generated resume linkage and PDF download.
6. **Settings/cost:** keep agent mode cost-safe; configure provider keys only through existing encrypted settings UI. Make provider usage opt-in and test timeout/quota errors.
7. **Reliability/security:** auth, CSRF, upload/path restrictions, data isolation, database busy/interrupted writes, API failures, missing source descriptions and rollback tests.
8. **Cutover readiness:** full existing suites, route and browser e2e, data parity, browser console/log checks, backup/restore drill, setup docs. Local single-user only until identity issue is resolved.

## Stage D gates

- JobHunt discovery and application workflows pass regression tests against migrated disposable data.
- Matcher upload/edit/tailor/preview/export journeys pass in the unified interface.
- Source resume hash/content remains unchanged after tailoring; generated resume points to the correct source and job.
- Database/app status changes have explicit, test-covered ownership.
- Authentication, CSRF, host/origin checks and session behavior pass in development and production-like settings.
- Tests requiring WSL, PostgreSQL, a provider, browser, or external service are reported separately and never inferred as passing.

## Decisions and blockers

- User confirmation is needed before starting beyond the attached Stage A-only scope because the safest direction entails a substantial host/framework transition and additional pinned dependencies.
- Matcher auth is one shared password, not multi-user accounts. Do not expose a hosted multi-user product until identity and data ownership are specified.
- Free AI use cannot be guaranteed from repository code: providers have separate terms, availability, quotas and billing. Agent mode avoids app-originated model calls.
- Backend baseline cannot run in the available `uv` environment because pytest is absent; do not install it as part of a read-only audit.
