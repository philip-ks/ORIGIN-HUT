BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 020
-- ORGANIZATION SITES + PRODUCT MANUFACTURING LOCATIONS
-- ============================================================
--
-- Keep these facts distinct:
--
-- organization country
-- manufacturing / packaging / storage site country
-- manufacturer-product country of origin
--
-- Country of origin must not be inferred from organization
-- country or site country.
-- ============================================================


CREATE TABLE organization_sites (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE CASCADE,

    name TEXT NOT NULL,

    site_type TEXT NOT NULL,

    country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    trade_location_id UUID
        REFERENCES trade_locations(id)
        ON DELETE SET NULL,

    address JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    geography GEOGRAPHY(POINT, 4326),

    status TEXT NOT NULL
        DEFAULT 'active',

    source_type TEXT NOT NULL
        DEFAULT 'manual',

    canonical_source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    confidence NUMERIC(5,4),

    identifiers JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        organization_sites_name_not_blank
    CHECK (
        BTRIM(name) <> ''
    ),


    CONSTRAINT
        organization_sites_type
    CHECK (
        site_type IN (
            'manufacturing',
            'packaging',
            'warehouse',
            'distribution_center',
            'office',
            'laboratory',
            'other'
        )
    ),


    CONSTRAINT
        organization_sites_status_not_blank
    CHECK (
        BTRIM(status) <> ''
    ),


    CONSTRAINT
        organization_sites_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        organization_sites_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

);


CREATE INDEX
idx_organization_sites_organization
ON organization_sites (
    organization_id,
    status,
    site_type,
    updated_at DESC
);


CREATE INDEX
idx_organization_sites_country
ON organization_sites (
    country_id
);


CREATE INDEX
idx_organization_sites_trade_location
ON organization_sites (
    trade_location_id
);


CREATE INDEX
idx_organization_sites_geography
ON organization_sites
USING GIST (
    geography
);


CREATE INDEX
idx_organization_sites_name_trgm
ON organization_sites
USING GIN (
    name gin_trgm_ops
);


CREATE INDEX
idx_organization_sites_metadata_gin
ON organization_sites
USING GIN (
    metadata
);


CREATE UNIQUE INDEX
organization_sites_active_name_unique
ON organization_sites (
    organization_id,
    name
)
WHERE status = 'active';


CREATE TRIGGER
trg_organization_sites_updated_at
BEFORE UPDATE
ON organization_sites
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TABLE manufacturer_product_sites (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    manufacturer_product_id UUID NOT NULL
        REFERENCES manufacturer_products(id)
        ON DELETE CASCADE,

    organization_site_id UUID NOT NULL
        REFERENCES organization_sites(id)
        ON DELETE RESTRICT,

    relationship_type TEXT NOT NULL,

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
        manufacturer_product_sites_relationship_type
    CHECK (
        relationship_type IN (
            'manufactured_at',
            'packaged_at',
            'stored_at',
            'distributed_from'
        )
    ),


    CONSTRAINT
        manufacturer_product_sites_status_not_blank
    CHECK (
        BTRIM(status) <> ''
    ),


    CONSTRAINT
        manufacturer_product_sites_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        manufacturer_product_sites_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    CONSTRAINT
        manufacturer_product_sites_valid_dates
    CHECK (
        valid_from IS NULL
        OR valid_to IS NULL
        OR valid_to >= valid_from
    )

);


CREATE INDEX
idx_manufacturer_product_sites_product
ON manufacturer_product_sites (
    manufacturer_product_id,
    status,
    relationship_type,
    updated_at DESC
);


CREATE INDEX
idx_manufacturer_product_sites_site
ON manufacturer_product_sites (
    organization_site_id,
    status,
    relationship_type
);


CREATE INDEX
idx_manufacturer_product_sites_source_record
ON manufacturer_product_sites (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE UNIQUE INDEX
manufacturer_product_sites_active_unique
ON manufacturer_product_sites (
    manufacturer_product_id,
    organization_site_id,
    relationship_type
)
WHERE
    status = 'active'
    AND valid_to IS NULL;


CREATE TRIGGER
trg_manufacturer_product_sites_updated_at
BEFORE UPDATE
ON manufacturer_product_sites
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '020',
    'organization_sites_and_product_manufacturing_locations'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
