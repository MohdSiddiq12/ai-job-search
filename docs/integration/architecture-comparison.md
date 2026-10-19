# Architecture comparison

| Concern | JobHunt | Resume Matcher | Consequence |
|---|---|---|---|
| Runtime | Python stdlib HTTP server | FastAPI + async services | Existing direct imports are not compatible without a runtime consolidation |
| Web UI | Hand-built single HTML/CSS/JS SPA and hash routes | Next.js 16 / React 19 / Tailwind 4, Swiss design system | One interface should use a single Next.js shell and migrate JobHunt screens; do not iframe |
| Persistence | Local SQLite, synchronous operations | SQLAlchemy async SQLite default, optional PostgreSQL | Avoid sharing DB files or running both against one SQLite DB; define ownership and an additive import/migration |
| Data model | job discovery, saved searches, applications/events, descriptions, tailoring requests | Resume, job text, improvements, preview, applications, API keys, queue | IDs/status vocabularies differ; JobHunt remains source for discovery/application outcome, Resume Matcher source for resume versions/analysis |
| Authentication | No login; loopback-only | Single password in hosted mode; signed HttpOnly cookie and CSRF token; in-memory sessions | No account merge. Local reverse-proxy may preserve matcher auth with one origin; production needs durable sessions/identity assessment |
| Background work | discovery scheduler while server remains on, CLI `--run-once` | asyncio tailoring queue worker | Separate jobs; require bounded concurrency and cancellation semantics |
| AI | rule-based score and external discovery source | LiteLLM configured provider, optional agent mode, ChatGPT connection | AI calls are not inherently free; integrate explicit opt-in/provider status and budgets |
| Files | app paths under documents, local files | resume records, parser and Chromium PDF generation | Keep originals and generated outputs separate; secure document references and limits |
| Tests | Python unittest; app suite 24 tests; broader suite has WSL-dependent reset failures | pytest backend, Vitest frontend, optional eval/postgres/browser tests | Baseline all relevant suites before adopting matcher code |

## Chosen direction

JobHunt repository and user-facing local URL remain authoritative. For a maintainable unified experience, use Resume Matcher’s Next.js/React UI shell and Swiss components as the eventual product shell, while porting JobHunt functionality behind a FastAPI router/service boundary. Keep domain modules and DB ownership explicit: JobHunt discovery/application data should not be casually converted into Resume Matcher `Job`/`Application` rows. This is a gradual migration, not a wholesale copy of either repo.

The present JobHunt prototype is too small to host the large Resume Matcher frontend without replacing its serving layer, and a second remote backend would introduce cross-origin auth, CSRF, availability and credential problems. A same-origin FastAPI deployment with Next.js reverse proxy is the strongest target architecture, but it is a substantial rewrite and must be split into verified slices. The existing JobHunt loopback app remains runnable until those slices replace it.

## Authentication decision required before public use

For a local single-user first release, retain Resume Matcher’s password/session middleware and serve all pages/API under one origin; preserve local development mode only when explicitly bound to loopback. Do not map records by email because neither side has a user table. Before multi-user/hosted usage, redesign or replace the single-password identity model with durable account/session storage and ownership on every record; this exceeds a safe “integration” patch and requires explicit migration design.

## Data migration policy

Back up the JobHunt SQLite DB and Resume Matcher data directory before any migration. Build read-only exporters and a dry-run report first. Preserve JobHunt job keys, source URLs and application event sequence. Resume Matcher `applications` are a separate Kanban concept keyed to job/resume pairs; they are not equivalent to JobHunt application status. Migration must not auto-mark an application as applied or merge these records without user-reviewed mapping.
