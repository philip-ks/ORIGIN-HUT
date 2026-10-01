BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 030
-- BUYER QUOTATIONS
-- ============================================================
--
-- A Quotation is an outbound commercial document / proposal.
-- It is distinct from the supplier Commercial Offer and from the
-- internal Landed Cost Scenario used as a pricing basis.
-- ============================================================


CREATE TABLE quotations (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    quotation_reference TEXT NOT NULL,

    issuer_organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    customer_organization_id UUID NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    source_rfq_id UUID
        REFERENCES rfqs(id)
        ON DELETE RESTRICT,

    currency_id UUID NOT NULL
        REFERENCES currencies(id)
        ON DELETE RESTRICT,

    issue_date DATE,

    valid_until DATE,

    status TEXT NOT NULL
        DEFAULT 'draft',

    payment_terms TEXT,

    incoterm_rule_id UUID
        REFERENCES incoterm_rules(id)
        ON DELETE RESTRICT,

    named_place_text TEXT,

    named_trade_location_id UUID
        REFERENCES trade_locations(id)
        ON DELETE RESTRICT,

    named_organization_site_id UUID
        REFERENCES organization_sites(id)
        ON DELETE RESTRICT,

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
        quotations_reference_not_blank
    CHECK (
        BTRIM(quotation_reference) <> ''
    ),


    CONSTRAINT
        quotations_distinct_issuer_customer
    CHECK (
        issuer_organization_id
        <> customer_organization_id
    ),


    CONSTRAINT
        quotations_status
    CHECK (
        status IN (
            'draft',
            'issued',
            'accepted',
            'rejected',
            'expired',
            'cancelled'
        )
    ),


    CONSTRAINT
        quotations_dates
    CHECK (
        issue_date IS NULL
        OR valid_until IS NULL
        OR valid_until >= issue_date
    ),


    CONSTRAINT
        quotations_payment_terms_not_blank
    CHECK (
        payment_terms IS NULL
        OR BTRIM(payment_terms) <> ''
    ),


    CONSTRAINT
        quotations_named_place_not_blank
    CHECK (
        named_place_text IS NULL
        OR BTRIM(named_place_text) <> ''
    ),


    CONSTRAINT
        quotations_notes_not_blank
    CHECK (
        notes IS NULL
        OR BTRIM(notes) <> ''
    ),


    CONSTRAINT
        quotations_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        quotations_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

);


CREATE UNIQUE INDEX
quotations_reference_unique
ON quotations (
    quotation_reference
);


CREATE INDEX
idx_quotations_issuer
ON quotations (
    issuer_organization_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_quotations_customer
ON quotations (
    customer_organization_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_quotations_source_rfq
ON quotations (
    source_rfq_id
)
WHERE source_rfq_id IS NOT NULL;


CREATE INDEX
idx_quotations_source_record
ON quotations (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_quotations_metadata_gin
ON quotations
USING GIN (
    metadata
);


CREATE TABLE quotation_lines (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    quotation_id UUID NOT NULL
        REFERENCES quotations(id)
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

    source_rfq_line_id UUID
        REFERENCES rfq_lines(id)
        ON DELETE RESTRICT,

    source_commercial_offer_id UUID
        REFERENCES commercial_offers(id)
        ON DELETE RESTRICT,

    source_landed_cost_scenario_id UUID
        REFERENCES landed_cost_scenarios(id)
        ON DELETE RESTRICT,

    quantity NUMERIC(30,12) NOT NULL,

    uom_id UUID NOT NULL
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    internal_cost_unit_price NUMERIC(30,12),

    pricing_method TEXT NOT NULL
        DEFAULT 'manual',

    pricing_rate NUMERIC(18,8),

    quoted_unit_price NUMERIC(30,12),

    quoted_line_total NUMERIC(30,12)
        NOT NULL
        DEFAULT 0,

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
        quotation_lines_line_number_positive
    CHECK (
        line_number > 0
    ),


    CONSTRAINT
        quotation_lines_quantity_positive
    CHECK (
        quantity > 0
    ),


    CONSTRAINT
        quotation_lines_internal_cost_positive
    CHECK (
        internal_cost_unit_price IS NULL
        OR internal_cost_unit_price >= 0
    ),


    CONSTRAINT
        quotation_lines_pricing_method
    CHECK (
        pricing_method IN (
            'manual',
            'markup_percent',
            'margin_percent'
        )
    ),


    CONSTRAINT
        quotation_lines_pricing_shape
    CHECK (
        (
            pricing_method = 'manual'
            AND pricing_rate IS NULL
            AND quoted_unit_price IS NOT NULL
            AND quoted_unit_price > 0
        )
        OR (
            pricing_method = 'markup_percent'
            AND internal_cost_unit_price IS NOT NULL
            AND pricing_rate IS NOT NULL
            AND pricing_rate >= 0
            AND quoted_unit_price IS NOT NULL
            AND quoted_unit_price > 0
        )
        OR (
            pricing_method = 'margin_percent'
            AND internal_cost_unit_price IS NOT NULL
            AND pricing_rate IS NOT NULL
            AND pricing_rate >= 0
            AND pricing_rate < 100
            AND quoted_unit_price IS NOT NULL
            AND quoted_unit_price > 0
        )
    ),


    CONSTRAINT
        quotation_lines_total_nonnegative
    CHECK (
        quoted_line_total >= 0
    ),


    CONSTRAINT
        quotation_lines_notes_not_blank
    CHECK (
        notes IS NULL
        OR BTRIM(notes) <> ''
    ),


    CONSTRAINT
        quotation_lines_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        quotation_lines_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    UNIQUE (
        quotation_id,
        line_number
    )

);


CREATE INDEX
idx_quotation_lines_quotation
ON quotation_lines (
    quotation_id,
    line_number
);


CREATE INDEX
idx_quotation_lines_product
ON quotation_lines (
    product_id
);


CREATE INDEX
idx_quotation_lines_source_offer
ON quotation_lines (
    source_commercial_offer_id
)
WHERE source_commercial_offer_id IS NOT NULL;


CREATE INDEX
idx_quotation_lines_source_landed_cost
ON quotation_lines (
    source_landed_cost_scenario_id
)
WHERE source_landed_cost_scenario_id IS NOT NULL;


CREATE INDEX
idx_quotation_lines_source_record
ON quotation_lines (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_quotation_lines_metadata_gin
ON quotation_lines
USING GIN (
    metadata
);


CREATE OR REPLACE FUNCTION
originhut_validate_quotation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_rfq_buyer_id UUID;
    v_incoterm_named_location_role TEXT;
    v_location_function_codes TEXT;
    v_location_marked_for_deletion BOOLEAN;
    v_site_country_id UUID;
BEGIN

    IF NEW.source_rfq_id IS NOT NULL THEN

        SELECT buyer_organization_id
        INTO v_rfq_buyer_id
        FROM rfqs
        WHERE id =
              NEW.source_rfq_id;


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Source RFQ does not exist.';
        END IF;


        IF
            v_rfq_buyer_id
            <> NEW.customer_organization_id
        THEN
            RAISE EXCEPTION
                'Quotation customer must match source RFQ buyer.';
        END IF;

    END IF;


    IF NEW.incoterm_rule_id IS NOT NULL THEN

        SELECT named_location_role
        INTO v_incoterm_named_location_role
        FROM incoterm_rules
        WHERE
            id = NEW.incoterm_rule_id
            AND is_active = TRUE;


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Quotation Incoterm does not exist or is inactive.';
        END IF;


        IF
            NEW.named_place_text IS NULL
            AND NEW.named_trade_location_id IS NULL
            AND NEW.named_organization_site_id IS NULL
        THEN
            RAISE EXCEPTION
                'Quotation Incoterm requires a named place or location.';
        END IF;


        IF
            v_incoterm_named_location_role IN (
                'shipment_port',
                'destination_port'
            )
            AND NEW.named_trade_location_id IS NULL
        THEN
            RAISE EXCEPTION
                'Maritime Quotation Incoterm requires a canonical maritime trade location.';
        END IF;

    END IF;


    IF NEW.named_trade_location_id IS NOT NULL THEN

        SELECT
            function_codes,
            marked_for_deletion
        INTO
            v_location_function_codes,
            v_location_marked_for_deletion
        FROM trade_locations
        WHERE id =
              NEW.named_trade_location_id;


        IF NOT FOUND
           OR v_location_marked_for_deletion
        THEN
            RAISE EXCEPTION
                'Quotation named trade location does not exist or is inactive.';
        END IF;


        IF
            v_incoterm_named_location_role IN (
                'shipment_port',
                'destination_port'
            )
            AND (
                v_location_function_codes IS NULL
                OR LEFT(
                    v_location_function_codes,
                    1
                ) <> '1'
            )
        THEN
            RAISE EXCEPTION
                'Quotation maritime Incoterm requires a UN/LOCODE maritime-port location.';
        END IF;

    END IF;


    IF NEW.named_organization_site_id IS NOT NULL THEN

        SELECT country_id
        INTO v_site_country_id
        FROM organization_sites
        WHERE
            id = NEW.named_organization_site_id
            AND status = 'active';


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Quotation named organization site does not exist or is inactive.';
        END IF;

    END IF;


    RETURN NEW;

END;
$$;


CREATE OR REPLACE FUNCTION
originhut_prepare_quotation_line()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_quotation RECORD;
    v_product_dimension TEXT;
    v_line_dimension TEXT;
    v_mp_product_id UUID;
    v_packaging_mp_id UUID;
    v_rfq_line RECORD;
    v_offer RECORD;
    v_scenario RECORD;
    v_cost_per_line_uom NUMERIC;
BEGIN

    SELECT
        q.source_rfq_id,
        q.currency_id
    INTO v_quotation
    FROM quotations q
    WHERE q.id =
          NEW.quotation_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Quotation does not exist.';
    END IF;


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
            'Quotation Product does not exist or is inactive.';
    END IF;


    SELECT dimension_code
    INTO v_line_dimension
    FROM units_of_measure
    WHERE
        id = NEW.uom_id
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Quotation line UOM does not exist or is inactive.';
    END IF;


    IF
        v_product_dimension IS NOT NULL
        AND v_line_dimension
            <> v_product_dimension
    THEN
        RAISE EXCEPTION
            'Quotation line UOM dimension must match Product base UOM dimension.';
    END IF;


    IF NEW.manufacturer_product_id IS NOT NULL THEN

        SELECT product_id
        INTO v_mp_product_id
        FROM manufacturer_products
        WHERE
            id = NEW.manufacturer_product_id
            AND status = 'active';


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Quotation Manufacturer Product does not exist or is inactive.';
        END IF;


        IF
            v_mp_product_id
            <> NEW.product_id
        THEN
            RAISE EXCEPTION
                'Quotation Manufacturer Product must belong to the line Product.';
        END IF;

    END IF;


    IF NEW.packaging_configuration_id IS NOT NULL THEN

        IF NEW.manufacturer_product_id IS NULL THEN
            RAISE EXCEPTION
                'Quotation packaging requires a Manufacturer Product.';
        END IF;


        SELECT manufacturer_product_id
        INTO v_packaging_mp_id
        FROM packaging_configurations
        WHERE
            id = NEW.packaging_configuration_id
            AND status = 'active';


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Quotation packaging does not exist or is inactive.';
        END IF;


        IF
            v_packaging_mp_id
            <> NEW.manufacturer_product_id
        THEN
            RAISE EXCEPTION
                'Quotation packaging must belong to the selected Manufacturer Product.';
        END IF;

    END IF;


    IF NEW.source_rfq_line_id IS NOT NULL THEN

        SELECT
            rl.rfq_id,
            rl.product_id,
            rl.manufacturer_product_id,
            rl.packaging_configuration_id
        INTO v_rfq_line
        FROM rfq_lines rl
        WHERE rl.id =
              NEW.source_rfq_line_id;


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Source RFQ line does not exist.';
        END IF;


        IF
            v_quotation.source_rfq_id IS NULL
            OR v_rfq_line.rfq_id
               <> v_quotation.source_rfq_id
        THEN
            RAISE EXCEPTION
                'Source RFQ line must belong to the Quotation source RFQ.';
        END IF;


        IF
            v_rfq_line.product_id
            <> NEW.product_id
        THEN
            RAISE EXCEPTION
                'Quotation Product must match source RFQ line Product.';
        END IF;


        IF
            v_rfq_line.manufacturer_product_id IS NOT NULL
            AND NEW.manufacturer_product_id
                IS DISTINCT FROM
                v_rfq_line.manufacturer_product_id
        THEN
            RAISE EXCEPTION
                'Quotation Manufacturer Product must satisfy the source RFQ line restriction.';
        END IF;


        IF
            v_rfq_line.packaging_configuration_id IS NOT NULL
            AND NEW.packaging_configuration_id
                IS DISTINCT FROM
                v_rfq_line.packaging_configuration_id
        THEN
            RAISE EXCEPTION
                'Quotation packaging must satisfy the source RFQ line restriction.';
        END IF;

    END IF;


    IF NEW.source_commercial_offer_id IS NOT NULL THEN

        SELECT
            co.manufacturer_product_id,
            co.packaging_configuration_id,
            mp.product_id
        INTO v_offer
        FROM commercial_offers co
        JOIN manufacturer_products mp
          ON mp.id =
             co.manufacturer_product_id
        WHERE co.id =
              NEW.source_commercial_offer_id;


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Source Commercial Offer does not exist.';
        END IF;


        IF
            v_offer.product_id
            <> NEW.product_id
        THEN
            RAISE EXCEPTION
                'Source Commercial Offer Product must match Quotation line Product.';
        END IF;


        IF
            NEW.manufacturer_product_id IS NOT NULL
            AND v_offer.manufacturer_product_id
                <> NEW.manufacturer_product_id
        THEN
            RAISE EXCEPTION
                'Source Commercial Offer Manufacturer Product must match Quotation line restriction.';
        END IF;


        IF
            NEW.packaging_configuration_id IS NOT NULL
            AND v_offer.packaging_configuration_id
                IS DISTINCT FROM
                NEW.packaging_configuration_id
        THEN
            RAISE EXCEPTION
                'Source Commercial Offer packaging must match Quotation line restriction.';
        END IF;


        IF
            NEW.source_rfq_line_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM rfq_responses rr
                WHERE
                    rr.rfq_line_id =
                        NEW.source_rfq_line_id
                    AND rr.commercial_offer_id =
                        NEW.source_commercial_offer_id
                    AND rr.status =
                        'submitted'
            )
        THEN
            RAISE EXCEPTION
                'Source Commercial Offer must be a submitted response to the source RFQ line.';
        END IF;

    END IF;


    IF NEW.source_landed_cost_scenario_id IS NOT NULL THEN

        IF NEW.source_commercial_offer_id IS NULL THEN
            RAISE EXCEPTION
                'Source Landed Cost Scenario requires its source Commercial Offer.';
        END IF;


        SELECT
            lcs.commercial_offer_id,
            lcs.scenario_currency_id,
            lcs.target_uom_id,
            lcs.landed_cost_per_target_uom,
            scenario_uom.code
                AS target_uom_code
        INTO v_scenario
        FROM landed_cost_scenarios lcs
        JOIN units_of_measure scenario_uom
          ON scenario_uom.id =
             lcs.target_uom_id
        WHERE
            lcs.id =
                NEW.source_landed_cost_scenario_id
            AND lcs.status =
                'calculated';


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Source Landed Cost Scenario does not exist or is not calculated.';
        END IF;


        IF
            v_scenario.scenario_currency_id
            <> v_quotation.currency_id
        THEN
            RAISE EXCEPTION
                'Landed Cost Scenario currency must match Quotation currency.';
        END IF;


        IF
            NEW.source_commercial_offer_id IS NOT NULL
            AND v_scenario.commercial_offer_id
                <> NEW.source_commercial_offer_id
        THEN
            RAISE EXCEPTION
                'Landed Cost Scenario must belong to the source Commercial Offer.';
        END IF;


        SELECT
            ROUND(
                v_scenario.landed_cost_per_target_uom
                * originhut_convert_uom(
                    1,
                    line_uom.code,
                    v_scenario.target_uom_code
                ),
                12
            )
        INTO v_cost_per_line_uom
        FROM units_of_measure line_uom
        WHERE line_uom.id =
              NEW.uom_id;


        NEW.internal_cost_unit_price :=
            v_cost_per_line_uom;

    END IF;


    IF NEW.pricing_method =
       'markup_percent'
    THEN

        IF
            NEW.internal_cost_unit_price IS NULL
            OR NEW.pricing_rate IS NULL
        THEN
            RAISE EXCEPTION
                'Markup pricing requires internal cost and pricing rate.';
        END IF;


        NEW.quoted_unit_price :=
            ROUND(
                NEW.internal_cost_unit_price
                * (
                    1
                    + NEW.pricing_rate
                      / 100
                ),
                12
            );

    ELSIF NEW.pricing_method =
          'margin_percent'
    THEN

        IF
            NEW.internal_cost_unit_price IS NULL
            OR NEW.pricing_rate IS NULL
            OR NEW.pricing_rate >= 100
        THEN
            RAISE EXCEPTION
                'Margin pricing requires internal cost and rate below 100 percent.';
        END IF;


        NEW.quoted_unit_price :=
            ROUND(
                NEW.internal_cost_unit_price
                / (
                    1
                    - NEW.pricing_rate
                      / 100
                ),
                12
            );

    END IF;


    IF
        NEW.quoted_unit_price IS NULL
        OR NEW.quoted_unit_price <= 0
    THEN
        RAISE EXCEPTION
            'Quotation line requires a positive quoted unit price.';
    END IF;


    NEW.quoted_line_total :=
        ROUND(
            NEW.quantity
            * NEW.quoted_unit_price,
            12
        );


    RETURN NEW;

END;
$$;


CREATE TRIGGER
trg_quotations_validate
BEFORE INSERT OR UPDATE
ON quotations
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_quotation();


CREATE TRIGGER
trg_quotations_updated_at
BEFORE UPDATE
ON quotations
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_quotations_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON quotations
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'quotation',
    'quotation_evidence'
);


CREATE TRIGGER
trg_quotation_lines_prepare
BEFORE INSERT OR UPDATE
ON quotation_lines
FOR EACH ROW
EXECUTE FUNCTION
originhut_prepare_quotation_line();


CREATE TRIGGER
trg_quotation_lines_updated_at
BEFORE UPDATE
ON quotation_lines
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_quotation_lines_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON quotation_lines
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'quotation_line',
    'quotation_line_evidence'
);


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '030',
    'buyer_quotations'
)
ON CONFLICT (version)
DO NOTHING;


COMMIT;
