# Stage 0 triage runbook (Windows / PowerShell)

Goal: find out why the backend shows 23 failed + 14 errors, and why `tsc` and the frontend
tests did not finish, without touching your working tree, `.env` or databases.

## What I measured on pristine upstream (Linux sandbox, 1 CPU, 3 GB RAM)

| Check | Result |
|---|---|
| Backend suite | 1,860 passed, 22 skipped, **0 failed** (3 min) |
| `tsc --noEmit` | **22 s**, 4,269 files, 657 MB |
| Frontend tests (161 files) | Still running after **11+ minutes** on pristine code (1 CPU). Stopping at 10 minutes proves nothing. |
| One local `.env` line (`TRACKER_AUTO_STATUS=saved`) | Turned 2 healthy tests red when run in place (reproduced) |

So: the backend failures come from your changes, your environment, or your `.env`, because
pristine code is green. A 10-minute silent `tsc` is abnormal (22 s baseline). A frontend test
run that is slow is not by itself a bug.

## Step 1: back up uncommitted work (read-only for the repo, no commit)

```powershell
cd D:\Resume-Matcher\Resume-Matcher
New-Item -ItemType Directory D:\AI-Job\backups -Force | Out-Null
$ts = Get-Date -Format yyyyMMdd-HHmm
git diff HEAD --binary > D:\AI-Job\backups\wip-$ts.patch
git ls-files -o --exclude-standard > D:\AI-Job\backups\wip-untracked-$ts.txt
tar -cf D:\AI-Job\backups\wip-untracked-$ts.tar -T D:\AI-Job\backups\wip-untracked-$ts.txt
git diff HEAD --stat | Select-Object -Last 30      # which EXISTING files you modified
```

## Step 2: stop the dev servers, then run the backend triage

Servers on 3013/8013 can hold the SQLite file and cause "locked" or "address in use" failures.

```powershell
$base = git merge-base HEAD origin/main        # run `git fetch origin` first if this errors
python D:\AI-Job\triage\triage_backend.py --repo D:\Resume-Matcher\Resume-Matcher --base $base `
    --hash "<path-to-your-resume-matcher-db-file>"
```

Use the same Python that has the backend dependencies installed. Expect 5 to 15 minutes. It
writes `triage-report.md` into `%TEMP%\rm-triage` and prints three buckets:

| Bucket | Meaning | Action |
|---|---|---|
| REGRESSION | passes on pristine, fails with your changes | Fix these first. They are caused by your edits. |
| PRE-EXISTING | fails on pristine too | Environment (Windows, deps, machine). Fix by the hint; do not change product code. |
| NEW-TEST | test does not exist on base | Judge on its own; usually your new tests. |

It runs on clean copies with `.env`, databases and every Settings environment variable
stripped. If the clean copy shows far fewer failures than your 23 + 14, the root cause is
configuration leaking into tests, not code.

## Step 3: frontend diagnostics (run alone, servers stopped)

```powershell
cd D:\Resume-Matcher\Resume-Matcher\apps\frontend
(npx tsc --noEmit --listFilesOnly | Measure-Object -Line).Lines     # pristine: 4269
Measure-Command { npx tsc --noEmit --extendedDiagnostics }          # pristine: ~22 s
```

- File count far above 4,269: `tsconfig.json` is picking up junk (snapshots, `.work`, generated data). Add it to `exclude`.
- Count normal but still slow or hung: a type-level blowup in a changed file. Run `npx tsc --noEmit --generateTrace $env:TEMP\tsc-trace` and open the slowest file.

```powershell
npx vitest run --reporter=json --outputFile=$env:TEMP\vt.json     # long: let it finish
# or split it so each part reports on its own:
1..4 | ForEach-Object { npx vitest run --shard=$_/4 --reporter=dot }
python -c "import json,os;d=json.load(open(os.environ['TEMP']+'/vt.json'));print({k:d[k] for k in ('numPassedTests','numFailedTests')});[print(r['name'].split('tests')[-1]) for r in d['testResults'] if r['status']!='passed']"
```

## Step 4: decision rule for the C.3 conflict

Your handoff says uncommitted C.3 work edits existing upstream code, which conflicts with the
additive-only plan. After step 2:

1. If REGRESSION failures sit in files from `git diff HEAD --stat` (existing upstream files), those edits are the cause. Keep the backup patch, revert only those hunks (after you approve), and rebuild them as new files per the plan.
2. Keep C.1/C.2 (read-only discovery). Their tests passed in your own run.
3. Only re-run Stage 0 after the fixes. Do not start C.3 until backend, frontend and tsc are green.

## Meanwhile: do not pause the job search

Standalone JobHunt does not depend on any of this. Run `python app\server.py` for daily
discovery, shortlist there, and paste a job description into Resume Matcher to tailor. That
loop works today; the unified app is a convenience, not a prerequisite.
