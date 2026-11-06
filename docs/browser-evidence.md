# Browser checks

Start the local demo, then run:

```bash
python scripts/demo_smoke.py --browser chromium --record-video
python scripts/demo_smoke.py --browser firefox
```

Results go into `docs/evidence/<browser>/`. If a check fails, the script saves
screenshots of open pages and a trace, then exits with an error. A successful run
also keeps its trace. CI uploads these files even when a check fails.

| Check | Expected result |
|---|---|
| Publishing | Draft page returns 404; approved page returns 200 with the approved text |
| Private edits | Public page does not show saved draft changes |
| Edit conflict | Stale save returns 409, keeps unsaved text and focuses the error message |
| Keyboard | Tab reaches the controls; Enter activates them |
| Mobile | At 390×844, the page fits the screen and the role button is visible |
| Separate sessions | A second visitor cannot open the first visitor's workspace |
| Duplicate slug | The form keeps the submitted text and focuses the error message |

[Results](evidence/chromium/workflow-results.json) ·
[Recording](evidence/chromium/recordings/publishing-workflow.webm) ·
[Published page](evidence/chromium/publication.jpg) ·
[Mobile view](evidence/chromium/demo-mobile.jpg)

On 6 November 2026, all 79 local tests passed with Python 3.12.10 and PostgreSQL
17.11, including both concurrency tests. Publishing coverage was 96.45%.
Chromium passed locally. Firefox could not launch on this Windows machine, but
both browser workflows passed in [Linux CI](https://github.com/Mohamedajab/pressroom/actions/runs/42226869847).
CI runs Firefox in its own job. Shared traces have local paths and demo session
credentials removed.
