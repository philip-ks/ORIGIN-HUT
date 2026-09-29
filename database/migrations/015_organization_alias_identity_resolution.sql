BEGIN;

CREATE OR REPLACE FUNCTION originhut_normalize_organization_name(value TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $$
DECLARE
    normalized TEXT;
BEGIN
    normalized := LOWER(BTRIM(value));
    normalized := REPLACE(normalized, '&', ' and ');
    normalized := REGEXP_REPLACE(normalized, E'[^[:alnum:]]+', ' ', 'g');
    normalized := REGEXP_REPLACE(normalized, E'\\mpvt\\M', 'private', 'g');
    normalized := REGEXP_REPLACE(normalized, E'\\mltd\\M', 'limited', 'g');
    normalized := REGEXP_REPLACE(normalized, E'\\mco\\M', 'company', 'g');
    normalized := REGEXP_REPLACE(
        normalized,
        E'\\ml[[:space:]]+l[[:space:]]+c\\M',
        'llc',
        'g'
    );
    normalized := REGEXP_REPLACE(
        normalized,
        E'\\mf[[:space:]]+z\\M',
        'fz',
        'g'
    );
    normalized := REGEXP_REPLACE(
        normalized,
        E'[[:space:]]+',
        ' ',
        'g'
    );
    RETURN BTRIM(normalized);
END;
$$;


CREATE TABLE organization_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE CASCADE,

    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,

    alias_type TEXT NOT NULL
        DEFAULT 'source_name',

    language_code TEXT,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT organization_aliases_alias_not_blank
        CHECK (BTRIM(alias) <> ''),

    CONSTRAINT organization_aliases_normalized_not_blank
        CHECK (BTRIM(normalized_alias) <> ''),

    CONSTRAINT organization_aliases_type_not_blank
        CHECK (BTRIM(alias_type) <> ''),

    UNIQUE (
        organization_id,
        alias,
        alias_type
    )
);


CREATE INDEX idx_organization_aliases_organization
ON organization_aliases (
    organization_id,
    is_active
);

CREATE INDEX idx_organization_aliases_normalized
ON organization_aliases (
    normalized_alias
)
WHERE is_active = TRUE;

CREATE INDEX idx_organization_aliases_alias_trgm
ON organization_aliases
USING GIN (alias gin_trgm_ops);

CREATE INDEX idx_organization_aliases_normalized_trgm
ON organization_aliases
USING GIN (normalized_alias gin_trgm_ops);

CREATE INDEX idx_organization_aliases_source_record
ON organization_aliases (
    source_record_id
)
WHERE source_record_id IS NOT NULL;


CREATE INDEX idx_organizations_lei_normalized
ON organizations (
    UPPER(BTRIM(lei))
)
WHERE lei IS NOT NULL;

CREATE INDEX idx_organizations_registration_country_normalized
ON organizations (
    country_id,
    UPPER(BTRIM(registration_number))
)
WHERE registration_number IS NOT NULL;

CREATE INDEX idx_organizations_tax_country_normalized
ON organizations (
    country_id,
    UPPER(BTRIM(tax_identifier))
)
WHERE tax_identifier IS NOT NULL;


CREATE TRIGGER trg_organization_aliases_updated_at
BEFORE UPDATE
ON organization_aliases
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


CREATE OR REPLACE FUNCTION originhut_sync_organization_name_aliases()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO organization_aliases (
        organization_id,
        alias,
        normalized_alias,
        alias_type,
        is_active,
        metadata
    )
    VALUES (
        NEW.id,
        NEW.legal_name,
        originhut_normalize_organization_name(NEW.legal_name),
        'legal_name',
        TRUE,
        jsonb_build_object(
            'synchronizedFrom',
            'organizations.legal_name'
        )
    )
    ON CONFLICT (
        organization_id,
        alias,
        alias_type
    )
    DO UPDATE SET
        alias = EXCLUDED.alias,
        is_active = TRUE,
        metadata =
            organization_aliases.metadata
            || EXCLUDED.metadata,
        updated_at = NOW();

    IF (
        NEW.trading_name IS NOT NULL
        AND BTRIM(NEW.trading_name) <> ''
    ) THEN
        INSERT INTO organization_aliases (
            organization_id,
            alias,
            normalized_alias,
            alias_type,
            is_active,
            metadata
        )
        VALUES (
            NEW.id,
            NEW.trading_name,
            originhut_normalize_organization_name(NEW.trading_name),
            'trading_name',
            TRUE,
            jsonb_build_object(
                'synchronizedFrom',
                'organizations.trading_name'
            )
        )
        ON CONFLICT (
        organization_id,
        alias,
        alias_type
    )
        DO UPDATE SET
            alias = EXCLUDED.alias,
            is_active = TRUE,
            metadata =
                organization_aliases.metadata
                || EXCLUDED.metadata,
            updated_at = NOW();
    END IF;

    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_organizations_sync_name_aliases
AFTER INSERT OR UPDATE OF legal_name, trading_name
ON organizations
FOR EACH ROW
EXECUTE FUNCTION originhut_sync_organization_name_aliases();


INSERT INTO organization_aliases (
    organization_id,
    alias,
    normalized_alias,
    alias_type,
    is_active,
    metadata
)
SELECT
    id,
    legal_name,
    originhut_normalize_organization_name(legal_name),
    'legal_name',
    TRUE,
    jsonb_build_object('backfilledBy', 'migration_015')
FROM organizations
WHERE BTRIM(legal_name) <> ''
ON CONFLICT (
        organization_id,
        alias,
        alias_type
    )
DO NOTHING;


INSERT INTO organization_aliases (
    organization_id,
    alias,
    normalized_alias,
    alias_type,
    is_active,
    metadata
)
SELECT
    id,
    trading_name,
    originhut_normalize_organization_name(trading_name),
    'trading_name',
    TRUE,
    jsonb_build_object('backfilledBy', 'migration_015')
FROM organizations
WHERE
    trading_name IS NOT NULL
    AND BTRIM(trading_name) <> ''
ON CONFLICT (
        organization_id,
        alias,
        alias_type
    )
DO NOTHING;


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '015',
    'organization_alias_identity_resolution'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
