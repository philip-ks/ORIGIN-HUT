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


from connectors.company_web import (
    CompanyWebError,
    evidence_result,
    html_to_text,
    validate_config,
)


class CompanyWebConnectorTest(
    unittest.TestCase
):

    def test_html_to_text_removes_script_and_style(
        self,
    ) -> None:

        raw = b"""
        <html>
          <head>
            <style>.x { color: red; }</style>
            <script>secretScript()</script>
          </head>
          <body>
            <h1>Activated Carbon</h1>
            <p>Manufacturer in India</p>
          </body>
        </html>
        """


        text = html_to_text(
            raw
        )


        self.assertIn(
            "Activated Carbon",
            text,
        )

        self.assertIn(
            "Manufacturer in India",
            text,
        )

        self.assertNotIn(
            "secretScript",
            text,
        )


    def test_evidence_requires_all_and_any_terms(
        self,
    ) -> None:

        result = evidence_result(
            (
                "We manufacture activated carbon "
                "from coconut shell in India."
            ),
            {
                "allTerms":
                    [
                        "activated carbon",
                    ],

                "anyTerms":
                    [
                        "manufacturer",
                        "manufacture",
                    ],
            },
        )


        self.assertTrue(
            result[
                "passed"
            ]
        )


        failed = evidence_result(
            "Activated carbon products.",
            {
                "allTerms":
                    [
                        "activated carbon",
                    ],

                "anyTerms":
                    [
                        "manufacturer",
                        "manufacture",
                    ],
            },
        )


        self.assertFalse(
            failed[
                "passed"
            ]
        )


    def test_config_normalizes_activity_and_roles(
        self,
    ) -> None:

        config = validate_config(
            {
                "sources":
                    [
                        {
                            "code":
                                "example_company",

                            "name":
                                "Example Official Website",

                            "provider":
                                "Example Company",

                            "url":
                                "https://example.com/",

                            "official":
                                True,

                            "organization":
                                {
                                    "legalName":
                                        "Example Company Pvt Ltd",

                                    "countryIso2":
                                        "in",

                                    "roles":
                                        [
                                            "Manufacturer",
                                            "Export Supplier",
                                        ],
                                },

                            "activities":
                                [
                                    {
                                        "activityType":
                                            "Manufactures",

                                        "hsCode":
                                            "380210",

                                        "productId":
                                            "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",

                                        "marketCountryIso2":
                                            "in",

                                        "confidence":
                                            0.95,

                                        "allTerms":
                                            [
                                                "activated carbon",
                                            ],

                                        "anyTerms":
                                            [
                                                "manufacturer",
                                            ],
                                    }
                                ],
                        }
                    ]
            }
        )


        source = config[
            "sources"
        ][0]


        self.assertEqual(
            source[
                "organization"
            ][
                "countryIso2"
            ],
            "IN",
        )

        self.assertEqual(
            source[
                "organization"
            ][
                "roles"
            ],
            [
                "export_supplier",
                "manufacturer",
            ],
        )

        self.assertEqual(
            source[
                "activities"
            ][0][
                "activityType"
            ],
            "manufactures",
        )


        self.assertEqual(
            source[
                "activities"
            ][0][
                "productId"
            ],
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        )


    def test_config_rejects_invalid_product_id(
        self,
    ) -> None:

        with self.assertRaises(
            CompanyWebError
        ):

            validate_config(
                {
                    "sources":
                        [
                            {
                                "code":
                                    "product_scope",

                                "name":
                                    "Product Scope",

                                "provider":
                                    "Product Scope",

                                "url":
                                    "https://example.com/",

                                "organization":
                                    {
                                        "legalName":
                                            "Product Scope Company",

                                        "countryIso2":
                                            "IN",
                                    },

                                "activities":
                                    [
                                        {
                                            "activityType":
                                                "supplies",

                                            "hsCode":
                                                "380210",

                                            "productId":
                                                "not-a-uuid",

                                            "marketCountryIso2":
                                                "IN",
                                        }
                                    ],
                            }
                        ]
                }
            )


    def test_missing_confidence_remains_null(
        self,
    ) -> None:

        config = validate_config(
            {
                "sources":
                    [
                        {
                            "code":
                                "confidence_test",

                            "name":
                                "Confidence Test",

                            "provider":
                                "Confidence Test",

                            "url":
                                "https://example.com/",

                            "organization":
                                {
                                    "legalName":
                                        "Confidence Test Company",

                                    "countryIso2":
                                        "IN",
                                },

                            "activities":
                                [
                                    {
                                        "activityType":
                                            "supplies",

                                        "hsCode":
                                            "380210",

                                        "marketCountryIso2":
                                            "IN",
                                    }
                                ],
                        }
                    ]
            }
        )


        self.assertIsNone(
            config[
                "sources"
            ][0][
                "activities"
            ][0][
                "confidence"
            ]
        )


    def test_config_rejects_invalid_hs_code(
        self,
    ) -> None:

        with self.assertRaises(
            CompanyWebError
        ):

            validate_config(
                {
                    "sources":
                        [
                            {
                                "code":
                                    "example",

                                "name":
                                    "Example",

                                "provider":
                                    "Example",

                                "url":
                                    "https://example.com/",

                                "organization":
                                    {
                                        "legalName":
                                            "Example",

                                        "countryIso2":
                                            "IN",
                                    },

                                "activities":
                                    [
                                        {
                                            "activityType":
                                                "supplies",

                                            "hsCode":
                                                "ABC",

                                            "marketCountryIso2":
                                                "AE",
                                        }
                                    ],
                            }
                        ]
                }
            )


if __name__ == "__main__":

    unittest.main()
