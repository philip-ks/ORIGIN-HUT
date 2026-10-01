# OH16 — Commercial Offers + Incoterms

**Branch:** `work/oh16`  
**Status:** in progress  
**Starting schema head:** `022`

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
