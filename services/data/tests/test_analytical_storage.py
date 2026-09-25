from __future__ import annotations

import json
import sys
import tempfile
import unittest

from pathlib import Path


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


import duckdb

from storage.manifests import (
    artifact_descriptor,
    build_manifest,
    sha256_file,
    write_json_atomic,
)

from storage.parquet import (
    TRADE_SCHEMA_VERSION,
    write_trade_partitions,
)


class AnalyticalStorageTest(
    unittest.TestCase
):

    def test_trade_parquet_and_manifest(
        self,
    ) -> None:

        with tempfile.TemporaryDirectory() as temporary:

            root = Path(
                temporary
            )

            raw_directory = (
                root
                / "imports"
                / "comtrade"
                / "test-run"
            )

            raw_directory.mkdir(
                parents=True
            )


            raw_payload = (
                b'{"count":1,"data":[{"cmdCode":"380210"}]}\n'
            )


            raw_path = (
                raw_directory
                / "response.json"
            )

            raw_path.write_bytes(
                raw_payload
            )


            raw_hash = sha256_file(
                raw_path
            )


            records = [
                {
                    "sourceSystem":
                        "un_comtrade",

                    "sourceExternalId":
                        "test-observation-1",

                    "sourceContentHash":
                        raw_hash,

                    "reporterISO3":
                        "IND",

                    "partnerISO3":
                        "ARE",

                    "flowDirection":
                        "export",

                    "classificationCode":
                        "H6",

                    "hsCode":
                        "380210",

                    "referenceYear":
                        2024,

                    "periodStart":
                        "2024-01-01",

                    "periodEnd":
                        "2024-12-31",

                    "periodType":
                        "annual",

                    "quantity":
                        "4268940",

                    "quantityUnit":
                        "kg",

                    "netWeightKg":
                        "4268940",

                    "grossWeightKg":
                        "0",

                    "tradeValueUsd":
                        "6410583.797",

                    "fobValueUsd":
                        "6410583.797",

                    "cifValueUsd":
                        None,

                    "customsCode":
                        "C00",

                    "transportModeCode":
                        "0",

                    "isAggregate":
                        True,

                    "isReported":
                        False,

                    "isQtyEstimated":
                        False,

                    "isNetWeightEstimated":
                        False,

                    "isGrossWeightEstimated":
                        False,

                    "rawMetadata":
                        {
                            "test":
                                True
                        },
                }
            ]


            parquet_paths = (
                write_trade_partitions(
                    records,
                    root / "parquet",
                )
            )


            self.assertEqual(
                len(parquet_paths),
                1,
            )


            parquet_path = (
                parquet_paths[0]
            )


            self.assertTrue(
                parquet_path.is_file()
            )


            expected_fragment = (
                "trade/"
                "year=2024/"
                "reporter=IND/"
                "flow=export/"
                "hs=380210/"
            )


            self.assertIn(
                expected_fragment,
                parquet_path.as_posix(),
            )


            connection = (
                duckdb.connect()
            )

            try:

                row = connection.execute(
                    """
                    SELECT
                        COUNT(*) AS rows,
                        SUM("tradeValueUsd")
                            AS trade_value
                    FROM read_parquet(?)
                    """,
                    [
                        str(
                            parquet_path
                        )
                    ],
                ).fetchone()

            finally:

                connection.close()


            self.assertEqual(
                row[0],
                1,
            )


            self.assertAlmostEqual(
                float(
                    row[1]
                ),
                6410583.797,
                places=3,
            )


            manifest = build_manifest(
                source_code=
                    "un_comtrade_trade",

                run_id=
                    "test-run",

                request={
                    "reporterCode":
                        699,

                    "partnerCode":
                        784,

                    "cmdCode":
                        "380210",

                    "period":
                        "2024",
                },

                raw_artifacts=[
                    artifact_descriptor(
                        raw_path,
                        root=root,
                    )
                ],

                parquet_artifacts=[
                    artifact_descriptor(
                        parquet_path,
                        root=root,
                    )
                ],

                record_count=1,

                schema_version=
                    TRADE_SCHEMA_VERSION,

                metadata={
                    "test":
                        True
                },
            )


            manifest_path = (
                raw_directory
                / "manifest.json"
            )


            write_json_atomic(
                manifest_path,
                manifest,
            )


            loaded = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )


            self.assertEqual(
                loaded[
                    "recordCount"
                ],
                1,
            )


            self.assertEqual(
                loaded[
                    "schemaVersion"
                ],
                TRADE_SCHEMA_VERSION,
            )


            self.assertEqual(
                loaded[
                    "rawArtifacts"
                ][0][
                    "sha256"
                ],
                raw_hash,
            )


if __name__ == "__main__":

    unittest.main()
