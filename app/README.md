# JobHunt (local job-search workspace)

Stdlib-only Python app: SQLite store, Freehire discovery, explainable fit scores, dashboard.
Runs on 127.0.0.1 only. Data lives in `app/data/` (self-ignored by git).

    python app/server.py                  # dashboard at http://127.0.0.1:8787
    python app/server.py --run-once       # one discovery run (Task Scheduler friendly)
    python app/server.py --import-seen    # read-only import of job_scraper/seen_jobs.json
    python -m unittest tests.test_app_core tests.test_app_server tests.test_resume_matcher_adapter

Design rules: discovery state and application state are separate tables; "applied" and later
statuses need explicit confirmation; scores show evidence, missing data and a confidence figure
(they are NOT ATS scores or hiring predictions); the app never sends or submits anything.

Open a job and paste the full text from its original posting into **Job description**. The app
keeps timestamped, deduplicated snapshots and labels user-pasted content `manual`; it never
pretends a search snippet is a complete description. It identifies profile skills mentioned in
the pasted text as evidence, but this does not yet change the fit score. The job list supports
description-state and source filters with server-side pagination.

 
The **Applications** tab shows persisted application records and follow-up dates. In a job's
Resume Matcher section, enter a resume path under `documents/cv/` and prepare a handoff packet.
JobHunt does not transmit the resume or contact Resume Matcher. To use the manual fallback,
download the packet, perform tailoring in the separate app yourself, save its returned PDF/DOCX
under `documents/applications/`, then confirm and link that file in JobHunt.
 
Not configured: automated description fetchers, additional job sources, Resume Matcher API,
resume upload/library, email/Notion sync, recruiter research, and automatic submission. Returned
documents are referenced by private local path; the app does not serve their contents. It remains
loopback-only; do not expose it to the public internet.
