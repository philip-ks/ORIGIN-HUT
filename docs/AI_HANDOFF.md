# Origin Hut — AI Development Handoff

**Snapshot:** 2026-09-30  
**Current milestone:** OH15 — Product Trade Master — IN PROGRESS  
**Development branch:** `work/oh15`  
**Verified implementation HEAD:** `43230651da045a7d5759170d74d28812208e5ade` — `Use unique OH14.6 disposable databases`  
**Base branch:** `main`  
**Base commit for OH14 lineage:** `9a182e2bd0396dbbc534bcb5ab1fe26e938897fe` — `Add trade market intelligence API`  
**Schema head:** `021`

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

Commit: `7e89044`

Verified endpoints:

- `GET /api/organizations/:id/intelligence`
- `GET /api/organizations/:id/trade-activities`
- `GET /api/organizations/:id/aliases`
- `GET /api/organizations/:id/evidence`

Verification:

- GitHub Actions run #29 passed Node/API and Python/Data
- disposable PostgreSQL proof applied migrations 001–015
- API started successfully on the disposable database
- intelligence summary passed
- trade-activities endpoint passed with HS2022 380210 / India filtering
- alias endpoint preserved literal + normalized identity semantics
- evidence/source endpoint returned organization, alias and activity provenance
- evidence entityType filter passed
- migration head remained 015
- OH13 production remained unchanged at `11|123982|3`

## OH14.6 — Product-first end-to-end proof — COMPLETE

Activated Carbon / HS2022 `380210` / India -> UAE is now the first
fully verified Product-first counterparty vertical.

Verified local proof on 2026-09-30 established:

- canonical Activated Carbon Product created through the API
- explicit Product -> HS2022 `380210` confirmation
- migrations 001-015 applied cleanly
- API typecheck and build passed
- disposable API became healthy
- UN Comtrade India -> UAE 2024 export fact canonicalized
- market-intelligence API returned the UAE market
- Jacobi official web evidence created a Product + HS scoped manufacturing activity
- Saiph official web evidence created a Product + HS scoped supply activity
- product-filtered counterparty discovery returned the expected organizations
- organization evidence/provenance inspection passed
- migration head remained 015
- production database remained unchanged at `11|123982|3`

The proof runner uses a unique disposable database per run. On the
verified Windows/PostgreSQL runtime, final disposal emitted a
`checkpoint request failed` warning after the proof had already
passed. This is an environment cleanup issue and does not change the
verified production-invariance result.

GitHub Actions run #38 for commit `4323065` passed both:

- Node / API
- Python / Data

## Next milestone

### OH15 — Product Trade Master

Strengthen Product as the center of Origin Hut before building
commercial offers and Incoterms.

Initial scope:

- canonical Product trade profile
- structured specifications
- units of measure
- packaging / weights / dimensions
- origin and manufacturer context
- compliance / document references
- clear separation between generic Product and manufacturer SKU/variant
- product-level provenance

Incoterms belong to the later commercial-offer layer, not to the Product itself.

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


## OH15 start

OH14 was fast-forwarded into `main` at
`52fc069226ec1e301287a070e24b47e3a8672cf7`.

`work/oh15` was created from that verified release.

OH15.1 begins with Manufacturer Product Identity. Generic
`products` remain the stable trade concept. Manufacturer-specific
grade/SKU/GTIN/origin belongs in `manufacturer_products`.


## OH15.2 — Units of Measure

Migration 017 introduces a canonical unit-of-measure reference layer
using UN/CEFACT Recommendation 20 common codes for physical units.

Initial safe-conversion dimensions:

- mass: KGM, GRM, TNE
- length: MTR, CMT, MMT
- volume: MTQ, LTR

Automatic conversion is permitted only inside the same dimension.
Cross-dimension conversion (for example kilograms to litres) is
rejected unless a later product-specific rule supplies the required
physical relationship.

Packaging codes are deliberately deferred to the packaging milestone
and should use UN/CEFACT Recommendation 21 rather than being mixed
into physical UOM.


## OH15.3 — Structured Specifications

Migration 018 introduces:

- specification_definitions
- product_specifications

A specification is typed as numeric, text or boolean and belongs to
exactly one subject:

- generic Product
- manufacturer Product

Numeric definitions may carry a measurement dimension and canonical
UOM. Specification values may retain source type, canonical source
record, confidence, validity dates and metadata.

Only one active, open-ended value for the same definition is allowed
per subject. Historical values remain possible by closing or
deactivating the previous value.


## OH15.4 — Product Packaging

Migration 019 introduces:

- package_types using UN/CEFACT Recommendation 21 codes
- packaging_configurations for manufacturer Products

Packaging supports:

- primary / secondary / tertiary / logistics levels
- product content quantity + physical UOM
- nested packaging counts
- net / gross weight
- package dimensions
- default package designation
- source record / confidence / validity / metadata

The inner package in a packaging hierarchy must belong to the same
manufacturer Product.

Shipping containers remain outside packaging and will belong to a
later logistics/load-plan layer.


## OH15.5 — Manufacturing / Origin

Migration 020 introduces:

- organization_sites
- manufacturer_product_sites

The canonical model keeps organization country, site country and
manufacturer-product country of origin as separate facts.

Sites support manufacturing, packaging, warehouse,
distribution-center, office, laboratory and other roles.

Manufacturer Products can link to sites as:

- manufactured_at
- packaged_at
- stored_at
- distributed_from

The model intentionally permits contract manufacturing: a Product's
manufacturer organization and the organization operating a
manufacturing site do not have to be the same legal entity.


## OH15.6 — Documents / Compliance / Provenance

Migration 021 introduces:

- product_document_types
- product_documents
- compliance_frameworks
- product_compliance_records

Documents and compliance records belong to exactly one Product
subject: generic Product OR manufacturer Product.

Documents support issuer, document number, issue/expiry dates,
verification status, file/reference metadata, SHA-256, canonical
source record, confidence and metadata.

Compliance records support jurisdiction/framework, requirement code,
registration number, status, validity, evidence document, canonical
source record and confidence.

A compliance evidence document must belong to the same Product
subject as the compliance record. API-created source-backed records
also create entity_source_links for provenance.
