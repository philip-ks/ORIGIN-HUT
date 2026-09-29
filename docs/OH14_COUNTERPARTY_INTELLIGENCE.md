# OH14 - Counterparty Intelligence

## Objective

OH14 extends the existing Origin Hut organization model into a
source-backed counterparty intelligence layer.

The milestone must answer questions such as:

- Which organizations manufacture a product?
- Which organizations export or import an HS code?
- Which organizations distribute a product in a target market?
- What evidence supports each counterparty claim?
- Which organizations are relevant to a selected trade market?
- How are organizations connected to one another?
- Which facts are verified, inferred, manually entered or source-derived?

OH14 does not replace the existing organization directory.


## Existing Foundation

Origin Hut already contains:

- organizations
- organization_roles
- organization_relationships
- products
- product_hs_classifications
- countries
- trade_locations
- data_sources
- source_records
- entity_source_links

The existing organization record already supports:

- legal name
- trading name
- country
- registration number
- LEI
- tax identifier
- website
- status
- address JSON
- external identifiers JSON
- metadata
- multiple organization roles

Existing organization roles describe what an organization generally IS.

Examples:

- manufacturer
- exporter
- importer
- distributor
- supplier
- buyer
- wholesaler
- retailer
- hospital
- pharmacy

Existing organization_relationships describe how two organizations
INTERACT.

Examples:

- supplies
- exports_to
- imports_from
- distributes_to

Products already support a manufacturer organization.

Products can already carry accepted HS classifications.


## Core OH14 Principle

General organization roles and product-specific trade activity are
different concepts.

Example:

    Organization:
        ABC Carbon Pvt Ltd

    General roles:
        manufacturer
        exporter

    Product / HS evidence:
        manufactures HS 380210
        exports HS 380210
        sells Activated Carbon

    Market evidence:
        activity market: India

An organization must therefore not be marked as an importer,
exporter or buyer for a specific product merely because it has a
general organization role.


## New Canonical Concept

OH14 introduces:

    organization_trade_activities

This is the product / HS / market scoped intelligence layer.


## organization_trade_activities

Proposed canonical fields:

    id
    organization_id

    activity_type

    product_id
    hs_code_id

    market_country_id

    status
    confidence

    valid_from
    valid_to

    source_type

    canonical_source_record_id

    metadata

    created_at
    updated_at


## Activity Types

Initial activity vocabulary:

    manufactures
    exports
    imports
    distributes
    supplies
    buys
    sells
    wholesales
    retails
    consumes
    services

The vocabulary remains extensible.

activity_type is deliberately separate from organization_roles.


## Product and HS Scope

A trade activity may reference:

1. a specific Origin Hut product;
2. an HS code;
3. both a product and its accepted HS code.

At least one of product_id or hs_code_id must be present.

This prevents meaningless counterparty activity with no commercial
subject.


## Market Scope

market_country_id identifies where the activity is evidenced.

Examples:

    Organization in India
    activity_type = exports
    HS = 380210
    market_country = India

or:

    Organization in UAE
    activity_type = imports
    HS = 380210
    market_country = UAE

Bilateral shipment-level origin/destination evidence belongs to OH15
Shipment Intelligence and must not be fabricated from statistical
trade data.


## Provenance

Counterparty intelligence must follow the same provenance discipline
already established for UN Comtrade.

A source-derived activity should preserve:

    data_source
        ->
    source_record
        ->
    organization_trade_activity

entity_source_links should be used to support multiple evidence
records for the same canonical activity.

canonical_source_record_id may identify the currently preferred source
revision.

No API credential belongs in canonical metadata.


## Confidence

confidence is evidence confidence, not a commercial ranking.

Range:

    0.0000 - 1.0000

Examples:

    1.0000
        official registry or explicit company statement

    lower values
        derived or less-direct evidence

Origin Hut must preserve the evidence source so users can inspect why
the fact exists.


## Statistical Trade Data Boundary

UN Comtrade trade_flows describe statistical trade observations.

They MUST NOT automatically create company-level buyer, supplier,
importer or exporter records.

Example:

    India exported HS 380210 to UAE

does NOT prove:

    Company X exported HS 380210 to Company Y

Company-level claims require company-level evidence.


## Existing Relationship Boundary

organization_relationships represents organization-to-organization
relationships.

organization_trade_activities represents an organization's evidenced
commercial activity around a product or HS code.

Examples:

    ABC Carbon
        manufactures -> HS380210

    ABC Carbon
        supplies -> XYZ Distributor

These are separate facts.


## Initial API

OH14 should introduce:

    GET /api/intelligence/counterparties

Initial filters:

    q
    country
    activityType
    hsCode
    hsNomenclature
    productId
    status
    minimumConfidence
    limit
    offset


Example:

    GET /api/intelligence/counterparties
        ?country=AE
        &activityType=imports
        &hsCode=380210


Returned organization data should include:

    organization identity
    country
    roles
    matched activities
    HS code
    product
    confidence
    evidence count
    source coverage


## Organization Detail Expansion

Existing organization detail should eventually expose:

    overview
    roles
    products
    tradeActivities
    relationships
    locations
    sources

This supports the future tabbed frontend:

    Overview
    Products
    Trade
    Relationships
    Locations
    Sources
    Documents


## Evidence Sources

OH14 source integrations can be added incrementally.

Candidate source classes include:

    official company registries
    LEI / GLEIF
    official company websites
    government trade directories
    chambers and industry associations
    customs / shipment sources where legally available
    verified manufacturer catalogues
    OpenStreetMap for facility/location evidence

Each connector must preserve source provenance.

Source licensing and reuse restrictions must be respected.


## Identity Resolution

Multiple sources may refer to the same organization.

Identity resolution should use strong identifiers first:

    LEI
    registration number + jurisdiction
    tax identifier + jurisdiction

Then supporting signals:

    normalized legal name
    domain
    address
    location

Name similarity alone must not silently merge organizations.


## Aliases

Organization aliases will be required for source matching.

Examples:

    legal spelling variants
    former names
    abbreviations
    local-language names
    source-specific names

Alias support is normalized in OH14.4 through organization_aliases.
Source-specific names remain separate from the canonical organization row.


## Location Model

organizations.address currently provides a general address field.

Origin Hut also has trade_locations / UNLOCODE.

OH14 must not assume every company facility is a UNLOCODE location.

A future organization location model should support:

    headquarters
    registered office
    factory
    warehouse
    branch
    distribution centre
    port-linked facility

and optionally reference a trade_location where appropriate.


## First Vertical Proof

Use the existing activated-carbon example:

    HS2022 380210
    India
    UAE

Target workflow:

    HS 380210
        ->
    India / UAE market
        ->
    source-backed organizations
        ->
    manufacturer / exporter / importer / distributor activity
        ->
    organization profile
        ->
    evidence / provenance


## OH14 Delivery Sequence

### OH14.1
Canonical organization_trade_activities schema.

### OH14.2
Counterparty intelligence API.

### OH14.3
Reusable company-web intelligence connector.

### OH14.4
Organization aliases / identity-resolution support.

### OH14.5
Organization activity / evidence / detail endpoints.

### OH14.6
Activated-carbon India/UAE end-to-end counterparty proof.


## Non-Goals

OH14 does NOT yet implement:

- bill-of-lading shipment records
- containers
- vessels
- shipment parties
- freight quotations
- tariffs
- landed-cost calculations
- RFQs
- purchase orders
- logistics execution
- payments

Those belong to later Origin Hut milestones.


## Milestone Boundary

OH14 is complete when Origin Hut can take a product or HS code and
return source-backed organizations with product/HS-scoped commercial
activities and inspectable evidence.

It must remain possible to distinguish:

    statistical market evidence

from:

    company-level evidence

from:

    organization-to-organization relationships

from:

    future shipment-level evidence.


## OH14.2 Implementation

Counterparty discovery endpoint:

    GET /api/intelligence/counterparties

Implemented filters:

    q
    country
    marketCountry
    activityType
    hsCode
    hsNomenclature
    productId
    status
    minimumConfidence
    limit
    offset

Pagination is organization-based rather than activity-row based.

Each matched organization exposes:

    canonical organization identity
    country
    roles
    matchedActivityCount
    matchedActivities
    activity confidence
    product
    HS code
    market country
    canonical source
    evidence count
    source coverage count

The endpoint queries organization_trade_activities only.

It does not infer companies from aggregate trade_flows.

## OH14.3 Company Web Intelligence Connector

A reusable company-web connector is now available at:

    services/data/src/connectors/company_web.py

The connector is configuration-driven and supports:

- live HTTP/HTTPS page acquisition
- retry handling for transient provider failures
- raw HTML Bronze artifact preservation
- SHA-256 content hashing
- manifest creation
- HTML-to-text extraction
- configurable evidence-term validation
- immutable source-record reuse
- independent ingestion-run audit history
- organization identity resolution
- organization role upserts
- HS-scoped organization trade activity canonicalization
- entity_source_links provenance
- dry validation mode
- PostgreSQL apply mode

The connector deliberately does not infer shipment-level relationships
or create exporter/importer claims from aggregate UN Comtrade data.

Example:

    python services/data/src/connectors/company_web.py \
      --config services/data/config/company_web_sources.example.json

Apply to PostgreSQL:

    python services/data/src/connectors/company_web.py \
      --config services/data/config/company_web_sources.example.json \
      --apply

## OH14.4 Organization Identity Resolution

OH14.4 introduces migration 015 and a conservative organization
identity-resolution layer.

Resolution precedence:

    LEI exact
        ->
    registration number + country exact
        ->
    tax identifier + country exact
        ->
    known normalized alias + country
        ->
    no automatic match

Supporting domains are observed but do not independently trigger an
automatic merge.

Ambiguous aliases and conflicting strong identifiers are hard stops.
Name similarity alone never silently merges organizations.

organization_aliases preserves canonical legal names, trading names,
source-specific names, normalized match keys and source provenance.

Company-web identity integration:

- existing canonical legal names are preserved on reuse
- source legal/trading names are recorded as aliases
- resolution method is returned by the connector
- missing evidence confidence remains NULL rather than defaulting to 1.0
- organization search includes active aliases
- counterparty search includes active aliases
- supporting domain matches are recorded but do not independently auto-merge

Alias provenance semantics:

- literal spelling variants remain separate alias rows even when they normalize to the same identity key
- normalized_alias is used for conservative identity matching
- source_record_id records the first observed source for one literal alias
- entity_source_links preserves all source evidence for that alias


## OH14.5 Organization Intelligence Detail APIs

OH14.5 adds read-only organization intelligence sub-resources without
introducing a new database migration.

Implemented endpoints:

    GET /api/organizations/:id/intelligence

        compact organization intelligence summary including role,
        product, trade-activity, alias, relationship, evidence and
        source-coverage counts.

    GET /api/organizations/:id/trade-activities

        paginated product / HS / market scoped commercial activities
        with confidence, canonical source and evidence coverage.

    GET /api/organizations/:id/aliases

        paginated literal aliases with normalized identity key,
        alias type, first observed source and provenance coverage.

    GET /api/organizations/:id/evidence

        paginated evidence links across the organization itself,
        organization aliases and organization trade activities.

The organization overview endpoint remains intentionally lightweight.
Products and relationships remain separate existing sub-resources.

The evidence list does not return the full raw source payload. It
returns inspectable source-record metadata and data-source provenance;
raw source payload remains in the provenance/storage layer.
