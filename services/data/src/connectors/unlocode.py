from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import zipfile

from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg

from dotenv import load_dotenv
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[4]

load_dotenv(ROOT / ".env")


RELEASE = "2025-1"

EXPECTED_RAW_ROWS = 116_232

EXPECTED_UNIQUE_CODES = 116_086


SOURCE_CODE = "unece_unlocode"

SOURCE_NAME = (
    "United Nations Code for "
    "Trade and Transport Locations"
)

SOURCE_PROVIDER = (
    "United Nations Economic "
    "Commission for Europe"
)

PUBLICATION_URL = (
    "https://unlocode.unece.org/"
    "publications/"
)


FUNCTION_LABELS = {

    "1":
        "maritime_transport",

    "2":
        "rail_transport",

    "3":
        "road_transport",

    "4":
        "air_transport",

    "5":
        "international_mail_processing_centre",

    "6":
        "multimodal_transport_facility",

    "7":
        "fixed_transport_installation",

    "8":
        "inland_water_transport",

    "0":
        "not_officially_functional",

    "A":
        "special_economic_zone",

    "B":
        "cross_border",

}


def sha256_bytes(
    value: bytes,
) -> str:

    return hashlib.sha256(
        value
    ).hexdigest()


def sha256_payload(
    value: dict[str, Any],
) -> str:

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def find_latest_archive() -> Path:

    root = (
        ROOT
        / "storage"
        / "imports"
        / "unlocode"
        / RELEASE
    )

    archives = sorted(
        root.glob(
            "*/unlocode-2025-1-official.zip"
        ),
        key=lambda path:
            path.stat().st_mtime,
        reverse=True,
    )

    if not archives:

        raise RuntimeError(
            "No inspected official "
            "UN/LOCODE archive exists."
        )

    return archives[0]


def recursive_members(
    archive: bytes,
    prefix: str = "",
    depth: int = 0,
):

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
                prefix
                + info.filename
            )

            if (
                logical_name
                .lower()
                .endswith(".zip")
                and data.startswith(b"PK")
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
]:

    for encoding in (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ):

        try:

            text = content.decode(
                encoding
            )

            break

        except UnicodeDecodeError:

            continue

    else:

        raise RuntimeError(
            "Unable to decode "
            "UN/LOCODE CSV."
        )


    try:

        dialect = csv.Sniffer().sniff(
            text[:50_000],
            delimiters=",;\t",
        )

        delimiter = (
            dialect.delimiter
        )

    except csv.Error:

        delimiter = ","


    return (
        text,
        delimiter,
    )


def select_location_files(
    members,
):

    files = [
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

    files.sort(
        key=lambda item:
            item[0]
    )

    if len(files) != 3:

        raise RuntimeError(
            "Expected exactly three "
            "published UN/LOCODE CSV parts; "
            f"found {len(files)}."
        )

    return files


def normalize_change(
    value: str | None,
) -> str:

    value = (
        value or ""
    ).strip()

    # Published CSV commonly renders the
    # vertical-bar change indicator as ¦.
    if value == "¦":
        return "|"

    return value


def parse_csv(
    name: str,
    content: bytes,
):

    text, delimiter = (
        decode_csv(content)
    )

    reader = csv.reader(
        io.StringIO(text),
        delimiter=delimiter,
    )


    records = []


    for row_number, row in enumerate(
        reader,
        start=1,
    ):

        row = [
            value
            .replace("\x00", "")
            .strip()
            for value in row
        ]


        if len(row) < 12:
            continue


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


        records.append(
            {

                "change":
                    row[0] or None,

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
        )


    return records


def publication_content(
    record: dict[str, Any],
) -> dict[str, Any]:

    # Physical filename and row number are
    # provenance, but are not part of the
    # semantic identity of a published row.

    return {

        "change":
            record["change"],

        "country":
            record["country"],

        "location":
            record["location"],

        "unlocode":
            record["unlocode"],

        "name":
            record["name"],

        "name_without_diacritics":
            record[
                "name_without_diacritics"
            ],

        "subdivision":
            record["subdivision"],

        "function":
            record["function"],

        "status":
            record["status"],

        "date":
            record["date"],

        "iata":
            record["iata"],

        "coordinates":
            record["coordinates"],

        "remarks":
            record["remarks"],

    }


def parse_coordinates(
    value: str | None,
) -> tuple[
    float | None,
    float | None,
]:

    if not value:
        return (
            None,
            None,
        )


    compact = re.sub(
        r"\s+",
        "",
        value.upper(),
    )


    match = re.fullmatch(
        r"(\d{2})(\d{2})([NS])"
        r"(\d{3})(\d{2})([EW])",
        compact,
    )


    if not match:

        return (
            None,
            None,
        )


    lat_deg = int(
        match.group(1)
    )

    lat_min = int(
        match.group(2)
    )

    lat_hemi = (
        match.group(3)
    )

    lon_deg = int(
        match.group(4)
    )

    lon_min = int(
        match.group(5)
    )

    lon_hemi = (
        match.group(6)
    )


    if (
        lat_min >= 60
        or lon_min >= 60
        or lat_deg > 90
        or lon_deg > 180
    ):

        return (
            None,
            None,
        )


    latitude = (
        lat_deg
        + lat_min / 60.0
    )

    longitude = (
        lon_deg
        + lon_min / 60.0
    )


    if lat_hemi == "S":
        latitude *= -1


    if lon_hemi == "W":
        longitude *= -1


    return (
        round(latitude, 6),
        round(longitude, 6),
    )


def date_score(
    value: str | None,
) -> int:

    if (
        not value
        or not re.fullmatch(
            r"\d{4}",
            value,
        )
    ):

        return 0


    yy = int(
        value[:2]
    )

    month = int(
        value[2:]
    )


    if not 1 <= month <= 12:
        month = 0


    # Release is 2025-1.
    # YY values 00-25 are treated as 2000-2025;
    # older values as 19YY for deterministic
    # duplicate resolution.

    if yy <= 25:
        year = 2000 + yy
    else:
        year = 1900 + yy


    return (
        year * 100
        + month
    )


def change_priority(
    value: str | None,
) -> int:

    normalized = (
        normalize_change(value)
    )

    return {

        "#": 60,
        "|": 50,
        "+": 40,
        "=": 30,
        "!": 20,
        "": 10,
        "X": 0,

    }.get(
        normalized,
        5,
    )


def marked_for_deletion(
    record: dict[str, Any],
) -> bool:

    return (
        normalize_change(
            record["change"]
        )
        == "X"
        or (
            record["status"]
            or ""
        ).upper()
        == "XX"
    )


def canonical_score(
    record: dict[str, Any],
):

    return (

        0
        if marked_for_deletion(
            record
        )
        else 1,

        change_priority(
            record["change"]
        ),

        date_score(
            record["date"]
        ),

        1
        if record["coordinates"]
        else 0,

        1
        if record["function"]
        else 0,

        -int(
            record["source_row"]
        ),

    )


def function_labels(
    value: str | None,
):

    if not value:
        return []


    labels = []


    for character in value:

        if character == "-":
            continue

        label = (
            FUNCTION_LABELS.get(
                character
            )
        )

        if (
            label
            and label not in labels
        ):
            labels.append(
                label
            )


    return labels


def register_source(
    connection,
    archive_path: Path,
    archive_hash: str,
):

    result = connection.execute(
        """
        INSERT INTO data_sources (
            code,
            name,
            provider,
            category,
            access_method,
            base_url,
            attribution,
            refresh_frequency,
            is_official,
            is_active,
            metadata
        )
        VALUES (
            %s,
            %s,
            %s,
            'reference',
            'official_release_archive',
            %s,
            %s,
            'biannual',
            TRUE,
            TRUE,
            %s
        )
        ON CONFLICT (code)
        DO UPDATE SET
            name =
                EXCLUDED.name,
            provider =
                EXCLUDED.provider,
            category =
                EXCLUDED.category,
            access_method =
                EXCLUDED.access_method,
            base_url =
                EXCLUDED.base_url,
            attribution =
                EXCLUDED.attribution,
            refresh_frequency =
                EXCLUDED.refresh_frequency,
            is_official =
                TRUE,
            is_active =
                TRUE,
            metadata =
                EXCLUDED.metadata,
            updated_at =
                NOW()
        RETURNING id
        """,
        (
            SOURCE_CODE,
            SOURCE_NAME,
            SOURCE_PROVIDER,
            PUBLICATION_URL,
            (
                "UNECE / UN/CEFACT "
                "UN/LOCODE"
            ),
            Jsonb(
                {
                    "release":
                        RELEASE,
                    "archive_path":
                        str(
                            archive_path
                        ),
                    "archive_sha256":
                        archive_hash,
                    "publication_type":
                        "official_production",
                }
            ),
        ),
    ).fetchone()


    if result is None:

        raise RuntimeError(
            "Unable to register "
            "UN/LOCODE source."
        )


    return str(
        result[0]
    )


def start_run(
    connection,
    source_id: str,
    archive_path: Path,
    archive_hash: str,
):

    result = connection.execute(
        """
        INSERT INTO ingestion_runs (
            data_source_id,
            status,
            metadata
        )
        VALUES (
            %s,
            'running',
            %s
        )
        RETURNING id
        """,
        (
            source_id,
            Jsonb(
                {
                    "release":
                        RELEASE,
                    "archive_path":
                        str(
                            archive_path
                        ),
                    "archive_sha256":
                        archive_hash,
                }
            ),
        ),
    ).fetchone()


    if result is None:

        raise RuntimeError(
            "Unable to create "
            "UN/LOCODE ingestion run."
        )


    return str(
        result[0]
    )


def main():

    database_url = os.environ.get(
        "DATABASE_URL"
    )


    if not database_url:

        raise RuntimeError(
            "DATABASE_URL missing."
        )


    archive_path = (
        find_latest_archive()
    )


    archive = (
        archive_path.read_bytes()
    )


    archive_hash = (
        sha256_bytes(
            archive
        )
    )


    print(
        f"Release: {RELEASE}"
    )

    print(
        f"Archive: {archive_path}"
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


    files = (
        select_location_files(
            members
        )
    )


    records = []


    for name, content in files:

        parsed = parse_csv(
            name,
            content,
        )

        print(
            f"{name}: "
            f"{len(parsed):,} rows"
        )

        records.extend(
            parsed
        )


    print(
        f"Total published rows: "
        f"{len(records):,}"
    )


    if (
        len(records)
        != EXPECTED_RAW_ROWS
    ):

        raise RuntimeError(
            "Parsed raw-row count does "
            "not match inspected release. "
            f"Expected "
            f"{EXPECTED_RAW_ROWS:,}, "
            f"got {len(records):,}."
        )


    grouped = defaultdict(
        list
    )


    for record in records:

        grouped[
            record["unlocode"]
        ].append(
            record
        )


    print(
        f"Unique UN/LOCODEs: "
        f"{len(grouped):,}"
    )


    if (
        len(grouped)
        != EXPECTED_UNIQUE_CODES
    ):

        raise RuntimeError(
            "Unique-code count does not "
            "match inspected release."
        )


    canonical = {

        code:
            max(
                rows,
                key=canonical_score,
            )

        for code, rows
        in grouped.items()

    }


    hashed_records = [

        (
            record,
            sha256_payload(
                publication_content(
                    record
                )
            ),
        )

        for record in records

    ]


    with psycopg.connect(
        database_url
    ) as connection:


        with connection.transaction():

            source_id = (
                register_source(
                    connection,
                    archive_path,
                    archive_hash,
                )
            )

            run_id = (
                start_run(
                    connection,
                    source_id,
                    archive_path,
                    archive_hash,
                )
            )


        try:

            with connection.transaction():


                # ------------------------------------------------
                # COUNTRY REFERENCE MAP
                # ------------------------------------------------

                country_rows = (
                    connection.execute(
                        """
                        SELECT
                            iso2,
                            id
                        FROM countries
                        """
                    ).fetchall()
                )


                country_ids = {

                    row[0]:
                        str(row[1])

                    for row
                    in country_rows

                }


                unlocode_country_codes = {
                    record["country"]
                    for record in records
                }


                unmatched_countries = sorted(
                    unlocode_country_codes
                    - set(
                        country_ids.keys()
                    )
                )


                print()
                print(
                    "UN/LOCODE country codes "
                    "not present in UN M49:"
                )

                print(
                    unmatched_countries
                )


                if (
                    len(
                        unmatched_countries
                    )
                    > 5
                ):

                    raise RuntimeError(
                        "Unexpected number of "
                        "UN/LOCODE country codes "
                        "without M49 mapping."
                    )


                # ------------------------------------------------
                # RAW SOURCE RECORDS
                # ------------------------------------------------

                before_raw = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM source_records
                        WHERE
                            data_source_id =
                                %s
                            AND record_type =
                                'unlocode_entry'
                        """,
                        (source_id,),
                    ).fetchone()[0]
                )


                print()
                print(
                    "Preserving raw "
                    "UN/LOCODE rows..."
                )


                with connection.cursor() as cursor:

                    cursor.executemany(
                        """
                        INSERT INTO source_records (
                            data_source_id,
                            ingestion_run_id,
                            external_id,
                            record_type,
                            content_hash,
                            payload,
                            metadata
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            'unlocode_entry',
                            %s,
                            %s,
                            %s
                        )
                        ON CONFLICT (
                            data_source_id,
                            record_type,
                            external_id,
                            content_hash
                        )
                        WHERE
                            external_id
                                IS NOT NULL
                            AND content_hash
                                IS NOT NULL
                        DO NOTHING
                        """,
                        (
                            (
                                source_id,
                                run_id,
                                record[
                                    "unlocode"
                                ],
                                content_hash,
                                Jsonb(
                                    publication_content(
                                        record
                                    )
                                ),
                                Jsonb(
                                    {
                                        "release":
                                            RELEASE,
                                        "source_file":
                                            record[
                                                "source_file"
                                            ],
                                        "source_row":
                                            record[
                                                "source_row"
                                            ],
                                    }
                                ),
                            )

                            for record,
                                content_hash
                            in hashed_records
                        ),
                    )


                after_raw = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM source_records
                        WHERE
                            data_source_id =
                                %s
                            AND record_type =
                                'unlocode_entry'
                        """,
                        (source_id,),
                    ).fetchone()[0]
                )


                raw_new = (
                    after_raw
                    - before_raw
                )


                raw_reused = (
                    len(records)
                    - raw_new
                )


                print(
                    f"New raw records: "
                    f"{raw_new:,}"
                )

                print(
                    f"Reused raw records: "
                    f"{raw_reused:,}"
                )


                # ------------------------------------------------
                # LOAD SOURCE RECORD IDS
                # ------------------------------------------------

                source_rows = (
                    connection.execute(
                        """
                        SELECT
                            external_id,
                            content_hash,
                            id
                        FROM source_records
                        WHERE
                            data_source_id =
                                %s
                            AND record_type =
                                'unlocode_entry'
                        """,
                        (source_id,),
                    ).fetchall()
                )


                source_record_ids = {

                    (
                        row[0],
                        row[1],
                    ):
                        str(row[2])

                    for row
                    in source_rows

                }


                # ------------------------------------------------
                # RECORD THIS RUN -> SOURCE RECORD RELATION
                # ------------------------------------------------

                print(
                    "Recording ingestion-run "
                    "membership..."
                )


                with connection.cursor() as cursor:

                    cursor.executemany(
                        """
                        INSERT INTO
                            ingestion_run_records (
                                ingestion_run_id,
                                source_record_id
                            )
                        VALUES (
                            %s,
                            %s
                        )
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            (
                                run_id,
                                source_record_ids[
                                    (
                                        record[
                                            "unlocode"
                                        ],
                                        content_hash,
                                    )
                                ],
                            )

                            for record,
                                content_hash
                            in hashed_records
                        ),
                    )


                # ------------------------------------------------
                # CANONICAL TRADE LOCATIONS
                # ------------------------------------------------

                print(
                    "Normalizing "
                    f"{len(canonical):,} "
                    "trade locations..."
                )


                canonical_params = []


                for (
                    code,
                    record
                ) in canonical.items():


                    content_hash = (
                        sha256_payload(
                            publication_content(
                                record
                            )
                        )
                    )


                    source_record_id = (
                        source_record_ids[
                            (
                                code,
                                content_hash,
                            )
                        ]
                    )


                    latitude, longitude = (
                        parse_coordinates(
                            record[
                                "coordinates"
                            ]
                        )
                    )


                    deletion = (
                        marked_for_deletion(
                            record
                        )
                    )


                    canonical_params.append(
                        (

                            code,

                            country_ids.get(
                                record[
                                    "country"
                                ]
                            ),

                            record[
                                "country"
                            ],

                            record[
                                "location"
                            ],

                            record[
                                "name"
                            ],

                            record[
                                "name_without_diacritics"
                            ],

                            record[
                                "subdivision"
                            ],

                            "trade_transport_location",

                            record[
                                "function"
                            ],

                            record[
                                "status"
                            ],

                            latitude,

                            longitude,

                            normalize_change(
                                record[
                                    "change"
                                ]
                            )
                            or None,

                            record[
                                "iata"
                            ],

                            record[
                                "date"
                            ],

                            record[
                                "remarks"
                            ],

                            RELEASE,

                            deletion,

                            not deletion,

                            source_record_id,

                            Jsonb(
                                {
                                    "source":
                                        SOURCE_CODE,
                                    "release":
                                        RELEASE,
                                    "raw_change_indicator":
                                        record[
                                            "change"
                                        ],
                                    "raw_coordinates":
                                        record[
                                            "coordinates"
                                        ],
                                    "function_labels":
                                        function_labels(
                                            record[
                                                "function"
                                            ]
                                        ),
                                    "published_variants":
                                        len(
                                            grouped[
                                                code
                                            ]
                                        ),
                                }
                            ),

                        )
                    )


                with connection.cursor() as cursor:

                    cursor.executemany(
                        """
                        INSERT INTO trade_locations (
                            unlocode,
                            country_id,
                            country_code,
                            location_code,
                            name,
                            name_without_diacritics,
                            subdivision_code,
                            location_type,
                            function_codes,
                            status,
                            latitude,
                            longitude,
                            change_indicator,
                            iata_code,
                            release_date_code,
                            remarks,
                            source_release,
                            marked_for_deletion,
                            is_active,
                            canonical_source_record_id,
                            metadata
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s
                        )
                        ON CONFLICT (unlocode)
                        DO UPDATE SET
                            country_id =
                                EXCLUDED.country_id,
                            country_code =
                                EXCLUDED.country_code,
                            location_code =
                                EXCLUDED.location_code,
                            name =
                                EXCLUDED.name,
                            name_without_diacritics =
                                EXCLUDED.name_without_diacritics,
                            subdivision_code =
                                EXCLUDED.subdivision_code,
                            location_type =
                                EXCLUDED.location_type,
                            function_codes =
                                EXCLUDED.function_codes,
                            status =
                                EXCLUDED.status,
                            latitude =
                                EXCLUDED.latitude,
                            longitude =
                                EXCLUDED.longitude,
                            change_indicator =
                                EXCLUDED.change_indicator,
                            iata_code =
                                EXCLUDED.iata_code,
                            release_date_code =
                                EXCLUDED.release_date_code,
                            remarks =
                                EXCLUDED.remarks,
                            source_release =
                                EXCLUDED.source_release,
                            marked_for_deletion =
                                EXCLUDED.marked_for_deletion,
                            is_active =
                                EXCLUDED.is_active,
                            canonical_source_record_id =
                                EXCLUDED.canonical_source_record_id,
                            metadata =
                                EXCLUDED.metadata,
                            updated_at =
                                NOW()
                        """,
                        canonical_params,
                    )


                # ------------------------------------------------
                # POSTGIS GEOGRAPHY
                # ------------------------------------------------

                print(
                    "Creating PostGIS "
                    "geography points..."
                )


                connection.execute(
                    """
                    UPDATE trade_locations
                    SET geography =
                        CASE
                            WHEN
                                latitude
                                    IS NOT NULL
                                AND longitude
                                    IS NOT NULL
                            THEN
                                ST_SetSRID(
                                    ST_MakePoint(
                                        longitude,
                                        latitude
                                    ),
                                    4326
                                )::geography
                            ELSE NULL
                        END
                    WHERE source_release = %s
                    """,
                    (RELEASE,),
                )


                # ------------------------------------------------
                # LOAD NORMALIZED LOCATION IDS
                # ------------------------------------------------

                location_rows = (
                    connection.execute(
                        """
                        SELECT
                            unlocode,
                            id
                        FROM trade_locations
                        WHERE source_release = %s
                        """,
                        (RELEASE,),
                    ).fetchall()
                )


                location_ids = {

                    row[0]:
                        str(row[1])

                    for row
                    in location_rows

                }


                if (
                    len(location_ids)
                    != EXPECTED_UNIQUE_CODES
                ):

                    raise RuntimeError(
                        "Normalized location count "
                        "does not match release."
                    )


                # ------------------------------------------------
                # ENTITY PROVENANCE LINKS
                # ------------------------------------------------

                print(
                    "Linking every source row "
                    "to its trade-location entity..."
                )


                with connection.cursor() as cursor:

                    cursor.executemany(
                        """
                        INSERT INTO entity_source_links (
                            source_record_id,
                            entity_type,
                            entity_id,
                            relationship_type,
                            confidence,
                            metadata
                        )
                        VALUES (
                            %s,
                            'trade_location',
                            %s,
                            'official_reference',
                            1.0000,
                            %s
                        )
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            (
                                source_record_ids[
                                    (
                                        record[
                                            "unlocode"
                                        ],
                                        content_hash,
                                    )
                                ],

                                location_ids[
                                    record[
                                        "unlocode"
                                    ]
                                ],

                                Jsonb(
                                    {
                                        "source":
                                            SOURCE_CODE,
                                        "release":
                                            RELEASE,
                                    }
                                ),

                            )

                            for record,
                                content_hash
                            in hashed_records
                        ),
                    )


                # ------------------------------------------------
                # PUBLISHED NAME ALIASES
                # ------------------------------------------------

                print(
                    "Preserving alternate "
                    "published names..."
                )


                alias_params = []


                for (
                    record,
                    content_hash
                ) in hashed_records:


                    code = (
                        record[
                            "unlocode"
                        ]
                    )


                    preferred = (
                        record
                        is canonical[
                            code
                        ]
                    )


                    alias_params.append(
                        (

                            location_ids[
                                code
                            ],

                            record[
                                "name"
                            ],

                            record[
                                "name_without_diacritics"
                            ],

                            preferred,

                            source_record_ids[
                                (
                                    code,
                                    content_hash,
                                )
                            ],

                            Jsonb(
                                {
                                    "release":
                                        RELEASE,
                                    "change":
                                        record[
                                            "change"
                                        ],
                                    "date":
                                        record[
                                            "date"
                                        ],
                                }
                            ),

                        )
                    )


                with connection.cursor() as cursor:

                    cursor.executemany(
                        """
                        INSERT INTO trade_location_aliases (
                            trade_location_id,
                            name,
                            name_without_diacritics,
                            alias_type,
                            is_preferred,
                            source_record_id,
                            metadata
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            'published_name',
                            %s,
                            %s,
                            %s
                        )
                        ON CONFLICT (
                            trade_location_id,
                            name,
                            alias_type
                        )
                        DO UPDATE SET
                            name_without_diacritics =
                                EXCLUDED.name_without_diacritics,
                            is_preferred =
                                trade_location_aliases.is_preferred
                                OR EXCLUDED.is_preferred,
                            source_record_id =
                                CASE
                                    WHEN EXCLUDED.is_preferred
                                    THEN EXCLUDED.source_record_id
                                    ELSE
                                        trade_location_aliases.source_record_id
                                END,
                            metadata =
                                trade_location_aliases.metadata
                                || EXCLUDED.metadata
                        """,
                        alias_params,
                    )


                # ------------------------------------------------
                # RUN STATISTICS
                # ------------------------------------------------

                coordinate_entities = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM trade_locations
                        WHERE
                            source_release = %s
                            AND geography
                                IS NOT NULL
                        """,
                        (RELEASE,),
                    ).fetchone()[0]
                )


                aliases = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM trade_location_aliases
                        """
                    ).fetchone()[0]
                )


                canonical_deletions = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM trade_locations
                        WHERE
                            source_release = %s
                            AND marked_for_deletion
                        """,
                        (RELEASE,),
                    ).fetchone()[0]
                )


                raw_deletions = sum(
                    1
                    for record in records
                    if normalize_change(
                        record[
                            "change"
                        ]
                    ) == "X"
                )


                connection.execute(
                    """
                    UPDATE ingestion_runs
                    SET
                        status =
                            'completed',
                        finished_at =
                            NOW(),
                        records_seen =
                            %s,
                        records_inserted =
                            %s,
                        records_updated =
                            %s,
                        records_rejected =
                            0,
                        metadata =
                            metadata || %s
                    WHERE id = %s
                    """,
                    (
                        len(records),
                        raw_new,
                        raw_reused,
                        Jsonb(
                            {
                                "release":
                                    RELEASE,
                                "unique_unlocodes":
                                    len(
                                        canonical
                                    ),
                                "duplicate_groups":
                                    sum(
                                        1
                                        for rows
                                        in grouped.values()
                                        if len(rows) > 1
                                    ),
                                "canonical_coordinates":
                                    coordinate_entities,
                                "aliases":
                                    aliases,
                                "raw_deletion_rows":
                                    raw_deletions,
                                "canonical_marked_for_deletion":
                                    canonical_deletions,
                                "unmatched_country_codes":
                                    unmatched_countries,
                            }
                        ),
                        run_id,
                    ),
                )


            print()
            print(
                json.dumps(
                    {
                        "ok":
                            True,

                        "release":
                            RELEASE,

                        "raw_rows":
                            len(records),

                        "unique_unlocodes":
                            len(canonical),

                        "raw_records_new":
                            raw_new,

                        "raw_records_reused":
                            raw_reused,

                        "trade_locations":
                            len(
                                location_ids
                            ),

                        "aliases":
                            aliases,

                        "canonical_coordinates":
                            coordinate_entities,

                        "raw_deletion_rows":
                            raw_deletions,

                        "canonical_marked_for_deletion":
                            canonical_deletions,

                        "unmatched_country_codes":
                            unmatched_countries,

                        "ingestion_run_id":
                            run_id,

                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )


        except Exception as error:


            with connection.transaction():

                connection.execute(
                    """
                    UPDATE ingestion_runs
                    SET
                        status =
                            'failed',
                        finished_at =
                            NOW(),
                        error_message =
                            %s
                    WHERE id = %s
                    """,
                    (
                        str(error),
                        run_id,
                    ),
                )


            raise


if __name__ == "__main__":
    main()
