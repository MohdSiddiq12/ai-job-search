# Integration risks and controls

| Risk | Evidence / impact | Required mitigation |
|---|---|---|
| Authentication is not a user-account system | Matcher offers one configured password; sessions are in process memory; development bypasses auth | Keep loopback-only for single-user phase. Do not merge identities. Add durable auth and per-record ownership before multi-user exposure |
| Cross-origin/session mismatch | JobHunt and Matcher have separate servers today | Move to one origin/reverse proxy before UI integration; test cookies, CSRF, host guard, login/logout and callback behavior |
| Job/application data semantics conflict | JobHunt tracks actual application lifecycle; Matcher tracker tracks resume-specific cards | JobHunt owns application truth. Do not synchronize status implicitly; use explicit, auditable mapping |
| Data loss during migration | Both use independent SQLite stores; Matcher can also use PostgreSQL | Backup, read-only export, dry-run, transactional additive migration and rollback path; never reuse/overwrite a DB file |
| Free-tier assumptions | LiteLLM supports providers but provider quota/pricing is external; ChatGPT connection has its own eligibility/terms | Agent mode/no app model call is the cost-safe default. Provider calls require explicit configured credentials and budget/rate policy |
| Browser/PDF runtime | Playwright Chromium, fonts and PDF routes required | Verify install/runtime and PDF rendering on Windows; bounded operation timeouts and clear errors |
| Package stack increase | Matcher backend/frontend pin many dependencies; JobHunt has no app-level dependency manifest | Adopt existing lockfiles/manifests only through documented stack transition; do not blend manifests or install dependencies blindly |
| Personal resume exposure | Resume content and generated files are sensitive | Local storage only by default; redact logs; validate uploads and paths; no external model call without provider/config and user choice |
| Main product regression | Existing JobHunt tests/data/app are local untracked work | Keep all current files and DB intact, preserve branch/remotes, run old suite at each migration step |
| Feature parity false claims | Matcher has many real flows and tests, but no current integrated route | Track each feature in inventory; call it integrated only after UI and API journey tests |
| Discovery source availability | JobHunt uses Freehire discovery helpers | Isolate source failures and keep manual import; not part of Resume Matcher integration |
| Production readiness overclaim | Neither current architecture provides the required combined account isolation | Mark local single-user only until reviewed identity, durable session, deployment and e2e gates pass |

No integration-specific code has yet changed. The main blocker to a direct backend API call is the absence of a supported service credential/API contract and incompatible session/user semantics. Running both apps locally behind one browser does not itself make them one authenticated product.
