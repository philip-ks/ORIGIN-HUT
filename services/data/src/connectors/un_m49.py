from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[4]

load_dotenv(ROOT / ".env")


SOURCE_CODE = "un_m49"

SOURCE_NAME = (
    "UN M49 Standard Country or Area Codes "
    "for Statistical Use"
)

SOURCE_PROVIDER = (
    "United Nations Statistics Division"
)

SOURCE_URL = (
    "https://unstats.un.org/"
    "unsd/methodology/m49/overview"
)


REQUIRED_HEADERS = {
    "country or area",
    "m49 code",
    "iso-alpha2 code",
    "iso-alpha3 code",
}


def clean(value: str) -> str:

    return " ".join(
        value
        .replace("\xa0", " ")
        .split()
    ).strip()


def canonical(value: str) -> str:

    return clean(value).casefold()


def sha256_bytes(
    value: bytes,
) -> str:

    return hashlib.sha256(
        value
    ).hexdigest()


def sha256_payload(
    payload: dict[str, Any],
) -> str:

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def find_latest_snapshot() -> Path:

    root = (
        ROOT
        / "storage"
        / "imports"
        / "un_m49"
    )

    snapshots = sorted(
        root.glob(
            "*/m49-overview.html"
        ),
        key=lambda path: (
            path.stat().st_mtime
        ),
        reverse=True,
    )

    if not snapshots:

        raise RuntimeError(
            "No UN M49 source snapshot exists."
        )

    return snapshots[0]


def parse_table(
    table,
) -> tuple[
    list[str],
    list[dict[str, str]],
]:

    rows = table.find_all("tr")

    for header_index, row in enumerate(
        rows
    ):

        cells = row.find_all(
            ["th", "td"]
        )

        headers = [
            clean(
                cell.get_text(
                    " ",
                    strip=True,
                )
            )
            for cell in cells
        ]

        normalized_headers = {
            canonical(header)
            for header in headers
        }

        if not REQUIRED_HEADERS.issubset(
            normalized_headers
        ):
            continue

        records: list[
            dict[str, str]
        ] = []

        for data_row in rows[
            header_index + 1:
        ]:

            data_cells = (
                data_row.find_all(
                    ["th", "td"]
                )
            )

            values = [
                clean(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in data_cells
            ]

            if len(values) != len(
                headers
            ):
                continue

            raw_record = dict(
                zip(
                    headers,
                    values,
                )
            )

            normalized = {
                canonical(key): value
                for key, value
                in raw_record.items()
            }

            country = normalized.get(
                "country or area",
                "",
            )

            m49 = normalized.get(
                "m49 code",
                "",
            )

            iso2 = normalized.get(
                "iso-alpha2 code",
                "",
            ).upper()

            iso3 = normalized.get(
                "iso-alpha3 code",
                "",
            ).upper()

            if (
                country
                and len(m49) == 3
                and m49.isdigit()
                and len(iso2) == 2
                and len(iso3) == 3
            ):
                records.append(
                    raw_record
                )

        return headers, records

    return [], []


def find_english_records(
    html: str,
) -> list[dict[str, str]]:

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = []

    for table in soup.find_all(
        "table"
    ):

        _, records = parse_table(
            table
        )

        if not records:
            continue

        india = None

        for record in records:

            normalized = {
                canonical(key): value
                for key, value
                in record.items()
            }

            if (
                normalized.get(
                    "iso-alpha2 code"
                ) == "IN"
                and normalized.get(
                    "iso-alpha3 code"
                ) == "IND"
            ):
                india = normalized
                break

        if india:

            candidates.append(
                (
                    records,
                    india,
                )
            )

    english = next(
        (
            records
            for records, india
            in candidates
            if india.get(
                "country or area"
            )
            == "India"
            and india.get(
                "region name"
            )
            == "Asia"
        ),
        None,
    )

    if english is None:

        raise RuntimeError(
            "Unable to identify the "
            "English UN M49 table."
        )

    if len(english) < 200:

        raise RuntimeError(
            "UN M49 English table "
            "contains too few records."
        )

    return english


def register_source(
    connection: psycopg.Connection,
    snapshot: Path,
    snapshot_hash: str,
) -> str:

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
            'official_html_snapshot',
            %s,
            %s,
            'periodic',
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
            is_official = TRUE,
            is_active = TRUE,
            metadata =
                EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id
        """,
        (
            SOURCE_CODE,
            SOURCE_NAME,
            SOURCE_PROVIDER,
            SOURCE_URL,
            (
                "United Nations "
                "Statistics Division"
            ),
            Jsonb(
                {
                    "standard": "M49",
                    "snapshot": str(
                        snapshot
                    ),
                    "snapshot_sha256":
                        snapshot_hash,
                    "language": "English",
                }
            ),
        ),
    ).fetchone()

    if result is None:

        raise RuntimeError(
            "Unable to register "
            "UN M49 source."
        )

    return str(
        result[0]
    )


def start_ingestion(
    connection: psycopg.Connection,
    source_id: str,
    snapshot: Path,
    snapshot_hash: str,
) -> str:

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
                    "source_url":
                        SOURCE_URL,
                    "snapshot":
                        str(snapshot),
                    "snapshot_sha256":
                        snapshot_hash,
                    "language":
                        "English",
                }
            ),
        ),
    ).fetchone()

    if result is None:

        raise RuntimeError(
            "Unable to create "
            "ingestion run."
        )

    return str(
        result[0]
    )


def normalized_record(
    raw: dict[str, str],
) -> dict[str, str]:

    return {
        canonical(key): value
        for key, value in raw.items()
    }


def ingest_record(
    connection: psycopg.Connection,
    source_id: str,
    run_id: str,
    raw: dict[str, str],
) -> bool:

    record = normalized_record(
        raw
    )

    name = record[
        "country or area"
    ]

    iso2 = record[
        "iso-alpha2 code"
    ].upper()

    iso3 = record[
        "iso-alpha3 code"
    ].upper()

    numeric_code = record[
        "m49 code"
    ].zfill(3)

    region = (
        record.get(
            "region name"
        )
        or None
    )

    subregion = (
        record.get(
            "sub-region name"
        )
        or None
    )

    record_hash = sha256_payload(
        raw
    )


    source_result = (
        connection.execute(
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
                'country_or_area',
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
            RETURNING id
            """,
            (
                source_id,
                run_id,
                iso3,
                record_hash,
                Jsonb(raw),
                Jsonb(
                    {
                        "iso2": iso2,
                        "iso3": iso3,
                        "m49":
                            numeric_code,
                    }
                ),
            ),
        ).fetchone()
    )


    source_was_new = (
        source_result is not None
    )


    if source_result is None:

        source_result = (
            connection.execute(
                """
                SELECT id
                FROM source_records
                WHERE
                    data_source_id = %s
                    AND record_type =
                        'country_or_area'
                    AND external_id = %s
                    AND content_hash = %s
                """,
                (
                    source_id,
                    iso3,
                    record_hash,
                ),
            ).fetchone()
        )


    if source_result is None:

        raise RuntimeError(
            f"Unable to obtain source "
            f"record for {iso3}."
        )


    source_record_id = str(
        source_result[0]
    )


    country_result = (
        connection.execute(
            """
            INSERT INTO countries (
                iso2,
                iso3,
                numeric_code,
                name,
                region,
                subregion,
                is_active
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                TRUE
            )
            ON CONFLICT (iso2)
            DO UPDATE SET
                iso3 =
                    EXCLUDED.iso3,
                numeric_code =
                    EXCLUDED.numeric_code,
                name =
                    EXCLUDED.name,
                region =
                    EXCLUDED.region,
                subregion =
                    EXCLUDED.subregion,
                is_active = TRUE,
                updated_at = NOW()
            RETURNING id
            """,
            (
                iso2,
                iso3,
                numeric_code,
                name,
                region,
                subregion,
            ),
        ).fetchone()
    )


    if country_result is None:

        raise RuntimeError(
            f"Unable to normalize "
            f"{iso3}."
        )


    country_id = str(
        country_result[0]
    )


    connection.execute(
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
            'country',
            %s,
            'official_reference',
            1.0000,
            %s
        )
        ON CONFLICT DO NOTHING
        """,
        (
            source_record_id,
            country_id,
            Jsonb(
                {
                    "source":
                        SOURCE_CODE,
                    "standard":
                        "M49",
                }
            ),
        ),
    )


    return source_was_new


def main() -> None:

    database_url = os.environ.get(
        "DATABASE_URL"
    )

    if not database_url:

        raise RuntimeError(
            "DATABASE_URL missing."
        )


    snapshot = (
        find_latest_snapshot()
    )

    snapshot_bytes = (
        snapshot.read_bytes()
    )

    snapshot_hash = (
        sha256_bytes(
            snapshot_bytes
        )
    )

    html = (
        snapshot_bytes.decode(
            "utf-8",
            errors="replace",
        )
    )

    records = (
        find_english_records(
            html
        )
    )


    print(
        f"Snapshot: {snapshot}"
    )

    print(
        f"Snapshot SHA-256: "
        f"{snapshot_hash}"
    )

    print(
        f"English records parsed: "
        f"{len(records)}"
    )


    with psycopg.connect(
        database_url
    ) as connection:


        with connection.transaction():

            source_id = (
                register_source(
                    connection,
                    snapshot,
                    snapshot_hash,
                )
            )

            run_id = (
                start_ingestion(
                    connection,
                    source_id,
                    snapshot,
                    snapshot_hash,
                )
            )


        inserted = 0
        reused = 0


        try:

            with connection.transaction():

                for raw in records:

                    was_new = (
                        ingest_record(
                            connection,
                            source_id,
                            run_id,
                            raw,
                        )
                    )

                    if was_new:
                        inserted += 1
                    else:
                        reused += 1


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
                            metadata ||
                            %s
                    WHERE id = %s
                    """,
                    (
                        len(records),
                        inserted,
                        reused,
                        Jsonb(
                            {
                                "normalized_records":
                                    len(records),
                                "source_records_new":
                                    inserted,
                                "source_records_reused":
                                    reused,
                            }
                        ),
                        run_id,
                    ),
                )


        except Exception as error:

            with connection.transaction():

                connection.execute(
                    """
                    UPDATE ingestion_runs
                    SET
                        status = 'failed',
                        finished_at =
                            NOW(),
                        records_seen =
                            %s,
                        error_message =
                            %s
                    WHERE id = %s
                    """,
                    (
                        len(records),
                        str(error),
                        run_id,
                    ),
                )

            raise


        country_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM countries
                """
            ).fetchone()[0]
        )


        source_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM source_records
                WHERE
                    data_source_id =
                        %s
                    AND record_type =
                        'country_or_area'
                """,
                (source_id,),
            ).fetchone()[0]
        )


        link_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM entity_source_links
                WHERE
                    entity_type =
                        'country'
                """
            ).fetchone()[0]
        )


        india = (
            connection.execute(
                """
                SELECT
                    iso2,
                    iso3,
                    numeric_code,
                    name,
                    official_name,
                    region,
                    subregion
                FROM countries
                WHERE iso2 = 'IN'
                """
            ).fetchone()
        )


        print(
            json.dumps(
                {
                    "ok": True,
                    "source":
                        SOURCE_CODE,
                    "records_parsed":
                        len(records),
                    "source_records_new":
                        inserted,
                    "source_records_reused":
                        reused,
                    "countries":
                        country_count,
                    "source_records":
                        source_count,
                    "provenance_links":
                        link_count,
                    "india":
                        list(india)
                        if india
                        else None,
                    "ingestion_run_id":
                        run_id,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
