# Stage B — baseline results

Date: 2026-10-19. Commands ran without resetting databases, installing packages, or editing application source.

## Repository state

- JobHunt: `D:\AI-Job\ai-job-search`, branch `master`, origin `https://github.com/MohdSiddiq12/ai-job-search.git`. Existing untracked paths remain `.opencode/`, `app/`, `docs/`, `files.zip`, and the three app test files. Preserved.
- Resume Matcher: `D:\Resume-Matcher\Resume-Matcher`, branch `deployment-hardening`, origin `https://github.com/MohdSiddiq12/Resume-Matcher.git`; clean worktree.
- All six Stage A audit documents exist. Their older JobHunt count of one application was a prior snapshot; current read-only count is two.

## JobHunt suite and data

Command: `python -m unittest discover -s tests -v`

Result: **681 tests, 11 failures, 1 error, 24 skipped** (exit 1). Failures/errors occur in reset command/document tests invoking WSL `bash`; Windows reports `/bin/bash` cannot be started. These are environment-dependent reset/symlink checks. The targeted command `python -m unittest tests.test_app_core tests.test_app_server tests.test_resume_matcher_adapter -v` passes **24 tests**.

SQLite was read with URI `mode=ro` on `app/data/jobhunt.db`. Tables include jobs, applications, events, searches, runs, description snapshots and tailoring requests. Counts: 244 jobs, 2 applications, 6 events, 2 searches, 2 runs, 0 description snapshots and 0 tailoring requests. No row or DB file was changed by this check. These are point-in-time counts and can change as the app is used.

## Resume Matcher backend

Relevant files: `apps/backend/pyproject.toml`, `apps/backend/uv.lock`, `apps/backend/requirements.txt`. Python requirement is 3.13+; the checkout has a project `.venv`, but `pytest` is absent there. `pytest>=8` and `pytest-asyncio` are in the optional `dev` group; `uv.lock` contains pytest packages.

Command attempted: `uv run --directory D:\Resume-Matcher\Resume-Matcher\apps\backend pytest -q`

Initial result: could not spawn `pytest` (“program not found”). With user approval, `uv sync --extra dev` completed in the existing project `.venv` and installed the locked dev tools (`pytest`, `pytest-asyncio`, `respx`, `ruff` and support dependencies). No global install occurred.

Command then run: `uv run pytest -q`. It collected 1,914 cases (2 deselected by repository config), but the full run was interrupted while at `tests/integration/test_pdf_grid_geometry.py` (about 28%). Before interruption, visible failures included 2 errors in `test_ats_parse_api.py`, 1 failure in `test_auth.py`, 2 failures in `test_llm_contract.py`, and a failure in `test_pdf_lifecycle.py`. The process tree showed pytest waiting on a Playwright Node child with no browser child; there was no visible progress in this PDF test for several minutes. Exact final counts and tracebacks are unavailable; this is incomplete, not a pass. Follow up by verifying Chromium setup, rerunning focused failing files, then the full suite.

Focused follow-up: `uv run pytest tests/integration/test_ats_parse_api.py -q --tb=short` — **14 passed, 2 errors** in 39.60 seconds. The emitted traceback was dominated by repeated parameterized input in test IDs and exceeded the tool’s safe output limit; the concise exception cause was not recovered. Do not guess the cause; rerun with locally captured and sanitized pytest output before Stage C.

## Resume Matcher frontend

Package manager: npm; `apps/frontend/package-lock.json`; scripts in `package.json`; Vitest/jsdom in `vitest.config.ts`. Existing `node_modules` was used; observed versions: Node v24.11.1, npm 11.6.2.

Command: `npm run test -- --run`. The full run continued without final output for several minutes and was manually interrupted. It had reported `Hero > runs the effect from the Launch CTA only` as a failure. Focused command `npm run test -- tests/block-dissolve-transition.test.tsx -t 'runs the effect from the Launch CTA only'` reproduced it (36 tests skipped): `tests/block-dissolve-transition.test.tsx:517` destructures three links (`github`, `docs`, `launch`), while `components/home/hero.tsx` renders two links (docs and launch), leaving `github` undefined. This is a test/implementation expectation mismatch in the clean source checkout; neither was changed.

The full run was not proven hung; it was stopped after limited visible progress. A complete all-suite result needs a longer run with a reporter that emits progress. Existing npm dependencies meant no install was needed.

## Environment changes

No tracked application source/dependency files were changed in Resume Matcher; its project-local ignored `.venv` now has the approved dev test dependencies. A new JobHunt branch/worktree was created as approved; selected app/tests/docs/helper files are untracked there for review. No backup or migration was performed. Test temp fixtures are managed by the suites.
