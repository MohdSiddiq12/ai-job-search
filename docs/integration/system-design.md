# Proposed unified system design

## Product structure

JobHunt remains the product name, repository, start command, and destination. The eventual frontend uses one Next.js shell, borrowing Resume Matcher’s Swiss design tokens/components. JobHunt screens are migrated into that shell; Matcher workflows remain real existing features, not iframe links.

### Navigation map

- **Overview** — discovery health, saved matches and application follow-ups.
- **Discover** — saved searches, search runs, job list/detail, description review.
- **Applications** — JobHunt’s canonical status/history/notes/follow-up tracker.
- **Resumes** — Resume Matcher library, upload, builder, templates and versions.
- **Tailor** — choose a JobHunt job and base resume; analyze, review gaps, tailor, edit, preview and export.
- **Preparation** — cover letter/outreach and interview preparation tied to a job/resume.
- **Settings** — provider/agent mode, language and local data controls.

Responsive navigation should retain the current compact job detail pattern on narrow screens while Resume Matcher editors/preview use their established responsive components.

## Service boundaries

- `jobhunt.discovery`: current Freehire discovery, saved searches, dedupe and run records.
- `jobhunt.applications`: canonical application statuses, events and follow-ups.
- `jobhunt.resume_workflow`: explicit association of discovered job ID and description snapshot with a selected Resume Matcher resume; calls real service functions in-process after runtime consolidation.
- `resume_matcher`: preserve existing parser, resume schema, tailoring, ATS, enrichment, queue and PDF services/routes.
- `jobhunt.integration`: stable use-case facade for job-to-resume commands and their audit metadata; no UI may update application status as a side effect.

Use in-process service calls after the FastAPI host transition rather than inventing an unauthenticated loopback HTTP API. Keep routers thin; validate inputs at boundary and reuse services. If a separate process is temporarily needed, use a documented authenticated private API with short timeouts, not a shared browser cookie as service auth.

## Data ownership

- JobHunt owns job discovery identity, source URL, posted/found dates, snapshots, user feedback and application status/events.
- Resume Matcher owns source and tailored resume content, template settings, analysis and generated files.
- A new integration association records JobHunt job key, description snapshot hash, source resume ID, resulting resume ID, request key, state and timestamps. It must not store duplicated resume text.
- Generated resume is a new version; source/master remains unchanged. Store output through the matcher’s existing API/service and document rendering pathway.
- Additive migrations only. Do not combine application tables. Never change `applied` without explicit user confirmation.

## Security and cost controls

- Same-origin pages/API, matcher authentication middleware retained for local first release, host guard and CSRF checks verified across all routes.
- Bind local mode to loopback. Hosted/multi-user remains blocked until durable identity, session persistence and user ownership are designed and tested.
- Agent mode as default cost-safe path. Provider mode requires configured key/account, visible provider/model, bounded timeouts, provider rate/error reporting and an explicit user action.
- Do not log resume or job description bodies; upload size/type checks and safe document result references; no provider calls during discovery or page load.

## Rollout and rollback

Maintain a runnable legacy JobHunt path throughout migration. Introduce the new FastAPI/Next host beside it on a distinct local port for development; test against copied, disposable data. Promote only after feature checks, then keep an export/backup and rollback command documented. Do not modify Resume Matcher source branch as part of the first integration increments.
