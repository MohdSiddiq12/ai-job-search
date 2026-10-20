#!/usr/bin/env python3
"""Root-cause triage for the Resume Matcher backend test suite.

Run from anywhere:  python triage_backend.py --repo D:\\Resume-Matcher\\Resume-Matcher --base origin/main

It NEVER touches your working tree, .env or databases. It builds two throwaway copies:
  dirty : tracked + untracked-not-ignored files, i.e. your uncommitted work, WITHOUT .env / DB files
  base  : `git archive <base>` (pristine)
runs pytest in each with every Settings env var scrubbed, then buckets each failure:
  REGRESSION   fails only with your changes
  PRE-EXISTING fails on pristine too (environment: Windows, deps, machine)
  NEW-TEST     test does not exist on base, so there is no baseline
Output: console summary + triage-report.md in --out (default: temp dir).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

HINTS = [  # (regex on message, likely cause). These are hypotheses to check, not conclusions.
    (r"WinError 32|PermissionError|being used by another process", "Windows file locking: SQLite/temp file still open, or a running server holds it"),
    (r"WinError 100(13|48)|address already in use|Errno 98", "Port already in use: stop the dev servers (3013/8013) before testing"),
    (r"database is locked|DatabaseBusy", "DB busy: another process (dev server) is using the same SQLite file"),
    (r"no such (table|column)|OperationalError|UndefinedTable|UndefinedColumn", "Schema drift: local models/migrations differ from what the tests expect"),
    (r"UnicodeDecodeError|UnicodeEncodeError|charmap", "Windows default encoding (cp1252): a file is opened without encoding='utf-8'"),
    (r"ModuleNotFoundError|ImportError|cannot import name", "Missing dependency, or a new/moved module is not importable"),
    (r"playwright|chromium|Executable doesn't exist", "Browser binary not installed (PDF/e2e tests)"),
    (r"ConnectError|ConnectionRefused|Max retries|TimeoutError|getaddrinfo|ssl", "Network/LLM call escaped its mock, or a real endpoint is configured"),
    (r"401|403|Unauthorized|Forbidden|host_guard|Invalid host", "Auth/host guard enabled by local config leaked into the test"),
    (r"ValidationError|422|Field required|extra_forbidden", "API/schema contract changed (request or response model)"),
    (r"assert .*(applied|saved)|ApplicationStatus", "Tracker status behaviour changed"),
]


def sh(cmd, cwd=None, env=None, timeout=None, capture=True):
    return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout, text=True, encoding="utf-8",
                          errors="replace", capture_output=capture)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_dirty(repo: Path, dest: Path):
    out = sh(["git", "ls-files", "-z", "-c", "-o", "--exclude-standard"], cwd=repo).stdout
    n = 0
    for rel in filter(None, out.split("\0")):
        src = repo / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
            n += 1
    return n


def export_base(repo: Path, base: str, dest: Path):
    # Extract from a completed archive file. On Windows, streaming extraction can
    # stop at tar's end markers before draining stdout; then git archive blocks
    # on a full pipe and p.wait() never returns.
    with tempfile.NamedTemporaryFile(prefix="rm-triage-base-", suffix=".tar", delete=False) as tmp:
        archive_path = Path(tmp.name)
    try:
        proc = sh(
            ["git", "archive", "--format=tar", f"--output={archive_path}", base],
            cwd=repo,
        )
        if proc.returncode != 0:
            sys.exit(f"git archive failed for base {base!r}: {proc.stderr[-1000:]}")
        with tarfile.open(archive_path, mode="r:") as tf:
            tf.extractall(dest)
    finally:
        archive_path.unlink(missing_ok=True)


def scrubbed_env(backend: Path, plugin_dir: Path, out_json: Path):
    env = dict(os.environ)
    code = "from app.config import Settings; print('\\n'.join(Settings.model_fields))"
    r = sh([sys.executable, "-c", code], cwd=backend, env=env)
    names = {n.upper() for n in r.stdout.split()} if r.returncode == 0 else set()
    removed = sorted(k for k in env if k.upper() in names)
    for k in removed:
        env.pop(k)
    env["PYTHONPATH"] = os.pathsep.join([str(plugin_dir), str(backend)])
    env["TRIAGE_OUT"] = str(out_json)
    env["PYTHONUTF8"] = "1"
    return env, removed


def run_pytest(tree: Path, plugin_dir: Path, out_json: Path, args, timeout):
    backend = tree / "apps" / "backend"
    env, removed = scrubbed_env(backend, plugin_dir, out_json)
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "triage_plugin",
           "--ignore=tests/integration/test_postgres_backend.py", *args]
    t = time.time()
    try:
        proc = sh(cmd, cwd=backend, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"timeout": True, "secs": round(time.time() - t), "removed_env": removed}
    data = json.loads(out_json.read_text(encoding="utf-8")) if out_json.exists() else None
    return {"data": data, "secs": round(time.time() - t), "removed_env": removed,
            "stdout_tail": (proc.stdout or "")[-1500:], "stderr_tail": (proc.stderr or "")[-800:]}


def hint(msg):
    for rx, why in HINTS:
        if re.search(rx, msg, re.I):
            return why
    return "no known pattern: read the traceback"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="path to the Resume Matcher repo root")
    ap.add_argument("--base", default="origin/main", help="git ref of the pristine baseline")
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "rm-triage"))
    ap.add_argument("--hash", action="append", default=[], help="file to SHA-256 before/after (e.g. your DB)")
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--pytest-args", nargs=argparse.REMAINDER, default=[], help="extra pytest args (e.g. a test path)")
    a = ap.parse_args()
    repo, out = Path(a.repo).resolve(), Path(a.out).resolve()
    if sh(["git", "rev-parse", "--verify", a.base + "^{commit}"], cwd=repo).returncode:
        sys.exit(f"base ref {a.base!r} not found. Try: git fetch, or pass --base <commit-sha>")
    shutil.rmtree(out, ignore_errors=True)
    dirty, base = out / "dirty", out / "base"
    dirty.mkdir(parents=True); base.mkdir()
    before = {p: sha(p) for p in a.hash if os.path.isfile(p)}

    print(f"[1/4] copying working tree (tracked + untracked, minus .env/DB): {copy_dirty(repo, dirty)} files")
    export_base(repo, a.base, base)
    print(f"[2/4] running DIRTY copy (clean env)...")
    rd = run_pytest(dirty, HERE, out / "dirty.json", a.pytest_args, a.timeout)
    if rd.get("timeout") or not rd.get("data"):
        sys.exit(f"dirty run produced no result: {json.dumps({k: v for k, v in rd.items() if k != 'data'})[:1200]}")
    D = rd["data"]
    files = sorted({nid.split("::")[0] for nid in D["failures"]})
    print(f"      dirty: {D['counts']} in {rd['secs']}s; {len(D['failures'])} failing ids in {len(files)} files")

    B = {"counts": {}, "failures": {}, "ran": []}
    rb = {"secs": 0}
    if files:
        print(f"[3/4] running BASE copy on those {len(files)} files only...")
        rb = run_pytest(base, HERE, out / "base.json", [f for f in files if (base / "apps" / "backend" / f).exists()] or ["--co", "-q"], a.timeout)
        B = rb.get("data") or B
    base_files = {f for f in files if (base / "apps" / "backend" / f).exists()}

    buckets = defaultdict(list)
    for nid, info in D["failures"].items():
        f = nid.split("::")[0]
        if f not in base_files or (B.get("ran") is not None and nid not in set(B["ran"])):
            buckets["NEW-TEST"].append((nid, info))
        elif nid in B["failures"]:
            buckets["PRE-EXISTING"].append((nid, info))
        else:
            buckets["REGRESSION"].append((nid, info))

    after = {p: sha(p) for p in before}
    lines = ["# Backend triage report", "",
             f"- repo: `{repo}`  base: `{a.base}`", f"- dirty run: {D['counts']} ({rd['secs']}s); base run on failing files: {B.get('counts')} ({rb.get('secs')}s)",
             f"- env vars scrubbed for the run: {', '.join(rd['removed_env']) or 'none'}",
             f"- file hashes unchanged: {before == after}" if before else "- no --hash files given", ""]
    for name in ("REGRESSION", "PRE-EXISTING", "NEW-TEST"):
        items = buckets.get(name, [])
        lines += [f"## {name}: {len(items)}", ""]
        groups = defaultdict(list)
        for nid, info in items:
            groups[info["signature"]].append((nid, info))
        for sig, g in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            nid, info = g[0]
            lines += [f"### {len(g)} x `{sig}`", f"- likely cause (hypothesis): **{hint(info['message'])}**",
                      f"- example: `{nid}` at `{info['where']}`", "```", *info["tail"], "```",
                      "- tests: " + ", ".join(f"`{n.split('/')[-1]}`" for n, _ in g[:8]) + (" ..." if len(g) > 8 else ""), ""]
    (out / "triage-report.md").write_text("\n".join(lines), encoding="utf-8")
    print("[4/4] summary")
    for name in ("REGRESSION", "PRE-EXISTING", "NEW-TEST"):
        items = buckets.get(name, [])
        print(f"  {name:<13} {len(items)}")
        sigs = defaultdict(int)
        for _, i in items:
            sigs[i["signature"]] += 1
        for s, c in sorted(sigs.items(), key=lambda kv: -kv[1])[:5]:
            print(f"      {c:>3} x {s[:110]}")
    print(f"\nfull report: {out / 'triage-report.md'}")
    return 1 if buckets.get("REGRESSION") else 0


if __name__ == "__main__":
    sys.exit(main())
