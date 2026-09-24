from __future__ import annotations

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


from connectors.comtrade_canonical import (
    canonical_customs_procedure,
    canonical_transport_mode,
    source_access_mode,
    trade_metadata,
)


class ComtradeCanonicalizationTest(
    unittest.TestCase
):

    def test_total_dimensions_become_null(
        self,
    ) -> None:

        self.assertIsNone(
            canonical_transport_mode(
                0
            )
        )

        self.assertIsNone(
            canonical_transport_mode(
                "0"
            )
        )

        self.assertIsNone(
            canonical_customs_procedure(
                "C00"
            )
        )


    def test_specific_dimensions_are_preserved(
        self,
    ) -> None:

        self.assertEqual(
            canonical_transport_mode(
                4
            ),
            "4",
        )

        self.assertEqual(
            canonical_customs_procedure(
                "C01"
            ),
            "C01",
        )


    def test_trade_metadata_identity(
        self,
    ) -> None:

        raw = {
            "reporterCode":
                699,

            "partnerCode":
                784,

            "partner2Code":
                0,

            "partner2ISO":
                "W00",

            "customsCode":
                "C00",

            "motCode":
                0,

            "aggrLevel":
                6,

            "isAggregate":
                True,

            "isReported":
                False,

            "isQtyEstimated":
                False,

            "isNetWgtEstimated":
                False,

            "isGrossWgtEstimated":
                False,
        }


        normalized = {
            "sourceExternalId":
                "observation-1",

            "sourceContentHash":
                "a" * 64,

            "classificationCode":
                "H6",

            "reporterISO3":
                "IND",

            "partnerISO3":
                "ARE",
        }


        metadata = trade_metadata(
            raw,
            normalized,
            request_url=(
                "https://comtradeapi.un.org/"
                "public/v1/preview/C/A/HS"
            ),
        )


        self.assertEqual(
            metadata[
                "sourceSystem"
            ],
            "un_comtrade",
        )

        self.assertEqual(
            metadata[
                "sourceExternalId"
            ],
            "observation-1",
        )

        self.assertEqual(
            metadata[
                "reporterISO3"
            ],
            "IND",
        )

        self.assertEqual(
            metadata[
                "partnerISO3"
            ],
            "ARE",
        )

        self.assertEqual(
            metadata[
                "sourceAccessMode"
            ],
            "public_preview",
        )

        self.assertEqual(
            metadata[
                "providerRevisionStatus"
            ],
            "unknown",
        )


    def test_source_access_mode(
        self,
    ) -> None:

        self.assertEqual(
            source_access_mode(
                "https://comtradeapi.un.org/"
                "public/v1/preview/C/A/HS"
            ),
            "public_preview",
        )

        self.assertEqual(
            source_access_mode(
                "https://comtradeapi.un.org/"
                "public/v1/preview"
            ),
            "public_preview",
        )

        self.assertEqual(
            source_access_mode(
                "https://comtradeapi.un.org/"
                "public/v1/other"
            ),
            "public_api",
        )

        self.assertEqual(
            source_access_mode(
                "https://example.invalid/data"
            ),
            "unknown",
        )


if __name__ == "__main__":

    unittest.main()
