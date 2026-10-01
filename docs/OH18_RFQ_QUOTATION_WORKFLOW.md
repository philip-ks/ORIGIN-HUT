# OH18 — RFQ + Quotation Workflow

**Branch:** `work/oh18`  
**Status:** in progress  
**Starting schema head:** `026`

## Purpose

OH18 turns Origin Hut from a Product / Offer / Cost intelligence
system into a buyer-supplier commercial operating workflow.

The canonical flow is:

```text
Buyer requirement
  -> RFQ
  -> supplier invitations
  -> supplier Commercial Offers
  -> Landed Cost Scenarios
  -> offer comparison
  -> buyer quotation
```

Existing canonical objects must be reused rather than copied into
free-text workflow records.

## Core boundaries

### RFQ != Commercial Offer

An RFQ expresses buyer demand.

A Commercial Offer expresses a seller's commercial response.

### Quotation != Commercial Offer

A supplier Commercial Offer is source-side seller pricing.

A buyer-facing Quotation is an Origin Hut commercial document /
proposal assembled from selected Product, offer and costing inputs.

### Landed Cost != Quotation price

Landed Cost is an internal analytical result.

Quotation price may use landed cost as an input, but may also include
margin, commercial adjustments and validity terms. The source landed
cost must remain inspectable.

## OH18.1 — RFQ model

Initial canonical objects:

### rfqs

Suggested fields:

- RFQ reference
- requester / buyer organization
- destination country
- optional destination trade location / site / text
- requested currency
- requested Incoterm preference / optional flexibility
- issue date
- response due date
- status
- notes
- provenance / metadata

Suggested statuses:

- draft
- issued
- partially_responded
- responded
- closed
- cancelled

### rfq_lines

Each line should reference canonical Product data.

Suggested fields:

- RFQ
- generic Product
- optional Manufacturer Product restriction
- requested quantity
- UOM
- optional packaging requirement
- requested specification snapshot/reference
- target delivery date
- notes

The line must not duplicate Product master fields unless a frozen
commercial snapshot is explicitly required.

### rfq_suppliers

Tracks invitation state per supplier:

- RFQ
- supplier organization
- invitation status
- invited at
- viewed / acknowledged at
- response due
- notes

Suggested statuses:

- invited
- acknowledged
- declined
- responded
- withdrawn

## OH18.2 — Supplier response linkage

Supplier responses should resolve to canonical Commercial Offers.

A response link should preserve:

- RFQ
- RFQ line
- supplier
- Commercial Offer
- response timestamp
- response status
- provenance

The Commercial Offer remains reusable outside the RFQ.

## OH18.3 — Offer comparison

Origin Hut should compare responses on common analytical bases:

- offered quantity
- currency
- Incoterm
- named place
- MOQ
- lead time
- payment terms
- packaging
- landed-cost scenario
- landed cost per common UOM
- evidence coverage

The system may expose sortable comparison views, but must not silently
alter source offers.

## OH18.4 — Buyer quotation

A quotation should be a separate canonical object.

Suggested fields:

- quotation reference
- customer / buyer
- source RFQ
- issue date
- valid until
- currency
- status
- payment terms
- delivery terms / Incoterm
- notes
- metadata / provenance

### quotation_lines

Each line should preserve:

- Product
- optional Manufacturer Product
- quantity / UOM
- selected source Commercial Offer
- optional selected Landed Cost Scenario
- internal cost basis
- quoted unit price
- quoted line total
- margin / markup inputs if used
- packaging / delivery context

The quotation price is commercial output and must never overwrite:

- Product
- supplier Commercial Offer
- Landed Cost Scenario

## Important constraints

1. RFQ buyer demand must be separate from supplier response.
2. Supplier response must link to a canonical Commercial Offer.
3. Multiple suppliers can respond to the same RFQ line.
4. One supplier can provide multiple alternate offers.
5. Landed Cost scenarios remain derived analytical objects.
6. Quotation prices are separate commercial outputs.
7. Margin must be explicit if Origin Hut computes it.
8. All state transitions should be auditable.
9. No hard-coded operational values in the frontend.
10. Provenance remains first-class.

## First end-to-end proof target

Use Activated Carbon again so continuity stays comparable:

```text
Buyer in UAE
  -> RFQ for 20 TNE Activated Carbon
  -> invite Supplier A and Supplier B
  -> record two Commercial Offers
  -> derive two Landed Cost Scenarios
  -> compare normalized cost / TNE
  -> select one source basis
  -> create buyer Quotation
  -> prove source RFQ / Offer / Landed Cost remain unchanged
```

Synthetic commercial values should be used for the proof unless a
real source is explicitly supplied.


## OH18.1 — RFQ master, lines and supplier invitations

Migration 027 introduces:

- `rfqs`
- `rfq_lines`
- `rfq_suppliers`

The RFQ header preserves:

- buyer organization
- optional requester organization
- destination country + optional canonical location/site/text
- optional requested ISO currency
- optional requested Incoterm rule + edition
- Incoterm flexibility flag
- issue date / response deadline
- workflow status
- provenance

RFQ lines preserve:

- canonical generic Product
- optional Manufacturer Product restriction
- optional packaging restriction
- requested quantity + canonical UOM
- target delivery date
- structured requirement JSON
- provenance

Supplier invitations preserve:

- canonical supplier organization
- invitation / acknowledgement / response state
- invitation / acknowledgement / response timestamps
- response deadline
- provenance

Database integrity rules enforce:

- destination location/site country matches RFQ destination country
- requested UOM dimension matches Product base-UOM dimension
- Manufacturer Product restriction belongs to the requested Product
- packaging restriction belongs to the selected Manufacturer Product
- packaging restriction cannot exist without a Manufacturer Product restriction
- buyer cannot be invited as its own supplier

API:

- `GET /api/rfqs`
- `POST /api/rfqs`
- `GET /api/rfqs/:id`
- `POST /api/rfqs/:id/lines`
- `POST /api/rfqs/:id/suppliers`


## OH18.2 — Supplier response linkage

Migration 028 introduces `rfq_responses`.

A response links:

- RFQ
- RFQ line
- invited supplier record
- canonical Commercial Offer
- response status / timestamp
- provenance

No commercial terms are copied into `rfq_responses`.

Validation enforces:

- RFQ line belongs to the same RFQ
- supplier invitation belongs to the same RFQ
- Commercial Offer seller matches the invited supplier
- buyer-specific Commercial Offer matches the RFQ buyer
- Commercial Offer Product matches the RFQ line Product
- Manufacturer Product restrictions are respected
- packaging restrictions are respected

A submitted response updates the supplier invitation to
`responded`. RFQ status becomes `partially_responded` or
`responded` based on supplier terminal states.

API:

- `GET /api/rfqs/:id/responses`
- `POST /api/rfqs/:id/responses`


## OH18.3 — Offer comparison read model

Migration 029 introduces `rfq_response_comparison`.

Comparison is derived from:

- RFQ line demand
- submitted supplier response
- canonical Commercial Offer
- a matching calculated Landed Cost Scenario

A Landed Cost Scenario is considered comparison-ready only when:

- it belongs to the response Commercial Offer
- it is calculated
- its scenario currency matches the RFQ requested currency
- its destination country matches the RFQ destination
- its target quantity normalizes to the RFQ requested quantity

If those conditions are not met, the response remains visible but is
marked non-comparable. Origin Hut does not fabricate FX or cost data.

The comparison normalizes:

- offer price per RFQ requested UOM in the offer currency
- landed cost per RFQ requested UOM in the RFQ requested currency

API:

- `GET /api/rfqs/:id/comparison`


## OH18.4 — Buyer quotation model

Migration 030 introduces:

- `quotations`
- `quotation_lines`

Quotation header preserves:

- issuer organization
- customer organization
- optional source RFQ
- currency
- issue / validity dates
- status
- payment terms
- Incoterm + named place/location/site
- provenance

Quotation lines preserve:

- Product / optional Manufacturer Product / packaging
- optional source RFQ line
- optional source Commercial Offer
- optional source Landed Cost Scenario
- quantity / UOM
- internal cost basis
- explicit pricing method
- explicit pricing rate when derived
- quoted unit price
- quoted line total
- provenance

Supported pricing methods:

- `manual`
- `markup_percent`
- `margin_percent`

If a calculated Landed Cost Scenario is linked, its scenario currency
must match the Quotation currency and its per-UOM cost becomes the
line's internal cost basis after safe UOM normalization.

Source RFQ, Commercial Offer and Landed Cost objects remain immutable.

API:

- `GET /api/quotations`
- `POST /api/quotations`
- `GET /api/quotations/:id`
- `POST /api/quotations/:id/lines`


### OH18.4 traceability hardening

Quotation validation also requires:

- maritime quotation terms use a canonical UN/LOCODE maritime port
- source RFQ line Manufacturer Product / packaging restrictions remain satisfied
- a source Commercial Offer tied to an RFQ line must be a submitted RFQ response
- a source Landed Cost Scenario must be accompanied by its source Commercial Offer

This prevents a quotation from citing an unrelated offer or costing
scenario merely because Product identity happens to match.
