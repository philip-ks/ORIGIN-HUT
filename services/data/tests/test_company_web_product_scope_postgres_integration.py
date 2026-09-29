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
    CompanyWebError,
    apply_source,
    evidence_result,
    validate_config,
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
class CompanyWebProductScopePostgresIntegrationTest(
    unittest.TestCase
):

    PRODUCT_ID = (
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    )

    SOURCE_CODE = (
        "oh14_product_scope_company_web_test"
    )

    LEGAL_NAME = (
        "OH14 Product Scope Company Private Limited"
    )


    @classmethod
    def setUpClass(
        cls,
    ) -> None:

        with psycopg.connect(
            database_url()
        ) as connection:

            database_name = connection.execute(
                "SELECT current_database()"
            ).fetchone()[0]

            if "test" not in database_name.lower():
                raise RuntimeError(
                    "Refusing to run product-scope integration "
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
                    description = EXCLUDED.description
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

            connection.execute(
                "DELETE FROM products WHERE id = %s",
                (
                    self.PRODUCT_ID,
                ),
            )

            connection.execute(
                "DELETE FROM organizations WHERE legal_name = %s",
                (
                    self.LEGAL_NAME,
                ),
            )

            source = connection.execute(
                "SELECT id FROM data_sources WHERE code = %s",
                (
                    self.SOURCE_CODE,
                ),
            ).fetchone()

            if source is not None:

                connection.execute(
                    "DELETE FROM source_records WHERE data_source_id = %s",
                    (
                        source[0],
                    ),
                )

                connection.execute(
                    "DELETE FROM ingestion_runs WHERE data_source_id = %s",
                    (
                        source[0],
                    ),
                )

                connection.execute(
                    "DELETE FROM data_sources WHERE id = %s",
                    (
                        source[0],
                    ),
                )


    def _seed_product(
        self,
        *,
        classified: bool,
    ) -> None:

        with psycopg.connect(
            database_url()
        ) as connection:

            connection.execute(
                """
                INSERT INTO products (
                    id,
                    name,
                    description,
                    attributes,
                    metadata,
                    is_active
                )
                VALUES (
                    %s,
                    'Activated Carbon',
                    'Canonical product-first OH14.6 proof product.',
                    %s::jsonb,
                    %s::jsonb,
                    TRUE
                )
                """,
                (
                    self.PRODUCT_ID,
                    '{"form":"activated carbon"}',
                    '{"proof":"OH14.6"}',
                ),
            )

            if classified:

                connection.execute(
                    """
                    INSERT INTO product_hs_classifications (
                        product_id,
                        hs_code_id,
                        is_primary,
                        confidence,
                        decision_method,
                        decision_notes
                    )
                    SELECT
                        %s,
                        h.id,
                        TRUE,
                        1.0000,
                        'explicit_proof',
                        'OH14.6 product-first connector proof'
                    FROM hs_codes h
                    WHERE
                        h.nomenclature = 'HS2022'
                        AND h.code = '380210'
                    """,
                    (
                        self.PRODUCT_ID,
                    ),
                )


    def _source(
        self,
    ) -> dict:

        return validate_config(
            {
                "sources":
                    [
                        {
                            "code":
                                self.SOURCE_CODE,

                            "name":
                                "OH14 Product Scope Source",

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

                                    "countryIso2":
                                        "IN",

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

                                        "productId":
                                            self.PRODUCT_ID,

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
                                            "product-scoped proof claim",
                                    }
                                ],
                        }
                    ]
            }
        )["sources"][0]


    def _fetched(
        self,
    ) -> dict:

        raw = (
            b"<html><body>"
            b"Activated carbon manufacturer in India."
            b"</body></html>"
        )

        return {
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


    def _evidence(
        self,
        source: dict,
        fetched: dict,
    ) -> list[dict]:

        return [
            {
                "activityType":
                    "manufactures",

                "hsCode":
                    "380210",

                "productId":
                    self.PRODUCT_ID,

                **evidence_result(
                    fetched["text"],
                    source["activities"][0],
                ),
            }
        ]


    def test_product_scoped_activity_is_canonicalized(
        self,
    ) -> None:

        self._seed_product(
            classified=True,
        )

        source = self._source()
        fetched = self._fetched()

        with tempfile.TemporaryDirectory() as directory:

            root = Path(directory)
            raw_path = root / "page.html"
            manifest_path = root / "manifest.json"

            raw_path.write_bytes(
                fetched["raw"]
            )

            manifest_path.write_text(
                "{}",
                encoding="utf-8",
            )

            with psycopg.connect(
                database_url()
            ) as connection:

                result = apply_source(
                    connection,
                    source,
                    fetched,
                    self._evidence(
                        source,
                        fetched,
                    ),
                    {
                        "raw": raw_path,
                        "manifest": manifest_path,
                    },
                    run_id="oh14-product-scope-test",
                )

        with psycopg.connect(
            database_url()
        ) as connection:

            row = connection.execute(
                """
                SELECT
                    ota.product_id::text,
                    h.code,
                    ota.metadata ->> 'subject'
                FROM organization_trade_activities ota
                JOIN hs_codes h
                  ON h.id = ota.hs_code_id
                WHERE ota.id = %s
                """,
                (
                    result["activities"][0]["id"],
                ),
            ).fetchone()

        self.assertEqual(
            row,
            (
                self.PRODUCT_ID,
                "380210",
                "product_hs",
            ),
        )


    def test_product_scope_requires_matching_classification(
        self,
    ) -> None:

        self._seed_product(
            classified=False,
        )

        source = self._source()
        fetched = self._fetched()

        with tempfile.TemporaryDirectory() as directory:

            root = Path(directory)
            raw_path = root / "page.html"
            manifest_path = root / "manifest.json"

            raw_path.write_bytes(
                fetched["raw"]
            )

            manifest_path.write_text(
                "{}",
                encoding="utf-8",
            )

            with psycopg.connect(
                database_url()
            ) as connection:

                with self.assertRaises(
                    CompanyWebError
                ):

                    apply_source(
                        connection,
                        source,
                        fetched,
                        self._evidence(
                            source,
                            fetched,
                        ),
                        {
                            "raw": raw_path,
                            "manifest": manifest_path,
                        },
                        run_id="oh14-product-scope-unclassified",
                    )


if __name__ == "__main__":

    unittest.main()
