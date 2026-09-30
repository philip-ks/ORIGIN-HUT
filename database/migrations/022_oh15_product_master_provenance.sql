BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 022
-- OH15 PRODUCT MASTER PROVENANCE
-- ============================================================
--
-- Manufacturer Product identity must carry the same source-backed
-- semantics as specifications, packaging, sites, documents and
-- compliance records.
--
-- This migration also makes entity_source_links automatic for all
-- OH15 canonical records that expose canonical_source_record_id.
-- Direct database ingestion and API writes therefore preserve the
-- same provenance chain.
-- ============================================================


ALTER TABLE manufacturer_products
ADD COLUMN source_type TEXT NOT NULL
    DEFAULT 'manual';


ALTER TABLE manufacturer_products
ADD COLUMN canonical_source_record_id UUID
    REFERENCES source_records(id)
    ON DELETE SET NULL;


ALTER TABLE manufacturer_products
ADD COLUMN confidence NUMERIC(5,4);


ALTER TABLE manufacturer_products
ADD CONSTRAINT
    manufacturer_products_source_type_not_blank
CHECK (
    BTRIM(source_type) <> ''
);


ALTER TABLE manufacturer_products
ADD CONSTRAINT
    manufacturer_products_confidence_range
CHECK (
    confidence IS NULL
    OR (
        confidence >= 0
        AND confidence <= 1
    )
);


CREATE INDEX
idx_manufacturer_products_source_record
ON manufacturer_products (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE OR REPLACE FUNCTION
originhut_link_canonical_source_record()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_entity_type TEXT;
    v_relationship_type TEXT;
BEGIN

    IF NEW.canonical_source_record_id IS NULL THEN
        RETURN NEW;
    END IF;


    v_entity_type :=
        TG_ARGV[0];

    v_relationship_type :=
        TG_ARGV[1];


    INSERT INTO entity_source_links (
        source_record_id,
        entity_type,
        entity_id,
        relationship_type,
        confidence,
        metadata
    )
    VALUES (
        NEW.canonical_source_record_id,
        v_entity_type,
        NEW.id,
        v_relationship_type,
        NEW.confidence,
        jsonb_build_object(
            'createdBy',
            'originhut_link_canonical_source_record'
        )
    )
    ON CONFLICT DO NOTHING;


    RETURN NEW;

END;
$$;


CREATE TRIGGER
trg_manufacturer_products_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON manufacturer_products
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'manufacturer_product',
    'identity_evidence'
);


CREATE TRIGGER
trg_product_specifications_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON product_specifications
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'product_specification',
    'specification_evidence'
);


CREATE TRIGGER
trg_packaging_configurations_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON packaging_configurations
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'packaging_configuration',
    'packaging_evidence'
);


CREATE TRIGGER
trg_organization_sites_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON organization_sites
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'organization_site',
    'site_evidence'
);


CREATE TRIGGER
trg_manufacturer_product_sites_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON manufacturer_product_sites
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'manufacturer_product_site',
    'site_relationship_evidence'
);


CREATE TRIGGER
trg_product_documents_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON product_documents
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'product_document',
    'documentary_evidence'
);


CREATE TRIGGER
trg_product_compliance_records_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON product_compliance_records
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'product_compliance_record',
    'compliance_evidence'
);


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '022',
    'oh15_product_master_provenance'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
