from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import zipfile

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx


ROOT = Path(__file__).resolve().parents[4]

RELEASE = "2025-1"

OFFICIAL_PUBLICATION_URL = (
    "https://opensource.unicc.org/"
    "un/unece/uncefact/vocab-locode/"
    "-/jobs/artifacts/2025-1/download"
    "?job=package-release"
)

OFFICIAL_TAG_ARCHIVE_URL = (
    "https://opensource.unicc.org/"
    "un/unece/uncefact/vocab-locode/"
    "-/archive/2025-1/"
    "vocab-locode-2025-1.zip"
)


def sha256_bytes(value: bytes) -> str:

    return hashlib.sha256(
        value
    ).hexdigest()


def download_zip() -> tuple[
    bytes,
    str,
]:

    candidates = [
        (
            "official_release_artifact",
            OFFICIAL_PUBLICATION_URL,
        ),
        (
            "official_release_tag_archive",
            OFFICIAL_TAG_ARCHIVE_URL,
        ),
    ]

    errors: list[str] = []

    with httpx.Client(
        timeout=180.0,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "OriginHut/0.1 "
                "(UNLOCODE official reference inspection)"
            )
        },
    ) as client:

        for source_type, url in candidates:

            print()
            print(
                f"Attempting source: {source_type}"
            )

            try:

                response = client.get(
                    url
                )

                response.raise_for_status()

                content = response.content

                if not content.startswith(
                    b"PK"
                ):

                    errors.append(
                        f"{source_type}: "
                        "response was not a ZIP archive"
                    )

                    continue

                if len(content) < 100_000:

                    errors.append(
                        f"{source_type}: "
                        "archive unexpectedly small"
                    )

                    continue

                print(
                    f"PASS: Downloaded "
                    f"{len(content):,} bytes."
                )

                return (
                    content,
                    source_type,
                )

            except Exception as error:

                errors.append(
                    f"{source_type}: {error}"
                )

    raise RuntimeError(
        "Unable to download an official "
        "UN/LOCODE release archive.\n"
        + "\n".join(errors)
    )


def recursive_members(
    archive: bytes,
    prefix: str = "",
    depth: int = 0,
) -> Iterable[
    tuple[str, bytes]
]:

    if depth > 3:
        return

    with zipfile.ZipFile(
        io.BytesIO(archive)
    ) as zf:

        for info in zf.infolist():

            if info.is_dir():
                continue

            data = zf.read(
                info.filename
            )

            logical_name = (
                f"{prefix}"
                f"{info.filename}"
            )

            if (
                logical_name
                .lower()
                .endswith(".zip")
                and data.startswith(
                    b"PK"
                )
            ):

                yield from recursive_members(
                    data,
                    prefix=(
                        logical_name
                        + "::"
                    ),
                    depth=depth + 1,
                )

            else:

                yield (
                    logical_name,
                    data,
                )


def decode_csv(
    content: bytes,
) -> tuple[
    str,
    str,
    str,
]:

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ]

    decoded = None
    encoding_used = None

    for encoding in encodings:

        try:

            decoded = content.decode(
                encoding
            )

            encoding_used = encoding

            break

        except UnicodeDecodeError:
            continue

    if decoded is None:

        raise RuntimeError(
            "Unable to decode CSV."
        )

    sample = decoded[:50_000]

    try:

        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=",;\t",
        )

        delimiter = dialect.delimiter

    except csv.Error:

        delimiter = ","

    return (
        decoded,
        delimiter,
        encoding_used,
    )


def parse_location_csv(
    name: str,
    content: bytes,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:

    text, delimiter, encoding_used = decode_csv(
        content
    )

    reader = csv.reader(
        io.StringIO(text),
        delimiter=delimiter,
    )

    records: list[
        dict[str, Any]
    ] = []

    physical_rows = 0
    malformed_rows = 0

    for row_number, row in enumerate(
        reader,
        start=1,
    ):

        physical_rows += 1

        row = [
            value
            .replace("\x00", "")
            .strip()
            for value in row
        ]

        # Published UN/LOCODE files use 12 fields.
        # The repository source files may contain two
        # additional internal decimal-coordinate fields.
        if len(row) < 12:

            malformed_rows += 1
            continue

        change = row[0]

        country = (
            row[1]
            .upper()
        )

        location = (
            row[2]
            .upper()
        )

        name_value = row[3]

        if not re.fullmatch(
            r"[A-Z]{2}",
            country,
        ):
            continue

        if not re.fullmatch(
            r"[A-Z0-9]{3}",
            location,
        ):
            continue

        if not name_value:
            continue

        record = {

            "change":
                change,

            "country":
                country,

            "location":
                location,

            "unlocode":
                country + location,

            "name":
                name_value,

            "name_without_diacritics":
                row[4] or None,

            "subdivision":
                row[5] or None,

            "function":
                row[6] or None,

            "status":
                row[7] or None,

            "date":
                row[8] or None,

            "iata":
                row[9] or None,

            "coordinates":
                row[10] or None,

            "remarks":
                row[11] or None,

            "source_file":
                name,

            "source_row":
                row_number,

        }

        # Repository working files can contain fields
        # 13/14. They are intentionally inspected but
        # NOT treated as authoritative published
        # coordinates.
        if len(row) >= 14:

            record[
                "repository_decimal_latitude"
            ] = (
                row[12] or None
            )

            record[
                "repository_decimal_longitude"
            ] = (
                row[13] or None
            )

        records.append(
            record
        )

    diagnostics = {

        "file":
            name,

        "encoding":
            encoding_used,

        "delimiter":
            repr(delimiter),

        "physical_rows":
            physical_rows,

        "valid_location_rows":
            len(records),

        "short_or_malformed_rows":
            malformed_rows,

    }

    return (
        records,
        diagnostics,
    )


def select_data_files(
    members: list[
        tuple[str, bytes]
    ],
) -> tuple[
    str,
    list[tuple[str, bytes]],
]:

    publication_parts = [
        (
            name,
            content,
        )
        for name, content
        in members
        if (
            name.lower()
            .endswith(".csv")
            and re.search(
                r"unlocode\s+codelistpart\d+\.csv$",
                name,
                flags=re.IGNORECASE,
            )
        )
    ]

    if publication_parts:

        publication_parts.sort(
            key=lambda item:
                item[0]
        )

        return (
            "published_release_csv",
            publication_parts,
        )


    repository_files = [
        (
            name,
            content,
        )
        for name, content
        in members
        if (
            name.lower()
            .endswith(".csv")
            and re.search(
                r"(?:^|/)locodes/"
                r"[A-Z]{2}\.csv$",
                name,
                flags=re.IGNORECASE,
            )
        )
    ]

    if repository_files:

        repository_files.sort(
            key=lambda item:
                item[0]
        )

        return (
            "tagged_repository_source",
            repository_files,
        )


    csv_names = [
        name
        for name, _
        in members
        if name.lower()
        .endswith(".csv")
    ]

    raise RuntimeError(
        "UN/LOCODE location CSV files "
        "were not identified.\n"
        "CSV files seen:\n"
        + "\n".join(
            csv_names[:50]
        )
    )


def main() -> None:

    print(
        "UN/LOCODE official release inspector"
    )

    print(
        f"Release: {RELEASE}"
    )


    archive, downloaded_from = (
        download_zip()
    )


    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )


    snapshot_dir = (
        ROOT
        / "storage"
        / "imports"
        / "unlocode"
        / RELEASE
        / timestamp
    )

    snapshot_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


    archive_path = (
        snapshot_dir
        / (
            f"unlocode-"
            f"{RELEASE}-official.zip"
        )
    )

    archive_path.write_bytes(
        archive
    )


    archive_hash = sha256_bytes(
        archive
    )


    print()
    print(
        f"Raw archive saved: "
        f"{archive_path}"
    )

    print(
        f"Archive SHA-256: "
        f"{archive_hash}"
    )


    members = list(
        recursive_members(
            archive
        )
    )


    print()
    print(
        f"Archive files discovered: "
        f"{len(members):,}"
    )


    source_mode, data_files = (
        select_data_files(
            members
        )
    )


    print(
        f"Data layout: {source_mode}"
    )

    print(
        f"Location CSV files: "
        f"{len(data_files):,}"
    )


    all_records: list[
        dict[str, Any]
    ] = []

    file_diagnostics = []


    for name, content in data_files:

        records, diagnostics = (
            parse_location_csv(
                name,
                content,
            )
        )

        all_records.extend(
            records
        )

        file_diagnostics.append(
            diagnostics
        )


    if len(all_records) < 100_000:

        raise RuntimeError(
            "Only "
            f"{len(all_records):,} "
            "valid UN/LOCODE rows were "
            "parsed. Expected more than "
            "100,000 for the current "
            "production dataset."
        )


    by_code: dict[
        str,
        list[dict[str, Any]]
    ] = defaultdict(list)


    for record in all_records:

        by_code[
            record["unlocode"]
        ].append(record)


    duplicate_groups = {
        code: records
        for code, records
        in by_code.items()
        if len(records) > 1
    }


    country_counts = Counter(
        record["country"]
        for record in all_records
    )


    change_counts = Counter(
        (
            record["change"]
            if record["change"]
            else "(blank)"
        )
        for record in all_records
    )


    status_counts = Counter(
        (
            record["status"]
            if record["status"]
            else "(blank)"
        )
        for record in all_records
    )


    coordinate_count = sum(
        1
        for record in all_records
        if record["coordinates"]
    )


    iata_count = sum(
        1
        for record in all_records
        if record["iata"]
    )


    deletion_count = sum(
        1
        for record in all_records
        if record["change"] == "X"
    )


    india_rows = [
        record
        for record in all_records
        if record["country"]
        == "IN"
    ]


    india_codes = {
        record["unlocode"]
        for record in india_rows
    }


    expected_examples = [
        "INBLR",
        "INBOM",
        "INMAA",
        "INNSA",
    ]


    india_examples = {}

    for code in expected_examples:

        rows = by_code.get(
            code,
            []
        )

        india_examples[
            code
        ] = [
            {
                "change":
                    row["change"],

                "name":
                    row["name"],

                "subdivision":
                    row["subdivision"],

                "function":
                    row["function"],

                "status":
                    row["status"],

                "date":
                    row["date"],

                "iata":
                    row["iata"],

                "coordinates":
                    row["coordinates"],

            }
            for row in rows
        ]


    duplicate_examples = []

    for code in sorted(
        duplicate_groups
    )[:20]:

        rows = duplicate_groups[
            code
        ]

        duplicate_examples.append(
            {
                "unlocode":
                    code,

                "rows": [
                    {
                        "change":
                            row["change"],

                        "name":
                            row["name"],

                        "date":
                            row["date"],

                        "status":
                            row["status"],

                    }
                    for row in rows
                ],
            }
        )


    summary = {

        "ok":
            True,

        "release":
            RELEASE,

        "downloaded_from":
            downloaded_from,

        "data_layout":
            source_mode,

        "archive_path":
            str(archive_path),

        "archive_sha256":
            archive_hash,

        "archive_members":
            len(members),

        "location_csv_files":
            len(data_files),

        "location_rows":
            len(all_records),

        "unique_unlocodes":
            len(by_code),

        "duplicate_unlocode_groups":
            len(duplicate_groups),

        "surplus_duplicate_rows":
            (
                len(all_records)
                - len(by_code)
            ),

        "country_codes":
            len(country_counts),

        "rows_with_coordinates":
            coordinate_count,

        "rows_with_iata":
            iata_count,

        "rows_marked_for_deletion":
            deletion_count,

        "change_indicators":
            dict(
                change_counts
            ),

        "top_status_codes":
            dict(
                status_counts
                .most_common(20)
            ),

        "india": {

            "rows":
                len(india_rows),

            "unique_codes":
                len(india_codes),

            "examples":
                india_examples,

        },

        "duplicate_examples":
            duplicate_examples,

        "files":
            file_diagnostics,

    }


    diagnostic_path = (
        snapshot_dir
        / "inspection.json"
    )

    diagnostic_path.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    metadata_path = (
        snapshot_dir
        / "source-metadata.json"
    )

    metadata_path.write_text(
        json.dumps(
            {
                "release":
                    RELEASE,

                "official_publication_url":
                    OFFICIAL_PUBLICATION_URL,

                "official_tag_archive_url":
                    OFFICIAL_TAG_ARCHIVE_URL,

                "selected_download":
                    downloaded_from,

                "archive_sha256":
                    archive_hash,

                "downloaded_at_utc":
                    timestamp,

            },
            indent=2,
        ),
        encoding="utf-8",
    )


    print()
    print(
        "============================================================"
    )

    print(
        " UN/LOCODE RELEASE DIAGNOSTIC"
    )

    print(
        "============================================================"
    )

    print(
        json.dumps(
            {
                "release":
                    RELEASE,

                "source":
                    downloaded_from,

                "layout":
                    source_mode,

                "location_rows":
                    len(all_records),

                "unique_unlocodes":
                    len(by_code),

                "duplicate_groups":
                    len(
                        duplicate_groups
                    ),

                "surplus_duplicate_rows":
                    (
                        len(all_records)
                        - len(by_code)
                    ),

                "country_codes":
                    len(country_counts),

                "coordinates":
                    coordinate_count,

                "iata_codes":
                    iata_count,

                "marked_for_deletion":
                    deletion_count,

                "india_rows":
                    len(india_rows),

                "india_unique_codes":
                    len(india_codes),

            },
            indent=2,
        )
    )


    print()
    print(
        "CHANGE INDICATORS"
    )

    print(
        json.dumps(
            dict(change_counts),
            indent=2,
            ensure_ascii=False,
        )
    )


    print()
    print(
        "INDIA EXAMPLES"
    )

    print(
        json.dumps(
            india_examples,
            indent=2,
            ensure_ascii=False,
        )
    )


    print()
    print(
        "FIRST DUPLICATE GROUPS"
    )

    print(
        json.dumps(
            duplicate_examples,
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
        "PASS: Official UN/LOCODE "
        "release inspected successfully."
    )


if __name__ == "__main__":
    main()

