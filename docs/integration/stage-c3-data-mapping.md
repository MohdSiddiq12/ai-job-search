# Stage C.3 — Data Mapping Specification: JobHunt to Resume Matcher

**Date:** 2026-10-19  
**Role:** Backend / Data Auditor for JobHunt + Resume Matcher Integration  
**Mode:** Read-only architectural design. No live data migration, no schema alteration, and no code changes.

---

## 1. Overview and Core Design Principles

This specification establishes the authoritative, field-by-field mapping between JobHunt (`ai-job-search`) and Resume Matcher (`Resume-Matcher`).

### 1.1 Mandatory Design Rules
1. **Single-User Ownership Model:** The system operates as a private, local, single-user instance on loopback (`127.0.0.1`). No multi-tenant user accounts, tenant IDs, or email-based record merging are permitted. Identity is anchored locally via a dedicated `legacy_application_id` column to guarantee idempotent round-trip lookups.
2. **Separation of Discovery and Application State:** Browsing job listings, viewing details, bookmarking/shortlisting, or generating a tailored resume must **never** mutate an application status to `applied`. Advancing to `applied` requires an explicit, confirmed user submission action.
3. **Stateless Discovery Endpoints:** Read-only job discovery endpoints (`/api/v1/discovery/jobs`) must remain completely isolated from application cards, status mutations, and resume records.
4. **Secure Handoff:** Job-to-tailoring transitions must pass job descriptions and metadata exclusively via backend-managed database records or validated route state—**never via URL query strings or browser history**.
5. **Description Provenance:** Every job description must carry explicit provenance metadata (`source-provided`, `retrieved`, or `pasted`), a SHA-256 digest, and verification status.

---

## 2. Field-by-Field Mapping Specification

### 2.1 Table: `applications` (JobHunt) $\to$ `applications` (Resume Matcher)

JobHunt's `applications` records represent tracking leads for discovered jobs. Resume Matcher's `applications` records represent Kanban board cards tied to both a job and an applied resume.

| Source Field | Target Field | Target Type | Nullable | Transform / Logic | ID Handling | Default | Validation | Authority |
|---|---|---|:---:|---|---|---|---|:---:|
| `job_key` | `legacy_application_id` | `VARCHAR(256)` | No | Direct copy of JobHunt canonical key (e.g. `mitgo_middle-python-developer`). | Preserves source natural PK in target as indexed unique column. | None | Must match `^[a-z0-9_-]+$` | Authoritative |
| *(None)* | `application_id` | `VARCHAR(36)` | No | Generate deterministic UUIDv5 (using namespace `6ba7b810-9dad-11d1-80b4-00c04fd430c8` and name `job_key`) or UUIDv4. | Target PK generation. | UUIDv4/v5 | Valid RFC 4122 UUID | Derived |
| `job_key` | `job_id` | `VARCHAR(36)` | No | Map to the migrated Resume Matcher `Job.job_id` corresponding to this `job_key`. | Foreign key to `jobs.job_id`. | None | Must resolve to existing row in `jobs` | Authoritative |
| *(None)* | `resume_id` | `VARCHAR(36)` | **Yes** *(Schema Update)* | Set to linked tailored `resume_id` if a completed tailoring request exists; otherwise `NULL`. | Foreign key to `resumes.resume_id`. | `NULL` | Must resolve to `resumes` if present | Authoritative |
| *(None)* | `master_resume_id` | `VARCHAR(36)` | Yes | Set to base master resume if linked tailored resume descends from one; otherwise default master resume ID. | Foreign key to `resumes.resume_id`. | `NULL` | Must resolve to `resumes` if present | Derived |
| `status` | `status` | `VARCHAR(32)` | No | Mapped via Status Transition Matrix (§3). Preserves current stage in 7-column board. | None | `'saved'` | Must belong to target `ApplicationStatus` | Authoritative |
| `status` | `legacy_status` | `VARCHAR(32)` | No | Additive column: stores original 13-value JobHunt status (e.g., `'investigating'`, `'drafting'`). | Preserves exact source vocabulary for filtering and badges. | None | Must belong to JobHunt `APP_STATUSES` | Authoritative |
| `notes` | `notes` | `TEXT` | Yes | Direct copy of notes string. If empty string `''`, normalize to `NULL`. | None | `NULL` | Max length 10,000 characters | Authoritative |
| `follow_up` | `follow_up_date` | `VARCHAR(10)` | Yes | Additive column: direct copy of ISO date (`YYYY-MM-DD`). | None | `NULL` | Valid `YYYY-MM-DD` or `NULL` | Authoritative |
| `updated_at` | `updated_at` | `VARCHAR(32)` | No | Parse and normalize to ISO-8601 UTC string (`_utcnow_iso`). | None | Current UTC | Valid ISO-8601 timestamp | Authoritative |
| *(Derived from jobs)* | `created_at` | `VARCHAR(32)` | No | Earliest event timestamp in `events` for this `job_key` where `kind='status'`; fallback to `jobs.first_seen`. | None | `jobs.first_seen` | Valid ISO-8601 timestamp | Derived |
| *(Derived from jobs)* | `company` | `VARCHAR(256)` | Yes | Direct copy from `jobs.company`. | None | `NULL` | Max 256 characters | Authoritative (Job) |
| *(Derived from jobs)* | `role` | `VARCHAR(256)` | Yes | Direct copy from `jobs.title`. | None | `NULL` | Max 256 characters | Authoritative (Job) |
| *(None)* | `applied_at` | `VARCHAR(32)` | Yes | If mapped `status == 'applied'` or post-application, use timestamp from earliest `events` row where `detail LIKE '%-> applied%'`; otherwise `NULL`. | None | `NULL` | Valid ISO-8601 or `NULL` | Authoritative |
| *(None)* | `position` | `INTEGER` | No | Server-assigned contiguous sequence `0..N-1` within each target status column. | None | `0` | Non-negative integer | Derived |

> [!IMPORTANT]
> **Schema Requirement for Target `applications`:**  
> In Resume Matcher's existing `models.py`, `resume_id` is defined as `Mapped[str] = mapped_column(String, index=True)` (NOT NULL). To allow JobHunt applications (which are discovered opportunities tracked before any resume is created) to migrate into the tracker, `resume_id` **must be made nullable** (`Mapped[str | None] = mapped_column(String, nullable=True)`), or records must be stored in an isolated extension table `jobhunt_applications`. Making `resume_id` nullable in `models.py` is the recommended path.

---

### 2.2 Table: `jobs` (JobHunt) $\to$ `jobs` (Resume Matcher)

| Source Field | Target Field | Target Type | Nullable | Transform / Logic | ID Handling | Default | Validation | Authority |
|---|---|---|:---:|---|---|---|---|:---:|
| `key` | `metadata_json['jobhunt_key']` | `VARCHAR(256)` | No | Stored in JSON metadata to preserve JobHunt canonical key. | Opaque lookup key. | None | Unique string | Authoritative |
| *(None)* | `job_id` | `VARCHAR(36)` | No | Generate deterministic UUIDv5 (from `key`) or UUIDv4. | Primary Key. | None | RFC 4122 UUID | Derived |
| `title` | `metadata_json['role']` | `VARCHAR(256)` | No | Direct copy of job title. Flattened on read by facade. | None | None | Non-empty string | Authoritative |
| `company` | `metadata_json['company']` | `VARCHAR(256)` | Yes | Direct copy of company name. Flattened on read. | None | `NULL` | String | Authoritative |
| `url` | `metadata_json['source_url']` | `TEXT` | No | Direct copy of unique posting URL. | None | None | Valid HTTP/HTTPS URL | Authoritative |
| `location` | `metadata_json['location']` | `TEXT` | Yes | Direct copy of location string. | None | `NULL` | String | Authoritative |
| `location_class` | `metadata_json['location_class']` | `VARCHAR(32)` | Yes | Direct copy (`dubai`, `uae-other`, etc.). | None | `'uncertain'` | Standard class | Authoritative |
| `work_mode` | `metadata_json['work_mode']` | `VARCHAR(32)` | Yes | Direct copy (`onsite`, `remote`, `hybrid`). | None | `NULL` | String | Authoritative |
| `posted_date` | `metadata_json['posted_date']` | `VARCHAR(10)` | Yes | Direct copy of posting date string (`YYYY-MM-DD`). | None | `NULL` | ISO Date or NULL | Authoritative |
| `first_seen` | `created_at` | `VARCHAR(32)` | No | Normalized to UTC ISO-8601 string. | None | Current UTC | Valid ISO-8601 | Authoritative |
| `score` | `metadata_json['jobhunt_fit_score']` | `INTEGER` | Yes | Direct copy of JobHunt fit score (0-100). | None | `NULL` | Integer 0-100 | Authoritative |
| `score_json` | `metadata_json['fit_components']` | `JSON` | Yes | Parse JSON string to dict and embed into metadata. | None | `NULL` | Valid JSON | Authoritative |
| *(None)* | `content` | `TEXT` | No | If a `job_description_snapshots` record exists, use `original_text`; if missing, use placeholder: `"Description unavailable in JobHunt snapshot."` | None | `"Description unavailable."` | Text | Authoritative / Placeholder |

---

### 2.3 Table: `job_description_snapshots` (JobHunt) $\to$ `Job` Description & Provenance

| Source Field | Target Field | Target Type | Nullable | Transform / Logic | Validation | Authority |
|---|---|---|:---:|---|---|:---:|
| `original_text` | `jobs.content` | `TEXT` | No | Complete text of job description. | Text $\le$ 100,000 chars | Authoritative |
| `normalized_text` | `metadata_json['normalized_content']` | `TEXT` | Yes | Stripped, normalized text. | Text | Derived |
| `status` | `metadata_json['description_status']` | `VARCHAR(32)` | No | `'complete'`, `'partial'`, `'failed'`, `'manual'`. | In allowlist | Authoritative |
| `method` | `metadata_json['provenance_method']` | `VARCHAR(32)` | No | `'manual_paste'`, `'scraped'`, `'api'`, `'crawler'`. | In allowlist | Authoritative |
| `content_sha256` | `metadata_json['content_sha256']` | `VARCHAR(64)` | No | Hex SHA-256 digest of normalized text. | 64-char hex | Authoritative |
| `source_url` | `metadata_json['description_url']` | `TEXT` | Yes | Source URL where description was obtained. | HTTP/HTTPS URL | Authoritative |
| `retrieved_at` | `metadata_json['retrieved_at']` | `VARCHAR(32)` | Yes | ISO-8601 UTC timestamp. | ISO-8601 | Authoritative |

---

### 2.4 Table: `events` (JobHunt) $\to$ `application_events` (Additive Audit Store)

Because Resume Matcher currently lacks an audit trail table, status events from JobHunt must be migrated into an additive audit table to prevent data loss:

```sql
CREATE TABLE IF NOT EXISTS application_events (
  event_id VARCHAR(36) PRIMARY KEY,
  application_id VARCHAR(36) NOT NULL REFERENCES applications(application_id),
  legacy_event_id INTEGER,
  kind VARCHAR(32) NOT NULL,
  detail TEXT,
  occurred_at VARCHAR(32) NOT NULL
);
```

| Source Field | Target Field | Target Type | Nullable | Transform / Logic | Default | Authority |
|---|---|---|:---:|---|---|:---:|
| `id` | `legacy_event_id` | `INTEGER` | Yes | Direct copy of integer event ID. | None | Authoritative |
| *(None)* | `event_id` | `VARCHAR(36)` | No | Generated UUIDv4. | None | Derived |
| `job_key` | `application_id` | `VARCHAR(36)` | No | Resolved from `applications.legacy_application_id = events.job_key`. | None | Authoritative |
| `kind` | `kind` | `VARCHAR(32)` | No | Direct copy (`status`, `feedback`, `description`, etc.). | None | Authoritative |
| `detail` | `detail` | `TEXT` | Yes | Direct copy of detail string. | `NULL` | Authoritative |
| `ts` | `occurred_at` | `VARCHAR(32)` | No | Normalized ISO-8601 UTC timestamp. | Current UTC | Authoritative |

---

## 3. Status Mapping Matrix and Loss Analysis

### 3.1 Mapping JobHunt (13 Statuses) to Resume Matcher (7 Statuses)

| JobHunt Source Status | Target 7-Column Status | Semantic Alignment | Semantic Loss / Nuance Impact | Remediation Strategy |
|---|---|---|---|---|
| `investigating` | `saved` | Early discovery research; not yet submitted. | Subsumed into generic "saved". | Tag card with badge: `[Investigating]`. Store in `legacy_status`. |
| `shortlisted` | `saved` | Qualified lead selected for pursuit. | Distinction between general saved and curated shortlist lost. | Tag card with badge: `[Shortlisted]`. Store in `legacy_status`. |
| `drafting` | `saved` | Active preparation of tailored CV/cover letter. | Active drafting obscured as passive saved lead. | Tag card with badge: `[Drafting]`. Store in `legacy_status`. |
| `ready_for_review` | `saved` | Materials complete; pending applicant final check. | Ready-to-send milestone obscured. | Tag card with badge: `[Ready for Review]`. Store in `legacy_status`. |
| `applied` | `applied` | Exactly equivalent: externally submitted. | None. Full semantic parity. | Direct status mapping. |
| `assessment` | `response` | Employer responded with test/take-home task. | Technical evaluation grouped with general employer communication. | Target `response` column, badge: `[Assessment]`. |
| `interview` | `interview` | Exactly equivalent: interviews scheduled/active. | None. Full semantic parity. | Direct status mapping. |
| `offer` | `accepted` | Formal offer extended by employer. | Confuses "offer extended" with "offer accepted". | Target `accepted` column, badge: `[Offer Received]`. |
| `hired` | `accepted` | Candidate accepted offer and completed onboarding. | None. Full semantic parity with target outcome. | Direct status mapping. |
| `rejected` | `rejected` | Exactly equivalent: formal rejection received. | None. Full semantic parity. | Direct status mapping. |
| `withdrawn` | `rejected` | Terminal negative state; candidate withdrew. | Conflates employer rejection with applicant withdrawal. | Target `rejected` column, badge: `[Withdrawn]`. |
| `no_response` | `no_response` | Exactly equivalent: employer ghosted/expired. | None. Full semantic parity. | Direct status mapping. |
| `offer_declined` | `rejected` | Candidate declined employer's offer. | Conflates success (getting an offer) with rejection. | Target `rejected` column, badge: `[Offer Declined]`. |

### 3.2 Proposed Expanded Taxonomy (Future Non-Lossy Model)
To eliminate semantic loss without breaking existing Kanban views, a two-level status taxonomy is proposed:
- **`board_stage` (7 Macro Columns):** `saved`, `applied`, `no_response`, `response`, `interview`, `accepted`, `rejected`.
- **`sub_status` (Granular Pipeline State):**
  - Within `saved`: `investigating`, `shortlisted`, `drafting`, `ready_for_review`.
  - Within `response`: `acknowledged`, `assessment`.
  - Within `accepted`: `offer_received`, `hired`.
  - Within `rejected`: `rejected_by_employer`, `withdrawn_by_applicant`, `offer_declined`.

---

## 4. Ownership and Identity Model

### 4.1 Single-User Local Model (Recommended)
- **Architecture:** The application runs exclusively for an individual user on a local workstation (`127.0.0.1`).
- **Identity Preservation:** Every migrated record stores `legacy_application_id = job_key`.
- **No Email Merging:** The migration script **never** attempts to merge applications based on applicant email address or company domain. Matcher cards are tied to their unique JobHunt `job_key`.
- **Security:** Data access is restricted via operating system Windows ACLs on the target SQLite database file.

### 4.2 Alternatives Evaluated and Trade-offs
1. **Isolated Extension Table (`jobhunt_applications`):**
   - *Description:* Leave Resume Matcher's `applications` table untouched. Create a parallel `jobhunt_applications` table for JobHunt records.
   - *Pros:* Zero changes to Resume Matcher models; zero risk of breaking existing Matcher Kanban queries.
   - *Cons:* Fractures the user experience. The user would have to look in two separate Kanban boards.
2. **Multi-User Tenant Scoping (`user_id` / Account Linking):**
   - *Description:* Introduce a `users` table and add `user_id` foreign keys to all application tables.
   - *Pros:* Future-proof for multi-tenant SaaS.
   - *Cons:* Violates current single-user project scope; unnecessary complexity; requires building user authentication and session management not present in either application today.
3. **Additive In-Place Unification (Selected Recommendation):**
   - *Description:* Extend Resume Matcher's `applications` table with `legacy_application_id`, `legacy_status`, `follow_up_date`, and allow `resume_id` to be nullable.
   - *Pros:* Single unified Kanban board; 100% data fidelity preserved; backward compatible with existing Resume Matcher functionality.

---

## 5. Job-to-Tailoring Handoff Specification

### 5.1 Security and Integrity Rules
1. **No URL Description Passing:** Under no circumstances should job descriptions, candidate notes, or resume contents be serialized into URL query parameters, hash fragments, or HTTP headers. (Prevents URL truncation, escaping errors, and exposure in server access logs and browser history).
2. **Backend-Managed Handoff State:** When a user triggers "Tailor Resume" from a job listing:
   - The frontend issues an HTTP POST to `/api/v1/tailor/initiate` passing `{ "job_key": "..." }`.
   - The backend retrieves the job and its validated description snapshot directly from the database.
   - The backend provisions a draft tailoring record in `tailoring_previews` or `queue_items` and returns an opaque `preview_id` or `job_id`.
   - The frontend navigates to `/tailor?job_id=UUID` using only the opaque reference.
3. **Description Provenance Tracking:**
   Every tailoring handoff packet must carry:
   - `provenance_type`: One of `'source_provided'` (scraped from portal), `'retrieved'` (downloaded via automated fetcher), or `'pasted'` (manually pasted by user).
   - `content_sha256`: Cryptographic digest of the description text at time of tailoring handoff.
   - `verified`: Boolean indicating if content was verified against an active public listing.

