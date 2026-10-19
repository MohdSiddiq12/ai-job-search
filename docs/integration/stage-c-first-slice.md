# Stage C first slice — read-only JobHunt job browsing

Status: **pilot implemented and exercised locally**. It reads a disposable SQLite snapshot through Resume Matcher’s FastAPI API and Next.js interface. The original JobHunt database remains authoritative and unchanged. This pilot does not migrate records into Resume Matcher’s persistent database. See `stage-c-pilot-report.md` for exact files, hashes, commands, and results.

## Source and boundary

JobHunt's existing SQLite store is `app/data/jobhunt.db`; the `jobs` table is the source of discovered listings. Its `key` is the primary key and `url` has a unique constraint. The pilot snapshot contains 244 jobs and zero description snapshots. Its adapter is implemented in Resume Matcher on the existing `deployment-hardening` branch. The source store is not used by the app.

Expose a bounded page of job summaries through a small Resume Matcher backend service/adapter. The adapter opens an explicitly supplied SQLite snapshot URI in `mode=ro&immutable=1`, enables `PRAGMA query_only=ON`, uses parameterized filters and a hard maximum result count (page cap 20; scan cap 10,000), and maps only the canonical JobHunt key, title, company, location, source URL, source, posted/first-seen dates, and description-availability status. The source key remains authoritative; no Matcher UUIDs or persistent job copies are created. Description text is not fetched or returned.

The UI displays this page as a read-only Discover list and opens the original listing URL only after an explicit user click. It supports case-insensitive substring search across title/company/location; location, exact case-insensitive source, description-availability, and inclusive ISO posting-date filters; stable sorting by first seen, posting date, title, company, location, or source; and bounded 20-row pages with offsets capped at 10,000. Filter/sort/page state is reflected in the list URL and carried back from job details. Description content remains excluded; the detail view reports availability/status only. No edit, save, apply, dismiss, feedback, search-run, or status action is exposed through this slice.

## Record handling

- Missing description: show the listing with a clear “description unavailable” state; disable any downstream tailoring action. Do not fetch automatically.
- Duplicate canonical key or URL: report a deterministic conflict with opaque key(s), skip ambiguous rows, and do not silently choose the newest or merge them. The current unique constraints should be checked against the snapshot schema.
- Malformed title/URL/date/JSON: reject or skip that row with an opaque key and typed error code; do not log job text, resume contents, credentials, or delete/repair source rows. Keep other valid summaries available.
- Invalid database/schema or missing source path: fail closed with a safe unavailable state; never silently substitute the live database.

## Tests for the boundary

The implemented adapter and API tests cover bounded reads, optional fields, missing descriptions, duplicate and malformed rows, parameterized search/filters, sort allowlists, deterministic ordering, invalid pagination, read-only write rejection, generic missing/corrupt snapshot errors, GET-only behavior, and source hash stability. The UI tests cover normal, empty, unavailable/error, retry, pagination, details, and safe outbound links. Results are recorded in `stage-c-pilot-report.md`.

## Live verification without live-data mutation

The pilot snapshot was created through SQLite's backup API from a `mode=ro` source connection, stored outside both repositories, and ACL-restricted to the current user, SYSTEM, and Administrators. The app received only the snapshot path and a separate empty Resume Matcher data directory. The browser check exercised list, pagination data, detail and outbound-link rendering against `127.0.0.1`; the API rejected POST and the source/snapshot hashes remained unchanged. Exact integrity evidence is in `stage-c-pilot-report.md`.

No permanent duplicate DB, new destination schema, application history, resume files, authentication, or cross-system identity association is part of this slice. A later phase may design a controlled migration after the adapter and boundary tests pass.

## Next gate

Do not broaden this pilot into an application-history, resume, authentication, or tailoring migration until the remaining full-suite/type-check limitations are resolved and separately reviewed. Keep using the disposable snapshot for local preview; do not configure the adapter to use the original live database.
