from __future__ import annotations

import copy
import os
import sys
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


from connectors.comtrade import (
    normalize_record,
)

from connectors.comtrade_canonical import (
    SOURCE_CODE,
    canonicalize_trade_observation,
    database_url,
)


RUN_DATABASE_INTEGRATION = (
    os.environ.get(
        "ORIGINHUT_RUN_DB_INTEGRATION"
    )
    == "1"
)


def base_record() -> dict:

    return {
        "typeCode":
            "C",

        "freqCode":
            "A",

        "refPeriodId":
            20240101,

        "refYear":
            2024,

        "refMonth":
            52,

        "period":
            "2024",

        "reporterCode":
            699,

        "reporterISO":
            "IND",

        "reporterDesc":
            "India",

        "flowCode":
            "X",

        "flowDesc":
            "Export",

        "partnerCode":
            784,

        "partnerISO":
            "ARE",

        "partnerDesc":
            "United Arab Emirates",

        "partner2Code":
            0,

        "partner2ISO":
            "W00",

        "partner2Desc":
            "World",

        "classificationCode":
            "H6",

        "classificationSearchCode":
            "HS",

        "isOriginalClassification":
            True,

        "cmdCode":
            "380210",

        "cmdDesc":
            "Carbon; activated",

        "aggrLevel":
            6,

        "isLeaf":
            True,

        "customsCode":
            "C00",

        "customsDesc":
            "TOTAL CPC",

        "mosCode":
            "0",

        "motCode":
            0,

        "motDesc":
            "TOTAL MOT",

        "qtyUnitCode":
            8,

        "qtyUnitAbbr":
            "kg",

        "qty":
            4268940.0,

        "isQtyEstimated":
            False,

        "altQtyUnitCode":
            8,

        "altQtyUnitAbbr":
            "kg",

        "altQty":
            4268940.0,

        "isAltQtyEstimated":
            False,

        "netWgt":
            4268940.0,

        "isNetWgtEstimated":
            False,

        "grossWgt":
            0.0,

        "isGrossWgtEstimated":
            False,

        "cifvalue":
            None,

        "fobvalue":
            6410583.797,

        "primaryValue":
            6410583.797,

        "legacyEstimationFlag":
            0,

        "isReported":
            False,

        "isAggregate":
            True,
    }


@unittest.skipUnless(
    RUN_DATABASE_INTEGRATION,
    "Database integration tests are disabled.",
)
class ComtradePostgresIntegrationTest(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ) -> None:

        with psycopg.connect(
            database_url()
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
                    "Refusing to run Comtrade integration "
                    "tests against a non-test database: "
                    + database_name
                )


            with connection.transaction():

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
                        iso3 =
                            EXCLUDED.iso3,
                        numeric_code =
                            EXCLUDED.numeric_code,
                        name =
                            EXCLUDED.name,
                        official_name =
                            EXCLUDED.official_name,
                        is_active =
                            TRUE
                    """
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
                        'AE',
                        'ARE',
                        '784',
                        'United Arab Emirates',
                        'United Arab Emirates',
                        TRUE
                    )
                    ON CONFLICT (iso2)
                    DO UPDATE SET
                        iso3 =
                            EXCLUDED.iso3,
                        numeric_code =
                            EXCLUDED.numeric_code,
                        name =
                            EXCLUDED.name,
                        official_name =
                            EXCLUDED.official_name,
                        is_active =
                            TRUE
                    """
                )


                connection.execute(
                    """
                    INSERT INTO currencies (
                        code,
                        name,
                        symbol,
                        decimal_places,
                        is_active
                    )
                    VALUES (
                        'USD',
                        'US Dollar',
                        '$',
                        2,
                        TRUE
                    )
                    ON CONFLICT (code)
                    DO UPDATE SET
                        name =
                            EXCLUDED.name,
                        decimal_places =
                            EXCLUDED.decimal_places,
                        is_active =
                            TRUE
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
                        level =
                            EXCLUDED.level,
                        description =
                            EXCLUDED.description,
                        valid_from =
                            EXCLUDED.valid_from
                    """
                )


    def setUp(
        self,
    ) -> None:

        self._clean_comtrade()


    def tearDown(
        self,
    ) -> None:

        self._clean_comtrade()


    def _clean_comtrade(
        self,
    ) -> None:

        with psycopg.connect(
            database_url()
        ) as connection:

            with connection.transaction():

                source_row = (
                    connection.execute(
                        """
                        SELECT id
                        FROM data_sources
                        WHERE code = %s
                        """,
                        (
                            SOURCE_CODE,
                        ),
                    ).fetchone()
                )


                connection.execute(
                    """
                    DELETE FROM trade_flows
                    WHERE
                        metadata ->> 'sourceSystem'
                            = 'un_comtrade'
                    """
                )


                if source_row is None:
                    return


                source_id = source_row[0]


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


    def _apply(
        self,
        record: dict,
        *,
        run_id: str,
    ) -> tuple[
        dict,
        dict,
    ]:

        normalized = normalize_record(
            record,
            request_url=
                f"https://example.invalid/{run_id}",

            raw_artifact_hash=
                "f" * 64,

            run_id=
                run_id,
        )


        result = canonicalize_trade_observation(
            record,
            normalized,
            artifact_run_id=
                run_id,

            request_url=
                f"https://example.invalid/{run_id}",

            raw_path=
                Path(
                    "storage"
                )
                / "test"
                / run_id
                / "response.json",

            parquet_paths=[
                Path(
                    "storage"
                )
                / "test"
                / run_id
                / "observation.parquet"
            ],
        )


        return (
            normalized,
            result,
        )


    def test_revised_observation_creates_new_source_version(
        self,
    ) -> None:

        first = base_record()


        first_normalized, first_result = (
            self._apply(
                first,
                run_id=
                    "integration-revision-1",
            )
        )


        revised = copy.deepcopy(
            first
        )

        revised[
            "primaryValue"
        ] = 6500000.123

        revised[
            "fobvalue"
        ] = 6500000.123

        revised[
            "qty"
        ] = 4300000.0

        revised[
            "netWgt"
        ] = 4300000.0


        revised_normalized, revised_result = (
            self._apply(
                revised,
                run_id=
                    "integration-revision-2",
            )
        )


        self.assertEqual(
            first_normalized[
                "sourceExternalId"
            ],
            revised_normalized[
                "sourceExternalId"
            ],
        )


        self.assertNotEqual(
            first_normalized[
                "sourceContentHash"
            ],
            revised_normalized[
                "sourceContentHash"
            ],
        )


        self.assertEqual(
            first_result[
                "sourceRecordAction"
            ],
            "inserted",
        )


        self.assertEqual(
            revised_result[
                "sourceRecordAction"
            ],
            "inserted",
        )


        self.assertEqual(
            first_result[
                "tradeFlowAction"
            ],
            "inserted",
        )


        self.assertEqual(
            revised_result[
                "tradeFlowAction"
            ],
            "updated",
        )


        self.assertNotEqual(
            first_result[
                "sourceRecordId"
            ],
            revised_result[
                "sourceRecordId"
            ],
        )


        self.assertEqual(
            first_result[
                "tradeFlowId"
            ],
            revised_result[
                "tradeFlowId"
            ],
        )


        with psycopg.connect(
            database_url()
        ) as connection:

            source_count = (
                connection.execute(
                    """
                    SELECT COUNT(*)

                    FROM source_records sr

                    JOIN data_sources ds
                        ON ds.id =
                           sr.data_source_id

                    WHERE
                        ds.code = %s
                        AND sr.external_id = %s
                    """,
                    (
                        SOURCE_CODE,
                        first_normalized[
                            "sourceExternalId"
                        ],
                    ),
                ).fetchone()[0]
            )


            flow_row = (
                connection.execute(
                    """
                    SELECT
                        id::text,
                        canonical_source_record_id::text,
                        trade_value,
                        quantity

                    FROM trade_flows

                    WHERE
                        metadata ->> 'sourceSystem'
                            = 'un_comtrade'

                        AND metadata ->> 'sourceExternalId'
                            = %s
                    """,
                    (
                        first_normalized[
                            "sourceExternalId"
                        ],
                    ),
                ).fetchone()
            )


            provenance_count = (
                connection.execute(
                    """
                    SELECT COUNT(*)

                    FROM entity_source_links

                    WHERE
                        entity_type =
                            'trade_flow'

                        AND entity_id =
                            %s
                    """,
                    (
                        revised_result[
                            "tradeFlowId"
                        ],
                    ),
                ).fetchone()[0]
            )


        self.assertEqual(
            source_count,
            2,
        )


        self.assertIsNotNone(
            flow_row
        )


        self.assertEqual(
            flow_row[0],
            revised_result[
                "tradeFlowId"
            ],
        )


        self.assertEqual(
            flow_row[1],
            revised_result[
                "sourceRecordId"
            ],
        )


        self.assertAlmostEqual(
            float(
                flow_row[2]
            ),
            6500000.123,
            places=3,
        )


        self.assertAlmostEqual(
            float(
                flow_row[3]
            ),
            4300000.0,
            places=3,
        )


        self.assertEqual(
            provenance_count,
            2,
        )


    def test_world_partner_stays_null_in_postgres(
        self,
    ) -> None:

        record = base_record()

        record[
            "partnerCode"
        ] = 0

        record[
            "partnerISO"
        ] = "W00"

        record[
            "partnerDesc"
        ] = "World"


        normalized, result = self._apply(
            record,
            run_id=
                "integration-world",
        )


        self.assertIsNone(
            normalized[
                "partnerISO3"
            ]
        )


        with psycopg.connect(
            database_url()
        ) as connection:

            row = connection.execute(
                """
                SELECT
                    tf.partner_country_id,
                    tf.metadata ->>
                        'sourcePartnerCode',

                    sr.payload ->>
                        'partnerISO'

                FROM trade_flows tf

                JOIN source_records sr
                    ON sr.id =
                       tf.canonical_source_record_id

                WHERE tf.id = %s
                """,
                (
                    result[
                        "tradeFlowId"
                    ],
                ),
            ).fetchone()


        self.assertIsNotNone(
            row
        )


        self.assertIsNone(
            row[0]
        )


        self.assertEqual(
            row[1],
            "0",
        )


        self.assertEqual(
            row[2],
            "W00",
        )


    def test_monthly_period_reaches_postgres_correctly(
        self,
    ) -> None:

        record = base_record()

        record[
            "freqCode"
        ] = "M"

        record[
            "refPeriodId"
        ] = 20240201

        record[
            "refMonth"
        ] = 2

        record[
            "period"
        ] = "202402"


        normalized, result = self._apply(
            record,
            run_id=
                "integration-monthly",
        )


        self.assertEqual(
            normalized[
                "periodStart"
            ].isoformat(),
            "2024-02-01",
        )


        self.assertEqual(
            normalized[
                "periodEnd"
            ].isoformat(),
            "2024-02-29",
        )


        self.assertEqual(
            normalized[
                "periodType"
            ],
            "monthly",
        )


        with psycopg.connect(
            database_url()
        ) as connection:

            row = connection.execute(
                """
                SELECT
                    period_start::text,
                    period_end::text,
                    period_type

                FROM trade_flows

                WHERE id = %s
                """,
                (
                    result[
                        "tradeFlowId"
                    ],
                ),
            ).fetchone()


        self.assertEqual(
            row,
            (
                "2024-02-01",
                "2024-02-29",
                "monthly",
            ),
        )


if __name__ == "__main__":

    unittest.main()
