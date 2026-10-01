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
class RfqPostgresIntegrationTest(
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
                    "Refusing to run RFQ tests against a non-test database."
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
                'OH18-RFQ-TEST-%'
            """
        )

        connection.execute(
            """
            DELETE FROM products
            WHERE name LIKE
                'OH18 RFQ Test Product%'
            """
        )

        connection.execute(
            """
            DELETE FROM organizations
            WHERE legal_name LIKE
                'OH18 RFQ Test%'
            """
        )


    def _seed(
        self,
        connection: psycopg.Connection,
        suffix: str,
    ) -> dict[str, str]:

        buyer_id = str(
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
                WHERE c.iso2 = 'AE'
                RETURNING id
                """,
                (
                    "OH18 RFQ Test Buyer "
                    + suffix,
                ),
            ).fetchone()[0]
        )

        supplier_id = str(
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
                WHERE c.iso2 = 'IN'
                RETURNING id
                """,
                (
                    "OH18 RFQ Test Supplier "
                    + suffix,
                ),
            ).fetchone()[0]
        )

        manufacturer_id = str(
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
                WHERE c.iso2 = 'IN'
                RETURNING id
                """,
                (
                    "OH18 RFQ Test Manufacturer "
                    + suffix,
                ),
            ).fetchone()[0]
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
                    'OH18 RFQ integration Product.',
                    u.id
                FROM units_of_measure u
                WHERE u.code = 'KGM'
                RETURNING id
                """,
                (
                    "OH18 RFQ Test Product "
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
                        "OH18 RFQ Test Grade "
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
                        "OH18 RFQ Test 25kg Bag "
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
            "product_id":
                product_id,
            "manufacturer_product_id":
                manufacturer_product_id,
            "packaging_id":
                packaging_id,
        }


    def _create_rfq(
        self,
        connection: psycopg.Connection,
        ids: dict[str, str],
        suffix: str,
    ) -> str:

        row = connection.execute(
            """
            INSERT INTO rfqs (
                rfq_reference,
                buyer_organization_id,
                destination_country_id,
                destination_trade_location_id,
                requested_currency_id,
                requested_incoterm_rule_id,
                incoterm_flexible,
                issue_date,
                response_due_at,
                status
            )
            SELECT
                %s,
                %s,
                country.id,
                location.id,
                currency.id,
                incoterm.id,
                TRUE,
                DATE '2026-10-01',
                TIMESTAMPTZ '2026-10-15T12:00:00+00:00',
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
                "OH18-RFQ-TEST-"
                + suffix,
                ids["buyer_id"],
            ),
        ).fetchone()

        self.assertIsNotNone(
            row
        )

        return str(
            row[0]
        )


    def test_rfq_line_and_supplier_are_canonical(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "CANONICAL",
            )

            rfq_id = self._create_rfq(
                connection,
                ids,
                "CANONICAL",
            )

            line_id = connection.execute(
                """
                INSERT INTO rfq_lines (
                    rfq_id,
                    line_number,
                    product_id,
                    manufacturer_product_id,
                    packaging_configuration_id,
                    requested_quantity,
                    requested_uom_id,
                    target_delivery_date,
                    specification_requirements
                )
                SELECT
                    %s,
                    1,
                    %s,
                    %s,
                    %s,
                    20,
                    u.id,
                    DATE '2026-11-15',
                    '{"iodineNumberMin":1000}'::jsonb
                FROM units_of_measure u
                WHERE u.code = 'TNE'
                RETURNING id
                """,
                (
                    rfq_id,
                    ids[
                        "product_id"
                    ],
                    ids[
                        "manufacturer_product_id"
                    ],
                    ids[
                        "packaging_id"
                    ],
                ),
            ).fetchone()[0]

            supplier_invitation_id = connection.execute(
                """
                INSERT INTO rfq_suppliers (
                    rfq_id,
                    supplier_organization_id,
                    status,
                    invited_at,
                    response_due_at
                )
                VALUES (
                    %s,
                    %s,
                    'invited',
                    TIMESTAMPTZ '2026-10-01T12:00:00+00:00',
                    TIMESTAMPTZ '2026-10-15T12:00:00+00:00'
                )
                RETURNING id
                """,
                (
                    rfq_id,
                    ids[
                        "supplier_id"
                    ],
                ),
            ).fetchone()[0]

            self.assertIsNotNone(
                line_id
            )

            self.assertIsNotNone(
                supplier_invitation_id
            )


    def test_rfq_rejects_destination_country_mismatch(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "DESTINATION",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO rfqs (
                            rfq_reference,
                            buyer_organization_id,
                            destination_country_id,
                            destination_trade_location_id,
                            status
                        )
                        SELECT
                            'OH18-RFQ-TEST-DESTINATION',
                            %s,
                            country.id,
                            location.id,
                            'draft'
                        FROM countries country
                        CROSS JOIN trade_locations location
                        WHERE
                            country.iso2 = 'IN'
                            AND location.unlocode = 'AEJEA'
                        """,
                        (
                            ids[
                                "buyer_id"
                            ],
                        ),
                    )


    def test_rfq_line_rejects_wrong_manufacturer_product(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids_a = self._seed(
                connection,
                "MPA",
            )

            ids_b = self._seed(
                connection,
                "MPB",
            )

            rfq_id = self._create_rfq(
                connection,
                ids_a,
                "MPA",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO rfq_lines (
                            rfq_id,
                            line_number,
                            product_id,
                            manufacturer_product_id,
                            requested_quantity,
                            requested_uom_id
                        )
                        SELECT
                            %s,
                            1,
                            %s,
                            %s,
                            20,
                            u.id
                        FROM units_of_measure u
                        WHERE u.code = 'TNE'
                        """,
                        (
                            rfq_id,
                            ids_a[
                                "product_id"
                            ],
                            ids_b[
                                "manufacturer_product_id"
                            ],
                        ),
                    )


    def test_rfq_line_rejects_cross_dimension_uom(
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

            rfq_id = self._create_rfq(
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
                        INSERT INTO rfq_lines (
                            rfq_id,
                            line_number,
                            product_id,
                            requested_quantity,
                            requested_uom_id
                        )
                        SELECT
                            %s,
                            1,
                            %s,
                            20,
                            u.id
                        FROM units_of_measure u
                        WHERE u.code = 'LTR'
                        """,
                        (
                            rfq_id,
                            ids[
                                "product_id"
                            ],
                        ),
                    )


    def test_rfq_supplier_cannot_equal_buyer(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            ids = self._seed(
                connection,
                "SAMEPARTY",
            )

            rfq_id = self._create_rfq(
                connection,
                ids,
                "SAMEPARTY",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

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
                        """,
                        (
                            rfq_id,
                            ids[
                                "buyer_id"
                            ],
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
