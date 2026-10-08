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

This record describes the observed checks, not a production traffic or security audit. PostgreSQL race tests and the Docker build are configured in GitHub Actions; their result is visible in the repository's CI workflow.
