BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 012
-- CANONICAL TRADE FLOW FACT MODEL
-- ============================================================
--
-- trade_flows contains statistical / aggregated trade facts.
--
-- It does NOT represent individual bills of lading,
-- containers, vessels or organization-level shipments.
-- ============================================================


CREATE TABLE trade_flows (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),


    -- --------------------------------------------------------
    -- FLOW
    -- --------------------------------------------------------

    flow_direction TEXT NOT NULL,


    -- --------------------------------------------------------
    -- REPORTER / PARTNER ECONOMIES
    -- --------------------------------------------------------

    reporter_country_id UUID NOT NULL
        REFERENCES countries(id)
        ON DELETE RESTRICT,

    partner_country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,


    -- --------------------------------------------------------
    -- PHYSICAL ORIGIN / DESTINATION
    -- --------------------------------------------------------

    origin_country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    destination_country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    origin_location_id UUID
        REFERENCES trade_locations(id)
        ON DELETE SET NULL,

    destination_location_id UUID
        REFERENCES trade_locations(id)
        ON DELETE SET NULL,


    -- --------------------------------------------------------
    -- PRODUCT / HS
    -- --------------------------------------------------------

    hs_code_id UUID
        REFERENCES hs_codes(id)
        ON DELETE SET NULL,

    product_id UUID
        REFERENCES products(id)
        ON DELETE SET NULL,


    -- --------------------------------------------------------
    -- REPORTING PERIOD
    -- --------------------------------------------------------

    period_start DATE NOT NULL,

    period_end DATE NOT NULL,

    period_type TEXT NOT NULL,


    -- --------------------------------------------------------
    -- PHYSICAL MEASURES
    -- --------------------------------------------------------

    quantity NUMERIC(30,6),

    quantity_unit TEXT,

    net_weight_kg NUMERIC(30,6),

    gross_weight_kg NUMERIC(30,6),


    -- --------------------------------------------------------
    -- MONETARY MEASURES
    -- --------------------------------------------------------

    trade_value NUMERIC(30,6),

    fob_value NUMERIC(30,6),

    cif_value NUMERIC(30,6),

    currency_id UUID
        REFERENCES currencies(id)
        ON DELETE SET NULL,


    -- --------------------------------------------------------
    -- OPTIONAL DIMENSIONS
    -- --------------------------------------------------------

    transport_mode TEXT,

    customs_procedure TEXT,


    -- --------------------------------------------------------
    -- SOURCE / LIFECYCLE
    -- --------------------------------------------------------

    status TEXT NOT NULL
        DEFAULT 'published',

    is_provisional BOOLEAN NOT NULL
        DEFAULT FALSE,

    canonical_source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,


    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    -- --------------------------------------------------------
    -- VALIDATION
    -- --------------------------------------------------------

    CONSTRAINT
        trade_flows_direction_not_blank
    CHECK (
        BTRIM(flow_direction) <> ''
    ),


    CONSTRAINT
        trade_flows_period_type_not_blank
    CHECK (
        BTRIM(period_type) <> ''
    ),


    CONSTRAINT
        trade_flows_status_not_blank
    CHECK (
        BTRIM(status) <> ''
    ),


    CONSTRAINT
        trade_flows_valid_period
    CHECK (
        period_end >= period_start
    ),


    CONSTRAINT
        trade_flows_quantity_nonnegative
    CHECK (
        quantity IS NULL
        OR quantity >= 0
    ),


    CONSTRAINT
        trade_flows_net_weight_nonnegative
    CHECK (
        net_weight_kg IS NULL
        OR net_weight_kg >= 0
    ),


    CONSTRAINT
        trade_flows_gross_weight_nonnegative
    CHECK (
        gross_weight_kg IS NULL
        OR gross_weight_kg >= 0
    ),


    CONSTRAINT
        trade_flows_trade_value_nonnegative
    CHECK (
        trade_value IS NULL
        OR trade_value >= 0
    ),


    CONSTRAINT
        trade_flows_fob_value_nonnegative
    CHECK (
        fob_value IS NULL
        OR fob_value >= 0
    ),


    CONSTRAINT
        trade_flows_cif_value_nonnegative
    CHECK (
        cif_value IS NULL
        OR cif_value >= 0
    ),


    CONSTRAINT
        trade_flows_currency_required_for_value
    CHECK (
        (
            trade_value IS NULL
            AND fob_value IS NULL
            AND cif_value IS NULL
        )
        OR currency_id IS NOT NULL
    ),


    CONSTRAINT
        trade_flows_measure_required
    CHECK (
        quantity IS NOT NULL
        OR net_weight_kg IS NOT NULL
        OR gross_weight_kg IS NOT NULL
        OR trade_value IS NOT NULL
        OR fob_value IS NOT NULL
        OR cif_value IS NOT NULL
    )

);


-- ============================================================
-- COUNTRY / MARKET ANALYTICS
-- ============================================================

CREATE INDEX
idx_trade_flows_reporter_direction_period
ON trade_flows (
    reporter_country_id,
    flow_direction,
    period_start DESC
);


CREATE INDEX
idx_trade_flows_partner_direction_period
ON trade_flows (
    partner_country_id,
    flow_direction,
    period_start DESC
)
WHERE partner_country_id IS NOT NULL;


-- ============================================================
-- HS ANALYTICS
-- ============================================================

CREATE INDEX
idx_trade_flows_hs_period
ON trade_flows (
    hs_code_id,
    period_start DESC
)
WHERE hs_code_id IS NOT NULL;


CREATE INDEX
idx_trade_flows_reporter_partner_hs_period
ON trade_flows (
    reporter_country_id,
    partner_country_id,
    hs_code_id,
    period_start DESC
);


-- ============================================================
-- ROUTE ANALYTICS
-- ============================================================

CREATE INDEX
idx_trade_flows_origin_destination_period
ON trade_flows (
    origin_country_id,
    destination_country_id,
    period_start DESC
);


CREATE INDEX
idx_trade_flows_origin_location
ON trade_flows (
    origin_location_id,
    period_start DESC
)
WHERE origin_location_id IS NOT NULL;


CREATE INDEX
idx_trade_flows_destination_location
ON trade_flows (
    destination_location_id,
    period_start DESC
)
WHERE destination_location_id IS NOT NULL;


-- ============================================================
-- PRODUCT MAPPING
-- ============================================================

CREATE INDEX
idx_trade_flows_product_period
ON trade_flows (
    product_id,
    period_start DESC
)
WHERE product_id IS NOT NULL;


-- ============================================================
-- PROVENANCE
-- ============================================================

CREATE INDEX
idx_trade_flows_canonical_source
ON trade_flows (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


-- ============================================================
-- PERIOD SCANS
-- ============================================================

CREATE INDEX
idx_trade_flows_period_brin
ON trade_flows
USING BRIN (
    period_start
);


-- ============================================================
-- METADATA
-- ============================================================

CREATE INDEX
idx_trade_flows_metadata_gin
ON trade_flows
USING GIN (
    metadata
);


-- ============================================================
-- UPDATED AT
-- ============================================================

CREATE TRIGGER
trg_trade_flows_updated_at
BEFORE UPDATE
ON trade_flows
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


-- ============================================================
-- MIGRATION HISTORY
-- ============================================================

INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '012',
    'trade_flow_fact_model'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
