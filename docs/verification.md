# Verification record

## Visitor demo and hosted verification — 14 October 2026

- 76 tests passed against local PostgreSQL 17, including concurrent editor and scheduler tests; 96.25% coverage of `publishing` on Windows/Python 3.14.5.
- Ruff, Django system/migration checks, OpenAPI validation and the hosted production configuration check passed.
- [GitHub CI](https://github.com/Mohamedajab/pressroom/actions/runs/38497767218) passed on Python 3.12 and 3.13, with PostgreSQL and the Chromium visitor flow; the container build also passed.
- The deployed [visitor demo](https://pressroom-demo.onrender.com/demo/) was checked directly: `/health/` returned HTTP 200 with `status: ok`.
- Chromium created two independent temporary visitor workspaces. The author created a private draft, submitted it for review, switched to editor and published it. A later unapproved edit stayed out of the public page.
- The second visitor could not access the first visitor's workspace (HTTP 403). The 390 px layout had no horizontal document overflow, and the browser reported no JavaScript page errors.

These are deployment smoke checks, not a traffic benchmark or independent security audit. Free hosting and database-expiry limitations remain documented in [hosted demo setup](hosted-demo.md).

## Original application verification

Local verification on 8 October 2026, Windows / Python 3.12.10 / SQLite:

- 68 backend tests passed; 2 PostgreSQL-only concurrency tests skipped locally.
- 97.47% line coverage of the `publishing` package on this run, including management commands and views.
- Ruff lint and format checks passed.
- Django system checks and migration drift checks passed.
- OpenAPI schema validation passed with warnings treated as failures.
- Production configuration passed Django's deployment checks with warnings treated as failures.
- A real Chromium browser completed author creation → submit → editor approval → public read → archive.
- Browser smoke verification checked mobile document overflow at 390px, and captured desktop/mobile screenshots.

GitHub Actions verification for commit `b8c9ecb`:

- **70 tests passed** on both Python 3.12 and Python 3.13 with PostgreSQL 16, including both real concurrent-worker tests.
- **97.63% backend line coverage** on both PostgreSQL runs.
- Both quality jobs and the Docker image build completed successfully.
- [Verified CI run](https://github.com/Mohamedajab/pressroom/actions/runs/37799259398).

This record describes the observed checks, not a production traffic or security audit. The CI badge in the README shows the latest run; the linked run preserves the evidence for this implementation.
