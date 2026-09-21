from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[4]


CLASSIFICATION = "H6"

NOMENCLATURE = "HS2022"

SOURCE_PROVIDER = (
    "United Nations Statistics Division / "
    "UN Comtrade"
)

SOURCE_URL = (
    "https://"
    + "comtradeapi.un.org"
    + "/files/v1/app/reference/H6.json"
)


def sha256_bytes(
    value: bytes,
) -> str:

    return hashlib.sha256(
        value
    ).hexdigest()


def first_value(
    record: dict[str, Any],
    names: list[str],
) -> Any:

    lowered = {
        str(key).casefold(): value
        for key, value in record.items()
    }

    for name in names:

        if name.casefold() in lowered:

            return lowered[
                name.casefold()
            ]

    return None


def find_record_list(
    value: Any,
) -> list[dict[str, Any]]:

    # Expected format is an array of objects,
    # but this keeps the diagnostic resilient
    # if UN Comtrade wraps it in a JSON object.

    if isinstance(
        value,
        list,
    ):

        dictionaries = [
            item
            for item in value
            if isinstance(
                item,
                dict,
            )
        ]

        if dictionaries:

            sample = dictionaries[0]

            keys = {
                str(key).casefold()
                for key in sample.keys()
            }

            if (
                "id" in keys
                or "code" in keys
                or "cmdcode" in keys
            ):
                return dictionaries


        for item in value:

            result = (
                find_record_list(
                    item
                )
            )

            if result:
                return result


    if isinstance(
        value,
        dict,
    ):

        preferred_keys = [
            "results",
            "data",
            "items",
            "records",
        ]

        for key in preferred_keys:

            if key in value:

                result = (
                    find_record_list(
                        value[key]
                    )
                )

                if result:
                    return result


        for nested in value.values():

            result = (
                find_record_list(
                    nested
                )
            )

            if result:
                return result


    return []


def normalize_record(
    raw: dict[str, Any],
) -> dict[str, Any]:

    code = first_value(
        raw,
        [
            "id",
            "code",
            "cmdCode",
            "commodityCode",
        ],
    )

    text = first_value(
        raw,
        [
            "text",
            "description",
            "commodityName",
            "name",
        ],
    )

    parent = first_value(
        raw,
        [
            "parent",
            "parentCode",
        ],
    )

    is_leaf = first_value(
        raw,
        [
            "isLeaf",
            "leaf",
        ],
    )

    aggregation_level = first_value(
        raw,
        [
            "aggrlevel",
            "aggregationLevel",
            "level",
        ],
    )

    unit = first_value(
        raw,
        [
            "standardUnitAbbr",
            "standardUnit",
            "unit",
        ],
    )

    if code is not None:
        code = str(
            code
        ).strip()

    if text is not None:
        text = str(
            text
        ).strip()

    if parent is not None:
        parent = str(
            parent
        ).strip()

    return {
        "code":
            code,

        "description":
            text,

        "parent":
            parent,

        "is_leaf":
            is_leaf,

        "aggregation_level":
            aggregation_level,

        "standard_unit":
            unit,

        "raw":
            raw,
    }


def expected_parent(
    code: str,
) -> str | None:

    if len(code) == 4:
        return code[:2]

    if len(code) == 6:
        return code[:4]

    return None


def main() -> None:

    print(
        "Official HS 2022 reference inspector"
    )

    print(
        f"Classification: {CLASSIFICATION}"
    )

    print(
        f"Nomenclature: {NOMENCLATURE}"
    )

    print()
    print(
        "Downloading official "
        "UNSD / UN Comtrade H6 reference..."
    )


    response = httpx.get(
        SOURCE_URL,
        timeout=180.0,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "OriginHut/0.1 "
                "(HS2022 reference inspection)"
            )
        },
    )

    response.raise_for_status()


    content = response.content


    if len(content) < 100_000:

        raise RuntimeError(
            "Downloaded H6 reference file "
            "is unexpectedly small."
        )


    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )


    snapshot_directory = (
        ROOT
        / "storage"
        / "imports"
        / "hs2022"
        / timestamp
    )


    snapshot_directory.mkdir(
        parents=True,
        exist_ok=True,
    )


    snapshot_path = (
        snapshot_directory
        / "H6.json"
    )


    snapshot_path.write_bytes(
        content
    )


    snapshot_hash = (
        sha256_bytes(
            content
        )
    )


    print(
        f"Raw snapshot saved: "
        f"{snapshot_path}"
    )

    print(
        f"Snapshot size: "
        f"{len(content):,} bytes"
    )

    print(
        f"Snapshot SHA-256: "
        f"{snapshot_hash}"
    )


    try:

        document = json.loads(
            content.decode(
                "utf-8-sig"
            )
        )

    except Exception as error:

        raise RuntimeError(
            "Downloaded H6 reference "
            "is not valid JSON."
        ) from error


    print()
    print(
        "Top-level JSON type:",
        type(document).__name__,
    )


    if isinstance(
        document,
        dict,
    ):

        print(
            "Top-level keys:",
            list(
                document.keys()
            )[:30],
        )


    raw_records = (
        find_record_list(
            document
        )
    )


    if not raw_records:

        raise RuntimeError(
            "Unable to locate HS records "
            "inside the H6 JSON."
        )


    records = [
        normalize_record(
            record
        )
        for record in raw_records
    ]


    print()
    print(
        f"Raw reference objects: "
        f"{len(records):,}"
    )


    records_with_code = [
        record
        for record in records
        if record["code"]
    ]


    numeric_records = [
        record
        for record in records_with_code
        if (
            record["code"].isdigit()
            and len(
                record["code"]
            ) in (
                2,
                4,
                6,
            )
        )
    ]


    if len(numeric_records) < 6_000:

        raise RuntimeError(
            "Too few valid HS 2022 "
            "2/4/6-digit records were parsed."
        )


    code_counter = Counter(
        record["code"]
        for record in numeric_records
    )


    duplicate_codes = {
        code: count
        for code, count
        in code_counter.items()
        if count > 1
    }


    length_counts = Counter(
        len(
            record["code"]
        )
        for record in numeric_records
    )


    supplied_level_counts = Counter(
        str(
            record[
                "aggregation_level"
            ]
        )
        for record in records
    )


    leaf_counts = Counter(
        str(
            record[
                "is_leaf"
            ]
        )
        for record in records
    )


    code_lookup = {
        record["code"]:
            record
        for record in numeric_records
    }


    missing_parent_examples = []


    for record in numeric_records:

        parent = expected_parent(
            record["code"]
        )

        if (
            parent
            and parent
            not in code_lookup
        ):

            missing_parent_examples.append(
                {
                    "code":
                        record["code"],

                    "expected_parent":
                        parent,

                    "description":
                        record[
                            "description"
                        ],
                }
            )


    sample_codes = [
        "01",
        "0101",
        "010121",
        "30",
        "3004",
        "300490",
        "84",
        "8471",
        "847130",
        "85",
        "8517",
        "851713",
        "87",
        "8703",
    ]


    samples = {}


    for code in sample_codes:

        record = (
            code_lookup.get(
                code
            )
        )

        if record:

            samples[
                code
            ] = {
                "description":
                    record[
                        "description"
                    ],

                "parent":
                    record[
                        "parent"
                    ],

                "is_leaf":
                    record[
                        "is_leaf"
                    ],

                "aggregation_level":
                    record[
                        "aggregation_level"
                    ],

                "standard_unit":
                    record[
                        "standard_unit"
                    ],
            }


    first_five = [
        {
            "code":
                record["code"],

            "description":
                record["description"],

            "parent":
                record["parent"],

            "is_leaf":
                record["is_leaf"],

            "aggregation_level":
                record[
                    "aggregation_level"
                ],
        }
        for record in numeric_records[:5]
    ]


    diagnostic = {

        "ok":
            True,

        "classification":
            CLASSIFICATION,

        "nomenclature":
            NOMENCLATURE,

        "provider":
            SOURCE_PROVIDER,

        "snapshot":
            str(
                snapshot_path
            ),

        "snapshot_sha256":
            snapshot_hash,

        "snapshot_bytes":
            len(content),

        "raw_objects":
            len(records),

        "numeric_hs_records":
            len(
                numeric_records
            ),

        "code_length_counts":
            dict(
                sorted(
                    length_counts.items()
                )
            ),

        "supplied_aggregation_levels":
            dict(
                supplied_level_counts
            ),

        "leaf_values":
            dict(
                leaf_counts
            ),

        "duplicate_code_count":
            len(
                duplicate_codes
            ),

        "duplicate_codes":
            dict(
                list(
                    sorted(
                        duplicate_codes.items()
                    )
                )[:50]
            ),

        "missing_expected_parent_count":
            len(
                missing_parent_examples
            ),

        "missing_parent_examples":
            missing_parent_examples[:50],

        "samples":
            samples,

        "first_five":
            first_five,

    }


    diagnostic_path = (
        snapshot_directory
        / "inspection.json"
    )


    diagnostic_path.write_text(
        json.dumps(
            diagnostic,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


    print()
    print(
        "============================================================"
    )

    print(
        " HS 2022 / H6 DIAGNOSTIC"
    )

    print(
        "============================================================"
    )


    print(
        json.dumps(
            {
                "raw_objects":
                    len(records),

                "numeric_hs_records":
                    len(
                        numeric_records
                    ),

                "code_length_counts":
                    dict(
                        sorted(
                            length_counts.items()
                        )
                    ),

                "aggregation_levels":
                    dict(
                        supplied_level_counts
                    ),

                "duplicate_code_count":
                    len(
                        duplicate_codes
                    ),

                "missing_expected_parent_count":
                    len(
                        missing_parent_examples
                    ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


    print()
    print(
        "KNOWN CODE SAMPLES"
    )

    print(
        json.dumps(
            samples,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


    print()
    print(
        "FIRST FIVE NUMERIC RECORDS"
    )

    print(
        json.dumps(
            first_five,
            indent=2,
            ensure_ascii=False,
        )
    )


    print()
    print(
        f"Full diagnostic: "
        f"{diagnostic_path}"
    )


    print()
    print(
        "PASS: Official HS 2022 "
        "reference inspected successfully."
    )


if __name__ == "__main__":
    main()
