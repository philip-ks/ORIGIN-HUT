# Origin Hut - AI Development Handoff

## Current Milestone

OH13 - Analytical Storage & UN Comtrade Ingestion Foundation

## Development Branch

work/oh13

## Base Branch

main

## Last Completed Milestone

OH12 - Trade Market Intelligence

Commit:
9a182e2 Add trade market intelligence API

## OH13 Architecture

UN Comtrade API
  -> Bronze raw response + SHA-256 + manifest
  -> Silver normalized partitioned Parquet
  -> Curated PostgreSQL trade_flows + provenance
  -> Market Intelligence API

## Verified State

- Analytical storage foundation created
- Polars installed and tested
- DuckDB installed and tested
- Parquet write/read regression passed
- Manifest/checksum regression passed
- UN Comtrade Bronze/Silver connector implemented
- India to UAE HS380210 2024 export live ingestion passed
- Bronze raw-response checksum verified
- record-level SHA-256 provenance verified
- Silver Parquet checksum verified
- DuckDB read-back verified
- PostgreSQL canonicalization implemented
- UN Comtrade data source registered
- immutable trade_observation source record preserved
- ingestion_run_records audit coverage verified
- canonical trade_flow created
- entity_source_links provenance verified
- reporter and partner resolved through ISO3
- repeated identical ingestion reuses source record
- repeated identical ingestion reuses canonical trade_flow
- second identical ingestion creates an independent ingestion audit run
- canonical source-record pointer verified
- raw trade value and FOB value verified against canonical trade_flow
- aggregate transport mode 0 normalized to NULL
- aggregate customs code C00 normalized to NULL
- PostgreSQL integration suite established
- revised Comtrade observation creates a new immutable source version
- revised observation updates the existing canonical trade flow
- World/W00 partner remains NULL through PostgreSQL canonicalization
- monthly period normalization verified through PostgreSQL
- disposable integration database verified against migrations 001-012
- local PostgreSQL host connections normalize localhost to 127.0.0.1
- PostgreSQL connection timeout hardened to 5 seconds
- Python regression passed
- API TypeScript typecheck passed
- API build passed
- Migration 012 remains schema head
- no Migration 013 required currently

## Current Database State

data_sources: 5
ingestion_runs: 7
source_records: 123980
ingestion_run_records: 123981
entity_source_links: 123974
trade_flows: 1
migration_head: 012

## Current Comtrade State

data_sources: 1
ingestion_runs: 2
completed_runs: 2
failed_runs: 0
source_records: 1
ingestion_run_records: 2
trade_flows: 1
provenance_links: 1

## Verified Canonical Observation

reporterISO3: IND
partnerISO3: ARE
flowDirection: export
classification: HS2022
hsCode: 380210
periodStart: 2024-01-01
periodEnd: 2024-12-31
periodType: annual
quantity: 4268940
quantityUnit: kg
netWeightKg: 4268940
grossWeightKg: 0
tradeValueUsd: 6410583.797
fobValueUsd: 6410583.797
currency: USD
status: published
isProvisional: false

## Idempotency Proof

First apply:
- source record: inserted
- trade flow: inserted
- ingestion run: completed

Second identical apply:
- source record: reused
- trade flow: reused
- ingestion run: completed

Invariant after second apply:
- one logical Comtrade source record
- one canonical Comtrade trade flow
- one provenance link
- two ingestion-run audit links

## Current OH13 Files

.gitignore
.github/workflows/origin-hut-ci.yml
docs/AI_HANDOFF.md
services/data/requirements.txt
services/data/src/connectors/comtrade.py
services/data/src/connectors/comtrade_canonical.py
services/data/src/storage/__init__.py
services/data/src/storage/manifests.py
services/data/src/storage/parquet.py
services/data/tests/test_analytical_storage.py
services/data/tests/test_comtrade_connector.py
services/data/tests/test_comtrade_canonical.py
storage/parquet/.gitkeep

## CI

GitHub Actions workflow:
.github/workflows/origin-hut-ci.yml

Checks:
- Node API typecheck
- Node API build
- Python compile
- Python tests

## Next Action

Complete OH13 production hardening.

Priority checks:

- revised source-record version handling
- World partner normalization through the full PostgreSQL path
- monthly-period normalization through the full PostgreSQL path
- preview versus production UN Comtrade source semantics
- production UN Comtrade authenticated API configuration
- production-scale ingestion batching and pagination
- retain Bronze raw artifacts and Silver Parquet outside Git

## Development Workflow

1. Edit and test locally in VS Code.
2. Commit to work/oh13.
3. Push work/oh13.
4. GitHub Actions runs.
5. ChatGPT reads repository and CI logs directly.
6. Fix locally and repeat.
7. Merge to main only after OH13 is green.

Raw PowerShell logs remain local and are not committed.
