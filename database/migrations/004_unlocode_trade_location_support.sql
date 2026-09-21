BEGIN;

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS country_code VARCHAR(2);

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS location_code VARCHAR(3);

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS name_without_diacritics TEXT;

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS change_indicator VARCHAR(1);

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS iata_code VARCHAR(3);

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS release_date_code VARCHAR(4);

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS remarks TEXT;

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS source_release VARCHAR(20);

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS marked_for_deletion BOOLEAN
NOT NULL DEFAULT FALSE;

ALTER TABLE trade_locations
ADD COLUMN IF NOT EXISTS canonical_source_record_id UUID
REFERENCES source_records(id)
ON DELETE SET NULL;


CREATE INDEX IF NOT EXISTS idx_trade_locations_country_code
ON trade_locations(country_code);

CREATE INDEX IF NOT EXISTS idx_trade_locations_location_code
ON trade_locations(location_code);

CREATE INDEX IF NOT EXISTS idx_trade_locations_iata
ON trade_locations(iata_code);

CREATE INDEX IF NOT EXISTS idx_trade_locations_release
ON trade_locations(source_release);

CREATE INDEX IF NOT EXISTS idx_trade_locations_deletion
ON trade_locations(marked_for_deletion);

CREATE INDEX IF NOT EXISTS idx_trade_locations_canonical_source
ON trade_locations(canonical_source_record_id);


-- ------------------------------------------------------------
-- ALTERNATE / HISTORICAL PUBLISHED NAMES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS trade_location_aliases (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    trade_location_id UUID NOT NULL
        REFERENCES trade_locations(id)
        ON DELETE CASCADE,

    name TEXT NOT NULL,

    name_without_diacritics TEXT,

    alias_type TEXT NOT NULL
        DEFAULT 'published_name',

    is_preferred BOOLEAN NOT NULL
        DEFAULT FALSE,

    source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW()

);


CREATE UNIQUE INDEX IF NOT EXISTS
ux_trade_location_alias_identity
ON trade_location_aliases(
    trade_location_id,
    name,
    alias_type
);


CREATE INDEX IF NOT EXISTS
idx_trade_location_alias_location
ON trade_location_aliases(trade_location_id);


CREATE INDEX IF NOT EXISTS
idx_trade_location_alias_name_trgm
ON trade_location_aliases
USING GIN(name gin_trgm_ops);


CREATE INDEX IF NOT EXISTS
idx_trade_location_alias_name_wo_trgm
ON trade_location_aliases
USING GIN(name_without_diacritics gin_trgm_ops);


-- ------------------------------------------------------------
-- INGESTION RUN <-> SOURCE RECORD HISTORY
--
-- A source record can appear in several future releases.
-- Do not destroy its original ingestion provenance merely
-- because it was observed again.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingestion_run_records (

    ingestion_run_id UUID NOT NULL
        REFERENCES ingestion_runs(id)
        ON DELETE CASCADE,

    source_record_id UUID NOT NULL
        REFERENCES source_records(id)
        ON DELETE CASCADE,

    seen_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    PRIMARY KEY (
        ingestion_run_id,
        source_record_id
    )

);


CREATE INDEX IF NOT EXISTS
idx_ingestion_run_records_source
ON ingestion_run_records(source_record_id);


-- Backfill provenance for datasets already ingested.
INSERT INTO ingestion_run_records (
    ingestion_run_id,
    source_record_id
)
SELECT
    ingestion_run_id,
    id
FROM source_records
WHERE ingestion_run_id IS NOT NULL
ON CONFLICT DO NOTHING;


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '004',
    'unlocode_trade_location_support'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
