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
class ManufacturerProductPostgresIntegrationTest(
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
                    "Refusing to run manufacturer-product "
                    "tests against a non-test database."
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
                        'DE',
                        'DEU',
                        '276',
                        'Germany',
                        'Federal Republic of Germany',
                        TRUE
                    )
                ON CONFLICT (iso2)
                DO UPDATE SET
                    is_active = TRUE
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
            DELETE FROM products
            WHERE name LIKE
                'OH15 Manufacturer Product Test%'
            """
        )

        connection.execute(
            """
            DELETE FROM organizations
            WHERE legal_name LIKE
                'OH15 Manufacturer Product Test%'
            """
        )


    def _seed(
        self,
        connection: psycopg.Connection,
        suffix: str,
    ) -> tuple[
        str,
        str,
    ]:

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
                    (
                        "OH15 Manufacturer Product Test "
                        + suffix
                    ),
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
                    description
                )
                VALUES (
                    %s,
                    'Generic trade product.'
                )
                RETURNING id
                """,
                (
                    (
                        "OH15 Manufacturer Product Test Product "
                        + suffix
                    ),
                ),
            ).fetchone()[0]
        )

        return (
            manufacturer_id,
            product_id,
        )


    def test_manufacturer_product_links_generic_product_and_origin(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            (
                manufacturer_id,
                product_id,
            ) = self._seed(
                connection,
                "A",
            )

            row = connection.execute(
                """
                INSERT INTO manufacturer_products (
                    product_id,
                    manufacturer_id,
                    country_of_origin_id,
                    name,
                    brand,
                    grade,
                    sku,
                    attributes
                )
                SELECT
                    %s,
                    %s,
                    c.id,
                    'Activated Carbon Grade AC-1000',
                    'Example Carbon',
                    'AC-1000',
                    'AC-1000-25',
                    '{"iodineNumberMgG":1000}'::jsonb
                FROM countries c
                WHERE c.iso2 = 'IN'
                RETURNING
                    id::text,
                    product_id::text,
                    manufacturer_id::text,
                    country_of_origin_id::text
                """,
                (
                    product_id,
                    manufacturer_id,
                ),
            ).fetchone()

            self.assertIsNotNone(
                row
            )

            self.assertEqual(
                row[1],
                product_id,
            )

            self.assertEqual(
                row[2],
                manufacturer_id,
            )

            origin = connection.execute(
                """
                SELECT c.iso2
                FROM manufacturer_products mp
                JOIN countries c
                  ON c.id =
                     mp.country_of_origin_id
                WHERE mp.id = %s
                """,
                (
                    row[0],
                ),
            ).fetchone()[0]

            self.assertEqual(
                origin,
                "IN",
            )


    def test_source_backed_identity_creates_provenance_link(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            (
                manufacturer_id,
                product_id,
            ) = self._seed(
                connection,
                "PROVENANCE",
            )

            source_id = connection.execute(
                """
                INSERT INTO data_sources (
                    code,
                    name,
                    provider,
                    category,
                    access_method,
                    is_official
                )
                VALUES (
                    'oh15_manufacturer_product_test_source',
                    'OH15 Manufacturer Product Test Source',
                    'Origin Hut Test',
                    'product_intelligence',
                    'test',
                    TRUE
                )
                ON CONFLICT (code)
                DO UPDATE SET
                    name = EXCLUDED.name
                RETURNING id
                """
            ).fetchone()[0]

            run_id = connection.execute(
                """
                INSERT INTO ingestion_runs (
                    data_source_id,
                    status
                )
                VALUES (
                    %s,
                    'completed'
                )
                RETURNING id
                """,
                (
                    source_id,
                ),
            ).fetchone()[0]

            source_record_id = connection.execute(
                """
                INSERT INTO source_records (
                    data_source_id,
                    ingestion_run_id,
                    external_id,
                    record_type,
                    content_hash,
                    payload
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'manufacturer_product_identity',
                    repeat('a', 64),
                    '{}'::jsonb
                )
                RETURNING id
                """,
                (
                    source_id,
                    run_id,
                    (
                        "oh15-manufacturer-product-provenance-"
                        + manufacturer_id
                    ),
                ),
            ).fetchone()[0]

            manufacturer_product_id = connection.execute(
                """
                INSERT INTO manufacturer_products (
                    product_id,
                    manufacturer_id,
                    name,
                    source_type,
                    canonical_source_record_id,
                    confidence
                )
                VALUES (
                    %s,
                    %s,
                    'Source-backed grade',
                    'official_manufacturer',
                    %s,
                    0.9900
                )
                RETURNING id
                """,
                (
                    product_id,
                    manufacturer_id,
                    source_record_id,
                ),
            ).fetchone()[0]

            row = connection.execute(
                """
                SELECT
                    source_type,
                    canonical_source_record_id::text,
                    confidence::double precision
                FROM manufacturer_products
                WHERE id = %s
                """,
                (
                    manufacturer_product_id,
                ),
            ).fetchone()

            self.assertEqual(
                row[0],
                "official_manufacturer",
            )

            self.assertEqual(
                row[1],
                str(
                    source_record_id
                ),
            )

            self.assertAlmostEqual(
                row[2],
                0.99,
            )

            evidence_count = connection.execute(
                """
                SELECT COUNT(*)::int
                FROM entity_source_links
                WHERE
                    source_record_id = %s
                    AND entity_type =
                        'manufacturer_product'
                    AND entity_id = %s
                    AND relationship_type =
                        'identity_evidence'
                """,
                (
                    source_record_id,
                    manufacturer_product_id,
                ),
            ).fetchone()[0]

            self.assertEqual(
                evidence_count,
                1,
            )


    def test_sku_is_unique_within_manufacturer(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            (
                manufacturer_id,
                product_id,
            ) = self._seed(
                connection,
                "B",
            )

            connection.execute(
                """
                INSERT INTO manufacturer_products (
                    product_id,
                    manufacturer_id,
                    name,
                    sku
                )
                VALUES (
                    %s,
                    %s,
                    'Grade One',
                    'DUPLICATE-SKU'
                )
                """,
                (
                    product_id,
                    manufacturer_id,
                ),
            )

            with self.assertRaises(
                psycopg.errors.UniqueViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO manufacturer_products (
                            product_id,
                            manufacturer_id,
                            name,
                            sku
                        )
                        VALUES (
                            %s,
                            %s,
                            'Grade Two',
                            'DUPLICATE-SKU'
                        )
                        """,
                        (
                            product_id,
                            manufacturer_id,
                        ),
                    )


    def test_origin_is_not_derived_from_manufacturer_country(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            (
                manufacturer_id,
                product_id,
            ) = self._seed(
                connection,
                "C",
            )

            germany_id = connection.execute(
                """
                SELECT id
                FROM countries
                WHERE iso2 = 'DE'
                """
            ).fetchone()[0]

            connection.execute(
                """
                UPDATE organizations
                SET country_id = %s
                WHERE id = %s
                """,
                (
                    germany_id,
                    manufacturer_id,
                ),
            )

            india_id = connection.execute(
                """
                SELECT id
                FROM countries
                WHERE iso2 = 'IN'
                """
            ).fetchone()[0]

            row = connection.execute(
                """
                INSERT INTO manufacturer_products (
                    product_id,
                    manufacturer_id,
                    country_of_origin_id,
                    name
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'Made in India Grade'
                )
                RETURNING country_of_origin_id::text
                """,
                (
                    product_id,
                    manufacturer_id,
                    india_id,
                ),
            ).fetchone()

            self.assertEqual(
                row[0],
                str(
                    india_id
                ),
            )


if __name__ == "__main__":

    unittest.main()
