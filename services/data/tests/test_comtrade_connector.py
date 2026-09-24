from __future__ import annotations

import copy
import sys
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


from connectors.comtrade import (
    normalize_record,
)

from storage.manifests import (
    sha256_json,
)


SAMPLE = {
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


class ComtradeConnectorTest(
    unittest.TestCase
):

    def test_country_partner_normalization(
        self,
    ) -> None:

        normalized = normalize_record(
            SAMPLE,
            request_url=
                "https://example.invalid/comtrade",

            raw_artifact_hash=
                "a" * 64,

            run_id=
                "test-run",
        )


        self.assertEqual(
            normalized[
                "reporterISO3"
            ],
            "IND",
        )

        self.assertEqual(
            normalized[
                "partnerISO3"
            ],
            "ARE",
        )

        self.assertEqual(
            normalized[
                "flowDirection"
            ],
            "export",
        )

        self.assertEqual(
            normalized[
                "hsCode"
            ],
            "380210",
        )

        self.assertEqual(
            normalized[
                "sourceContentHash"
            ],
            sha256_json(
                SAMPLE
            ),
        )


    def test_world_partner_becomes_null(
        self,
    ) -> None:

        record = copy.deepcopy(
            SAMPLE
        )

        record[
            "partnerCode"
        ] = 0

        record[
            "partnerISO"
        ] = "W00"

        record[
            "partnerDesc"
        ] = "World"


        normalized = normalize_record(
            record,
            request_url=
                "https://example.invalid/comtrade",

            raw_artifact_hash=
                "b" * 64,

            run_id=
                "test-world",
        )


        self.assertIsNone(
            normalized[
                "partnerISO3"
            ]
        )


if __name__ == "__main__":

    unittest.main()
