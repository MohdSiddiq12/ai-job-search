# Stage C.3 — Application Tracking and Status Audit

**Date:** 2026-10-19  
**Role:** Backend / Data Auditor for JobHunt + Resume Matcher Integration  
**Mode:** Read-only audit and design specification. No migration code executed, no database modified, and no application records touched.

---

## 1. Preflight and Environment Baseline

Preflight checks were executed strictly in read-only mode prior to code and schema inspection. No services were started, stopped, or modified.

### 1.1 Repository and Branch Status (Observed Now)
- **JobHunt Original** (`D:\AI-Job\ai-job-search`):
  - Current Branch: `master`
  - Working Tree Status: Untracked directories/files present (`?? .opencode/`, `?? app/`, `?? docs/`, `?? files.zip`, `?? tests/test_app_core.py`, `?? tests/test_app_server.py`, `?? tests/test_resume_matcher_adapter.py`). Unmodified application code; left untouched.
- **JobHunt Integration Worktree** (`D:\AI-Job\ai-job-search-integration`):
  - Current Branch: `integration/resume-matcher-foundation`
  - Working Tree Status: Same untracked baseline; destination for all integration documentation.
- **Resume Matcher** (`D:\Resume-Matcher\Resume-Matcher`):
  - Current Branch: `deployment-hardening`
  - Working Tree Status: Modified existing files (`apps/backend/app/main.py`, `apps/backend/app/routers/__init__.py`, `apps/frontend/components/home/swiss-grid.tsx`, localization messages, and tests); uncommitted Stage C.1 and C.2 discovery additions present (`apps/backend/app/routers/jobhunt_discovery.py`, `apps/backend/app/schemas/jobhunt_discovery.py`, `apps/backend/app/services/jobhunt_snapshot.py`, `apps/frontend/app/(default)/discover/`, `apps/frontend/components/discovery/`).

### 1.2 Disposable Snapshot Integrity (Observed Now)
- **Snapshot Path:** `D:\AI-Job\stage-c-pilot\jobhunt_snapshot.sqlite`
- **Computed SHA-256 (Observed Now):**
  `1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b`
- **Comparison to Historical Reference:** Matches historical hash `1541e113ea6a3fcf2f5c30aee008d715f281aea62984168aa74c08d45d2bfd7b` *(historical, not guaranteed)*.
- **Inspection Protocol:** Opened exclusively via SQLite URI with `?mode=ro` and `PRAGMA query_only = ON;`. The live database `app/data/jobhunt.db` was not opened.

### 1.3 Local Network Port State (Observed Now)
- **Port 8013 (Resume Matcher Backend):** `127.0.0.1:8013` is active (State: `FinWait1` / `Established`, PID 18132).
- **Port 3013 (Resume Matcher Frontend):** `127.0.0.1:3013` is active (State: `Established`, PID 23528).
- **Action Taken:** Neither port was interrupted, restarted, or altered.

---

## 2. JobHunt Application Tracking Architecture (Established from Source)

The architecture and behavior of JobHunt's application tracking were established strictly by analyzing `app/core.py`, `app/server.py`, `app/static/index.html`, and `tests/test_app_core.py`.

### 2.1 Database Schema and Tables
JobHunt stores application state across two primary tables, plus peripheral auditing and workflow tables:

```sql
-- Core Applications Table
CREATE TABLE applications (
  job_key TEXT PRIMARY KEY REFERENCES jobs(key),
  status TEXT NOT NULL,
  notes TEXT DEFAULT '',
  follow_up TEXT,
  updated_at TEXT NOT NULL
);

-- Event Audit Log
CREATE TABLE events (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  job_key TEXT,
  detail TEXT
);

-- Feedback Table
CREATE TABLE feedback (
  id INTEGER PRIMARY KEY,
  job_key TEXT REFERENCES jobs(key),
  verdict TEXT NOT NULL,
  reason TEXT,
  ts TEXT NOT NULL
);

-- Job Description Snapshots
CREATE TABLE job_description_snapshots (
  id INTEGER PRIMARY KEY,
  job_key TEXT NOT NULL REFERENCES jobs(key) ON DELETE CASCADE,
  original_text TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('complete','partial','failed','manual')),
  method TEXT NOT NULL,
  source_url TEXT,
  retrieved_at TEXT,
  content_sha256 TEXT NOT NULL,
  extraction_error TEXT,
  created_at TEXT NOT NULL
);

-- Tailoring Handoff Requests
CREATE TABLE tailoring_requests (
  id INTEGER PRIMARY KEY,
  job_key TEXT NOT NULL REFERENCES jobs(key),
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('not_configured','prepared_for_manual','submitted','running','complete','failed')),
  selected_resume_ref TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  external_operation_id TEXT,
  result_document_ref TEXT,
  result_source TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### 2.2 Primary and Foreign Keys, Relations to Jobs
- **Primary Key:** `applications.job_key` is the primary key. JobHunt uses no surrogate integer or UUID column for applications.
- **Foreign Key:** `applications.job_key` references `jobs(key)`. Enforced when `PRAGMA foreign_keys = ON;` is set.
- **Cardinality:** Exactly 1-to-0..1 relationship. Each job in `jobs` has at most one corresponding tracking row in `applications`. A job cannot have multiple concurrent applications.
- **External References to Applications:** No external table references `applications(job_key)` directly. Foreign references in `events`, `feedback`, `job_description_snapshots`, and `tailoring_requests` all reference `jobs(key)`.

### 2.3 Status Taxonomy and Semantic Meanings
JobHunt defines 13 application statuses in `core.APP_STATUSES`:
1. `investigating`: Initial research into the role and company fit.
2. `shortlisted`: Qualified as a high-potential opportunity to pursue.
3. `drafting`: Application materials (tailored resume, cover letter) are currently being assembled.
4. `ready_for_review`: Application materials are complete and awaiting final applicant verification.
5. `applied`: Application has been submitted externally to the employer or recruiter.
6. `assessment`: Employer has issued a screening test, take-home task, or technical questionnaire.
7. `interview`: Screening, technical, or behavioral interviews are scheduled or ongoing.
8. `offer`: A formal written or verbal job offer has been extended by the employer.
9. `hired`: Offer accepted and employment finalized.
10. `rejected`: Application or interview process was rejected by the employer.
11. `withdrawn`: Applicant voluntarily withdrew their application.
12. `no_response`: Employer failed to respond within a standard window after submission.
13. `offer_declined`: Formal job offer was declined by the applicant.

#### Confirmation Requirements (`CONFIRM_REQUIRED`)
Six statuses represent events occurring outside the local application in the physical/external world:
`{"applied", "assessment", "interview", "offer", "hired", "offer_declined"}`
- When an API caller attempts to update a status to any of these six values without `confirmed=True`, `app/server.py` and `app/core.py` reject the request with **HTTP 409 Conflict**:
  `"'{status}' records something that happened outside this app. Resend with confirmed=true once it is true."`

#### Stage Aggregations in JobHunt Queries
JobHunt aggregates statuses into three logical stage filters in `list_applications`:
- `prepared`: `drafting`, `ready_for_review`
- `submitted`: `applied`, `assessment`, `interview`, `offer`, `hired`, `rejected`, `withdrawn`, `no_response`, `offer_declined`
- `offer`: `offer`, `hired`, `offer_declined`

### 2.4 Status Persistence and Event Logging
- **Persistence Method:** `core.set_app_status(c, key, status, notes=None, follow_up=None, confirmed=False)`.
- **Atomic Upsert:**
  ```sql
  INSERT INTO applications(job_key, status, notes, follow_up, updated_at)
  VALUES (?, ?, ?, ?, ?)
  ON CONFLICT(job_key) DO UPDATE SET
    status = excluded.status,
    notes = COALESCE(?, notes),
    follow_up = COALESCE(?, follow_up),
    updated_at = excluded.updated_at
  ```
- **Event Audit Log:** On every status change, JobHunt writes an entry to `events`:
  ```sql
  INSERT INTO events(ts, kind, job_key, detail)
  VALUES (utcnow(), 'status', key, 'application status -> ' || status)
  ```
- **Status History Existence:** JobHunt **does not** maintain a dedicated `application_status_history` table. The current status in `applications.status` is overwritten on each change. Historical transitions can only be reconstructed by parsing the `events` table where `kind = 'status'` and `detail LIKE 'application status -> %'`.

### 2.5 Notes, Follow-up Dates, and Timestamps
- `notes`: `TEXT DEFAULT ''`. `app/server.py` validates `notes` as text up to 10,000 characters. If omitted during updates, the existing note is preserved via `COALESCE(?, notes)`.
- `follow_up`: `TEXT` nullable. Validated in `server.py` to be either empty or an ISO date matching format `YYYY-MM-DD` (`date.fromisoformat(val).isoformat() == val`).
  - Filtered in `list_applications`:
    - `overdue`: `follow_up < today AND follow_up IS NOT NULL AND follow_up != ''`
    - `upcoming`: `follow_up BETWEEN today AND today + 7 days`
    - `none`: `follow_up IS NULL OR follow_up = ''`
  - Filtered in `overview()` to exclude resolved applications: terminal statuses (`hired`, `rejected`, `withdrawn`, `no_response`, `offer_declined`) are excluded from overdue/upcoming follow-up counts.
- `updated_at`: `TEXT NOT NULL`. Set via `core.utcnow()` formatted strictly as UTC ISO-8601: `%Y-%m-%dT%H:%M:%SZ`.

### 2.6 Duplicate Handling and Unmappable Records
- **Duplicate Prevention:** Enforced at the SQLite engine level by `PRIMARY KEY (job_key)` on `applications`. Re-submitting an application for an existing job key is handled cleanly by the upsert logic.
- **Orphan Prevention:** Enforced by foreign key `REFERENCES jobs(key)`. An application cannot be saved for a nonexistent job key (raises HTTP 404 in `server.py` and SQLite FK violation on low-level insert).

### 2.7 Current Snapshot Application Data (Observed Now)
Inspection of `D:\AI-Job\stage-c-pilot\jobhunt_snapshot.sqlite` via read-only connection reveals:
- Total `applications` rows: **2**
  1. `job_key`: `'mitgo_middle-python-developer'`, `status`: `'investigating'`, `notes`: `'how to apply'`, `follow_up`: `None`, `updated_at`: `'2026-10-18T20:44:29Z'`
  2. `job_key`: `'vps-elite-human-resources-consultancies-a40bae_ai-software-engineer'`, `status`: `'investigating'`, `notes`: `''`, `follow_up`: `''`, `updated_at`: `'2026-10-18T22:53:43Z'`
- Total `events` rows: **6** (Event IDs 3 and 6 document the transition to `investigating` for both applications).
- Total `jobs` rows: **244**
- Total `job_description_snapshots` rows: **0**
- Total `tailoring_requests` rows: **0**

---

## 3. Resume Matcher Application Tracking Architecture (Established from Source)

The architecture and behavior of Resume Matcher's application tracking were established strictly by analyzing `apps/backend/app/models.py`, `apps/backend/app/database.py`, `apps/backend/app/schemas/applications.py`, `apps/backend/app/routers/applications.py`, and integration test suites.

### 3.1 Database Schema and Models
Resume Matcher's application tracking is modeled in SQLAlchemy and persisted in SQLite (or optional PostgreSQL):

```python
class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "resume_id", name="uq_application_job_resume"),
    )

    application_id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    resume_id: Mapped[str] = mapped_column(String, index=True)
    master_resume_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="applied", index=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_at: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=_utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String, default=_utcnow_iso)
```

Peripheral models related to applications:
- `Job` (`jobs`): `job_id` (String PK), `content` (Text), `resume_id` (String NULL), `created_at` (String), `metadata_json` (JSON dict).
- `Resume` (`resumes`): `resume_id` (String PK), `content` (Text), `is_master` (Boolean), `is_default_master` (Boolean), `parent_id` (String NULL), `processed_data` (JSON).
- `Improvement` (`improvements`): `request_id` (String PK), `original_resume_id`, `tailored_resume_id`, `job_id`, `improvements`, `ats_score`, `created_at`.
- `TailoringPreview` (`tailoring_previews`): transient preview handshake tracking `preview_id`, `job_id`, `source_id`, `claim_token`, `expires_at`.

### 3.2 Primary and Foreign Keys, Relations to Jobs and Resumes
- **Primary Key:** `application_id`, a generated UUID string (`str(uuid4())`).
- **Foreign Keys / Relations:**
  - `job_id`: Non-null string referencing `jobs.job_id`.
  - `resume_id`: Non-null string referencing `resumes.resume_id` (the tailored/applied resume).
  - `master_resume_id`: Nullable string referencing `resumes.resume_id` (the base career track).
- **Cardinality & Constraints:**
  - `UniqueConstraint("job_id", "resume_id", name="uq_application_job_resume")`.
  - Exactly one application card per `(job_id, resume_id)` pair.
  - Unlike JobHunt, where an application belongs only to a job, Resume Matcher's application card is inherently bound to a specific tailored resume.

### 3.3 Status Taxonomy and Kanban Board Columns
Resume Matcher defines exactly 7 application statuses in `ApplicationStatus` (`apps/backend/app/schemas/applications.py`):
1. `saved`: Stored opportunity; not yet submitted.
2. `applied`: Application submitted.
3. `no_response`: No employer response received.
4. `response`: Employer acknowledged or contacted candidate.
5. `interview`: Screening or interview underway.
6. `accepted`: Job offer accepted.
7. `rejected`: Candidate rejected.

- **Board Column Ordering:** Rendered in strict order:
  `APPLICATION_STATUS_ORDER = ["saved", "applied", "no_response", "response", "interview", "accepted", "rejected"]`
- **Missing/Unknown Status Handling:** `apps/backend/app/routers/applications.py` explicitly drops cards with unrecognized statuses during board rendering:
  ```python
  if status not in columns:
      logger.warning("Skipping application with unknown status %r", status)
      continue
  ```
  Unknown statuses cause cards to vanish from the UI canvas rather than generating HTTP 500 errors.

### 3.4 Card Positioning and Server-Side Renumbering
- `position`: An integer tracking vertical order within a Kanban column (0..N-1).
- `update_application`: When a card moves between columns or changes position, `database.py` temporarily sets `row.position = 10_000_000`, flushes the session, and renumbers both the source and target columns to guarantee contiguous 0..N-1 indexing.

### 3.5 Timestamps and Automatic `applied_at` Assignment
- All timestamps (`created_at`, `updated_at`, `applied_at`) are stored as lexical ISO-8601 UTC strings via `datetime.now(timezone.utc).isoformat()`.
- **Automatic Applied Timestamp Rule:** In `_insert_application` and `update_application`:
  ```python
  if applied_at is None and status != "saved":
      applied_at = now
  ```
  Moving a card out of `saved` to any other status automatically populates `applied_at` with the current timestamp if previously null.

### 3.6 Automated Card Creation during Tailoring Handoff
In `apps/backend/tests/integration/test_tracker_autocreate.py` and the tailoring pipeline (`/api/v1/resumes/improve/confirm`), confirming a tailored resume automatically invokes `db.create_application(...)` with `status="applied"`.
- **Architectural Conflict:** This behavior directly contradicts JobHunt's core design invariant ("generating a resume or starting a draft must NEVER set 'applied'; only verified submission does").

### 3.7 Absence of Follow-up and History Structures
- **No Follow-up Field:** Resume Matcher's `applications` table has no `follow_up` date column.
- **No Event History:** Resume Matcher possesses no `events` or status history table. The application row is modified in place; previous statuses are lost upon update.

### 3.8 Authentication and Session Model
- Configured in `apps/backend/app/auth.py`.
- In `APP_ENV=development` (local dev mode on loopback), authentication middleware is bypassed completely.
- In hosted/production mode, auth relies on a single shared administrative password (`APP_AUTH_PASSWORD`), verified via scrypt, issuing an HMAC-signed `rm_session` cookie and CSRF token (`rm_csrf`).
- Sessions are stored in a process-local in-memory dictionary (`_sessions`).
- **No Multi-User Accounts:** There is no multi-user schema, no user ID column on `applications`, and no tenant identifier.

---

## 4. Cross-System Architectural and Semantic Comparison

| Dimension | JobHunt (`ai-job-search`) | Resume Matcher (`Resume-Matcher`) | Architectural Gap / Risk |
|---|---|---|---|
| **Application PK** | `job_key` (TEXT) | `application_id` (UUID String) | JobHunt uses natural job key; Matcher uses surrogate UUID. |
| **Resume Association** | Optional / Independent (stored in `tailoring_requests`) | Mandatory `resume_id` (String NOT NULL) | Migrating JobHunt applications without a generated resume violates Matcher's non-null constraint. |
| **Status Vocabulary** | 13 statuses | 7 statuses | 6 JobHunt statuses have no direct Matcher equivalent; Matcher drops unknown statuses. |
| **External Confirmation** | Required (`CONFIRM_REQUIRED` enforces 409) | None (any status written directly) | Matcher risk of premature/accidental `applied` state. |
| **Auto-Apply Trigger** | None (strictly forbidden) | Automated on `/improve/confirm` | Conflict with rule: tailoring must not mark as applied. |
| **Follow-up Tracking** | First-class `follow_up` (YYYY-MM-DD date) | None | Risk of losing scheduled follow-up dates during migration. |
| **Status History** | Stored in `events` table (`kind='status'`) | None (in-place overwrite) | History lost unless preserved in an additive event store. |
| **User Identity** | Loopback single-user | Loopback single-user (or single-pass hosted) | Neither system supports multi-tenant user accounts. |

---

## 5. Audit Conclusions

1. **Schema Incompatibility:** A direct insert of JobHunt's `applications` records into Resume Matcher's current `applications` table cannot succeed without resolving:
   - The non-null `resume_id` requirement in Resume Matcher.
   - The status vocabulary mismatch (13 vs 7 statuses).
   - The lack of a `follow_up` column in Resume Matcher.
2. **Preservation Invariant:** Preserving JobHunt's application data requires a target schema extension (`legacy_application_id`, nullable `resume_id`, `follow_up` date column) or an isolated staging model.
3. **Behavioral Invariant:** Resume Matcher's `/improve/confirm` auto-apply behavior must be decoupled so that tailoring a document for a discovered job leaves application tracking in `drafting` or `saved`, requiring explicit confirmation to advance to `applied`.

