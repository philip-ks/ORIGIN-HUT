from __future__ import annotations

import copy
import sys
import unittest

from pathlib import Path
from types import SimpleNamespace


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
    ConnectorError,
    normalize_record,
    resolve_access_mode,
    resolve_max_records,
    select_exact_record,
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


    def test_access_mode_resolution(
        self,
    ) -> None:

        self.assertEqual(
            resolve_access_mode(
                "auto",
                None,
            ),
            "public_preview",
        )

        self.assertEqual(
            resolve_access_mode(
                "auto",
                "secret",
            ),
            "authenticated_data",
        )

        self.assertEqual(
            resolve_access_mode(
                "preview",
                "secret",
            ),
            "public_preview",
        )

        self.assertEqual(
            resolve_access_mode(
                "data",
                "secret",
            ),
            "authenticated_data",
        )

        with self.assertRaises(
            ConnectorError
        ):

            resolve_access_mode(
                "data",
                None,
            )


    def test_record_limits(
        self,
    ) -> None:

        self.assertEqual(
            resolve_max_records(
                None,
                "public_preview",
            ),
            500,
        )

        self.assertEqual(
            resolve_max_records(
                None,
                "authenticated_data",
            ),
            100000,
        )

        self.assertEqual(
            resolve_max_records(
                250000,
                "authenticated_data",
            ),
            250000,
        )

        with self.assertRaises(
            ConnectorError
        ):

            resolve_max_records(
                501,
                "public_preview",
            )


    def test_zero_exact_records_can_be_explicitly_allowed(
        self,
    ) -> None:

        args = SimpleNamespace(
            reporter_code=699,
            partner_code=784,
            cmd_code="380210",
            flow_code="X",
        )


        payload = {
            "data":
                [],
        }


        with self.assertRaises(
            ConnectorError
        ):

            select_exact_record(
                payload,
                args,
            )


        self.assertIsNone(
            select_exact_record(
                payload,
                args,
                allow_no_data=True,
            )
        )


    def test_multiple_exact_records_remain_invalid(
        self,
    ) -> None:

        args = SimpleNamespace(
            reporter_code=699,
            partner_code=784,
            cmd_code="380210",
            flow_code="X",
        )


        payload = {
            "data":
                [
                    copy.deepcopy(
                        SAMPLE
                    ),
                    copy.deepcopy(
                        SAMPLE
                    ),
                ],
        }


        with self.assertRaises(
            ConnectorError
        ):

            select_exact_record(
                payload,
                args,
                allow_no_data=True,
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
