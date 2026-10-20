"""JobHunt core: SQLite store, discovery runs, explainable fit scoring.

Stdlib only. Discovery state and application state live in separate tables, so a
discovered job can never become "applied" by accident.
"""
import json
import os
import re
import sqlite3
import sys
import threading
import hashlib
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import freehire_discover as fd  # noqa: E402  (verified search/classify/collapse)
from job_key import make_key  # noqa: E402

DB_PATH = Path(os.environ.get("JOBHUNT_DB", ROOT / "app" / "data" / "jobhunt.db"))
APP_STATUSES = ["investigating", "shortlisted", "drafting", "ready_for_review", "applied", "assessment",
                "interview", "offer", "hired", "rejected", "withdrawn", "no_response", "offer_declined"]
# These claim something happened outside the app, so the API demands explicit confirmation.
CONFIRM_REQUIRED = {"applied", "assessment", "interview", "offer", "hired", "offer_declined"}
DISCOVERY_STATUSES = ["new", "reviewed", "dismissed", "skipped", "expired"]
RUN_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
  key TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT, url TEXT UNIQUE NOT NULL, location TEXT,
  location_class TEXT, work_mode TEXT, skills TEXT DEFAULT '[]', posted_date TEXT, first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL, last_verified TEXT, source TEXT, alt_listings TEXT DEFAULT '[]', extra TEXT DEFAULT '{}',
  discovery_status TEXT NOT NULL DEFAULT 'new', score INTEGER, score_json TEXT);
CREATE TABLE IF NOT EXISTS applications(
  job_key TEXT PRIMARY KEY REFERENCES jobs(key), status TEXT NOT NULL, notes TEXT DEFAULT '',
  follow_up TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY, job_key TEXT REFERENCES jobs(key), verdict TEXT NOT NULL, reason TEXT, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL, job_key TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS searches(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, queries TEXT NOT NULL, country TEXT DEFAULT 'AE', city TEXT DEFAULT 'dubai',
  jobage INTEGER DEFAULT 14, include_remote INTEGER DEFAULT 1, enabled INTEGER DEFAULT 1, interval_minutes INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY, search_id INTEGER, trigger TEXT, started TEXT, finished TEXT, status TEXT,
  found INTEGER DEFAULT 0, new_jobs INTEGER DEFAULT 0, errors TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS job_description_snapshots(
  id INTEGER PRIMARY KEY, job_key TEXT NOT NULL REFERENCES jobs(key) ON DELETE CASCADE,
  original_text TEXT NOT NULL, normalized_text TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('complete','partial','failed','manual')),
  method TEXT NOT NULL, source_url TEXT, retrieved_at TEXT, content_sha256 TEXT NOT NULL,
  extraction_error TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_description_job ON job_description_snapshots(job_key,id DESC);
CREATE TABLE IF NOT EXISTS tailoring_requests(
  id INTEGER PRIMARY KEY, job_key TEXT NOT NULL REFERENCES jobs(key), idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('not_configured','prepared_for_manual','submitted','running','complete','failed')),
  selected_resume_ref TEXT NOT NULL, payload_json TEXT NOT NULL, external_operation_id TEXT,
  result_document_ref TEXT, result_source TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tailoring_job ON tailoring_requests(job_key,id DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score);
"""

# Seeded ONLY from the skills/roles you listed in your project handover. Edit in the Profile tab.
DEFAULT_PROFILE = {
    "skills": ["python", "sql", "nlp", "deep learning", "genai", "llm", "rag", "embeddings", "prompt engineering",
               "transfer learning", "pytorch", "keras", "hugging face", "langchain", "pandas", "numpy", "flask",
               "mlflow", "dvc", "docker", "github actions", "aws", "ec2", "s3", "lambda"],
    "target_titles": ["AI Engineer", "Machine Learning Engineer", "NLP Engineer", "Generative AI Engineer",
                      "LLM Engineer", "Python Developer", "Data Engineer", "Data Analyst", "MLOps Engineer",
                      "Technical Support Engineer", "Application Support Engineer", "Python Support Engineer"],
    "essential_skills": [], "irrelevant_skills": [],
    "weights": {"skills": 0.35, "role": 0.30, "seniority": 0.15, "location": 0.20},
    "notes": "",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def connect():
    """Yield a configured connection and always close it after committing/rolling back.

    sqlite3.Connection's context manager handles transactions but does not close the
    connection. Closing here matters on Windows, where open handles prevent temporary
    databases and WAL files from being removed after tests or app shutdown.
    """
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    gi = DB_PATH.parent / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")  # private data never reaches the public fork
    with connect() as c:
        c.executescript(SCHEMA)
        if not c.execute("SELECT 1 FROM profile").fetchone():
            c.execute("INSERT INTO profile VALUES(1,?)", (json.dumps(DEFAULT_PROFILE),))
        if not c.execute("SELECT 1 FROM searches").fetchone():
            c.execute("INSERT INTO searches(name,queries) VALUES(?,?)",
                      ("Dubai/UAE tech roles", json.dumps(fd.QUERIES)))


def log(c, kind, job_key=None, detail=""):
    c.execute("INSERT INTO events(ts,kind,job_key,detail) VALUES(?,?,?,?)", (utcnow(), kind, job_key, detail[:500]))


# ------------------------------------------------------------------ scoring
def _n(s: str) -> str:
    return re.sub(r"[^a-z0-9+#]", "", str(s).lower())


SENIOR = ("senior", "sr.", "lead", "principal", "staff", "manager", "head of", "director", "architect")
JUNIOR = ("junior", "jr", "entry", "graduate", "intern", "trainee", "associate", "fresher")
LOC_SCORE = {"dubai": 100, "uae-other": 85, "remote-unverified": 40, "uncertain": 30}


def score_job(job: dict, profile: dict) -> dict:
    """Evidence-backed component scores. Unknown data is labelled and receives a neutral
    ranking value; confidence shows how much of the score has direct evidence."""
    comps = []
    mine = {_n(s) for s in profile.get("skills", [])} - {_n(s) for s in profile.get("irrelevant_skills", [])}
    theirs = {_n(s): s for s in job.get("skills", [])}
    if theirs:
        hit = sorted(theirs[k] for k in theirs if k in mine)
        miss = sorted(theirs[k] for k in theirs if k not in mine)
        ess = [s for s in profile.get("essential_skills", []) if _n(s) in theirs and _n(s) not in mine]
        sc = round(100 * len(hit) / len(theirs))
        if ess:
            sc = min(sc, 30)
        comps.append(("skills", sc, f"You match {len(hit)} of {len(theirs)} tagged skills: {', '.join(hit) or 'none'}",
                      [f"Not in your profile: {', '.join(miss[:8])}"] if miss else []))
    else:
        comps.append(("skills", None, "No skill tags on this listing (description not analysed in v1); counted as a neutral 50", ["skills unknown"]))

    title = (job.get("title") or "").lower()
    ttoks = set(re.findall(r"[a-z0-9+#]+", title))
    best, best_t = 0.0, None
    for t in profile.get("target_titles", []):
        toks = set(re.findall(r"[a-z0-9+#]+", t.lower()))
        if t.lower() in title:
            best, best_t = 1.0, t
            break
        r = len(toks & ttoks) / len(toks) if toks else 0
        if r > best:
            best, best_t = r, t
    rsc = max(15, round(100 * best))  # floor: adjacent roles stay discoverable
    comps.append(("role", rsc, f"Closest target title: {best_t!r}" if best else "No overlap with your target titles",
                  [] if best >= 0.5 else ["Title differs from your targets; check the description"]))

    if any(w in title for w in SENIOR):
        comps.append(("seniority", 25, "Title signals a senior or lead level", ["May exceed your experience; still worth a look if the duties fit"]))
    elif any(w in title for w in JUNIOR):
        comps.append(("seniority", 100, "Title signals junior or entry level", []))
    else:
        comps.append(("seniority", 70, "No seniority signal in title; years required are unknown", ["required experience unknown"]))

    lc = job.get("location_class") or "uncertain"
    comps.append(("location", LOC_SCORE.get(lc, 30), f"Location class: {lc} ({job.get('location') or 'no location text'})",
                  ["Work eligibility not verified"] if lc in ("remote-unverified", "uncertain") else []))
    comps.append(("compensation", None, "No salary data in v1", ["salary unknown"]))

    w = profile.get("weights", {})
    # Unknown data counts as a neutral 50 for ranking (so thin listings cannot outrank well-evidenced
    # ones), and lowers `confidence`, which is shown next to the score.
    used = [(n, 50 if s is None else s, w.get(n, 0)) for n, s, _, _ in comps if w.get(n, 0) > 0]
    tw = sum(x[2] for x in used) or 1
    overall = round(sum(s * wt for _, s, wt in used) / tw)
    known_w = sum(w.get(n, 0) for n, s, _, _ in comps if s is not None)
    conf = round(100 * known_w / (sum(w.values()) or 1))
    return {"overall": overall, "confidence": conf,
            "components": [{"name": n, "score": s, "weight": w.get(n, 0), "evidence": e, "missing": m} for n, s, e, m in comps],
            "note": "Resume/job similarity from structured tags only. Not an ATS score and not a hiring prediction."}


def get_profile(c) -> dict:
    return json.loads(c.execute("SELECT data FROM profile").fetchone()[0])


def rescore_all(c) -> int:
    prof = get_profile(c)
    rows = c.execute("SELECT * FROM jobs").fetchall()
    for r in rows:
        s = score_job(_job_dict(r), prof)
        c.execute("UPDATE jobs SET score=?, score_json=? WHERE key=?", (s["overall"], json.dumps(s), r["key"]))
    return len(rows)


def _job_dict(r) -> dict:
    d = dict(r)
    for f in ("skills", "alt_listings", "extra", "score_json"):
        d[f] = json.loads(d[f]) if d.get(f) else ([] if f in ("skills", "alt_listings") else {})
    return d


# --------------------------------------------------------------- discovery
def _safe_url(u: str) -> bool:
    from urllib.parse import urlsplit
    if not isinstance(u, str):
        return False
    try:
        p = urlsplit(u.strip())
        return p.scheme.lower() in ("http", "https") and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def run_discovery(search_id: int | None, trigger: str = "manual") -> dict:
    if not RUN_LOCK.acquire(blocking=False):
        return {"error": "a run is already in progress"}
    try:
        with connect() as c:
            s = c.execute("SELECT * FROM searches WHERE id=?", (search_id,)).fetchone() if search_id else \
                c.execute("SELECT * FROM searches WHERE enabled=1 ORDER BY id LIMIT 1").fetchone()
            if not s:
                return {"error": "no such search"}
            rid = c.execute("INSERT INTO runs(search_id,trigger,started,status) VALUES(?,?,?,'running')",
                            (s["id"], trigger, utcnow())).lastrowid
            c.commit()
        return _execute(s, rid)
    finally:
        RUN_LOCK.release()


def _execute(s, rid) -> dict:
    today = date.today()
    cutoff = today - timedelta(days=s["jobage"])
    passes = [(s["country"], False)] + ([(None, True)] if s["include_remote"] else [])
    collected, errors, fails, found = [], [], 0, 0
    for q in json.loads(s["queries"]):
        for country, remote in passes:
            if fails >= 3:
                errors.append("aborted after 3 consecutive failures (service likely down)")
                break
            try:
                rows = fd.search(q, jobage=s["jobage"], limit=25, pages=1, country=country, remote=remote)
                fails = 0
            except fd.SearchError as exc:
                errors.append(f"{q}: {str(exc).splitlines()[0][:200]}")
                fails += 1
                continue
            found += len(rows)
            for r in rows:
                cls = fd.classify(r, s["country"].upper(), s["city"].lower())
                if cls and fd.posted_ok(r, cutoff) and r.get("title") and _safe_url(r.get("url")):
                    r["_class"] = cls
                    collected.append(r)
        if fails >= 3:
            break
    jobs = fd.collapse(collected)
    new = 0
    with connect() as c:
        prof = get_profile(c)
        for j in jobs:
            now = utcnow()
            hit = c.execute("SELECT key FROM jobs WHERE key=? OR url=?", (j["_key"], j["url"])).fetchone()
            if hit:
                c.execute("UPDATE jobs SET last_seen=?, last_verified=? WHERE key=?", (now, now, hit["key"]))
                continue
            row = {"title": j["title"], "company": j.get("company") or "", "location_class": j["_class"],
                   "location": j.get("location"), "skills": j.get("skills") or []}
            sc = score_job(row, prof)
            c.execute("""INSERT INTO jobs(key,title,company,url,location,location_class,work_mode,skills,posted_date,
                         first_seen,last_seen,last_verified,source,alt_listings,score,score_json)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (j["_key"], j["title"], j.get("company") or "", j["url"], j.get("location"), j["_class"],
                       j.get("work_mode"), json.dumps(j.get("skills") or []), j.get("date"), now, now, now,
                       fd.PORTAL, json.dumps(j.get("_alts", [])), sc["overall"], json.dumps(sc)))
            new += 1
        status = "failed" if errors and not collected else ("partial" if errors else "complete")
        c.execute("UPDATE runs SET finished=?,status=?,found=?,new_jobs=?,errors=? WHERE id=?",
                  (utcnow(), status, len(jobs), new, json.dumps(errors), rid))
        log(c, "run", None, f"run {rid} {status}: {len(jobs)} jobs, {new} new, {len(errors)} errors")
    return {"run_id": rid, "status": status, "jobs": len(jobs), "new": new, "errors": errors}


def import_seen_jobs(c, path: Path | None = None) -> dict:
    """Read-only import of the repo's seen_jobs.json. Never writes back to it."""
    path = path or ROOT / "job_scraper" / "seen_jobs.json"
    if not path.is_file():
        return {"imported": 0, "note": f"{path.name} not found"}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return {"imported": 0, "note": "invalid seen_jobs.json format"}
    seen = doc.get("seen", doc)
    if not isinstance(seen, dict):
        return {"imported": 0, "note": "invalid seen_jobs.json format"}
    prof, n = get_profile(c), 0
    for key, e in seen.items():
        if not isinstance(e, dict) or not isinstance(key, str) or not key or not e.get("title") or not _safe_url(e.get("url", "")) or c.execute("SELECT 1 FROM jobs WHERE key=? OR url=?", (key, e["url"])).fetchone():
            continue
        status = {"skipped": "skipped", "expired": "expired"}.get(e.get("status"), "new")
        extra = {k: e[k] for k in ("rank_score", "rank_verdict", "location_verdict", "strengths", "gaps") if k in e}
        row = {"title": e.get("title", ""), "company": e.get("company", ""), "skills": [],
               "location_class": e.get("location_class") or "uncertain", "location": e.get("location")}
        sc = score_job(row, prof)
        c.execute("""INSERT INTO jobs(key,title,company,url,location,location_class,posted_date,first_seen,last_seen,
                     source,extra,discovery_status,score,score_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (key, row["title"], row["company"], e["url"], row["location"], row["location_class"],
                   e.get("posted_date"), e.get("first_seen") or utcnow()[:10], e.get("first_seen") or utcnow()[:10],
                   e.get("portal", "import"), json.dumps(extra), status, sc["overall"], json.dumps(sc)))
        n += 1
    log(c, "import", None, f"imported {n} from seen_jobs.json")
    return {"imported": n}


# ------------------------------------------------------------------ queries
def list_jobs(c, q: dict) -> dict:
    where, args = ["1=1"], []
    g = lambda k: (q.get(k) or [""])[0]
    if g("q"):
        where.append("(title LIKE ? OR company LIKE ?)"); args += [f"%{g('q')}%"] * 2
    if g("status"):
        where.append("discovery_status=?"); args.append(g("status"))
    if g("loc"):
        where.append("location_class=?"); args.append(g("loc"))
    if g("min_score"):
        where.append("score>=?"); args.append(int(g("min_score")))
    if g("since"):
        where.append("first_seen>=?"); args.append(g("since"))
    if g("stale"):
        where.append("last_seen<? AND discovery_status IN ('new','reviewed')")
        args.append((date.today() - timedelta(days=14)).isoformat())
    if g("app"):
        where.append("key IN (SELECT job_key FROM applications WHERE status=?)"); args.append(g("app"))
    if g("untracked"):
        where.append("key NOT IN (SELECT job_key FROM applications)")
    if g("tailored"):
        where.append("key IN (SELECT job_key FROM tailoring_requests)")
    if g("description_status"):
        where.append("(SELECT status FROM job_description_snapshots d WHERE d.job_key=j.key ORDER BY id DESC LIMIT 1)=?")
        args.append(g("description_status"))
    if g("source"):
        where.append("source=?"); args.append(g("source"))
    try:
        page = max(1, int(g("page") or 1))
        page_size = min(100, max(1, int(g("page_size") or 50)))
    except ValueError:
        page, page_size = 1, 50
    order = {"new": "first_seen DESC, score DESC", "posted": "posted_date DESC"}.get(g("sort"), "score DESC, first_seen DESC")
    sql = f"""SELECT j.key,title,company,url,location,location_class,posted_date,first_seen,last_seen,discovery_status,
              score,source,(SELECT status FROM applications a WHERE a.job_key=j.key) AS app_status,
              (SELECT status FROM job_description_snapshots d WHERE d.job_key=j.key ORDER BY id DESC LIMIT 1) AS description_status
              FROM jobs j
              WHERE {' AND '.join(where)} ORDER BY {order} LIMIT 300"""
    count = c.execute(f"SELECT COUNT(*) FROM jobs j WHERE {' AND '.join(where)}", args).fetchone()[0]
    rows = [dict(r) for r in c.execute(sql.replace("LIMIT 300", "LIMIT ? OFFSET ?"), (*args, page_size, (page - 1) * page_size))]
    return {"jobs": rows, "count": len(rows), "total": count, "page": page, "page_size": page_size}


def list_applications(c, q: dict) -> dict:
    """Return persisted applications joined to their source jobs with composable filters."""
    where, args = ["1=1"], []
    g = lambda k: (q.get(k) or [""])[0]
    if g("q"):
        where.append("(j.title LIKE ? OR j.company LIKE ?)")
        args += [f"%{g('q')}%"] * 2
    if g("status"):
        where.append("a.status=?")
        args.append(g("status"))
    stage = g("stage")
    if stage == "prepared":
        where.append("a.status IN ('drafting','ready_for_review')")
    elif stage == "submitted":
        where.append("a.status IN ('applied','assessment','interview','offer','hired','rejected','withdrawn','no_response','offer_declined')")
    elif stage == "offer":
        where.append("a.status IN ('offer','hired','offer_declined')")
    follow = g("follow_up")
    today = date.today().isoformat()
    if follow == "overdue":
        where.append("a.follow_up < ? AND a.follow_up IS NOT NULL")
        args.append(today)
    elif follow == "upcoming":
        where.append("a.follow_up BETWEEN ? AND ?")
        args.extend([today, (date.today() + timedelta(days=7)).isoformat()])
    elif follow == "none":
        where.append("a.follow_up IS NULL OR a.follow_up = ''")
    try:
        page = max(1, int(g("page") or 1))
        page_size = min(100, max(1, int(g("page_size") or 50)))
    except ValueError:
        page, page_size = 1, 50
    predicate = " AND ".join(f"({w})" if " OR " in w else w for w in where)
    total = c.execute(f"SELECT COUNT(*) FROM applications a JOIN jobs j ON j.key=a.job_key WHERE {predicate}", args).fetchone()[0]
    rows = [dict(r) for r in c.execute(f"""SELECT a.job_key,j.title,j.company,j.url,j.location,j.location_class,
        a.status,a.notes,a.follow_up,a.updated_at
        FROM applications a JOIN jobs j ON j.key=a.job_key
        WHERE {predicate} ORDER BY CASE WHEN a.follow_up IS NULL THEN 1 ELSE 0 END,a.follow_up,a.updated_at DESC
        LIMIT ? OFFSET ?""", (*args, page_size, (page - 1) * page_size))]
    return {"applications": rows, "count": len(rows), "total": total, "page": page, "page_size": page_size}


def get_job(c, key: str):
    r = c.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone()
    if not r:
        return None
    d = _job_dict(r)
    a = c.execute("SELECT * FROM applications WHERE job_key=?", (key,)).fetchone()
    d["application"] = dict(a) if a else None
    d["feedback"] = [dict(x) for x in c.execute("SELECT verdict,reason,ts FROM feedback WHERE job_key=? ORDER BY id DESC", (key,))]
    d["history"] = [dict(x) for x in c.execute("SELECT ts,kind,detail FROM events WHERE job_key=? ORDER BY id DESC LIMIT 30", (key,))]
    desc = c.execute("SELECT * FROM job_description_snapshots WHERE job_key=? ORDER BY id DESC LIMIT 1", (key,)).fetchone()
    d["description"] = dict(desc) if desc else None
    if desc:
        profile_skills = get_profile(c).get("skills", [])
        d["description_skill_mentions"] = [skill for skill in profile_skills
            if re.search(r"(?<![\\w])" + re.escape(skill) + r"(?![\\w])", desc["normalized_text"], re.I)]
    else:
        d["description_skill_mentions"] = []
    d["tailoring_requests"] = [dict(x) for x in c.execute(
        "SELECT id,status,selected_resume_ref,result_document_ref,result_source,error,created_at,updated_at FROM tailoring_requests WHERE job_key=? ORDER BY id DESC", (key,))]
    return d


def save_manual_description(c, key: str, content: str) -> dict:
    """Persist user-pasted description text as manual, immutable snapshots.

    Manual content is never labelled complete because JobHunt cannot verify it against
    the source posting. HTML is stored as text and the UI renders text nodes only.
    """
    job = c.execute("SELECT url FROM jobs WHERE key=?", (key,)).fetchone()
    if not job:
        return {"error": "unknown job", "http_status": 404}
    if not isinstance(content, str):
        return {"error": "description must be text", "http_status": 400}
    original = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not original:
        return {"error": "description cannot be empty", "http_status": 400}
    if len(original) > 100_000:
        return {"error": "description exceeds 100000 characters", "http_status": 413}
    normalized = "\n".join(line.strip() for line in original.split("\n")).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    current = c.execute("SELECT id,content_sha256 FROM job_description_snapshots WHERE job_key=? ORDER BY id DESC LIMIT 1", (key,)).fetchone()
    if current and current["content_sha256"] == digest:
        return {"ok": True, "snapshot_id": current["id"], "unchanged": True, "status": "manual"}
    now = utcnow()
    cur = c.execute("""INSERT INTO job_description_snapshots
      (job_key,original_text,normalized_text,status,method,source_url,retrieved_at,content_sha256,created_at)
      VALUES(?,?,?,'manual','manual_paste',?,?,?,?)""",
      (key, original, normalized, job["url"], now, digest, now))
    log(c, "description", key, "manual job description saved")
    return {"ok": True, "snapshot_id": cur.lastrowid, "unchanged": False, "status": "manual"}


def create_tailoring_request(c, key: str, resume_ref: str, idempotency_key: str) -> dict:
    """Persist a local tailoring handoff. Never claims a remote service was called."""
    prior = c.execute("SELECT * FROM tailoring_requests WHERE idempotency_key=?", (idempotency_key,)).fetchone()
    if prior:
        if prior["job_key"] != key or prior["selected_resume_ref"] != resume_ref:
            return {"error": "idempotency_key is already bound to a different job or resume", "http_status": 409}
        result = dict(prior)
        result["payload"] = json.loads(result.pop("payload_json"))
        result["reused"] = True
        return result
    job = c.execute("SELECT key,title,company,url FROM jobs WHERE key=?", (key,)).fetchone()
    if not job:
        return {"error": "unknown job", "http_status": 404}
    desc = c.execute("SELECT * FROM job_description_snapshots WHERE job_key=? ORDER BY id DESC LIMIT 1", (key,)).fetchone()
    if not desc:
        return {"error": "save a job description before preparing a tailoring request", "http_status": 409}
    payload = {
        "schema_version": 1,
        "job": {"id": job["key"], "title": job["title"], "company": job["company"],
                "source_url": job["url"], "description": desc["original_text"],
                "description_status": desc["status"], "description_source_url": desc["source_url"]},
        "resume_reference": resume_ref,
    }
    now = utcnow()
    cur = c.execute("""INSERT INTO tailoring_requests
      (job_key,idempotency_key,status,selected_resume_ref,payload_json,created_at,updated_at)
      VALUES(?,?,'not_configured',?,?,?,?)""",
      (key, idempotency_key, resume_ref, json.dumps(payload, ensure_ascii=False), now, now))
    log(c, "tailoring", key, f"tailoring request {cur.lastrowid} prepared; Resume Matcher not configured")
    return {"id": cur.lastrowid, "job_key": key, "idempotency_key": idempotency_key, "status": "not_configured",
            "selected_resume_ref": resume_ref, "payload": payload, "created_at": now, "updated_at": now, "reused": False}


def overview(c) -> dict:
    today, week = date.today().isoformat(), (date.today() - timedelta(days=7)).isoformat()
    next_week = (date.today() + timedelta(days=7)).isoformat()
    one = lambda sql, *a: c.execute(sql, a).fetchone()[0]
    last = c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    lastok = c.execute("SELECT finished FROM runs WHERE status IN ('complete','partial') ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "new_today": one("SELECT COUNT(*) FROM jobs WHERE first_seen>=?", today),
        "new_week": one("SELECT COUNT(*) FROM jobs WHERE first_seen>=?", week),
        "awaiting_review": one("SELECT COUNT(*) FROM jobs WHERE discovery_status='new'"),
        "stale": one("SELECT COUNT(*) FROM jobs WHERE last_seen<? AND discovery_status IN ('new','reviewed')",
                     (date.today() - timedelta(days=14)).isoformat()),
        "total": one("SELECT COUNT(*) FROM jobs"),
        "shortlisted": one("SELECT COUNT(*) FROM applications WHERE status='shortlisted'"),
        "fit_analyses": one("SELECT COUNT(*) FROM jobs WHERE score_json IS NOT NULL"),
        "applications_prepared": one("SELECT COUNT(*) FROM applications WHERE status IN ('drafting','ready_for_review')"),
        "applications_submitted": one("SELECT COUNT(*) FROM applications WHERE status IN ('applied','assessment','interview','offer','hired','rejected','withdrawn','no_response','offer_declined')"),
        "interviews": one("SELECT COUNT(*) FROM applications WHERE status='interview'"),
        "offers": one("SELECT COUNT(*) FROM applications WHERE status IN ('offer','hired','offer_declined')"),
        "overdue_followups": one("SELECT COUNT(*) FROM applications WHERE follow_up IS NOT NULL AND follow_up!='' AND follow_up<? AND status NOT IN ('hired','rejected','withdrawn','no_response','offer_declined')", today),
        "upcoming_followups": one("SELECT COUNT(*) FROM applications WHERE follow_up BETWEEN ? AND ? AND status NOT IN ('hired','rejected','withdrawn','no_response','offer_declined')", today, next_week),
        "by_location": {r[0]: r[1] for r in c.execute("SELECT location_class,COUNT(*) FROM jobs GROUP BY 1")},
        "applications": {r[0]: r[1] for r in c.execute("SELECT status,COUNT(*) FROM applications GROUP BY 1")},
        "descriptions": {
            "manual": one("SELECT COUNT(*) FROM (SELECT job_key,status,ROW_NUMBER() OVER(PARTITION BY job_key ORDER BY id DESC) n FROM job_description_snapshots) WHERE n=1 AND status='manual'"),
            "complete": one("SELECT COUNT(*) FROM (SELECT job_key,status,ROW_NUMBER() OVER(PARTITION BY job_key ORDER BY id DESC) n FROM job_description_snapshots) WHERE n=1 AND status='complete'"),
            "partial": one("SELECT COUNT(*) FROM (SELECT job_key,status,ROW_NUMBER() OVER(PARTITION BY job_key ORDER BY id DESC) n FROM job_description_snapshots) WHERE n=1 AND status='partial'"),
            "failed": one("SELECT COUNT(*) FROM (SELECT job_key,status,ROW_NUMBER() OVER(PARTITION BY job_key ORDER BY id DESC) n FROM job_description_snapshots) WHERE n=1 AND status='failed'"),
        },
        "tailoring": {
            "total": one("SELECT COUNT(*) FROM tailoring_requests"),
            "not_configured": one("SELECT COUNT(*) FROM tailoring_requests WHERE status='not_configured'"),
            "complete": one("SELECT COUNT(*) FROM tailoring_requests WHERE status='complete'"),
            "failed": one("SELECT COUNT(*) FROM tailoring_requests WHERE status='failed'"),
        },
        "top": [dict(r) for r in c.execute("""SELECT key,title,company,score,location_class FROM jobs
                 WHERE discovery_status IN ('new','reviewed') AND key NOT IN (SELECT job_key FROM applications)
                 ORDER BY score DESC, first_seen DESC LIMIT 8""")],
        "last_run": dict(last) if last else None,
        "last_success": lastok[0] if lastok else None,
        "failed_runs_7d": one("SELECT COUNT(*) FROM runs WHERE status IN ('failed','partial') AND started>=?", week),
    }


def set_app_status(c, key, status, notes=None, follow_up=None, confirmed=False):
    if not c.execute("SELECT 1 FROM jobs WHERE key=?", (key,)).fetchone():
        return 404, {"error": "unknown job"}
    if status not in APP_STATUSES:
        return 400, {"error": f"status must be one of {APP_STATUSES}"}
    if status in CONFIRM_REQUIRED and not confirmed:
        return 409, {"error": f"'{status}' records something that happened outside this app. Resend with confirmed=true once it is true."}
    c.execute("""INSERT INTO applications(job_key,status,notes,follow_up,updated_at) VALUES(?,?,?,?,?)
                 ON CONFLICT(job_key) DO UPDATE SET status=excluded.status,
                 notes=COALESCE(?,notes), follow_up=COALESCE(?,follow_up), updated_at=excluded.updated_at""",
              (key, status, notes or "", follow_up, utcnow(), notes, follow_up))
    log(c, "status", key, f"application status -> {status}")
    return 200, {"ok": True}
