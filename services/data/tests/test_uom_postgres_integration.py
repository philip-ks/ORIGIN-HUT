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
class UnitOfMeasurePostgresIntegrationTest(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.database_url = os.environ[
            "DATABASE_URL"
        ]

        with psycopg.connect(
            self.database_url
        ) as connection:

            database_name = connection.execute(
                "SELECT current_database()"
            ).fetchone()[0]

            if "test" not in database_name.lower():

                raise RuntimeError(
                    "Refusing to run UOM integration "
                    "tests against a non-test database."
                )


    def convert(
        self,
        value: float,
        from_code: str,
        to_code: str,
    ) -> float:

        with psycopg.connect(
            self.database_url
        ) as connection:

            row = connection.execute(
                """
                SELECT originhut_convert_uom(
                    %s,
                    %s,
                    %s
                )::double precision
                """,
                (
                    value,
                    from_code,
                    to_code,
                ),
            ).fetchone()

        return float(
            row[0]
        )


    def test_seeded_trade_units_exist(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            rows = connection.execute(
                """
                SELECT code
                FROM units_of_measure
                WHERE code = ANY(
                    ARRAY[
                        'KGM',
                        'GRM',
                        'TNE',
                        'MTR',
                        'CMT',
                        'MMT',
                        'MTQ',
                        'LTR'
                    ]
                )
                ORDER BY code
                """
            ).fetchall()

        self.assertEqual(
            len(
                rows
            ),
            8,
        )


    def test_mass_conversion_is_dimension_safe(
        self,
    ) -> None:

        self.assertAlmostEqual(
            self.convert(
                1000,
                "GRM",
                "KGM",
            ),
            1.0,
        )

        self.assertAlmostEqual(
            self.convert(
                1,
                "TNE",
                "KGM",
            ),
            1000.0,
        )


    def test_volume_conversion_is_dimension_safe(
        self,
    ) -> None:

        self.assertAlmostEqual(
            self.convert(
                1,
                "LTR",
                "MTQ",
            ),
            0.001,
        )


    def test_cross_dimension_conversion_is_rejected(
        self,
    ) -> None:

        with psycopg.connect(
            self.database_url
        ) as connection:

            with self.assertRaises(
                psycopg.errors.RaiseException
            ):

                connection.execute(
                    """
                    SELECT originhut_convert_uom(
                        1,
                        'KGM',
                        'LTR'
                    )
                    """
                )


if __name__ == "__main__":

    unittest.main()
