# Origin Hut — AI Development Handoff

**Snapshot:** 2026-09-29  
**Current milestone:** OH14 — Counterparty Intelligence  
**Development branch:** `work/oh14`  
**Verified implementation HEAD:** `1de53b53c53b49b30ddd35cf9a114281116fb952` — `Add organization alias identity resolution`  
**Base branch:** `main`  
**Base commit for OH14 lineage:** `9a182e2bd0396dbbc534bcb5ab1fe26e938897fe` — `Add trade market intelligence API`  
**Schema head:** `015`

## Verified state

OH14.4 is committed, pushed, locally proven, and GitHub-CI proven.

Local final post-provenance proof established:

- migrations 001–015 apply cleanly
- migration head = `0000000015`
- literal alias spellings remain separate provenance rows
- normalized aliases remain conservative identity match keys
- zero normalized-alias conflict targets remain
- four literal-alias conflict targets are present
- ambiguous aliases do not auto-merge
- conflicting strong identifiers stop resolution
- Private Limited / Pvt. Ltd. variants can resolve through aliases
- repeated company-web source ingestion remains idempotent
- full Python regression passed: 48 tests
- API TypeScript typecheck passed
- API build passed
- `git diff --check` passed
- OH13 production database remained unchanged at `11|123982|3`

GitHub Actions for commit `1de53b5`, run #27:

- Python / Data — success
- Node / API — success

## OH14 objective

Return source-backed organizations with product/HS/market-scoped commercial activities and inspectable evidence while preserving the distinction between:

1. statistical market evidence
2. company-level evidence
3. organization-to-organization relationships
4. future shipment-level evidence

## Completed OH14 sequence

### OH14.1 — Trade activity model

Commit: `c7d30cd`

Introduced `organization_trade_activities` through migration 014.

### OH14.2 — Counterparty intelligence API

Commit: `19b5b6d`

Implemented `GET /api/intelligence/counterparties`.

### OH14.3 — Reusable company-web intelligence connector

Commit: `ca3b0df`

Implemented source-backed company-web acquisition, evidence validation, canonicalization, provenance, and PostgreSQL apply support.

### OH14.4 — Organization aliases and identity resolution

Commit: `1de53b5`

Introduced migration 015, `organization_aliases`, conservative organization identity resolution, alias-aware organization/counterparty search, company-web identity integration, literal alias provenance preservation, and identity unit/PostgreSQL integration tests.

Resolution precedence:

```text
LEI exact
  -> registration number + country exact
  -> tax identifier + country exact
  -> known normalized alias + country
  -> no automatic match
```

Supporting domains are evidence signals only and do not independently cause an automatic merge.

Name similarity alone must never silently merge organizations.

## Core architecture

- `apps/web` — Next.js frontend foundation
- `apps/api` — TypeScript/Fastify application API
- `services/data` — Python ingestion, canonicalization, provenance and analytical storage
- `packages/shared` — shared application contracts/utilities
- `database/migrations` — canonical PostgreSQL/PostGIS schema
- `infra` — Docker/local/Windows scheduling infrastructure

## Provenance model

External source facts should preserve a chain such as:

```text
data_source
  -> source_record
  -> canonical entity/fact
  -> entity_source_links
```

Important boundaries:

- aggregate UN Comtrade facts must not create company-level claims automatically
- organization role != product/HS/market activity
- organization activity != organization-to-organization relationship
- statistical market fact != shipment-level fact

## Current next increment

### OH14.5 — Organization activity / evidence / detail endpoints

Expected direction:

- expand organization detail with trade activities
- expose activity evidence/source coverage
- expose alias/source identity evidence where useful
- preserve canonical/provenance boundaries
- support future tabbed organization UI:
  - Overview
  - Products
  - Trade
  - Relationships
  - Locations
  - Sources
  - Documents

## Later OH14 target

### OH14.6 — Activated-carbon India/UAE end-to-end counterparty proof

Use HS2022 `380210` as the first complete source-backed counterparty vertical.

## Workflow

1. Edit/test locally in VS Code.
2. Commit to the active work branch.
3. Push.
4. GitHub Actions validates.
5. Read repository and CI directly.
6. Merge to `main` only after the milestone is green and intentionally closed.

Raw PowerShell command logs remain local unless sanitized.

## Continuity files

Future AI sessions should read, in order:

1. `docs/ORIGIN_HUT_MASTER_CONTEXT.md`
2. `docs/AI_HANDOFF.md`
3. `docs/ORIGIN_HUT_MILESTONE_HISTORY.md`
4. current milestone document
5. active branch / HEAD / CI state
