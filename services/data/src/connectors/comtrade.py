from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import time

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx


SOURCE_FILE = Path(__file__).resolve()

SRC_ROOT = SOURCE_FILE.parents[1]
PROJECT_ROOT = SOURCE_FILE.parents[4]

STORAGE_ROOT = PROJECT_ROOT / "storage"
RAW_ROOT = STORAGE_ROOT / "imports" / "comtrade"
PARQUET_ROOT = STORAGE_ROOT / "parquet"


if str(SRC_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_ROOT),
    )


from storage.manifests import (
    artifact_descriptor,
    build_manifest,
    new_run_id,
    sha256_file,
    sha256_json,
    write_json_atomic,
)

from storage.parquet import (
    TRADE_SCHEMA_VERSION,
    write_trade_partitions,
)


from connectors.comtrade_canonical import (
    canonicalize_trade_observation,
)


SOURCE_CODE = "un_comtrade_trade"

PREVIEW_BASE = (
    "https://comtradeapi.un.org/public/v1/preview"
)


class ConnectorError(
    RuntimeError
):
    pass


def stop(
    message: str,
) -> None:

    raise ConnectorError(
        message
    )


def as_decimal(
    value: Any,
) -> Decimal | None:

    if value is None:
        return None

    return Decimal(
        str(value)
    )


def build_request_url(
    args: argparse.Namespace,
) -> str:

    route = (
        f"{PREVIEW_BASE}/"
        f"{args.type_code}/"
        f"{args.frequency}/"
        f"{args.classification}"
    )

    params = {
        "reporterCode":
            args.reporter_code,

        "period":
            args.period,

        "partnerCode":
            args.partner_code,

        "cmdCode":
            args.cmd_code,

        "flowCode":
            args.flow_code,

        "maxRecords":
            args.max_records,

        "format":
            "JSON",

        "breakdownMode":
            "classic",

        "includeDesc":
            "true",
    }

    request = httpx.Request(
        "GET",
        route,
        params=params,
    )

    return str(
        request.url
    )


def fetch_json(
    url: str,
) -> tuple[
    dict[str, Any],
    bytes,
]:

    retry_statuses = {
        429,
        500,
        502,
        503,
        504,
    }

    headers = {
        "Accept":
            "application/json",

        "User-Agent":
            "OriginHut/0.1 UN-Comtrade-Connector",
    }


    last_error: Exception | None = None


    for attempt in range(
        1,
        5,
    ):

        try:

            response = httpx.get(
                url,
                headers=headers,
                timeout=60.0,
                follow_redirects=True,
            )


            if (
                response.status_code
                in retry_statuses
                and attempt < 4
            ):

                time.sleep(
                    min(
                        2 ** (attempt - 1),
                        8,
                    )
                )

                continue


            response.raise_for_status()


            payload = response.json()


            if not isinstance(
                payload,
                dict,
            ):

                stop(
                    "UN Comtrade returned a non-object response."
                )


            return (
                payload,
                response.content,
            )


        except (
            httpx.HTTPError,
            json.JSONDecodeError,
        ) as error:

            last_error = error


            if attempt >= 4:
                raise


            time.sleep(
                min(
                    2 ** (attempt - 1),
                    8,
                )
            )


    if last_error is not None:
        raise last_error


    stop(
        "UN Comtrade request failed."
    )


def select_exact_record(
    payload: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:

    api_error = payload.get(
        "error"
    )

    if api_error:

        stop(
            "UN Comtrade returned error: "
            + str(api_error)
        )


    data = payload.get(
        "data"
    )


    if not isinstance(
        data,
        list,
    ):

        stop(
            "UN Comtrade response does not contain a data array."
        )


    matches: list[
        dict[str, Any]
    ] = []


    for record in data:

        if not isinstance(
            record,
            dict,
        ):

            continue


        try:

            reporter_code = int(
                record.get(
                    "reporterCode"
                )
            )

            partner_code = int(
                record.get(
                    "partnerCode"
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            continue


        if (
            reporter_code == args.reporter_code
            and partner_code == args.partner_code
            and str(
                record.get(
                    "cmdCode"
                )
            ) == args.cmd_code
            and str(
                record.get(
                    "flowCode"
                )
            ).upper() == args.flow_code
        ):

            matches.append(
                record
            )


    if len(matches) != 1:

        stop(
            "Expected exactly one exact UN Comtrade "
            f"observation; found {len(matches)}."
        )


    return matches[0]


def period_bounds(
    record: dict[str, Any],
) -> tuple[
    date,
    date,
    str,
]:

    frequency = str(
        record.get(
            "freqCode"
        )
    ).upper()

    year = int(
        record.get(
            "refYear"
        )
    )


    if frequency == "A":

        return (
            date(
                year,
                1,
                1,
            ),
            date(
                year,
                12,
                31,
            ),
            "annual",
        )


    if frequency == "M":

        month = int(
            record.get(
                "refMonth"
            )
        )


        if (
            month < 1
            or month > 12
        ):

            stop(
                "Invalid monthly refMonth."
            )


        last_day = calendar.monthrange(
            year,
            month,
        )[1]


        return (
            date(
                year,
                month,
                1,
            ),
            date(
                year,
                month,
                last_day,
            ),
            "monthly",
        )


    stop(
        "Unsupported frequency: "
        + frequency
    )


def external_id_for(
    record: dict[str, Any],
) -> str:

    identity_fields = (
        "typeCode",
        "freqCode",
        "refPeriodId",
        "reporterCode",
        "flowCode",
        "partnerCode",
        "partner2Code",
        "classificationCode",
        "cmdCode",
        "customsCode",
        "mosCode",
        "motCode",
    )


    return "|".join(
        f"{field}={record.get(field)}"
        for field
        in identity_fields
    )


def normalize_record(
    record: dict[str, Any],
    *,
    request_url: str,
    raw_artifact_hash: str,
    run_id: str,
) -> dict[str, Any]:

    classification_code = str(
        record.get(
            "classificationCode"
        )
    ).upper()


    if classification_code != "H6":

        stop(
            "Expected H6 / HS2022 classification."
        )


    try:

        aggregate_level = int(
            record.get(
                "aggrLevel"
            )
        )

    except (
        TypeError,
        ValueError,
    ) as error:

        raise ConnectorError(
            "Invalid Comtrade aggregate level."
        ) from error


    if aggregate_level != 6:

        stop(
            "OH13 currently requires six-digit HS observations."
        )


    reporter_iso3 = str(
        record.get(
            "reporterISO"
        )
    ).upper()


    if (
        len(reporter_iso3) != 3
        or not reporter_iso3.isalpha()
    ):

        stop(
            "Invalid reporter ISO3."
        )


    partner_code = int(
        record.get(
            "partnerCode"
        )
    )

    partner_source_iso = str(
        record.get(
            "partnerISO"
        )
        or ""
    ).upper()


    if (
        partner_code == 0
        or partner_source_iso == "W00"
    ):

        partner_iso3 = None

    else:

        partner_iso3 = partner_source_iso


        if (
            len(partner_iso3) != 3
            or not partner_iso3.isalpha()
        ):

            stop(
                "Invalid partner ISO3."
            )


    source_flow = str(
        record.get(
            "flowCode"
        )
    ).upper()


    flow_map = {
        "X":
            "export",

        "M":
            "import",
    }


    if source_flow not in flow_map:

        stop(
            "Unsupported flowCode: "
            + source_flow
        )


    hs_code = str(
        record.get(
            "cmdCode"
        )
    )


    if (
        len(hs_code) != 6
        or not hs_code.isdigit()
    ):

        stop(
            "Expected a six-digit HS code."
        )


    period_start, period_end, period_type = (
        period_bounds(
            record
        )
    )


    record_hash = sha256_json(
        record
    )


    external_id = external_id_for(
        record
    )


    return {
        "sourceSystem":
            "un_comtrade",

        "sourceExternalId":
            external_id,

        "sourceContentHash":
            record_hash,

        "reporterISO3":
            reporter_iso3,

        "partnerISO3":
            partner_iso3,

        "flowDirection":
            flow_map[
                source_flow
            ],

        "classificationCode":
            classification_code,

        "hsCode":
            hs_code,

        "referenceYear":
            int(
                record.get(
                    "refYear"
                )
            ),

        "periodStart":
            period_start,

        "periodEnd":
            period_end,

        "periodType":
            period_type,

        "quantity":
            as_decimal(
                record.get(
                    "qty"
                )
            ),

        "quantityUnit":
            record.get(
                "qtyUnitAbbr"
            ),

        "netWeightKg":
            as_decimal(
                record.get(
                    "netWgt"
                )
            ),

        "grossWeightKg":
            as_decimal(
                record.get(
                    "grossWgt"
                )
            ),

        "tradeValueUsd":
            as_decimal(
                record.get(
                    "primaryValue"
                )
            ),

        "fobValueUsd":
            as_decimal(
                record.get(
                    "fobvalue"
                )
            ),

        "cifValueUsd":
            as_decimal(
                record.get(
                    "cifvalue"
                )
            ),

        "customsCode":
            (
                str(
                    record.get(
                        "customsCode"
                    )
                )
                if record.get(
                    "customsCode"
                )
                is not None
                else None
            ),

        "transportModeCode":
            (
                str(
                    record.get(
                        "motCode"
                    )
                )
                if record.get(
                    "motCode"
                )
                is not None
                else None
            ),

        "isAggregate":
            record.get(
                "isAggregate"
            ),

        "isReported":
            record.get(
                "isReported"
            ),

        "isQtyEstimated":
            record.get(
                "isQtyEstimated"
            ),

        "isNetWeightEstimated":
            record.get(
                "isNetWgtEstimated"
            ),

        "isGrossWeightEstimated":
            record.get(
                "isGrossWgtEstimated"
            ),

        "rawMetadata": {
            "runId":
                run_id,

            "requestUrl":
                request_url,

            "rawArtifactSha256":
                raw_artifact_hash,

            "sourceRecordSha256":
                record_hash,

            "reporterCode":
                record.get(
                    "reporterCode"
                ),

            "reporterDesc":
                record.get(
                    "reporterDesc"
                ),

            "partnerCode":
                record.get(
                    "partnerCode"
                ),

            "partnerISO":
                record.get(
                    "partnerISO"
                ),

            "partnerDesc":
                record.get(
                    "partnerDesc"
                ),

            "partner2Code":
                record.get(
                    "partner2Code"
                ),

            "partner2ISO":
                record.get(
                    "partner2ISO"
                ),

            "partner2Desc":
                record.get(
                    "partner2Desc"
                ),

            "cmdDesc":
                record.get(
                    "cmdDesc"
                ),

            "aggrLevel":
                aggregate_level,

            "customsDesc":
                record.get(
                    "customsDesc"
                ),

            "transportModeDesc":
                record.get(
                    "motDesc"
                ),

            "legacyEstimationFlag":
                record.get(
                    "legacyEstimationFlag"
                ),
        },
    }


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Origin Hut UN Comtrade Bronze/Silver "
            "analytical ingestion."
        )
    )


    parser.add_argument(
        "--type-code",
        default="C",
        choices=[
            "C",
        ],
    )


    parser.add_argument(
        "--frequency",
        default="A",
        choices=[
            "A",
            "M",
        ],
    )


    parser.add_argument(
        "--classification",
        default="HS",
    )


    parser.add_argument(
        "--reporter-code",
        type=int,
        default=699,
    )


    parser.add_argument(
        "--period",
        default="2024",
    )


    parser.add_argument(
        "--partner-code",
        type=int,
        default=784,
    )


    parser.add_argument(
        "--cmd-code",
        default="380210",
    )


    parser.add_argument(
        "--flow-code",
        default="X",
        choices=[
            "X",
            "M",
        ],
    )


    parser.add_argument(
        "--max-records",
        type=int,
        default=20,
    )


    parser.add_argument(
        "--run-id",
        default=None,
    )


    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist provenance and the canonical "
            "trade_flow fact to PostgreSQL."
        ),
    )


    args = parser.parse_args()


    if (
        args.max_records < 1
        or args.max_records > 500
    ):

        parser.error(
            "--max-records must be between 1 and 500."
        )


    if (
        len(args.cmd_code) != 6
        or not args.cmd_code.isdigit()
    ):

        parser.error(
            "--cmd-code must be a six-digit HS code."
        )


    return args


def main() -> int:

    args = parse_args()

    run_id = (
        args.run_id
        or new_run_id()
    )


    run_directory = (
        RAW_ROOT
        / run_id
    )


    if run_directory.exists():

        stop(
            "Run directory already exists: "
            + str(run_directory)
        )


    run_directory.mkdir(
        parents=True,
        exist_ok=False,
    )


    request_url = build_request_url(
        args
    )


    print("")
    print(
        "=== UN COMTRADE REQUEST ==="
    )
    print(
        "runId:",
        run_id,
    )
    print(
        "url:",
        request_url,
    )


    payload, raw_bytes = fetch_json(
        request_url
    )


    raw_path = (
        run_directory
        / "response.json"
    )

    temporary_raw_path = (
        run_directory
        / "response.json.tmp"
    )


    temporary_raw_path.write_bytes(
        raw_bytes
    )

    os.replace(
        temporary_raw_path,
        raw_path,
    )


    raw_artifact_hash = sha256_file(
        raw_path
    )


    record = select_exact_record(
        payload,
        args,
    )


    normalized = normalize_record(
        record,
        request_url=request_url,
        raw_artifact_hash=raw_artifact_hash,
        run_id=run_id,
    )


    parquet_paths = write_trade_partitions(
        [
            normalized
        ],
        PARQUET_ROOT,
    )


    database_result = None


    if args.apply:

        database_result = canonicalize_trade_observation(
            record,
            normalized,
            artifact_run_id=
                run_id,
            request_url=
                request_url,
            raw_path=
                raw_path,
            parquet_paths=
                parquet_paths,
        )


        print("")
        print(
            "=== POSTGRESQL CANONICALIZATION ==="
        )

        print(
            json.dumps(
                database_result,
                indent=2,
                ensure_ascii=False,
            )
        )


    manifest = build_manifest(
        source_code=
            SOURCE_CODE,

        run_id=
            run_id,

        request={
            "mode":
                "public_preview",

            "url":
                request_url,

            "typeCode":
                args.type_code,

            "frequency":
                args.frequency,

            "classificationSearchCode":
                args.classification,

            "reporterCode":
                args.reporter_code,

            "period":
                args.period,

            "partnerCode":
                args.partner_code,

            "cmdCode":
                args.cmd_code,

            "flowCode":
                args.flow_code,

            "maxRecords":
                args.max_records,
        },

        raw_artifacts=[
            artifact_descriptor(
                raw_path,
                root=STORAGE_ROOT,
            )
        ],

        parquet_artifacts=[
            artifact_descriptor(
                path,
                root=STORAGE_ROOT,
            )
            for path
            in parquet_paths
        ],

        record_count=
            1,

        schema_version=
            TRADE_SCHEMA_VERSION,

        metadata={
            "responseCount":
                payload.get(
                    "count"
                ),

            "elapsedTime":
                payload.get(
                    "elapsedTime"
                ),

            "sourceExternalId":
                normalized[
                    "sourceExternalId"
                ],

            "sourceRecordSha256":
                normalized[
                    "sourceContentHash"
                ],

            "rawArtifactSha256":
                raw_artifact_hash,

            "databaseWrites":
                (
                    1
                    if database_result
                    else 0
                ),

            "database":
                database_result,
        },
    )


    manifest_path = (
        run_directory
        / "manifest.json"
    )


    write_json_atomic(
        manifest_path,
        manifest,
    )


    summary = {
        "ok":
            True,

        "runId":
            run_id,

        "sourceExternalId":
            normalized[
                "sourceExternalId"
            ],

        "sourceRecordSha256":
            normalized[
                "sourceContentHash"
            ],

        "rawArtifactSha256":
            raw_artifact_hash,

        "rawPath":
            str(
                raw_path
            ),

        "manifestPath":
            str(
                manifest_path
            ),

        "parquetPaths":
            [
                str(path)
                for path
                in parquet_paths
            ],

        "reporterISO3":
            normalized[
                "reporterISO3"
            ],

        "partnerISO3":
            normalized[
                "partnerISO3"
            ],

        "flowDirection":
            normalized[
                "flowDirection"
            ],

        "hsCode":
            normalized[
                "hsCode"
            ],

        "periodStart":
            normalized[
                "periodStart"
            ].isoformat(),

        "periodEnd":
            normalized[
                "periodEnd"
            ].isoformat(),

        "tradeValueUsd":
            (
                str(
                    normalized[
                        "tradeValueUsd"
                    ]
                )
                if normalized[
                    "tradeValueUsd"
                ]
                is not None
                else None
            ),

        "databaseWrites":
            (
                1
                if database_result
                else 0
            ),

        "database":
            database_result,
    }


    print("")
    print(
        "=== INGESTION ARTIFACTS ==="
    )

    print(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        )
    )


    print("")
    print(
        "=============================================="
    )
    print(
        "OH13 COMTRADE INGESTION PASSED"
    )
    print(
        "=============================================="
    )


    return 0


if __name__ == "__main__":

    try:

        raise SystemExit(
            main()
        )

    except ConnectorError as error:

        print(
            "STOP:",
            error,
            file=sys.stderr,
        )

        raise SystemExit(
            2
        )
