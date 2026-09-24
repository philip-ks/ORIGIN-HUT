from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_FILE = Path(__file__).resolve()

SRC_ROOT = SOURCE_FILE.parents[1]
PROJECT_ROOT = SOURCE_FILE.parents[4]

COMTRADE_SCRIPT = (
    SOURCE_FILE.parent
    / "comtrade.py"
)

CHECKPOINT_ROOT = (
    PROJECT_ROOT
    / "storage"
    / "imports"
    / "comtrade"
    / "checkpoints"
)


if str(SRC_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(SRC_ROOT),
    )


from connectors.comtrade import (
    ConnectorError,
    comtrade_api_key,
    resolve_access_mode,
    resolve_max_records,
)

from storage.manifests import (
    sha256_json,
    write_json_atomic,
)


CHECKPOINT_SCHEMA_VERSION = (
    "comtrade_history_checkpoint_v1"
)


class HistoricalPlannerError(
    RuntimeError
):
    pass


def stop(
    message: str,
) -> None:

    raise HistoricalPlannerError(
        message
    )


def utc_now() -> str:

    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )


def unique_sorted_ints(
    values: list[int],
) -> list[int]:

    return sorted(
        set(values)
    )


def unique_sorted_strings(
    values: list[str],
) -> list[str]:

    return sorted(
        set(values)
    )


def parse_int_list(
    value: str,
) -> list[int]:

    result: list[int] = []


    for item in value.split(","):

        item = item.strip()

        if not item:
            continue

        try:

            result.append(
                int(item)
            )

        except ValueError as error:

            raise HistoricalPlannerError(
                "Expected comma-separated integers: "
                + value
            ) from error


    if not result:

        stop(
            "At least one integer value is required."
        )


    return unique_sorted_ints(
        result
    )


def parse_string_list(
    value: str,
) -> list[str]:

    result = [
        item.strip().upper()
        for item
        in value.split(",")
        if item.strip()
    ]


    if not result:

        stop(
            "At least one value is required."
        )


    return unique_sorted_strings(
        result
    )


def validate_hs6(
    codes: list[str],
) -> None:

    for code in codes:

        if (
            len(code) != 6
            or not code.isdigit()
        ):

            stop(
                "Historical planner currently requires "
                "six-digit HS codes. Invalid code: "
                + code
            )


def validate_period(
    period: str,
    frequency: str,
) -> None:

    if frequency == "A":

        if (
            len(period) != 4
            or not period.isdigit()
        ):

            stop(
                "Annual periods must use YYYY: "
                + period
            )

        return


    if frequency == "M":

        if (
            len(period) != 6
            or not period.isdigit()
        ):

            stop(
                "Monthly periods must use YYYYMM: "
                + period
            )


        month = int(
            period[4:]
        )


        if (
            month < 1
            or month > 12
        ):

            stop(
                "Invalid monthly period: "
                + period
            )

        return


    stop(
        "Unsupported frequency: "
        + frequency
    )


def build_periods(
    *,
    frequency: str,
    start_year: int | None = None,
    end_year: int | None = None,
    explicit_periods: list[str] | None = None,
) -> list[str]:

    if explicit_periods:

        periods = unique_sorted_strings(
            explicit_periods
        )


        for period in periods:

            validate_period(
                period,
                frequency,
            )


        return periods


    if (
        start_year is None
        or end_year is None
    ):

        stop(
            "Provide --periods or both "
            "--start-year and --end-year."
        )


    if end_year < start_year:

        stop(
            "--end-year cannot be earlier "
            "than --start-year."
        )


    if frequency == "A":

        return [
            str(year)
            for year
            in range(
                start_year,
                end_year + 1,
            )
        ]


    if frequency == "M":

        return [
            f"{year}{month:02d}"

            for year
            in range(
                start_year,
                end_year + 1,
            )

            for month
            in range(
                1,
                13,
            )
        ]


    stop(
        "Unsupported frequency: "
        + frequency
    )


@dataclass(
    frozen=True
)
class HistoricalTask:

    reporter_code: int
    period: str
    partner_code: int
    cmd_code: str
    flow_code: str
    frequency: str
    classification: str


    def specification(
        self,
    ) -> dict[str, Any]:

        return {
            "reporterCode":
                self.reporter_code,

            "period":
                self.period,

            "partnerCode":
                self.partner_code,

            "cmdCode":
                self.cmd_code,

            "flowCode":
                self.flow_code,

            "frequency":
                self.frequency,

            "classification":
                self.classification,
        }


    @property
    def task_id(
        self,
    ) -> str:

        return (
            sha256_json(
                self.specification()
            )[:24]
        )


def build_tasks(
    *,
    reporter_codes: list[int],
    periods: list[str],
    partner_codes: list[int],
    cmd_codes: list[str],
    flow_codes: list[str],
    frequency: str,
    classification: str,
) -> list[HistoricalTask]:

    validate_hs6(
        cmd_codes
    )


    for period in periods:

        validate_period(
            period,
            frequency,
        )


    tasks = [

        HistoricalTask(
            reporter_code=
                reporter_code,

            period=
                period,

            partner_code=
                partner_code,

            cmd_code=
                cmd_code,

            flow_code=
                flow_code,

            frequency=
                frequency,

            classification=
                classification,
        )

        for reporter_code
        in unique_sorted_ints(
            reporter_codes
        )

        for period
        in unique_sorted_strings(
            periods
        )

        for partner_code
        in unique_sorted_ints(
            partner_codes
        )

        for cmd_code
        in unique_sorted_strings(
            cmd_codes
        )

        for flow_code
        in unique_sorted_strings(
            flow_codes
        )
    ]


    return tasks


def plan_specification(
    *,
    reporter_codes: list[int],
    periods: list[str],
    partner_codes: list[int],
    cmd_codes: list[str],
    flow_codes: list[str],
    frequency: str,
    classification: str,
) -> dict[str, Any]:

    return {
        "reporterCodes":
            unique_sorted_ints(
                reporter_codes
            ),

        "periods":
            unique_sorted_strings(
                periods
            ),

        "partnerCodes":
            unique_sorted_ints(
                partner_codes
            ),

        "cmdCodes":
            unique_sorted_strings(
                cmd_codes
            ),

        "flowCodes":
            unique_sorted_strings(
                flow_codes
            ),

        "frequency":
            frequency,

        "classification":
            classification,
    }


def plan_id_for(
    specification: dict[str, Any],
) -> str:

    return (
        sha256_json(
            specification
        )[:24]
    )


def checkpoint_path_for(
    plan_id: str,
) -> Path:

    return (
        CHECKPOINT_ROOT
        / f"{plan_id}.json"
    )


def create_checkpoint(
    *,
    plan_id: str,
    specification: dict[str, Any],
    tasks: list[HistoricalTask],
) -> dict[str, Any]:

    now = utc_now()


    return {
        "schemaVersion":
            CHECKPOINT_SCHEMA_VERSION,

        "planId":
            plan_id,

        "createdAt":
            now,

        "updatedAt":
            now,

        "plan":
            specification,

        "taskOrder":
            [
                task.task_id
                for task
                in tasks
            ],

        "tasks":
            {
                task.task_id: {

                    "task":
                        task.specification(),

                    "status":
                        "pending",

                    "attempts":
                        0,

                    "lastRunId":
                        None,

                    "lastStartedAt":
                        None,

                    "lastFinishedAt":
                        None,

                    "lastError":
                        None,

                }

                for task
                in tasks
            },
    }


def load_checkpoint(
    path: Path,
) -> dict[str, Any]:

    try:

        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:

        raise HistoricalPlannerError(
            "Unable to read checkpoint: "
            + str(path)
        ) from error


    if not isinstance(
        payload,
        dict,
    ):

        stop(
            "Checkpoint must contain a JSON object."
        )


    return payload


def save_checkpoint(
    path: Path,
    checkpoint: dict[str, Any],
) -> None:

    checkpoint[
        "updatedAt"
    ] = utc_now()


    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    write_json_atomic(
        path,
        checkpoint,
    )


def load_or_create_checkpoint(
    *,
    path: Path,
    plan_id: str,
    specification: dict[str, Any],
    tasks: list[HistoricalTask],
) -> dict[str, Any]:

    if not path.exists():

        checkpoint = create_checkpoint(
            plan_id=
                plan_id,

            specification=
                specification,

            tasks=
                tasks,
        )

        save_checkpoint(
            path,
            checkpoint,
        )

        return checkpoint


    checkpoint = load_checkpoint(
        path
    )


    if (
        checkpoint.get(
            "schemaVersion"
        )
        != CHECKPOINT_SCHEMA_VERSION
    ):

        stop(
            "Unsupported checkpoint schema."
        )


    if (
        checkpoint.get(
            "planId"
        )
        != plan_id
    ):

        stop(
            "Checkpoint belongs to a "
            "different historical plan."
        )


    if (
        checkpoint.get(
            "plan"
        )
        != specification
    ):

        stop(
            "Checkpoint plan specification "
            "does not match current request."
        )


    expected_ids = [
        task.task_id
        for task
        in tasks
    ]


    if (
        checkpoint.get(
            "taskOrder"
        )
        != expected_ids
    ):

        stop(
            "Checkpoint task order does not "
            "match deterministic plan."
        )


    task_state = checkpoint.get(
        "tasks"
    )


    if not isinstance(
        task_state,
        dict,
    ):

        stop(
            "Checkpoint tasks are invalid."
        )


    for task_id in expected_ids:

        state = task_state.get(
            task_id
        )


        if not isinstance(
            state,
            dict,
        ):

            stop(
                "Checkpoint task missing: "
                + task_id
            )


        if (
            state.get(
                "status"
            )
            == "running"
        ):

            state[
                "status"
            ] = "pending"

            state[
                "lastError"
            ] = (
                "Recovered interrupted task."
            )


    save_checkpoint(
        path,
        checkpoint,
    )


    return checkpoint


def checkpoint_counts(
    checkpoint: dict[str, Any],
) -> dict[str, int]:

    counts = {
        "pending":
            0,

        "running":
            0,

        "completed":
            0,

        "failed":
            0,

        "deferred":
            0,
    }


    tasks = checkpoint[
        "tasks"
    ]


    for state in tasks.values():

        status = state.get(
            "status"
        )


        if status in counts:

            counts[
                status
            ] += 1


    return counts


def runnable_task_ids(
    checkpoint: dict[str, Any],
    *,
    retry_failed: bool,
    max_tasks: int,
) -> list[str]:

    result: list[str] = []


    for task_id in checkpoint[
        "taskOrder"
    ]:

        state = checkpoint[
            "tasks"
        ][
            task_id
        ]

        status = state[
            "status"
        ]


        allowed = (
            status == "pending"
            or status == "deferred"
            or (
                retry_failed
                and status == "failed"
            )
        )


        if not allowed:
            continue


        result.append(
            task_id
        )


        if len(result) >= max_tasks:
            break


    return result


def run_id_for(
    *,
    plan_id: str,
    task_id: str,
    attempt: int,
) -> str:

    return (
        "history-"
        + plan_id[:8]
        + "-"
        + task_id[:12]
        + "-a"
        + str(attempt)
    )


def child_access_mode(
    access_mode: str,
) -> str:

    mapping = {
        "public_preview":
            "preview",

        "authenticated_data":
            "data",
    }


    if access_mode not in mapping:

        stop(
            "Unsupported resolved access mode "
            "for child connector: "
            + access_mode
        )


    return mapping[
        access_mode
    ]


def classify_failure(
    error: str | None,
) -> str:

    if not error:

        return (
            "failed"
        )


    transient_markers = (
        "429 Too Many Requests",
        "500 Internal Server Error",
        "502 Bad Gateway",
        "503 Service Unavailable",
        "504 Gateway Timeout",
        "ConnectTimeout",
        "ReadTimeout",
        "RemoteProtocolError",
        "ConnectError",
    )


    if any(
        marker in error
        for marker
        in transient_markers
    ):

        return (
            "deferred"
        )


    return (
        "failed"
    )


def execute_task(
    *,
    task: dict[str, Any],
    run_id: str,
    access_mode: str,
    max_records: int,
    apply: bool,
) -> tuple[
    bool,
    str | None,
]:

    command = [
        sys.executable,
        str(
            COMTRADE_SCRIPT
        ),

        "--access-mode",
        child_access_mode(
            access_mode
        ),

        "--frequency",
        str(
            task[
                "frequency"
            ]
        ),

        "--classification",
        str(
            task[
                "classification"
            ]
        ),

        "--reporter-code",
        str(
            task[
                "reporterCode"
            ]
        ),

        "--period",
        str(
            task[
                "period"
            ]
        ),

        "--partner-code",
        str(
            task[
                "partnerCode"
            ]
        ),

        "--cmd-code",
        str(
            task[
                "cmdCode"
            ]
        ),

        "--flow-code",
        str(
            task[
                "flowCode"
            ]
        ),

        "--max-records",
        str(
            max_records
        ),

        "--run-id",
        run_id,
    ]


    if apply:

        command.append(
            "--apply"
        )


    result = subprocess.run(
        command,
        cwd=
            PROJECT_ROOT,

        capture_output=True,
        text=True,
        check=False,
    )


    if result.returncode == 0:

        return (
            True,
            None,
        )


    combined = (
        (
            result.stderr
            or ""
        )
        + "\n"
        + (
            result.stdout
            or ""
        )
    ).strip()


    if len(combined) > 4000:

        combined = combined[
            -4000:
        ]


    return (
        False,
        combined
        or (
            "Comtrade child process "
            f"failed with code {result.returncode}."
        ),
    )


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Origin Hut deterministic and resumable "
            "UN Comtrade historical ingestion planner."
        )
    )


    parser.add_argument(
        "--reporter-codes",
        required=True,
        help=(
            "Comma-separated UN M49 reporter codes."
        ),
    )


    parser.add_argument(
        "--partner-codes",
        required=True,
        help=(
            "Comma-separated UN M49 partner codes."
        ),
    )


    parser.add_argument(
        "--cmd-codes",
        required=True,
        help=(
            "Comma-separated six-digit HS codes."
        ),
    )


    parser.add_argument(
        "--flow-codes",
        default="X,M",
        help=(
            "Comma-separated flow codes. "
            "Currently X and M."
        ),
    )


    parser.add_argument(
        "--frequency",
        choices=[
            "A",
            "M",
        ],
        default="A",
    )


    parser.add_argument(
        "--classification",
        default="HS",
        help=(
            "UN Comtrade classification search code. "
            "HS requests original/as-reported HS data; "
            "the returned record is validated against "
            "the canonical H6 / HS2022 observation."
        ),
    )


    parser.add_argument(
        "--periods",
        default=None,
        help=(
            "Explicit comma-separated periods. "
            "YYYY for annual or YYYYMM for monthly."
        ),
    )


    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
    )


    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
    )


    parser.add_argument(
        "--access-mode",
        choices=[
            "auto",
            "preview",
            "data",
        ],
        default="auto",
    )


    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help=(
            "Defaults to 500 for public preview "
            "and 100000 for authenticated data."
        ),
    )


    parser.add_argument(
        "--max-tasks",
        type=int,
        default=100,
        help=(
            "Maximum pending tasks executed in this invocation."
        ),
    )


    parser.add_argument(
        "--requests-per-second",
        type=float,
        default=1.0,
        help=(
            "Throttle between requests. "
            "Default is deliberately conservative."
        ),
    )


    parser.add_argument(
        "--checkpoint",
        default=None,
        help=(
            "Optional checkpoint JSON path."
        ),
    )


    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Execute planned API tasks. "
            "Without this flag the command is plan-only."
        ),
    )


    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "When executing, persist canonical observations "
            "to PostgreSQL."
        ),
    )


    parser.add_argument(
        "--retry-failed",
        action="store_true",
    )


    parser.add_argument(
        "--continue-on-error",
        action="store_true",
    )


    parser.add_argument(
        "--allow-preview-batch",
        action="store_true",
        help=(
            "Permit more than ten tasks when resolved "
            "access mode is public preview."
        ),
    )


    args = parser.parse_args()


    if args.max_tasks < 1:

        parser.error(
            "--max-tasks must be at least 1."
        )


    if (
        args.requests_per_second <= 0
        or args.requests_per_second > 5
    ):

        parser.error(
            "--requests-per-second must be "
            "greater than 0 and no more than 5."
        )


    if args.apply and not args.execute:

        parser.error(
            "--apply requires --execute."
        )


    return args


def main() -> int:

    args = parse_args()


    reporter_codes = parse_int_list(
        args.reporter_codes
    )

    partner_codes = parse_int_list(
        args.partner_codes
    )

    cmd_codes = parse_string_list(
        args.cmd_codes
    )

    flow_codes = parse_string_list(
        args.flow_codes
    )


    unsupported_flows = (
        set(
            flow_codes
        )
        - {
            "X",
            "M",
        }
    )


    if unsupported_flows:

        stop(
            "Unsupported OH13 historical flow codes: "
            + ",".join(
                sorted(
                    unsupported_flows
                )
            )
        )


    explicit_periods = (
        parse_string_list(
            args.periods
        )
        if args.periods
        else None
    )


    periods = build_periods(
        frequency=
            args.frequency,

        start_year=
            args.start_year,

        end_year=
            args.end_year,

        explicit_periods=
            explicit_periods,
    )


    specification = plan_specification(
        reporter_codes=
            reporter_codes,

        periods=
            periods,

        partner_codes=
            partner_codes,

        cmd_codes=
            cmd_codes,

        flow_codes=
            flow_codes,

        frequency=
            args.frequency,

        classification=
            args.classification.upper(),
    )


    tasks = build_tasks(
        reporter_codes=
            reporter_codes,

        periods=
            periods,

        partner_codes=
            partner_codes,

        cmd_codes=
            cmd_codes,

        flow_codes=
            flow_codes,

        frequency=
            args.frequency,

        classification=
            args.classification.upper(),
    )


    plan_id = plan_id_for(
        specification
    )


    checkpoint_path = (
        Path(
            args.checkpoint
        ).resolve()

        if args.checkpoint

        else checkpoint_path_for(
            plan_id
        )
    )


    checkpoint = load_or_create_checkpoint(
        path=
            checkpoint_path,

        plan_id=
            plan_id,

        specification=
            specification,

        tasks=
            tasks,
    )


    try:

        access_mode = resolve_access_mode(
            args.access_mode,
            comtrade_api_key(),
        )

        max_records = resolve_max_records(
            args.max_records,
            access_mode,
        )

    except ConnectorError as error:

        raise HistoricalPlannerError(
            str(error)
        ) from error


    counts = checkpoint_counts(
        checkpoint
    )


    runnable_ids = runnable_task_ids(
        checkpoint,
        retry_failed=
            args.retry_failed,

        max_tasks=
            args.max_tasks,
    )


    summary = {
        "ok":
            True,

        "planId":
            plan_id,

        "checkpoint":
            str(
                checkpoint_path
            ),

        "accessMode":
            access_mode,

        "maxRecords":
            max_records,

        "execute":
            args.execute,

        "apply":
            args.apply,

        "frequency":
            args.frequency,

        "classification":
            args.classification.upper(),

        "periodCount":
            len(
                periods
            ),

        "reporterCount":
            len(
                reporter_codes
            ),

        "partnerCount":
            len(
                partner_codes
            ),

        "commodityCount":
            len(
                cmd_codes
            ),

        "flowCount":
            len(
                flow_codes
            ),

        "plannedCalls":
            len(
                tasks
            ),

        "thisInvocationLimit":
            args.max_tasks,

        "runnableNow":
            len(
                runnable_ids
            ),

        "checkpointCounts":
            counts,
    }


    print("")
    print(
        "=== COMTRADE HISTORICAL PLAN ==="
    )

    print(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        )
    )


    if not args.execute:

        print("")
        print(
            "PLAN ONLY: no API requests executed."
        )

        return 0


    if (
        access_mode == "public_preview"
        and len(runnable_ids) > 10
        and not args.allow_preview_batch
    ):

        stop(
            "Refusing a public-preview batch larger "
            "than 10 tasks. Configure "
            "UN_COMTRADE_API_KEY or explicitly use "
            "--allow-preview-batch."
        )


    delay_seconds = (
        1.0
        / args.requests_per_second
    )


    for index, task_id in enumerate(
        runnable_ids,
        start=1,
    ):

        state = checkpoint[
            "tasks"
        ][
            task_id
        ]


        state[
            "attempts"
        ] = (
            int(
                state.get(
                    "attempts",
                    0,
                )
            )
            + 1
        )


        attempt = state[
            "attempts"
        ]


        run_id = run_id_for(
            plan_id=
                plan_id,

            task_id=
                task_id,

            attempt=
                attempt,
        )


        state[
            "status"
        ] = "running"

        state[
            "lastRunId"
        ] = run_id

        state[
            "lastStartedAt"
        ] = utc_now()

        state[
            "lastError"
        ] = None


        save_checkpoint(
            checkpoint_path,
            checkpoint,
        )


        task = state[
            "task"
        ]


        print("")
        print(
            f"[{index}/{len(runnable_ids)}] "
            f"{task_id} "
            f"reporter={task['reporterCode']} "
            f"partner={task['partnerCode']} "
            f"period={task['period']} "
            f"hs={task['cmdCode']} "
            f"flow={task['flowCode']}"
        )


        success, error = execute_task(
            task=
                task,

            run_id=
                run_id,

            access_mode=
                access_mode,

            max_records=
                max_records,

            apply=
                args.apply,
        )


        state[
            "lastFinishedAt"
        ] = utc_now()


        if success:

            state[
                "status"
            ] = "completed"

            state[
                "lastError"
            ] = None

            print(
                "PASS:",
                task_id,
            )

        else:

            failure_status = classify_failure(
                error
            )

            state[
                "status"
            ] = failure_status

            state[
                "lastError"
            ] = error

            print(
                failure_status.upper() + ":",
                task_id,
            )

            if error:

                print(
                    error
                )


        save_checkpoint(
            checkpoint_path,
            checkpoint,
        )


        if (
            not success
            and state[
                "status"
            ] == "failed"
            and not args.continue_on_error
        ):

            stop(
                "Historical ingestion stopped "
                "after permanent task failure."
            )


        if index < len(
            runnable_ids
        ):

            time.sleep(
                delay_seconds
            )


    final_counts = checkpoint_counts(
        checkpoint
    )


    print("")
    print(
        "=== HISTORICAL CHECKPOINT ==="
    )

    print(
        json.dumps(
            final_counts,
            indent=2,
        )
    )


    return 0


if __name__ == "__main__":

    try:

        raise SystemExit(
            main()
        )

    except (
        HistoricalPlannerError,
        ConnectorError,
    ) as error:

        print(
            "STOP:",
            error,
            file=sys.stderr,
        )

        raise SystemExit(
            2
        )
