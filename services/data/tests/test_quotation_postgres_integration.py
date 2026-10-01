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
class QuotationPostgresIntegrationTest(
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
                    "Refusing to run quotation tests against a non-test database."
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
                VALUES (
                    'USD',
                    '840',
                    'US Dollar',
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
            DELETE FROM quotations
            WHERE quotation_reference LIKE
                'OH18-QUOTE-TEST-%'
            """
        )

        connection.execute(
            """
            DELETE FROM rfqs
            WHERE rfq_reference LIKE
                'OH18-QUOTE-RFQ-%'
            """
        )

        connection.execute(
            """
            DELETE FROM landed_cost_scenarios
            WHERE commercial_offer_id IN (
                SELECT id
                FROM commercial_offers
                WHERE offer_reference LIKE
                    'OH18-QUOTE-OFFER-%'
            )
            """
        )

        connection.execute(
            """
            DELETE FROM commercial_offers
            WHERE offer_reference LIKE
                'OH18-QUOTE-OFFER-%'
            """
        )

        connection.execute(
            """
            DELETE FROM products
            WHERE name LIKE
                'OH18 Quote Test Product%'
            """
        )

        connection.execute(
            """
            DELETE FROM organizations
            WHERE legal_name LIKE
                'OH18 Quote Test%'
            """
        )


    def _seed(
        self,
        connection: psycopg.Connection,
        suffix: str,
    ) -> dict[str, str]:

        def organization(
            name: str,
            country: str,
        ) -> str:

            return str(
                connection.execute(
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
                    WHERE c.iso2 = %s
                    RETURNING id
                    """,
                    (
                        name,
                        country,
                    ),
                ).fetchone()[0]
            )

        issuer_id = organization(
            "OH18 Quote Test Issuer "
            + suffix,
            "IN",
        )

        customer_id = organization(
            "OH18 Quote Test Customer "
            + suffix,
            "AE",
        )

        supplier_id = organization(
            "OH18 Quote Test Supplier "
            + suffix,
            "IN",
        )

        manufacturer_id = organization(
            "OH18 Quote Test Manufacturer "
            + suffix,
            "IN",
        )

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

        product_id = str(
            connection.execute(
                """
                INSERT INTO products (
                    name,
                    description,
                    base_uom_id
                )
                SELECT
                    %s,
                    'OH18 quotation test Product.',
                    u.id
                FROM units_of_measure u
                WHERE u.code = 'KGM'
                RETURNING id
                """,
                (
                    "OH18 Quote Test Product "
                    + suffix,
                ),
            ).fetchone()[0]
        )

        manufacturer_product_id = str(
            connection.execute(
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
                        "OH18 Quote Test Grade "
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )

        packaging_id = str(
            connection.execute(
                """
                INSERT INTO packaging_configurations (
                    manufacturer_product_id,
                    package_type_id,
                    name,
                    packaging_level,
                    content_quantity,
                    content_uom_id,
                    status
                )
                SELECT
                    %s,
                    pt.id,
                    %s,
                    'primary',
                    25,
                    u.id,
                    'active'
                FROM package_types pt
                CROSS JOIN units_of_measure u
                WHERE
                    pt.code = '5H'
                    AND u.code = 'KGM'
                RETURNING id
                """,
                (
                    manufacturer_product_id,
                    (
                        "OH18 Quote Test Bag "
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )

        rfq_id = str(
            connection.execute(
                """
                INSERT INTO rfqs (
                    rfq_reference,
                    buyer_organization_id,
                    destination_country_id,
                    destination_trade_location_id,
                    requested_currency_id,
                    requested_incoterm_rule_id,
                    status
                )
                SELECT
                    %s,
                    %s,
                    country.id,
                    location.id,
                    currency.id,
                    incoterm.id,
                    'responded'
                FROM countries country
                CROSS JOIN trade_locations location
                CROSS JOIN currencies currency
                CROSS JOIN incoterm_rules incoterm
                WHERE
                    country.iso2 = 'AE'
                    AND location.unlocode = 'AEJEA'
                    AND currency.code = 'USD'
                    AND incoterm.edition = 2020
                    AND incoterm.code = 'CIF'
                RETURNING id
                """,
                (
                    "OH18-QUOTE-RFQ-"
                    + suffix,
                    customer_id,
                ),
            ).fetchone()[0]
        )

        rfq_line_id = str(
            connection.execute(
                """
                INSERT INTO rfq_lines (
                    rfq_id,
                    line_number,
                    product_id,
                    manufacturer_product_id,
                    packaging_configuration_id,
                    requested_quantity,
                    requested_uom_id
                )
                SELECT
                    %s,
                    1,
                    %s,
                    %s,
                    %s,
                    20,
                    u.id
                FROM units_of_measure u
                WHERE u.code = 'TNE'
                RETURNING id
                """,
                (
                    rfq_id,
                    product_id,
                    manufacturer_product_id,
                    packaging_id,
                ),
            ).fetchone()[0]
        )

        offer_id = str(
            connection.execute(
                """
                INSERT INTO commercial_offers (
                    seller_organization_id,
                    buyer_organization_id,
                    manufacturer_product_id,
                    packaging_configuration_id,
                    offer_reference,
                    status,
                    unit_price,
                    currency_id,
                    price_uom_id,
                    incoterm_rule_id,
                    named_trade_location_id
                )
                SELECT
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'active',
                    1150,
                    currency.id,
                    u.id,
                    incoterm.id,
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
                    supplier_id,
                    customer_id,
                    manufacturer_product_id,
                    packaging_id,
                    (
                        "OH18-QUOTE-OFFER-"
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )

        scenario_id = str(
            connection.execute(
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
                    (
                        "OH18-QUOTE-SCENARIO-"
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )

        return {
            "issuer_id":
                issuer_id,
            "customer_id":
                customer_id,
            "supplier_id":
                supplier_id,
            "product_id":
                product_id,
            "manufacturer_product_id":
                manufacturer_product_id,
            "packaging_id":
                packaging_id,
            "rfq_id":
                rfq_id,
            "rfq_line_id":
                rfq_line_id,
            "offer_id":
                offer_id,
            "scenario_id":
                scenario_id,
        }


    def _create_quotation(
        self,
        connection: psycopg.Connection,
        ids: dict[str, str],
        suffix: str,
    ) -> str:

        return str(
            connection.execute(
                """
                INSERT INTO quotations (
                    quotation_reference,
                    issuer_organization_id,
                    customer_organization_id,
                    source_rfq_id,
                    currency_id,
                    issue_date,
                    valid_until,
                    status,
                    incoterm_rule_id,
                    named_trade_location_id
                )
                SELECT
                    %s,
                    %s,
                    %s,
                    %s,
                    currency.id,
                    DATE '2026-10-01',
                    DATE '2026-10-31',
                    'issued',
                    incoterm.id,
                    location.id
                FROM currencies currency
                CROSS JOIN incoterm_rules incoterm
                CROSS JOIN trade_locations location
                WHERE
                    currency.code = 'USD'
                    AND incoterm.edition = 2020
                    AND incoterm.code = 'CIF'
                    AND location.unlocode = 'AEJEA'
                RETURNING id
                """,
                (
                    "OH18-QUOTE-TEST-"
                    + suffix,
                    ids[
                        "issuer_id"
                    ],
                    ids[
                        "customer_id"
                    ],
                    ids[
                        "rfq_id"
                    ],
                ),
            ).fetchone()[0]
        )


    def test_markup_quotation_uses_landed_cost_without_mutating_sources(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "MARKUP",
            )

            quotation_id = self._create_quotation(
                connection,
                ids,
                "MARKUP",
            )

            offer_before = connection.execute(
                """
                SELECT
                    unit_price::double precision,
                    status
                FROM commercial_offers
                WHERE id = %s
                """,
                (
                    ids[
                        "offer_id"
                    ],
                ),
            ).fetchone()

            scenario_before = connection.execute(
                """
                SELECT
                    landed_cost_total_scenario_currency::double precision,
                    landed_cost_per_target_uom::double precision
                FROM landed_cost_scenarios
                WHERE id = %s
                """,
                (
                    ids[
                        "scenario_id"
                    ],
                ),
            ).fetchone()

            line = connection.execute(
                """
                INSERT INTO quotation_lines (
                    quotation_id,
                    line_number,
                    product_id,
                    manufacturer_product_id,
                    packaging_configuration_id,
                    source_rfq_line_id,
                    source_commercial_offer_id,
                    source_landed_cost_scenario_id,
                    quantity,
                    uom_id,
                    pricing_method,
                    pricing_rate
                )
                SELECT
                    %s,
                    1,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    20,
                    u.id,
                    'markup_percent',
                    10
                FROM units_of_measure u
                WHERE u.code = 'TNE'
                RETURNING
                    internal_cost_unit_price::double precision,
                    quoted_unit_price::double precision,
                    quoted_line_total::double precision
                """,
                (
                    quotation_id,
                    ids[
                        "product_id"
                    ],
                    ids[
                        "manufacturer_product_id"
                    ],
                    ids[
                        "packaging_id"
                    ],
                    ids[
                        "rfq_line_id"
                    ],
                    ids[
                        "offer_id"
                    ],
                    ids[
                        "scenario_id"
                    ],
                ),
            ).fetchone()

            self.assertEqual(
                line[0],
                1150.0,
            )

            self.assertEqual(
                line[1],
                1265.0,
            )

            self.assertEqual(
                line[2],
                25300.0,
            )

            offer_after = connection.execute(
                """
                SELECT
                    unit_price::double precision,
                    status
                FROM commercial_offers
                WHERE id = %s
                """,
                (
                    ids[
                        "offer_id"
                    ],
                ),
            ).fetchone()

            scenario_after = connection.execute(
                """
                SELECT
                    landed_cost_total_scenario_currency::double precision,
                    landed_cost_per_target_uom::double precision
                FROM landed_cost_scenarios
                WHERE id = %s
                """,
                (
                    ids[
                        "scenario_id"
                    ],
                ),
            ).fetchone()

            self.assertEqual(
                offer_after,
                offer_before,
            )

            self.assertEqual(
                scenario_after,
                scenario_before,
            )


    def test_quotation_customer_must_match_source_rfq_buyer(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "CUSTOMER",
            )

            other_customer_id = connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    status
                )
                VALUES (
                    'OH18 Quote Test Other Customer CUSTOMER',
                    'active'
                )
                RETURNING id
                """
            ).fetchone()[0]

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO quotations (
                            quotation_reference,
                            issuer_organization_id,
                            customer_organization_id,
                            source_rfq_id,
                            currency_id
                        )
                        SELECT
                            'OH18-QUOTE-TEST-CUSTOMER',
                            %s,
                            %s,
                            %s,
                            currency.id
                        FROM currencies currency
                        WHERE currency.code = 'USD'
                        """,
                        (
                            ids[
                                "issuer_id"
                            ],
                            other_customer_id,
                            ids[
                                "rfq_id"
                            ],
                        ),
                    )


    def test_quotation_line_rejects_cross_dimension_uom(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "DIMENSION",
            )

            quotation_id = self._create_quotation(
                connection,
                ids,
                "DIMENSION",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO quotation_lines (
                            quotation_id,
                            line_number,
                            product_id,
                            quantity,
                            uom_id,
                            pricing_method,
                            quoted_unit_price
                        )
                        SELECT
                            %s,
                            1,
                            %s,
                            20,
                            u.id,
                            'manual',
                            1500
                        FROM units_of_measure u
                        WHERE u.code = 'LTR'
                        """,
                        (
                            quotation_id,
                            ids[
                                "product_id"
                            ],
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
