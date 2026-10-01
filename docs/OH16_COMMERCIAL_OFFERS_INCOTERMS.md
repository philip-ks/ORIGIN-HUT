# OH16 — Commercial Offers + Incoterms

**Branch:** `work/oh16`  
**Status:** COMPLETE / VERIFIED  
**Starting schema head:** `022`  
**Final schema head:** `025`

## Purpose

OH16 introduces the commercial layer that sits between Product Master
and later costing / RFQ / quotation / order execution.

The canonical boundary is:

```text
Product
  !=
Commercial Offer
```

A Product describes what the goods are.

A Commercial Offer describes a seller's commercial proposition for
those goods at a point in time.

## Non-negotiable distinction

The existing `trade_flows.fob_value` and `trade_flows.cif_value`
fields are statistical monetary measures sourced from trade data.

They are not contractual Incoterms and must never be interpreted as:

```text
FOB Kochi Port — Incoterms 2020
CIF Jebel Ali Port — Incoterms 2020
```

Commercial Incoterms belong only in the offer / quotation /
transaction layer.

## OH16.1 — Incoterms reference

Migration 023 introduces `incoterm_rules`.

Incoterms 2020 contains eleven rules.

Rules for any mode or modes of transport:

- EXW — Ex Works
- FCA — Free Carrier
- CPT — Carriage Paid To
- CIP — Carriage and Insurance Paid To
- DAP — Delivered at Place
- DPU — Delivered at Place Unloaded
- DDP — Delivered Duty Paid

Rules for sea and inland waterway transport:

- FAS — Free Alongside Ship
- FOB — Free On Board
- CFR — Cost and Freight
- CIF — Cost Insurance and Freight

Origin Hut also records the semantic role of the named location:

- delivery place
- destination place
- shipment port
- destination port

This allows later Commercial Offer validation to require the correct
kind of named location without embedding legal rules in free text.

## API

OH16.1 adds:

- `GET /api/reference/incoterms`
- `GET /api/reference/incoterms/:edition/:code`

## Planned OH16.2 — Commercial Offer

The next schema increment should model:

```text
seller
+ manufacturer Product
+ packaging
+ quantity / price basis
+ currency
+ MOQ
+ lead time
+ payment terms
+ Incoterm rule + edition
+ named place / port
+ validity
+ provenance
```

Buyer may be optional so Origin Hut can represent both:

- seller catalogue / market offers
- buyer-specific quotations

Commercial Offer must remain separate from Product identity.


## OH16.2 — Commercial Offers

Migration 024 introduces `commercial_offers`.

A Commercial Offer now binds:

- seller organization
- optional buyer organization
- Manufacturer Product
- optional Product packaging configuration
- unit price
- ISO 4217 currency
- price UOM
- optional MOQ + UOM
- optional lead time
- optional payment terms
- Incoterm rule + edition
- named place / port
- validity
- source record / confidence / provenance

Named-location semantics are enforced:

- maritime rules require a canonical trade location
- any-mode rules may use free named-place text, a canonical trade
  location, or an organization site

Product-dimension integrity is also enforced:

- price UOM must match the generic Product base-UOM dimension
- MOQ UOM must match the generic Product base-UOM dimension
- packaging must belong to the same Manufacturer Product

API:

- `GET /api/commercial-offers`
- `POST /api/commercial-offers`
- `GET /api/commercial-offers/:id`

Commercial Offer provenance links through `entity_source_links`.


## OH16.3 — Maritime named-location integrity

Migration 025 strengthens maritime Incoterm validation.

For FAS, FOB, CFR and CIF, a Commercial Offer must reference a
canonical UN/LOCODE trade location whose function codes include the
maritime-port function in position 1.

This prevents a maritime term from being attached to an airport,
inland-only location or arbitrary location record.

The OH16 test fixture uses the published Cochin/Kochi UN/LOCODE
`INCOK`.


## OH16.4 — End-to-End Commercial Offer Proof

Repository-tracked proof runner:

    infra/windows/Run-OH16-Proof.ps1

The proof uses synthetic commercial terms only. It does not claim a
real supplier has quoted the demonstrated price, MOQ, lead time or
payment terms.

The integrated proof chain is:

```text
Activated Carbon
  -> HS2022 380210
  -> Manufacturer Product
  -> 25 KGM packaging
  -> seller + buyer
  -> USD / TNE price basis
  -> MOQ / lead time / payment terms
  -> CIF Incoterms 2020
  -> Jebel Ali / AEJEA
  -> offer provenance
  -> Product Workbench build
```

Negative proof checks also reject:

- maritime Incoterms without a canonical port
- price UOMs from a different physical dimension than the Product

Production database invariance is checked before and after the proof.


## OH16 Verified Closeout

Verified locally on 2026-10-01 with:

    infra/windows/Run-OH16-Proof.ps1

Final result:

```text
OH16 COMMERCIAL OFFER + INCOTERMS PROOF PASSED
SCHEMA HEAD 025 PASS
PRODUCT WORKBENCH BUILD PASS
INCOTERMS 2020 REFERENCE PASS
PRODUCT -> MANUFACTURER PRODUCT -> PACKAGING PASS
COMMERCIAL OFFER PRICE / CURRENCY / UOM PASS
MOQ / LEAD TIME / PAYMENT TERMS PASS
CIF + JEBEL ALI NAMED PORT PASS
MARITIME PORT VALIDATION PASS
COMMERCIAL OFFER PROVENANCE PASS
PRODUCT-SCOPED OFFER DISCOVERY PASS
PRODUCTION DATABASE UNCHANGED
```

Verified integrated behavior:

- migrations 001-025 apply cleanly
- API TypeScript typecheck passes
- API build passes
- Product Workbench production build passes
- Incoterms 2020 reference layer exposes all 11 rules
- Product remains separate from Commercial Offer
- Manufacturer Product and packaging are preserved as offer scope
- price basis uses canonical currency + UOM
- MOQ / lead time / payment terms remain commercial fields
- CIF offer preserves edition 2020 and canonical destination port AEJEA
- maritime rules reject free-text-only ports
- maritime rules require UN/LOCODE maritime-port function
- incompatible cross-dimension price UOMs are rejected
- Commercial Offer provenance links through entity_source_links
- Product-scoped Commercial Offer discovery works
- production database remains unchanged at `11|123982|3`

The local Windows/PostgreSQL runtime again emitted a final disposable-
database cleanup warning:

```text
checkpoint request failed
```

This occurred after the proof had already passed and after production
database invariance had been verified. Treat it as a local PostgreSQL
cleanup/runtime issue, not a Commercial Offer proof failure.

GitHub Actions run #65 on commit `ab563de` passed both:

- Node / API
- Python / Data
- Web build

OH16 is complete.

The next milestone is OH17 — Landed Cost Engine.
