# Stage B — UI integration plan

No UI was redesigned in Stage B. Use Resume Matcher’s Swiss International Style, Next.js components and design tokens as the shared visual baseline. Keep JobHunt as the user-facing product and preserve Matcher routes/workflows.

| Navigation/page | Proposed route | Existing implementation to reuse/adapt | Owner |
|---|---|---|---|
| Overview | `/` or `/overview` | Matcher dashboard composition with discovery health, shortlisted matches and follow-ups | JobHunt summary + Matcher resume summary |
| Discover | `/discover` | New Swiss list/filter view; responsive job details adapted from JobHunt drawer | JobHunt discovery/jobs/snapshots |
| Searches | `/discover/searches` | JobHunt saved-search controls and run actions | JobHunt discovery |
| Search runs | `/discover/runs` | JobHunt run history, status/errors | JobHunt runs |
| Job detail | `/discover/jobs/[key]` | Description snapshots plus Matcher analysis panels/dialogs | JobHunt + orchestration |
| Applications | `/applications` | JobHunt canonical status/history/follow-up view; do not make Matcher Kanban authoritative | JobHunt applications |
| Resume library | `/resumes` | Matcher dashboard cards and upload dialog | Matcher resume API/services |
| Resume editor | `/resumes/[id]` | Existing builder, renderers, templates, enrichment and cover-letter/outreach editors | Matcher |
| Resume wizard | `/resume-wizard` | Existing `ResumeWizardPage` | Matcher |
| Tailor | `/tailor` and job-detail action | Existing tailor, diff review, keyword/JD comparison and ATS components; JobHunt supplies reviewed snapshot | Matcher + orchestration |
| Queue | `/queue` | Existing queue status/error controls | Matcher queue/jobs API |
| Interview prep | Resume/job panel | Existing interview-prep view | Matcher + selected JobHunt description |
| Settings | `/settings` | Existing language/provider/agent mode settings | Matcher config; no key copied |
| Preview/export | Existing `/print/...` | Print pages and Playwright renderer | Matcher |
| Login | `/login` | Existing login page and `AuthGate` | Matcher auth |

JobHunt’s one-file HTML/CSS/JS hash-routed SPA is not reusable as React components. Migrate views incrementally into Next.js while keeping the old Python app runnable; recreate behavior from source/service contracts, and use Matcher tokens for tables, controls, dialogs, drawers and notifications.

All async flows need pending, success, retryable error, unavailable and empty states. Use explicit confirmation before external-action application statuses. Preserve Matcher diff review, safe HTML rendering, keyboard/focus behavior and reduced motion. Keep resume/JD text out of URLs/telemetry. On narrow screens, use mobile navigation and full-screen job details. Stage B makes no visual parity claim; verify with component tests and browser journeys later.
