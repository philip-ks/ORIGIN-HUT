BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 017
-- UNIT OF MEASURE REFERENCE
-- ============================================================
--
-- Physical measurement units use UN/CEFACT Recommendation 20
-- common codes where applicable.
--
-- Packaging types are deliberately NOT represented here.
-- Package / packaging material codes belong to UN/CEFACT
-- Recommendation 21 and will be introduced with packaging.
--
-- Safe conversion rule:
-- only units in the same measurement dimension and marked
-- linearly convertible may be converted automatically.
-- ============================================================


CREATE TABLE units_of_measure (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    code VARCHAR(3) NOT NULL
        UNIQUE,

    name TEXT NOT NULL,

    symbol TEXT,

    dimension_code TEXT NOT NULL,

    standard TEXT NOT NULL
        DEFAULT 'UNCEFACT_REC20',

    scale_to_base NUMERIC(30,15),

    offset_to_base NUMERIC(30,15)
        DEFAULT 0,

    is_dimension_base BOOLEAN NOT NULL
        DEFAULT FALSE,

    is_linear_convertible BOOLEAN NOT NULL
        DEFAULT FALSE,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        units_of_measure_code_not_blank
    CHECK (
        BTRIM(code) <> ''
    ),


    CONSTRAINT
        units_of_measure_name_not_blank
    CHECK (
        BTRIM(name) <> ''
    ),


    CONSTRAINT
        units_of_measure_dimension_not_blank
    CHECK (
        BTRIM(dimension_code) <> ''
    ),


    CONSTRAINT
        units_of_measure_standard_not_blank
    CHECK (
        BTRIM(standard) <> ''
    ),


    CONSTRAINT
        units_of_measure_linear_conversion_complete
    CHECK (
        NOT is_linear_convertible
        OR (
            scale_to_base IS NOT NULL
            AND scale_to_base > 0
            AND offset_to_base IS NOT NULL
        )
    ),


    CONSTRAINT
        units_of_measure_base_is_convertible
    CHECK (
        NOT is_dimension_base
        OR (
            is_linear_convertible
            AND scale_to_base = 1
            AND offset_to_base = 0
        )
    )

);


CREATE UNIQUE INDEX
units_of_measure_dimension_base_unique
ON units_of_measure (
    dimension_code
)
WHERE
    is_dimension_base = TRUE;


CREATE INDEX
idx_units_of_measure_dimension
ON units_of_measure (
    dimension_code,
    is_active,
    code
);


CREATE INDEX
idx_units_of_measure_name_trgm
ON units_of_measure
USING GIN (
    name gin_trgm_ops
);


CREATE INDEX
idx_units_of_measure_metadata_gin
ON units_of_measure
USING GIN (
    metadata
);


CREATE TRIGGER
trg_units_of_measure_updated_at
BEFORE UPDATE
ON units_of_measure
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


INSERT INTO units_of_measure (
    code,
    name,
    symbol,
    dimension_code,
    scale_to_base,
    offset_to_base,
    is_dimension_base,
    is_linear_convertible,
    metadata
)
VALUES

    (
        'KGM',
        'kilogram',
        'kg',
        'mass',
        1,
        0,
        TRUE,
        TRUE,
        '{"source":"UN/CEFACT Recommendation 20"}'::jsonb
    ),

    (
        'GRM',
        'gram',
        'g',
        'mass',
        0.001,
        0,
        FALSE,
        TRUE,
        '{"source":"UN/CEFACT Recommendation 20"}'::jsonb
    ),

    (
        'TNE',
        'tonne (metric ton)',
        't',
        'mass',
        1000,
        0,
        FALSE,
        TRUE,
        '{"source":"UN/CEFACT Recommendation 20"}'::jsonb
    ),

    (
        'MTR',
        'metre',
        'm',
        'length',
        1,
        0,
        TRUE,
        TRUE,
        '{"source":"UN/CEFACT Recommendation 20"}'::jsonb
    ),

    (
        'CMT',
        'centimetre',
        'cm',
        'length',
        0.01,
        0,
        FALSE,
        TRUE,
        '{"source":"UN/CEFACT Recommendation 20"}'::jsonb
    ),

    (
        'MMT',
        'millimetre',
        'mm',
        'length',
        0.001,
        0,
        FALSE,
        TRUE,
        '{"source":"UN/CEFACT Recommendation 20"}'::jsonb
    ),

    (
        'MTQ',
        'cubic metre',
        'm3',
        'volume',
        1,
        0,
        TRUE,
        TRUE,
        '{"source":"UN/CEFACT Recommendation 20"}'::jsonb
    ),

    (
        'LTR',
        'litre',
        'L',
        'volume',
        0.001,
        0,
        FALSE,
        TRUE,
        '{"source":"UN/CEFACT Recommendation 20"}'::jsonb
    )

ON CONFLICT (code)
DO NOTHING;


ALTER TABLE products
ADD COLUMN base_uom_id UUID
    REFERENCES units_of_measure(id)
    ON DELETE SET NULL;


CREATE INDEX
idx_products_base_uom
ON products (
    base_uom_id
);


CREATE OR REPLACE FUNCTION
originhut_convert_uom(
    p_value NUMERIC,
    p_from_code TEXT,
    p_to_code TEXT
)
RETURNS NUMERIC
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_from units_of_measure%ROWTYPE;
    v_to units_of_measure%ROWTYPE;
    v_base NUMERIC;
BEGIN

    SELECT *
    INTO v_from
    FROM units_of_measure
    WHERE
        code = UPPER(BTRIM(p_from_code))
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Unknown or inactive source UOM: %',
            p_from_code;
    END IF;


    SELECT *
    INTO v_to
    FROM units_of_measure
    WHERE
        code = UPPER(BTRIM(p_to_code))
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Unknown or inactive target UOM: %',
            p_to_code;
    END IF;


    IF
        v_from.dimension_code
        <> v_to.dimension_code
    THEN
        RAISE EXCEPTION
            'Cannot convert UOM across dimensions: % -> %',
            v_from.dimension_code,
            v_to.dimension_code;
    END IF;


    IF
        NOT v_from.is_linear_convertible
        OR NOT v_to.is_linear_convertible
    THEN
        RAISE EXCEPTION
            'Automatic conversion is not enabled for % -> %',
            v_from.code,
            v_to.code;
    END IF;


    v_base :=
        (
            p_value
            * v_from.scale_to_base
        )
        + v_from.offset_to_base;


    RETURN
        (
            v_base
            - v_to.offset_to_base
        )
        / v_to.scale_to_base;

END;
$$;


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '017',
    'unit_of_measure_reference'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
