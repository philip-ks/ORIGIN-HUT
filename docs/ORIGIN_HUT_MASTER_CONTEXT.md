# Origin Hut — Master Project Context

**Continuity snapshot:** 2026-10-01  
**Repository:** `philip-ks/ORIGIN-HUT`  
**Current development branch:** `work/oh16`  
**Verified OH14.4 implementation commit:** `1de53b5`  
**Schema head:** `023`

## Purpose

This file is the durable high-level memory for Origin Hut. Future AI sessions should use the repository as implementation truth and this document for stable product intent, architectural boundaries, and decisions that should survive individual chat limits.

When sources disagree, prefer current committed code, migrations, tests and CI over old chat wording.

## Product definition

Origin Hut is an export/import intelligence and trade operating platform.

Core principle:

> External data sources are inputs, not the product. Origin Hut normalizes trade, market, company, compliance, logistics and transaction information into its own canonical model and exposes workflows through its own APIs.

The platform combines trade/market intelligence, company/counterparty intelligence, and future operating workflows such as RFQ, quotation, costing, compliance, documents, finance, logistics and execution.

## Architecture

### `apps/web`

Next.js frontend foundation.

### `apps/api`

TypeScript/Fastify canonical application API.

Current route domains include reference data, HS classification, products, organizations, relationships, trade flows, market intelligence and counterparties.

### `services/data`

Python data layer for external connectors, canonicalization, provenance, PostgreSQL integration, analytical storage, UN Comtrade planning/refresh, company-web intelligence and organization identity resolution.

### `database/migrations`

PostgreSQL/PostGIS canonical schema. Current schema head: migration 023.

### `storage`

Analytical/raw storage foundation introduced in OH13.

### `infra`

Docker/local and Windows scheduling infrastructure. Production direction remains Azure-oriented; Vercel may serve frontend preview/development use cases but is not the intended dependency for the complete production platform.

## Non-negotiable data principles

### Backend/database is the source of truth

Operational frontend values should originate in canonical APIs, concerned-user input, or source-backed ingestion. Avoid hard-coded operational values in UI modules.

### Provenance is first-class

Preserve source lineage such as:

```text
data_source
  -> source_record
  -> canonical entity/fact
  -> entity_source_links
```

Provider credentials must never be persisted in canonical metadata, manifests or audit artifacts.

### Statistical evidence != company evidence

`India exported HS 380210 to UAE` does not prove `Company X exported HS 380210 to Company Y`.

Aggregate statistical data is market evidence. Company claims require company-level evidence.

### Organization role != product-specific activity

A general role such as `manufacturer` or `exporter` is different from `ABC Carbon manufactures HS 380210 in India`.

Product/HS/market-scoped commercial evidence belongs in `organization_trade_activities`.

### Relationship != activity

`organization_relationships` describes how two organizations interact.

`organization_trade_activities` describes an organization's evidenced activity around a product/HS code/market.

### Shipment facts are separate

Do not fabricate bills of lading, vessels, containers, shipment parties, or bilateral shipment facts from statistical trade data.

## Canonical subject areas implemented so far

- source/provenance records
- countries and reference geography
- currencies and country-currency relationships
- UN/LOCODE trade locations
- HS2022 reference hierarchy
- HS classification requests/confirmed classifications
- products
- organizations and roles
- organization relationships
- trade-flow facts
- market intelligence
- UN Comtrade ingestion and analytical storage
- organization trade activities
- counterparty intelligence
- company-web evidence ingestion
- organization aliases and conservative identity resolution

## Identity-resolution policy

OH14.4 establishes conservative organization identity resolution.

```text
LEI exact
  -> registration number + country exact
  -> tax identifier + country exact
  -> known normalized alias + country
  -> no automatic match
```

Rules:

- strong identifier conflicts are hard stops
- ambiguous aliases are hard stops
- domain evidence alone does not auto-merge
- name similarity alone does not auto-merge
- canonical legal name is preserved on reuse
- source spellings are stored as aliases
- literal alias spelling and normalized matching identity are separate concepts

Alias provenance semantics:

- `alias` preserves literal spelling
- `normalized_alias` supports matching
- multiple literal spellings may normalize to the same value
- literal variants remain separate rows
- source provenance is retained through alias/source links

## Analytical storage / Comtrade policy

OH13 established:

```text
provider
  -> Bronze raw response
  -> checksum/manifest
  -> Silver normalized Parquet
  -> canonical PostgreSQL fact
  -> provenance
  -> API
```

Important invariants include immutable source revisions, idempotent canonicalization, independent ingestion-run history, credential-safe authenticated transport, historical planner/checkpoint support, scheduled refresh orchestration, valid zero-observation handling, and PostgreSQL/CI validation.

## Current milestone

OH15 — Product Trade Master — complete and verified.

OH16 — Commercial Offers + Incoterms — in progress.

OH16 begins by introducing a canonical Incoterms reference layer
before commercial offers are created.

Core commercial boundary:

```text
Product
  -> Manufacturer Product
  -> Packaging
  -> Commercial Offer
       -> price / currency
       -> quantity basis / MOQ
       -> lead time
       -> payment terms
       -> Incoterm + edition
       -> named place / port
       -> validity
       -> provenance
```

Statistical FOB/CIF values in `trade_flows` remain market
statistics and are not contractual Incoterms.

## Historical UI note

Earlier Origin Hut chats contain broader dashboard/workflow concepts, including command, port, vessel, shipment, route, alerts, PMIS, governance and external-data areas. Treat those as historical product/design context unless implementation exists in the rebuilt repository.

## Infrastructure direction

```text
local development
  -> local proof
  -> GitHub work branch
  -> GitHub Actions
  -> preview/deployment environments
  -> Azure-oriented production
```

## Continuity rule

A new AI session should read this file, `docs/AI_HANDOFF.md`, `docs/ORIGIN_HUT_MILESTONE_HISTORY.md`, the current milestone document, active branch/HEAD/CI, and relevant migrations/tests before continuing.
