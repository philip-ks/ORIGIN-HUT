from __future__ import annotations

import sys
import unittest

from datetime import date
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


from connectors.comtrade_refresh import (
    annual_rolling_periods,
    budget_ledger_for_run,
    effective_daily_budget,
    new_budget_ledger,
    reserve_calls,
    task_capacity,
    validate_budget_ledger,
)


class ComtradeRefreshTest(
    unittest.TestCase
):

    def test_annual_rolling_periods(
        self,
    ) -> None:

        periods = annual_rolling_periods(
            rolling_years=3,
            end_year_offset=-1,
            today=date(
                2026,
                9,
                24,
            ),
        )


        self.assertEqual(
            periods,
            [
                "2023",
                "2024",
                "2025",
            ],
        )


    def test_dry_run_budget_does_not_create_file(
        self,
    ) -> None:

        import tempfile


        with tempfile.TemporaryDirectory() as directory:

            path = (
                Path(directory)
                / "budget.json"
            )


            ledger = budget_ledger_for_run(
                path,
                day="2026-09-25",
                provider_daily_limit=500,
                reserved_provider_calls=50,
                dry_run=True,
            )


            self.assertEqual(
                ledger[
                    "reservedCalls"
                ],
                0,
            )

            self.assertFalse(
                path.exists()
            )


    def test_budget_ledger_configuration_is_validated(
        self,
    ) -> None:

        ledger = new_budget_ledger(
            day="2026-09-25",
            provider_daily_limit=500,
            reserved_provider_calls=50,
        )


        validate_budget_ledger(
            ledger,
            day="2026-09-25",
            provider_daily_limit=500,
            reserved_provider_calls=50,
        )


        with self.assertRaises(
            Exception
        ):

            validate_budget_ledger(
                ledger,
                day="2026-09-25",
                provider_daily_limit=1000,
                reserved_provider_calls=50,
            )


    def test_effective_daily_budget(
        self,
    ) -> None:

        self.assertEqual(
            effective_daily_budget(
                provider_daily_limit=500,
                reserved_provider_calls=50,
            ),
            450,
        )


    def test_task_capacity_reserves_retry_headroom(
        self,
    ) -> None:

        self.assertEqual(
            task_capacity(
                provider_daily_limit=500,
                reserved_provider_calls=50,
                already_reserved_calls=0,
                calls_per_task=4,
                max_tasks_per_run=200,
            ),
            112,
        )


        self.assertEqual(
            task_capacity(
                provider_daily_limit=500,
                reserved_provider_calls=50,
                already_reserved_calls=448,
                calls_per_task=4,
                max_tasks_per_run=100,
            ),
            0,
        )


    def test_call_reservation_ledger(
        self,
    ) -> None:

        ledger = new_budget_ledger(
            day="2026-09-24",
            provider_daily_limit=500,
            reserved_provider_calls=50,
        )


        reserved = reserve_calls(
            ledger,
            plan_name="test-plan",
            task_count=10,
            calls_per_task=4,
        )


        self.assertEqual(
            reserved,
            40,
        )

        self.assertEqual(
            ledger[
                "reservedCalls"
            ],
            40,
        )

        self.assertEqual(
            len(
                ledger[
                    "events"
                ]
            ),
            1,
        )


if __name__ == "__main__":

    unittest.main()
