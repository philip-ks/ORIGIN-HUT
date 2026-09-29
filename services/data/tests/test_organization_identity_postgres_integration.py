from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import psycopg

DATA_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = DATA_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from connectors.comtrade_canonical import database_url
from identity.organizations import (
    IdentityResolutionError,
    normalize_organization_name,
    record_source_alias,
    resolve_organization_identity,
)

RUN_DATABASE_INTEGRATION = (
    os.environ.get("ORIGINHUT_RUN_DB_INTEGRATION") == "1"
)


@unittest.skipUnless(
    RUN_DATABASE_INTEGRATION,
    "Database integration tests are disabled.",
)
class OrganizationIdentityPostgresIntegrationTest(
    unittest.TestCase
):

    PREFIX = "OH14 Identity Test"

    @classmethod
    def setUpClass(cls) -> None:
        with psycopg.connect(database_url()) as connection:
            database_name = connection.execute(
                "SELECT current_database()"
            ).fetchone()[0]

            if "test" not in database_name.lower():
                raise RuntimeError(
                    "Refusing to run identity integration "
                    "tests against a non-test database: "
                    + database_name
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
                VALUES (
                    'IN',
                    'IND',
                    '356',
                    'India',
                    'Republic of India',
                    TRUE
                )
                ON CONFLICT (iso2)
                DO UPDATE SET
                    iso3 = EXCLUDED.iso3,
                    numeric_code = EXCLUDED.numeric_code,
                    name = EXCLUDED.name,
                    official_name = EXCLUDED.official_name,
                    is_active = TRUE
                """
            )

    def setUp(self) -> None:
        self._cleanup()

    def tearDown(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        with psycopg.connect(database_url()) as connection:
            connection.execute(
                """
                DELETE FROM organizations
                WHERE legal_name LIKE %s
                """,
                (self.PREFIX + "%",),
            )


            sources = connection.execute(
                """
                SELECT id
                FROM data_sources
                WHERE code LIKE
                    'oh14_identity_alias_source_%'
                """
            ).fetchall()


            for source in sources:

                connection.execute(
                    """
                    DELETE FROM source_records
                    WHERE data_source_id = %s
                    """,
                    (
                        source[0],
                    ),
                )


                connection.execute(
                    """
                    DELETE FROM data_sources
                    WHERE id = %s
                    """,
                    (
                        source[0],
                    ),
                )

    def _country_id(
        self,
        connection: psycopg.Connection,
    ) -> str:
        return str(
            connection.execute(
                """
                SELECT id
                FROM countries
                WHERE iso2 = 'IN'
                """
            ).fetchone()[0]
        )

    def test_private_limited_variant_resolves_by_alias(
        self,
    ) -> None:
        with psycopg.connect(database_url()) as connection:
            country_id = self._country_id(connection)

            organization_id = str(
                connection.execute(
                    """
                    INSERT INTO organizations (
                        legal_name,
                        country_id,
                        status
                    )
                    VALUES (
                        %s,
                        %s,
                        'active'
                    )
                    RETURNING id
                    """,
                    (
                        self.PREFIX + " Private Limited",
                        country_id,
                    ),
                ).fetchone()[0]
            )

            canonical = normalize_organization_name(
                connection,
                self.PREFIX + " Private Limited",
            )

            variant = normalize_organization_name(
                connection,
                self.PREFIX + " Pvt. Ltd.",
            )

            self.assertEqual(canonical, variant)

            result = resolve_organization_identity(
                connection,
                {
                    "legalName":
                        self.PREFIX + " Pvt. Ltd.",
                    "tradingName":
                        None,
                    "registrationNumber":
                        None,
                    "lei":
                        None,
                    "taxIdentifier":
                        None,
                    "website":
                        None,
                },
                country_id,
            )

            self.assertEqual(
                result.organization_id,
                organization_id,
            )
            self.assertEqual(
                result.method,
                "alias",
            )

    def test_literal_alias_variants_preserve_separate_provenance(
        self,
    ) -> None:

        with psycopg.connect(
            database_url()
        ) as connection:

            country_id = self._country_id(
                connection
            )


            organization_id = str(
                connection.execute(
                    """
                    INSERT INTO organizations (
                        legal_name,
                        country_id,
                        status
                    )
                    VALUES (
                        %s,
                        %s,
                        'active'
                    )
                    RETURNING id
                    """,
                    (
                        self.PREFIX
                        + " Private Limited",
                        country_id,
                    ),
                ).fetchone()[0]
            )


            source_records = []


            for suffix in (
                "a",
                "b",
            ):

                source_id = connection.execute(
                    """
                    INSERT INTO data_sources (
                        code,
                        name,
                        category,
                        access_method,
                        is_official,
                        is_active
                    )
                    VALUES (
                        %s,
                        %s,
                        'company_intelligence',
                        'test',
                        TRUE,
                        TRUE
                    )
                    RETURNING id
                    """,
                    (
                        "oh14_identity_alias_source_"
                        + suffix,

                        "OH14 Identity Alias Source "
                        + suffix.upper(),
                    ),
                ).fetchone()[0]


                source_record_id = str(
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
                            'company_official_web_page',
                            %s,
                            '{}'::jsonb
                        )
                        RETURNING id
                        """,
                        (
                            source_id,
                            "identity-alias-"
                            + suffix,
                            "identity-alias-hash-"
                            + suffix,
                        ),
                    ).fetchone()[0]
                )


                source_records.append(
                    (
                        suffix,
                        source_record_id,
                    )
                )


            first_alias_id = record_source_alias(
                connection,
                organization_id=
                    organization_id,
                alias=
                    self.PREFIX
                    + " Private Limited",
                source_record_id=
                    source_records[0][1],
                source_code=
                    "oh14_identity_alias_source_a",
            )


            second_alias_id = record_source_alias(
                connection,
                organization_id=
                    organization_id,
                alias=
                    self.PREFIX
                    + " Pvt. Ltd.",
                source_record_id=
                    source_records[1][1],
                source_code=
                    "oh14_identity_alias_source_b",
            )


            self.assertNotEqual(
                first_alias_id,
                second_alias_id,
            )


            rows = connection.execute(
                """
                SELECT
                    oa.alias,
                    oa.normalized_alias,
                    ds.code
                FROM organization_aliases oa
                JOIN source_records sr
                  ON sr.id =
                     oa.source_record_id
                JOIN data_sources ds
                  ON ds.id =
                     sr.data_source_id
                WHERE
                    oa.organization_id = %s
                    AND oa.alias_type =
                        'source_name'
                ORDER BY oa.alias
                """,
                (
                    organization_id,
                ),
            ).fetchall()


            self.assertEqual(
                len(
                    rows
                ),
                2,
            )


            normalized_values = {
                row[1]
                for row
                in rows
            }


            self.assertEqual(
                len(
                    normalized_values
                ),
                1,
            )


            provenance = {
                row[0]:
                    row[2]
                for row
                in rows
            }


            self.assertEqual(
                provenance[
                    self.PREFIX
                    + " Private Limited"
                ],
                "oh14_identity_alias_source_a",
            )


            self.assertEqual(
                provenance[
                    self.PREFIX
                    + " Pvt. Ltd."
                ],
                "oh14_identity_alias_source_b",
            )


    def test_conflicting_strong_identifiers_stop(
        self,
    ) -> None:
        with psycopg.connect(database_url()) as connection:
            country_id = self._country_id(connection)

            connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    country_id,
                    lei,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    '5493001KJTIIGC8Y1R12',
                    'active'
                )
                """,
                (
                    self.PREFIX + " LEI",
                    country_id,
                ),
            )

            connection.execute(
                """
                INSERT INTO organizations (
                    legal_name,
                    country_id,
                    registration_number,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    'REG-IDENTITY-002',
                    'active'
                )
                """,
                (
                    self.PREFIX + " Registration",
                    country_id,
                ),
            )

            with self.assertRaises(
                IdentityResolutionError
            ):
                resolve_organization_identity(
                    connection,
                    {
                        "legalName":
                            self.PREFIX + " Incoming",
                        "tradingName":
                            None,
                        "registrationNumber":
                            "REG-IDENTITY-002",
                        "lei":
                            "5493001KJTIIGC8Y1R12",
                        "taxIdentifier":
                            None,
                        "website":
                            None,
                    },
                    country_id,
                )

    def test_ambiguous_alias_does_not_auto_merge(
        self,
    ) -> None:
        with psycopg.connect(database_url()) as connection:
            country_id = self._country_id(connection)

            first_id = str(
                connection.execute(
                    """
                    INSERT INTO organizations (
                        legal_name,
                        country_id,
                        status
                    )
                    VALUES (%s, %s, 'active')
                    RETURNING id
                    """,
                    (
                        self.PREFIX + " Alpha",
                        country_id,
                    ),
                ).fetchone()[0]
            )

            second_id = str(
                connection.execute(
                    """
                    INSERT INTO organizations (
                        legal_name,
                        country_id,
                        status
                    )
                    VALUES (%s, %s, 'active')
                    RETURNING id
                    """,
                    (
                        self.PREFIX + " Beta",
                        country_id,
                    ),
                ).fetchone()[0]
            )

            normalized = normalize_organization_name(
                connection,
                self.PREFIX + " Shared",
            )

            for organization_id in (
                first_id,
                second_id,
            ):
                connection.execute(
                    """
                    INSERT INTO organization_aliases (
                        organization_id,
                        alias,
                        normalized_alias,
                        alias_type
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        'manual'
                    )
                    """,
                    (
                        organization_id,
                        self.PREFIX + " Shared",
                        normalized,
                    ),
                )

            with self.assertRaises(
                IdentityResolutionError
            ):
                resolve_organization_identity(
                    connection,
                    {
                        "legalName":
                            self.PREFIX + " Shared",
                        "tradingName":
                            None,
                        "registrationNumber":
                            None,
                        "lei":
                            None,
                        "taxIdentifier":
                            None,
                        "website":
                            None,
                    },
                    country_id,
                )


if __name__ == "__main__":
    unittest.main()
