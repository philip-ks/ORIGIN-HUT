from __future__ import annotations

import hashlib
import json
import os
import re

from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import polars as pl


TRADE_SCHEMA_VERSION = (
    "origin_hut_trade_observation_v1"
)


_DECIMAL_TYPE = pl.Decimal(
    precision=38,
    scale=6,
)


TRADE_SCHEMA: dict[str, pl.DataType] = {

    "sourceSystem":
        pl.String,

    "sourceExternalId":
        pl.String,

    "sourceContentHash":
        pl.String,

    "reporterISO3":
        pl.String,

    "partnerISO3":
        pl.String,

    "flowDirection":
        pl.String,

    "classificationCode":
        pl.String,

    "hsCode":
        pl.String,

    "referenceYear":
        pl.Int32,

    "periodStart":
        pl.Date,

    "periodEnd":
        pl.Date,

    "periodType":
        pl.String,

    "quantity":
        _DECIMAL_TYPE,

    "quantityUnit":
        pl.String,

    "netWeightKg":
        _DECIMAL_TYPE,

    "grossWeightKg":
        _DECIMAL_TYPE,

    "tradeValueUsd":
        _DECIMAL_TYPE,

    "fobValueUsd":
        _DECIMAL_TYPE,

    "cifValueUsd":
        _DECIMAL_TYPE,

    "customsCode":
        pl.String,

    "transportModeCode":
        pl.String,

    "isAggregate":
        pl.Boolean,

    "isReported":
        pl.Boolean,

    "isQtyEstimated":
        pl.Boolean,

    "isNetWeightEstimated":
        pl.Boolean,

    "isGrossWeightEstimated":
        pl.Boolean,

    "rawMetadataJson":
        pl.String,
}


def _as_date(
    value: Any,
    field: str,
) -> date:

    if isinstance(
        value,
        date,
    ):

        return value


    if isinstance(
        value,
        str,
    ):

        try:

            return date.fromisoformat(
                value
            )

        except ValueError as error:

            raise ValueError(
                f"{field} must be YYYY-MM-DD."
            ) from error


    raise ValueError(
        f"{field} must be a date."
    )


def _as_decimal(
    value: Any,
) -> Decimal | None:

    if value is None:
        return None


    return Decimal(
        str(value)
    )


def _required_text(
    row: dict[str, Any],
    field: str,
) -> str:

    value = row.get(
        field
    )


    if value is None:

        raise ValueError(
            f"{field} is required."
        )


    text = str(
        value
    ).strip()


    if not text:

        raise ValueError(
            f"{field} is required."
        )


    return text


def normalize_trade_row(
    row: dict[str, Any],
) -> dict[str, Any]:

    reporter = _required_text(
        row,
        "reporterISO3",
    ).upper()

    partner_value = row.get(
        "partnerISO3"
    )

    partner = (
        None
        if partner_value is None
        else str(
            partner_value
        ).strip().upper()
    )

    if partner == "W00":
        partner = None

    flow = _required_text(
        row,
        "flowDirection",
    ).lower()

    hs_code = _required_text(
        row,
        "hsCode",
    )

    source_system = _required_text(
        row,
        "sourceSystem",
    )

    source_external_id = _required_text(
        row,
        "sourceExternalId",
    )

    source_content_hash = _required_text(
        row,
        "sourceContentHash",
    ).lower()


    if not re.fullmatch(
        r"[A-Z]{3}",
        reporter,
    ):

        raise ValueError(
            "reporterISO3 must contain three uppercase letters."
        )


    if (
        partner is not None
        and not re.fullmatch(
            r"[A-Z]{3}",
            partner,
        )
    ):

        raise ValueError(
            "partnerISO3 must contain three uppercase letters when present."
        )


    if flow not in {
        "export",
        "import",
    }:

        raise ValueError(
            "flowDirection must be export or import."
        )


    if not re.fullmatch(
        r"\d{6}",
        hs_code,
    ):

        raise ValueError(
            "hsCode must be a six-digit HS code."
        )


    if not re.fullmatch(
        r"[0-9a-f]{64}",
        source_content_hash,
    ):

        raise ValueError(
            "sourceContentHash must be a SHA-256 hex digest."
        )


    period_start = _as_date(
        row.get(
            "periodStart"
        ),
        "periodStart",
    )

    period_end = _as_date(
        row.get(
            "periodEnd"
        ),
        "periodEnd",
    )


    if period_end < period_start:

        raise ValueError(
            "periodEnd cannot be earlier than periodStart."
        )


    reference_year = int(
        row.get(
            "referenceYear"
        )
    )


    if reference_year != period_start.year:

        raise ValueError(
            "referenceYear must match periodStart year."
        )


    raw_metadata = row.get(
        "rawMetadata"
    )


    raw_metadata_json = json.dumps(
        raw_metadata or {},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


    return {

        "sourceSystem":
            source_system,

        "sourceExternalId":
            source_external_id,

        "sourceContentHash":
            source_content_hash,

        "reporterISO3":
            reporter,

        "partnerISO3":
            partner,

        "flowDirection":
            flow,

        "classificationCode":
            _required_text(
                row,
                "classificationCode",
            ),

        "hsCode":
            hs_code,

        "referenceYear":
            reference_year,

        "periodStart":
            period_start,

        "periodEnd":
            period_end,

        "periodType":
            _required_text(
                row,
                "periodType",
            ).lower(),

        "quantity":
            _as_decimal(
                row.get(
                    "quantity"
                )
            ),

        "quantityUnit":
            row.get(
                "quantityUnit"
            ),

        "netWeightKg":
            _as_decimal(
                row.get(
                    "netWeightKg"
                )
            ),

        "grossWeightKg":
            _as_decimal(
                row.get(
                    "grossWeightKg"
                )
            ),

        "tradeValueUsd":
            _as_decimal(
                row.get(
                    "tradeValueUsd"
                )
            ),

        "fobValueUsd":
            _as_decimal(
                row.get(
                    "fobValueUsd"
                )
            ),

        "cifValueUsd":
            _as_decimal(
                row.get(
                    "cifValueUsd"
                )
            ),

        "customsCode":
            (
                str(
                    row[
                        "customsCode"
                    ]
                )
                if row.get(
                    "customsCode"
                )
                is not None
                else None
            ),

        "transportModeCode":
            (
                str(
                    row[
                        "transportModeCode"
                    ]
                )
                if row.get(
                    "transportModeCode"
                )
                is not None
                else None
            ),

        "isAggregate":
            row.get(
                "isAggregate"
            ),

        "isReported":
            row.get(
                "isReported"
            ),

        "isQtyEstimated":
            row.get(
                "isQtyEstimated"
            ),

        "isNetWeightEstimated":
            row.get(
                "isNetWeightEstimated"
            ),

        "isGrossWeightEstimated":
            row.get(
                "isGrossWeightEstimated"
            ),

        "rawMetadataJson":
            raw_metadata_json,
    }


def trade_partition_path(
    parquet_root: str | Path,
    *,
    year: int,
    reporter_iso3: str,
    flow_direction: str,
    hs_code: str,
) -> Path:

    reporter = reporter_iso3.upper()

    flow = flow_direction.lower()


    if not re.fullmatch(
        r"[A-Z]{3}",
        reporter,
    ):

        raise ValueError(
            "Invalid reporter partition."
        )


    if flow not in {
        "export",
        "import",
    }:

        raise ValueError(
            "Invalid flow partition."
        )


    if not re.fullmatch(
        r"\d{6}",
        hs_code,
    ):

        raise ValueError(
            "Invalid HS partition."
        )


    return (
        Path(parquet_root)
        / "trade"
        / f"year={int(year)}"
        / f"reporter={reporter}"
        / f"flow={flow}"
        / f"hs={hs_code}"
    )


def _partition_filename(
    rows: list[dict[str, Any]],
) -> str:

    identities = sorted(
        (
            row[
                "sourceExternalId"
            ],
            row[
                "sourceContentHash"
            ],
        )
        for row in rows
    )


    encoded = json.dumps(
        identities,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


    digest = hashlib.sha256(
        encoded
    ).hexdigest()[:20]


    return (
        f"part-{digest}.parquet"
    )


def write_trade_partitions(
    records: Iterable[dict[str, Any]],
    parquet_root: str | Path,
) -> list[Path]:

    normalized_rows = [
        normalize_trade_row(
            record
        )
        for record in records
    ]


    if not normalized_rows:

        raise ValueError(
            "At least one trade observation is required."
        )


    groups: dict[
        tuple[int, str, str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)


    for row in normalized_rows:

        key = (
            row[
                "referenceYear"
            ],
            row[
                "reporterISO3"
            ],
            row[
                "flowDirection"
            ],
            row[
                "hsCode"
            ],
        )

        groups[key].append(
            row
        )


    written: list[Path] = []


    for (
        year,
        reporter,
        flow,
        hs_code,
    ), rows in sorted(
        groups.items()
    ):

        partition = trade_partition_path(
            parquet_root,
            year=year,
            reporter_iso3=reporter,
            flow_direction=flow,
            hs_code=hs_code,
        )

        partition.mkdir(
            parents=True,
            exist_ok=True,
        )


        destination = (
            partition
            / _partition_filename(
                rows
            )
        )


        temporary = destination.with_name(
            destination.name
            + ".tmp"
        )


        frame = pl.DataFrame(
            rows,
            schema=TRADE_SCHEMA,
            strict=False,
        )


        frame.write_parquet(
            temporary,
            compression="zstd",
            statistics=True,
        )


        os.replace(
            temporary,
            destination,
        )


        written.append(
            destination
        )


    return written
