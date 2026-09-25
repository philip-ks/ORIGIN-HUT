from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from datetime import (
    date,
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any


SOURCE_FILE = Path(__file__).resolve()

SRC_ROOT = SOURCE_FILE.parents[1]
PROJECT_ROOT = SOURCE_FILE.parents[4]

HISTORY_SCRIPT = (
    SOURCE_FILE.parent
    / "comtrade_history.py"
)

REFRESH_STATE_ROOT = (
    PROJECT_ROOT
    / "storage"
    / "imports"
    / "comtrade"
    / "refresh"
)


if str(SRC_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(SRC_ROOT),
    )


from connectors.comtrade import (
    comtrade_api_key,
    resolve_access_mode,
)

from connectors.comtrade_history import (
    build_periods,
    build_tasks,
    create_checkpoint,
    load_or_create_checkpoint,
    plan_id_for,
    plan_specification,
    runnable_task_ids,
)

from storage.manifests import (
    write_json_atomic,
)


REFRESH_CONFIG_VERSION = (
    "comtrade_refresh_config_v1"
)

LEDGER_VERSION = (
    "comtrade_call_budget_v1"
)


class RefreshError(
    RuntimeError
):
    pass


def stop(
    message: str,
) -> None:

    raise RefreshError(
        message
    )


def utc_now() -> datetime:

    return datetime.now(
        timezone.utc
    )


def utc_day(
    now: datetime | None = None,
) -> str:

    value = (
        now
        or utc_now()
    )

    return value.date().isoformat()


def safe_name(
    value: str,
) -> str:

    cleaned = "".join(
        character
        if (
            character.isalnum()
            or character in {
                "-",
                "_",
            }
        )
        else "-"
        for character
        in value.strip()
    )

    cleaned = cleaned.strip(
        "-"
    )

    if not cleaned:

        stop(
            "Refresh plan name cannot be empty."
        )

    return cleaned


def annual_rolling_periods(
    *,
    rolling_years: int,
    end_year_offset: int,
    today: date | None = None,
) -> list[str]:

    if rolling_years < 1:

        stop(
            "rollingYears must be at least 1."
        )


    current = (
        today
        or date.today()
    )


    end_year = (
        current.year
        + end_year_offset
    )

    start_year = (
        end_year
        - rolling_years
        + 1
    )


    return build_periods(
        frequency="A",
        start_year=start_year,
        end_year=end_year,
    )


def effective_daily_budget(
    *,
    provider_daily_limit: int,
    reserved_provider_calls: int,
) -> int:

    if provider_daily_limit < 1:

        stop(
            "providerDailyCallLimit must be positive."
        )


    if reserved_provider_calls < 0:

        stop(
            "reservedProviderCalls cannot be negative."
        )


    result = (
        provider_daily_limit
        - reserved_provider_calls
    )


    if result < 0:

        stop(
            "reservedProviderCalls exceeds "
            "providerDailyCallLimit."
        )


    return result


def task_capacity(
    *,
    provider_daily_limit: int,
    reserved_provider_calls: int,
    already_reserved_calls: int,
    calls_per_task: int,
    max_tasks_per_run: int,
) -> int:

    if calls_per_task < 1:

        stop(
            "callsPerTaskReservation must be positive."
        )


    if max_tasks_per_run < 1:

        stop(
            "maxTasksPerRun must be positive."
        )


    budget = effective_daily_budget(
        provider_daily_limit=
            provider_daily_limit,

        reserved_provider_calls=
            reserved_provider_calls,
    )


    remaining = max(
        0,
        budget
        - already_reserved_calls,
    )


    return min(
        max_tasks_per_run,
        remaining
        // calls_per_task,
    )


def new_budget_ledger(
    *,
    day: str,
    provider_daily_limit: int,
    reserved_provider_calls: int,
) -> dict[str, Any]:

    return {
        "schemaVersion":
            LEDGER_VERSION,

        "day":
            day,

        "providerDailyCallLimit":
            provider_daily_limit,

        "reservedProviderCalls":
            reserved_provider_calls,

        "reservedCalls":
            0,

        "events":
            [],
    }


def validate_budget_ledger(
    ledger: dict[str, Any],
    *,
    day: str,
    provider_daily_limit: int,
    reserved_provider_calls: int,
) -> None:

    if (
        ledger.get(
            "schemaVersion"
        )
        != LEDGER_VERSION
    ):

        stop(
            "Unsupported call-budget ledger schema."
        )


    if ledger.get("day") != day:

        stop(
            "Call-budget ledger belongs "
            "to a different UTC day."
        )


    if (
        int(
            ledger.get(
                "providerDailyCallLimit",
                -1,
            )
        )
        != provider_daily_limit
    ):

        stop(
            "Existing call-budget ledger uses a "
            "different providerDailyCallLimit."
        )


    if (
        int(
            ledger.get(
                "reservedProviderCalls",
                -1,
            )
        )
        != reserved_provider_calls
    ):

        stop(
            "Existing call-budget ledger uses a "
            "different reservedProviderCalls value."
        )


    reserved_calls = int(
        ledger.get(
            "reservedCalls",
            0,
        )
    )


    if reserved_calls < 0:

        stop(
            "Call-budget ledger contains a "
            "negative reservedCalls value."
        )


def load_or_create_budget_ledger(
    path: Path,
    *,
    day: str,
    provider_daily_limit: int,
    reserved_provider_calls: int,
) -> dict[str, Any]:

    if not path.exists():

        ledger = new_budget_ledger(
            day=
                day,

            provider_daily_limit=
                provider_daily_limit,

            reserved_provider_calls=
                reserved_provider_calls,
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        write_json_atomic(
            path,
            ledger,
        )

        return ledger


    ledger = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


    validate_budget_ledger(
        ledger,
        day=
            day,

        provider_daily_limit=
            provider_daily_limit,

        reserved_provider_calls=
            reserved_provider_calls,
    )


    return ledger


def budget_ledger_for_run(
    path: Path,
    *,
    day: str,
    provider_daily_limit: int,
    reserved_provider_calls: int,
    dry_run: bool,
) -> dict[str, Any]:

    if not dry_run:

        return load_or_create_budget_ledger(
            path,
            day=
                day,

            provider_daily_limit=
                provider_daily_limit,

            reserved_provider_calls=
                reserved_provider_calls,
        )


    if not path.exists():

        return new_budget_ledger(
            day=
                day,

            provider_daily_limit=
                provider_daily_limit,

            reserved_provider_calls=
                reserved_provider_calls,
        )


    ledger = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


    validate_budget_ledger(
        ledger,
        day=
            day,

        provider_daily_limit=
            provider_daily_limit,

        reserved_provider_calls=
            reserved_provider_calls,
    )


    return ledger


def reserve_calls(
    ledger: dict[str, Any],
    *,
    plan_name: str,
    task_count: int,
    calls_per_task: int,
) -> int:

    reserved = (
        task_count
        * calls_per_task
    )


    ledger[
        "reservedCalls"
    ] = (
        int(
            ledger.get(
                "reservedCalls",
                0,
            )
        )
        + reserved
    )


    ledger[
        "events"
    ].append(
        {
            "timestamp":
                utc_now().isoformat(),

            "plan":
                plan_name,

            "tasks":
                task_count,

            "callsReserved":
                reserved,
        }
    )


    return reserved


def plan_periods(
    plan: dict[str, Any],
) -> list[str]:

    frequency = str(
        plan.get(
            "frequency",
            "A",
        )
    ).upper()


    explicit = plan.get(
        "periods"
    )


    if explicit is not None:

        if not isinstance(
            explicit,
            list,
        ):

            stop(
                "plan.periods must be an array."
            )


        return build_periods(
            frequency=
                frequency,

            explicit_periods=[
                str(value)
                for value
                in explicit
            ],
        )


    if frequency != "A":

        stop(
            "Rolling refresh periods currently "
            "support annual frequency only. "
            "Use explicit periods for monthly plans."
        )


    rolling_years = int(
        plan.get(
            "rollingYears",
            2,
        )
    )

    end_year_offset = int(
        plan.get(
            "endYearOffset",
            -1,
        )
    )


    return annual_rolling_periods(
        rolling_years=
            rolling_years,

        end_year_offset=
            end_year_offset,
    )


def checkpoint_for_run(
    path: Path,
    *,
    plan_id: str,
    specification: dict[str, Any],
    tasks: list[Any],
    dry_run: bool,
) -> dict[str, Any]:

    if not dry_run:

        return load_or_create_checkpoint(
            path=
                path,

            plan_id=
                plan_id,

            specification=
                specification,

            tasks=
                tasks,
        )


    if not path.exists():

        return create_checkpoint(
            plan_id=
                plan_id,

            specification=
                specification,

            tasks=
                tasks,
        )


    checkpoint = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


    if (
        checkpoint.get(
            "planId"
        )
        != plan_id
    ):

        stop(
            "Refresh checkpoint belongs "
            "to a different plan."
        )


    if (
        checkpoint.get(
            "plan"
        )
        != specification
    ):

        stop(
            "Refresh checkpoint specification "
            "does not match current plan."
        )


    expected_order = [
        task.task_id
        for task
        in tasks
    ]


    if (
        checkpoint.get(
            "taskOrder"
        )
        != expected_order
    ):

        stop(
            "Refresh checkpoint task order "
            "does not match current plan."
        )


    return checkpoint


def checkpoint_path_for_refresh(
    *,
    plan_name: str,
    day: str,
) -> Path:

    return (
        REFRESH_STATE_ROOT
        / "checkpoints"
        / safe_name(
            plan_name
        )
        / f"{day}.json"
    )


def history_command(
    *,
    plan: dict[str, Any],
    periods: list[str],
    checkpoint: Path,
    task_limit: int,
    access_mode: str,
    requests_per_second: float,
    apply: bool,
) -> list[str]:

    command = [
        sys.executable,
        str(
            HISTORY_SCRIPT
        ),

        "--reporter-codes",
        ",".join(
            str(value)
            for value
            in plan[
                "reporterCodes"
            ]
        ),

        "--partner-codes",
        ",".join(
            str(value)
            for value
            in plan[
                "partnerCodes"
            ]
        ),

        "--cmd-codes",
        ",".join(
            str(value)
            for value
            in plan[
                "cmdCodes"
            ]
        ),

        "--flow-codes",
        ",".join(
            str(value)
            for value
            in plan.get(
                "flowCodes",
                [
                    "X",
                    "M",
                ],
            )
        ),

        "--frequency",
        str(
            plan.get(
                "frequency",
                "A",
            )
        ).upper(),

        "--classification",
        str(
            plan.get(
                "classification",
                "HS",
            )
        ).upper(),

        "--periods",
        ",".join(
            periods
        ),

        "--access-mode",
        access_mode,

        "--max-tasks",
        str(
            task_limit
        ),

        "--requests-per-second",
        str(
            requests_per_second
        ),

        "--checkpoint",
        str(
            checkpoint
        ),

        "--execute",
    ]


    if apply:

        command.append(
            "--apply"
        )


    if bool(
        plan.get(
            "retryFailed",
            False,
        )
    ):

        command.append(
            "--retry-failed"
        )


    command.append(
        "--continue-on-error"
    )


    return command


def validate_config(
    config: dict[str, Any],
) -> None:

    if (
        config.get(
            "schemaVersion"
        )
        != REFRESH_CONFIG_VERSION
    ):

        stop(
            "Unsupported refresh configuration schema."
        )


    plans = config.get(
        "plans"
    )


    if (
        not isinstance(
            plans,
            list,
        )
        or not plans
    ):

        stop(
            "Refresh configuration requires plans."
        )


    required_plan_fields = {
        "name",
        "reporterCodes",
        "partnerCodes",
        "cmdCodes",
    }


    for plan in plans:

        if not isinstance(
            plan,
            dict,
        ):

            stop(
                "Each refresh plan must be an object."
            )


        missing = (
            required_plan_fields
            - set(
                plan
            )
        )


        if missing:

            stop(
                "Refresh plan is missing: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Origin Hut scheduled UN Comtrade "
            "refresh orchestrator."
        )
    )


    parser.add_argument(
        "--config",
        required=True,
    )


    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Plan work without making provider "
            "or database calls."
        ),
    )


    return parser.parse_args()


def main() -> int:

    args = parse_args()


    config_path = Path(
        args.config
    ).resolve()


    config = json.loads(
        config_path.read_text(
            encoding="utf-8"
        )
    )


    validate_config(
        config
    )


    settings = config.get(
        "settings",
        {}
    )


    provider_daily_limit = int(
        settings.get(
            "providerDailyCallLimit",
            500,
        )
    )

    reserved_provider_calls = int(
        settings.get(
            "reservedProviderCalls",
            50,
        )
    )

    calls_per_task = int(
        settings.get(
            "callsPerTaskReservation",
            4,
        )
    )

    max_tasks_per_run = int(
        settings.get(
            "maxTasksPerRun",
            100,
        )
    )

    requests_per_second = float(
        settings.get(
            "requestsPerSecond",
            1.0,
        )
    )


    if (
        requests_per_second <= 0
        or requests_per_second > 1.0
    ):

        stop(
            "Scheduled refresh requestsPerSecond "
            "must be greater than 0 and no more "
            "than 1.0."
        )


    require_authenticated = bool(
        settings.get(
            "requireAuthenticated",
            True,
        )
    )

    apply = bool(
        settings.get(
            "apply",
            True,
        )
    )


    resolved_access = resolve_access_mode(
        "auto",
        comtrade_api_key(),
    )


    if (
        require_authenticated
        and resolved_access
        != "authenticated_data"
        and not args.dry_run
    ):

        stop(
            "Scheduled production refresh requires "
            "UN_COMTRADE_API_KEY. "
            "Use --dry-run until the key is configured."
        )


    child_access = (
        "data"
        if resolved_access
        == "authenticated_data"
        else "preview"
    )


    day = utc_day()


    ledger_path = (
        REFRESH_STATE_ROOT
        / "budget"
        / f"{day}.json"
    )


    ledger = budget_ledger_for_run(
        ledger_path,
        day=
            day,

        provider_daily_limit=
            provider_daily_limit,

        reserved_provider_calls=
            reserved_provider_calls,

        dry_run=
            args.dry_run,
    )


    results: list[
        dict[str, Any]
    ] = []


    for plan in config[
        "plans"
    ]:

        name = str(
            plan[
                "name"
            ]
        )

        periods = plan_periods(
            plan
        )


        specification = plan_specification(
            reporter_codes=[
                int(value)
                for value
                in plan[
                    "reporterCodes"
                ]
            ],

            periods=
                periods,

            partner_codes=[
                int(value)
                for value
                in plan[
                    "partnerCodes"
                ]
            ],

            cmd_codes=[
                str(value)
                for value
                in plan[
                    "cmdCodes"
                ]
            ],

            flow_codes=[
                str(value)
                for value
                in plan.get(
                    "flowCodes",
                    [
                        "X",
                        "M",
                    ],
                )
            ],

            frequency=
                str(
                    plan.get(
                        "frequency",
                        "A",
                    )
                ).upper(),

            classification=
                str(
                    plan.get(
                        "classification",
                        "HS",
                    )
                ).upper(),
        )


        tasks = build_tasks(
            reporter_codes=
                specification[
                    "reporterCodes"
                ],

            periods=
                specification[
                    "periods"
                ],

            partner_codes=
                specification[
                    "partnerCodes"
                ],

            cmd_codes=
                specification[
                    "cmdCodes"
                ],

            flow_codes=
                specification[
                    "flowCodes"
                ],

            frequency=
                specification[
                    "frequency"
                ],

            classification=
                specification[
                    "classification"
                ],
        )


        plan_id = plan_id_for(
            specification
        )


        checkpoint_path = (
            checkpoint_path_for_refresh(
                plan_name=
                    name,

                day=
                    day,
            )
        )


        checkpoint = checkpoint_for_run(
            checkpoint_path,
            plan_id=
                plan_id,

            specification=
                specification,

            tasks=
                tasks,

            dry_run=
                args.dry_run,
        )


        runnable = runnable_task_ids(
            checkpoint,
            retry_failed=
                bool(
                    plan.get(
                        "retryFailed",
                        False,
                    )
                ),

            max_tasks=
                len(
                    tasks
                )
                or 1,
        )


        capacity = task_capacity(
            provider_daily_limit=
                provider_daily_limit,

            reserved_provider_calls=
                reserved_provider_calls,

            already_reserved_calls=
                int(
                    ledger.get(
                        "reservedCalls",
                        0,
                    )
                ),

            calls_per_task=
                calls_per_task,

            max_tasks_per_run=
                max_tasks_per_run,
        )


        selected = min(
            len(
                runnable
            ),
            capacity,
        )


        result = {
            "name":
                name,

            "planId":
                plan_id,

            "periods":
                periods,

            "plannedTasks":
                len(
                    tasks
                ),

            "runnableTasks":
                len(
                    runnable
                ),

            "selectedTasks":
                selected,

            "checkpoint":
                str(
                    checkpoint_path
                ),
        }


        results.append(
            result
        )


        if (
            args.dry_run
            or selected == 0
        ):

            continue


        reserved = reserve_calls(
            ledger,
            plan_name=
                name,

            task_count=
                selected,

            calls_per_task=
                calls_per_task,
        )


        write_json_atomic(
            ledger_path,
            ledger,
        )


        result[
            "callsReserved"
        ] = reserved


        command = history_command(
            plan=
                plan,

            periods=
                periods,

            checkpoint=
                checkpoint_path,

            task_limit=
                selected,

            access_mode=
                child_access,

            requests_per_second=
                requests_per_second,

            apply=
                apply,
        )


        child = subprocess.run(
            command,
            cwd=
                PROJECT_ROOT,

            check=False,
        )


        result[
            "exitCode"
        ] = child.returncode


        if child.returncode != 0:

            stop(
                "Refresh plan failed: "
                + name
            )


    summary = {
        "ok":
            True,

        "dryRun":
            args.dry_run,

        "utcDay":
            day,

        "accessMode":
            resolved_access,

        "authenticated":
            resolved_access
            == "authenticated_data",

        "providerDailyCallLimit":
            provider_daily_limit,

        "reservedProviderCalls":
            reserved_provider_calls,

        "effectiveDailyBudget":
            effective_daily_budget(
                provider_daily_limit=
                    provider_daily_limit,

                reserved_provider_calls=
                    reserved_provider_calls,
            ),

        "callsReservedToday":
            ledger.get(
                "reservedCalls",
                0,
            ),

        "requestsPerSecond":
            requests_per_second,

        "apply":
            apply,

        "plans":
            results,
    }


    print("")
    print(
        "=== COMTRADE REFRESH ORCHESTRATION ==="
    )

    print(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        )
    )


    if args.dry_run:

        print("")
        print(
            "DRY RUN: no UN Comtrade "
            "or PostgreSQL writes executed."
        )


    return 0


if __name__ == "__main__":

    try:

        raise SystemExit(
            main()
        )

    except (
        RefreshError,
        ValueError,
        OSError,
        json.JSONDecodeError,
    ) as error:

        print(
            "STOP:",
            error,
            file=sys.stderr,
        )

        raise SystemExit(
            2
        )
