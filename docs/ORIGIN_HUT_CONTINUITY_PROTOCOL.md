# Origin Hut — AI Continuity Protocol

## Goal

Make ChatGPT thread limits irrelevant to Origin Hut continuity.

The repository is the durable implementation source of truth.

## Permanent sources

1. **Code truth:** `philip-ks/ORIGIN-HUT`
2. **Current state:** `docs/AI_HANDOFF.md`
3. **Stable architecture/context:** `docs/ORIGIN_HUT_MASTER_CONTEXT.md`
4. **Implementation history:** `docs/ORIGIN_HUT_MILESTONE_HISTORY.md`
5. **Milestone design:** current `docs/OH*.md`

## End-of-increment ritual

Before considering an implementation increment complete:

1. run relevant unit tests
2. run PostgreSQL proof where applicable
3. run Node typecheck/build where applicable
4. run `git diff --check`
5. inspect status/diff
6. commit to active work branch
7. push
8. verify GitHub Actions
9. update `AI_HANDOFF.md`
10. update milestone/master context for durable architectural changes

## Start-of-new-chat ritual

A fresh Origin Hut chat should read:

1. Master Context
2. AI Handoff
3. Milestone History
4. current milestone document
5. active branch and HEAD
6. current migration head
7. relevant CI/tests

Then continue from the documented gate instead of reconstructing the project from old chats.

A sufficient user prompt is:

`Continue Origin Hut from GitHub.`

## Local-only work rule

If VS Code has uncommitted changes, do not mutate the same remote branch through GitHub automation until divergence is understood.

Local uncommitted files are not visible through the GitHub connector.

Prefer validate locally -> commit -> push -> inspect remotely, or explicitly provide the patch for pre-commit review.

## Logs and secrets

Do not commit raw operational logs blindly. Scan for passwords, API keys, bearer tokens, database URLs, subscription keys and private connection strings.

Sanitized milestone summaries belong in Git. Raw command logs can remain local/ignored.

## Source precedence

When sources conflict:

1. current committed code/migrations/tests
2. current local diff/status supplied by developer
3. CI/runtime proof
4. current handoff/milestone docs
5. older chat history

Historical chat wording never silently overrides current implementation.

## Current state — 2026-09-29

- active branch: `work/oh14`
- OH14.4 implementation commit: `1de53b5`
- schema head: migration 015
- final local DB proof passed
- GitHub Actions run #27 passed
- next increment: OH14.5 organization activity/evidence/detail endpoints
