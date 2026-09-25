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
- disposable integration database verified against migrations 001-013
- local PostgreSQL host connections normalize localhost to 127.0.0.1
- PostgreSQL connection timeout hardened to 5 seconds
- Migration 013 trade observation revision semantics applied
- trade_flows.is_provisional is now tri-state
- TRUE means explicitly provisional
- FALSE means explicitly non-provisional
- NULL means provider revision status unknown or not supplied
- existing UN Comtrade observation corrected from FALSE to NULL
- UN Comtrade public preview access mode preserved in metadata
- provider revision status preserved as unknown
- market intelligence no longer excludes unknown revision state by default
- authenticated UN Comtrade Data API foundation implemented
- UN_COMTRADE_API_KEY loaded from environment only
- API credentials are not written to request URLs, manifests or logs
- public preview remains available as an explicit/fallback access mode
- authenticated Data API uses safe 100000-record default
- public preview retains 500-record limit
- deterministic historical query planner implemented
- historical task IDs are deterministic across equivalent plans
- resumable JSON checkpoint state implemented outside Git
- interrupted tasks recover to pending state
- transient provider failures can be deferred and retried
- planner-to-child connector access-mode mapping verified
- live 2023 and 2024 multi-period planner execution verified
- historical planner resume after provider HTTP 500 verified
- 2024 planner apply reused immutable source record and canonical trade flow
- 2023 planner apply inserted a new source record and canonical trade flow
- scheduled UN Comtrade refresh orchestrator implemented
- rolling annual refresh plans supported
- daily provider-call budget ledger implemented
- default scheduled budget reserves 50 of 500 provider calls as safety headroom
- per-task call reservation accounts for connector retry attempts
- scheduled execution requires authenticated_data by default
- unattended refresh rate is capped at 1 request per second
- refresh dry-run performs no provider, PostgreSQL, checkpoint or budget-state writes
- Python regression passed
- API TypeScript typecheck passed
- API build passed
- Migration 013 is schema head
- Migration 013 verified on disposable and real local PostgreSQL databases

## Current Database State

data_sources: 5
ingestion_runs: 9
source_records: 123981
ingestion_run_records: 123983
entity_source_links: 123975
trade_flows: 2
migration_head: 013

## Current Comtrade State

data_sources: 1
ingestion_runs: 4
completed_runs: 4
failed_runs: 0
source_records: 2
ingestion_run_records: 4
trade_flows: 2
provenance_links: 2

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
isProvisional: null
sourceAccessMode: public_preview
providerRevisionStatus: unknown

## Verified 2023 Historical Observation

reporterISO3: IND
partnerISO3: ARE
flowDirection: export
classification: HS2022
hsCode: 380210
periodStart: 2023-01-01
periodEnd: 2023-12-31
periodType: annual
quantity: 3556760
quantityUnit: kg
netWeightKg: 3556760
tradeValueUsd: 6130302.438
fobValueUsd: 6130302.438
currency: USD
status: published
isProvisional: null
sourceAccessMode: public_preview
providerRevisionStatus: unknown

## Idempotency Proof

First apply:
- source record: inserted
- trade flow: inserted
- ingestion run: completed

Second identical apply:
- source record: reused
- trade flow: reused
- ingestion run: completed

2024 historical planner re-apply:
- source record: reused
- trade flow: reused
- new ingestion audit run: completed

Current 2024 identity invariant:
- one logical 2024 Comtrade source record
- one canonical 2024 Comtrade trade flow
- one 2024 provenance link
- three ingestion-run audit links for the 2024 source record

2023 historical planner apply:
- source record: inserted
- trade flow: inserted
- provenance link: inserted
- ingestion run: completed

## Current OH13 Files

.gitignore
.github/workflows/origin-hut-ci.yml
docs/AI_HANDOFF.md
services/data/requirements.txt
services/data/config/comtrade_refresh.example.json
services/data/src/connectors/comtrade.py
services/data/src/connectors/comtrade_canonical.py
services/data/src/connectors/comtrade_history.py
services/data/src/connectors/comtrade_refresh.py
services/data/src/storage/__init__.py
services/data/src/storage/manifests.py
services/data/src/storage/parquet.py
services/data/tests/test_analytical_storage.py
services/data/tests/test_comtrade_connector.py
services/data/tests/test_comtrade_canonical.py
services/data/tests/test_comtrade_history.py
services/data/tests/test_comtrade_refresh.py
services/data/tests/test_comtrade_postgres_integration.py
database/migrations/013_trade_observation_revision_semantics.sql
storage/parquet/.gitkeep

## CI

GitHub Actions workflow:
.github/workflows/origin-hut-ci.yml

Checks:
- Node API typecheck
- Node API build
- Python compile
- Python unit tests
- PostgreSQL integration tests
- migrations 001-013 applied in disposable PostGIS CI database

## Next Action

Complete OH13 production hardening.

Priority checks:

- obtain/configure a real UN Comtrade API subscription key and live-test authenticated_data
- add scheduled historical refresh orchestration
- define retry/backoff and daily call-budget policy for unattended runs
- evaluate premium bulk ingestion for very large reporter-period datasets
- retain Bronze raw artifacts and Silver Parquet outside Git in production storage

## Development Workflow

1. Edit and test locally in VS Code.
2. Commit to work/oh13.
3. Push work/oh13.
4. GitHub Actions runs.
5. ChatGPT reads repository and CI logs directly.
6. Fix locally and repeat.
7. Merge to main only after OH13 is green.

Raw PowerShell logs remain local and are not committed.
