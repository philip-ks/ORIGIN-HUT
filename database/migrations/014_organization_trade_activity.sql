BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 014
-- ORGANIZATION TRADE ACTIVITY
-- ============================================================
--
-- organization_roles:
--     what an organization generally IS
--
-- organization_relationships:
--     how two organizations INTERACT
--
-- organization_trade_activities:
--     what commercial activity an organization is evidenced
--     performing for a product / HS code and optional market
--
-- Statistical trade_flows MUST NOT automatically create
-- organization_trade_activities.
-- ============================================================


CREATE TABLE organization_trade_activities (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE CASCADE,

    activity_type TEXT NOT NULL,

    product_id UUID
        REFERENCES products(id)
        ON DELETE CASCADE,

    hs_code_id UUID
        REFERENCES hs_codes(id)
        ON DELETE CASCADE,

    market_country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    status TEXT NOT NULL
        DEFAULT 'active',

    confidence NUMERIC(5,4),

    valid_from DATE,

    valid_to DATE,

    source_type TEXT NOT NULL
        DEFAULT 'manual',

    canonical_source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        organization_trade_activities_subject_required
    CHECK (
        product_id IS NOT NULL
        OR hs_code_id IS NOT NULL
    ),


    CONSTRAINT
        organization_trade_activities_type_not_blank
    CHECK (
        BTRIM(activity_type) <> ''
    ),


    CONSTRAINT
        organization_trade_activities_status_not_blank
    CHECK (
        BTRIM(status) <> ''
    ),


    CONSTRAINT
        organization_trade_activities_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        organization_trade_activities_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    CONSTRAINT
        organization_trade_activities_valid_dates
    CHECK (
        valid_from IS NULL
        OR valid_to IS NULL
        OR valid_to >= valid_from
    )

);


-- ------------------------------------------------------------
-- ORGANIZATION LOOKUPS
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_trade_activities_organization
ON organization_trade_activities (
    organization_id
);


CREATE INDEX
idx_organization_trade_activities_organization_status
ON organization_trade_activities (
    organization_id,
    status,
    updated_at DESC
);


-- ------------------------------------------------------------
-- ACTIVITY SEARCH
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_trade_activities_type_status
ON organization_trade_activities (
    activity_type,
    status
);


-- ------------------------------------------------------------
-- PRODUCT / HS SEARCH
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_trade_activities_product
ON organization_trade_activities (
    product_id
)
WHERE product_id IS NOT NULL;


CREATE INDEX
idx_organization_trade_activities_hs
ON organization_trade_activities (
    hs_code_id
)
WHERE hs_code_id IS NOT NULL;


CREATE INDEX
idx_organization_trade_activities_hs_market
ON organization_trade_activities (
    hs_code_id,
    market_country_id,
    activity_type,
    status
)
WHERE hs_code_id IS NOT NULL;


CREATE INDEX
idx_organization_trade_activities_product_market
ON organization_trade_activities (
    product_id,
    market_country_id,
    activity_type,
    status
)
WHERE product_id IS NOT NULL;


-- ------------------------------------------------------------
-- MARKET SEARCH
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_trade_activities_market
ON organization_trade_activities (
    market_country_id,
    activity_type,
    status
)
WHERE market_country_id IS NOT NULL;


-- ------------------------------------------------------------
-- CANONICAL SOURCE
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_trade_activities_source
ON organization_trade_activities (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


-- ------------------------------------------------------------
-- CONFIDENCE / METADATA
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_trade_activities_confidence
ON organization_trade_activities (
    confidence DESC
)
WHERE confidence IS NOT NULL;


CREATE INDEX
idx_organization_trade_activities_metadata_gin
ON organization_trade_activities
USING GIN (
    metadata
);


-- ------------------------------------------------------------
-- CANONICAL CURRENT-ACTIVITY IDENTITY
--
-- Multiple pieces of evidence must link to ONE canonical
-- activity through entity_source_links rather than creating
-- duplicate activity rows.
--
-- NULLS NOT DISTINCT makes:
--
--     product_id = NULL
--     market_country_id = NULL
--
-- participate in uniqueness as real scope values.
-- ------------------------------------------------------------

CREATE UNIQUE INDEX
organization_trade_activities_active_open_unique
ON organization_trade_activities (
    organization_id,
    activity_type,
    product_id,
    hs_code_id,
    market_country_id
)
NULLS NOT DISTINCT
WHERE
    status = 'active'
    AND valid_to IS NULL;


-- ------------------------------------------------------------
-- UPDATED_AT
-- ------------------------------------------------------------

CREATE TRIGGER
trg_organization_trade_activities_updated_at
BEFORE UPDATE
ON organization_trade_activities
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


-- ------------------------------------------------------------
-- MIGRATION HISTORY
-- ------------------------------------------------------------

INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '014',
    'organization_trade_activity'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
