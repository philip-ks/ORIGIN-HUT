from __future__ import annotations

import os
import unittest

import psycopg


RUN_DATABASE_INTEGRATION = (
    os.environ.get(
        "ORIGINHUT_RUN_DB_INTEGRATION"
    )
    == "1"
)


@unittest.skipUnless(
    RUN_DATABASE_INTEGRATION,
    "Database integration tests are disabled.",
)
class LandedCostPostgresIntegrationTest(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        database_url = os.environ[
            "DATABASE_URL"
        ]

        with psycopg.connect(
            database_url
        ) as connection:

            database_name = connection.execute(
                "SELECT current_database()"
            ).fetchone()[0]

            if "test" not in database_name.lower():
                raise RuntimeError(
                    "Refusing to run landed-cost tests "
                    "against a non-test database."
                )

            self._cleanup(
                connection
            )

            connection.execute(
                """
                INSERT INTO countries (
                    iso2,
                    iso3,
                    numeric_code,
                    name,
                    official_name,
                    is_active
                )
                VALUES
                    (
                        'IN',
                        'IND',
                        '356',
                        'India',
                        'Republic of India',
                        TRUE
                    ),
                    (
                        'AE',
                        'ARE',
                        '784',
                        'United Arab Emirates',
                        'United Arab Emirates',
                        TRUE
                    )
                ON CONFLICT (iso2)
                DO UPDATE SET
                    is_active = TRUE
                """
            )

            connection.execute(
                """
                INSERT INTO currencies (
                    code,
                    numeric_code,
                    name,
                    decimal_places,
                    is_active
                )
                VALUES
                    (
                        'USD',
                        '840',
                        'US Dollar',
                        2,
                        TRUE
                    ),
                    (
                        'AED',
                        '784',
                        'UAE Dirham',
                        2,
                        TRUE
                    )
                ON CONFLICT (code)
                DO UPDATE SET
                    is_active = TRUE
                """
            )

            connection.execute(
                """
                INSERT INTO trade_locations (
                    unlocode,
                    country_id,
                    country_code,
                    location_code,
                    name,
                    function_codes,
                    status,
                    marked_for_deletion
                )
                SELECT
                    'AEJEA',
                    c.id,
                    'AE',
                    'JEA',
                    'Jebel Ali',
                    '1-------',
                    'AA',
                    FALSE
                FROM countries c
                WHERE c.iso2 = 'AE'
                ON CONFLICT (unlocode)
                DO UPDATE SET
                    country_id = EXCLUDED.country_id,
                    country_code = EXCLUDED.country_code,
                    location_code = EXCLUDED.location_code,
                    name = EXCLUDED.name,
                    function_codes = EXCLUDED.function_codes,
                    marked_for_deletion = FALSE
                """
            )


    def tearDown(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:
            self._cleanup(
                connection
            )


    def _cleanup(
        self,
        connection: psycopg.Connection,
    ) -> None:

        connection.execute(
            """
            DELETE FROM landed_cost_scenarios
            WHERE commercial_offer_id IN (
                SELECT co.id
                FROM commercial_offers co
                JOIN manufacturer_products mp
                  ON mp.id =
                     co.manufacturer_product_id
                JOIN products p
                  ON p.id =
                     mp.product_id
                WHERE p.name LIKE
                    'OH17 Landed Cost Test%'
            )
            """
        )

        connection.execute(
            """
            DELETE FROM commercial_offers
            WHERE manufacturer_product_id IN (
                SELECT mp.id
                FROM manufacturer_products mp
                JOIN products p
                  ON p.id =
                     mp.product_id
                WHERE p.name LIKE
                    'OH17 Landed Cost Test%'
            )
            """
        )

        connection.execute(
            """
            DELETE FROM products
            WHERE name LIKE
                'OH17 Landed Cost Test%'
            """
        )

        connection.execute(
            """
            DELETE FROM organizations
            WHERE legal_name LIKE
                'OH17 Landed Cost Test%'
            """
        )


    def _seed_offer(
        self,
        connection: psycopg.Connection,
        suffix: str,
    ) -> str:

        seller_id = connection.execute(
            """
            INSERT INTO organizations (
                legal_name,
                country_id,
                status
            )
            SELECT
                %s,
                c.id,
                'active'
            FROM countries c
            WHERE c.iso2 = 'IN'
            RETURNING id
            """,
            (
                "OH17 Landed Cost Test Seller "
                + suffix,
            ),
        ).fetchone()[0]

        manufacturer_id = connection.execute(
            """
            INSERT INTO organizations (
                legal_name,
                country_id,
                status
            )
            SELECT
                %s,
                c.id,
                'active'
            FROM countries c
            WHERE c.iso2 = 'IN'
            RETURNING id
            """,
            (
                "OH17 Landed Cost Test Manufacturer "
                + suffix,
            ),
        ).fetchone()[0]

        connection.execute(
            """
            INSERT INTO organization_roles (
                organization_id,
                role_code
            )
            VALUES (
                %s,
                'manufacturer'
            )
            """,
            (
                manufacturer_id,
            ),
        )

        product_id = connection.execute(
            """
            INSERT INTO products (
                name,
                description,
                base_uom_id
            )
            SELECT
                %s,
                'OH17 landed-cost test product.',
                u.id
            FROM units_of_measure u
            WHERE u.code = 'KGM'
            RETURNING id
            """,
            (
                "OH17 Landed Cost Test Product "
                + suffix,
            ),
        ).fetchone()[0]

        manufacturer_product_id = connection.execute(
            """
            INSERT INTO manufacturer_products (
                product_id,
                manufacturer_id,
                name,
                status
            )
            VALUES (
                %s,
                %s,
                %s,
                'active'
            )
            RETURNING id
            """,
            (
                product_id,
                manufacturer_id,
                (
                    "OH17 Landed Cost Test Grade "
                    + suffix
                ),
            ),
        ).fetchone()[0]

        offer_id = connection.execute(
            """
            INSERT INTO commercial_offers (
                seller_organization_id,
                manufacturer_product_id,
                status,
                unit_price,
                currency_id,
                price_uom_id,
                incoterm_rule_id,
                named_place_text,
                named_trade_location_id
            )
            SELECT
                %s,
                %s,
                'active',
                1150,
                currency.id,
                u.id,
                incoterm.id,
                'Jebel Ali, UAE',
                location.id
            FROM currencies currency
            CROSS JOIN units_of_measure u
            CROSS JOIN incoterm_rules incoterm
            CROSS JOIN trade_locations location
            WHERE
                currency.code = 'USD'
                AND u.code = 'TNE'
                AND incoterm.edition = 2020
                AND incoterm.code = 'CIF'
                AND location.unlocode = 'AEJEA'
            RETURNING id
            """,
            (
                seller_id,
                manufacturer_product_id,
            ),
        ).fetchone()[0]

        return str(
            offer_id
        )


    def _create_scenario(
        self,
        connection: psycopg.Connection,
        offer_id: str,
        suffix: str,
    ) -> str:

        scenario_id = connection.execute(
            """
            INSERT INTO landed_cost_scenarios (
                commercial_offer_id,
                scenario_reference,
                status,
                target_quantity,
                target_uom_id,
                scenario_currency_id,
                destination_country_id,
                destination_trade_location_id
            )
            SELECT
                %s,
                %s,
                'calculated',
                20,
                u.id,
                currency.id,
                country.id,
                location.id
            FROM units_of_measure u
            CROSS JOIN currencies currency
            CROSS JOIN countries country
            CROSS JOIN trade_locations location
            WHERE
                u.code = 'TNE'
                AND currency.code = 'USD'
                AND country.iso2 = 'AE'
                AND location.unlocode = 'AEJEA'
            RETURNING id
            """,
            (
                offer_id,
                "OH17-" + suffix,
            ),
        ).fetchone()[0]

        return str(
            scenario_id
        )


    def test_scenario_starts_from_offer_amount(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            offer_id = self._seed_offer(
                connection,
                "BASE",
            )

            scenario_id = self._create_scenario(
                connection,
                offer_id,
                "BASE",
            )

            row = connection.execute(
                """
                SELECT
                    offer_amount_source_currency::double precision,
                    offer_amount_scenario_currency::double precision,
                    added_component_total_scenario_currency::double precision,
                    landed_cost_total_scenario_currency::double precision,
                    landed_cost_per_target_uom::double precision,
                    offer_fx_rate_to_scenario::double precision
                FROM landed_cost_scenarios
                WHERE id = %s
                """,
                (
                    scenario_id,
                ),
            ).fetchone()

            self.assertEqual(
                row[0],
                23000.0,
            )

            self.assertEqual(
                row[1],
                23000.0,
            )

            self.assertEqual(
                row[2],
                0.0,
            )

            self.assertEqual(
                row[3],
                23000.0,
            )

            self.assertEqual(
                row[4],
                1150.0,
            )

            self.assertEqual(
                row[5],
                1.0,
            )


    def test_included_components_do_not_double_count(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            offer_id = self._seed_offer(
                connection,
                "INCLUDED",
            )

            scenario_id = self._create_scenario(
                connection,
                offer_id,
                "INCLUDED",
            )

            currency_id = connection.execute(
                """
                SELECT id
                FROM currencies
                WHERE code = 'USD'
                """
            ).fetchone()[0]

            connection.execute(
                """
                INSERT INTO landed_cost_components (
                    scenario_id,
                    component_type_code,
                    sequence,
                    description,
                    included_in_offer,
                    calculation_method,
                    source_amount,
                    source_currency_id,
                    exchange_rate_to_scenario
                )
                VALUES (
                    %s,
                    'insurance',
                    60,
                    'CIF insurance breakout',
                    TRUE,
                    'fixed_amount',
                    500,
                    %s,
                    1
                )
                """,
                (
                    scenario_id,
                    currency_id,
                ),
            )

            row = connection.execute(
                """
                SELECT
                    included_component_total_scenario_currency::double precision,
                    added_component_total_scenario_currency::double precision,
                    landed_cost_total_scenario_currency::double precision
                FROM landed_cost_scenarios
                WHERE id = %s
                """,
                (
                    scenario_id,
                ),
            ).fetchone()

            self.assertEqual(
                row[0],
                500.0,
            )

            self.assertEqual(
                row[1],
                0.0,
            )

            self.assertEqual(
                row[2],
                23000.0,
            )


    def test_added_and_percentage_components_refresh_totals(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            offer_id = self._seed_offer(
                connection,
                "ADDED",
            )

            scenario_id = self._create_scenario(
                connection,
                offer_id,
                "ADDED",
            )

            currency_id = connection.execute(
                """
                SELECT id
                FROM currencies
                WHERE code = 'USD'
                """
            ).fetchone()[0]

            connection.execute(
                """
                INSERT INTO landed_cost_components (
                    scenario_id,
                    component_type_code,
                    sequence,
                    description,
                    included_in_offer,
                    calculation_method,
                    source_amount,
                    source_currency_id,
                    exchange_rate_to_scenario
                )
                VALUES (
                    %s,
                    'destination_handling',
                    70,
                    'Destination handling',
                    FALSE,
                    'fixed_amount',
                    600,
                    %s,
                    1
                )
                """,
                (
                    scenario_id,
                    currency_id,
                ),
            )

            connection.execute(
                """
                INSERT INTO landed_cost_components (
                    scenario_id,
                    component_type_code,
                    sequence,
                    description,
                    included_in_offer,
                    calculation_method,
                    percentage_rate,
                    taxable_base_scenario_currency
                )
                VALUES (
                    %s,
                    'import_duty',
                    90,
                    'Synthetic proof duty',
                    FALSE,
                    'percentage',
                    5,
                    23600
                )
                """,
                (
                    scenario_id,
                ),
            )

            row = connection.execute(
                """
                SELECT
                    added_component_total_scenario_currency::double precision,
                    landed_cost_total_scenario_currency::double precision,
                    landed_cost_per_target_uom::double precision
                FROM landed_cost_scenarios
                WHERE id = %s
                """,
                (
                    scenario_id,
                ),
            ).fetchone()

            self.assertEqual(
                row[0],
                1780.0,
            )

            self.assertEqual(
                row[1],
                24780.0,
            )

            self.assertEqual(
                row[2],
                1239.0,
            )


    def test_target_uom_must_match_offer_dimension(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            offer_id = self._seed_offer(
                connection,
                "DIMENSION",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO landed_cost_scenarios (
                            commercial_offer_id,
                            target_quantity,
                            target_uom_id,
                            scenario_currency_id,
                            destination_country_id,
                            destination_place_text
                        )
                        SELECT
                            %s,
                            20,
                            u.id,
                            currency.id,
                            country.id,
                            'Dubai, UAE'
                        FROM units_of_measure u
                        CROSS JOIN currencies currency
                        CROSS JOIN countries country
                        WHERE
                            u.code = 'LTR'
                            AND currency.code = 'USD'
                            AND country.iso2 = 'AE'
                        """,
                        (
                            offer_id,
                        ),
                    )


    def test_cross_currency_scenario_requires_fx_provenance(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            offer_id = self._seed_offer(
                connection,
                "FX",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO landed_cost_scenarios (
                            commercial_offer_id,
                            target_quantity,
                            target_uom_id,
                            scenario_currency_id,
                            destination_country_id,
                            destination_place_text,
                            offer_fx_rate_to_scenario
                        )
                        SELECT
                            %s,
                            20,
                            u.id,
                            currency.id,
                            country.id,
                            'Dubai, UAE',
                            3.67
                        FROM units_of_measure u
                        CROSS JOIN currencies currency
                        CROSS JOIN countries country
                        WHERE
                            u.code = 'TNE'
                            AND currency.code = 'AED'
                            AND country.iso2 = 'AE'
                        """,
                        (
                            offer_id,
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
