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
class OrganizationSitePostgresIntegrationTest(
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
                    "Refusing to run organization-site tests "
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
                'OH15 Site Test%'
            """
        )

        connection.execute(
            """
            DELETE FROM organizations
            WHERE legal_name LIKE
                'OH15 Site Test%'
            """
        )


    def test_manufacturer_site_country_is_independent_of_org_country_and_origin(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            india_id = connection.execute(
                """
                SELECT id
                FROM countries
                WHERE iso2 = 'IN'
                """
            ).fetchone()[0]

            germany_id = connection.execute(
                """
                SELECT id
                FROM countries
                WHERE iso2 = 'DE'
                """
            ).fetchone()[0]

            manufacturer_id = connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    country_id,
                    status
                )
                VALUES (
                    'OH15 Site Test Manufacturer',
                    %s,
                    'active'
                )
                RETURNING id
                """,
                (
                    germany_id,
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
                    'OH15 Site Test Product'
                )
                RETURNING id
                """
            ).fetchone()[0]

            manufacturer_product_id = connection.execute(
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
                    'OH15 Site Test Grade'
                )
                RETURNING id
                """,
                (
                    product_id,
                    manufacturer_id,
                    india_id,
                ),
            ).fetchone()[0]

            site_id = connection.execute(
                """
                INSERT INTO organization_sites (
                    organization_id,
                    name,
                    site_type,
                    country_id,
                    geography
                )
                VALUES (
                    %s,
                    'OH15 Site Test Bengaluru Plant',
                    'manufacturing',
                    %s,
                    ST_SetSRID(
                        ST_MakePoint(
                            77.5946,
                            12.9716
                        ),
                        4326
                    )::geography
                )
                RETURNING id
                """,
                (
                    manufacturer_id,
                    india_id,
                ),
            ).fetchone()[0]

            relationship = connection.execute(
                """
                INSERT INTO manufacturer_product_sites (
                    manufacturer_product_id,
                    organization_site_id,
                    relationship_type
                )
                VALUES (
                    %s,
                    %s,
                    'manufactured_at'
                )
                RETURNING id
                """,
                (
                    manufacturer_product_id,
                    site_id,
                ),
            ).fetchone()

            self.assertIsNotNone(
                relationship
            )

            facts = connection.execute(
                """
                SELECT
                    org_country.iso2,
                    origin.iso2,
                    site_country.iso2
                FROM manufacturer_products mp
                JOIN organizations o
                  ON o.id =
                     mp.manufacturer_id
                LEFT JOIN countries org_country
                  ON org_country.id =
                     o.country_id
                LEFT JOIN countries origin
                  ON origin.id =
                     mp.country_of_origin_id
                JOIN manufacturer_product_sites mps
                  ON mps.manufacturer_product_id =
                     mp.id
                JOIN organization_sites os
                  ON os.id =
                     mps.organization_site_id
                LEFT JOIN countries site_country
                  ON site_country.id =
                     os.country_id
                WHERE mp.id = %s
                """,
                (
                    manufacturer_product_id,
                ),
            ).fetchone()

            self.assertEqual(
                facts,
                (
                    "DE",
                    "IN",
                    "IN",
                ),
            )


    def test_contract_manufacturing_site_can_belong_to_another_org(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            brand_owner = connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    status
                )
                VALUES (
                    'OH15 Site Test Brand Owner',
                    'active'
                )
                RETURNING id
                """
            ).fetchone()[0]

            contract_manufacturer = connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    status
                )
                VALUES (
                    'OH15 Site Test Contract Manufacturer',
                    'active'
                )
                RETURNING id
                """
            ).fetchone()[0]

            connection.execute(
                """
                INSERT INTO organization_roles (
                    organization_id,
                    role_code
                )
                VALUES
                    (
                        %s,
                        'manufacturer'
                    ),
                    (
                        %s,
                        'manufacturer'
                    )
                """,
                (
                    brand_owner,
                    contract_manufacturer,
                ),
            )

            product_id = connection.execute(
                """
                INSERT INTO products (
                    name
                )
                VALUES (
                    'OH15 Site Test Contract Product'
                )
                RETURNING id
                """
            ).fetchone()[0]

            manufacturer_product_id = connection.execute(
                """
                INSERT INTO manufacturer_products (
                    product_id,
                    manufacturer_id,
                    name
                )
                VALUES (
                    %s,
                    %s,
                    'OH15 Site Test Contract Grade'
                )
                RETURNING id
                """,
                (
                    product_id,
                    brand_owner,
                ),
            ).fetchone()[0]

            site_id = connection.execute(
                """
                INSERT INTO organization_sites (
                    organization_id,
                    name,
                    site_type
                )
                VALUES (
                    %s,
                    'OH15 Site Test Contract Plant',
                    'manufacturing'
                )
                RETURNING id
                """,
                (
                    contract_manufacturer,
                ),
            ).fetchone()[0]

            row = connection.execute(
                """
                INSERT INTO manufacturer_product_sites (
                    manufacturer_product_id,
                    organization_site_id,
                    relationship_type
                )
                VALUES (
                    %s,
                    %s,
                    'manufactured_at'
                )
                RETURNING id
                """,
                (
                    manufacturer_product_id,
                    site_id,
                ),
            ).fetchone()

            self.assertIsNotNone(
                row
            )


if __name__ == "__main__":

    unittest.main()
