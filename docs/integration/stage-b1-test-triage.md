# Stage B.1 — Test triage

Date: 2026-10-19. This report supplements, and does not replace, `stage-b-baseline-results.md`. No source, test, database, or production data was changed.

## State and scope

- Integration checkout: `D:\AI-Job\ai-job-search-integration`, branch `integration/resume-matcher-foundation`.
- Original JobHunt checkout remains `D:\AI-Job\ai-job-search`, branch `master`.
- Resume Matcher remains `D:\Resume-Matcher\Resume-Matcher`, branch `deployment-hardening`.
- Integration worktree contains only the previously copied, untracked Stage B app/docs/tests/helper content; no feature integration implementation is present. Its status was inspected; the existing untracked files were preserved.
- The Stage B full-suite baseline remains 681 tests, 11 failures, 1 error, 24 skipped. A safe focused rerun below has a different failure/error split because failed WSL child startup also causes temporary-directory cleanup errors; it does not replace the historical baseline.

## JobHunt

Reverified command from the integration worktree: `python -m unittest tests.test_app_core tests.test_app_server tests.test_resume_matcher_adapter -v` — **24 passed**.

Safe targeted reproduction: `python -m unittest tests.test_reset_command tests.test_reset_documents -v` — 13 test cases/subtests, 10 failures and 2 errors in this Windows environment. Every observed test failure starts with inability to launch `/bin/bash` (`execvpe /bin/bash failed 2`). A subset then reports Windows temporary-directory cleanup errors (WinError 32/5) after the WSL shim fails to start. `shutil.which('bash')` finds a WSL shim, so shell-backed tests proceed despite the missing usable Linux Bash runtime. Historic full-suite failures are all in these reset tests; counts in symlink subtests include subtest failures.

| Test | What the failure establishes | Bash/reset/data safety |
|---|---|---|
| `tests/test_reset_command.py::TestResetCoversEveryDocumentsSubfolder::test_delete_block_removes_every_subfolder` | Reset script cannot start `/bin/bash`; any later temp cleanup error is secondary | Requires WSL Bash; operates on test-created temporary documents, not the live DB |
| `tests/test_reset_documents.py::ResetDocuments::test_all_document_entries_are_removed_without_removing_the_scaffold` | Same unavailable `/bin/bash` | Requires WSL Bash; temporary test tree only |
| `tests/test_reset_documents.py::ResetDocuments::test_empty_document_folders_remain_usable` | Same unavailable `/bin/bash` | Requires WSL Bash; temporary test tree only |
| `tests/test_reset_documents.py::ResetDocuments::test_internal_symlink_is_removed_without_following_its_target` | Same unavailable `/bin/bash` | Requires WSL Bash; temporary symlink/tree only |
| `tests/test_reset_documents.py::ResetDocuments::test_symlinked_roots_stop_before_any_deletion` | Same unavailable `/bin/bash` across documents and its six subdirectories (seven subtest paths) | Requires WSL Bash; temporary symlink/tree only |

The full run's 11 failure + 1 error total therefore maps to the reset/symlink group above: four ordinary reset-test failures plus six failed symlink subtests and one error among the seven symlink subtests, as recorded by the original run. The focused rerun's cleanup exceptions are secondary and vary with Windows handle cleanup. No failure points to JobHunt application behavior. Safe reproduction is the targeted command above from the integration checkout; these tests construct isolated temp paths and must not be redirected to `app/data/jobhunt.db`.

## Resume Matcher backend

### ATS parse tests

Command: `uv run pytest tests/integration/test_ats_parse_api.py -q --tb=short` — **14 passed, 2 errors**. Captured output shows `ValueError: the environment variable is longer than 32767 characters` during pytest setup. The oversized-upload parameter embeds `b"x" * (MAX_FILE_SIZE + 1)` in its generated node ID. Pytest's runner assigns the current test ID to `PYTEST_CURRENT_TEST` (`_pytest/runner.py`, `runtestprotocol`); Windows rejects that environment value before the fixture/test body reaches the API. This is a platform-sensitive test-ID/test-harness issue, not evidence of an ATS endpoint regression.

Minimal proposed fix for a later approved test-only change: wrap the oversized case in `pytest.param(..., id="oversize_pdf")`, preserving the exact payload and assertions. No change was made in this triage.

### Other focused failures

A bounded deterministic backend smoke run passed **197 tests, 2 deselected** in 48.96 seconds:

`uv run pytest tests/unit/test_ats.py tests/unit/test_ats_parse.py tests/unit/test_tailor_selection.py tests/integration/test_applications_api.py tests/integration/test_health_api.py tests/integration/test_jobs_api.py tests/integration/test_pdf_lifecycle.py -k 'not disconnected_cached_browser_is_replaced_automatically and not simultaneous_recovery_callers_install_one_browser and not uploads' -q --tb=short`

The two real-browser lifecycle tests are explicitly excluded; the remaining lifecycle coverage uses controlled/fake browser objects.

A second bounded run of auth and LLM contracts produced **34 passed, 3 failed, 1 warning**:

- `tests/integration/test_auth.py::test_tampered_session_is_rejected`: the test calls `client.cookies.set(..., secure=True)`, but the locked HTTPX 0.28.1 signature is `(name, value, domain='', path='/')`; `secure` is not accepted. It raises `TypeError` in test setup before the request assertion. This is a test/client API mismatch, not an observed auth behavior regression. Proposed minimal fix: construct/set the cookie using a supported API while retaining the tampered-token assertion.
- `tests/integration/test_llm_contract.py::TestOllamaTransport::test_complete_happy_path` and `::test_complete_json_over_the_wire`: LiteLLM's token counting initialization tries to fetch `cl100k_base.tiktoken`; the repository test fixture blocks external network, so the request is denied and LiteLLM wraps it as `APIConnectionError`. The mocked Ollama wire responses are not reached as successful test completions. This is a missing tokenizer-cache/deterministic test setup. Do not solve by allowing live provider/network traffic in ordinary tests. Proposed fix: seed the approved encoding cache in test setup or stub token counting for these mocked transport tests.

### Interrupted PDF/Playwright run

The original full backend suite was interrupted around 28% while `tests/integration/test_pdf_grid_geometry.py` exercised a 16-case CSS/page-size/margin/gap render matrix. Process inspection showed pytest waiting on a Playwright Node child without a browser child and no visible progress for several minutes. This indicates a browser-launch/resource stall, but does not prove whether the cause is Playwright startup, Chrome launch, or an individual rendering assertion. The separate `test_pdf_lifecycle.py` failure from that interrupted run has no preserved complete traceback, so its cause remains **unresolved**. The successful 197-test subset above covers only mocked PDF lifecycle paths. Do not rerun the full 1,914-case suite; first establish a bounded single-browser launch/render probe with captured traceback and child-process cleanup.

Available environment evidence: project pins Playwright 1.63.0; `pdftoppm` and system Chrome were present during inspection, but no Playwright browser cache was present. Do not download browser binaries without approval.

## Resume Matcher frontend Hero failure

Reproduction: `npm run test -- tests/block-dissolve-transition.test.tsx -t 'runs the effect from the Launch CTA only'` — one failing test; 36 skipped. The test destructures three links as `github, docs, launch`, then checks Launch; `components/home/hero.tsx` renders two links: the external docs link and the `/dashboard` Launch CTA. Thus `launch` is `undefined` and the assertion fails before animation behavior can be checked. Evidence supports an outdated link-count assumption in the test, not a missing Launch link in the component. Proposed minimal fix: locate Launch by accessible name and assert its `/dashboard` URL; independently query the docs link. No component/test change was made. Full Vitest remains incomplete; the prior all-suite invocation was manually stopped and has no final counts.

## Proposed fixes (not applied)

1. Give oversized ATS upload parameter a short explicit pytest ID.
2. Update the tampered-session test to use HTTPX 0.28.1's supported cookie API.
3. Make mocked Ollama tests independent of uncached LiteLLM tokenizer downloads.
4. Rework the Hero test to select links by accessible name/URL.
5. Diagnose one Playwright launch/render case with a strict timeout and reliable process-tree cleanup before deciding whether the PDF test or implementation is defective.
6. Run shell-backed JobHunt reset tests only in a known working WSL environment or provide an explicit supported Windows-compatible harness; retain temp-only target assertions.

