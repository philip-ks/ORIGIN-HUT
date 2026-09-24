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
- UN Comtrade connector created
- India to UAE HS380210 2024 export live ingestion passed
- Bronze raw-response checksum verified
- record-level SHA-256 verified
- Silver Parquet checksum verified
- DuckDB read-back verified
- runtime Bronze/Silver artifacts ignored by Git
- PostgreSQL not yet populated by OH13
- no Migration 013 required currently

## Database Baseline

data_sources: 4
ingestion_runs: 5
source_records: 123979
ingestion_run_records: 123979
entity_source_links: 123973
trade_flows: 0
migration_head: 012

## Current OH13 Files

.gitignore
services/data/requirements.txt
services/data/src/connectors/comtrade.py
services/data/src/storage/__init__.py
services/data/src/storage/manifests.py
services/data/src/storage/parquet.py
services/data/tests/test_analytical_storage.py
services/data/tests/test_comtrade_connector.py
storage/parquet/.gitkeep
.github/workflows/origin-hut-ci.yml
docs/AI_HANDOFF.md

## CI

GitHub Actions workflow:
.github/workflows/origin-hut-ci.yml

Checks:
- Node API typecheck
- Node API build
- Python compile
- Python tests

## Next Action

Implement Silver to PostgreSQL canonicalization:

data_sources
  -> ingestion_runs
  -> source_records
  -> ingestion_run_records
  -> trade_flows
  -> entity_source_links

Requirements:

- reporter and partner resolved through ISO3
- immutable source-record revisions
- canonical source record maintained
- repeat-run idempotency
- no duplicate trade flow
- no Migration 013 unless genuinely required

## Development Workflow

1. Edit and test locally in VS Code.
2. Commit to work/oh13.
3. Push work/oh13.
4. GitHub Actions runs.
5. ChatGPT reads repository and CI logs directly.
6. Fix locally and repeat.
7. Merge to main only after OH13 is green.

Raw PowerShell logs remain local and are not committed.
