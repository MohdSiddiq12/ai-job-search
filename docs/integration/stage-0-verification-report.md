# Stage 0 — Verification Report

Date: 2026-10-20. Read-only verification of the current local integration checkout. No source changes, database writes, migrations, commits, or deployments were made during this verification.

## Results

| Check | Result | Details |
|---|---|---|
| Resume Matcher backend | **Failed** | `uv run pytest -q -p no:cacheprovider --tb=short` completed with **1,880 passed, 23 failed, 14 errors, 18 skipped, 2 deselected** in 21m 12s. PostgreSQL tests were skipped because `TEST_DATABASE_URL` was not configured. The run showed failures/errors in AI operation budgets, ATS parsing, auth, PDF lifecycle/rendering, temperature request contracts, upload recovery, crypto, and e2e monitor tests. |
| Resume Matcher frontend tests | **Incomplete / failed test observed** | `npm run test -- --pool=threads --maxWorkers=1` did not complete within about 10 minutes. The first reported file, `tests/resume-builder-attachments.test.tsx`, had 1 failure among 36 tests: `clears cover-letter when the next document has no value`; that test took about 499 seconds. The run was stopped while still active, so this is not a complete frontend-suite result. |
| TypeScript | **Unverified** | `npm run typecheck` (`tsc --noEmit`) produced no output and was stopped at the plan's 10-minute limit. |
| Local discovery route | **HTTP check passed; browser UI check unavailable** | `GET http://127.0.0.1:3013/discover/jobs` returned HTTP 200 (17,080 bytes). `GET http://127.0.0.1:8013/api/v1/discovery/jobs?page_size=1` returned HTTP 200, 244 total jobs, and one item. Computer/browser inventory returned no browsers, and the in-app browser was unavailable, so no visual browser check was possible. Existing pilot servers were left running. |
| JobHunt source DB hash | **Matches** | `56d7b8620bfe12133d749cf6219cc508d746c3d2ae458ccc9a9c6d222d23b3f0`, matching the recorded Stage C pilot value. |
| 244-job snapshot hash | **Matches** | `1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b`, matching the recorded Stage C pilot value. |

## Checkout state and next gate

The host checkout is `D:\Resume-Matcher\Resume-Matcher`, branch `deployment-hardening`. It already contains extensive uncommitted tracking and discovery changes; these were preserved. The integration checkout is on `integration/resume-matcher-foundation`.

The current host diff is ahead of the unified plan's C.3 prompt and overlaps its schema strategy: it rebuilds the existing `jobs` and `applications` SQLite tables and modifies the existing application model/schema/database paths, while the unified plan calls for new discovery tables and additive-only changes. The router currently exposes read-only discovery endpoints; the tracking helper has no save/skip endpoint, and the confirmation-status constant is declared but not enforced. These observations are not changes made by this verification.

**Stage 0 is not green.** The unified plan's Stage 0 prompt says to fix nothing and list failures. Do not stack additional C.3 changes until the failing/incomplete verification items and already-present C.3 diff are reconciled. No commit was made.

## Database handling

The JobHunt source DB and snapshot were hashed without opening a write connection. The active pilot Resume Matcher DB could not be hashed because the running app held it open; it was left untouched. Backend tests use pytest's temporary `DATA_DIR` and clear a developer `DATABASE_URL` in `tests/conftest.py`.
