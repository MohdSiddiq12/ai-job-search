# Stage B — authentication requirements

## Intended use

User clarified this is for **individual/personal use**, with wider deployment security to be managed later. Stage C target is a private, single-user local application. Do not claim multi-user accounts or deployment readiness. Still protect local resumes and application records; single-user scope does not permit exposing an unauthenticated service to a network.

## Existing behavior retained in Stage B

- Matcher hosted mode: one configured password, scrypt verification, HMAC-signed `rm_session`, CSRF cookie/header validation, origin restriction and login throttling. Sessions/throttle state are process-local.
- Matcher development mode bypasses login; restrict it to loopback.
- JobHunt has no account system and is intended for loopback with Host/Origin checks.
- No implementation changes, account linking, email matching, password collection or personal-data migration in Stage B.

## Stage C local requirements

- Bind UI/API to `127.0.0.1`; any LAN/hosted binding is a separate deployment decision.
- Preserve Matcher auth middleware. Serve all unified pages/APIs under one origin so cookies and CSRF checks apply consistently.
- No multi-user or per-record ownership claim. One local OS user owns the data directory; use OS ACLs and device encryption where available.
- Protect upload/download/generated-file routes with server-side gate; validate type, size and content; never accept arbitrary filesystem paths.
- No logging resume/JD content, credentials, tokens or private filenames. Keep local backups restricted.
- Keep explicit confirmation for application submissions/outcomes; tailoring never changes application status.
- AI provider use is explicit and visible. No provider calls during discovery or page load; agent mode remains available.

## Before public or multi-user deployment

Review durable sessions, account identity/lifecycle, ownership and authorization for every record/file, CSRF/cookie rules, rate limits, recovery, audit logging, encrypted backup/restore, upload security and deployment secrets. The existing shared-password/in-memory-session design does not establish multi-user security. Deployment has its own gate.
