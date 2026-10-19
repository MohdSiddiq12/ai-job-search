# Feature inventory

Scope: source-backed feature map for Resume Matcher and preservation map for JobHunt. Exact endpoint routes are grouped by router because multiple operations are defined in large router modules.

## Resume Matcher feature map

| User feature | UI / implementation | Persistence / external services | Integration decision and access in JobHunt |
|---|---|---|---|
| Dashboard and resume library | `(default)/dashboard`, resume upload dialog and resume cards; `routers/resumes.py` | `resumes` table; file parser; no provider required to list/edit existing content | Reuse existing page/components under a Resume Library navigation entry after shell consolidation |
| Resume upload, parsing, duplicate detection | Dashboard upload; `/api/v1/resumes` upload/list/detail handlers; `services/parser.py` | Resume row stores source/structured content and metadata; MarkItDown/PDF parser; local database/storage | Reuse backend handler and upload flow; test size/type/corrupt-file cases in unified origin |
| Resume builder, editing, templates and ordering | `/resumes/[id]`; `components/builder/*`, `components/resume/*` | Resume content and template settings in `resumes`; PDF preview renderer | Reuse components and schemas inside integrated UI |
| AI resume enrichment and bullet improvement | enrichment modal; `routers/enrichment.py`, `services/improver.py`, `refiner.py`, prompts | `improvements`/resume state; LiteLLM provider or agent mode | Preserve human review/confirm stages; never overwrite master implicitly |
| Resume wizard | `/resume-wizard`; `routers/resume_wizard.py`, service and prompt | Persists created resume through existing store; provider required for AI conversation | Expose within Resume Library; clarify provider or agent-mode constraints |
| Job description input, metadata parsing, queue | Tailor/queue pages; `/api/v1/jobs/*`, `services/queue_worker.py` | `jobs`, `queue_items`; queue worker; may call provider for tailoring | Replace manual copy step with JobHunt selected-job handoff while retaining existing standalone input |
| Tailoring and review | `/tailor`, builder/regenerate/diff components, resume router operations and tailor-selection service | New tailored resume linked to base and job; LiteLLM or agent mode | Reuse real tailoring code path; preserve source resume, associate result to JobHunt job |
| Match/keyword/fit and ATS score | builder ATS panels, highlighted resume and JD comparison; `services/ats.py`, ATS endpoints | Match/score fields in resume/job metadata; deterministic analysis plus optional AI | Surface actual evidence and missing data, not a hiring prediction |
| ATS parser round-trip check | ATS check view; `/api/v1/ats/parse-check` and resume parse-check | In-memory uploaded bytes or stored resume; Playwright for render check | Make available from resume detail; include bounded upload and renderer errors |
| Cover letters and outreach | builder cover-letter/outreach editors; resume endpoints and `services/cover_letter.py` | Stored with resume/tailored document; provider or agent mode for generation | Expose alongside tailored document; manual approval required before use |
| Interview preparation | interview prep view; resume API/service/prompt path | Derived from selected resume/job; provider may be required | Integrate as per-job preparation action |
| Application Kanban tracker | `/tracker`; tracker components; `/api/v1/applications` CRUD/bulk APIs | `applications`, unique `(job_id,resume_id)`; separate state machine | JobHunt already has applications. Keep JobHunt canonical status/history; adapter/migration map only on explicit design, avoid two conflicting trackers |
| Settings, language and feature prompts | `/settings`; config router and language context | `config.json`, encrypted `api_keys`, database; provider credentials | Reuse only needed settings UI. Never copy credential stores or expose them through JobHunt API |
| Provider/model setup and connection testing | settings components, `/config/llm-api-key`, `/config/api-keys`, `/config/llm-test` | LiteLLM, encrypted key store, Fernet key; network/provider account | Preserve provider config behavior, communicate paid/quota terms, default to no unexpected calls |
| OpenAI account connection | ChatGPT settings; `chatgpt_auth.py`, `chatgpt_inference.py`, callback route | External OAuth-like flow and stored tokens; OpenAI account eligibility and terms | Optional feature with callback/port constraints; cannot promise free availability or bundle with OpenRouter |
| Tailoring queue and history | `/queue`; jobs router and queue worker | `queue_items`, result resume IDs, concurrency/rate interval | Retain in JobHunt's Resume area; idempotency and application-state isolation required |
| PDF export and preview | print routes, resume components, PDF renderer | Playwright/Chromium and fonts; generated output | Reuse renderer/routes; unified origin and session tests required |
| MCP/CLI agent workflows | backend `mcp_server/*`, console scripts `resume-matcher` and `resume-matcher-mcp` | Direct local process and same DB; local `uv` env | Optional developer tool path; not a substitute for unified web interface |
| Localization and responsive/accessibility behavior | `messages/`, language context, frontend components/tests | No external service | Retain existing supported locales and Swiss visual system; include navigation adaption |

## JobHunt behavior to preserve

- Freehire discovery/classification and saved searches; run history/errors; deduplication.
- Persistent job keys/source URLs, fit scores with evidence, feedback and stale/source/description filters.
- Manual description snapshots and export.
- Application records, explicit confirmations for submitted/outcome statuses, event history, notes and follow-up dates.
- Tailoring request ledger and manual packet/result association. Current adapter must remain truthful until replaced by a verified integration.
- Loopback-only server and its existing tests/data. No Resume Matcher action should mark a JobHunt application submitted.

## Authentication and authorization note

Resume Matcher has a single shared password gate in hosted mode, not per-user identities. Its default local development mode bypasses authentication. JobHunt has no account model. Therefore “one session” cannot safely mean account merging, and multi-user isolation is not present in either product as currently inspected. A shared localhost product may defer account semantics for one machine user, but public/multi-user deployment is blocked until an explicit identity and data-ownership design exists.
