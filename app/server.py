#!/usr/bin/env python3
"""JobHunt local server.  python app/server.py            -> http://127.0.0.1:8787
   python app/server.py --run-once        -> one discovery run (for Task Scheduler), then exit
   python app/server.py --import-seen     -> read-only import of job_scraper/seen_jobs.json
Binds to 127.0.0.1 only. Private data stays on your machine."""
import argparse
import json
import re
import sys
import threading
import time
import webbrowser
import math
from pathlib import Path
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static" / "index.html"
PORT = 8787


def _ok(o, code=200):
    return code, o


def _document_reference(value, allowed_root):
    """Accept only existing PDF/DOCX files beneath a private document folder."""
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        return None
    rel = Path(value.strip())
    if rel.is_absolute() or any(part in ("..", "") for part in rel.parts):
        return None
    root = Path(allowed_root).resolve()
    try:
        candidate = (core.ROOT / rel).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    current = core.ROOT
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            return None
    if not candidate.is_file() or candidate.suffix.lower() not in (".pdf", ".docx"):
        return None
    return candidate.relative_to(core.ROOT.resolve()).as_posix()


def api(method, path, q, body):
    """Returns (status, json). One connection per request."""
    with core.connect() as c:
        m = lambda p: re.fullmatch(p, path)
        if method == "GET" and path == "/api/overview":
            return _ok(core.overview(c))
        if method == "GET" and path == "/api/jobs":
            return _ok(core.list_jobs(c, q))
        if method == "GET" and path == "/api/applications":
            return _ok(core.list_applications(c, q))
        if (mm := m(r"/api/jobs/([^/]+)")) and method == "GET":
            j = core.get_job(c, mm[1])
            return _ok(j) if j else (404, {"error": "unknown job"})
        if (mm := m(r"/api/jobs/([^/]+)/status")) and method == "POST":
            if not c.execute("SELECT 1 FROM jobs WHERE key=?", (mm[1],)).fetchone():
                return 404, {"error": "unknown job"}
            if "status" in body and body["status"] not in core.APP_STATUSES:
                return 400, {"error": f"status must be one of {core.APP_STATUSES}"}
            if "status" in body and body["status"] in core.CONFIRM_REQUIRED and not body.get("confirmed"):
                return 409, {"error": f"'{body['status']}' requires confirmed=true"}
            if "notes" in body and (body["notes"] is not None and (not isinstance(body["notes"], str) or len(body["notes"]) > 10000)):
                return 400, {"error": "notes must be text up to 10000 characters"}
            if "follow_up" in body and body["follow_up"] not in (None, ""):
                from datetime import date
                try:
                    if not isinstance(body["follow_up"], str) or date.fromisoformat(body["follow_up"]).isoformat() != body["follow_up"]:
                        raise ValueError
                except ValueError:
                    return 400, {"error": "follow_up must be a YYYY-MM-DD date or empty"}
            if "discovery_status" in body:
                if body["discovery_status"] not in core.DISCOVERY_STATUSES:
                    return 400, {"error": "bad discovery_status"}
                c.execute("UPDATE jobs SET discovery_status=? WHERE key=?", (body["discovery_status"], mm[1]))
                core.log(c, "discovery", mm[1], f"discovery status -> {body['discovery_status']}")
                if "status" not in body:
                    return _ok({"ok": True})
            return core.set_app_status(c, mm[1], body.get("status"), body.get("notes"), body.get("follow_up"),
                                       bool(body.get("confirmed")))
        if (mm := m(r"/api/jobs/([^/]+)/feedback")) and method == "POST":
            if not c.execute("SELECT 1 FROM jobs WHERE key=?", (mm[1],)).fetchone():
                return 404, {"error": "unknown job"}
            if body.get("verdict") not in ("like", "dislike", "maybe", "apply", "skip", "irrelevant"):
                return 400, {"error": "bad verdict"}
            c.execute("INSERT INTO feedback(job_key,verdict,reason,ts) VALUES(?,?,?,?)",
                      (mm[1], body["verdict"], str(body.get("reason", ""))[:500], core.utcnow()))
            core.log(c, "feedback", mm[1], body["verdict"])
            return _ok({"ok": True})
        if (mm := m(r"/api/jobs/([^/]+)/description")) and method == "POST":
            result = core.save_manual_description(c, mm[1], body.get("text"))
            status = result.pop("http_status", 200)
            return _ok(result, status) if status == 200 else (status, result)
        if method == "POST" and (mm := m(r"/api/jobs/([^/]+)/tailoring")):
            resume_ref = _document_reference(body.get("resume_reference"), core.ROOT / "documents" / "cv")
            if not resume_ref:
                return 400, {"error": "resume_reference must point to an existing PDF or DOCX under documents/cv"}
            idem = body.get("idempotency_key")
            if not isinstance(idem, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", idem):
                return 400, {"error": "idempotency_key must be 8-100 safe characters"}
            result = core.create_tailoring_request(c, mm[1], resume_ref, idem)
            status = result.pop("http_status", 200)
            return _ok(result, 201 if status == 200 and not result.get("reused") else status) if status == 200 else (status, result)
        if path == "/api/integrations/resume-matcher" and method == "GET":
            from integrations.resume_matcher import get_adapter
            return _ok(get_adapter().availability())
        if path == "/api/tailoring" and method == "GET":
            return _ok({"requests": [dict(r) for r in c.execute(
                "SELECT id,job_key,status,selected_resume_ref,external_operation_id,result_document_ref,result_source,error,created_at,updated_at FROM tailoring_requests ORDER BY id DESC LIMIT 100")]})
        if (mm := m(r"/api/tailoring/(\d+)/export")) and method == "GET":
            row = c.execute("SELECT * FROM tailoring_requests WHERE id=?", (mm[1],)).fetchone()
            if not row:
                return 404, {"error": "unknown tailoring request"}
            return _ok({"request_id": row["id"], "status": row["status"], "payload": json.loads(row["payload_json"]),
                        "note": "Manual handoff packet only. JobHunt has not contacted Resume Matcher."})
        if (mm := m(r"/api/tailoring/(\d+)/result")) and method == "POST":
            row = c.execute("SELECT * FROM tailoring_requests WHERE id=?", (mm[1],)).fetchone()
            if not row:
                return 404, {"error": "unknown tailoring request"}
            if body.get("confirmed") is not True:
                return 409, {"error": "confirm that this file is the returned tailored document"}
            doc_ref = _document_reference(body.get("document_reference"), core.ROOT / "documents" / "applications")
            if not doc_ref:
                return 400, {"error": "document_reference must point to an existing PDF or DOCX under documents/applications"}
            c.execute("UPDATE tailoring_requests SET status='complete',result_document_ref=?,result_source='manual_import',error=NULL,updated_at=? WHERE id=?",
                      (doc_ref, core.utcnow(), mm[1]))
            core.log(c, "tailoring_result", row["job_key"], f"manual tailored document linked to request {mm[1]}")
            return _ok({"ok": True, "status": "complete", "result_document_ref": doc_ref, "result_source": "manual_import"})
        if path == "/api/profile":
            if method == "GET":
                return _ok(core.get_profile(c))
            if method == "PUT":
                incoming_weights = body.get("weights", {})
                w = {**core.get_profile(c).get("weights", {}), **incoming_weights} if isinstance(incoming_weights, dict) else incoming_weights
                allowed_weights = {"skills", "role", "seniority", "location"}
                if (not isinstance(w, dict) or set(w) != allowed_weights or
                    any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 or v > 100 for v in w.values())):
                    return 400, {"error": "weights must be non-negative numbers"}
                for k in ("skills", "target_titles", "essential_skills", "irrelevant_skills"):
                    if k in body and (not isinstance(body[k], list) or len(body[k]) > 200 or
                                      any(not isinstance(x, str) or not x.strip() or len(x) > 120 for x in body[k])):
                        return 400, {"error": f"{k} must be a list of non-empty strings (max 200)"}
                if sum(w.values()) <= 0:
                    return 400, {"error": "at least one score weight must be greater than zero"}
                prof = {**core.get_profile(c), **{k: body[k] for k in body if k in core.DEFAULT_PROFILE}}
                prof["weights"] = w
                c.execute("UPDATE profile SET data=?", (json.dumps(prof),))
                n = core.rescore_all(c)
                core.log(c, "profile", None, f"profile updated, {n} jobs rescored")
                return _ok({"ok": True, "rescored": n})
        if path == "/api/searches":
            if method == "GET":
                return _ok({"searches": [dict(r) for r in c.execute("SELECT * FROM searches ORDER BY id")]})
            if method == "POST":
                if not isinstance(body.get("name"), str) or not body["name"].strip() or len(body["name"]) > 100:
                    return 400, {"error": "name must be a non-empty string (max 100)"}
                raw_qs = body.get("queries")
                if not isinstance(raw_qs, list) or len(raw_qs) > 40 or any(not isinstance(x, str) for x in raw_qs):
                    return 400, {"error": "queries must be a list of at most 40 strings"}
                qs = list(dict.fromkeys(x.strip() for x in raw_qs if x.strip()))
                if not qs or any(len(x) > 120 for x in qs):
                    return 400, {"error": "name and at least one query required"}
                try:
                    age = int(body.get("jobage", 14))
                    interval = int(body.get("interval_minutes", 0))
                except (TypeError, ValueError):
                    return 400, {"error": "jobage and interval_minutes must be integers"}
                if not 1 <= age <= 90 or not 0 <= interval <= 525600:
                    return 400, {"error": "jobage must be 1-90 and interval_minutes 0-525600"}
                country, city = body.get("country", "AE"), body.get("city", "dubai")
                if not isinstance(country, str) or not re.fullmatch(r"[A-Za-z]{2}", country) or not isinstance(city, str) or not city.strip() or len(city) > 80:
                    return 400, {"error": "country must be a 2-letter code and city a non-empty label"}
                sid = c.execute("""INSERT INTO searches(name,queries,country,city,jobage,include_remote,enabled,interval_minutes)
                                   VALUES(?,?,?,?,?,?,1,?)""",
                                (body["name"].strip(), json.dumps(qs), country.upper(), city.strip().lower(),
                                 age, int(bool(body.get("include_remote", True))), interval)).lastrowid
                return _ok({"id": sid}, 201)
        if (mm := m(r"/api/searches/(\d+)")) and method == "DELETE":
            c.execute("DELETE FROM searches WHERE id=?", (mm[1],))
            return _ok({"ok": True})
        if (mm := m(r"/api/searches/(\d+)")) and method == "PATCH":
            if not c.execute("SELECT 1 FROM searches WHERE id=?", (mm[1],)).fetchone():
                return 404, {"error": "unknown search"}
            if "enabled" in body and type(body["enabled"]) not in (int, bool):
                return 400, {"error": "enabled must be boolean"}
            if "interval_minutes" in body and (type(body["interval_minutes"]) is not int or not 0 <= body["interval_minutes"] <= 525600):
                return 400, {"error": "interval_minutes must be 0-525600"}
            for k in ("enabled", "interval_minutes"):
                if k in body:
                    c.execute(f"UPDATE searches SET {k}=? WHERE id=?", (int(body[k]), mm[1]))
            return _ok({"ok": True})
        if path == "/api/runs":
            if method == "GET":
                return _ok({"runs": [dict(r) for r in c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 30")],
                            "running": core.RUN_LOCK.locked()})
            if method == "POST":
                if core.RUN_LOCK.locked():
                    return 409, {"error": "a run is already in progress"}
                sid = body.get("search_id")
                if sid is not None and (type(sid) is not int or not c.execute("SELECT 1 FROM searches WHERE id=?", (sid,)).fetchone()):
                    return 404, {"error": "unknown search"}
                threading.Thread(target=core.run_discovery, args=(body.get("search_id"), "manual"), daemon=True).start()
                return 202, {"started": True}
        if path == "/api/import" and method == "POST":
            return _ok(core.import_seen_jobs(c))
        if path == "/api/export" and method == "GET":
            return _ok({"profile": core.get_profile(c),
                        "jobs": [dict(r) for r in c.execute("SELECT * FROM jobs")],
                        "applications": [dict(r) for r in c.execute("SELECT * FROM applications")],
                        "feedback": [dict(r) for r in c.execute("SELECT * FROM feedback")],
                        "job_descriptions": [dict(r) for r in c.execute("SELECT * FROM job_description_snapshots ORDER BY id")],
                        "tailoring_requests": [dict(r) for r in c.execute("SELECT * FROM tailoring_requests ORDER BY id")]})
    return 404, {"error": "not found"}


class Handler(BaseHTTPRequestHandler):
    def _allowed(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return False  # DNS-rebinding guard
        origin = self.headers.get("Origin")
        return origin is None or urlparse(origin).hostname in ("127.0.0.1", "localhost")  # cross-site POST guard

    def _send(self, code, payload, ctype="application/json"):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        if not self._allowed():
            return self._send(403, {"error": "forbidden host or origin"})
        u = urlparse(self.path)
        if method == "GET" and u.path in ("/", "/index.html"):
            return self._send(200, STATIC.read_bytes(), "text/html")
        body = {}
        if method in ("POST", "PUT", "PATCH"):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n < 0 or n > 1_000_000:
                    return self._send(413, {"error": "request body too large"})
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except (ValueError, json.JSONDecodeError):
                return self._send(400, {"error": "invalid JSON body"})
        try:
            code, out = api(method, u.path, parse_qs(u.query), body)
        except Exception as exc:  # isolate: one bad request never kills the server
            print(f"request error: {type(exc).__name__}: {exc}", file=sys.stderr)
            code, out = 500, {"error": "request could not be completed"}
        self._send(code, out)

    do_GET = lambda s: s._handle("GET")
    do_POST = lambda s: s._handle("POST")
    do_PUT = lambda s: s._handle("PUT")
    do_PATCH = lambda s: s._handle("PATCH")
    do_DELETE = lambda s: s._handle("DELETE")

    def log_message(self, *a):
        pass


def scheduler():
    """Run each enabled search whose interval has elapsed. Timestamps are UTC."""
    while True:
        time.sleep(60)
        try:
            with core.connect() as c:
                due = []
                for s in c.execute("SELECT * FROM searches WHERE enabled=1 AND interval_minutes>0"):
                    r = c.execute("SELECT started FROM runs WHERE search_id=? ORDER BY id DESC LIMIT 1", (s["id"],)).fetchone()
                    last = datetime.strptime(r[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if r else None
                    if not last or datetime.now(timezone.utc) - last >= timedelta(minutes=s["interval_minutes"]):
                        due.append(s["id"])
            for sid in due:
                core.run_discovery(sid, "scheduled")
        except Exception as exc:
            print("scheduler error:", exc, file=sys.stderr)


def main():
    for st in (sys.stdout, sys.stderr):
        if getattr(st, "reconfigure", None):
            st.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--run-once", action="store_true")
    ap.add_argument("--search-id", type=int)
    ap.add_argument("--import-seen", action="store_true")
    a = ap.parse_args()
    core.init()
    if a.import_seen:
        with core.connect() as c:
            print(core.import_seen_jobs(c))
        return 0
    if a.run_once:
        out = core.run_discovery(a.search_id, "scheduled")
        print(json.dumps(out, indent=2))
        return 0 if out.get("status") == "complete" else 3
    threading.Thread(target=scheduler, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}"
    print(f"JobHunt running at {url}  (Ctrl+C to stop)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
