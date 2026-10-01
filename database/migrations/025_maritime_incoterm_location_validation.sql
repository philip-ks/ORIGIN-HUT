BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 025
-- MARITIME INCOTERM LOCATION VALIDATION
-- ============================================================
--
-- FAS / FOB / CFR / CIF require a named port context.
-- A canonical trade-location reference is not sufficient unless
-- that UN/LOCODE entry actually carries maritime function "1".
-- ============================================================


CREATE OR REPLACE FUNCTION
originhut_validate_commercial_offer_maritime_location()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_named_location_role TEXT;
    v_function_codes TEXT;
    v_marked_for_deletion BOOLEAN;
BEGIN

    SELECT named_location_role
    INTO v_named_location_role
    FROM incoterm_rules
    WHERE
        id = NEW.incoterm_rule_id
        AND is_active = TRUE;


    IF NOT FOUND THEN
        RETURN NEW;
    END IF;


    IF
        v_named_location_role
        NOT IN (
            'shipment_port',
            'destination_port'
        )
    THEN
        RETURN NEW;
    END IF;


    IF NEW.named_trade_location_id IS NULL THEN
        RAISE EXCEPTION
            'Maritime Incoterms require a canonical maritime trade location.';
    END IF;


    SELECT
        function_codes,
        marked_for_deletion
    INTO
        v_function_codes,
        v_marked_for_deletion
    FROM trade_locations
    WHERE id = NEW.named_trade_location_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Named maritime trade location does not exist.';
    END IF;


    IF v_marked_for_deletion THEN
        RAISE EXCEPTION
            'Named maritime trade location is marked for deletion.';
    END IF;


    IF
        v_function_codes IS NULL
        OR LEFT(
            v_function_codes,
            1
        ) <> '1'
    THEN
        RAISE EXCEPTION
            'Named trade location does not carry the UN/LOCODE maritime-port function.';
    END IF;


    RETURN NEW;

END;
$$;


CREATE TRIGGER
trg_commercial_offers_validate_maritime_location
BEFORE INSERT OR UPDATE
ON commercial_offers
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_commercial_offer_maritime_location();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '025',
    'maritime_incoterm_location_validation'
)
ON CONFLICT (version)
DO NOTHING;


COMMIT;
