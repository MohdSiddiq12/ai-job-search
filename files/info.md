# JobHunt + Resume Matcher — Project Technical Brief

**Snapshot date:** 20 October 2026 (Asia/Kolkata)  
**Purpose:** Source-linked handoff for understanding the local integration, its current data, implementation, limits, verification state, and unresolved risks.  
**Scope:** JobHunt, the Resume Matcher host, and the integration plan. Resume text, contact details, credentials, and profile keywords are intentionally excluded.

## 1. Executive summary

The local Resume Matcher app now contains JobHunt discovery and tracking features. Live search calls Freehire’s public API, creates bounded title, skill, and semantic-neighbor queries from the saved profile, ranks results locally, and stores results in the Resume Matcher SQLite database. The current local database has **107 Freehire listings**, one saved search profile, five search runs, and a latest completed run with **106 matches, 38 new records, and no reported source errors**. All 107 stored descriptions currently carry the implementation’s “complete” status.

The migration is **not fully verified**. C.3–C.7 are recorded as implemented; the complete 11-step search-to-export journey and Stage 0 regression gate remain open. The full backend suite has recorded failures and the full frontend test suite stalled. At inspection, the database had zero tailoring-preview rows and zero JobHunt-to-job link rows; this is not a substitute for running the full workflow. The active SQLite database is in WAL mode; the existing final backup contains 69 live listings, so it predates the current 107-listing state.

This is a **local application with external network dependencies**, not an air-gapped system. Freehire receives search terms, filters, and public seed job IDs. Resume text is not sent to Freehire. Resume Matcher can send tailoring or other AI prompts to its configured LLM provider; the active provider was not inspected for this report.

## 2. Evidence labels

- **[CURRENT]** Read-only inspection on 20 October 2026: SQLite metadata, Git status, process metrics, source code, or HTTP probes.
- **[RECORDED]** Result documented in dated execution or verification reports; not necessarily rerun while writing this brief.
- **[CODE]** Behavior present in the implementation; this does not by itself prove the entire user journey works.
- **[OPEN]** Not verified or a known unresolved issue.
- **[HYPOTHESIS]** Plausible explanation without enough evidence to call it the root cause.

No application code, database contents, or test files were changed while collecting the facts for this report. Database inspection used read-only SQLite connections. The only intended file change is this brief.

## 3. What the project does

### JobHunt

JobHunt is a local job-search and application workflow built around a Python standard-library HTTP server, a single-page HTML/CSS/JavaScript interface, and SQLite. Its broader agent workflow covers candidate profiling, searching, fit review, CV/cover-letter drafting, application tracking, company research, and interview preparation. Portal search skills are separate instructions and CLI integrations under .agents/skills; they are not all connected to the integrated Resume Matcher search page.

The local JobHunt application data inspected here contains 244 jobs, two application records, and zero job-description snapshots. The source database was not changed by the integration work. [CURRENT]

### Resume Matcher

Resume Matcher is the host application. Its existing product includes resume storage and editing, job-description-based tailoring with preview/confirmation, ATS-related parsing/scoring, document export, and application tracking. The integration calls its existing tailoring workflow instead of introducing a second resume editor. [CODE]

### Integrated local workflow

The migration adds a discovery page, persistent Freehire results, save/skip states, saved searches, a development-only scheduler, an application follow-up workspace, and a handoff to Resume Matcher tailoring. The local UI is served at [http://127.0.0.1:3013](http://127.0.0.1:3013); the FastAPI backend listens at [http://127.0.0.1:8013](http://127.0.0.1:8013). [CURRENT]

~~~mermaid
flowchart LR
  JH[(JobHunt SQLite<br/>read-only source)] --> SNAP[Local snapshot<br/>244 legacy jobs]
  SNAP --> API[Resume Matcher<br/>FastAPI]
  FH[(Freehire public API)] --> SEARCH[Profile search<br/>HTTPX client]
  SEARCH --> DB[(Resume Matcher<br/>SQLite + WAL)]
  API --> DB
  UI[Next.js local UI] <--> API
  UI -->|selected job + full description| TAILOR[Existing tailor preview]
  TAILOR --> DB
  TAILOR -. configured provider may be remote .-> LLM[LLM provider]
~~~

The original JobHunt database and its snapshot are separate from Resume Matcher’s active database. The app reads the snapshot for the legacy 244 listings and writes newly discovered Freehire listings to Resume Matcher’s database. [CODE]

## 4. Repository and working-tree map

| Checkout | Branch / revision | Current state |
|---|---|---|
| JobHunt: D:\AI-Job\ai-job-search | master / 30158c0 | Has untracked local additions including app/, docs/, tests/, .opencode/, and files.zip. These are present in the checkout and are not integration changes made while preparing this report. The source DB hash still matches the recorded baseline. [CURRENT] |
| Integration workspace: D:\AI-Job\ai-job-search-integration | integration/resume-matcher-foundation / d1b67fe | Holds integration plans and reports. It currently has eight untracked report/plan/tool files under docs/integration and files/, including this brief. See [unified-execution-plan.md](unified-execution-plan.md). [CURRENT] |
| Resume Matcher host: D:\Resume-Matcher\Resume-Matcher | deployment-hardening / 36223c97 | **48 uncommitted paths:** 29 modified tracked files and 19 untracked files across backend, frontend, and tests. Migration code lives here. No commit, push, or deployment has been made. [CURRENT] |

The integration execution plan says C.3–C.7 are implemented, C.8 is partial, and Stage 0 remains open. The present database has advanced beyond the counts written in that plan: the plan records 69 live listings/four runs, while the current database has 107/five. Treat this report’s current database query as the latest count; reconcile the plan’s numbers on its next update. [CURRENT]

## 5. Feature inventory and code ownership

| Feature | What it does / current state | Source of truth |
|---|---|---|
| Legacy JobHunt dashboard and API | Local single-user job list, search/discovery, statuses, notes, follow-ups, and events backed by SQLite. | [server.py](../../ai-job-search/app/server.py), [core.py](../../ai-job-search/app/core.py), [dashboard](../../ai-job-search/app/static/index.html) |
| JobHunt portal-search skills | Separate portal-focused skills exist for Freehire, Jobbank, JobDanmark, Jobindex, Jobnet, and LinkedIn, plus job-application and scraper workflows. Presence of a skill does not prove its CLI is installed, authenticated, or used by the integrated page. | [JobHunt skill folders](../../ai-job-search/.agents/skills), [job scraper workflow](../../ai-job-search/.claude/skills/job-scraper) |
| Legacy JobHunt browsing | Read-only catalog adapter exposes the 244-row source snapshot to Resume Matcher. The source database itself is not the live write target. The snapshot has no description snapshots. | [jobhunt_snapshot.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/services/jobhunt_snapshot.py), [jobhunt_discovery.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/jobhunt_discovery.py) |
| Live external search | Calls Freehire’s public API using profile title queries, configured title synonyms, skill/full-text queries, and optional similar-job expansion. The source adapter uses HTTPX; it does not automate a browser across job-board sites. | [jobhunt_live_search.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/services/jobhunt_live_search.py) |
| Local fit ranking | Computes a deterministic weighted score from role/title overlap, skills, seniority, and location. The score is a sorting aid, not an ATS result or a prediction of hiring. | [jobhunt_live_search.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/services/jobhunt_live_search.py) |
| Search history and persistence | Stores canonical Freehire keys, source URLs, descriptions, retrieval/check times, description hashes, score evidence, run counts, and profile/search state in local SQL tables. | [models.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/models.py), [database.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/database.py) |
| Search UI | Profile search, query/search controls, saved searches, stored results, filters, and job detail screens. | [discovery page](<../../../Resume-Matcher/Resume-Matcher/apps/frontend/app/(default)/discover/jobs/page.tsx>), [detail page](<../../../Resume-Matcher/Resume-Matcher/apps/frontend/app/(default)/discover/jobs/[jobKey]/page.tsx>), [discovery components](../../../Resume-Matcher/Resume-Matcher/apps/frontend/components/discovery), [API client](../../../Resume-Matcher/Resume-Matcher/apps/frontend/lib/api/jobhunt-discovery.ts) |
| Save / skip / tracker link | Discovery state can be saved or skipped; records are designed to be idempotent. Imported and tailored JobHunt cards remain saved, not automatically applied. | [jobhunt_discovery.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/jobhunt_discovery.py), [application models](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/models.py) |
| Description detail | Displays stored descriptions and provenance. A manual-paste path exists for missing source text; incomplete text is not treated as ready for normal tailoring. | [jobhunt_snapshot.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/services/jobhunt_snapshot.py), [jobhunt_discovery.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/jobhunt_discovery.py), [discovery API client](../../../Resume-Matcher/Resume-Matcher/apps/frontend/lib/api/jobhunt-discovery.ts) |
| Tailor handoff | A selected discovery job and description are prepared as an existing Resume Matcher job, then routed through the existing tailor preview/confirm flow. A real search-to-export journey has not yet been fully exercised end to end. | [JobHunt tailor endpoint](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/jobhunt_discovery.py), [tailor page](<../../../Resume-Matcher/Resume-Matcher/apps/frontend/app/(default)/tailor/page.tsx>), [resumes router](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/resumes.py) |
| Application follow-ups | Follow-up overview, saved outreach drafts, notes, and status history with confirmation metadata. | [applications router](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/applications.py), [application schemas](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/schemas/applications.py), [follow-up page](<../../../Resume-Matcher/Resume-Matcher/apps/frontend/app/(default)/applications/follow-ups/page.tsx>) |
| Existing host tracker | Kanban tracker and application detail dialogs remain in Resume Matcher and have been extended to retain JobHunt source/status data. | [tracker components](../../../Resume-Matcher/Resume-Matcher/apps/frontend/components/tracker), [tracker API client](../../../Resume-Matcher/Resume-Matcher/apps/frontend/lib/api/tracker.ts) |
| Localization | Discovery and tracker strings exist in English, Spanish, French, Japanese, Korean, Brazilian Portuguese, and Chinese. | [frontend messages](../../../Resume-Matcher/Resume-Matcher/apps/frontend/messages) |

## 6. Live-search method and hard limits

The integrated search currently has **one source adapter: Freehire**. Freehire may index postings from multiple employers and boards, but this application queries Freehire’s aggregate index; it does not independently crawl each employer or job board. Listings retain their canonical source URL so the user can continue at the source. [CODE]

The adapter’s bounded implementation includes:

- Up to 30 profile titles per run and up to five configured alternatives per title.
- Up to two skill-query groups, each with up to five terms.
- Up to two semantic seed jobs and up to five similar results for each seed.
- At most three concurrent search requests and a 15-second HTTP timeout.
- Full-text responses capped at 100,000 characters; descriptions shorter than 200 characters are marked partial.
- Local filters for country, city, posting age, and remote preference.
- Deterministic local fit ranking; no resume is sent to Freehire.

The current saved profile has 12 target titles, 25 skills, country AE, city Dubai, a 14-day age window, and remote jobs enabled. [CURRENT]

These are bounded query strategies, not “all available browser search algorithms.” Integrated live search does not launch LinkedIn, Indeed, Jobindex, or other board pages. JobHunt’s portal skills are a separate workflow and are not wired into this API. Search coverage depends on Freehire’s index, metadata, the query groups, and its rate limits. [CODE]

The complete description status is based on the Freehire response text and the local length/truncation checks. It does not prove the text was independently fetched from or compared with the employer’s original page. [CODE]

The [Freehire API reference](https://freehire.me/docs/api) describes public read endpoints as unauthenticated for personal, non-commercial use and rate-limited per address; it says a product offered to others needs an API plan. Current code records source failures but cannot guarantee source availability, freshness, coverage, or continued API terms. [CURRENT]

## 7. Technical stack

| Layer | Current implementation |
|---|---|
| JobHunt standalone | Python standard library for its local HTTP server and SQLite access; HTML, CSS, and browser JavaScript in app/static/index.html; separate portal skills/CLI workflows. The repository’s documented workflow also uses Python, Bun-based portal tools, and LaTeX for CV/cover-letter output. [CODE] |
| Resume Matcher backend | Python 3.13+; FastAPI 0.143; Uvicorn 0.54; Pydantic 2.14; SQLAlchemy async 2.1; SQLite via aiosqlite 0.22; HTTPX 0.28; LiteLLM 1.104; document parsing/rendering libraries including MarkItDown, pdfminer, python-docx, and Playwright. Optional PostgreSQL driver is installed, but PostgreSQL tests were skipped because TEST_DATABASE_URL was not configured. [CODE/RECORDED] |
| Resume Matcher frontend | Next.js 16.4, React 19.3, TypeScript 5, Tailwind CSS 4, Next dev server with Turbopack, Vitest 5, Oxlint/Oxfmt. [CODE] |
| Runtime observed | Python 3.13.5 and Node.js 24.11.1. The backend Uvicorn process uses port 8013; the Next dev server uses port 3013, both bound to loopback. [CURRENT] |
| Persistence | Resume Matcher’s active database is local SQLite. The original JobHunt database is separate; a read-only snapshot is configured for legacy browsing. No hosted database or public deployment is part of this local setup. [CURRENT] |

Pinned backend dependency versions and frontend package versions are listed in [backend pyproject.toml](../../../Resume-Matcher/Resume-Matcher/apps/backend/pyproject.toml) and [frontend package.json](../../../Resume-Matcher/Resume-Matcher/apps/frontend/package.json). The JobHunt architecture baseline is in [jobhunt-architecture.md](../../ai-job-search/docs/jobhunt-architecture.md).

## 8. Local data inventory

Counts below are aggregate metadata only; no resume text, job descriptions, or contact details are reproduced.

| Data set | Current observed state | File / evidence |
|---|---|---|
| JobHunt source database | 244 jobs, two application rows, zero description snapshots; SQLite integrity check ok; SHA-256 56d7b8620bfe12133d749cf6219cc508d746c3d2ae458ccc9a9c6d222d23b3f0. | [jobhunt.db](../../ai-job-search/app/data/jobhunt.db) |
| Read-only JobHunt snapshot | 244 jobs, two application rows, zero description snapshots; integrity ok; SHA-256 1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b. The snapshot is at [jobhunt_snapshot.sqlite](../../stage-c-pilot/jobhunt_snapshot.sqlite). | [stage-c-pilot-report.md](../docs/integration/stage-c-pilot-report.md) |
| Active Resume Matcher database | One resume; two jobs; two application cards; two application events; two discovery-state rows; 107 Freehire listings; one saved search profile; five search runs; zero saved searches; zero outreach drafts; zero tailoring previews; zero JobHunt-to-job link rows. All 107 descriptions report complete; provider is Freehire; SQLite integrity ok; foreign-key violations: zero. | [resume_matcher.db](../../../Resume-Matcher/Resume-Matcher/apps/backend/data/resume_matcher.db), queried read-only |
| Latest search run | Status complete; 106 found, 38 new, zero recorded errors. Started 20 October 2026 12:27:27 UTC and finished 12:27:35 UTC. | jobhunt_search_runs table in the active database |
| Existing final backup | 69 live listings and four search runs; file SHA-256 69921d7cc7d719421283c97a51b163f772e8a5fdfccd109df04c2790a74260aa. Restored copy also passed integrity and foreign-key checks with 69 listings. This backup predates the latest 107-listing state. | [resume_matcher_final_20261020.sqlite](../../backups/resume_matcher_final_20261020.sqlite), [restore rehearsal](../../backups/restore_rehearsal/resume_matcher_restored_final_20261020.sqlite) |
| JobHunt auxiliary local files | job_scraper/seen_jobs.json tracks seen-job state; job_discovery.csv is a separate export/data file. Candidate profile and career-workflow instructions live in CLAUDE.md and .claude/skills/; CV/application documents live under cv/ and documents/. | [JobHunt root](../../ai-job-search), [seen_jobs.json](../../ai-job-search/job_scraper/seen_jobs.json) |

### SQLite/WAL handling

At the current inspection, the active database has resume_matcher.db-wal and resume_matcher.db-shm sidecars; the WAL was about 1.7 MB. Current logical row counts were read through SQLite with WAL support. A hash of the main .db file alone would not represent the full live logical database while uncheckpointed WAL records exist. Use SQLite’s online backup API for a consistent backup; do not treat a raw copy of the live main file as a complete backup. [CURRENT]

The final backup is **stale relative to the active database**: 69 versus 107 listings, and four versus five search runs. Before any further schema/data change, take and verify a fresh online backup of the active database and rehearse restoration. This report did not create or alter a backup. [CURRENT]

## 9. Privacy and external data boundaries

- Search results, descriptions, fit evidence, application state, and resumes are persisted locally in SQLite/files. [CODE]
- Live search necessarily sends profile-derived title/skill query text, location/date/remote filters, and public Freehire job identifiers used for semantic expansion to Freehire. The resume itself is not sent to the search provider. [CODE]
- Resume Matcher has a configurable LLM layer. The code supports OpenAI, Anthropic, OpenRouter, Gemini, DeepSeek, Groq, Ollama/custom endpoints, Claude CLI, ChatGPT, and other configured routes. Its code default is OpenAI with model gpt-5-nano-2025-08-07; a local runtime override may differ. The active provider and endpoint were deliberately not inspected, so do not assume tailoring is offline. [CODE/OPEN]
- Strictly local storage is different from strictly local inference. Verify the provider setting in the app before sending resume or job-description content through tailoring if offline processing is required.
- No credentials or .env values were read into this report.

## 10. Progress and verification status

| Area | State |
|---|---|
| Stage 0 baseline/regression gate | **Open.** TypeScript and focused checks later passed, but full backend/frontend suites did not complete cleanly. |
| C.3 discovery-to-tracker save/skip | **Implemented locally** per execution plan; idempotent save/skip and saved-state behavior are recorded. |
| C.4 descriptions and provenance | **Implemented locally** for API-returned text and manual paste. The 244-row legacy snapshot itself has no descriptions. |
| C.5 direct tailor handoff | **Implemented locally** in the discovery UI/API and reuses existing preview/confirm. Not yet validated as a complete live search-to-export journey. |
| C.6 application workspace | **Implemented locally**: follow-ups, local outreach drafts, and status history with confirmation metadata. |
| C.7 discovery engine | **Implemented locally**: Freehire search expansion, local ranking, persistence, saved-search API, development-only scheduler, and filters. The current database has no saved searches, so no recurring search is enabled. |
| C.8 end-to-end | **Partial.** Browser smoke, restart persistence, and the earlier backup/restore rehearsal passed. The full 11-step journey remains unrun. |

### Verification evidence

**Later focused checks recorded in the execution plan:**

- npm run typecheck passed; a triage run reported 4,282 files with no TypeScript errors in 133 seconds.
- Optimized Next.js production build completed successfully.
- Discovery UI tests: 11 passed; tracker dialog tests: 7 passed; tracker API tests: 7 passed.
- Current focused backend API/import/snapshot/tracker group: 40 passed. Earlier live-search unit/API checks: 10 passed.
- Scoped Ruff checks passed.
- Headless Edge smoke opened /discover/jobs, /tracker, and /applications/follow-ups with HTTP 200 and no JavaScript page errors.
- During this report, the local discovery page returned HTTP 200 (17,388 bytes, 4.52 seconds on retry); the correct local live-jobs API route returned HTTP 200 in about 0.45 seconds.

**Incomplete or failed broad checks:**

- Backend full-suite run: 1,880 passed, 23 failed, 14 errors, 18 skipped, and two deselected in 21 minutes 12 seconds. PostgreSQL-dependent tests were skipped without TEST_DATABASE_URL.
- Frontend full Vitest run did not finish in about 10 minutes. Its first reported file had one failure among 36 tests; one test took about 499 seconds. A later worker run also stalled. Focused UI tests passing do not establish that the full suite passes.
- Full 11-step browser automation was not run.
- Earlier whole-repository lint reported formatting issues in hundreds of existing files; changed-file scoped checks passed.

Details are in the [Stage 0 verification report](../docs/integration/stage-0-verification-report.md), [targeted triage results](../docs/integration/stage-0-targeted-triage-results.md), and [unified execution plan](unified-execution-plan.md).

## 11. Test failures, known causes, and uncertainty

| Finding | Evidence and root-cause assessment |
|---|---|
| Windows environment-variable length failure | Reproduced on both the dirty checkout and pristine comparison. A very long parameterized ATS upload test ID is placed into PYTEST_CURRENT_TEST, exceeding Windows’ 32,767-character environment-variable limit. This is a test-ID/Windows constraint, not evidence of a discovery regression. |
| POSIX file-permission assertions | Reproduced on pristine code on Windows. Tests expect POSIX 0o600 behavior but observe Windows permission semantics. These assertions are not portable as written. |
| AI operation deadline candidate | One variant, test_parse_deadline_marks_only_owned_processing_attempt_failed[retry-False], failed only in the dirty targeted run because the expected event was not set before the 0.2-second deadline; logged operation time was about 0.471 seconds. Related variants also failed on pristine code. Treat this as a timing-sensitive candidate regression until independently reproduced with a meaningful timeout and isolated load. |
| Cookie API mismatch | test_tampered_session_is_rejected raised TypeError because installed httpx.Cookies.set() does not accept secure=. The test is absent at the selected merge base, so the comparison cannot attribute its introduction to the migration. |
| Upload-recovery rows missing | An upload recovery test expected a committed resume row and found none on both dirty and pristine comparisons. The exact cause remains unresolved. |
| PDF/Playwright and frontend worker stalls | The full backend triage timed out after 2,403 seconds with a Playwright driver still active. The frontend worker also stalled, including a test taking about 499 seconds. The precise cause of each stall is not established. |
| The reported 90-minute Codex command | No per-process trace for that specific command is available, so its full duration cannot be assigned to one root cause. Long-running Playwright/Vitest work and low available RAM are plausible contributors, not proven causes. |
| Database migration rule divergence | Current db_engine.py contains SQLite table-rebuild functions that create replacement jobs/applications tables, copy rows, drop the old tables, and rename the replacements. The code includes transaction, row-count, and foreign-key checks, but this is not strictly additive and conflicts with the plan’s additive-only requirement. The current live database passed integrity/FK checks; this does not remove the need for a fresh backup and migration review. |

The targeted comparison recorded 159 passed / 7 failed / 2 errors on the dirty checkout versus 83 passed / 5 failed / 2 errors on the pristine selected-file baseline. One dirty-only AI-budget result remains a candidate; the other listed failures reproduced on the baseline or could not be attributed. See the [triage summary](../docs/integration/stage-0-targeted-triage-results.md).

## 12. Resource snapshot

Measured 20 October 2026 at **18:36:21 +05:30**, over a two-second sample. This is a point-in-time development-server observation, not a benchmark of a full test run.

| Process in the local app tree | Resident working set | Private memory | CPU used during 2-second sample |
|---|---:|---:|---:|
| Python Uvicorn backend, PID 25408 | 10.6 MiB | 647.4 MiB | 0.016 s |
| Next dev runner, PID 33860 | <0.1 MiB | 66.5 MiB | 0.000 s |
| Next server, PID 7604 | 136.5 MiB | 529.2 MiB | 0.484 s |
| Turbopack worker, PID 28384 | <0.1 MiB | 94.9 MiB | 0.000 s |
| **App process group total** | **147.1 MiB** | **1,338.0 MiB** | **0.500 s** |

The Windows host reported 7.69 GiB visible RAM, 0.69 GiB free, and 12 logical processors at that time. App-process CPU was about 2.08% of the host’s 12-logical-processor capacity during the sample (0.500 CPU-seconds / 2 seconds / 12 processors). Working set is resident RAM; private memory includes committed private pages and is not equivalent to resident RAM. The near-zero working set for two processes indicates their pages were not resident at the instant sampled; it should not be read as zero allocated memory.

The low free-memory figure is evidence of memory pressure at the capture time. It cannot by itself explain the earlier 90-minute command or establish an average CPU/RAM requirement. Other host processes are excluded from the app process totals. [CURRENT]

## 13. Important technical limitations

1. **One integrated search source.** Live discovery uses Freehire’s index, not direct browser crawling of every job board. The JobHunt portal skills are not integrated into the Resume Matcher search API.
2. **Source freshness and completeness are upstream-dependent.** Freehire’s records, source links, job availability, metadata, and rate limits can change. “Complete” is a local response-length/truncation judgment, not external validation against the employer page.
3. **Heuristic score only.** Fit ranking is deterministic keyword/field weighting. It is not an ATS score, semantic resume evaluation, or hiring probability.
4. **Scheduler scope.** The scheduler only starts in development mode and only processes saved searches that are enabled and due. There are currently zero saved searches. It does not run while the application is closed.
5. **Local app is not offline.** Freehire search requires network access. AI tailoring may use a remote provider according to runtime configuration.
6. **Database upgrade safety.** Existing jobs and applications tables are rebuilt by startup migration code in SQLite when their schema needs the new fields. It checks row counts and FKs, but the operation diverges from the additive-only plan and must be backed up/reviewed before future changes.
7. **Backup is behind active data.** The final verified backup has 69 live listings; the active database has 107 and has WAL sidecars. The existing backup/restore rehearsal does not cover the current logical database state.
8. **End-to-end quality gate is open.** A full search → save → description → select resume → tailor → preview/edit → export → tracker journey has not been demonstrated with a real live result.
9. **Windows test portability and duration.** Some tests assume POSIX permissions, long test IDs exceed Windows environment limits, and browser/test workers have stalled. Full regression status is unresolved.
10. **Legacy descriptions are missing.** The read-only JobHunt snapshot has 244 listings but no description snapshots. Those entries need a manual description or a successful supported retrieval before normal tailoring.

## 14. Recommended next actions

1. Create a fresh SQLite online backup of the active database, verify integrity and foreign keys, and rehearse restore; record the 107-listing state before any migration or schema work.
2. Review db_engine.py rebuild behavior against the plan’s additive-only constraint. Decide whether the migration should remain as-is or be replaced with a safer explicitly versioned migration before further schema changes.
3. Run and record the full 11-step workflow against one real live listing, including source URL, description status, selected resume, tailor preview, export, and saved tracker status.
4. Reconcile the execution plan with current database counts (107 listings, five runs, latest 106 found/38 new) and the backup discrepancy.
5. Finish the backend/frontend regression gates. Isolate the 0.2-second AI-budget test and separately address the Windows-only test failures; do not treat focused green tests as a full-suite pass.
6. Check the app’s active LLM provider configuration before tailoring if the requirement is offline inference rather than local file/database storage.
7. If broader source coverage is needed, add permitted provider adapters one at a time and verify each source’s terms, availability, rate limits, and original links. Do not describe the current Freehire adapter as a universal web search.

## 15. Primary inspection files

| Topic | Files |
|---|---|
| Current implementation plan and stage state | [unified-execution-plan.md](unified-execution-plan.md), [Stage 0 verification](../docs/integration/stage-0-verification-report.md), [Stage 0 triage](../docs/integration/stage-0-targeted-triage-results.md) |
| JobHunt behavior and local architecture | [README.md](../../ai-job-search/README.md), [AGENTS.md](../../ai-job-search/AGENTS.md), [app/server.py](../../ai-job-search/app/server.py), [app/core.py](../../ai-job-search/app/core.py), [jobhunt-architecture.md](../../ai-job-search/docs/jobhunt-architecture.md) |
| Resume Matcher backend configuration and schema | [pyproject.toml](../../../Resume-Matcher/Resume-Matcher/apps/backend/pyproject.toml), [config.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/config.py), [main.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/main.py), [db_engine.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/db_engine.py), [models.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/models.py), [database.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/database.py) |
| Discovery engine, API, and persistence | [jobhunt_live_search.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/services/jobhunt_live_search.py), [jobhunt_discovery.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/jobhunt_discovery.py), [jobhunt_scheduler.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/services/jobhunt_scheduler.py), [jobhunt_snapshot.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/services/jobhunt_snapshot.py), [jobhunt_import.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/services/jobhunt_import.py) |
| Tracker, applications, and resume handoff | [applications.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/applications.py), [resumes.py](../../../Resume-Matcher/Resume-Matcher/apps/backend/app/routers/resumes.py), [tracker components](../../../Resume-Matcher/Resume-Matcher/apps/frontend/components/tracker), [discovery components](../../../Resume-Matcher/Resume-Matcher/apps/frontend/components/discovery), [tailor page](<../../../Resume-Matcher/Resume-Matcher/apps/frontend/app/(default)/tailor/page.tsx>) |
| Focused tests | [backend tests](../../../Resume-Matcher/Resume-Matcher/apps/backend/tests), [frontend tests](../../../Resume-Matcher/Resume-Matcher/apps/frontend/tests) |

**Inspection note:** This is a dated state report. Job postings, provider limits, search history, saved searches, process memory, CPU use, and WAL size can change. Recheck those facts before using them for a later migration or performance decision.
