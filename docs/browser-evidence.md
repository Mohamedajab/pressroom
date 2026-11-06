# Browser workflow evidence

Run against the opt-in visitor demo, using an isolated local PostgreSQL database:

```bash
python scripts/demo_smoke.py --browser chromium --record-video
python scripts/demo_smoke.py --browser firefox
```

Each browser gets a separate `docs/evidence/<browser>/` directory. Failures save
screenshots of open pages and a trace before propagating the exception; success
also retains a trace. CI uploads this directory even after failure. Chromium runs
in the existing quality job and Firefox runs in a separate PostgreSQL-backed job.

| Workflow | Assertion in `scripts/demo_smoke.py` |
|---|---|
| Publication visibility | Draft URL returns 404; approved URL returns 200 with approved text |
| Private edits | Public response excludes saved private draft text |
| Edit conflict | Stale POST returns 409, retains unsaved body, focuses error summary |
| Keyboard controls | Real Tab navigation reaches controls and Enter activates them |
| Mobile layout | 390×844 viewport has no document overflow and role control remains visible |
| Session isolation | A separate demo context cannot open the first workspace (403) |
| Validation | Duplicate slug retains submitted body and focuses errors |

[Chromium assertion record](evidence/chromium/workflow-results.json),
[recording](evidence/chromium/recordings/publishing-workflow.webm),
[publication screenshot](evidence/chromium/publication.jpg),
[mobile screenshot](evidence/chromium/demo-mobile.jpg).

Measured locally on 6 November 2026: Python 3.12.10 and PostgreSQL 17.11,
**78 tests passed, including both concurrency tests**, 96.45% publishing coverage.
The Chromium visitor workflow passed. Firefox could not launch on this Windows
host (`spawn UNKNOWN`); the separate Linux CI job is the authoritative Firefox
verification. No application behaviour was changed by this PR.
