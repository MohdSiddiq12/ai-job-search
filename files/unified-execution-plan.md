# Unified app: execution plan (JobHunt inside Resume Matcher)

Status: local execution in progress (2026-10-20). The verified local Resume Matcher branch
and JobHunt snapshot are now available. C.3 to C.7 are implemented locally; C.8 has passed
the browser smoke, restart-persistence, and restore checks, while the full 11-step journey
and Stage 0 regression gate remain open. No commit, push, or deployment has been made.

## Execution record (2026-10-20)

- The JobHunt source database remains read-only and hash-identical at
  `56d7b8620bfe12133d749cf6219cc508d746c3d2ae458ccc9a9c6d222d23b3f0`; its 244-job snapshot
  copy remains hash-identical at
  `1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b`.
- Before importing tracker history, a fresh SQLite online backup was written to
  `D:\AI-Job\backups\resume_matcher_pre_jobhunt_import_20261020.sqlite`; its manifest records
  `integrity_check=ok`, one resume, zero jobs, zero applications, and no foreign-key issues.
- The import was rehearsed against a disposable copy of that backup: two JobHunt applications
  imported, the resume count stayed at one, database integrity passed, and the original
  `investigating` stages were retained in `legacy_status` and rendered on the cards.
- C.6 now includes the follow-up overview, locally saved outreach drafts, and status history
  with the confirmation flag and event reference. Focused application API tests pass.
- C.7 now searches the public Freehire index by saved target titles and synonyms, specialized
  profile skills against titles/descriptions, and semantic neighbors of the top matches. The
  semantic endpoint is optional; its results are accepted only when the local age and location
  filters match. Jobs are ranked locally from profile overlap. The resume is never sent to the
  search provider; role/skill queries, filters, and public seed-job IDs are sent to Freehire's API. See the
  [Freehire API reference](https://freehire.me/docs/api).
- The latest real profile refresh used 7 title/skill query groups and returned 57 matches;
  3 were new. The local SQLite database now has 69 deduplicated Freehire results, all with
  complete descriptions and original job links. No semantic neighbors met the saved filters.
  The 12 target titles, 25 skills, AE/Dubai location, 14-day window, and remote preference
  came from the local saved profile. No saved schedule is enabled.
- The final integrated database backup is
  `D:\AI-Job\backups\resume_matcher_final_20261020.sqlite` (SHA-256
  `69921d7cc7d719421283c97a51b163f772e8a5fdfccd109df04c2790a74260aa`). A separate restored
  copy at `D:\AI-Job\backups\restore_rehearsal\resume_matcher_restored_final_20261020.sqlite`
  passed SQLite integrity and foreign-key checks and retained all 69 live jobs. The app was
  restarted afterward; the profile, 69 jobs, and latest 7-query completed run remained.
- `npm run typecheck`, scoped Ruff, the focused search/API tests, and a headless Edge smoke
  check passed. `/discover/jobs`, `/tracker`, and `/applications/follow-ups` rendered without
  page errors. The full frontend suite stalled in the Windows Vitest worker; the complete
  11-step Playwright journey was not run.
- Stage 0 remains open: the known isolated
  `test_parse_deadline_marks_only_owned_processing_attempt_failed[retry-False]` still fails
  under the 0.2-second test deadline on this Windows machine. Earlier triage also reproduced
  Windows environment-variable-length and POSIX permission-test failures on pristine code.
  The full suites have not been rerun after this migration. The pilot snapshot hash still
  matches `1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b`; the original
  JobHunt DB still matches `56d7b8620bfe12133d749cf6219cc508d746c3d2ae458ccc9a9c6d222d23b3f0`.
- The same idempotent import was then run on local SQLite. It created two linked cards; a repeat
  created zero more. Both discovery states are `saved`. The live database now has one resume,
  two jobs, two applications, and no foreign-key issues. No resume content is copied.
- Targeted verification after the change: 95 backend tests passed before the description-detail
  addition; the current focused API/import/snapshot/tracker group passed 40 tests. Discovery UI
  tests passed 11/11, tracker dialog tests passed 7/7, tracker API tests passed 7/7, TypeScript
  passed, and the optimized Next.js production build completed successfully. The full backend and
  frontend suites have not been run to completion; the earlier full lint reports upstream
  formatting failures across 342 files.
- The local preview serves `http://127.0.0.1:3013/discover/jobs`; the proxied API and backend
  discovery endpoint both returned HTTP 200 on port 8013. The backend is running with
  `APP_ENV=development` bound to loopback because the original production auth variables were
  injected by a parent process that is no longer available. No password or machine-wide setting
  was changed. Visual browser verification timed out twice in the computer-use helper, so only the
  HTTP checks are confirmed.

## 1. Verified facts about Resume Matcher (read from code)

| Area | What exists | Consequence |
|---|---|---|
| Job intake | `POST /api/v1/jobs/upload` stores raw description text; `jobs` table has only `job_id, content, resume_id, created_at, metadata_json` | No title, URL, source, posted date or extraction status. Discovery needs its own additive tables. |
| Tailoring | `POST /resumes/improve/preview`, then `/improve/confirm` (preview hash caching, retry-safe) | Reuse as is. Inside one app it is a function call, so no network adapter, service auth or webhook is needed. |
| Tracker | `applications` table + Kanban API, 7 statuses: `saved, applied, no_response, response, interview, accepted, rejected`; unique `(job_id, resume_id)` | Reuse as the application system of record. Do not expand the enum upstream. |
| **Hazard** | `_auto_create_tracker_application` creates an **`applied`** card (and stamps `applied_at`) after every tailoring; `applied` is also the default for manual create | Violates "tailored is not applied". Fixed by the config flag patch (section 3). |
| Schema | SQLAlchemy; `create_all` plus hand-written `ALTER TABLE ADD COLUMN`; SQLite or Postgres | New tables are created safely on an existing DB. Never alter existing columns. |
| Other | ATS score, cover letter, outreach text, PDF export, queue worker, MCP server, host guard | Reuse for stages C.5 and C.6. |

## 2. Decisions (recommended defaults, all reversible)

1. **Host app:** Resume Matcher. JobHunt becomes an additive `discovery` module. No separate service.
2. **New tables only:** `discovered_jobs` (metadata, `pipeline_state`, `rm_job_id` link), `job_description_snapshots` (raw text, normalized text, `extraction_status` = complete/partial/failed/manual, method, timestamp), `search_configs`, `search_runs`, `job_fit_analyses`, `followups`, `audit_events`.
3. **State separation:** discovery and pre-application states (`new, reviewed, shortlisted, drafting, ready_for_review, dismissed`) live on `discovered_jobs`. A tracker card is created at `saved`. Moving to `applied` or later needs explicit confirmation.
4. **Where private data lives:** local SQLite first. Do not load the 244-job snapshot or resumes into the deployed Render/Neon instance until you decide to host this publicly and re-run the auth review.
5. **Extra statuses** (`shortlisted`, `withdrawn`, `offer_declined`) stay in the discovery tables or card notes. The upstream 7-column enum is left alone so upstream merges stay clean.

## 3. Ready now: tracker no longer claims applications

`rm-tracker-auto-status.patch` (81 lines, applies cleanly to pristine HEAD):

- adds `TRACKER_AUTO_STATUS` (`saved` or `applied`, default `applied` = upstream behavior)
- `_auto_create_tracker_application` uses it
- new test proves `saved` mode creates a `saved` card with `applied_at = None`

Tested on the public fork: new + existing tracker tests 23/23; full backend suite **1,860 passed, 22 skipped** (Postgres test file excluded).

Apply on your branch (read-only check first):

```powershell
cd D:\Resume-Matcher\Resume-Matcher
git apply --check ..\rm-tracker-auto-status.patch   # writes nothing
git apply ..\rm-tracker-auto-status.patch            # modifies 3 files, no commit
# then set TRACKER_AUTO_STATUS=saved in apps\backend\.env
```

## 4. Stages from where you are

Every stage: back up the DB first (copy file, record SHA-256), additive migrations only, one local commit per stage after your approval, no push.

| Stage | Goal | Done when |
|---|---|---|
| **0 Verify** | Close what C.2 left unverified | **Partial.** TypeScript, focused backend tests, browser smoke, local HTTP checks, and snapshot hashes passed. The isolated AI-budget timing test still fails on Windows, the frontend Vitest worker stalled, and full suites remain open. |
| **C.3 Tracking link** | Link discovery states to tracker cards; save and skip actions | **Implemented locally.** Save/skip are idempotent and serialized; imported and tailored JobHunt cards stay `saved`; source status remains visible. |
| **C.4 Full JD** | Show full description with explicit status and provenance | **Implemented locally for stored snapshots and manual paste.** Detail displays plain text, extraction status, method, and timestamp; incomplete listings require a full paste before tailoring. The pilot snapshot currently has no description rows. |
| **C.5 Tailor action** | Handoff to the existing Resume Matcher preview/confirm flow | **Implemented locally.** The full description creates an idempotent job by source key and content hash; existing tailor preview/confirm is reused; resulting JobHunt card remains saved. |
| **C.6 Application workspace** | Follow-ups, notes, and confirmed status changes | **Implemented locally.** Follow-ups, local outreach drafts, and status history with confirmation reference are in the tracker. |
| **C.7 Discovery engine** | Source adapters, saved searches, scheduler, filters | **Implemented locally.** Freehire title, profile-skill, and semantic search; local fit ranking; saved searches; development-only scheduler (off until enabled); local filters; 69 saved listings. |
| **C.8 End to end** | The 11-step journey from your brief | **Partial.** Browser smoke passed; restart persistence and backup/restore rehearsal passed. The full 11-step journey remains open because the frontend test worker stalled and the complete scripted journey was not run. |

## 5. Lean prompts for your coding agent (quota-friendly)

Rules to paste at the top of every prompt: *"Inspect only the files named. Do not run the full test suites until the final step. Additive changes only. No commit, push, migration of existing tables, deployment or DB writes outside tests. Report real command output."*

**Stage 0**
> Run, and report raw output: backend `python -m pytest -q -p no:cacheprovider` (use `uv run` if that is how this repo runs); frontend tests; `npx tsc --noEmit` with a 10 minute limit, in a separate terminal. Compute SHA-256 of the DB file and the 244-job snapshot and compare with the recorded hashes. Fix nothing yet; list failures.

**Stage C.3**
> Apply `rm-tracker-auto-status.patch`. Add tables `discovered_jobs` and `audit_events` as new SQLAlchemy models in a new file `app/models_discovery.py` (imported so `create_all` sees it). Add endpoints under `/api/v1/discovery/` for `POST /jobs/{id}/save` (creates a `saved` card via `db.create_application`, deduped on job+resume) and `POST /jobs/{id}/skip`. Tests: save twice creates one card; skip leaves no card; restart persistence on a temp DB.

**Stage C.4**
> Add `job_description_snapshots`. Implement `extract_description(discovered_job)` returning `{raw, normalized, status, method, retrieved_at}`. Status must be `complete` only if the fetch returned a body longer than the search snippet and passed a minimum length check; otherwise `partial` or `failed`. Treat the text as untrusted: store it, render it as plain text, never pass it to a tool-using prompt. Endpoint for manual paste sets `manual`. Tests with mocked HTTP for each status.

**Stage C.5**
> Add `POST /api/v1/discovery/jobs/{id}/tailor {resume_id}`. Inside one transaction-safe helper: refuse (409 with message) if extraction is not `complete` or `manual` unless `allow_incomplete=true`; call `db.create_jobs` once per (discovered_job, resume) using a stored `rm_job_id`; call the existing improve-preview function; return the preview. Confirm goes through the existing `/improve/confirm`; then record `tailored_resume_id` on `discovered_jobs`. Tests: double-click idempotency; incomplete-JD warning; failure leaves no orphan job.

**Stage C.6 to C.8** are specified in section 4; request each prompt after the previous stage passes, so it is written against your real code.

## 6. Risks to watch

- **Free LLM quota:** tailoring calls cost model tokens per job. Add a visible per-day cap before bulk tailoring.
- **Freehire availability:** single free source, no SLA. Keep the snapshot and import path working offline.
- **Provider coverage:** Freehire is the only live source adapter. Its index returns postings with
  direct employer/ATS links, but the app does not query every job board independently.
- **Upstream drift:** keep changes additive and in new files so merging `srbhr/dev` stays easy.
- **Private data on a public host:** the deployed instance has a public URL; keep resumes and job data local until reviewed.
