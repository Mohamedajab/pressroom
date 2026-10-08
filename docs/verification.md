# Verification record

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
