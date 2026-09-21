BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 001
-- CORE TRADE DATA MODEL
-- ============================================================


-- ------------------------------------------------------------
-- MIGRATION HISTORY
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schema_migrations (

    version VARCHAR(50) PRIMARY KEY,

    name TEXT NOT NULL,

    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);


-- ------------------------------------------------------------
-- COUNTRIES
-- ISO-based canonical country reference
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS countries (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    iso2 VARCHAR(2) NOT NULL UNIQUE,

    iso3 VARCHAR(3) UNIQUE,

    numeric_code VARCHAR(3),

    name TEXT NOT NULL,

    official_name TEXT,

    region TEXT,

    subregion TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);


CREATE INDEX IF NOT EXISTS idx_countries_name_trgm
ON countries
USING GIN (name gin_trgm_ops);


-- ------------------------------------------------------------
-- CURRENCIES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS currencies (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    code VARCHAR(3) NOT NULL UNIQUE,

    name TEXT NOT NULL,

    symbol TEXT,

    decimal_places SMALLINT NOT NULL DEFAULT 2,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);


-- ------------------------------------------------------------
-- COUNTRY <-> CURRENCY
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS country_currencies (

    country_id UUID NOT NULL
        REFERENCES countries(id)
        ON DELETE CASCADE,

    currency_id UUID NOT NULL
        REFERENCES currencies(id)
        ON DELETE CASCADE,

    is_primary BOOLEAN NOT NULL DEFAULT TRUE,

    valid_from DATE,

    valid_to DATE,

    PRIMARY KEY (
        country_id,
        currency_id
    )

);


-- ------------------------------------------------------------
-- HS NOMENCLATURE
--
-- Supports multiple HS editions:
-- HS2017
-- HS2022
-- future revisions
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS hs_codes (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    nomenclature VARCHAR(20) NOT NULL,

    code VARCHAR(20) NOT NULL,

    level SMALLINT NOT NULL,

    parent_id UUID
        REFERENCES hs_codes(id)
        ON DELETE SET NULL,

    description TEXT NOT NULL,

    notes TEXT,

    valid_from DATE,

    valid_to DATE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        nomenclature,
        code
    )

);


CREATE INDEX IF NOT EXISTS idx_hs_codes_code
ON hs_codes(code);


CREATE INDEX IF NOT EXISTS idx_hs_codes_description_trgm
ON hs_codes
USING GIN (description gin_trgm_ops);


CREATE INDEX IF NOT EXISTS idx_hs_codes_parent
ON hs_codes(parent_id);


-- ------------------------------------------------------------
-- TRADE LOCATIONS
--
-- Ports
-- Airports
-- ICDs
-- terminals
-- cities
-- logistics locations
-- UN/LOCODE
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS trade_locations (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    unlocode VARCHAR(5),

    country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    subdivision_code TEXT,

    name TEXT NOT NULL,

    location_type TEXT,

    function_codes TEXT,

    status TEXT,

    latitude NUMERIC(9,6),

    longitude NUMERIC(9,6),

    geography GEOGRAPHY(POINT, 4326),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        unlocode
    )

);


CREATE INDEX IF NOT EXISTS idx_trade_locations_country
ON trade_locations(country_id);


CREATE INDEX IF NOT EXISTS idx_trade_locations_geography
ON trade_locations
USING GIST (geography);


CREATE INDEX IF NOT EXISTS idx_trade_locations_name_trgm
ON trade_locations
USING GIN (name gin_trgm_ops);


-- ------------------------------------------------------------
-- ORGANIZATIONS
--
-- One legal/company entity.
--
-- Roles are deliberately stored separately because one
-- organization can simultaneously be:
-- exporter
-- importer
-- manufacturer
-- supplier
-- buyer
-- distributor
-- logistics provider
-- etc.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS organizations (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    legal_name TEXT NOT NULL,

    trading_name TEXT,

    country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    registration_number TEXT,

    lei VARCHAR(20),

    tax_identifier TEXT,

    website TEXT,

    status TEXT,

    address JSONB NOT NULL DEFAULT '{}'::jsonb,

    geography GEOGRAPHY(POINT, 4326),

    identifiers JSONB NOT NULL DEFAULT '{}'::jsonb,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);


CREATE INDEX IF NOT EXISTS idx_organizations_legal_name_trgm
ON organizations
USING GIN (legal_name gin_trgm_ops);


CREATE INDEX IF NOT EXISTS idx_organizations_trading_name_trgm
ON organizations
USING GIN (trading_name gin_trgm_ops);


CREATE INDEX IF NOT EXISTS idx_organizations_country
ON organizations(country_id);


CREATE INDEX IF NOT EXISTS idx_organizations_lei
ON organizations(lei);


CREATE INDEX IF NOT EXISTS idx_organizations_registration_number
ON organizations(registration_number);


-- ------------------------------------------------------------
-- ORGANIZATION ROLES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS organization_roles (

    organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE CASCADE,

    role_code TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (
        organization_id,
        role_code
    )

);


CREATE INDEX IF NOT EXISTS idx_organization_roles_role
ON organization_roles(role_code);


-- ------------------------------------------------------------
-- PRODUCTS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS products (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    manufacturer_id UUID
        REFERENCES organizations(id)
        ON DELETE SET NULL,

    name TEXT NOT NULL,

    brand TEXT,

    sku TEXT,

    gtin TEXT,

    description TEXT,

    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);


CREATE INDEX IF NOT EXISTS idx_products_name_trgm
ON products
USING GIN (name gin_trgm_ops);


CREATE INDEX IF NOT EXISTS idx_products_brand_trgm
ON products
USING GIN (brand gin_trgm_ops);


CREATE INDEX IF NOT EXISTS idx_products_manufacturer
ON products(manufacturer_id);


CREATE INDEX IF NOT EXISTS idx_products_gtin
ON products(gtin);


-- ------------------------------------------------------------
-- PRODUCT HS CLASSIFICATIONS
--
-- Product classification can change across HS editions,
-- countries and time.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS product_hs_classifications (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    product_id UUID NOT NULL
        REFERENCES products(id)
        ON DELETE CASCADE,

    hs_code_id UUID NOT NULL
        REFERENCES hs_codes(id)
        ON DELETE CASCADE,

    country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    is_primary BOOLEAN NOT NULL DEFAULT FALSE,

    confidence NUMERIC(5,4),

    valid_from DATE,

    valid_to DATE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        product_id,
        hs_code_id,
        country_id
    )

);


CREATE INDEX IF NOT EXISTS idx_product_hs_product
ON product_hs_classifications(product_id);


CREATE INDEX IF NOT EXISTS idx_product_hs_code
ON product_hs_classifications(hs_code_id);


-- ------------------------------------------------------------
-- DATA SOURCE CATALOGUE
--
-- Every external dataset/API must be registered here.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS data_sources (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    code TEXT NOT NULL UNIQUE,

    name TEXT NOT NULL,

    provider TEXT,

    category TEXT,

    access_method TEXT,

    base_url TEXT,

    license TEXT,

    terms_url TEXT,

    attribution TEXT,

    refresh_frequency TEXT,

    is_official BOOLEAN NOT NULL DEFAULT FALSE,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);


-- ------------------------------------------------------------
-- INGESTION RUNS
--
-- One execution of a data-source import.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingestion_runs (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    data_source_id UUID NOT NULL
        REFERENCES data_sources(id)
        ON DELETE RESTRICT,

    status TEXT NOT NULL,

    cursor_value TEXT,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    finished_at TIMESTAMPTZ,

    records_seen BIGINT NOT NULL DEFAULT 0,

    records_inserted BIGINT NOT NULL DEFAULT 0,

    records_updated BIGINT NOT NULL DEFAULT 0,

    records_rejected BIGINT NOT NULL DEFAULT 0,

    error_message TEXT,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb

);


CREATE INDEX IF NOT EXISTS idx_ingestion_runs_source
ON ingestion_runs(data_source_id);


CREATE INDEX IF NOT EXISTS idx_ingestion_runs_started
ON ingestion_runs(started_at DESC);


-- ------------------------------------------------------------
-- RAW SOURCE RECORDS
--
-- Preserve source payload independently from normalized data.
--
-- This is critical:
-- Origin Hut never loses provenance.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS source_records (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    data_source_id UUID NOT NULL
        REFERENCES data_sources(id)
        ON DELETE RESTRICT,

    ingestion_run_id UUID
        REFERENCES ingestion_runs(id)
        ON DELETE SET NULL,

    external_id TEXT,

    record_type TEXT NOT NULL,

    source_timestamp TIMESTAMPTZ,

    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    content_hash TEXT,

    payload JSONB NOT NULL,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb

);


CREATE INDEX IF NOT EXISTS idx_source_records_source
ON source_records(data_source_id);


CREATE INDEX IF NOT EXISTS idx_source_records_external
ON source_records(
    data_source_id,
    external_id
);


CREATE INDEX IF NOT EXISTS idx_source_records_record_type
ON source_records(record_type);


-- ------------------------------------------------------------
-- ENTITY SOURCE LINKS
--
-- Links normalized Origin Hut records back to raw source data.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS entity_source_links (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    source_record_id UUID NOT NULL
        REFERENCES source_records(id)
        ON DELETE CASCADE,

    entity_type TEXT NOT NULL,

    entity_id UUID NOT NULL,

    relationship_type TEXT NOT NULL DEFAULT 'source',

    confidence NUMERIC(5,4),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        source_record_id,
        entity_type,
        entity_id,
        relationship_type
    )

);


CREATE INDEX IF NOT EXISTS idx_entity_source_links_entity
ON entity_source_links(
    entity_type,
    entity_id
);


-- ------------------------------------------------------------
-- UPDATED_AT FUNCTION
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION originhut_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    NEW.updated_at = NOW();

    RETURN NEW;

END;
$$;


-- ------------------------------------------------------------
-- UPDATED_AT TRIGGERS
-- ------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_countries_updated_at
ON countries;

CREATE TRIGGER trg_countries_updated_at
BEFORE UPDATE ON countries
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


DROP TRIGGER IF EXISTS trg_currencies_updated_at
ON currencies;

CREATE TRIGGER trg_currencies_updated_at
BEFORE UPDATE ON currencies
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


DROP TRIGGER IF EXISTS trg_hs_codes_updated_at
ON hs_codes;

CREATE TRIGGER trg_hs_codes_updated_at
BEFORE UPDATE ON hs_codes
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


DROP TRIGGER IF EXISTS trg_trade_locations_updated_at
ON trade_locations;

CREATE TRIGGER trg_trade_locations_updated_at
BEFORE UPDATE ON trade_locations
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


DROP TRIGGER IF EXISTS trg_organizations_updated_at
ON organizations;

CREATE TRIGGER trg_organizations_updated_at
BEFORE UPDATE ON organizations
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


DROP TRIGGER IF EXISTS trg_products_updated_at
ON products;

CREATE TRIGGER trg_products_updated_at
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


DROP TRIGGER IF EXISTS trg_data_sources_updated_at
ON data_sources;

CREATE TRIGGER trg_data_sources_updated_at
BEFORE UPDATE ON data_sources
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


-- ------------------------------------------------------------
-- RECORD MIGRATION
-- ------------------------------------------------------------

INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '001',
    'core_trade_data_model'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
