BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 019
-- PRODUCT PACKAGING
-- ============================================================
--
-- Physical units remain in units_of_measure / Rec 20.
-- Package type names use UN/CEFACT Recommendation 21.
--
-- Examples:
--
-- manufacturer product
--   -> 25 KGM woven bag
--   -> pallet containing 40 of those bags
--
-- Shipping containers are NOT packaging configurations here.
-- Container loading belongs to a later logistics/load-plan layer.
-- ============================================================


CREATE TABLE package_types (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    code VARCHAR(3) NOT NULL
        UNIQUE,

    name TEXT NOT NULL,

    standard TEXT NOT NULL
        DEFAULT 'UNCEFACT_REC21',

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        package_types_code_not_blank
    CHECK (
        BTRIM(code) <> ''
    ),


    CONSTRAINT
        package_types_name_not_blank
    CHECK (
        BTRIM(name) <> ''
    )

);


CREATE INDEX
idx_package_types_name_trgm
ON package_types
USING GIN (
    name gin_trgm_ops
);


CREATE TRIGGER
trg_package_types_updated_at
BEFORE UPDATE
ON package_types
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


INSERT INTO package_types (
    code,
    name,
    metadata
)
VALUES
    (
        'BG',
        'Bag',
        '{"source":"UN/CEFACT Recommendation 21"}'::jsonb
    ),
    (
        'JB',
        'Bag, jumbo',
        '{"source":"UN/CEFACT Recommendation 21"}'::jsonb
    ),
    (
        '43',
        'Bag, super bulk',
        '{"source":"UN/CEFACT Recommendation 21"}'::jsonb
    ),
    (
        '5H',
        'Bag, woven plastic',
        '{"source":"UN/CEFACT Recommendation 21"}'::jsonb
    ),
    (
        'CT',
        'Carton',
        '{"source":"UN/CEFACT Recommendation 21"}'::jsonb
    ),
    (
        'PX',
        'Pallet',
        '{"source":"UN/CEFACT Recommendation 21"}'::jsonb
    ),
    (
        '1A',
        'Drum, steel',
        '{"source":"UN/CEFACT Recommendation 21"}'::jsonb
    ),
    (
        '4G',
        'Box, fibreboard',
        '{"source":"UN/CEFACT Recommendation 21"}'::jsonb
    )
ON CONFLICT (code)
DO NOTHING;


CREATE TABLE packaging_configurations (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    manufacturer_product_id UUID NOT NULL
        REFERENCES manufacturer_products(id)
        ON DELETE CASCADE,

    package_type_id UUID NOT NULL
        REFERENCES package_types(id)
        ON DELETE RESTRICT,

    name TEXT NOT NULL,

    packaging_level TEXT NOT NULL,

    packaging_material TEXT,

    content_quantity NUMERIC(30,12),

    content_uom_id UUID
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    inner_packaging_id UUID
        REFERENCES packaging_configurations(id)
        ON DELETE RESTRICT,

    inner_package_count INTEGER,

    net_weight NUMERIC(30,12),

    gross_weight NUMERIC(30,12),

    weight_uom_id UUID
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    length NUMERIC(30,12),

    width NUMERIC(30,12),

    height NUMERIC(30,12),

    dimension_uom_id UUID
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    is_default BOOLEAN NOT NULL
        DEFAULT FALSE,

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
        packaging_configurations_name_not_blank
    CHECK (
        BTRIM(name) <> ''
    ),


    CONSTRAINT
        packaging_configurations_level
    CHECK (
        packaging_level IN (
            'primary',
            'secondary',
            'tertiary',
            'logistics'
        )
    ),


    CONSTRAINT
        packaging_configurations_content_pair
    CHECK (
        (
            content_quantity IS NULL
            AND content_uom_id IS NULL
        )
        OR (
            content_quantity IS NOT NULL
            AND content_quantity > 0
            AND content_uom_id IS NOT NULL
        )
    ),


    CONSTRAINT
        packaging_configurations_inner_pair
    CHECK (
        (
            inner_packaging_id IS NULL
            AND inner_package_count IS NULL
        )
        OR (
            inner_packaging_id IS NOT NULL
            AND inner_package_count IS NOT NULL
            AND inner_package_count > 0
        )
    ),


    CONSTRAINT
        packaging_configurations_has_content_or_inner
    CHECK (
        content_quantity IS NOT NULL
        OR inner_packaging_id IS NOT NULL
    ),


    CONSTRAINT
        packaging_configurations_no_self_inner
    CHECK (
        inner_packaging_id IS NULL
        OR inner_packaging_id <> id
    ),


    CONSTRAINT
        packaging_configurations_weight_values
    CHECK (
        (
            net_weight IS NULL
            AND gross_weight IS NULL
            AND weight_uom_id IS NULL
        )
        OR (
            weight_uom_id IS NOT NULL
            AND (
                net_weight IS NOT NULL
                OR gross_weight IS NOT NULL
            )
            AND (
                net_weight IS NULL
                OR net_weight > 0
            )
            AND (
                gross_weight IS NULL
                OR gross_weight > 0
            )
            AND (
                net_weight IS NULL
                OR gross_weight IS NULL
                OR gross_weight >= net_weight
            )
        )
    ),


    CONSTRAINT
        packaging_configurations_dimensions
    CHECK (
        (
            length IS NULL
            AND width IS NULL
            AND height IS NULL
            AND dimension_uom_id IS NULL
        )
        OR (
            length IS NOT NULL
            AND width IS NOT NULL
            AND height IS NOT NULL
            AND dimension_uom_id IS NOT NULL
            AND length > 0
            AND width > 0
            AND height > 0
        )
    ),


    CONSTRAINT
        packaging_configurations_status_not_blank
    CHECK (
        BTRIM(status) <> ''
    ),


    CONSTRAINT
        packaging_configurations_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        packaging_configurations_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    CONSTRAINT
        packaging_configurations_valid_dates
    CHECK (
        valid_from IS NULL
        OR valid_to IS NULL
        OR valid_to >= valid_from
    )

);


CREATE INDEX
idx_packaging_configurations_manufacturer_product
ON packaging_configurations (
    manufacturer_product_id,
    status,
    packaging_level,
    updated_at DESC
);


CREATE INDEX
idx_packaging_configurations_package_type
ON packaging_configurations (
    package_type_id
);


CREATE INDEX
idx_packaging_configurations_inner
ON packaging_configurations (
    inner_packaging_id
)
WHERE inner_packaging_id IS NOT NULL;


CREATE INDEX
idx_packaging_configurations_source_record
ON packaging_configurations (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_packaging_configurations_metadata_gin
ON packaging_configurations
USING GIN (
    metadata
);


CREATE UNIQUE INDEX
packaging_configurations_active_name_unique
ON packaging_configurations (
    manufacturer_product_id,
    name
)
WHERE
    status = 'active'
    AND valid_to IS NULL;


CREATE UNIQUE INDEX
packaging_configurations_default_unique
ON packaging_configurations (
    manufacturer_product_id
)
WHERE
    is_default = TRUE
    AND status = 'active'
    AND valid_to IS NULL;


CREATE OR REPLACE FUNCTION
originhut_validate_packaging_inner()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_inner_manufacturer_product_id UUID;
BEGIN

    IF NEW.inner_packaging_id IS NULL THEN
        RETURN NEW;
    END IF;


    SELECT manufacturer_product_id
    INTO v_inner_manufacturer_product_id
    FROM packaging_configurations
    WHERE id = NEW.inner_packaging_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Inner packaging configuration does not exist.';
    END IF;


    IF
        v_inner_manufacturer_product_id
        <> NEW.manufacturer_product_id
    THEN
        RAISE EXCEPTION
            'Inner packaging must belong to the same manufacturer product.';
    END IF;


    RETURN NEW;

END;
$$;


CREATE TRIGGER
trg_packaging_configurations_validate_inner
BEFORE INSERT OR UPDATE
ON packaging_configurations
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_packaging_inner();


CREATE TRIGGER
trg_packaging_configurations_updated_at
BEFORE UPDATE
ON packaging_configurations
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '019',
    'product_packaging'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
