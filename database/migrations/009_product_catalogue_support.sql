BEGIN;

ALTER TABLE products
ADD COLUMN IF NOT EXISTS metadata JSONB
NOT NULL
DEFAULT '{}'::jsonb;


CREATE INDEX IF NOT EXISTS
idx_products_sku_trgm
ON products
USING GIN (sku gin_trgm_ops);


CREATE INDEX IF NOT EXISTS
idx_products_description_trgm
ON products
USING GIN (description gin_trgm_ops);


CREATE INDEX IF NOT EXISTS
idx_products_attributes_gin
ON products
USING GIN (attributes);


CREATE INDEX IF NOT EXISTS
idx_products_metadata_gin
ON products
USING GIN (metadata);


CREATE INDEX IF NOT EXISTS
idx_products_active_updated
ON products (
    is_active,
    updated_at DESC
);


CREATE INDEX IF NOT EXISTS
idx_products_manufacturer_active
ON products (
    manufacturer_id,
    is_active
)
WHERE manufacturer_id IS NOT NULL;


-- ------------------------------------------------------------
-- CLASSIFICATION RETRIEVAL VERSION DEFAULTS
-- ------------------------------------------------------------

ALTER TABLE hs_classification_requests
ALTER COLUMN retrieval_version
SET DEFAULT 'trigram_polarity_v2';


ALTER TABLE hs_classification_candidates
ALTER COLUMN retrieval_method
SET DEFAULT 'trigram_polarity_v2';


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '009',
    'product_catalogue_support'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
