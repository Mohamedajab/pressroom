# Contributing

Use Python 3.12 or 3.13. Install `requirements-dev.txt`, migrate the database and seed the local demo as shown in the README.

Open an issue for significant changes. Describe the user-visible problem and expected behaviour. For small fixes, a focused pull request is enough.

Put workflow and permission rules in `publishing/services.py` so HTML and API paths stay consistent. Check both paths when changing behaviour. Add regression tests that reproduce the problem, including denied access or invalid transitions when applicable.

Before submitting:

```bash
ruff check .
ruff format --check .
pytest --cov=publishing --cov-fail-under=85
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --fail-on-warn --file openapi.yaml
```

Run CI against PostgreSQL for lock/concurrency changes. Include migrations when changing models, and explain data migration or release implications. Update screenshots when the user interface changes substantially.

AI assistance is allowed. Review generated code, understand what you submit and disclose substantial assistance in the PR description. Never include real credentials or private content in prompts, fixtures, screenshots or commits.
