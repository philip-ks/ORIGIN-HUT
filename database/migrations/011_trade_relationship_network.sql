BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 011
-- TRADE RELATIONSHIP NETWORK
-- ============================================================


-- ------------------------------------------------------------
-- ORGANIZATION RELATIONSHIPS
--
-- Directional relationship:
--
-- source_organization_id
--          |
--          | relationship_type
--          v
-- target_organization_id
--
-- Examples:
--
-- manufacturer -> supplies       -> distributor
-- supplier     -> supplies       -> hospital
-- exporter     -> exports_to     -> importer
-- distributor  -> distributes_to -> pharmacy
--
-- Organization roles describe what an organization IS.
-- Organization relationships describe how organizations
-- INTERACT with one another.
-- ------------------------------------------------------------

CREATE TABLE organization_relationships (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    source_organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE CASCADE,

    target_organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE CASCADE,

    relationship_type TEXT NOT NULL,

    status TEXT NOT NULL
        DEFAULT 'active',

    valid_from DATE,

    valid_to DATE,

    confidence NUMERIC(5,4),

    source_type TEXT NOT NULL
        DEFAULT 'manual',

    notes TEXT,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        organization_relationships_distinct_organizations
    CHECK (
        source_organization_id
        <> target_organization_id
    ),


    CONSTRAINT
        organization_relationships_type_not_blank
    CHECK (
        BTRIM(relationship_type)
        <> ''
    ),


    CONSTRAINT
        organization_relationships_status_not_blank
    CHECK (
        BTRIM(status)
        <> ''
    ),


    CONSTRAINT
        organization_relationships_source_type_not_blank
    CHECK (
        BTRIM(source_type)
        <> ''
    ),


    CONSTRAINT
        organization_relationships_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    CONSTRAINT
        organization_relationships_valid_dates
    CHECK (
        valid_from IS NULL
        OR valid_to IS NULL
        OR valid_to >= valid_from
    )

);


-- ------------------------------------------------------------
-- COUNTERPARTY LOOKUPS
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_relationships_source
ON organization_relationships (
    source_organization_id
);


CREATE INDEX
idx_organization_relationships_target
ON organization_relationships (
    target_organization_id
);


-- ------------------------------------------------------------
-- SOURCE / TARGET + STATUS
--
-- Useful for:
--   outgoing active relationships
--   incoming active relationships
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_relationships_source_status
ON organization_relationships (
    source_organization_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_organization_relationships_target_status
ON organization_relationships (
    target_organization_id,
    status,
    updated_at DESC
);


-- ------------------------------------------------------------
-- RELATIONSHIP-TYPE SEARCH
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_relationships_type_status
ON organization_relationships (
    relationship_type,
    status
);


-- ------------------------------------------------------------
-- TEMPORAL LOOKUPS
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_relationships_validity
ON organization_relationships (
    valid_from,
    valid_to
);


-- ------------------------------------------------------------
-- METADATA SEARCH
-- ------------------------------------------------------------

CREATE INDEX
idx_organization_relationships_metadata_gin
ON organization_relationships
USING GIN (
    metadata
);


-- ------------------------------------------------------------
-- PREVENT DUPLICATE OPEN ACTIVE RELATIONSHIPS
--
-- Only one currently-open active relationship of the same type
-- may exist between the same directional pair.
--
-- Historical relationships remain possible after valid_to is set
-- or status changes.
-- ------------------------------------------------------------

CREATE UNIQUE INDEX
organization_relationships_active_open_unique
ON organization_relationships (
    source_organization_id,
    target_organization_id,
    relationship_type
)
WHERE
    status = 'active'
    AND valid_to IS NULL;


-- ------------------------------------------------------------
-- UPDATED_AT
-- ------------------------------------------------------------

CREATE TRIGGER
trg_organization_relationships_updated_at
BEFORE UPDATE
ON organization_relationships
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
    '011',
    'trade_relationship_network'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
