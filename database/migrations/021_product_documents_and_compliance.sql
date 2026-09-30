BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 021
-- PRODUCT DOCUMENTS + COMPLIANCE
-- ============================================================

CREATE TABLE product_document_types (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    code TEXT NOT NULL UNIQUE,

    name TEXT NOT NULL,

    category TEXT NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT product_document_types_code_not_blank
    CHECK (BTRIM(code) <> ''),

    CONSTRAINT product_document_types_name_not_blank
    CHECK (BTRIM(name) <> ''),

    CONSTRAINT product_document_types_category_not_blank
    CHECK (BTRIM(category) <> '')

);


CREATE TRIGGER trg_product_document_types_updated_at
BEFORE UPDATE ON product_document_types
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


INSERT INTO product_document_types (
    code,
    name,
    category
)
VALUES
    ('sds', 'Safety Data Sheet', 'safety'),
    ('tds', 'Technical Data Sheet', 'technical'),
    ('coa', 'Certificate of Analysis', 'quality'),
    ('coo', 'Certificate of Origin', 'trade'),
    ('test_report', 'Test Report', 'quality'),
    ('certificate', 'Certificate', 'compliance'),
    ('registration', 'Regulatory Registration', 'compliance')
ON CONFLICT (code) DO NOTHING;


CREATE TABLE product_documents (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    document_type_id UUID NOT NULL
        REFERENCES product_document_types(id)
        ON DELETE RESTRICT,

    product_id UUID
        REFERENCES products(id)
        ON DELETE CASCADE,

    manufacturer_product_id UUID
        REFERENCES manufacturer_products(id)
        ON DELETE CASCADE,

    issuer_organization_id UUID
        REFERENCES organizations(id)
        ON DELETE SET NULL,

    title TEXT NOT NULL,

    document_number TEXT,

    issue_date DATE,

    expiry_date DATE,

    status TEXT NOT NULL DEFAULT 'active',

    verification_status TEXT NOT NULL DEFAULT 'unverified',

    file_name TEXT,

    mime_type TEXT,

    storage_uri TEXT,

    content_sha256 CHAR(64),

    source_type TEXT NOT NULL DEFAULT 'manual',

    canonical_source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    confidence NUMERIC(5,4),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT product_documents_exactly_one_subject
    CHECK (
        (product_id IS NOT NULL AND manufacturer_product_id IS NULL)
        OR
        (product_id IS NULL AND manufacturer_product_id IS NOT NULL)
    ),

    CONSTRAINT product_documents_title_not_blank
    CHECK (BTRIM(title) <> ''),

    CONSTRAINT product_documents_status
    CHECK (
        status IN (
            'draft',
            'active',
            'superseded',
            'expired',
            'revoked'
        )
    ),

    CONSTRAINT product_documents_verification_status
    CHECK (
        verification_status IN (
            'unverified',
            'source_backed',
            'verified',
            'rejected'
        )
    ),

    CONSTRAINT product_documents_dates
    CHECK (
        issue_date IS NULL
        OR expiry_date IS NULL
        OR expiry_date >= issue_date
    ),

    CONSTRAINT product_documents_sha256
    CHECK (
        content_sha256 IS NULL
        OR content_sha256 ~ '^[0-9a-f]{64}$'
    ),

    CONSTRAINT product_documents_confidence_range
    CHECK (
        confidence IS NULL
        OR (confidence >= 0 AND confidence <= 1)
    )

);


CREATE INDEX idx_product_documents_product
ON product_documents (
    product_id,
    status,
    updated_at DESC
)
WHERE product_id IS NOT NULL;


CREATE INDEX idx_product_documents_manufacturer_product
ON product_documents (
    manufacturer_product_id,
    status,
    updated_at DESC
)
WHERE manufacturer_product_id IS NOT NULL;


CREATE INDEX idx_product_documents_type
ON product_documents (
    document_type_id,
    status
);


CREATE INDEX idx_product_documents_source_record
ON product_documents (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX idx_product_documents_metadata_gin
ON product_documents USING GIN (metadata);


CREATE TRIGGER trg_product_documents_updated_at
BEFORE UPDATE ON product_documents
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


CREATE TABLE compliance_frameworks (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    code TEXT NOT NULL UNIQUE,

    name TEXT NOT NULL,

    authority TEXT,

    jurisdiction_country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    website TEXT,

    status TEXT NOT NULL DEFAULT 'active',

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT compliance_frameworks_code_not_blank
    CHECK (BTRIM(code) <> ''),

    CONSTRAINT compliance_frameworks_name_not_blank
    CHECK (BTRIM(name) <> ''),

    CONSTRAINT compliance_frameworks_status_not_blank
    CHECK (BTRIM(status) <> '')

);


CREATE INDEX idx_compliance_frameworks_jurisdiction
ON compliance_frameworks (
    jurisdiction_country_id,
    status
);


CREATE TRIGGER trg_compliance_frameworks_updated_at
BEFORE UPDATE ON compliance_frameworks
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


CREATE TABLE product_compliance_records (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    framework_id UUID NOT NULL
        REFERENCES compliance_frameworks(id)
        ON DELETE RESTRICT,

    product_id UUID
        REFERENCES products(id)
        ON DELETE CASCADE,

    manufacturer_product_id UUID
        REFERENCES manufacturer_products(id)
        ON DELETE CASCADE,

    requirement_code TEXT,

    registration_number TEXT,

    compliance_status TEXT NOT NULL DEFAULT 'claimed',

    evidence_document_id UUID
        REFERENCES product_documents(id)
        ON DELETE SET NULL,

    valid_from DATE,

    valid_to DATE,

    source_type TEXT NOT NULL DEFAULT 'manual',

    canonical_source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    confidence NUMERIC(5,4),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT product_compliance_records_exactly_one_subject
    CHECK (
        (product_id IS NOT NULL AND manufacturer_product_id IS NULL)
        OR
        (product_id IS NULL AND manufacturer_product_id IS NOT NULL)
    ),

    CONSTRAINT product_compliance_records_status
    CHECK (
        compliance_status IN (
            'unknown',
            'claimed',
            'compliant',
            'non_compliant',
            'not_applicable',
            'expired'
        )
    ),

    CONSTRAINT product_compliance_records_dates
    CHECK (
        valid_from IS NULL
        OR valid_to IS NULL
        OR valid_to >= valid_from
    ),

    CONSTRAINT product_compliance_records_confidence_range
    CHECK (
        confidence IS NULL
        OR (confidence >= 0 AND confidence <= 1)
    )

);


CREATE INDEX idx_product_compliance_records_product
ON product_compliance_records (
    product_id,
    compliance_status,
    updated_at DESC
)
WHERE product_id IS NOT NULL;


CREATE INDEX idx_product_compliance_records_manufacturer_product
ON product_compliance_records (
    manufacturer_product_id,
    compliance_status,
    updated_at DESC
)
WHERE manufacturer_product_id IS NOT NULL;


CREATE INDEX idx_product_compliance_records_framework
ON product_compliance_records (
    framework_id,
    compliance_status
);


CREATE INDEX idx_product_compliance_records_source_record
ON product_compliance_records (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX idx_product_compliance_records_metadata_gin
ON product_compliance_records USING GIN (metadata);


CREATE UNIQUE INDEX product_compliance_records_active_product_unique
ON product_compliance_records (
    product_id,
    framework_id,
    COALESCE(requirement_code, '')
)
WHERE
    product_id IS NOT NULL
    AND compliance_status IN ('claimed', 'compliant');


CREATE UNIQUE INDEX product_compliance_records_active_manufacturer_product_unique
ON product_compliance_records (
    manufacturer_product_id,
    framework_id,
    COALESCE(requirement_code, '')
)
WHERE
    manufacturer_product_id IS NOT NULL
    AND compliance_status IN ('claimed', 'compliant');


CREATE OR REPLACE FUNCTION
originhut_validate_compliance_document_subject()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_product_id UUID;
    v_manufacturer_product_id UUID;
BEGIN

    IF NEW.evidence_document_id IS NULL THEN
        RETURN NEW;
    END IF;


    SELECT
        product_id,
        manufacturer_product_id
    INTO
        v_product_id,
        v_manufacturer_product_id
    FROM product_documents
    WHERE id = NEW.evidence_document_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Evidence document does not exist.';
    END IF;


    IF
        v_product_id IS DISTINCT FROM NEW.product_id
        OR
        v_manufacturer_product_id
            IS DISTINCT FROM NEW.manufacturer_product_id
    THEN
        RAISE EXCEPTION
            'Compliance evidence document must belong to the same Product subject.';
    END IF;


    RETURN NEW;

END;
$$;


CREATE TRIGGER trg_product_compliance_records_validate_document
BEFORE INSERT OR UPDATE
ON product_compliance_records
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_compliance_document_subject();


CREATE TRIGGER trg_product_compliance_records_updated_at
BEFORE UPDATE ON product_compliance_records
FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '021',
    'product_documents_and_compliance'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
