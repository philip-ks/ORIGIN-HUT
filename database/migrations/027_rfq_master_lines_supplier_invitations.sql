BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 027
-- RFQ MASTER / LINES / SUPPLIER INVITATIONS
-- ============================================================
--
-- RFQ = buyer demand.
-- Commercial Offer = seller response.
--
-- RFQ lines reference canonical Product objects rather than
-- duplicating Product master data.
-- ============================================================


CREATE TABLE rfqs (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    rfq_reference TEXT NOT NULL,

    buyer_organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    requester_organization_id UUID
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    destination_country_id UUID NOT NULL
        REFERENCES countries(id)
        ON DELETE RESTRICT,

    destination_trade_location_id UUID
        REFERENCES trade_locations(id)
        ON DELETE RESTRICT,

    destination_organization_site_id UUID
        REFERENCES organization_sites(id)
        ON DELETE RESTRICT,

    destination_place_text TEXT,

    requested_currency_id UUID
        REFERENCES currencies(id)
        ON DELETE RESTRICT,

    requested_incoterm_rule_id UUID
        REFERENCES incoterm_rules(id)
        ON DELETE RESTRICT,

    incoterm_flexible BOOLEAN NOT NULL
        DEFAULT TRUE,

    issue_date DATE,

    response_due_at TIMESTAMPTZ,

    status TEXT NOT NULL
        DEFAULT 'draft',

    notes TEXT,

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
        rfqs_reference_not_blank
    CHECK (
        BTRIM(rfq_reference) <> ''
    ),


    CONSTRAINT
        rfqs_distinct_requester_buyer
    CHECK (
        requester_organization_id IS NULL
        OR requester_organization_id
           <> buyer_organization_id
    ),


    CONSTRAINT
        rfqs_destination_required
    CHECK (
        destination_trade_location_id IS NOT NULL
        OR destination_organization_site_id IS NOT NULL
        OR destination_place_text IS NOT NULL
    ),


    CONSTRAINT
        rfqs_destination_text_not_blank
    CHECK (
        destination_place_text IS NULL
        OR BTRIM(destination_place_text) <> ''
    ),


    CONSTRAINT
        rfqs_status
    CHECK (
        status IN (
            'draft',
            'issued',
            'partially_responded',
            'responded',
            'closed',
            'cancelled'
        )
    ),


    CONSTRAINT
        rfqs_dates
    CHECK (
        issue_date IS NULL
        OR response_due_at IS NULL
        OR response_due_at::date >= issue_date
    ),


    CONSTRAINT
        rfqs_notes_not_blank
    CHECK (
        notes IS NULL
        OR BTRIM(notes) <> ''
    ),


    CONSTRAINT
        rfqs_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        rfqs_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

);


CREATE UNIQUE INDEX
rfqs_reference_unique
ON rfqs (
    rfq_reference
);


CREATE INDEX
idx_rfqs_buyer
ON rfqs (
    buyer_organization_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_rfqs_destination
ON rfqs (
    destination_country_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_rfqs_due
ON rfqs (
    response_due_at,
    status
);


CREATE INDEX
idx_rfqs_source_record
ON rfqs (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_rfqs_metadata_gin
ON rfqs
USING GIN (
    metadata
);


CREATE TABLE rfq_lines (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    rfq_id UUID NOT NULL
        REFERENCES rfqs(id)
        ON DELETE CASCADE,

    line_number INTEGER NOT NULL,

    product_id UUID NOT NULL
        REFERENCES products(id)
        ON DELETE RESTRICT,

    manufacturer_product_id UUID
        REFERENCES manufacturer_products(id)
        ON DELETE RESTRICT,

    packaging_configuration_id UUID
        REFERENCES packaging_configurations(id)
        ON DELETE RESTRICT,

    requested_quantity NUMERIC(30,12) NOT NULL,

    requested_uom_id UUID NOT NULL
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    target_delivery_date DATE,

    specification_requirements JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    notes TEXT,

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
        rfq_lines_line_number_positive
    CHECK (
        line_number > 0
    ),


    CONSTRAINT
        rfq_lines_quantity_positive
    CHECK (
        requested_quantity > 0
    ),


    CONSTRAINT
        rfq_lines_notes_not_blank
    CHECK (
        notes IS NULL
        OR BTRIM(notes) <> ''
    ),


    CONSTRAINT
        rfq_lines_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        rfq_lines_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    UNIQUE (
        rfq_id,
        line_number
    )

);


CREATE INDEX
idx_rfq_lines_rfq
ON rfq_lines (
    rfq_id,
    line_number
);


CREATE INDEX
idx_rfq_lines_product
ON rfq_lines (
    product_id,
    rfq_id
);


CREATE INDEX
idx_rfq_lines_manufacturer_product
ON rfq_lines (
    manufacturer_product_id
)
WHERE manufacturer_product_id IS NOT NULL;


CREATE INDEX
idx_rfq_lines_source_record
ON rfq_lines (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_rfq_lines_metadata_gin
ON rfq_lines
USING GIN (
    metadata
);


CREATE TABLE rfq_suppliers (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    rfq_id UUID NOT NULL
        REFERENCES rfqs(id)
        ON DELETE CASCADE,

    supplier_organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    status TEXT NOT NULL
        DEFAULT 'invited',

    invited_at TIMESTAMPTZ,

    acknowledged_at TIMESTAMPTZ,

    responded_at TIMESTAMPTZ,

    response_due_at TIMESTAMPTZ,

    notes TEXT,

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
        rfq_suppliers_status
    CHECK (
        status IN (
            'invited',
            'acknowledged',
            'declined',
            'responded',
            'withdrawn'
        )
    ),


    CONSTRAINT
        rfq_suppliers_dates
    CHECK (
        acknowledged_at IS NULL
        OR invited_at IS NULL
        OR acknowledged_at >= invited_at
    ),


    CONSTRAINT
        rfq_suppliers_response_dates
    CHECK (
        responded_at IS NULL
        OR invited_at IS NULL
        OR responded_at >= invited_at
    ),


    CONSTRAINT
        rfq_suppliers_due_dates
    CHECK (
        response_due_at IS NULL
        OR invited_at IS NULL
        OR response_due_at >= invited_at
    ),


    CONSTRAINT
        rfq_suppliers_notes_not_blank
    CHECK (
        notes IS NULL
        OR BTRIM(notes) <> ''
    ),


    CONSTRAINT
        rfq_suppliers_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        rfq_suppliers_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    UNIQUE (
        rfq_id,
        supplier_organization_id
    )

);


CREATE INDEX
idx_rfq_suppliers_rfq
ON rfq_suppliers (
    rfq_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_rfq_suppliers_supplier
ON rfq_suppliers (
    supplier_organization_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_rfq_suppliers_source_record
ON rfq_suppliers (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_rfq_suppliers_metadata_gin
ON rfq_suppliers
USING GIN (
    metadata
);


CREATE OR REPLACE FUNCTION
originhut_validate_rfq()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_location_country_id UUID;
    v_site_country_id UUID;
BEGIN

    IF NEW.destination_trade_location_id IS NOT NULL THEN

        SELECT country_id
        INTO v_location_country_id
        FROM trade_locations
        WHERE
            id = NEW.destination_trade_location_id
            AND marked_for_deletion = FALSE;


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'RFQ destination trade location does not exist or is inactive.';
        END IF;


        IF
            v_location_country_id
            <> NEW.destination_country_id
        THEN
            RAISE EXCEPTION
                'RFQ destination trade location country must match RFQ destination country.';
        END IF;

    END IF;


    IF NEW.destination_organization_site_id IS NOT NULL THEN

        SELECT country_id
        INTO v_site_country_id
        FROM organization_sites
        WHERE
            id = NEW.destination_organization_site_id
            AND status = 'active';


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'RFQ destination organization site does not exist or is inactive.';
        END IF;


        IF
            v_site_country_id IS NOT NULL
            AND v_site_country_id
                <> NEW.destination_country_id
        THEN
            RAISE EXCEPTION
                'RFQ destination organization site country must match RFQ destination country.';
        END IF;

    END IF;


    RETURN NEW;

END;
$$;


CREATE OR REPLACE FUNCTION
originhut_validate_rfq_line()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_product_dimension TEXT;
    v_requested_dimension TEXT;
    v_manufacturer_product_product_id UUID;
    v_packaging_manufacturer_product_id UUID;
BEGIN

    SELECT base_uom.dimension_code
    INTO v_product_dimension
    FROM products p
    LEFT JOIN units_of_measure base_uom
      ON base_uom.id =
         p.base_uom_id
    WHERE
        p.id = NEW.product_id
        AND p.is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'RFQ Product does not exist or is inactive.';
    END IF;


    SELECT dimension_code
    INTO v_requested_dimension
    FROM units_of_measure
    WHERE
        id = NEW.requested_uom_id
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'RFQ requested UOM does not exist or is inactive.';
    END IF;


    IF
        v_product_dimension IS NOT NULL
        AND v_requested_dimension
            <> v_product_dimension
    THEN
        RAISE EXCEPTION
            'RFQ requested UOM dimension must match Product base UOM dimension.';
    END IF;


    IF NEW.manufacturer_product_id IS NOT NULL THEN

        SELECT product_id
        INTO v_manufacturer_product_product_id
        FROM manufacturer_products
        WHERE
            id = NEW.manufacturer_product_id
            AND status = 'active';


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'RFQ Manufacturer Product does not exist or is inactive.';
        END IF;


        IF
            v_manufacturer_product_product_id
            <> NEW.product_id
        THEN
            RAISE EXCEPTION
                'RFQ Manufacturer Product must belong to the requested Product.';
        END IF;

    END IF;


    IF NEW.packaging_configuration_id IS NOT NULL THEN

        IF NEW.manufacturer_product_id IS NULL THEN
            RAISE EXCEPTION
                'RFQ packaging restriction requires a Manufacturer Product restriction.';
        END IF;


        SELECT manufacturer_product_id
        INTO v_packaging_manufacturer_product_id
        FROM packaging_configurations
        WHERE
            id = NEW.packaging_configuration_id
            AND status = 'active';


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'RFQ packaging configuration does not exist or is inactive.';
        END IF;


        IF
            v_packaging_manufacturer_product_id
            <> NEW.manufacturer_product_id
        THEN
            RAISE EXCEPTION
                'RFQ packaging restriction must belong to the selected Manufacturer Product.';
        END IF;

    END IF;


    RETURN NEW;

END;
$$;


CREATE OR REPLACE FUNCTION
originhut_validate_rfq_supplier()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_buyer_id UUID;
BEGIN

    SELECT buyer_organization_id
    INTO v_buyer_id
    FROM rfqs
    WHERE id =
          NEW.rfq_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'RFQ does not exist.';
    END IF;


    IF
        NEW.supplier_organization_id
        = v_buyer_id
    THEN
        RAISE EXCEPTION
            'RFQ supplier cannot be the RFQ buyer.';
    END IF;


    RETURN NEW;

END;
$$;


CREATE TRIGGER
trg_rfqs_validate
BEFORE INSERT OR UPDATE
ON rfqs
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_rfq();


CREATE TRIGGER
trg_rfqs_updated_at
BEFORE UPDATE
ON rfqs
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_rfqs_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON rfqs
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'rfq',
    'rfq_evidence'
);


CREATE TRIGGER
trg_rfq_lines_validate
BEFORE INSERT OR UPDATE
ON rfq_lines
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_rfq_line();


CREATE TRIGGER
trg_rfq_lines_updated_at
BEFORE UPDATE
ON rfq_lines
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_rfq_lines_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON rfq_lines
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'rfq_line',
    'rfq_line_evidence'
);


CREATE TRIGGER
trg_rfq_suppliers_validate
BEFORE INSERT OR UPDATE
ON rfq_suppliers
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_rfq_supplier();


CREATE TRIGGER
trg_rfq_suppliers_updated_at
BEFORE UPDATE
ON rfq_suppliers
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_rfq_suppliers_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON rfq_suppliers
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'rfq_supplier',
    'supplier_invitation_evidence'
);


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '027',
    'rfq_master_lines_supplier_invitations'
)
ON CONFLICT (version)
DO NOTHING;


COMMIT;
