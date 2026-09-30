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
class ProductPackagingPostgresIntegrationTest(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.database_url = os.environ[
            "DATABASE_URL"
        ]

        with psycopg.connect(
            self.database_url
        ) as connection:

            database_name = connection.execute(
                "SELECT current_database()"
            ).fetchone()[0]

            if "test" not in database_name.lower():

                raise RuntimeError(
                    "Refusing to run packaging integration "
                    "tests against a non-test database."
                )

            self._cleanup(
                connection
            )


    def tearDown(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
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
            DELETE FROM products
            WHERE name LIKE
                'OH15 Packaging Test%'
            """
        )

        connection.execute(
            """
            DELETE FROM organizations
            WHERE legal_name LIKE
                'OH15 Packaging Test%'
            """
        )


    def _manufacturer_product(
        self,
        connection: psycopg.Connection,
        suffix: str,
    ) -> str:

        manufacturer_id = connection.execute(
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
                (
                    "OH15 Packaging Test Manufacturer "
                    + suffix
                ),
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
                name
            )
            VALUES (
                %s
            )
            RETURNING id
            """,
            (
                (
                    "OH15 Packaging Test Product "
                    + suffix
                ),
            ),
        ).fetchone()[0]

        return str(
            connection.execute(
                """
                INSERT INTO manufacturer_products (
                    product_id,
                    manufacturer_id,
                    name
                )
                VALUES (
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    product_id,
                    manufacturer_id,
                    (
                        "OH15 Packaging Test Grade "
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )


    def test_primary_and_pallet_hierarchy(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            manufacturer_product_id = (
                self._manufacturer_product(
                    connection,
                    "A",
                )
            )

            bag_type = connection.execute(
                """
                SELECT id
                FROM package_types
                WHERE code = '5H'
                """
            ).fetchone()[0]

            pallet_type = connection.execute(
                """
                SELECT id
                FROM package_types
                WHERE code = 'PX'
                """
            ).fetchone()[0]

            kg = connection.execute(
                """
                SELECT id
                FROM units_of_measure
                WHERE code = 'KGM'
                """
            ).fetchone()[0]

            bag_id = connection.execute(
                """
                INSERT INTO packaging_configurations (
                    manufacturer_product_id,
                    package_type_id,
                    name,
                    packaging_level,
                    content_quantity,
                    content_uom_id,
                    net_weight,
                    gross_weight,
                    weight_uom_id,
                    is_default
                )
                VALUES (
                    %s,
                    %s,
                    '25 kg woven bag',
                    'primary',
                    25,
                    %s,
                    25,
                    25.4,
                    %s,
                    TRUE
                )
                RETURNING id
                """,
                (
                    manufacturer_product_id,
                    bag_type,
                    kg,
                    kg,
                ),
            ).fetchone()[0]

            pallet = connection.execute(
                """
                INSERT INTO packaging_configurations (
                    manufacturer_product_id,
                    package_type_id,
                    name,
                    packaging_level,
                    inner_packaging_id,
                    inner_package_count
                )
                VALUES (
                    %s,
                    %s,
                    '40 bag pallet',
                    'logistics',
                    %s,
                    40
                )
                RETURNING
                    inner_packaging_id::text,
                    inner_package_count
                """,
                (
                    manufacturer_product_id,
                    pallet_type,
                    bag_id,
                ),
            ).fetchone()

            self.assertEqual(
                pallet[0],
                str(
                    bag_id
                ),
            )

            self.assertEqual(
                pallet[1],
                40,
            )


    def test_inner_packaging_must_match_manufacturer_product(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            product_a = (
                self._manufacturer_product(
                    connection,
                    "B1",
                )
            )

            product_b = (
                self._manufacturer_product(
                    connection,
                    "B2",
                )
            )

            bag_type = connection.execute(
                """
                SELECT id
                FROM package_types
                WHERE code = 'BG'
                """
            ).fetchone()[0]

            pallet_type = connection.execute(
                """
                SELECT id
                FROM package_types
                WHERE code = 'PX'
                """
            ).fetchone()[0]

            kg = connection.execute(
                """
                SELECT id
                FROM units_of_measure
                WHERE code = 'KGM'
                """
            ).fetchone()[0]

            foreign_bag = connection.execute(
                """
                INSERT INTO packaging_configurations (
                    manufacturer_product_id,
                    package_type_id,
                    name,
                    packaging_level,
                    content_quantity,
                    content_uom_id
                )
                VALUES (
                    %s,
                    %s,
                    'Foreign bag',
                    'primary',
                    25,
                    %s
                )
                RETURNING id
                """,
                (
                    product_b,
                    bag_type,
                    kg,
                ),
            ).fetchone()[0]

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO packaging_configurations (
                            manufacturer_product_id,
                            package_type_id,
                            name,
                            packaging_level,
                            inner_packaging_id,
                            inner_package_count
                        )
                        VALUES (
                            %s,
                            %s,
                            'Invalid pallet',
                            'logistics',
                            %s,
                            40
                        )
                        """,
                        (
                            product_a,
                            pallet_type,
                            foreign_bag,
                        ),
                    )


    def test_gross_weight_cannot_be_below_net_weight(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            manufacturer_product_id = (
                self._manufacturer_product(
                    connection,
                    "C",
                )
            )

            bag_type = connection.execute(
                """
                SELECT id
                FROM package_types
                WHERE code = 'BG'
                """
            ).fetchone()[0]

            kg = connection.execute(
                """
                SELECT id
                FROM units_of_measure
                WHERE code = 'KGM'
                """
            ).fetchone()[0]

            with self.assertRaises(
                psycopg.errors.CheckViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO packaging_configurations (
                            manufacturer_product_id,
                            package_type_id,
                            name,
                            packaging_level,
                            content_quantity,
                            content_uom_id,
                            net_weight,
                            gross_weight,
                            weight_uom_id
                        )
                        VALUES (
                            %s,
                            %s,
                            'Invalid weight bag',
                            'primary',
                            25,
                            %s,
                            25,
                            24,
                            %s
                        )
                        """,
                        (
                            manufacturer_product_id,
                            bag_type,
                            kg,
                            kg,
                        ),
                    )


if __name__ == "__main__":

    unittest.main()
