# Stage 0 — Targeted Backend Triage Results

Date: 2026-10-20. Comparison base: `ff5b370372d39b6cb6b56fd0dad88a2fe5c3abce` (`origin/main` merge base).

## Full-suite attempt

The clean-copy triage runner's full dirty-copy backend pass did not finish. It timed out at 2,403 seconds while a Playwright driver remained active; no `dirty.json` was written, so the pristine comparison did not run. I fixed the runner's base export to extract from a completed tar file instead of a streaming pipe, which had blocked on Windows. No host application source was changed by that fix.

## Targeted non-browser comparison

The targeted run covered AI operation budgets, ATS parsing, auth, CLI, confirmation transactions, upload enhancement recovery, crypto, and e2e monitor collection.

| Copy | Passed | Failed | Errors | Duration |
|---|---:|---:|---:|---:|
| Current branch plus uncommitted changes | 159 | 7 | 2 | 294 s |
| Pristine merge base, same failing files | 83 | 5 | 2 | 119 s |

The snapshot SHA-256 was unchanged. The runner reported no inherited Settings environment variables to scrub.

### Candidate regression

- `tests/integration/test_ai_operation_budgets.py::test_parse_deadline_marks_only_owned_processing_attempt_failed[retry-False]` failed only in the dirty copy: its `entered` event was still unset at the assertion. The closely related `[none-False]` and `[delete-False]` variants failed on both copies. Treat the single dirty-only variant as a candidate regression or timing-sensitive result; rerun it in isolation before attributing it to the C.3 edits.

### Reproduced on pristine baseline

- The related AI operation budget variants above also failed on pristine.
- A parameterized ATS upload rejection with a very long filename raised `ValueError: the environment variable is longer than 32767 characters` while pytest set `PYTEST_CURRENT_TEST`; this is a Windows environment-variable length limit triggered by the test ID.
- An upload enhancement recovery test expected one resume row but found none, on both copies.
- File mode assertions expected POSIX `0o600` (`384`) but observed `438` on Windows, in crypto and e2e monitor tests.

### New relative to the comparison base

- `tests/integration/test_auth.py::test_tampered_session_is_rejected` failed with `TypeError: Cookies.set() got an unexpected keyword argument 'secure'`. The test is absent at the selected merge base, so the runner labels it `NEW-TEST`; this does not establish whether it was newly added in the uncommitted work or an intervening branch commit.

## Limits and next gate

This targeted comparison does not account for the PDF/Playwright failures from the full suite, and the dirty-only candidate has not yet been independently rerun. The full triage report is at `D:\AI-Job\stage-c-pilot\triage-targeted-20261020-030000\triage-report.md`; its ATS parameterized test ID is exceptionally long, so this summary is easier to review.

Stage 0 remains incomplete: frontend tests were not completed, and the full backend triage stalled in Playwright. The local TypeScript check itself completed successfully with 4,282 files and no errors in 133 seconds. Do not begin C.3 implementation until the remaining Stage 0 gates and the existing C.3 working-tree diff are reconciled.
