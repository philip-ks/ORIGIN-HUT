BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 010
-- ORGANIZATION DIRECTORY SUPPORT
-- ============================================================


-- Fast lifecycle/status filtering.
CREATE INDEX IF NOT EXISTS
idx_organizations_status
ON organizations(status);


-- Country + lifecycle filtering is common in trade-party search.
CREATE INDEX IF NOT EXISTS
idx_organizations_country_status
ON organizations(
    country_id,
    status
);


-- Tax identifiers are often exact-search identifiers.
CREATE INDEX IF NOT EXISTS
idx_organizations_tax_identifier
ON organizations(tax_identifier);


-- Preserve/search external identifiers and operational metadata.
CREATE INDEX IF NOT EXISTS
idx_organizations_identifiers_gin
ON organizations
USING GIN (identifiers);


CREATE INDEX IF NOT EXISTS
idx_organizations_metadata_gin
ON organizations
USING GIN (metadata);


-- Useful when filtering organizations by role and then joining
-- back to the organization entity.
CREATE INDEX IF NOT EXISTS
idx_organization_roles_role_organization
ON organization_roles(
    role_code,
    organization_id
);


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '010',
    'organization_directory_support'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
