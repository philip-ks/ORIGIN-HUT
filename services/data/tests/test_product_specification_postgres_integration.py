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
class ProductSpecificationPostgresIntegrationTest(
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
                    "Refusing to run product specification "
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
                'OH15 Specification Test%'
            """
        )

        connection.execute(
            """
            DELETE FROM specification_definitions
            WHERE code LIKE
                'oh15_spec_test_%'
            """
        )


    def _product(
        self,
        connection: psycopg.Connection,
    ) -> str:

        return str(
            connection.execute(
                """
                INSERT INTO products (
                    name
                )
                VALUES (
                    'OH15 Specification Test Product'
                )
                RETURNING id
                """
            ).fetchone()[0]
        )


    def test_numeric_specification_uses_canonical_uom(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            product_id = self._product(
                connection
            )

            kg_id = connection.execute(
                """
                SELECT id
                FROM units_of_measure
                WHERE code = 'KGM'
                """
            ).fetchone()[0]

            definition_id = connection.execute(
                """
                INSERT INTO specification_definitions (
                    code,
                    name,
                    value_type,
                    dimension_code,
                    default_uom_id
                )
                VALUES (
                    'oh15_spec_test_mass',
                    'Test Mass',
                    'numeric',
                    'mass',
                    %s
                )
                RETURNING id
                """,
                (
                    kg_id,
                ),
            ).fetchone()[0]

            row = connection.execute(
                """
                INSERT INTO product_specifications (
                    specification_definition_id,
                    product_id,
                    qualifier,
                    numeric_value,
                    uom_id
                )
                VALUES (
                    %s,
                    %s,
                    'exact',
                    25,
                    %s
                )
                RETURNING id
                """,
                (
                    definition_id,
                    product_id,
                    kg_id,
                ),
            ).fetchone()

            self.assertIsNotNone(
                row
            )


    def test_specification_requires_exactly_one_subject(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            product_id = self._product(
                connection
            )

            definition_id = connection.execute(
                """
                INSERT INTO specification_definitions (
                    code,
                    name,
                    value_type
                )
                VALUES (
                    'oh15_spec_test_text',
                    'Test Text',
                    'text'
                )
                RETURNING id
                """
            ).fetchone()[0]

            with self.assertRaises(
                psycopg.errors.CheckViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO product_specifications (
                            specification_definition_id,
                            text_value
                        )
                        VALUES (
                            %s,
                            'invalid'
                        )
                        """,
                        (
                            definition_id,
                        ),
                    )

            valid = connection.execute(
                """
                INSERT INTO product_specifications (
                    specification_definition_id,
                    product_id,
                    text_value
                )
                VALUES (
                    %s,
                    %s,
                    'coconut shell'
                )
                RETURNING id
                """,
                (
                    definition_id,
                    product_id,
                ),
            ).fetchone()

            self.assertIsNotNone(
                valid
            )


    def test_active_current_definition_is_unique_per_product(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            product_id = self._product(
                connection
            )

            definition_id = connection.execute(
                """
                INSERT INTO specification_definitions (
                    code,
                    name,
                    value_type
                )
                VALUES (
                    'oh15_spec_test_unique',
                    'Test Unique',
                    'text'
                )
                RETURNING id
                """
            ).fetchone()[0]

            connection.execute(
                """
                INSERT INTO product_specifications (
                    specification_definition_id,
                    product_id,
                    text_value
                )
                VALUES (
                    %s,
                    %s,
                    'first'
                )
                """,
                (
                    definition_id,
                    product_id,
                ),
            )

            with self.assertRaises(
                psycopg.errors.UniqueViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO product_specifications (
                            specification_definition_id,
                            product_id,
                            text_value
                        )
                        VALUES (
                            %s,
                            %s,
                            'second'
                        )
                        """,
                        (
                            definition_id,
                            product_id,
                        ),
                    )


if __name__ == "__main__":

    unittest.main()
