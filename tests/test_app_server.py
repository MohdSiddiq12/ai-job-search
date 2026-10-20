import json
import sys
import tempfile
import threading
import unittest
import socket
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import core  # noqa: E402
import server  # noqa: E402


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = core.DB_PATH
        core.DB_PATH = Path(self.tmp.name) / "test.db"
        core.init()
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_address[1]}"

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)
        core.DB_PATH = self.old_db
        self.tmp.cleanup()

    def request(self, path, method="GET", body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        req = Request(self.base + path, data=data, method=method, headers=headers or {})
        try:
            with urlopen(req, timeout=3) as r:
                return r.status, r.headers, r.read()
        except HTTPError as e:
            return e.code, e.headers, e.read()

    def add_job(self):
        with core.connect() as c:
            c.execute("""INSERT INTO jobs(key,title,url,first_seen,last_seen,location_class)
                         VALUES('job-1','AI Engineer','https://example.com/job/1',? ,?,'dubai')""",
                      (core.utcnow(), core.utcnow()))
        return "job-1"

    def test_http_dashboard_and_host_origin_guards(self):
        code, headers, data = self.request("/")
        self.assertEqual(code, 200)
        self.assertIn(b"JobHunt", data)
        self.assertIn("nosniff", headers["X-Content-Type-Options"])
        self.assertEqual(self.request("/api/profile", headers={"Host": "evil.example"})[0], 403)
        with socket.create_connection(("127.0.0.1", self.http.server_address[1]), timeout=3) as sock:
            sock.sendall((f"PUT /api/profile HTTP/1.1\r\nHost: 127.0.0.1:{self.http.server_address[1]}\r\n"
                          "Origin: https://attacker.example\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}").encode())
            response = sock.recv(4096)
        self.assertIn(b"403 Forbidden", response)

    def test_profile_validation_and_search_crud(self):
        self.assertEqual(self.request("/api/profile", "PUT", {"weights": {"skills": -1}})[0], 400)
        self.assertEqual(self.request("/api/profile", "PUT", {"weights": {"skills": 0.5}})[0], 200)
        saved_profile = json.loads(self.request("/api/profile")[2])
        self.assertEqual(set(saved_profile["weights"]), {"skills", "role", "seniority", "location"})
        self.assertEqual(saved_profile["weights"]["skills"], 0.5)
        payload = {"name": "UAE support", "queries": ["Technical Support Engineer", "Technical Support Engineer"],
                   "country": "AE", "city": "Dubai", "jobage": 14, "interval_minutes": 0}
        code, _, raw = self.request("/api/searches", "POST", payload)
        self.assertEqual(code, 201)
        sid = json.loads(raw)["id"]
        searches = json.loads(self.request("/api/searches")[2])["searches"]
        saved = next(s for s in searches if s["id"] == sid)
        self.assertEqual(json.loads(saved["queries"]), ["Technical Support Engineer"])
        self.assertEqual(self.request("/api/searches", "POST", {**payload, "jobage": "bad"})[0], 400)
        self.assertEqual(self.request(f"/api/searches/{sid}", "PATCH", {"enabled": False})[0], 200)
        self.assertEqual(self.request(f"/api/searches/{sid}", "DELETE")[0], 200)

    def test_job_feedback_status_filter_and_confirmation(self):
        self.add_job()
        self.assertEqual(self.request("/api/jobs/job-1/feedback", "POST", {"verdict": "like"})[0], 200)
        self.assertEqual(self.request("/api/jobs/missing/feedback", "POST", {"verdict": "like"})[0], 404)
        self.assertEqual(self.request("/api/jobs/job-1/status", "POST", {
            "discovery_status": "reviewed", "status": "applied"})[0], 409)
        with core.connect() as c:
            self.assertEqual(c.execute("SELECT discovery_status FROM jobs WHERE key='job-1'").fetchone()[0], "new")
        self.assertEqual(self.request("/api/jobs/job-1/status", "POST", {
            "discovery_status": "reviewed", "status": "applied", "confirmed": True})[0], 200)
        detail = json.loads(self.request("/api/jobs/job-1")[2])
        self.assertEqual(detail["discovery_status"], "reviewed")
        self.assertEqual(detail["application"]["status"], "applied")

    def test_overview_jobs_and_export(self):
        self.add_job()
        overview = json.loads(self.request("/api/overview")[2])
        self.assertEqual(overview["total"], 1)
        jobs = json.loads(self.request("/api/jobs?q=AI")[2])
        self.assertEqual(jobs["count"], 1)
        exported = json.loads(self.request("/api/export")[2])
        self.assertEqual(exported["jobs"][0]["key"], "job-1")

    def test_manual_description_endpoint_export_and_status_filter(self):
        self.add_job()
        body = {"text": "Python engineer\nOwn services. <script>alert(1)</script>"}
        code, _, first = self.request("/api/jobs/job-1/description", "POST", body)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(first)["status"], "manual")
        code, _, second = self.request("/api/jobs/job-1/description", "POST", body)
        self.assertTrue(json.loads(second)["unchanged"])
        detail = json.loads(self.request("/api/jobs/job-1")[2])
        self.assertEqual(detail["description"]["status"], "manual")
        self.assertIn("<script>", detail["description"]["original_text"])
        self.assertEqual(json.loads(self.request("/api/jobs?description_status=manual")[2])["total"], 1)
        self.assertEqual(json.loads(self.request("/api/overview")[2])["descriptions"]["manual"], 1)
        self.assertEqual(len(json.loads(self.request("/api/export")[2])["job_descriptions"]), 1)
        self.assertEqual(self.request("/api/jobs/no-such-job/description", "POST", body)[0], 404)
        self.assertEqual(self.request("/api/jobs/job-1/description", "POST", {"text": " "})[0], 400)

    def test_resume_matcher_boundary_manual_packet_and_result_link(self):
        self.add_job()
        self.request("/api/jobs/job-1/description", "POST", {"text": "Python engineer and SQL"})
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resume = root / "documents" / "cv" / "resume.pdf"
            resume_alt = root / "documents" / "cv" / "resume-alt.pdf"
            result = root / "documents" / "applications" / "tailored.docx"
            resume.parent.mkdir(parents=True)
            result.parent.mkdir(parents=True)
            resume.write_bytes(b"resume fixture")
            resume_alt.write_bytes(b"other resume fixture")
            result.write_bytes(b"tailored fixture")
            with patch.object(core, "ROOT", root):
                integration = json.loads(self.request("/api/integrations/resume-matcher")[2])
                self.assertEqual(integration["status"], "not_configured")
                self.assertFalse(integration["available"])
                req = {"resume_reference": "documents/cv/resume.pdf", "idempotency_key": "idem_test_001"}
                code, _, raw = self.request("/api/jobs/job-1/tailoring", "POST", req)
                self.assertEqual(code, 201)
                task = json.loads(raw)
                code, _, repeated = self.request("/api/jobs/job-1/tailoring", "POST", req)
                self.assertEqual(code, 200)
                self.assertTrue(json.loads(repeated)["reused"])
                conflict = self.request("/api/jobs/job-1/tailoring", "POST", {
                    "resume_reference": "documents/cv/resume-alt.pdf", "idempotency_key": "idem_test_001"})
                self.assertEqual(conflict[0], 409)
                packet = json.loads(self.request(f"/api/tailoring/{task['id']}/export")[2])
                self.assertEqual(packet["payload"]["job"]["description"], "Python engineer and SQL")
                self.assertIn("has not contacted", packet["note"])
                self.assertEqual(self.request(f"/api/tailoring/{task['id']}/result", "POST", {
                    "document_reference": "documents/applications/tailored.docx"})[0], 409)
                code, _, result_body = self.request(f"/api/tailoring/{task['id']}/result", "POST", {
                    "document_reference": "documents/applications/tailored.docx", "confirmed": True})
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(result_body)["result_source"], "manual_import")
                self.assertEqual(self.request(f"/api/tailoring/{task['id']}/result", "POST", {
                    "document_reference": "../cv/resume.pdf", "confirmed": True})[0], 400)
        detail = json.loads(self.request("/api/jobs/job-1")[2])
        self.assertEqual(detail["tailoring_requests"][0]["status"], "complete")
        self.assertEqual(detail["tailoring_requests"][0]["result_source"], "manual_import")

    def test_application_followups_metrics_and_filters(self):
        self.add_job()
        due = (date.today() + timedelta(days=3)).isoformat()
        code, _, _ = self.request("/api/jobs/job-1/status", "POST", {
            "status": "drafting", "notes": "Review role", "follow_up": due})
        self.assertEqual(code, 200)
        apps = json.loads(self.request("/api/applications?stage=prepared&follow_up=upcoming")[2])
        self.assertEqual(apps["total"], 1)
        self.assertEqual(apps["applications"][0]["follow_up"], due)
        metrics = json.loads(self.request("/api/overview")[2])
        self.assertEqual(metrics["applications_prepared"], 1)
        self.assertEqual(metrics["upcoming_followups"], 1)
        self.assertEqual(self.request("/api/jobs/job-1/status", "POST", {
            "status": "drafting", "follow_up": "next Tuesday"})[0], 400)
        self.assertEqual(self.request("/api/jobs/job-1/status", "POST", {
            "status": "ready_for_review", "follow_up": ""})[0], 200)
        self.assertEqual(json.loads(self.request("/api/applications?follow_up=none")[2])["total"], 1)

    def test_bad_json_and_unknown_search_run_are_clean_errors(self):
        code, _, _ = self.request("/api/profile", "PUT", {"skills": ["", 42]})
        self.assertEqual(code, 400)
        req = Request(self.base + "/api/profile", data=b"{", method="PUT",
                      headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 400)
        self.assertEqual(self.request("/api/runs", "POST", {"search_id": 999})[0], 404)

    def test_run_endpoint_starts_recorded_discovery(self):
        with patch.object(core, "run_discovery") as run:
            code, _, _ = self.request("/api/runs", "POST", {})
            self.assertEqual(code, 202)
            for _ in range(100):
                if run.called:
                    break
                threading.Event().wait(.01)
            self.assertTrue(run.called)


if __name__ == "__main__":
    unittest.main()
