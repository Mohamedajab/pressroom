# Deployment and operations

The Compose file is a local PostgreSQL demo. A remote deployment needs a TLS reverse proxy, managed secret values, persistent PostgreSQL storage and a scheduled worker. No hosted production deployment is created by this repository.

## Environment

| Variable | Purpose |
|---|---|
| `DEBUG` | Defaults to `true` for local setup. Set to `false` remotely. |
| `SECRET_KEY` | Unique random secret, minimum 50 characters when DEBUG is false. |
| `DATABASE_URL` | PostgreSQL connection string; SQLite if omitted. |
| `ALLOWED_HOSTS` | Comma-separated hostnames without URL schemes. |
| `CSRF_TRUSTED_ORIGINS` | Full trusted HTTPS origins for browser form requests. |
| `TRUST_PROXY` | Enable only when the reverse proxy strips incoming forwarded protocol headers and sets its own. |

Django reads process environment variables. `.env` is consumed by Docker Compose, not automatically by a local Python shell.

Generate a secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Use the platform's secret manager or environment configuration. Do not commit real secrets. The repository excludes `.env`, databases, logs, coverage data and virtual environments.

## Release sequence

1. Run CI and review the changes.
2. Take a database backup and verify the restore procedure.
3. Run `python manage.py migrate --noinput` as one release job.
4. Run `python manage.py collectstatic --noinput` during the build.
5. Start Gunicorn workers and the `publish_due` scheduler against the same database.
6. Check health, sign-in, a private workspace and the public publication.

Compose's one-shot migration service gates startup so app and scheduler do not race database migrations. Containers run as a non-root user. PostgreSQL has a named volume; deleting that volume deletes demo data.

## Scheduler

Run `python manage.py publish_due` every minute using the deployment platform's scheduler, or retain the Compose worker's 30-second polling loop. It is safe for PostgreSQL workers to overlap. Publication can occur up to one polling interval after the scheduled time.

Observe command failures and restart failures rather than assuming due pages were published. The command exits non-zero if a database operation fails, allowing a job runner to report it.

## Health and backups

`GET /health/` executes `SELECT 1`; it returns 200 on a database response and 503 when unavailable. It intentionally does not return database details. Monitor the public route separately to check the full serving path.

Use PostgreSQL backups and restore drills appropriate to your deployment. Revision history is not a database backup. Add a shared cache for consistent multi-worker API rate limits, request logging and an error reporting service before running a scaled public deployment.

## Verification

With production environment variables set:

```bash
python manage.py check --deploy --fail-level WARNING
```

This checks Django configuration; it does not prove a reverse proxy, TLS certificate or database backup is correctly configured.
