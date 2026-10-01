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
class RfqResponsePostgresIntegrationTest(
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
                    "Refusing to run RFQ response tests against a non-test database."
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
            DELETE FROM rfqs
            WHERE rfq_reference LIKE
                'OH18-RESP-TEST-%'
            """
        )

        connection.execute(
            """
            DELETE FROM landed_cost_scenarios
            WHERE commercial_offer_id IN (
                SELECT id
                FROM commercial_offers
                WHERE offer_reference LIKE
                    'OH18-RESP-OFFER-%'
            )
            """
        )

        connection.execute(
            """
            DELETE FROM commercial_offers
            WHERE offer_reference LIKE
                'OH18-RESP-OFFER-%'
            """
        )

        connection.execute(
            """
            DELETE FROM products
            WHERE name LIKE
                'OH18 Response Test Product%'
            """
        )

        connection.execute(
            """
            DELETE FROM organizations
            WHERE legal_name LIKE
                'OH18 Response Test%'
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

        buyer_id = organization(
            "OH18 Response Test Buyer "
            + suffix,
            "AE",
        )

        supplier_id = organization(
            "OH18 Response Test Supplier "
            + suffix,
            "IN",
        )

        other_supplier_id = organization(
            "OH18 Response Test Other Supplier "
            + suffix,
            "IN",
        )

        manufacturer_id = organization(
            "OH18 Response Test Manufacturer "
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
                    'OH18 response test Product.',
                    u.id
                FROM units_of_measure u
                WHERE u.code = 'KGM'
                RETURNING id
                """,
                (
                    "OH18 Response Test Product "
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
                        "OH18 Response Test Grade "
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
                        "OH18 Response Test Bag "
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
                    'issued'
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
                    "OH18-RESP-TEST-"
                    + suffix,
                    buyer_id,
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

        rfq_supplier_id = str(
            connection.execute(
                """
                INSERT INTO rfq_suppliers (
                    rfq_id,
                    supplier_organization_id,
                    status,
                    invited_at
                )
                VALUES (
                    %s,
                    %s,
                    'invited',
                    NOW()
                )
                RETURNING id
                """,
                (
                    rfq_id,
                    supplier_id,
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
                    buyer_id,
                    manufacturer_product_id,
                    packaging_id,
                    (
                        "OH18-RESP-OFFER-"
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )

        return {
            "buyer_id":
                buyer_id,
            "supplier_id":
                supplier_id,
            "other_supplier_id":
                other_supplier_id,
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
            "rfq_supplier_id":
                rfq_supplier_id,
            "offer_id":
                offer_id,
        }


    def test_response_links_offer_and_updates_workflow_status(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "VALID",
            )

            response_id = connection.execute(
                """
                INSERT INTO rfq_responses (
                    rfq_id,
                    rfq_line_id,
                    rfq_supplier_id,
                    commercial_offer_id,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    'submitted'
                )
                RETURNING id
                """,
                (
                    ids["rfq_id"],
                    ids["rfq_line_id"],
                    ids["rfq_supplier_id"],
                    ids["offer_id"],
                ),
            ).fetchone()[0]

            self.assertIsNotNone(
                response_id
            )

            supplier_status = connection.execute(
                """
                SELECT status
                FROM rfq_suppliers
                WHERE id = %s
                """,
                (
                    ids[
                        "rfq_supplier_id"
                    ],
                ),
            ).fetchone()[0]

            rfq_status = connection.execute(
                """
                SELECT status
                FROM rfqs
                WHERE id = %s
                """,
                (
                    ids[
                        "rfq_id"
                    ],
                ),
            ).fetchone()[0]

            self.assertEqual(
                supplier_status,
                "responded",
            )

            self.assertEqual(
                rfq_status,
                "responded",
            )


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
                    'OH18-RESP-COMPARE-VALID',
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
                    ids[
                        "offer_id"
                    ],
                ),
            ).fetchone()[0]

            comparison = connection.execute(
                """
                SELECT
                    is_comparable,
                    comparison_reason,
                    landed_cost_scenario_id,
                    landed_cost_per_requested_uom::double precision
                FROM rfq_response_comparison
                WHERE
                    rfq_id = %s
                    AND commercial_offer_id = %s
                """,
                (
                    ids[
                        "rfq_id"
                    ],
                    ids[
                        "offer_id"
                    ],
                ),
            ).fetchone()

            self.assertTrue(
                comparison[0]
            )

            self.assertEqual(
                comparison[1],
                "comparable",
            )

            self.assertEqual(
                str(
                    comparison[2]
                ),
                str(
                    scenario_id
                ),
            )

            self.assertEqual(
                comparison[3],
                1150.0,
            )


    def test_response_rejects_offer_from_uninvited_supplier(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "WRONGSELLER",
            )

            wrong_offer_id = connection.execute(
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
                    'OH18-RESP-OFFER-WRONGSELLER-OTHER',
                    'active',
                    1100,
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
                    ids[
                        "other_supplier_id"
                    ],
                    ids[
                        "buyer_id"
                    ],
                    ids[
                        "manufacturer_product_id"
                    ],
                    ids[
                        "packaging_id"
                    ],
                ),
            ).fetchone()[0]

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO rfq_responses (
                            rfq_id,
                            rfq_line_id,
                            rfq_supplier_id,
                            commercial_offer_id
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        """,
                        (
                            ids[
                                "rfq_id"
                            ],
                            ids[
                                "rfq_line_id"
                            ],
                            ids[
                                "rfq_supplier_id"
                            ],
                            wrong_offer_id,
                        ),
                    )


    def test_response_rejects_wrong_product_offer(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "WRONGPRODUCT",
            )

            other_product_id = connection.execute(
                """
                INSERT INTO products (
                    name,
                    description,
                    base_uom_id
                )
                SELECT
                    'OH18 Response Test Product WRONGPRODUCT OTHER',
                    'Other Product.',
                    u.id
                FROM units_of_measure u
                WHERE u.code = 'KGM'
                RETURNING id
                """
            ).fetchone()[0]

            other_mp_id = connection.execute(
                """
                INSERT INTO manufacturer_products (
                    product_id,
                    manufacturer_id,
                    name,
                    status
                )
                SELECT
                    %s,
                    mp.manufacturer_id,
                    'OH18 Response Test Grade WRONGPRODUCT OTHER',
                    'active'
                FROM manufacturer_products mp
                WHERE mp.id = %s
                RETURNING id
                """,
                (
                    other_product_id,
                    ids[
                        "manufacturer_product_id"
                    ],
                ),
            ).fetchone()[0]

            wrong_offer_id = connection.execute(
                """
                INSERT INTO commercial_offers (
                    seller_organization_id,
                    buyer_organization_id,
                    manufacturer_product_id,
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
                    'OH18-RESP-OFFER-WRONGPRODUCT-OTHER',
                    'active',
                    1100,
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
                    ids[
                        "supplier_id"
                    ],
                    ids[
                        "buyer_id"
                    ],
                    other_mp_id,
                ),
            ).fetchone()[0]

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO rfq_responses (
                            rfq_id,
                            rfq_line_id,
                            rfq_supplier_id,
                            commercial_offer_id
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        """,
                        (
                            ids[
                                "rfq_id"
                            ],
                            ids[
                                "rfq_line_id"
                            ],
                            ids[
                                "rfq_supplier_id"
                            ],
                            wrong_offer_id,
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
