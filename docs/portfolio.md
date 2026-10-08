# Demo and interview guide

## A five-minute demonstration

1. Sign in as `author`. Show the dashboard, statuses, filters and a draft.
2. Edit a previously published page. Open its public URL and show that unapproved text has not appeared.
3. Submit the draft for review. Switch to `editor` and approve it. Refresh the public site and read the new snapshot.
4. Restore an earlier revision and show that it becomes a new draft while the old live snapshot stays public.
5. Show the audit trail and API documentation. Open the tests covering draft leaks and stale edits, then the passing PostgreSQL CI run.

## A CV bullet to adapt after understanding the implementation

> Developed Pressroom, a Django/DRF publishing platform with workspace-based permissions, revision history, approval workflows and scheduled publishing; implemented transactional updates, optimistic concurrency checks and regression tests, with PostgreSQL CI and Docker deployment tooling.

Mention AI assistance honestly when asked. Describe only work and design decisions you can explain. Do not claim commercial users, production traffic, independent authorship of every line, or a hosted deployment unless those things are true. Replace any test counts or coverage claims with the results of the current checked commit.

## Questions you should be ready to answer

- Why is the published content stored as a revision pointer rather than a boolean on the draft?
- How does `expected_version` differ from a database lock? Why are both useful?
- What happens if two workers try to publish the same scheduled page?
- Why is checking membership on a list endpoint necessary even with object permissions?
- What happens to a schedule when an author changes the content after approval?
- Why do you create a fresh revision when restoring old content?
- How are CSRF-protected HTML forms different from token-authenticated API requests?
- What does SQLite fail to tell you about PostgreSQL concurrency?
- How would you extend search, media storage, invitations and observability?

## Meaningful work to own next

Take one extension from design to delivery yourself: write the issue, explain the tradeoff, implement the change, test failure cases and open a pull request against this repository. An email invitation workflow or PostgreSQL full-text search would be a strong next step. Keep a short engineering journal documenting what you learned and why you changed the code.
