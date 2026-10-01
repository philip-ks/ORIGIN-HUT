BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 029
-- RFQ RESPONSE COMPARISON READ MODEL
-- ============================================================
--
-- Comparison is derived from source RFQ demand, supplier Commercial
-- Offers and matching Landed Cost Scenarios.
--
-- No FX, duty, freight or other missing assumptions are fabricated.
-- ============================================================


CREATE VIEW rfq_response_comparison
AS
SELECT
    rr.id
        AS rfq_response_id,

    rr.rfq_id,

    rr.rfq_line_id,

    rl.line_number,

    r.buyer_organization_id,

    rr.rfq_supplier_id,

    rs.supplier_organization_id,

    rr.commercial_offer_id,

    rl.product_id,

    rl.manufacturer_product_id
        AS requested_manufacturer_product_id,

    rl.packaging_configuration_id
        AS requested_packaging_configuration_id,

    rl.requested_quantity,

    rl.requested_uom_id,

    requested_uom.code
        AS requested_uom_code,

    r.requested_currency_id,

    requested_currency.code
        AS requested_currency_code,

    co.unit_price,

    co.currency_id
        AS offer_currency_id,

    offer_currency.code
        AS offer_currency_code,

    co.price_uom_id
        AS offer_price_uom_id,

    offer_price_uom.code
        AS offer_price_uom_code,

    co.minimum_order_quantity,

    co.minimum_order_uom_id,

    co.lead_time_days,

    co.payment_terms,

    incoterm.edition
        AS incoterm_edition,

    incoterm.code
        AS incoterm_code,

    co.named_place_text,

    offer_location.unlocode
        AS offer_named_trade_location_unlocode,

    ROUND(
        co.unit_price
        * originhut_convert_uom(
            1,
            requested_uom.code,
            offer_price_uom.code
        ),
        12
    )
        AS offer_price_per_requested_uom_offer_currency,

    scenario.id
        AS landed_cost_scenario_id,

    scenario.scenario_currency_code,

    scenario.target_quantity
        AS landed_cost_target_quantity,

    scenario.target_uom_code
        AS landed_cost_target_uom_code,

    scenario.landed_cost_total,

    scenario.landed_cost_per_target_uom,

    CASE
        WHEN scenario.id IS NULL
        THEN NULL
        ELSE ROUND(
            scenario.landed_cost_per_target_uom
            * originhut_convert_uom(
                1,
                requested_uom.code,
                scenario.target_uom_code
            ),
            12
        )
    END
        AS landed_cost_per_requested_uom,

    (
        scenario.id IS NOT NULL
    )
        AS is_comparable,

    CASE
        WHEN r.requested_currency_id IS NULL
        THEN
            'rfq_currency_not_specified'

        WHEN scenario.id IS NULL
        THEN
            'no_matching_landed_cost_scenario'

        ELSE
            'comparable'
    END
        AS comparison_reason

FROM rfq_responses rr

JOIN rfqs r
  ON r.id =
     rr.rfq_id

JOIN rfq_lines rl
  ON rl.id =
     rr.rfq_line_id

JOIN rfq_suppliers rs
  ON rs.id =
     rr.rfq_supplier_id

JOIN commercial_offers co
  ON co.id =
     rr.commercial_offer_id

JOIN units_of_measure requested_uom
  ON requested_uom.id =
     rl.requested_uom_id

LEFT JOIN currencies requested_currency
  ON requested_currency.id =
     r.requested_currency_id

JOIN currencies offer_currency
  ON offer_currency.id =
     co.currency_id

JOIN units_of_measure offer_price_uom
  ON offer_price_uom.id =
     co.price_uom_id

JOIN incoterm_rules incoterm
  ON incoterm.id =
     co.incoterm_rule_id

LEFT JOIN trade_locations offer_location
  ON offer_location.id =
     co.named_trade_location_id

LEFT JOIN LATERAL (

    SELECT
        lcs.id,

        scenario_currency.code
            AS scenario_currency_code,

        lcs.target_quantity,

        scenario_uom.code
            AS target_uom_code,

        lcs.landed_cost_total_scenario_currency
            AS landed_cost_total,

        lcs.landed_cost_per_target_uom,

        lcs.calculated_at,

        lcs.updated_at

    FROM landed_cost_scenarios lcs

    JOIN currencies scenario_currency
      ON scenario_currency.id =
         lcs.scenario_currency_id

    JOIN units_of_measure scenario_uom
      ON scenario_uom.id =
         lcs.target_uom_id

    WHERE
        lcs.commercial_offer_id =
            rr.commercial_offer_id

        AND lcs.status =
            'calculated'

        AND r.requested_currency_id
            IS NOT NULL

        AND lcs.scenario_currency_id =
            r.requested_currency_id

        AND lcs.destination_country_id =
            r.destination_country_id

        AND ABS(
            originhut_convert_uom(
                lcs.target_quantity,
                scenario_uom.code,
                requested_uom.code
            )
            - rl.requested_quantity
        ) <= 0.000001

    ORDER BY
        lcs.calculated_at DESC
            NULLS LAST,
        lcs.updated_at DESC,
        lcs.id

    LIMIT 1

) scenario
ON TRUE

WHERE rr.status =
      'submitted';


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '029',
    'rfq_response_comparison_read_model'
)
ON CONFLICT (version)
DO NOTHING;


COMMIT;
