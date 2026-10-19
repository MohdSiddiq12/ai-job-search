# Stage B — data migration specification

No live migration was run. Destination names are proposals requiring schema review. The two DBs remain separate until a reversible migration exists.

| Source | Destination proposal | Mapping / transformation | Identity and duplicate policy |
|---|---|---|---|
| JobHunt `jobs` | `jobhunt_jobs` (or isolated prefixed tables) | Preserve source fields, dates, JSON evidence, score and discovery status | Preserve canonical `key` PK and unique `url`; conflicts stop dry-run, never overwrite silently |
| JobHunt `searches` | `jobhunt_searches` | Preserve query JSON, location, age, enabled and interval | Keep integer ID when safe; otherwise `legacy_id` plus explicit FK map |
| JobHunt `runs` | `jobhunt_discovery_runs` | Preserve trigger/times/status/counts/errors | Preserve ID if safe; map `search_id` through explicit map |
| JobHunt `job_description_snapshots` | `jobhunt_job_descriptions` | Preserve original/normalized text, method, status, URL, times, hash and errors | Preserve history; do not coalesce rows merely because hashes match |
| JobHunt `applications` | `jobhunt_applications` | Preserve status, notes, follow-up and timestamp | One per canonical JobHunt key; status vocabulary is authoritative |
| JobHunt `events` | `jobhunt_events` / `jobhunt_application_events` | Preserve kind/key/time/detail; classify only known event types | Preserve ID when safe; never synthesize history from current status |
| JobHunt `feedback` | `jobhunt_feedback` | Preserve verdict/reason/time | Preserve ID when safe; require resolvable job FK |
| JobHunt `tailoring_requests` | `jobhunt_resume_runs` | Preserve idempotency and manual/import state; map only known Matcher IDs | Unresolved refs stay explicitly unmapped; never infer from company/title |
| Matcher `resumes` | Existing Matcher `resumes` | Preserve content, master/default, parent, structured data, original Markdown and templates | Preserve `resume_id` PK; no copy between DBs |
| Matcher `jobs` | Existing Matcher `jobs` | Keep Matcher job text; optionally add explicit JobHunt key metadata after schema design | Matcher UUID is never treated as JobHunt canonical key |
| Matcher `improvements`, `tailoring_previews`, `queue_items` | Existing Matcher tables | Preserve operation history and result links | Do not assume every generated resume was applied |
| Matcher `applications` | Existing Matcher table; no automatic import | Resume-specific Kanban, unique `(job_id,resume_id)` | Never infer JobHunt application status from this table |
| Matcher file/generated output | Existing protected storage | Preserve bytes and ownership metadata | Do not copy into public documents or expose absolute paths; missing files are flagged |

## Proposed association

`jobhunt_resume_runs`: `run_id` UUID PK, `jobhunt_job_key`, `description_snapshot_id`, `description_sha256`, `source_resume_id`, nullable `matcher_job_id`, nullable `tailored_resume_id`, nullable `application_key`, unique `idempotency_key`, `state`, timestamps and `error_code`. Cross-database references are validated by the orchestration service. Application link remains optional and is set only when user selects an existing application. Matcher parent/source lineage must remain intact.

## Invalid/missing rows

- Missing job/snapshot/source resume: quarantine in dry-run report; do not invent an association.
- Invalid JSON/date/status: preserve raw value in an error report; block cutover for unresolved application statuses.
- Duplicate key/URL/idempotency key: report both IDs for deterministic review; do not choose newest automatically.
- Missing file: retain DB record and flag missing asset; do not pretend export works.
- Logs contain opaque IDs/counts/error codes, not resume or job-description text or secrets.

## Backup, rollback and validation

1. Before final snapshot, stop writers. Use SQLite’s backup API or another consistent snapshot for DBs; raw-copying live WAL DB files is unsafe. Back up file storage separately.
2. Store copies outside both repositories with restrictive Windows ACLs. Record hashes/byte sizes locally, not in Git.
3. Migrate to a new DB/copy transactionally, leaving sources read-only; record schema migration version and source snapshot hash.
4. Compare per-table counts, distinct job keys/URLs, statuses, event IDs/times, snapshot hashes, resume IDs/parent IDs; verify FK/unique constraints. Sample by opaque ID without logging content.
5. Restore DB and file copy into a disposable path and verify references and export before cutover.
6. Rollback points app to untouched original DB/data; delete no source rows. Reverse migration is a separately reviewed operation.

Current source counts are in `stage-b-baseline-results.md`; re-count immediately before any future migration.
