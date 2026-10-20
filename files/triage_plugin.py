"""pytest plugin: record every failure/error with a normalized signature to $TRIAGE_OUT (JSON)."""
import json
import os
import re

_fail = {}
_ran = []
_counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}


def _sig(msg: str) -> str:
    msg = (msg or "").strip().splitlines()[0] if msg else ""
    msg = re.sub(r"[A-Za-z]:\\[^\s'\"]+|/[^\s'\"]{3,}", "<path>", msg)
    msg = re.sub(r"0x[0-9a-fA-F]+|\b[0-9a-f]{8,}\b|\b\d+\b", "N", msg)
    msg = re.sub(r"'[^']{0,60}'|\"[^\"]{0,60}\"", "'S'", msg)
    return msg[:150]


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and (report.failed or report.skipped)):
        _ran.append(report.nodeid)
    if report.skipped:
        _counts["skipped"] += report.when == "setup" or report.when == "call"
        return
    if report.when == "call" and report.passed:
        _counts["passed"] += 1
        return
    if report.failed:
        kind = "error" if report.when != "call" else "failed"
        _counts[kind] += 1
        crash = getattr(report.longrepr, "reprcrash", None)
        message = getattr(crash, "message", "") or str(report.longrepr)[-300:]
        tail = str(report.longrepr).splitlines()[-8:]
        _fail[report.nodeid] = {
            "kind": kind, "when": report.when, "message": message[:600],
            "signature": _sig(message), "where": f"{getattr(crash, 'path', '')}:{getattr(crash, 'lineno', '')}",
            "tail": tail,
        }


def pytest_sessionfinish(session, exitstatus):
    out = os.environ.get("TRIAGE_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"counts": _counts, "failures": _fail, "ran": _ran, "exit": int(exitstatus)}, fh)
