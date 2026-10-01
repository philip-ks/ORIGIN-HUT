BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 024
-- COMMERCIAL OFFERS
-- ============================================================
--
-- A Commercial Offer is not Product master data.
--
-- It is a seller's time-bound commercial proposition for a
-- Manufacturer Product, optionally constrained to a buyer and
-- packaging configuration.
--
-- Statistical trade_flow FOB/CIF values remain separate.
-- ============================================================


CREATE TABLE commercial_offers (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    seller_organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    buyer_organization_id UUID
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    manufacturer_product_id UUID NOT NULL
        REFERENCES manufacturer_products(id)
        ON DELETE RESTRICT,

    packaging_configuration_id UUID
        REFERENCES packaging_configurations(id)
        ON DELETE RESTRICT,

    offer_reference TEXT,

    status TEXT NOT NULL
        DEFAULT 'draft',

    unit_price NUMERIC(30,12) NOT NULL,

    currency_id UUID NOT NULL
        REFERENCES currencies(id)
        ON DELETE RESTRICT,

    price_uom_id UUID NOT NULL
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    minimum_order_quantity NUMERIC(30,12),

    minimum_order_uom_id UUID
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    lead_time_days INTEGER,

    payment_terms TEXT,

    incoterm_rule_id UUID NOT NULL
        REFERENCES incoterm_rules(id)
        ON DELETE RESTRICT,

    named_place_text TEXT,

    named_trade_location_id UUID
        REFERENCES trade_locations(id)
        ON DELETE RESTRICT,

    named_organization_site_id UUID
        REFERENCES organization_sites(id)
        ON DELETE RESTRICT,

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
        commercial_offers_distinct_buyer_seller
    CHECK (
        buyer_organization_id IS NULL
        OR buyer_organization_id
           <> seller_organization_id
    ),


    CONSTRAINT
        commercial_offers_reference_not_blank
    CHECK (
        offer_reference IS NULL
        OR BTRIM(offer_reference) <> ''
    ),


    CONSTRAINT
        commercial_offers_status
    CHECK (
        status IN (
            'draft',
            'active',
            'expired',
            'withdrawn',
            'superseded'
        )
    ),


    CONSTRAINT
        commercial_offers_price_positive
    CHECK (
        unit_price > 0
    ),


    CONSTRAINT
        commercial_offers_moq_pair
    CHECK (
        (
            minimum_order_quantity IS NULL
            AND minimum_order_uom_id IS NULL
        )
        OR (
            minimum_order_quantity IS NOT NULL
            AND minimum_order_quantity > 0
            AND minimum_order_uom_id IS NOT NULL
        )
    ),


    CONSTRAINT
        commercial_offers_lead_time_nonnegative
    CHECK (
        lead_time_days IS NULL
        OR lead_time_days >= 0
    ),


    CONSTRAINT
        commercial_offers_payment_terms_not_blank
    CHECK (
        payment_terms IS NULL
        OR BTRIM(payment_terms) <> ''
    ),


    CONSTRAINT
        commercial_offers_named_location_required
    CHECK (
        named_place_text IS NOT NULL
        OR named_trade_location_id IS NOT NULL
        OR named_organization_site_id IS NOT NULL
    ),


    CONSTRAINT
        commercial_offers_named_place_not_blank
    CHECK (
        named_place_text IS NULL
        OR BTRIM(named_place_text) <> ''
    ),


    CONSTRAINT
        commercial_offers_valid_dates
    CHECK (
        valid_from IS NULL
        OR valid_to IS NULL
        OR valid_to >= valid_from
    ),


    CONSTRAINT
        commercial_offers_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        commercial_offers_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

);


CREATE INDEX
idx_commercial_offers_seller
ON commercial_offers (
    seller_organization_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_commercial_offers_buyer
ON commercial_offers (
    buyer_organization_id,
    status,
    updated_at DESC
)
WHERE buyer_organization_id IS NOT NULL;


CREATE INDEX
idx_commercial_offers_manufacturer_product
ON commercial_offers (
    manufacturer_product_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_commercial_offers_incoterm
ON commercial_offers (
    incoterm_rule_id,
    status
);


CREATE INDEX
idx_commercial_offers_validity
ON commercial_offers (
    valid_from,
    valid_to
);


CREATE INDEX
idx_commercial_offers_source_record
ON commercial_offers (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_commercial_offers_metadata_gin
ON commercial_offers
USING GIN (
    metadata
);


CREATE UNIQUE INDEX
commercial_offers_seller_reference_unique
ON commercial_offers (
    seller_organization_id,
    offer_reference
)
WHERE offer_reference IS NOT NULL;


CREATE OR REPLACE FUNCTION
originhut_validate_commercial_offer()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_product_id UUID;
    v_product_base_dimension TEXT;
    v_price_dimension TEXT;
    v_moq_dimension TEXT;
    v_packaging_product_id UUID;
    v_incoterm_scope TEXT;
BEGIN

    SELECT
        mp.product_id,
        base_uom.dimension_code
    INTO
        v_product_id,
        v_product_base_dimension
    FROM manufacturer_products mp
    JOIN products p
      ON p.id = mp.product_id
    LEFT JOIN units_of_measure base_uom
      ON base_uom.id = p.base_uom_id
    WHERE
        mp.id = NEW.manufacturer_product_id
        AND mp.status = 'active';


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Manufacturer Product does not exist or is inactive.';
    END IF;


    SELECT dimension_code
    INTO v_price_dimension
    FROM units_of_measure
    WHERE
        id = NEW.price_uom_id
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Price UOM does not exist or is inactive.';
    END IF;


    IF
        v_product_base_dimension IS NOT NULL
        AND v_price_dimension
            <> v_product_base_dimension
    THEN
        RAISE EXCEPTION
            'Price UOM dimension must match Product base UOM dimension.';
    END IF;


    IF NEW.minimum_order_uom_id IS NOT NULL THEN

        SELECT dimension_code
        INTO v_moq_dimension
        FROM units_of_measure
        WHERE
            id = NEW.minimum_order_uom_id
            AND is_active = TRUE;


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'MOQ UOM does not exist or is inactive.';
        END IF;


        IF
            v_product_base_dimension IS NOT NULL
            AND v_moq_dimension
                <> v_product_base_dimension
        THEN
            RAISE EXCEPTION
                'MOQ UOM dimension must match Product base UOM dimension.';
        END IF;

    END IF;


    IF NEW.packaging_configuration_id IS NOT NULL THEN

        SELECT manufacturer_product_id
        INTO v_packaging_product_id
        FROM packaging_configurations
        WHERE
            id = NEW.packaging_configuration_id
            AND status = 'active';


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Packaging configuration does not exist or is inactive.';
        END IF;


        IF
            v_packaging_product_id
            <> NEW.manufacturer_product_id
        THEN
            RAISE EXCEPTION
                'Packaging configuration must belong to the same Manufacturer Product.';
        END IF;

    END IF;


    SELECT transport_scope
    INTO v_incoterm_scope
    FROM incoterm_rules
    WHERE
        id = NEW.incoterm_rule_id
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Incoterm rule does not exist or is inactive.';
    END IF;


    IF
        v_incoterm_scope = 'sea_inland_waterway'
        AND NEW.named_trade_location_id IS NULL
    THEN
        RAISE EXCEPTION
            'Sea/inland-waterway Incoterms require a canonical trade location.';
    END IF;


    RETURN NEW;

END;
$$;


CREATE TRIGGER
trg_commercial_offers_validate
BEFORE INSERT OR UPDATE
ON commercial_offers
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_commercial_offer();


CREATE TRIGGER
trg_commercial_offers_updated_at
BEFORE UPDATE
ON commercial_offers
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_commercial_offers_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON commercial_offers
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'commercial_offer',
    'offer_evidence'
);


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '024',
    'commercial_offers'
)
ON CONFLICT (version)
DO NOTHING;


COMMIT;
