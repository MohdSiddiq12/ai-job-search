# Test strategy for incremental integration

Date: 2026-10-19. Use these gates per small slice. Commands run from the stated repository roots. Durations are recorded only where observed; do not infer a duration for other tiers.

## Tier 1 — fast logic and application smoke

JobHunt application and adapter tests, from `D:\AI-Job\ai-job-search-integration`:

```powershell
python -m unittest tests.test_app_core tests.test_app_server tests.test_resume_matcher_adapter -v
```

Observed: 24 passed (reverified during Stage B.1). This uses the copied app tests and does not require the original live DB.

Resume Matcher focused ATS, selection, and unit checks, from `D:\Resume-Matcher\Resume-Matcher\apps\backend`:

```powershell
uv run pytest tests/unit/test_ats.py tests/unit/test_ats_parse.py tests/unit/test_tailor_selection.py -q
```

The repository config excludes `eval` by default. For a quick frontend check from `D:\Resume-Matcher\Resume-Matcher\apps\frontend`:

```powershell
npm run test -- tests/block-dissolve-transition.test.tsx -t 'runs the effect from the Launch CTA only'
```

This focused Hero check currently fails due to the test's stale three-link assumption; keep it visible until corrected and verified. Do not interpret a red test as an app regression without examining the assertion/component pair.

## Tier 2 — bounded API/service/database smoke

From `D:\Resume-Matcher\Resume-Matcher\apps\backend`:

```powershell
uv run pytest tests/integration/test_applications_api.py tests/integration/test_health_api.py tests/integration/test_jobs_api.py -q --tb=short
```

For the currently verified broader smoke, including unit/ATS and mocked PDF lifecycle coverage:

```powershell
uv run pytest tests/unit/test_ats.py tests/unit/test_ats_parse.py tests/unit/test_tailor_selection.py tests/integration/test_applications_api.py tests/integration/test_health_api.py tests/integration/test_jobs_api.py tests/integration/test_pdf_lifecycle.py -k 'not disconnected_cached_browser_is_replaced_automatically and not simultaneous_recovery_callers_install_one_browser and not uploads' -q --tb=short
```

Observed: 197 passed, 2 deselected, 48.96 seconds. These API tests use the test configuration and isolated test database fixtures; verify `tests/conftest.py` before adding any command that changes test selection. No command in this tier should point to a user database. The broad smoke excludes the browser-dependent lifecycle cases and upload-named ATS cases, whose setup currently has platform issues.

## Tier 3 — browser, PDF, external/resource-heavy

Run these deliberately, separately, with a strict timeout and process-tree cleanup:

```powershell
uv run pytest tests/integration/test_pdf_lifecycle.py -q --tb=short
uv run pytest tests/integration/test_pdf_grid_geometry.py -q --tb=short
```

Prerequisites: Playwright 1.63.0, a usable browser (test helper supports Playwright Chromium and can fall back to installed Chrome/Edge), and `pdftoppm` for raster-based checks when invoked. The geometry test performs a 16-render page/style matrix. The previous all-suite run stopped progressing in this area with a Playwright Node process but no browser child. That is unresolved; do not repeat the entire backend suite. No browser was downloaded in Stage B.1.

Frontend complete run, from `apps/frontend`, only after a progress reporter/time budget is chosen:

```powershell
npm run test -- --run
```

The previous full Vitest attempt was interrupted and has no complete result. The focused Hero failure is known and recorded above.

## Environment-dependent reset gate

JobHunt reset tests require an operational WSL `/bin/bash` in the current test implementation. Safe targeted command from the integration worktree:

```powershell
python -m unittest tests.test_reset_command tests.test_reset_documents -v
```

It uses temporary fixtures but currently fails because Windows locates a WSL shim whose Linux Bash cannot launch. Do not aim it at the real `app/data/jobhunt.db`. Run only after the Bash environment is fixed or the tests gain a supported Windows runner.

## General rules

- Keep `-m not eval` (repository default) for routine tests; evals may contact a real model and are not a free deterministic smoke gate.
- Run one bounded tier at a time and record exact command, count, duration, and skips/deselections.
- Treat tokenizer/cache, browser, and platform setup as explicit prerequisites. Never enable external API traffic to make a mocked test pass.
- Use disposable DB copies and assert read-only boundaries for the first integration slice.
