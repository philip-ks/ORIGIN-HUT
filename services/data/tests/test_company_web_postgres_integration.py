from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest

from pathlib import Path

import psycopg


DATA_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

SRC_ROOT = (
    DATA_ROOT
    / "src"
)

sys.path.insert(
    0,
    str(SRC_ROOT),
)


from connectors.company_web import (
    apply_source,
    evidence_result,
)

from connectors.comtrade_canonical import (
    database_url,
)


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
class CompanyWebPostgresIntegrationTest(
    unittest.TestCase
):

    SOURCE_CODE = (
        "oh14_company_web_integration_test"
    )

    LEGAL_NAME = (
        "OH14 Company Web Integration Test Private Limited"
    )


    @classmethod
    def setUpClass(
        cls,
    ) -> None:

        with psycopg.connect(
            database_url()
        ) as connection:

            database_name = connection.execute(
                """
                SELECT current_database()
                """
            ).fetchone()[0]


            if (
                "test"
                not in database_name.lower()
            ):

                raise RuntimeError(
                    "Refusing to run company-web integration "
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


            connection.execute(
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
                """
            )


    def setUp(
        self,
    ) -> None:

        self._cleanup()


    def tearDown(
        self,
    ) -> None:

        self._cleanup()


    def _cleanup(
        self,
    ) -> None:

        with psycopg.connect(
            database_url()
        ) as connection:

            organizations = connection.execute(
                """
                SELECT id
                FROM organizations
                WHERE legal_name LIKE %s
                """,
                (
                    "OH14 Company Web Integration Test%",
                ),
            ).fetchall()


            for row in organizations:

                connection.execute(
                    """
                    DELETE FROM organizations
                    WHERE id = %s
                    """,
                    (
                        row[0],
                    ),
                )


            source = connection.execute(
                """
                SELECT id
                FROM data_sources
                WHERE code = %s
                """,
                (
                    self.SOURCE_CODE,
                ),
            ).fetchone()


            if source is not None:

                source_id = source[0]

                connection.execute(
                    """
                    DELETE FROM source_records
                    WHERE data_source_id = %s
                    """,
                    (
                        source_id,
                    ),
                )

                connection.execute(
                    """
                    DELETE FROM ingestion_runs
                    WHERE data_source_id = %s
                    """,
                    (
                        source_id,
                    ),
                )

                connection.execute(
                    """
                    DELETE FROM data_sources
                    WHERE id = %s
                    """,
                    (
                        source_id,
                    ),
                )


    def test_repeated_identical_source_is_idempotent(
        self,
    ) -> None:

        raw = (
            b"<html><body>"
            b"Activated carbon manufacturer in India."
            b"</body></html>"
        )


        fetched = {
            "requestedUrl":
                "https://example.invalid/company",

            "finalUrl":
                "https://example.invalid/company",

            "httpStatus":
                200,

            "contentType":
                "text/html",

            "fetchedAt":
                "2026-09-29T00:00:00Z",

            "sha256":
                hashlib.sha256(
                    raw
                ).hexdigest(),

            "raw":
                raw,

            "text":
                "Activated carbon manufacturer in India.",
        }


        source = {
            "code":
                self.SOURCE_CODE,

            "name":
                "OH14 Company Web Integration Test",

            "provider":
                "Origin Hut Test",

            "url":
                "https://example.invalid/company",

            "official":
                True,

            "organization":
                {
                    "legalName":
                        self.LEGAL_NAME,

                    "tradingName":
                        "OH14 Test Carbon",

                    "countryIso2":
                        "IN",

                    "registrationNumber":
                        None,

                    "lei":
                        None,

                    "taxIdentifier":
                        None,

                    "website":
                        "https://example.invalid/company",

                    "roles":
                        [
                            "manufacturer",
                        ],
                },

            "activities":
                [
                    {
                        "activityType":
                            "manufactures",

                        "hsCode":
                            "380210",

                        "hsNomenclature":
                            "HS2022",

                        "marketCountryIso2":
                            "IN",

                        "confidence":
                            0.99,

                        "allTerms":
                            [
                                "activated carbon",
                            ],

                        "anyTerms":
                            [
                                "manufacturer",
                            ],

                        "sourceClaim":
                            "test claim",
                    }
                ],
        }


        evidence = [
            {
                "activityType":
                    "manufactures",

                "hsCode":
                    "380210",

                **evidence_result(
                    fetched[
                        "text"
                    ],
                    source[
                        "activities"
                    ][0],
                ),
            }
        ]


        with tempfile.TemporaryDirectory() as temp_directory:

            temp = Path(
                temp_directory
            )

            raw_path = (
                temp
                / "page.html"
            )

            manifest_path = (
                temp
                / "manifest.json"
            )

            raw_path.write_bytes(
                raw
            )

            manifest_path.write_text(
                "{}",
                encoding="utf-8",
            )


            artifacts = {
                "raw":
                    raw_path,

                "manifest":
                    manifest_path,
            }


            with psycopg.connect(
                database_url()
            ) as connection:

                first = apply_source(
                    connection,
                    source,
                    fetched,
                    evidence,
                    artifacts,
                    run_id=
                        "oh14-company-web-test-1",
                )


            second_source = {
                **source,

                "organization":
                    {
                        **source[
                            "organization"
                        ],

                        "legalName":
                            "OH14 Company Web Integration Test Pvt. Ltd.",
                    },
            }


            with psycopg.connect(
                database_url()
            ) as connection:

                second = apply_source(
                    connection,
                    second_source,
                    fetched,
                    evidence,
                    artifacts,
                    run_id=
                        "oh14-company-web-test-2",
                )


            with psycopg.connect(
                database_url()
            ) as connection:

                source_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM source_records sr
                    JOIN data_sources ds
                      ON ds.id = sr.data_source_id
                    WHERE ds.code = %s
                    """,
                    (
                        self.SOURCE_CODE,
                    ),
                ).fetchone()[0]


                organization_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM organizations
                    WHERE legal_name LIKE
                        'OH14 Company Web Integration Test%'
                    """
                ).fetchone()[0]


                canonical_name = connection.execute(
                    """
                    SELECT legal_name
                    FROM organizations
                    WHERE legal_name LIKE
                        'OH14 Company Web Integration Test%'
                    LIMIT 1
                    """
                ).fetchone()[0]


                alias_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM organization_aliases oa
                    JOIN organizations o
                      ON o.id = oa.organization_id
                    WHERE o.legal_name = %s
                    """,
                    (
                        self.LEGAL_NAME,
                    ),
                ).fetchone()[0]


                activity_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM organization_trade_activities ota
                    JOIN organizations o
                      ON o.id = ota.organization_id
                    WHERE
                        o.legal_name = %s
                        AND ota.activity_type = 'manufactures'
                    """,
                    (
                        self.LEGAL_NAME,
                    ),
                ).fetchone()[0]


                ingestion_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM ingestion_runs ir
                    JOIN data_sources ds
                      ON ds.id = ir.data_source_id
                    WHERE ds.code = %s
                    """,
                    (
                        self.SOURCE_CODE,
                    ),
                ).fetchone()[0]


        self.assertEqual(
            first[
                "sourceRecordAction"
            ],
            "inserted",
        )

        self.assertEqual(
            second[
                "sourceRecordAction"
            ],
            "reused",
        )

        self.assertEqual(
            source_count,
            1,
        )

        self.assertEqual(
            organization_count,
            1,
        )

        self.assertEqual(
            activity_count,
            1,
        )

        self.assertEqual(
            ingestion_count,
            2,
        )


        self.assertEqual(
            canonical_name,
            self.LEGAL_NAME,
        )


        self.assertGreaterEqual(
            alias_count,
            3,
        )


        self.assertEqual(
            second[
                "organizationResolutionMethod"
            ],
            "alias",
        )


if __name__ == "__main__":

    unittest.main()
