# Source audit — JobHunt and Resume Matcher

Audit date: 2026-10-19. Read-only inspection; no code, dependency, database, remote, or branch changes were made.

## Repository state

| Repository | Branch | Origin | Worktree |
|---|---|---|---|
| JobHunt (`D:\AI-Job\ai-job-search`) | `master` | `https://github.com/MohdSiddiq12/ai-job-search.git` (public fork) | Existing untracked `.opencode/`, `app/`, `docs/`, `files.zip`, and app tests; preserved |
| Resume Matcher (`D:\Resume-Matcher\Resume-Matcher`) | `deployment-hardening` | `https://github.com/MohdSiddiq12/Resume-Matcher.git` | Clean |

No personal resume text, API key, credential, or environment value was copied into this report. No database file was opened for content inspection.

## JobHunt

- Entrypoint: `app/server.py`; static single-page UI: `app/static/index.html`; domain/persistence logic: `app/core.py`.
- Python standard library HTTP server, loopback binding, SQLite. Existing local database is under ignored `app/data/`.
- Current UI routes: Overview, Jobs, Applications, Searches, Profile, Runs. Job detail exposes description history, status/feedback, application follow-up, tailoring handoff and export.
- Core data separates discovered jobs from applications; additive SQLite schema includes job descriptions, application events, tailoring requests/results. Existing data at the previous audit was 244 jobs and one application; no current row counts were queried in this audit.
- Discovery calls the pre-existing Freehire helpers. Matcher adapter is `app/integrations/resume_matcher.py`, currently an explicit `NotConfiguredAdapter`; it does not make HTTP requests.
- No user authentication; the intended threat boundary is a local single-user loopback server. Host and Origin checks exist. Do not expose it publicly as-is.

## Resume Matcher

- Backend: FastAPI in `apps/backend/app/main.py`, routers under `apps/backend/app/routers/`, service and prompt modules under `services/` and `prompts/`.
- Frontend: Next.js 16 / React 19 app in `apps/frontend/app/`, reusable UI under `components/`, API clients under `lib/`; Swiss International design tokens are in `app/(default)/css/globals.css`.
- Persistence: SQLAlchemy async SQLite by default, PostgreSQL optional, with additive startup migration from legacy TinyDB. Models include resumes, jobs, improvements, tailoring previews, applications, encrypted API keys, and queue items. User content/config is local and ignored.
- Authentication: single configured password in hosted mode; password checked with scrypt; HMAC-signed `rm_session` and CSRF cookies; origin restriction; five attempts per 15 minutes. Sessions and throttling are in process memory. Development mode bypasses auth. This is not a user/account identity system and not a safe server-to-server integration contract.
- API families registered in `main.py`: health/status, auth, config, resumes, jobs, enrichment, applications, resume wizard, ATS parsing, ChatGPT connection/callback. Resume/job/ATS APIs are real FastAPI handlers, not just UI placeholders.
- AI providers flow through LiteLLM/configured provider keys; agent mode supports human-agent workflows without the app itself making model calls. Provider accounts, quotas, and pricing still apply. No free inference entitlement is established by source openness.
- File processing accepts supported resume formats, parses them, renders PDFs with Playwright/Chromium, and keeps structured resume versions in the database. The source includes upload/type/size and parser safeguards; combined-host auth and storage still need dedicated review.

## Baseline evidence

- JobHunt targeted app suite: `python -m unittest tests.test_app_core tests.test_app_server tests.test_resume_matcher_adapter -v` — 24 passed.
- Resume Matcher backend: `uv run --directory apps/backend pytest -q` could not start because the environment did not have the `pytest` executable available to that environment. No packages were installed.
- Resume Matcher frontend: the full Vitest run did not complete within the observed run window and was interrupted. It reported one failure in `tests/block-dissolve-transition.test.tsx` (`Hero > runs the effect from the Launch CTA only`); a focused rerun reproduced it because the test expected a third link but received `undefined` (`launch`), at line 517. This is pre-existing source/test behavior, not caused by this audit.
- Full JobHunt suite previously ran 681 tests: 12 reset-related failures/errors due to WSL `/bin/bash` unavailable on this Windows host, 24 skipped; the app-specific suite passed. This is historical baseline evidence from `docs/jobhunt-architecture.md`, not a new full-suite run for this audit.

## Limits

This audit establishes source structure and key boundaries. It is not an exhaustive security review, visual QA, or proof that every provider/upload/export path works. Neither project was modified, and no integration behavior is claimed.
