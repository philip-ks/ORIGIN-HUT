# OH17 — Landed Cost Engine

**Branch:** `work/oh17`  
**Status:** COMPLETE / VERIFIED  
**Starting schema head:** `025`  
**Final schema head:** `026`

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


## OH17.1 — Scenario + component engine

Migration 026 introduces:

- `landed_cost_component_types`
- `landed_cost_scenarios`
- `landed_cost_components`

Core calculation rule:

```text
offer amount in scenario currency
+ components where included_in_offer = false
= landed cost total
```

Components marked `included_in_offer = true` remain visible as
commercial breakouts but are not added again. This prevents
double-counting costs already contained in terms such as CIF.

Scenario calculations preserve:

- source Commercial Offer
- target quantity / UOM
- target currency
- destination
- offer FX rate / date / source when cross-currency
- source offer amount
- included component total
- added component total
- final landed cost total
- landed cost per target UOM
- source provenance

Component calculations support:

- fixed amount + currency + explicit FX rate
- percentage + explicit taxable base

No statutory tariff, tax or FX rate is hard-coded.

API:

- `GET /api/landed-cost/component-types`
- `GET /api/landed-cost/scenarios`
- `POST /api/landed-cost/scenarios`
- `GET /api/landed-cost/scenarios/:id`
- `POST /api/landed-cost/scenarios/:id/components`


## OH17.2 — Product Workbench Landed Cost tab

The Product Workbench now includes a `Landed Cost` tab.

It loads Product-scoped scenarios through the canonical API and shows:

- source seller / Incoterm
- target quantity
- destination
- offer amount in scenario currency
- included cost breakouts
- added costs
- total landed cost
- landed cost per target UOM
- scenario provenance coverage

Operational values remain API-backed; the UI contains no hard-coded
commercial cost values.


## OH17.3 — End-to-End Landed Cost proof

Repository-tracked proof runner:

    infra/windows/Run-OH17-Proof.ps1

The proof uses synthetic commercial and costing assumptions only. It
does not assert a real supplier price, FX rate, customs duty or
destination charge.

The proof verifies:

```text
CIF Commercial Offer
  -> target 20 TNE
  -> USD scenario
  -> offer amount USD 23,000
  -> included insurance USD 500 (no double count)
  -> added destination handling USD 600
  -> synthetic 5% duty on explicit USD 23,600 base
  -> duty USD 1,180
  -> landed total USD 24,780
  -> landed cost USD 1,239 / TNE
```

It also verifies:

- source Commercial Offer remains unchanged
- explicit cross-currency FX rate/date/source is retained
- Product-scoped scenario discovery
- scenario + component provenance
- production database invariance


## OH17 Verified Closeout

Verified locally on 2026-10-01 with:

    infra/windows/Run-OH17-Proof.ps1

Final result:

```text
OH17 LANDED COST ENGINE PROOF PASSED
SCHEMA HEAD 026 PASS
PRODUCT WORKBENCH BUILD PASS
SOURCE COMMERCIAL OFFER IMMUTABILITY PASS
OFFER AMOUNT NORMALIZATION PASS
INCLUDED COST NO DOUBLE COUNT PASS
ADDED FIXED COST PASS
PERCENTAGE DUTY BASE PASS
LANDED COST TOTAL 24780 USD PASS
LANDED COST PER TNE 1239 USD PASS
CROSS-CURRENCY FX PROVENANCE PASS
LANDED COST PROVENANCE PASS
PRODUCT-SCOPED SCENARIO DISCOVERY PASS
PRODUCTION DATABASE UNCHANGED
```

Verified integrated behavior:

- migrations 001-026 apply cleanly
- API typecheck/build passes
- Product Workbench production build passes
- source CIF Commercial Offer remains unchanged
- target quantity normalization produces USD 23,000 offer amount for 20 TNE at USD 1,150/TNE
- included insurance breakout is retained but not double-counted
- added destination handling increases scenario total
- percentage duty retains an explicit taxable base and rate
- final synthetic scenario totals USD 24,780 / USD 1,239 per TNE
- cross-currency FX rate/date/source are retained explicitly
- Product-scoped landed-cost scenario discovery works
- scenario and component provenance links are present
- production database remains unchanged at `11|123982|3`

The local Windows/PostgreSQL runtime again emitted a final disposable-
database cleanup warning:

```text
checkpoint request failed
```

This occurred after the proof footer and after production invariance
had already passed. It is a local PostgreSQL cleanup/runtime issue,
not an OH17 proof failure.

GitHub Actions run #74 on commit `00c9c67` passed:

- Node / API
- Python / Data
- Web build

OH17 is complete.

The next milestone is OH18 — RFQ + Quotation Workflow.
