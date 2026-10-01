BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 026
-- LANDED COST SCENARIOS + COMPONENTS
-- ============================================================
--
-- A Landed Cost Scenario is a derived, reproducible costing view
-- over an immutable Commercial Offer.
--
-- The source offer is never rewritten.
--
-- Components marked included_in_offer are informational breakouts
-- and are NOT added again to the scenario total.
-- ============================================================


CREATE TABLE landed_cost_component_types (

    code TEXT PRIMARY KEY,

    name TEXT NOT NULL,

    category TEXT NOT NULL,

    default_sequence INTEGER NOT NULL,

    is_active BOOLEAN NOT NULL
        DEFAULT TRUE,

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        landed_cost_component_types_code_not_blank
    CHECK (
        BTRIM(code) <> ''
    ),


    CONSTRAINT
        landed_cost_component_types_name_not_blank
    CHECK (
        BTRIM(name) <> ''
    ),


    CONSTRAINT
        landed_cost_component_types_category
    CHECK (
        category IN (
            'offer',
            'origin',
            'main_carriage',
            'destination',
            'border',
            'finance',
            'other'
        )
    ),


    CONSTRAINT
        landed_cost_component_types_sequence_positive
    CHECK (
        default_sequence > 0
    )

);


CREATE TRIGGER
trg_landed_cost_component_types_updated_at
BEFORE UPDATE
ON landed_cost_component_types
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


INSERT INTO landed_cost_component_types (
    code,
    name,
    category,
    default_sequence
)
VALUES
    (
        'goods',
        'Goods value',
        'offer',
        10
    ),
    (
        'origin_inland',
        'Origin inland transport',
        'origin',
        20
    ),
    (
        'origin_handling',
        'Origin handling',
        'origin',
        30
    ),
    (
        'export_clearance',
        'Export clearance',
        'origin',
        40
    ),
    (
        'main_carriage',
        'Main carriage / freight',
        'main_carriage',
        50
    ),
    (
        'insurance',
        'Insurance',
        'main_carriage',
        60
    ),
    (
        'destination_handling',
        'Destination handling',
        'destination',
        70
    ),
    (
        'customs_broker',
        'Customs broker / clearance',
        'border',
        80
    ),
    (
        'import_duty',
        'Import duty',
        'border',
        90
    ),
    (
        'import_tax',
        'Import tax',
        'border',
        100
    ),
    (
        'destination_inland',
        'Destination inland transport',
        'destination',
        110
    ),
    (
        'finance',
        'Finance cost',
        'finance',
        120
    ),
    (
        'other',
        'Other documented cost',
        'other',
        999
    )
ON CONFLICT (code)
DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    default_sequence = EXCLUDED.default_sequence,
    is_active = TRUE;


CREATE TABLE landed_cost_scenarios (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    commercial_offer_id UUID NOT NULL
        REFERENCES commercial_offers(id)
        ON DELETE RESTRICT,

    scenario_reference TEXT,

    status TEXT NOT NULL
        DEFAULT 'draft',

    target_quantity NUMERIC(30,12) NOT NULL,

    target_uom_id UUID NOT NULL
        REFERENCES units_of_measure(id)
        ON DELETE RESTRICT,

    scenario_currency_id UUID NOT NULL
        REFERENCES currencies(id)
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

    offer_fx_rate_to_scenario NUMERIC(30,12),

    offer_fx_rate_date DATE,

    offer_fx_source TEXT,

    offer_amount_source_currency NUMERIC(30,12)
        NOT NULL
        DEFAULT 0,

    offer_amount_scenario_currency NUMERIC(30,12)
        NOT NULL
        DEFAULT 0,

    included_component_total_scenario_currency NUMERIC(30,12)
        NOT NULL
        DEFAULT 0,

    added_component_total_scenario_currency NUMERIC(30,12)
        NOT NULL
        DEFAULT 0,

    landed_cost_total_scenario_currency NUMERIC(30,12)
        NOT NULL
        DEFAULT 0,

    landed_cost_per_target_uom NUMERIC(30,12)
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

    calculated_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        landed_cost_scenarios_reference_not_blank
    CHECK (
        scenario_reference IS NULL
        OR BTRIM(scenario_reference) <> ''
    ),


    CONSTRAINT
        landed_cost_scenarios_status
    CHECK (
        status IN (
            'draft',
            'calculated',
            'archived'
        )
    ),


    CONSTRAINT
        landed_cost_scenarios_target_quantity_positive
    CHECK (
        target_quantity > 0
    ),


    CONSTRAINT
        landed_cost_scenarios_destination_required
    CHECK (
        destination_trade_location_id IS NOT NULL
        OR destination_organization_site_id IS NOT NULL
        OR destination_place_text IS NOT NULL
    ),


    CONSTRAINT
        landed_cost_scenarios_destination_text_not_blank
    CHECK (
        destination_place_text IS NULL
        OR BTRIM(destination_place_text) <> ''
    ),


    CONSTRAINT
        landed_cost_scenarios_fx_rate_positive
    CHECK (
        offer_fx_rate_to_scenario IS NULL
        OR offer_fx_rate_to_scenario > 0
    ),


    CONSTRAINT
        landed_cost_scenarios_fx_source_not_blank
    CHECK (
        offer_fx_source IS NULL
        OR BTRIM(offer_fx_source) <> ''
    ),


    CONSTRAINT
        landed_cost_scenarios_notes_not_blank
    CHECK (
        notes IS NULL
        OR BTRIM(notes) <> ''
    ),


    CONSTRAINT
        landed_cost_scenarios_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        landed_cost_scenarios_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

);


CREATE UNIQUE INDEX
landed_cost_scenarios_offer_reference_unique
ON landed_cost_scenarios (
    commercial_offer_id,
    scenario_reference
)
WHERE scenario_reference IS NOT NULL;


CREATE INDEX
idx_landed_cost_scenarios_offer
ON landed_cost_scenarios (
    commercial_offer_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_landed_cost_scenarios_destination
ON landed_cost_scenarios (
    destination_country_id,
    status,
    updated_at DESC
);


CREATE INDEX
idx_landed_cost_scenarios_source_record
ON landed_cost_scenarios (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_landed_cost_scenarios_metadata_gin
ON landed_cost_scenarios
USING GIN (
    metadata
);


CREATE TABLE landed_cost_components (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    scenario_id UUID NOT NULL
        REFERENCES landed_cost_scenarios(id)
        ON DELETE CASCADE,

    component_type_code TEXT NOT NULL
        REFERENCES landed_cost_component_types(code)
        ON DELETE RESTRICT,

    sequence INTEGER NOT NULL,

    description TEXT,

    included_in_offer BOOLEAN NOT NULL
        DEFAULT FALSE,

    calculation_method TEXT NOT NULL
        DEFAULT 'fixed_amount',

    source_amount NUMERIC(30,12),

    source_currency_id UUID
        REFERENCES currencies(id)
        ON DELETE RESTRICT,

    exchange_rate_to_scenario NUMERIC(30,12),

    percentage_rate NUMERIC(18,8),

    taxable_base_scenario_currency NUMERIC(30,12),

    amount_scenario_currency NUMERIC(30,12) NOT NULL
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
        landed_cost_components_sequence_positive
    CHECK (
        sequence > 0
    ),


    CONSTRAINT
        landed_cost_components_description_not_blank
    CHECK (
        description IS NULL
        OR BTRIM(description) <> ''
    ),


    CONSTRAINT
        landed_cost_components_calculation_method
    CHECK (
        calculation_method IN (
            'fixed_amount',
            'percentage'
        )
    ),


    CONSTRAINT
        landed_cost_components_fixed_shape
    CHECK (
        calculation_method <> 'fixed_amount'
        OR (
            source_amount IS NOT NULL
            AND source_amount >= 0
            AND source_currency_id IS NOT NULL
            AND exchange_rate_to_scenario IS NOT NULL
            AND exchange_rate_to_scenario > 0
            AND percentage_rate IS NULL
            AND taxable_base_scenario_currency IS NULL
        )
    ),


    CONSTRAINT
        landed_cost_components_percentage_shape
    CHECK (
        calculation_method <> 'percentage'
        OR (
            source_amount IS NULL
            AND source_currency_id IS NULL
            AND exchange_rate_to_scenario IS NULL
            AND percentage_rate IS NOT NULL
            AND percentage_rate >= 0
            AND percentage_rate <= 100
            AND taxable_base_scenario_currency IS NOT NULL
            AND taxable_base_scenario_currency >= 0
        )
    ),


    CONSTRAINT
        landed_cost_components_notes_not_blank
    CHECK (
        notes IS NULL
        OR BTRIM(notes) <> ''
    ),


    CONSTRAINT
        landed_cost_components_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        landed_cost_components_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    )

);


CREATE INDEX
idx_landed_cost_components_scenario
ON landed_cost_components (
    scenario_id,
    sequence,
    component_type_code
);


CREATE INDEX
idx_landed_cost_components_type
ON landed_cost_components (
    component_type_code,
    included_in_offer
);


CREATE INDEX
idx_landed_cost_components_source_record
ON landed_cost_components (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_landed_cost_components_metadata_gin
ON landed_cost_components
USING GIN (
    metadata
);


CREATE OR REPLACE FUNCTION
originhut_prepare_landed_cost_scenario()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_offer RECORD;
    v_target_dimension TEXT;
    v_price_dimension TEXT;
    v_destination_country_id UUID;
    v_site_country_id UUID;
    v_quantity_in_price_uom NUMERIC;
BEGIN

    SELECT
        co.unit_price,
        co.currency_id,
        co.price_uom_id,
        p.base_uom_id
    INTO v_offer
    FROM commercial_offers co
    JOIN manufacturer_products mp
      ON mp.id = co.manufacturer_product_id
    JOIN products p
      ON p.id = mp.product_id
    WHERE co.id =
          NEW.commercial_offer_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Commercial Offer does not exist.';
    END IF;


    SELECT dimension_code
    INTO v_target_dimension
    FROM units_of_measure
    WHERE
        id = NEW.target_uom_id
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Target UOM does not exist or is inactive.';
    END IF;


    SELECT dimension_code
    INTO v_price_dimension
    FROM units_of_measure
    WHERE
        id = v_offer.price_uom_id
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Commercial Offer price UOM does not exist or is inactive.';
    END IF;


    IF v_target_dimension <> v_price_dimension THEN
        RAISE EXCEPTION
            'Target quantity UOM dimension must match Commercial Offer price UOM dimension.';
    END IF;


    IF NEW.destination_trade_location_id IS NOT NULL THEN

        SELECT country_id
        INTO v_destination_country_id
        FROM trade_locations
        WHERE
            id = NEW.destination_trade_location_id
            AND marked_for_deletion = FALSE;


        IF NOT FOUND THEN
            RAISE EXCEPTION
                'Destination trade location does not exist or is inactive.';
        END IF;


        IF
            v_destination_country_id
            <> NEW.destination_country_id
        THEN
            RAISE EXCEPTION
                'Destination trade location country must match scenario destination country.';
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
                'Destination organization site does not exist or is inactive.';
        END IF;


        IF
            v_site_country_id IS NOT NULL
            AND v_site_country_id
                <> NEW.destination_country_id
        THEN
            RAISE EXCEPTION
                'Destination organization site country must match scenario destination country.';
        END IF;

    END IF;


    IF
        v_offer.currency_id =
        NEW.scenario_currency_id
    THEN

        NEW.offer_fx_rate_to_scenario :=
            1;

        IF NEW.offer_fx_source IS NULL THEN
            NEW.offer_fx_source :=
                'same_currency';
        END IF;

    ELSE

        IF
            NEW.offer_fx_rate_to_scenario IS NULL
            OR NEW.offer_fx_rate_date IS NULL
            OR NEW.offer_fx_source IS NULL
        THEN
            RAISE EXCEPTION
                'Cross-currency scenario requires offer FX rate, date and source.';
        END IF;

    END IF;


    SELECT originhut_convert_uom(
        NEW.target_quantity,
        target.code,
        price.code
    )
    INTO v_quantity_in_price_uom
    FROM units_of_measure target
    CROSS JOIN units_of_measure price
    WHERE
        target.id = NEW.target_uom_id
        AND price.id = v_offer.price_uom_id;


    NEW.offer_amount_source_currency :=
        ROUND(
            v_offer.unit_price
            * v_quantity_in_price_uom,
            12
        );


    NEW.offer_amount_scenario_currency :=
        ROUND(
            NEW.offer_amount_source_currency
            * NEW.offer_fx_rate_to_scenario,
            12
        );


    RETURN NEW;

END;
$$;


CREATE OR REPLACE FUNCTION
originhut_prepare_landed_cost_component()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_scenario_currency_id UUID;
BEGIN

    SELECT scenario_currency_id
    INTO v_scenario_currency_id
    FROM landed_cost_scenarios
    WHERE id =
          NEW.scenario_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Landed Cost Scenario does not exist.';
    END IF;


    IF NEW.calculation_method =
       'fixed_amount'
    THEN

        IF
            NEW.source_currency_id =
            v_scenario_currency_id
        THEN
            NEW.exchange_rate_to_scenario :=
                1;
        END IF;


        NEW.amount_scenario_currency :=
            ROUND(
                NEW.source_amount
                * NEW.exchange_rate_to_scenario,
                12
            );

    ELSE

        NEW.amount_scenario_currency :=
            ROUND(
                NEW.taxable_base_scenario_currency
                * NEW.percentage_rate
                / 100,
                12
            );

    END IF;


    RETURN NEW;

END;
$$;


CREATE OR REPLACE FUNCTION
originhut_refresh_landed_cost_scenario(
    p_scenario_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_included NUMERIC;
    v_added NUMERIC;
BEGIN

    SELECT
        COALESCE(
            SUM(
                amount_scenario_currency
            ) FILTER (
                WHERE included_in_offer
            ),
            0
        ),
        COALESCE(
            SUM(
                amount_scenario_currency
            ) FILTER (
                WHERE NOT included_in_offer
            ),
            0
        )
    INTO
        v_included,
        v_added
    FROM landed_cost_components
    WHERE scenario_id =
          p_scenario_id;


    UPDATE landed_cost_scenarios
    SET
        included_component_total_scenario_currency =
            v_included,

        added_component_total_scenario_currency =
            v_added,

        landed_cost_total_scenario_currency =
            offer_amount_scenario_currency
            + v_added,

        landed_cost_per_target_uom =
            (
                offer_amount_scenario_currency
                + v_added
            )
            / target_quantity,

        calculated_at =
            NOW()

    WHERE id =
          p_scenario_id;

END;
$$;


CREATE OR REPLACE FUNCTION
originhut_refresh_landed_cost_after_component()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    IF TG_OP = 'DELETE' THEN

        PERFORM
            originhut_refresh_landed_cost_scenario(
                OLD.scenario_id
            );

        RETURN OLD;

    END IF;


    PERFORM
        originhut_refresh_landed_cost_scenario(
            NEW.scenario_id
        );


    IF
        TG_OP = 'UPDATE'
        AND OLD.scenario_id
            <> NEW.scenario_id
    THEN

        PERFORM
            originhut_refresh_landed_cost_scenario(
                OLD.scenario_id
            );

    END IF;


    RETURN NEW;

END;
$$;


CREATE OR REPLACE FUNCTION
originhut_refresh_landed_cost_after_scenario()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    NEW.included_component_total_scenario_currency :=
        0;

    NEW.added_component_total_scenario_currency :=
        0;

    NEW.landed_cost_total_scenario_currency :=
        NEW.offer_amount_scenario_currency;

    NEW.landed_cost_per_target_uom :=
        NEW.offer_amount_scenario_currency
        / NEW.target_quantity;

    NEW.calculated_at :=
        NOW();


    RETURN NEW;

END;
$$;


CREATE TRIGGER
trg_landed_cost_scenarios_prepare
BEFORE INSERT OR UPDATE OF
    commercial_offer_id,
    target_quantity,
    target_uom_id,
    scenario_currency_id,
    destination_country_id,
    destination_trade_location_id,
    destination_organization_site_id,
    offer_fx_rate_to_scenario,
    offer_fx_rate_date,
    offer_fx_source
ON landed_cost_scenarios
FOR EACH ROW
EXECUTE FUNCTION
originhut_prepare_landed_cost_scenario();


CREATE TRIGGER
trg_landed_cost_scenarios_initialize_totals
BEFORE INSERT
ON landed_cost_scenarios
FOR EACH ROW
EXECUTE FUNCTION
originhut_refresh_landed_cost_after_scenario();


CREATE TRIGGER
trg_landed_cost_scenarios_updated_at
BEFORE UPDATE
ON landed_cost_scenarios
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_landed_cost_scenarios_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON landed_cost_scenarios
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'landed_cost_scenario',
    'scenario_evidence'
);


CREATE TRIGGER
trg_landed_cost_components_prepare
BEFORE INSERT OR UPDATE
ON landed_cost_components
FOR EACH ROW
EXECUTE FUNCTION
originhut_prepare_landed_cost_component();


CREATE TRIGGER
trg_landed_cost_components_updated_at
BEFORE UPDATE
ON landed_cost_components
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_landed_cost_components_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON landed_cost_components
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'landed_cost_component',
    'cost_evidence'
);


CREATE TRIGGER
trg_landed_cost_components_refresh_scenario
AFTER INSERT OR UPDATE OR DELETE
ON landed_cost_components
FOR EACH ROW
EXECUTE FUNCTION
originhut_refresh_landed_cost_after_component();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '026',
    'landed_cost_scenarios_and_components'
)
ON CONFLICT (version)
DO NOTHING;


COMMIT;
