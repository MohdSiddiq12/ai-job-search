# Stage B — isolated workspace plan

## Recommendation

Keep JobHunt as the canonical product repository and prepare a dedicated integration worktree from its `master` branch (suggested branch: `integration/resume-matcher-foundation`). Use the clean Resume Matcher `deployment-hardening` checkout as a read-only source reference. Adapt selected code in later reviewed increments; do not copy the full repository or any `.git`, `.venv`, `node_modules`, build output, cache, ignored data, secrets or generated resume files.

This preserves the public JobHunt fork and original checkout. JobHunt's current untracked work is not automatically present in a Git worktree; review and copy files selectively rather than assuming they are disposable. The eventual UI/backend can adopt Resume Matcher’s Next/FastAPI patterns while JobHunt remains the product and data owner.

## Proposed locations and command — not executed

```powershell
git -C D:\AI-Job\ai-job-search worktree add `
  -b integration/resume-matcher-foundation `
  D:\AI-Job\ai-job-search-integration `
  master
```

Original JobHunt remains on `master`; Resume Matcher remains on `deployment-hardening`. The new worktree begins at tracked JobHunt `master`; its current untracked files (app, tests, audit docs) require deliberate review and selective copying before integration work. Verify both statuses/branch pointers before and after creation.

Approved and created on 2026-10-19. Worktree: `D:\AI-Job\ai-job-search-integration`, branch `integration/resume-matcher-foundation`, starting commit `30158c0` from JobHunt `master`. The original JobHunt worktree remains on `master`; Resume Matcher remains on `deployment-hardening`.

The worktree contains the reviewed JobHunt app files, three app test files, OpenCode setup command and all docs. `tools/freehire_discover.py` was selectively copied because `app/core.py` imports it at runtime and it is not tracked in source JobHunt `master`. Tracked `tools/job_key.py` was already available. The live `app/data/`, `__pycache__` and `files.zip` were not copied. Initial app-test execution exposed the missing helper; after copying it, the targeted JobHunt suite passed 24 tests.

## Data and dependency safety

- Do not copy either live database into the source tree.
- Before migration, create timestamped backups outside both Git roots with restrictive Windows ACLs; record size/hash/counts without printing content; prove restore on a disposable copy.
- JobHunt data remains at `app/data/jobhunt.db`; current snapshot is 244 jobs / 2 applications.
- Approved `uv sync --extra dev` ran in Resume Matcher’s existing `.venv`; the backend full suite was started, with partial failures/stall recorded in `stage-b-baseline-results.md`.
- Frontend test dependencies already exist in Matcher `node_modules`; its source checkout remains unchanged.
