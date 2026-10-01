# Origin Hut — AI Development Handoff

**Snapshot:** 2026-10-01  
**Current milestone:** OH18 — RFQ + Quotation Workflow — IN PROGRESS  
**Development branch:** `work/oh18`  
**Verified implementation HEAD:** `f6a56a4fd95a9d20ea4a19fa7e97a1a0ab249f28` — verified OH17 release
**Base branch:** `main`  
**OH15 base commit:** `52fc069226ec1e301287a070e24b47e3a8672cf7` — verified OH14 release  
**Schema head:** `028`

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


## OH15.7 — Product Workbench

The stock Next.js starter has been replaced by the first real Origin
Hut frontend workflow.

Routes:

- `/` — API-backed Product directory
- `/products/:id` — Product Workbench

Workbench tabs:

- Overview
- Classification
- Specifications
- Manufacturer Products
- Packaging
- Sites
- Documents
- Compliance
- Counterparties

All operational values come from Origin Hut APIs. Frontend build is
now included in CI.


## OH15.8 — Product Master Provenance Hardening

Migration 022 adds source-backed provenance to Manufacturer Product
identity and automatic `entity_source_links` for all OH15 entities
that carry `canonical_source_record_id`.

OH15 schema head is now `022`.


## OH15 verified closeout

OH15 Product Trade Master was locally proven on 2026-10-01 and
GitHub Actions run #56 passed on commit `0457108`.

Verified proof:

- schema head 022
- Product Workbench build
- generic Product + canonical base UOM
- Product -> HS2022 380210
- UOM conversion
- Manufacturer Product + explicit origin
- structured specifications
- packaging
- manufacturing site
- documents + compliance
- unified Product provenance
- production database unchanged

OH15 is complete.

## Next milestone

OH16 — Commercial Offers + Incoterms.

The canonical rule remains:

```text
Product != Commercial Offer

Commercial Offer
  = seller
  + manufacturer Product / packaging
  + quantity basis
  + price
  + currency
  + MOQ
  + lead time
  + payment terms
  + Incoterm
  + Incoterms edition
  + named place
  + validity
  + provenance
```

Statistical FOB/CIF values in trade_flow remain market statistics and
must never be treated as transaction Incoterms.


## OH16 start

OH15 was fast-forwarded into `main` at
`cd09fefee4c46a5521044bce331082a2b147094c`.

`work/oh16` was created from that verified release.

OH16.1 begins with a canonical Incoterms reference layer. Commercial
offers will reference Incoterm rule + edition + named place/port.
Statistical FOB/CIF values remain separate market-data measures.


## OH16.2 — Commercial Offers

Migration 024 introduces canonical `commercial_offers`.

The offer layer owns seller/buyer context, Manufacturer Product,
packaging, price/currency/UOM, MOQ, lead time, payment terms,
Incoterm + edition, named place/port, validity and provenance.

Maritime Incoterms require a canonical trade location. Price and MOQ
UOMs must match the underlying generic Product base-UOM dimension.


## OH16.3 — Maritime location integrity

Migration 025 requires maritime Incoterms to reference a canonical
trade location carrying the UN/LOCODE maritime-port function.


## OH16 verified closeout

OH16 Commercial Offers + Incoterms was locally proven on 2026-10-01
and GitHub Actions run #65 passed on commit `ab563de`.

Verified proof:

- schema head 025
- Product Workbench build
- Incoterms 2020 reference semantics
- Product -> Manufacturer Product -> packaging
- Commercial Offer price / currency / UOM
- MOQ / lead time / payment terms
- CIF + Jebel Ali / AEJEA
- maritime port validation
- Commercial Offer provenance
- Product-scoped offer discovery
- production database unchanged at `11|123982|3`

The local disposable-database cleanup emitted a post-proof checkpoint
warning. This did not affect production invariance or OH16 proof
results.

OH16 is complete.

## Next milestone

OH17 — Landed Cost Engine.

OH17 should compare supplier offers on a common delivered-cost basis
without mutating the original Commercial Offer.

Core boundary:

```text
Commercial Offer
  + route / origin / destination
  + cost components
  + duty / tax assumptions
  + FX assumptions
  = landed-cost scenario
```

The engine must preserve what the Incoterm already includes and only
add costs that remain outside the seller's commercial responsibility.


## OH17 start

OH16 was fast-forwarded into `main` at
`968b2b35679d61b2f1a37c18ecca016d83df53c5`.

`work/oh17` was created from that verified release.

OH17 introduces derived landed-cost scenarios. The source Commercial
Offer remains immutable; costing assumptions, FX, duty/tax inputs and
added cost components belong to the scenario layer.

Schema head remains `025` until the first OH17 migration.


## OH17.1 — Landed Cost Scenario engine

Migration 026 introduces landed-cost scenarios and cost components.

The source Commercial Offer remains immutable.

Included components are informational and do not increase the total;
only added components increase landed cost. Cross-currency scenarios
require explicit FX rate/date/source. Percentage cost components
retain both rate and taxable base.


## OH17 verified closeout

OH17 Landed Cost Engine was locally proven on 2026-10-01 and
GitHub Actions run #74 passed on commit `00c9c67`.

Verified proof:

- schema head 026
- Product Workbench build
- source Commercial Offer immutability
- offer amount normalization
- included cost no-double-count
- added fixed cost
- percentage duty base
- final synthetic total USD 24,780
- final synthetic USD 1,239/TNE
- cross-currency FX provenance
- scenario + component provenance
- Product-scoped scenario discovery
- production DB unchanged at `11|123982|3`

The post-proof disposable-database checkpoint warning remains a local
PostgreSQL cleanup issue and does not affect the verified result.

OH17 is complete.

## Next milestone

OH18 — RFQ + Quotation Workflow.

The next operating layer should turn buyer demand into a traceable
commercial workflow:

```text
Buyer requirement
  -> RFQ
  -> supplier invitations
  -> supplier Commercial Offers
  -> Landed Cost Scenarios
  -> comparison
  -> buyer quotation
```

Tariff and duty intelligence can later feed OH17 scenarios
automatically without blocking the transactional RFQ/quotation layer.


## OH18 start

OH17 was fast-forwarded into `main` at
`f6a56a4fd95a9d20ea4a19fa7e97a1a0ab249f28`.

`work/oh18` was created from that verified release.

OH18 introduces the transactional RFQ + Quotation workflow while
reusing the existing canonical Product, Commercial Offer and Landed
Cost objects.

Schema head remains `026` until the first OH18 migration.


## OH18.1 — RFQ foundation

Migration 027 introduces RFQ headers, Product request lines and
supplier invitations.

RFQ demand stays distinct from Commercial Offer response. Product,
Manufacturer Product, packaging, UOM, destination, currency and
Incoterm objects are referenced canonically rather than duplicated.


## OH18.2 — Supplier responses

Migration 028 links RFQ line + invited supplier to a canonical
Commercial Offer. Offer pricing/Incoterm/packaging remain in the
Commercial Offer rather than being duplicated into RFQ response data.
