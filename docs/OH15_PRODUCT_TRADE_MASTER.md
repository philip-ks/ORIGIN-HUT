# OH15 — Product Trade Master

**Branch:** `work/oh15`  
**Status:** in progress  
**Starting schema head:** `015`

## Purpose

OH15 makes Product a first-class trade object before Origin Hut
implements commercial offers, Incoterms, landed cost, RFQ,
quotation, order or shipment execution.

The central rule is:

> A generic trade Product is not the same thing as a manufacturer's
> concrete catalogue item, grade, model or SKU.

## Canonical hierarchy

```text
Product
"Activated Carbon"
    |
    +-- accepted HS classification
    +-- market intelligence
    +-- generic specifications
    |
    v
Manufacturer Product
"Manufacturer X / Grade AC-1000"
    |
    +-- manufacturer
    +-- brand
    +-- grade / model
    +-- SKU
    +-- GTIN
    +-- country of origin
    +-- manufacturer-specific specifications
    |
    v
Packaging / Commercial Offer / Transaction
```

## OH15.1 — Manufacturer Product Identity

Migration 016 introduces `manufacturer_products`.

`products` remains the canonical generic trade concept so all
existing Product IDs, HS classifications, organization activities,
trade intelligence and provenance remain valid.

The OH8-era fields on `products`:

- `manufacturer_id`
- `brand`
- `sku`
- `gtin`

remain for backward compatibility only. New manufacturer-specific
identity belongs in `manufacturer_products`.

### Manufacturer product fields

- generic Product
- manufacturer organization
- explicit country of origin
- name
- brand
- grade
- model code
- SKU
- GTIN
- description
- status
- identifiers
- attributes
- metadata

Country of origin is explicit and must never be inferred from the
manufacturer organization's country.

## API

OH15.1 adds:

- `GET /api/manufacturer-products`
- `GET /api/manufacturer-products/:id`
- `PATCH /api/manufacturer-products/:id`
- `GET /api/products/:id/manufacturer-products`
- `POST /api/products/:id/manufacturer-products`

The API requires the selected manufacturer organization to carry the
`manufacturer` role.

## Next increments

### OH15.2 — Units of Measure

Implemented by migration 017.

Physical units use UN/CEFACT Recommendation 20 common codes where
applicable. The first canonical dimensions are:

- mass: KGM, GRM, TNE
- length: MTR, CMT, MMT
- volume: MTQ, LTR

Origin Hut stores conversion scale/offset against one canonical base
unit per dimension and rejects cross-dimension automatic conversion.

Packaging types are intentionally not treated as physical UOM.
They belong to the later packaging model using UN/CEFACT
Recommendation 21.

### OH15.3 — Structured Specifications

Implemented by migration 018.

The specification engine is generic rather than
activated-carbon-specific.

Definitions are typed as:

- numeric
- text
- boolean

Values may belong either to the generic Product or to one
manufacturer Product, never both. Numeric definitions can constrain
the expected measurement dimension and default UOM.

Specification values retain:

- qualifier (exact / nominal / minimum / maximum / range)
- numeric, range, text or boolean value
- UOM
- validity dates
- source type
- canonical source record
- confidence
- metadata / provenance context

### OH15.4 — Packaging

Implemented by migration 019.

Package type names use UN/CEFACT Recommendation 21 and remain
separate from physical units in Recommendation 20.

A manufacturer Product can now carry packaging configurations such
as:

```text
25 KGM woven-plastic bag
    ->
40 bags per pallet
```

Packaging records support:

- primary / secondary / tertiary / logistics level
- package type
- package material
- product content quantity + UOM
- nested inner package + count
- net and gross weight
- length / width / height
- default package
- validity
- source / confidence / provenance metadata

Shipping containers are deliberately not modelled as packaging.
Container loading belongs to the later logistics/load-plan layer.

### OH15.5 — Manufacturing / Origin

Implemented by migration 020.

Origin Hut now separates:

```text
organization country
        !=
manufacturing-site country
        !=
country of origin
```

Organization sites are reusable operational locations with explicit
site type, country, optional UN/LOCODE, address and geography.

Manufacturer Products link to sites through evidenced relationships:

- manufactured_at
- packaged_at
- stored_at
- distributed_from

Country of origin remains an explicit Manufacturer Product field and
is not silently derived from an organization's headquarters or a
site location.

The model also permits contract manufacturing where the site operator
is a different legal organization from the Product's manufacturer /
brand owner.

### OH15.6 — Documents / Compliance / Provenance

Implemented by migration 021.

Product documents now support common trade/product evidence including:

- SDS
- TDS
- COA
- Certificate of Origin
- test reports
- certificates
- regulatory registrations

Each document belongs to either the generic Product or a manufacturer
Product, with issuer, issue/expiry dates, verification state,
document reference/file metadata, SHA-256, source record, confidence
and provenance metadata.

Compliance frameworks and Product compliance records are modelled
separately from the documents that may prove them. A compliance
evidence document must belong to the same Product subject as the
compliance record.

### OH15.7 — Product Workbench

Implemented as the first real Origin Hut frontend workflow.

The stock Next.js starter is replaced with:

- API-backed Product directory
- Product Workbench route at `/products/:id`
- horizontal/sticky tabs rather than long vertical module stacking
- Overview
- Classification
- Specifications
- Manufacturer Products
- Packaging
- Sites
- Documents
- Compliance
- Counterparties

Operational values are fetched from Origin Hut APIs using
`NEXT_PUBLIC_API_BASE_URL`. The UI contains no mock Product,
company, market or compliance records.

Frontend build is now part of GitHub Actions.

Incoterms remain outside Product and belong to the later commercial
offer layer.
