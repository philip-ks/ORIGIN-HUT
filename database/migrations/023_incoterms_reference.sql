BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 023
-- INCOTERMS REFERENCE
-- ============================================================
--
-- Incoterms are commercial contract terms, not Product attributes
-- and not statistical FOB/CIF value labels.
--
-- Reference source:
-- International Chamber of Commerce, Incoterms(R) 2020.
-- ============================================================


CREATE TABLE incoterm_rules (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    edition INTEGER NOT NULL,

    code VARCHAR(3) NOT NULL,

    name TEXT NOT NULL,

    transport_scope TEXT NOT NULL,

    named_location_role TEXT NOT NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        incoterm_rules_edition_positive
    CHECK (
        edition > 0
    ),


    CONSTRAINT
        incoterm_rules_code_format
    CHECK (
        code ~ '^[A-Z]{3}$'
    ),


    CONSTRAINT
        incoterm_rules_name_not_blank
    CHECK (
        BTRIM(name) <> ''
    ),


    CONSTRAINT
        incoterm_rules_transport_scope
    CHECK (
        transport_scope IN (
            'any_mode',
            'sea_inland_waterway'
        )
    ),


    CONSTRAINT
        incoterm_rules_named_location_role
    CHECK (
        named_location_role IN (
            'delivery_place',
            'destination_place',
            'shipment_port',
            'destination_port'
        )
    ),


    UNIQUE (
        edition,
        code
    )

);


CREATE INDEX
idx_incoterm_rules_edition_scope
ON incoterm_rules (
    edition,
    transport_scope,
    code
);


CREATE INDEX
idx_incoterm_rules_active
ON incoterm_rules (
    is_active,
    edition,
    code
);


CREATE TRIGGER
trg_incoterm_rules_updated_at
BEFORE UPDATE
ON incoterm_rules
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


INSERT INTO incoterm_rules (
    edition,
    code,
    name,
    transport_scope,
    named_location_role,
    metadata
)
VALUES
    (
        2020,
        'EXW',
        'Ex Works',
        'any_mode',
        'delivery_place',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'FCA',
        'Free Carrier',
        'any_mode',
        'delivery_place',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'CPT',
        'Carriage Paid To',
        'any_mode',
        'destination_place',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'CIP',
        'Carriage and Insurance Paid To',
        'any_mode',
        'destination_place',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'DAP',
        'Delivered at Place',
        'any_mode',
        'destination_place',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'DPU',
        'Delivered at Place Unloaded',
        'any_mode',
        'destination_place',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'DDP',
        'Delivered Duty Paid',
        'any_mode',
        'destination_place',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'FAS',
        'Free Alongside Ship',
        'sea_inland_waterway',
        'shipment_port',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'FOB',
        'Free On Board',
        'sea_inland_waterway',
        'shipment_port',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'CFR',
        'Cost and Freight',
        'sea_inland_waterway',
        'destination_port',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    ),
    (
        2020,
        'CIF',
        'Cost Insurance and Freight',
        'sea_inland_waterway',
        'destination_port',
        '{"source":"ICC Incoterms 2020"}'::jsonb
    )
ON CONFLICT (
    edition,
    code
)
DO UPDATE SET
    name = EXCLUDED.name,
    transport_scope = EXCLUDED.transport_scope,
    named_location_role = EXCLUDED.named_location_role,
    is_active = TRUE,
    metadata = EXCLUDED.metadata;


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '023',
    'incoterms_reference'
)
ON CONFLICT (version)
DO NOTHING;


COMMIT;
