BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 008
-- CONFIRMED PRODUCT HS CLASSIFICATION PROVENANCE
-- ============================================================


ALTER TABLE product_hs_classifications
ADD COLUMN IF NOT EXISTS classification_request_id UUID
REFERENCES hs_classification_requests(id)
ON DELETE SET NULL;


ALTER TABLE product_hs_classifications
ADD COLUMN IF NOT EXISTS decision_method TEXT;


ALTER TABLE product_hs_classifications
ADD COLUMN IF NOT EXISTS decision_notes TEXT;


ALTER TABLE product_hs_classifications
ADD COLUMN IF NOT EXISTS metadata JSONB
NOT NULL
DEFAULT '{}'::jsonb;


ALTER TABLE product_hs_classifications
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ
NOT NULL
DEFAULT NOW();


-- Existing constraint treats NULL country_id values as distinct.
-- That could allow duplicate global classifications.
ALTER TABLE product_hs_classifications
DROP CONSTRAINT IF EXISTS
product_hs_classifications_product_id_hs_code_id_country_id_key;


ALTER TABLE product_hs_classifications
ADD CONSTRAINT
product_hs_classifications_product_hs_country_unique

UNIQUE NULLS NOT DISTINCT (
    product_id,
    hs_code_id,
    country_id
);


CREATE INDEX IF NOT EXISTS
idx_product_hs_classification_request
ON product_hs_classifications(
    classification_request_id
);


CREATE INDEX IF NOT EXISTS
idx_product_hs_classification_metadata
ON product_hs_classifications
USING GIN(metadata);


DROP TRIGGER IF EXISTS
trg_product_hs_classifications_updated_at
ON product_hs_classifications;


CREATE TRIGGER
trg_product_hs_classifications_updated_at

BEFORE UPDATE
ON product_hs_classifications

FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '008',
    'confirmed_product_hs_classification_provenance'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
