from __future__ import annotations

import os
import unittest

import psycopg


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
class IncotermReferencePostgresIntegrationTest(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        database_url = os.environ[
            "DATABASE_URL"
        ]

        with psycopg.connect(
            database_url
        ) as connection:

            database_name = connection.execute(
                "SELECT current_database()"
            ).fetchone()[0]

            if "test" not in database_name.lower():
                raise RuntimeError(
                    "Refusing to run Incoterm tests "
                    "against a non-test database."
                )


    def test_incoterms_2020_has_eleven_rules(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            count = connection.execute(
                """
                SELECT COUNT(*)::int
                FROM incoterm_rules
                WHERE
                    edition = 2020
                    AND is_active = TRUE
                """
            ).fetchone()[0]

            self.assertEqual(
                count,
                11,
            )


    def test_transport_scope_split_is_seven_and_four(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            rows = dict(
                connection.execute(
                    """
                    SELECT
                        transport_scope,
                        COUNT(*)::int
                    FROM incoterm_rules
                    WHERE
                        edition = 2020
                        AND is_active = TRUE
                    GROUP BY transport_scope
                    """
                ).fetchall()
            )

            self.assertEqual(
                rows[
                    "any_mode"
                ],
                7,
            )

            self.assertEqual(
                rows[
                    "sea_inland_waterway"
                ],
                4,
            )


    def test_named_location_roles_match_rule_family(
        self,
    ) -> None:

        with psycopg.connect(
            os.environ[
                "DATABASE_URL"
            ]
        ) as connection:

            rows = dict(
                connection.execute(
                    """
                    SELECT
                        code,
                        named_location_role
                    FROM incoterm_rules
                    WHERE edition = 2020
                    """
                ).fetchall()
            )

            self.assertEqual(
                rows["EXW"],
                "delivery_place",
            )

            self.assertEqual(
                rows["FCA"],
                "delivery_place",
            )

            for code in [
                "CPT",
                "CIP",
                "DAP",
                "DPU",
                "DDP",
            ]:
                self.assertEqual(
                    rows[code],
                    "destination_place",
                )

            for code in [
                "FAS",
                "FOB",
            ]:
                self.assertEqual(
                    rows[code],
                    "shipment_port",
                )

            for code in [
                "CFR",
                "CIF",
            ]:
                self.assertEqual(
                    rows[code],
                    "destination_port",
                )


if __name__ == "__main__":
    unittest.main()
