from __future__ import annotations

import sys
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch


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


from connectors.comtrade_history import (
    HistoricalTask,
    build_periods,
    child_access_mode,
    build_tasks,
    checkpoint_counts,
    classify_failure,
    create_checkpoint,
    execute_task,
    load_or_create_checkpoint,
    plan_id_for,
    plan_specification,
    runnable_task_ids,
    save_checkpoint,
)


class ComtradeHistoricalPlannerTest(
    unittest.TestCase
):

    def test_historical_child_explicitly_allows_no_data(
        self,
    ) -> None:

        task = {
            "reporterCode":
                699,

            "partnerCode":
                784,

            "period":
                "2025",

            "cmdCode":
                "380210",

            "flowCode":
                "X",

            "frequency":
                "A",

            "classification":
                "HS",
        }


        with patch(
            "connectors.comtrade_history.subprocess.run"
        ) as run:

            run.return_value.returncode = 0
            run.return_value.stdout = ""
            run.return_value.stderr = ""


            success, error = execute_task(
                task=
                    task,

                run_id=
                    "test-no-data",

                access_mode=
                    "public_preview",

                max_records=
                    20,

                apply=
                    False,
            )


            self.assertTrue(
                success
            )

            self.assertIsNone(
                error
            )


            command = run.call_args.args[
                0
            ]


            self.assertIn(
                "--allow-no-data",
                command,
            )


    def test_transient_provider_failures_are_deferred(
        self,
    ) -> None:

        self.assertEqual(
            classify_failure(
                "500 Internal Server Error"
            ),
            "deferred",
        )

        self.assertEqual(
            classify_failure(
                "429 Too Many Requests"
            ),
            "deferred",
        )

        self.assertEqual(
            classify_failure(
                "503 Service Unavailable"
            ),
            "deferred",
        )

        self.assertEqual(
            classify_failure(
                "UN Comtrade HTTP error status=500."
            ),
            "deferred",
        )

        self.assertEqual(
            classify_failure(
                "UN Comtrade HTTP error status=429."
            ),
            "deferred",
        )

        self.assertEqual(
            classify_failure(
                "Invalid permanent task input"
            ),
            "failed",
        )


    def test_child_access_mode_mapping(
        self,
    ) -> None:

        self.assertEqual(
            child_access_mode(
                "public_preview"
            ),
            "preview",
        )

        self.assertEqual(
            child_access_mode(
                "authenticated_data"
            ),
            "data",
        )


    def test_annual_period_generation(
        self,
    ) -> None:

        self.assertEqual(
            build_periods(
                frequency="A",
                start_year=2022,
                end_year=2024,
            ),
            [
                "2022",
                "2023",
                "2024",
            ],
        )


    def test_monthly_period_generation(
        self,
    ) -> None:

        periods = build_periods(
            frequency="M",
            start_year=2024,
            end_year=2024,
        )


        self.assertEqual(
            len(periods),
            12,
        )

        self.assertEqual(
            periods[0],
            "202401",
        )

        self.assertEqual(
            periods[-1],
            "202412",
        )


    def test_task_matrix_is_deterministic(
        self,
    ) -> None:

        tasks = build_tasks(
            reporter_codes=[
                699,
            ],

            periods=[
                "2023",
                "2024",
            ],

            partner_codes=[
                784,
                0,
            ],

            cmd_codes=[
                "380210",
            ],

            flow_codes=[
                "X",
                "M",
            ],

            frequency=
                "A",

            classification=
                "HS",
        )


        self.assertEqual(
            len(tasks),
            8,
        )


        task_ids = [
            task.task_id
            for task
            in tasks
        ]


        self.assertEqual(
            len(
                set(
                    task_ids
                )
            ),
            8,
        )


        repeated = build_tasks(
            reporter_codes=[
                699,
            ],

            periods=[
                "2024",
                "2023",
            ],

            partner_codes=[
                0,
                784,
            ],

            cmd_codes=[
                "380210",
            ],

            flow_codes=[
                "M",
                "X",
            ],

            frequency=
                "A",

            classification=
                "HS",
        )


        self.assertEqual(
            task_ids,
            [
                task.task_id
                for task
                in repeated
            ],
        )


    def test_checkpoint_recovers_running_task(
        self,
    ) -> None:

        tasks = [
            HistoricalTask(
                reporter_code=
                    699,

                period=
                    "2024",

                partner_code=
                    784,

                cmd_code=
                    "380210",

                flow_code=
                    "X",

                frequency=
                    "A",

                classification=
                    "H6",
            )
        ]


        specification = plan_specification(
            reporter_codes=[
                699,
            ],

            periods=[
                "2024",
            ],

            partner_codes=[
                784,
            ],

            cmd_codes=[
                "380210",
            ],

            flow_codes=[
                "X",
            ],

            frequency=
                "A",

            classification=
                "HS",
        )


        plan_id = plan_id_for(
            specification
        )


        checkpoint = create_checkpoint(
            plan_id=
                plan_id,

            specification=
                specification,

            tasks=
                tasks,
        )


        task_id = tasks[0].task_id

        checkpoint[
            "tasks"
        ][
            task_id
        ][
            "status"
        ] = "running"


        with tempfile.TemporaryDirectory() as directory:

            path = (
                Path(directory)
                / "checkpoint.json"
            )


            save_checkpoint(
                path,
                checkpoint,
            )


            recovered = load_or_create_checkpoint(
                path=
                    path,

                plan_id=
                    plan_id,

                specification=
                    specification,

                tasks=
                    tasks,
            )


            state = recovered[
                "tasks"
            ][
                task_id
            ]


            self.assertEqual(
                state[
                    "status"
                ],
                "pending",
            )

            self.assertEqual(
                state[
                    "lastError"
                ],
                "Recovered interrupted task.",
            )


    def test_deferred_task_is_automatically_runnable(
        self,
    ) -> None:

        tasks = build_tasks(
            reporter_codes=[
                699,
            ],

            periods=[
                "2024",
            ],

            partner_codes=[
                784,
            ],

            cmd_codes=[
                "380210",
            ],

            flow_codes=[
                "X",
            ],

            frequency=
                "A",

            classification=
                "HS",
        )


        specification = plan_specification(
            reporter_codes=[
                699,
            ],

            periods=[
                "2024",
            ],

            partner_codes=[
                784,
            ],

            cmd_codes=[
                "380210",
            ],

            flow_codes=[
                "X",
            ],

            frequency=
                "A",

            classification=
                "HS",
        )


        checkpoint = create_checkpoint(
            plan_id=
                plan_id_for(
                    specification
                ),

            specification=
                specification,

            tasks=
                tasks,
        )


        task_id = tasks[0].task_id

        checkpoint[
            "tasks"
        ][
            task_id
        ][
            "status"
        ] = "deferred"


        self.assertEqual(
            runnable_task_ids(
                checkpoint,
                retry_failed=False,
                max_tasks=100,
            ),
            [
                task_id,
            ],
        )


    def test_runnable_selection_respects_resume_state(
        self,
    ) -> None:

        tasks = build_tasks(
            reporter_codes=[
                699,
            ],

            periods=[
                "2023",
                "2024",
            ],

            partner_codes=[
                784,
            ],

            cmd_codes=[
                "380210",
            ],

            flow_codes=[
                "X",
            ],

            frequency=
                "A",

            classification=
                "HS",
        )


        specification = plan_specification(
            reporter_codes=[
                699,
            ],

            periods=[
                "2023",
                "2024",
            ],

            partner_codes=[
                784,
            ],

            cmd_codes=[
                "380210",
            ],

            flow_codes=[
                "X",
            ],

            frequency=
                "A",

            classification=
                "HS",
        )


        checkpoint = create_checkpoint(
            plan_id=
                plan_id_for(
                    specification
                ),

            specification=
                specification,

            tasks=
                tasks,
        )


        first_id = tasks[0].task_id
        second_id = tasks[1].task_id


        checkpoint[
            "tasks"
        ][
            first_id
        ][
            "status"
        ] = "completed"

        checkpoint[
            "tasks"
        ][
            second_id
        ][
            "status"
        ] = "failed"


        self.assertEqual(
            runnable_task_ids(
                checkpoint,
                retry_failed=False,
                max_tasks=100,
            ),
            [],
        )


        self.assertEqual(
            runnable_task_ids(
                checkpoint,
                retry_failed=True,
                max_tasks=100,
            ),
            [
                second_id,
            ],
        )


        counts = checkpoint_counts(
            checkpoint
        )


        self.assertEqual(
            counts[
                "completed"
            ],
            1,
        )

        self.assertEqual(
            counts[
                "failed"
            ],
            1,
        )


if __name__ == "__main__":

    unittest.main()
