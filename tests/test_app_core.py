import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import core  # noqa: E402


def fake_rows():
    mk = lambda slug, title, comp, loc, ctry, skills, date="2026-10-15", mode="onsite": {
        "id": slug, "title": title, "company": comp, "url": f"https://freehire.me/jobs/{slug}", "location": loc,
        "countries": ctry, "skills": skills, "date": date, "work_mode": mode}
    return [mk("a", "AI Engineer, Entry Level", "InterSystems", "Dubai", ["AE"], ["python", "pytorch", "docker"]),
            mk("b", "Senior Data Engineer", "BigCo", "Abu Dhabi", ["AE"], ["spark", "scala", "sql"]),
            mk("c", "Backend Developer", "NoSkills", "", [], [], mode="remote"),
            mk("d", "ML Engineer", "Berlin GmbH", "Berlin", ["DE"], ["python"])]


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        core.DB_PATH = Path(self.tmp.name) / "t.db"
        core.init()
        self._orig = core.fd.search
        core.fd.search = lambda *a, **k: fake_rows()

    def tearDown(self):
        core.fd.search = self._orig
        self.tmp.cleanup()

    def run_once(self):
        with core.connect() as c:
            sid = c.execute("SELECT id FROM searches").fetchone()[0]
        return core.run_discovery(sid)

    def test_discovery_persists_filters_and_is_idempotent(self):
        r1 = self.run_once()
        self.assertEqual(r1["status"], "complete")
        self.assertEqual(r1["new"], 3)  # Berlin job dropped: known foreign country
        r2 = self.run_once()
        self.assertEqual(r2["new"], 0)
        with core.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 3)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM applications").fetchone()[0], 0)  # never auto-applied

    def test_score_is_explained_and_unknowns_labelled(self):
        self.run_once()
        with core.connect() as c:
            j = core.get_job(c, c.execute("SELECT key FROM jobs WHERE title LIKE 'Backend%'").fetchone()[0])
        s = j["score_json"]
        skills = next(x for x in s["components"] if x["name"] == "skills")
        self.assertIsNone(skills["score"])
        self.assertLess(s["confidence"], 100)
        self.assertTrue(all(x["evidence"] for x in s["components"]))

    def test_unknown_skills_count_neutral_not_excluded(self):
        prof = core.DEFAULT_PROFILE
        thin = core.score_job({"title": "AI Engineer", "skills": [], "location_class": "dubai"}, prof)
        full = core.score_job({"title": "AI Engineer", "skills": ["python", "pytorch"], "location_class": "dubai"}, prof)
        # (50*.35 + 100*.30 + 70*.15 + 100*.20) = 78: unknown skills must not be renormalised away (which gives 93)
        self.assertEqual(thin["overall"], 78)
        self.assertLess(thin["overall"], full["overall"])
        self.assertEqual(thin["confidence"], 65)

    def test_senior_role_stays_discoverable_with_low_seniority_score(self):
        self.run_once()
        with core.connect() as c:
            row = c.execute("SELECT * FROM jobs WHERE title LIKE 'Senior%'").fetchone()
            sen = next(x for x in json.loads(row["score_json"])["components"] if x["name"] == "seniority")
        self.assertEqual(sen["score"], 25)

    def test_applied_requires_confirmation(self):
        self.run_once()
        with core.connect() as c:
            key = c.execute("SELECT key FROM jobs LIMIT 1").fetchone()[0]
            self.assertEqual(core.set_app_status(c, key, "applied")[0], 409)
            self.assertEqual(core.set_app_status(c, key, "shortlisted")[0], 200)
            self.assertEqual(core.set_app_status(c, key, "applied", confirmed=True)[0], 200)
            self.assertEqual(core.set_app_status(c, key, "bogus")[0], 400)

    def test_failed_run_is_recorded_and_writes_no_jobs(self):
        def boom(*a, **k):
            raise core.fd.SearchError("exit=1 down")
        core.fd.search = boom
        r = self.run_once()
        self.assertEqual(r["status"], "failed")
        with core.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)

    def test_unsafe_url_rejected(self):
        rows = fake_rows()
        rows[0]["url"] = "javascript:alert(1)"
        core.fd.search = lambda *a, **k: rows
        self.assertEqual(self.run_once()["new"], 2)

    def test_import_seen_jobs_is_read_only_and_deduplicates(self):
        source = Path(self.tmp.name) / "seen.json"
        source.write_text(json.dumps({"seen": {
            "imported-key": {"url": "https://example.org/job/1", "title": "Python Developer",
                             "company": "Example", "status": "skipped"},
            "bad-key": {"url": "https://", "title": "Unsafe"},
        }}), encoding="utf-8")
        with core.connect() as c:
            self.assertEqual(core.import_seen_jobs(c, source)["imported"], 1)
            self.assertEqual(core.import_seen_jobs(c, source)["imported"], 0)
            row = c.execute("SELECT discovery_status FROM jobs WHERE key='imported-key'").fetchone()
            self.assertEqual(row[0], "skipped")

    def test_import_seen_jobs_handles_wrong_document_shape(self):
        source = Path(self.tmp.name) / "bad.json"
        source.write_text("[]", encoding="utf-8")
        with core.connect() as c:
            self.assertIn("note", core.import_seen_jobs(c, source))

    def test_manual_descriptions_are_versioned_and_never_claim_complete(self):
        self.run_once()
        with core.connect() as c:
            key = c.execute("SELECT key FROM jobs LIMIT 1").fetchone()[0]
            first = core.save_manual_description(c, key, "Python and SQL\r\nBuild data pipelines.")
            same = core.save_manual_description(c, key, "Python and SQL\nBuild data pipelines.")
            second = core.save_manual_description(c, key, "Python and SQL. Build data pipelines with AWS.")
            job = core.get_job(c, key)
            count = c.execute("SELECT COUNT(*) FROM job_description_snapshots WHERE job_key=?", (key,)).fetchone()[0]
        self.assertEqual(first["status"], "manual")
        self.assertTrue(same["unchanged"])
        self.assertEqual(count, 2)
        self.assertEqual(job["description"]["status"], "manual")
        self.assertEqual(job["description"]["method"], "manual_paste")
        self.assertIn("python", [s.lower() for s in job["description_skill_mentions"]])

    def test_description_rejects_empty_oversize_and_unknown_job(self):
        with core.connect() as c:
            self.assertEqual(core.save_manual_description(c, "missing", "body")["http_status"], 404)
        self.run_once()
        with core.connect() as c:
            key = c.execute("SELECT key FROM jobs LIMIT 1").fetchone()[0]
            self.assertEqual(core.save_manual_description(c, key, " ")["http_status"], 400)
            self.assertEqual(core.save_manual_description(c, key, "x" * 100001)["http_status"], 413)

    def test_additive_schema_upgrade_keeps_existing_jobs(self):
        self.run_once()
        with core.connect() as c:
            key = c.execute("SELECT key FROM jobs LIMIT 1").fetchone()[0]
            c.execute("DROP TABLE job_description_snapshots")
        core.init()
        with core.connect() as c:
            self.assertTrue(c.execute("SELECT 1 FROM jobs WHERE key=?", (key,)).fetchone())
            self.assertTrue(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_description_snapshots'").fetchone())

    def test_description_filter_and_pagination_compose(self):
        self.run_once()
        with core.connect() as c:
            keys = [r[0] for r in c.execute("SELECT key FROM jobs ORDER BY key LIMIT 3")]
            core.save_manual_description(c, keys[0], "Python SQL data platform")
            d = core.list_jobs(c, {"description_status": ["manual"], "page": ["1"], "page_size": ["1"]})
        self.assertEqual(d["total"], 1)
        self.assertEqual(d["count"], 1)
        self.assertEqual(d["jobs"][0]["key"], keys[0])


if __name__ == "__main__":
    unittest.main()
