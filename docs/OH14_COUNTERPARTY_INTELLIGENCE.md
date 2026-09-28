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

Alias support should be normalized in a later OH14 increment rather
than storing every name variant directly on organizations.


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
Organization activity and evidence endpoints.

### OH14.4
Organization aliases / identity-resolution support.

### OH14.5
First external organization intelligence connector.

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
