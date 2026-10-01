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
class CommercialOfferPostgresIntegrationTest(
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
                    "Refusing to run commercial-offer tests "
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
                    subdivision_code,
                    name,
                    function_codes,
                    status,
                    marked_for_deletion
                )
                SELECT
                    'INCCU',
                    c.id,
                    'KL',
                    'Cochin',
                    '1-------',
                    'AA',
                    FALSE
                FROM countries c
                WHERE c.iso2 = 'IN'
                ON CONFLICT (unlocode)
                DO UPDATE SET
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
            DELETE FROM commercial_offers
            WHERE manufacturer_product_id IN (
                SELECT mp.id
                FROM manufacturer_products mp
                JOIN products p
                  ON p.id = mp.product_id
                WHERE p.name LIKE
                    'OH16 Commercial Offer Test%'
            )
            OR seller_organization_id IN (
                SELECT id
                FROM organizations
                WHERE legal_name LIKE
                    'OH16 Commercial Offer Test%'
            )
            OR buyer_organization_id IN (
                SELECT id
                FROM organizations
                WHERE legal_name LIKE
                    'OH16 Commercial Offer Test%'
            )
            """
        )

        connection.execute(
            """
            DELETE FROM products
            WHERE name LIKE
                'OH16 Commercial Offer Test%'
            """
        )

        connection.execute(
            """
            DELETE FROM organizations
            WHERE legal_name LIKE
                'OH16 Commercial Offer Test%'
            """
        )


    def _seed(
        self,
        connection: psycopg.Connection,
        suffix: str,
    ) -> tuple[
        str,
        str,
        str,
        str,
        str,
    ]:

        seller_id = str(
            connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    status
                )
                VALUES (
                    %s,
                    'active'
                )
                RETURNING id
                """,
                (
                    "OH16 Commercial Offer Test Seller "
                    + suffix,
                ),
            ).fetchone()[0]
        )

        buyer_id = str(
            connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    status
                )
                VALUES (
                    %s,
                    'active'
                )
                RETURNING id
                """,
                (
                    "OH16 Commercial Offer Test Buyer "
                    + suffix,
                ),
            ).fetchone()[0]
        )

        manufacturer_id = str(
            connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    status
                )
                VALUES (
                    %s,
                    'active'
                )
                RETURNING id
                """,
                (
                    "OH16 Commercial Offer Test Manufacturer "
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
                    'OH16 commercial-offer test product.',
                    u.id
                FROM units_of_measure u
                WHERE u.code = 'KGM'
                RETURNING id
                """,
                (
                    "OH16 Commercial Offer Test Product "
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
                        "OH16 Commercial Offer Test Grade "
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
                        "OH16 Commercial Offer Test 25kg Bag "
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )

        return (
            seller_id,
            buyer_id,
            manufacturer_product_id,
            packaging_id,
            product_id,
        )


    def test_valid_fob_offer_links_trade_location(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            (
                seller_id,
                buyer_id,
                manufacturer_product_id,
                packaging_id,
                _product_id,
            ) = self._seed(
                connection,
                "FOB",
            )

            row = connection.execute(
                """
                INSERT INTO commercial_offers (
                    seller_organization_id,
                    buyer_organization_id,
                    manufacturer_product_id,
                    packaging_configuration_id,
                    status,
                    unit_price,
                    currency_id,
                    price_uom_id,
                    minimum_order_quantity,
                    minimum_order_uom_id,
                    incoterm_rule_id,
                    named_trade_location_id
                )
                SELECT
                    %s,
                    %s,
                    %s,
                    %s,
                    'active',
                    1150,
                    currency.id,
                    price_uom.id,
                    20,
                    moq_uom.id,
                    incoterm.id,
                    location.id
                FROM currencies currency
                CROSS JOIN units_of_measure price_uom
                CROSS JOIN units_of_measure moq_uom
                CROSS JOIN incoterm_rules incoterm
                CROSS JOIN trade_locations location
                WHERE
                    currency.code = 'USD'
                    AND price_uom.code = 'TNE'
                    AND moq_uom.code = 'TNE'
                    AND incoterm.edition = 2020
                    AND incoterm.code = 'FOB'
                    AND location.unlocode = 'INCCU'
                RETURNING
                    id::text,
                    unit_price::double precision
                """,
                (
                    seller_id,
                    buyer_id,
                    manufacturer_product_id,
                    packaging_id,
                ),
            ).fetchone()

            self.assertIsNotNone(
                row
            )

            self.assertEqual(
                row[1],
                1150.0,
            )


    def test_maritime_offer_requires_trade_location(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            (
                seller_id,
                _buyer_id,
                manufacturer_product_id,
                _packaging_id,
                _product_id,
            ) = self._seed(
                connection,
                "MARITIME",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO commercial_offers (
                            seller_organization_id,
                            manufacturer_product_id,
                            unit_price,
                            currency_id,
                            price_uom_id,
                            incoterm_rule_id,
                            named_place_text
                        )
                        SELECT
                            %s,
                            %s,
                            1000,
                            currency.id,
                            u.id,
                            incoterm.id,
                            'Some Port'
                        FROM currencies currency
                        CROSS JOIN units_of_measure u
                        CROSS JOIN incoterm_rules incoterm
                        WHERE
                            currency.code = 'USD'
                            AND u.code = 'TNE'
                            AND incoterm.edition = 2020
                            AND incoterm.code = 'FOB'
                        """,
                        (
                            seller_id,
                            manufacturer_product_id,
                        ),
                    )


    def test_price_uom_must_match_product_dimension(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            (
                seller_id,
                _buyer_id,
                manufacturer_product_id,
                _packaging_id,
                _product_id,
            ) = self._seed(
                connection,
                "DIMENSION",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO commercial_offers (
                            seller_organization_id,
                            manufacturer_product_id,
                            unit_price,
                            currency_id,
                            price_uom_id,
                            incoterm_rule_id,
                            named_place_text
                        )
                        SELECT
                            %s,
                            %s,
                            1000,
                            currency.id,
                            u.id,
                            incoterm.id,
                            'Bengaluru, India'
                        FROM currencies currency
                        CROSS JOIN units_of_measure u
                        CROSS JOIN incoterm_rules incoterm
                        WHERE
                            currency.code = 'USD'
                            AND u.code = 'LTR'
                            AND incoterm.edition = 2020
                            AND incoterm.code = 'FCA'
                        """,
                        (
                            seller_id,
                            manufacturer_product_id,
                        ),
                    )


    def test_packaging_must_belong_to_offer_product(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            (
                seller_id,
                _buyer_id,
                manufacturer_product_id,
                _packaging_id,
                _product_id,
            ) = self._seed(
                connection,
                "PKGA",
            )

            (
                _seller2,
                _buyer2,
                _manufacturer_product2,
                packaging_other,
                _product2,
            ) = self._seed(
                connection,
                "PKGB",
            )

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO commercial_offers (
                            seller_organization_id,
                            manufacturer_product_id,
                            packaging_configuration_id,
                            unit_price,
                            currency_id,
                            price_uom_id,
                            incoterm_rule_id,
                            named_place_text
                        )
                        SELECT
                            %s,
                            %s,
                            %s,
                            1000,
                            currency.id,
                            u.id,
                            incoterm.id,
                            'Bengaluru, India'
                        FROM currencies currency
                        CROSS JOIN units_of_measure u
                        CROSS JOIN incoterm_rules incoterm
                        WHERE
                            currency.code = 'USD'
                            AND u.code = 'TNE'
                            AND incoterm.edition = 2020
                            AND incoterm.code = 'FCA'
                        """,
                        (
                            seller_id,
                            manufacturer_product_id,
                            packaging_other,
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
