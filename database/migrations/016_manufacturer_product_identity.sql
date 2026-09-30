BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 016
-- MANUFACTURER PRODUCT IDENTITY
-- ============================================================
--
-- Canonical separation:
--
-- products
--   = generic trade concept
--     e.g. Activated Carbon
--
-- manufacturer_products
--   = a manufacturer's concrete catalogue item / grade / SKU
--     e.g. Manufacturer X Activated Carbon Grade ABC
--
-- Existing columns on products such as manufacturer_id, brand,
-- sku and gtin remain for backward compatibility with OH8-era
-- records and APIs. New manufacturer-specific identity should be
-- written to manufacturer_products.
-- ============================================================


CREATE TABLE manufacturer_products (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    product_id UUID NOT NULL
        REFERENCES products(id)
        ON DELETE CASCADE,

    manufacturer_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    country_of_origin_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    name TEXT NOT NULL,

    brand TEXT,

    grade TEXT,

    model_code TEXT,

    sku TEXT,

    gtin TEXT,

    description TEXT,

    status TEXT NOT NULL
        DEFAULT 'active',

    identifiers JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    attributes JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        manufacturer_products_name_not_blank
    CHECK (
        BTRIM(name) <> ''
    ),


    CONSTRAINT
        manufacturer_products_status_not_blank
    CHECK (
        BTRIM(status) <> ''
    ),


    CONSTRAINT
        manufacturer_products_brand_not_blank
    CHECK (
        brand IS NULL
        OR BTRIM(brand) <> ''
    ),


    CONSTRAINT
        manufacturer_products_grade_not_blank
    CHECK (
        grade IS NULL
        OR BTRIM(grade) <> ''
    ),


    CONSTRAINT
        manufacturer_products_model_code_not_blank
    CHECK (
        model_code IS NULL
        OR BTRIM(model_code) <> ''
    ),


    CONSTRAINT
        manufacturer_products_sku_not_blank
    CHECK (
        sku IS NULL
        OR BTRIM(sku) <> ''
    ),


    CONSTRAINT
        manufacturer_products_gtin_not_blank
    CHECK (
        gtin IS NULL
        OR BTRIM(gtin) <> ''
    )

);


CREATE INDEX
idx_manufacturer_products_product
ON manufacturer_products (
    product_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_manufacturer_products_manufacturer
ON manufacturer_products (
    manufacturer_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_manufacturer_products_origin
ON manufacturer_products (
    country_of_origin_id
);


CREATE INDEX
idx_manufacturer_products_name_trgm
ON manufacturer_products
USING GIN (
    name gin_trgm_ops
);


CREATE INDEX
idx_manufacturer_products_brand_trgm
ON manufacturer_products
USING GIN (
    brand gin_trgm_ops
);


CREATE INDEX
idx_manufacturer_products_grade_trgm
ON manufacturer_products
USING GIN (
    grade gin_trgm_ops
);


CREATE INDEX
idx_manufacturer_products_attributes_gin
ON manufacturer_products
USING GIN (
    attributes
);


CREATE INDEX
idx_manufacturer_products_identifiers_gin
ON manufacturer_products
USING GIN (
    identifiers
);


CREATE INDEX
idx_manufacturer_products_metadata_gin
ON manufacturer_products
USING GIN (
    metadata
);


CREATE UNIQUE INDEX
manufacturer_products_manufacturer_sku_unique
ON manufacturer_products (
    manufacturer_id,
    sku
)
WHERE
    sku IS NOT NULL;


CREATE UNIQUE INDEX
manufacturer_products_gtin_unique
ON manufacturer_products (
    gtin
)
WHERE
    gtin IS NOT NULL;


CREATE TRIGGER
trg_manufacturer_products_updated_at
BEFORE UPDATE
ON manufacturer_products
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '016',
    'manufacturer_product_identity'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
