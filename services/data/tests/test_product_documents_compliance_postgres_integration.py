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
class ProductDocumentsCompliancePostgresIntegrationTest(
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
                    "Refusing to run document/compliance tests "
                    "against a non-test database."
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
                'OH15 Document Test%'
            """
        )

        connection.execute(
            """
            DELETE FROM compliance_frameworks
            WHERE code LIKE
                'oh15_document_test_%'
            """
        )


    def _product(
        self,
        connection: psycopg.Connection,
        suffix: str,
    ) -> str:

        return str(
            connection.execute(
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
                        "OH15 Document Test Product "
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )


    def test_document_requires_exactly_one_subject_and_valid_hash(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            product_id =
                self._product(
                    connection,
                    "A",
                )

            document_type = connection.execute(
                """
                SELECT id
                FROM product_document_types
                WHERE code = 'tds'
                """
            ).fetchone()[0]

            row = connection.execute(
                """
                INSERT INTO product_documents (
                    document_type_id,
                    product_id,
                    title,
                    content_sha256
                )
                VALUES (
                    %s,
                    %s,
                    'Technical Data Sheet',
                    %s
                )
                RETURNING id
                """,
                (
                    document_type,
                    product_id,
                    "a" * 64,
                ),
            ).fetchone()

            self.assertIsNotNone(
                row
            )

            with self.assertRaises(
                psycopg.errors.CheckViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO product_documents (
                            document_type_id,
                            product_id,
                            title,
                            content_sha256
                        )
                        VALUES (
                            %s,
                            %s,
                            'Invalid Hash',
                            'not-a-hash'
                        )
                        """,
                        (
                            document_type,
                            product_id,
                        ),
                    )


    def test_compliance_document_must_match_same_product_subject(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            product_a =
                self._product(
                    connection,
                    "B1",
                )

            product_b =
                self._product(
                    connection,
                    "B2",
                )

            document_type = connection.execute(
                """
                SELECT id
                FROM product_document_types
                WHERE code = 'certificate'
                """
            ).fetchone()[0]

            foreign_document = connection.execute(
                """
                INSERT INTO product_documents (
                    document_type_id,
                    product_id,
                    title
                )
                VALUES (
                    %s,
                    %s,
                    'Foreign Product Certificate'
                )
                RETURNING id
                """,
                (
                    document_type,
                    product_b,
                ),
            ).fetchone()[0]

            framework_id = connection.execute(
                """
                INSERT INTO compliance_frameworks (
                    code,
                    name
                )
                VALUES (
                    'oh15_document_test_framework',
                    'OH15 Document Test Framework'
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
                        INSERT INTO product_compliance_records (
                            framework_id,
                            product_id,
                            compliance_status,
                            evidence_document_id
                        )
                        VALUES (
                            %s,
                            %s,
                            'compliant',
                            %s
                        )
                        """,
                        (
                            framework_id,
                            product_a,
                            foreign_document,
                        ),
                    )


    def test_document_dates_are_ordered(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            product_id =
                self._product(
                    connection,
                    "C",
                )

            document_type = connection.execute(
                """
                SELECT id
                FROM product_document_types
                WHERE code = 'coa'
                """
            ).fetchone()[0]

            with self.assertRaises(
                psycopg.errors.CheckViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO product_documents (
                            document_type_id,
                            product_id,
                            title,
                            issue_date,
                            expiry_date
                        )
                        VALUES (
                            %s,
                            %s,
                            'Invalid Date Certificate',
                            DATE '2026-09-30',
                            DATE '2026-01-01'
                        )
                        """,
                        (
                            document_type,
                            product_id,
                        ),
                    )


if __name__ == "__main__":

    unittest.main()
