BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 005
-- HS 2022 REFERENCE DATA SUPPORT
-- ============================================================

-- Preserve useful normalized attributes from the official
-- UNSD / UN Comtrade HS reference while the complete original
-- source object remains preserved in source_records.

ALTER TABLE hs_codes
ADD COLUMN IF NOT EXISTS is_leaf BOOLEAN;

ALTER TABLE hs_codes
ADD COLUMN IF NOT EXISTS standard_unit TEXT;

ALTER TABLE hs_codes
ADD COLUMN IF NOT EXISTS metadata JSONB
NOT NULL
DEFAULT '{}'::jsonb;

ALTER TABLE hs_codes
ADD COLUMN IF NOT EXISTS canonical_source_record_id UUID
REFERENCES source_records(id)
ON DELETE SET NULL;


CREATE INDEX IF NOT EXISTS idx_hs_codes_nomenclature_level
ON hs_codes(
    nomenclature,
    level
);

CREATE INDEX IF NOT EXISTS idx_hs_codes_canonical_source
ON hs_codes(
    canonical_source_record_id
);

CREATE INDEX IF NOT EXISTS idx_hs_codes_metadata
ON hs_codes
USING GIN(metadata);


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '005',
    'hs2022_reference_support'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
