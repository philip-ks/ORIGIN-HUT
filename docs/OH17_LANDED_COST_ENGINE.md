# OH17 — Landed Cost Engine

**Branch:** `work/oh17`  
**Status:** in progress  
**Starting schema head:** `025`

## Purpose

OH17 converts a source-backed Commercial Offer into one or more
comparable landed-cost scenarios without mutating the original offer.

The canonical boundary is:

```text
Commercial Offer
  !=
Landed Cost Scenario
```

A Commercial Offer records what a seller has commercially proposed.

A Landed Cost Scenario records Origin Hut assumptions and derived
costs needed to compare that offer at a chosen destination.

## Core principle

Do not silently reinterpret an Incoterm.

The scenario must preserve:

- source Commercial Offer
- Incoterm rule + edition
- offer named place / port
- target quantity
- target destination
- target currency
- each added or already-included cost component
- FX assumptions
- duty / tax assumptions
- source / user provenance

## Planned calculation chain

```text
Commercial Offer
    |
    +-- offered quantity basis
    +-- price / currency
    +-- Incoterm + named place
    |
    v
Landed Cost Scenario
    |
    +-- target quantity
    +-- target currency
    +-- destination
    |
    +-- origin inland
    +-- origin handling
    +-- export clearance
    +-- freight / main carriage
    +-- insurance
    +-- destination handling
    +-- customs / broker
    +-- import duty
    +-- import tax
    +-- destination inland
    +-- other documented costs
    |
    v
Comparable landed cost
```

## OH17.1 — Scenario and component model

First implementation should introduce:

### landed_cost_scenarios

Suggested fields:

- Commercial Offer
- scenario reference
- target quantity
- target UOM
- target currency
- destination country
- optional destination trade location / organization site / text
- FX rate / FX date / FX source
- status
- notes / metadata
- source provenance
- calculated totals

### landed_cost_components

Suggested fields:

- scenario
- component type
- sequence
- included-in-offer flag
- amount
- currency
- quantity basis / UOM where relevant
- percentage / taxable base where relevant
- source / assumption type
- source record / confidence
- notes / metadata

Initial component vocabulary:

- goods
- origin_inland
- origin_handling
- export_clearance
- main_carriage
- insurance
- destination_handling
- customs_broker
- import_duty
- import_tax
- destination_inland
- finance
- other

## Important constraints

1. The source Commercial Offer is immutable from the scenario.
2. Landed cost must be derived, not written back into Product or Offer.
3. Cost components must identify whether they are already included in
   the commercial term or are added by the scenario.
4. Currency conversion assumptions must be explicit and inspectable.
5. Percentage duties/taxes must retain the applied rate and taxable
   base rather than only storing the final amount.
6. A scenario must be reproducible from its stored inputs.
7. Tariff/duty rates should later come from source-backed trade-policy
   data; OH17 should not hard-code statutory rates.
8. Incoterms are commercial allocation context, not a substitute for
   actual freight, insurance, duty or tax data.

## First proof target

Use the same synthetic OH16 commercial offer:

```text
Activated Carbon
  -> Manufacturer Product
  -> 25 KGM package
  -> USD / TNE offer
  -> CIF Jebel Ali / AEJEA
```

Then create a landed-cost scenario that adds only costs outside the
offer scope, preserving each assumption independently.

The proof must demonstrate that two supplier offers can eventually be
normalized to a common delivered-cost basis without changing either
source offer.
