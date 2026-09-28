from __future__ import annotations

import os
import unittest
import uuid

import psycopg


RUN_DATABASE_INTEGRATION = (
    os.environ.get(
        "ORIGINHUT_RUN_DB_INTEGRATION"
    )
    == "1"
)


DATABASE_URL = (
    os.environ.get(
        "DATABASE_URL"
    )
)


@unittest.skipUnless(
    RUN_DATABASE_INTEGRATION
    and DATABASE_URL,
    "Database integration tests are disabled.",
)
class CounterpartyPostgresIntegrationTest(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ) -> None:

        assert DATABASE_URL is not None

        with psycopg.connect(
            DATABASE_URL
        ) as connection:

            database_name = (
                connection.execute(
                    """
                    SELECT current_database()
                    """
                ).fetchone()[0]
            )


            if (
                "test"
                not in database_name.lower()
            ):

                raise RuntimeError(
                    "Refusing to run counterparty integration "
                    "tests against a non-test database: "
                    + database_name
                )


            migration = (
                connection.execute(
                    """
                    SELECT name
                    FROM schema_migrations
                    WHERE version = '014'
                    """
                ).fetchone()
            )


            if migration is None:

                raise RuntimeError(
                    "Migration 014 has not been applied."
                )


    def _create_organization(
        self,
        connection: psycopg.Connection,
    ):

        suffix = uuid.uuid4().hex


        return connection.execute(
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
                "OH14 Test Organization "
                + suffix,
            ),
        ).fetchone()[0]


    def _ensure_country(
        self,
        connection: psycopg.Connection,
    ):

        return connection.execute(
            """
            INSERT INTO countries (
                iso2,
                iso3,
                numeric_code,
                name,
                official_name,
                is_active
            )
            VALUES (
                'AE',
                'ARE',
                '784',
                'United Arab Emirates',
                'United Arab Emirates',
                TRUE
            )
            ON CONFLICT (iso2)
            DO UPDATE SET
                iso3 = EXCLUDED.iso3,
                numeric_code = EXCLUDED.numeric_code,
                name = EXCLUDED.name,
                official_name = EXCLUDED.official_name,
                is_active = TRUE
            RETURNING id
            """
        ).fetchone()[0]


    def _ensure_hs(
        self,
        connection: psycopg.Connection,
    ):

        return connection.execute(
            """
            INSERT INTO hs_codes (
                nomenclature,
                code,
                level,
                description,
                valid_from
            )
            VALUES (
                'HS2022',
                '380210',
                6,
                'Carbon; activated',
                DATE '2022-01-01'
            )
            ON CONFLICT (
                nomenclature,
                code
            )
            DO UPDATE SET
                level = EXCLUDED.level,
                description = EXCLUDED.description,
                valid_from = EXCLUDED.valid_from
            RETURNING id
            """
        ).fetchone()[0]


    def test_activity_requires_product_or_hs_subject(
        self,
    ) -> None:

        assert DATABASE_URL is not None

        with psycopg.connect(
            DATABASE_URL
        ) as connection:

            organization_id = (
                self._create_organization(
                    connection
                )
            )


            with self.assertRaises(
                psycopg.errors.CheckViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO organization_trade_activities (
                            organization_id,
                            activity_type,
                            status
                        )
                        VALUES (
                            %s,
                            'exports',
                            'active'
                        )
                        """,
                        (
                            organization_id,
                        ),
                    )


    def test_open_active_scope_is_canonicalized_once(
        self,
    ) -> None:

        assert DATABASE_URL is not None

        with psycopg.connect(
            DATABASE_URL
        ) as connection:

            organization_id = (
                self._create_organization(
                    connection
                )
            )

            hs_code_id = (
                self._ensure_hs(
                    connection
                )
            )

            market_country_id = (
                self._ensure_country(
                    connection
                )
            )


            connection.execute(
                """
                INSERT INTO organization_trade_activities (
                    organization_id,
                    activity_type,
                    hs_code_id,
                    market_country_id,
                    status,
                    confidence,
                    source_type
                )
                VALUES (
                    %s,
                    'imports',
                    %s,
                    %s,
                    'active',
                    0.9500,
                    'official_registry'
                )
                """,
                (
                    organization_id,
                    hs_code_id,
                    market_country_id,
                ),
            )


            with self.assertRaises(
                psycopg.errors.UniqueViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO organization_trade_activities (
                            organization_id,
                            activity_type,
                            hs_code_id,
                            market_country_id,
                            status,
                            confidence,
                            source_type
                        )
                        VALUES (
                            %s,
                            'imports',
                            %s,
                            %s,
                            'active',
                            0.9000,
                            'company_website'
                        )
                        """,
                        (
                            organization_id,
                            hs_code_id,
                            market_country_id,
                        ),
                    )


    def test_activity_preserves_multiple_evidence_records(
        self,
    ) -> None:

        assert DATABASE_URL is not None

        with psycopg.connect(
            DATABASE_URL
        ) as connection:

            organization_id = (
                self._create_organization(
                    connection
                )
            )

            hs_code_id = (
                self._ensure_hs(
                    connection
                )
            )

            market_country_id = (
                self._ensure_country(
                    connection
                )
            )


            product_id = connection.execute(
                """
                INSERT INTO products (
                    manufacturer_id,
                    name,
                    description,
                    is_active
                )
                VALUES (
                    %s,
                    %s,
                    'Activated carbon test product',
                    TRUE
                )
                RETURNING id
                """,
                (
                    organization_id,
                    (
                        "OH14 Activated Carbon "
                        + uuid.uuid4().hex
                    ),
                ),
            ).fetchone()[0]


            source_code = (
                "oh14_test_"
                + uuid.uuid4().hex
            )


            source_id = connection.execute(
                """
                INSERT INTO data_sources (
                    code,
                    name,
                    provider,
                    category,
                    access_method,
                    is_official,
                    is_active
                )
                VALUES (
                    %s,
                    'OH14 Counterparty Test Source',
                    'Origin Hut Test',
                    'company_intelligence',
                    'test',
                    TRUE,
                    TRUE
                )
                RETURNING id
                """,
                (
                    source_code,
                ),
            ).fetchone()[0]


            source_record_one = (
                connection.execute(
                    """
                    INSERT INTO source_records (
                        data_source_id,
                        external_id,
                        record_type,
                        content_hash,
                        payload
                    )
                    VALUES (
                        %s,
                        %s,
                        'organization_trade_activity_evidence',
                        %s,
                        %s::jsonb
                    )
                    RETURNING id
                    """,
                    (
                        source_id,
                        "evidence-1",
                        "a" * 64,
                        '{"source":"registry"}',
                    ),
                ).fetchone()[0]
            )


            source_record_two = (
                connection.execute(
                    """
                    INSERT INTO source_records (
                        data_source_id,
                        external_id,
                        record_type,
                        content_hash,
                        payload
                    )
                    VALUES (
                        %s,
                        %s,
                        'organization_trade_activity_evidence',
                        %s,
                        %s::jsonb
                    )
                    RETURNING id
                    """,
                    (
                        source_id,
                        "evidence-2",
                        "b" * 64,
                        '{"source":"company_website"}',
                    ),
                ).fetchone()[0]
            )


            activity_id = connection.execute(
                """
                INSERT INTO organization_trade_activities (
                    organization_id,
                    activity_type,
                    product_id,
                    hs_code_id,
                    market_country_id,
                    status,
                    confidence,
                    source_type,
                    canonical_source_record_id,
                    metadata
                )
                VALUES (
                    %s,
                    'manufactures',
                    %s,
                    %s,
                    %s,
                    'active',
                    1.0000,
                    'official_registry',
                    %s,
                    '{"test":true}'::jsonb
                )
                RETURNING id
                """,
                (
                    organization_id,
                    product_id,
                    hs_code_id,
                    market_country_id,
                    source_record_one,
                ),
            ).fetchone()[0]


            for source_record_id in (
                source_record_one,
                source_record_two,
            ):

                connection.execute(
                    """
                    INSERT INTO entity_source_links (
                        source_record_id,
                        entity_type,
                        entity_id,
                        relationship_type,
                        confidence,
                        metadata
                    )
                    VALUES (
                        %s,
                        'organization_trade_activity',
                        %s,
                        'official_reference',
                        1.0000,
                        '{}'::jsonb
                    )
                    """,
                    (
                        source_record_id,
                        activity_id,
                    ),
                )


            activity = connection.execute(
                """
                SELECT
                    organization_id,
                    activity_type,
                    product_id,
                    hs_code_id,
                    market_country_id,
                    confidence::double precision,
                    canonical_source_record_id

                FROM organization_trade_activities

                WHERE id = %s
                """,
                (
                    activity_id,
                ),
            ).fetchone()


            evidence_count = (
                connection.execute(
                    """
                    SELECT COUNT(*)

                    FROM entity_source_links

                    WHERE
                        entity_type =
                            'organization_trade_activity'

                        AND entity_id =
                            %s
                    """,
                    (
                        activity_id,
                    ),
                ).fetchone()[0]
            )


            self.assertEqual(
                activity[0],
                organization_id,
            )

            self.assertEqual(
                activity[1],
                "manufactures",
            )

            self.assertEqual(
                activity[2],
                product_id,
            )

            self.assertEqual(
                activity[3],
                hs_code_id,
            )

            self.assertEqual(
                activity[4],
                market_country_id,
            )

            self.assertAlmostEqual(
                activity[5],
                1.0,
                places=4,
            )

            self.assertEqual(
                activity[6],
                source_record_one,
            )

            self.assertEqual(
                evidence_count,
                2,
            )


    def test_confidence_and_date_constraints(
        self,
    ) -> None:

        assert DATABASE_URL is not None

        with psycopg.connect(
            DATABASE_URL
        ) as connection:

            organization_id = (
                self._create_organization(
                    connection
                )
            )

            hs_code_id = (
                self._ensure_hs(
                    connection
                )
            )


            with self.assertRaises(
                psycopg.errors.CheckViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO organization_trade_activities (
                            organization_id,
                            activity_type,
                            hs_code_id,
                            confidence
                        )
                        VALUES (
                            %s,
                            'exports',
                            %s,
                            1.1000
                        )
                        """,
                        (
                            organization_id,
                            hs_code_id,
                        ),
                    )


            with self.assertRaises(
                psycopg.errors.CheckViolation
            ):

                with connection.transaction():

                    connection.execute(
                        """
                        INSERT INTO organization_trade_activities (
                            organization_id,
                            activity_type,
                            hs_code_id,
                            valid_from,
                            valid_to
                        )
                        VALUES (
                            %s,
                            'exports',
                            %s,
                            DATE '2026-12-31',
                            DATE '2026-01-01'
                        )
                        """,
                        (
                            organization_id,
                            hs_code_id,
                        ),
                    )


if __name__ == "__main__":

    unittest.main()
