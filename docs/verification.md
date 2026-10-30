# Verify the publishing workflow

Start the local demo using the README, then run:

```sh
pip install -e '.[browser]'
python -m playwright install chromium
python scripts/demo_smoke.py --base-url http://127.0.0.1:8000 --record-video
```

The browser uses Tab and Enter to reach and activate publishing controls. It creates a story,
submits it, switches to an editor and publishes it. A later draft stays private. Two tabs then
load one revision: the first saves; the second receives HTTP 409 with its text preserved and
focus on the error summary. A duplicate slug exercises server validation. A separate visitor
cannot read the first workspace. The mobile view must not overflow.

The recording in `recordings/publishing-workflow.webm` uses sample data and a local server.
It follows the main tab; the second-tab conflict is in `screenshots/edit-conflict.jpg`.

## Verification on 30 October 2026

Windows, Python 3.12.10, Django 5.2.18, Playwright 1.64.1 Chromium; local SQLite.

- `pytest --cov=publishing --cov-report=term-missing --cov-fail-under=85 -q`: 76 passed, two PostgreSQL concurrency tests skipped, 96.32% coverage.
- The browser command above passed, including conflicts, keyboard operation and validation.
- Django checks, migration drift, OpenAPI validation and production security checks: passed.
- `ruff check .` and `ruff format --check .`: passed.

The existing PR CI runs the tests and browser workflow against PostgreSQL 16 on Python 3.12
and 3.13. Its result must establish database concurrency evidence; SQLite does not verify row
locks. No hosted deployment was changed.

## Suggested CV bullets

- Built a Django publishing application with role-based review, revision history and approved public snapshots.
- Added keyboard-driven browser checks for publishing, private edits and conflicts, with focused error feedback that preserves unsaved text.
