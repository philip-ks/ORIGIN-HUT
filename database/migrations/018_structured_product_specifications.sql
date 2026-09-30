BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 018
-- STRUCTURED PRODUCT SPECIFICATIONS
-- ============================================================
--
-- Generic Product specifications and manufacturer-specific
-- specifications share one typed definition catalogue.
--
-- A specification value belongs to exactly one subject:
--   product_id
--   OR manufacturer_product_id
--
-- It may never belong to both simultaneously.
-- ============================================================


CREATE TABLE specification_definitions (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    code TEXT NOT NULL
        UNIQUE,

    name TEXT NOT NULL,

    category TEXT,

    description TEXT,

    value_type TEXT NOT NULL,

    dimension_code TEXT,

    default_uom_id UUID
        REFERENCES units_of_measure(id)
        ON DELETE SET NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        specification_definitions_code_not_blank
    CHECK (
        BTRIM(code) <> ''
    ),


    CONSTRAINT
        specification_definitions_name_not_blank
    CHECK (
        BTRIM(name) <> ''
    ),


    CONSTRAINT
        specification_definitions_value_type
    CHECK (
        value_type IN (
            'numeric',
            'text',
            'boolean'
        )
    ),


    CONSTRAINT
        specification_definitions_non_numeric_no_uom
    CHECK (
        value_type = 'numeric'
        OR (
            dimension_code IS NULL
            AND default_uom_id IS NULL
        )
    )

);


CREATE INDEX
idx_specification_definitions_category
ON specification_definitions (
    category,
    is_active,
    code
);


CREATE INDEX
idx_specification_definitions_name_trgm
ON specification_definitions
USING GIN (
    name gin_trgm_ops
);


CREATE INDEX
idx_specification_definitions_metadata_gin
ON specification_definitions
USING GIN (
    metadata
);


CREATE TRIGGER
trg_specification_definitions_updated_at
BEFORE UPDATE
ON specification_definitions
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TABLE product_specifications (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    specification_definition_id UUID NOT NULL
        REFERENCES specification_definitions(id)
        ON DELETE RESTRICT,

    product_id UUID
        REFERENCES products(id)
        ON DELETE CASCADE,

    manufacturer_product_id UUID
        REFERENCES manufacturer_products(id)
        ON DELETE CASCADE,

    qualifier TEXT NOT NULL
        DEFAULT 'exact',

    numeric_value NUMERIC(30,12),

    minimum_value NUMERIC(30,12),

    maximum_value NUMERIC(30,12),

    text_value TEXT,

    boolean_value BOOLEAN,

    uom_id UUID
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    status TEXT NOT NULL
        DEFAULT 'active',

    valid_from DATE,

    valid_to DATE,

    source_type TEXT NOT NULL
        DEFAULT 'manual',

    canonical_source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    confidence NUMERIC(5,4),

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        product_specifications_exactly_one_subject
    CHECK (
        (
            product_id IS NOT NULL
            AND manufacturer_product_id IS NULL
        )
        OR (
            product_id IS NULL
            AND manufacturer_product_id IS NOT NULL
        )
    ),


    CONSTRAINT
        product_specifications_qualifier
    CHECK (
        qualifier IN (
            'exact',
            'nominal',
            'minimum',
            'maximum',
            'range'
        )
    ),


    CONSTRAINT
        product_specifications_has_value
    CHECK (
        numeric_value IS NOT NULL
        OR minimum_value IS NOT NULL
        OR maximum_value IS NOT NULL
        OR text_value IS NOT NULL
        OR boolean_value IS NOT NULL
    ),


    CONSTRAINT
        product_specifications_range_valid
    CHECK (
        minimum_value IS NULL
        OR maximum_value IS NULL
        OR maximum_value >= minimum_value
    ),


    CONSTRAINT
        product_specifications_uom_requires_numeric
    CHECK (
        uom_id IS NULL
        OR (
            numeric_value IS NOT NULL
            OR minimum_value IS NOT NULL
            OR maximum_value IS NOT NULL
        )
    ),


    CONSTRAINT
        product_specifications_status_not_blank
    CHECK (
        BTRIM(status) <> ''
    ),


    CONSTRAINT
        product_specifications_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        product_specifications_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    CONSTRAINT
        product_specifications_valid_dates
    CHECK (
        valid_from IS NULL
        OR valid_to IS NULL
        OR valid_to >= valid_from
    )

);


CREATE INDEX
idx_product_specifications_product
ON product_specifications (
    product_id,
    status,
    updated_at DESC
)
WHERE product_id IS NOT NULL;


CREATE INDEX
idx_product_specifications_manufacturer_product
ON product_specifications (
    manufacturer_product_id,
    status,
    updated_at DESC
)
WHERE manufacturer_product_id IS NOT NULL;


CREATE INDEX
idx_product_specifications_definition
ON product_specifications (
    specification_definition_id,
    status
);


CREATE INDEX
idx_product_specifications_uom
ON product_specifications (
    uom_id
);


CREATE INDEX
idx_product_specifications_source_record
ON product_specifications (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_product_specifications_metadata_gin
ON product_specifications
USING GIN (
    metadata
);


CREATE UNIQUE INDEX
product_specifications_active_product_unique
ON product_specifications (
    product_id,
    specification_definition_id
)
WHERE
    product_id IS NOT NULL
    AND status = 'active'
    AND valid_to IS NULL;


CREATE UNIQUE INDEX
product_specifications_active_manufacturer_product_unique
ON product_specifications (
    manufacturer_product_id,
    specification_definition_id
)
WHERE
    manufacturer_product_id IS NOT NULL
    AND status = 'active'
    AND valid_to IS NULL;


CREATE TRIGGER
trg_product_specifications_updated_at
BEFORE UPDATE
ON product_specifications
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '018',
    'structured_product_specifications'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
