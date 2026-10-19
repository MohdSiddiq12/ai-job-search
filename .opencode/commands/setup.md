---
description: Safely build the candidate profile from local source documents
---

Set up this AI Job Search repository for use with OpenCode, not Claude Code.

Follow these instructions carefully:

1. Read the complete repository setup instructions in
   `.claude/commands/setup.md`, the root `CLAUDE.md`, and
   `documents/README.md`.

2. Inventory files in `documents/`. The primary CV is expected at
   `documents/cv/Mohammed_Siddiq_Resume.pdf`.
   Extract its text locally using `pdftotext -layout` and inspect the
   extracted contents. Do not send the CV to external services other
   than the model provider already configured for this OpenCode session.

3. Read the existing candidate-profile and related skill files before
   proposing any changes. Preserve their structure and existing useful
   guidance.

4. Treat the CV and source documents as the factual source of truth.
   Do not invent skills, experience, dates, qualifications, metrics,
   language proficiency, or achievements. Identify missing information
   and ask me questions when necessary.

5. Before editing anything, inspect `git remote -v` and explain that
   the origin is a public GitHub fork. Never push, commit, or publish
   personal information. Do not change Git remotes or repository
   settings.

6. First show me:
   - the documents discovered;
   - a concise summary of facts extracted from the CV;
   - conflicts or missing details needing my input;
   - the exact files you propose to create or modify.

7. STOP and wait for my approval before writing any candidate details.
   After approval, update the relevant profile files and root CLAUDE.md
   only as necessary. Keep all existing templates and unrelated files
   unchanged.

8. After writing, show a concise summary of changes and run `git status
   --short`. Do not stage or commit changes. Remind me to review the
   diff before any future Git operation.

Do not assume Claude Code slash commands or Claude-specific tools are
available. Use OpenCode's available file and terminal tools.
