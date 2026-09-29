# Origin Hut — Milestone History

**Scope:** Current September 2026 rebuilt repository. Older pre-rebuild chats are useful product/design history but are not assumed to describe currently implemented code.

| Stage | Commit / range | Main outcome |
|---|---|---|
| Foundation | `fa846bb` | Rebuilt Origin Hut platform foundation |
| OH5 | `78ed5b5` | Production HS2022 reference ingestion |
| OH6 | `bdc0219` | Reference intelligence API + ISO country/currency relationships |
| OH7 | `b665dfa` | HS classification intelligence workflow |
| OH8 | `c296b64` | Product catalogue + classification workbench |
| OH9 | `b6a2595` | Organization / trade-party directory |
| OH10 | `ffd444a` | Trade relationship network and counterparty API |
| OH11 | `79976d4` | Trade-flow fact model and intelligence API |
| OH12 | `9a182e2` | Trade market intelligence API |
| OH13 | `d14a845` → `cb13106` | Analytical storage + UN Comtrade ingestion/refresh hardening |
| OH14.1 | `c7d30cd` | Organization trade activity model |
| OH14.2 | `19b5b6d` | Counterparty intelligence API |
| OH14.3 | `ca3b0df` | Reusable company-web intelligence connector |
| OH14.4 | `1de53b5` | Organization aliases + conservative identity resolution |

## Persistent decisions by milestone

### Foundation
Canonical internal model; external providers are inputs.

### OH5
HS2022 is ingested into a normalized/provenanced hierarchy rather than exposed as a raw provider snapshot.

### OH7
Classification retrieval/ranking is advisory; accepted classification is an explicit canonical/provenanced decision.

### OH9
Organizations are reusable canonical entities, not duplicated names embedded in each workflow.

### OH10
Organization-to-organization relationships are distinct canonical facts from roles and product-specific activity.

### OH11/OH12
Statistical trade-flow facts support market intelligence but must not be converted into company-level claims without company-level evidence.

### OH13
Established Bronze raw evidence, checksums/manifests, Silver Parquet, canonical PostgreSQL facts, immutable source revisions, idempotency, authenticated/resumable UN Comtrade ingestion, zero-data semantics, scheduled refresh orchestration, and CI/PostgreSQL validation.

OH13 commit sequence includes:

- `d14a845` analytical ingestion foundation + CI
- `8bd780b` idempotent Comtrade canonicalization
- `904f7f7` PostgreSQL integration hardening
- `6e4440a` observation revision semantics
- `fe07313` authenticated/resumable ingestion
- `ef35ef9` scheduled refresh orchestration
- `b311c9b` no-data handling
- `1d15f17` Windows scheduler
- `402850b` documented Comtrade query authentication
- `479be86` scheduled runtime hardening
- `cb13106` Windows PowerShell scheduler fix

### OH14.1
Introduced `organization_trade_activities` through migration 014.

General organization roles are distinct from product/HS/market-scoped evidence.

### OH14.2
Implemented `GET /api/intelligence/counterparties`.

Counterparty results use company-level activity evidence and must not be inferred from aggregate Comtrade facts.

### OH14.3
Implemented reusable company-web intelligence acquisition/evidence/canonicalization/provenance connector.

### OH14.4
Commit `1de53b5`.

Implemented migration 015 and conservative organization identity resolution:

- `organization_aliases`
- literal alias provenance
- normalized identity keys
- alias-aware organization and counterparty search
- strong-identifier precedence
- ambiguous/conflicting match hard stops
- company-web identity integration
- unit/PostgreSQL integration coverage

Final proof:

- migrations 001–015 passed
- targeted identity PostgreSQL tests passed
- company-web PostgreSQL idempotency passed
- full Python regression: 48 tests passed
- Node typecheck/build passed
- OH13 production DB unchanged
- GitHub Actions run #27 passed Python/Data and Node/API

## Next

OH14.5: organization activity/evidence/detail APIs.

OH14.6: activated-carbon India/UAE end-to-end counterparty proof around HS2022 `380210`.

## Legacy / pre-rebuild history

Earlier Origin Hut chats may reuse OH labels differently. Use them for product intent and ideas, but do not assume those implementations exist unless confirmed by the current repository.
