# API guide

Private routes accept DRF token authentication (`Authorization: Token ...`) or a browser session. Session-authenticated mutations require a CSRF token. Public routes accept anonymous requests and expose approved snapshots only.

`/api/docs/` contains the generated interactive specification. `/api/schema/` returns OpenAPI. List endpoints use pages of 20 items with `count`, `next`, `previous` and `results`.

## Routes

Replace `{workspace}` with a workspace slug and `{id}` with a page UUID.

| Method | Route | Purpose |
|---|---|---|
| GET, POST | `/api/workspaces/{workspace}/pages/` | List or create pages |
| GET, PUT | `/api/workspaces/{workspace}/pages/{id}/` | Read or update the working draft |
| POST | `/api/workspaces/{workspace}/pages/{id}/workflow/` | Submit, publish, schedule, reject or archive |
| GET | `/api/workspaces/{workspace}/pages/{id}/revisions/` | Revision history |
| POST | `/api/workspaces/{workspace}/pages/{id}/restore/` | Restore a numbered revision as a draft |
| GET | `/api/workspaces/{workspace}/events/` | Workspace audit history |
| GET, POST | `/api/workspaces/{workspace}/members/` | Read membership; owner-only add/update |
| GET | `/api/public/{workspace}/pages/` | Published content list |
| GET | `/api/public/{workspace}/pages/{slug}/` | One published snapshot |

Page lists accept `q` (title/excerpt), `status` and `page`. Public lists accept `q` and `page`, with searches performed against **published** titles and excerpts. Member lists are not paginated in this release.

## Update a draft

`PUT` is a complete content update, not a partial patch. Slugs cannot change through this endpoint.

```json
{
  "expected_version": 3,
  "title": "A clearer headline",
  "excerpt": "A short introduction.",
  "body": "## The story\n\nMarkdown goes here."
}
```

## Submit and approve

```json
{"expected_version": 4, "action": "submit"}
```

The response contains version 5. An editor then submits:

```json
{"expected_version": 5, "action": "publish"}
```

For future publication, an editor can use an ISO 8601 timestamp with an explicit timezone offset:

```json
{"expected_version": 5, "action": "schedule", "scheduled_for": "2030-11-01T09:00:00Z"}
```

Without an explicit offset, Django interprets input in Europe/London. Future times are required. The scheduler must be running to publish due content.

## Restore

```json
{"expected_version": 6, "number": 2}
```

This creates version 7 with version 2's content. An existing live snapshot remains public until the restored draft is approved.

## Errors

| Status | Meaning |
|---|---|
| 400 | Invalid content, duplicate slug, invalid transition or invalid schedule |
| 401 | Missing or invalid authentication for a private endpoint |
| 403 | Insufficient membership/role, or a failed CSRF check |
| 404 | Resource absent from the selected workspace, or no public snapshot |
| 409 | Stale `expected_version`; fetch current state before retrying |
| 429 | Rate limit reached |

Preserve the user's unsaved text when handling a 409. Fetch the latest version and let them compare or merge rather than silently resubmitting over newer work.
