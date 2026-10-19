# Stage B — service boundaries and ownership

These are proposed ownership rules for the unified JobHunt product. Existing implementations remain intact until a reviewed migration replaces them.

| Boundary | Owns | Existing source | Destination service/contract |
|---|---|---|---|
| Discovery ingestion | Freehire query, source URL/ID, location and posting dates, deduplication, discovery state/errors | JobHunt `tools/freehire_discover.py`, `app/core.py`, `app/server.py`; `jobs`, `searches`, `runs` | `jobhunt.discovery`, `/api/v1/discovery` and `/api/v1/jobs` in unified FastAPI host |
| Description provenance | Original/normalized description, capture method, URL, timestamp, digest and completeness | JobHunt `job_description_snapshots` | `jobhunt.descriptions`; preserve `manual`; never label search snippets complete |
| Application lifecycle | Canonical status, notes, confirmation, follow-up, transition history/outcomes | JobHunt `applications`, `events` | `jobhunt.applications`; user action required; discovery/tailoring never sets `applied` |
| Resume documents | Source upload, parsing, master/source resume, immutable tailored versions, builder/template state | Matcher `Resume`, parser, resume router and builder | Existing Matcher DB/services; JobHunt does not duplicate resume content |
| Matching/tailoring | Selected resume + reviewed job text, analysis, keywords/ATS, tailoring, diffs and queue | Matcher `Job`, `Improvement`, `TailoringPreview`, `QueueItem`, services/routers | Existing Matcher domain functions behind a JobHunt orchestration use case; source resume unchanged |
| Generated documents | Tailored resume identity, preview, PDF/export | Matcher resume/PDF pipeline | Matcher storage/renderer; JobHunt stores an opaque stable reference, never an arbitrary path |
| Cross-domain orchestration | Link JobHunt job/snapshot to source resume, tailoring operation, result and optional application | Not yet present; current `tailoring_requests` is manual handoff | Proposed idempotent `jobhunt_resume_runs`; no duplicated resume/description body |
| LLM settings | Provider/model, encrypted keys, agent mode and external calls | Matcher config/LLM modules | Keep in Matcher settings; no keys copied to JobHunt; provider call requires explicit action |

## In-process contract after host consolidation

```text
TailorJobRequest(job_key, description_snapshot_id, source_resume_id, idempotency_key)
TailorJobResult(run_id, job_key, snapshot_sha256, source_resume_id,
                state, analysis_ref?, tailored_resume_id?, document_ref?, error_code?)
```

The use case validates the job/snapshot and exact reviewed text, calls existing Matcher functions, persists state transactionally and returns honest pending/succeeded/failed status. `idempotency_key` is unique; retries resolve the existing operation. A completed result links to its source and snapshot digest. No resume body, provider key, cookie or arbitrary local path is accepted as a result.

Until implemented, the adapter stays `not_configured`; no fake URL. A temporary process adapter, if later required, needs an authenticated private contract, bounded timeouts, validated references, idempotency and honest mapping of failures. There are no integration credentials configured.
