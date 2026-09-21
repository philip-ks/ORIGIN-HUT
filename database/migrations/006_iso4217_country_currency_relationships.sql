BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 006
-- ISO 4217 COUNTRY-CURRENCY RELATIONSHIP SUPPORT
-- ============================================================

-- ISO 4217 List One publishes currency/fund relationships
-- for entities, but does not define Origin Hut's concept of
-- a single "primary" currency.
--
-- Therefore do not infer primary currency automatically.

ALTER TABLE country_currencies
ALTER COLUMN is_primary SET DEFAULT FALSE;


ALTER TABLE country_currencies
ADD COLUMN IF NOT EXISTS is_fund BOOLEAN
NOT NULL
DEFAULT FALSE;


ALTER TABLE country_currencies
ADD COLUMN IF NOT EXISTS source_record_id UUID
REFERENCES source_records(id)
ON DELETE SET NULL;


ALTER TABLE country_currencies
ADD COLUMN IF NOT EXISTS source_entity TEXT;


ALTER TABLE country_currencies
ADD COLUMN IF NOT EXISTS metadata JSONB
NOT NULL
DEFAULT '{}'::jsonb;


CREATE INDEX IF NOT EXISTS
idx_country_currencies_source_record
ON country_currencies(source_record_id);


CREATE INDEX IF NOT EXISTS
idx_country_currencies_fund
ON country_currencies(is_fund);


CREATE INDEX IF NOT EXISTS
idx_country_currencies_metadata
ON country_currencies
USING GIN(metadata);


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '006',
    'iso4217_country_currency_relationships'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
