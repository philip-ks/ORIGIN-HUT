from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[4]

load_dotenv(ROOT / ".env")


SOURCE_CODE = "six_iso4217_list_one"

SOURCE_NAME = (
    "ISO 4217 List One - "
    "Current Currency & Funds"
)

SOURCE_PROVIDER = (
    "SIX Financial Information AG"
)

SOURCE_URL = (
    "https://www.six-group.com/"
    "dam/download/financial-information/"
    "data-center/iso-currrency/"
    "lists/list-one.xml"
)

REFERENCE_PAGE = (
    "https://www.six-group.com/en/"
    "products-services/financial-information/"
    "market-reference-data/data-standards.html"
)


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


def local_name(tag: str) -> str:

    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def child_text(
    element: ET.Element,
    name: str,
) -> str | None:

    for child in list(element):

        if local_name(
            child.tag
        ) == name:

            value = (
                child.text or ""
            ).strip()

            return value or None

    return None


def download_source() -> tuple[
    bytes,
    Path,
]:

    print(
        "Downloading official ISO 4217 "
        "List One from SIX..."
    )

    response = httpx.get(
        SOURCE_URL,
        timeout=90.0,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "OriginHut/0.1 "
                "(ISO 4217 reference ingestion)"
            )
        },
    )

    response.raise_for_status()

    content = response.content

    if len(content) < 1_000:

        raise RuntimeError(
            "Downloaded ISO 4217 XML "
            "is unexpectedly small."
        )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    directory = (
        ROOT
        / "storage"
        / "imports"
        / "iso4217"
        / timestamp
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        directory
        / "list-one.xml"
    )

    path.write_bytes(
        content
    )

    print(
        f"Raw snapshot saved: {path}"
    )

    return content, path


def parse_xml(
    content: bytes,
) -> tuple[
    list[dict[str, Any]],
    str | None,
]:

    root = ET.fromstring(
        content
    )

    published = (
        root.attrib.get("Pblshd")
        or root.attrib.get("Published")
    )

    records: list[
        dict[str, Any]
    ] = []

    for element in root.iter():

        if local_name(
            element.tag
        ) != "CcyNtry":
            continue

        entity = child_text(
            element,
            "CtryNm",
        )

        currency_name = child_text(
            element,
            "CcyNm",
        )

        code = child_text(
            element,
            "Ccy",
        )

        numeric_code = child_text(
            element,
            "CcyNbr",
        )

        minor_unit_raw = child_text(
            element,
            "CcyMnrUnts",
        )

        minor_unit = None

        if (
            minor_unit_raw
            and minor_unit_raw.isdigit()
        ):
            minor_unit = int(
                minor_unit_raw
            )

        records.append(
            {
                "entity": entity,
                "currency_name":
                    currency_name,
                "alphabetic_code":
                    code,
                "numeric_code":
                    numeric_code,
                "minor_unit":
                    minor_unit,
                "minor_unit_raw":
                    minor_unit_raw,
            }
        )

    if len(records) < 200:

        raise RuntimeError(
            f"Only {len(records)} ISO 4217 "
            "entity rows were parsed."
        )

    coded = [
        record
        for record in records
        if (
            record["alphabetic_code"]
            and len(
                record[
                    "alphabetic_code"
                ]
            ) == 3
        )
    ]

    if len(coded) < 100:

        raise RuntimeError(
            "Too few valid ISO 4217 "
            "currency codes were parsed."
        )

    return records, published


def register_source(
    connection: psycopg.Connection,
    snapshot: Path,
    snapshot_hash: str,
    published: str | None,
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
            'official_xml',
            %s,
            %s,
            'as_published',
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
                "SIX Financial Information AG, "
                "ISO 4217 Maintenance Agency"
            ),
            Jsonb(
                {
                    "standard":
                        "ISO 4217",
                    "list":
                        "List One",
                    "reference_page":
                        REFERENCE_PAGE,
                    "published":
                        published,
                    "snapshot":
                        str(snapshot),
                    "snapshot_sha256":
                        snapshot_hash,
                }
            ),
        ),
    ).fetchone()

    if result is None:

        raise RuntimeError(
            "Unable to register "
            "ISO 4217 data source."
        )

    return str(
        result[0]
    )


def start_run(
    connection: psycopg.Connection,
    source_id: str,
    snapshot: Path,
    snapshot_hash: str,
    published: str | None,
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
                    "published":
                        published,
                }
            ),
        ),
    ).fetchone()

    if result is None:

        raise RuntimeError(
            "Unable to create "
            "ISO 4217 ingestion run."
        )

    return str(
        result[0]
    )


def ingest_entry(
    connection: psycopg.Connection,
    source_id: str,
    run_id: str,
    record: dict[str, Any],
) -> tuple[
    bool,
    bool,
]:

    entity = (
        record["entity"]
        or "UNKNOWN"
    )

    code = record[
        "alphabetic_code"
    ]

    currency_name = record[
        "currency_name"
    ]

    numeric_code = record[
        "numeric_code"
    ]

    minor_unit = record[
        "minor_unit"
    ]


    external_id = (
        f"{entity}|"
        f"{code or currency_name or 'NONE'}"
    )


    content_hash = (
        sha256_payload(
            record
        )
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
                'iso4217_entry',
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
                external_id IS NOT NULL
                AND content_hash IS NOT NULL
            DO NOTHING
            RETURNING id
            """,
            (
                source_id,
                run_id,
                external_id,
                content_hash,
                Jsonb(record),
                Jsonb(
                    {
                        "entity":
                            entity,
                        "alphabetic_code":
                            code,
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
                        'iso4217_entry'
                    AND external_id = %s
                    AND content_hash = %s
                """,
                (
                    source_id,
                    external_id,
                    content_hash,
                ),
            ).fetchone()
        )


    if source_result is None:

        raise RuntimeError(
            "Unable to preserve "
            f"source entry {external_id}."
        )


    source_record_id = str(
        source_result[0]
    )


    # Some ISO entities explicitly have no universal
    # currency. Preserve those source rows but do not
    # create a fake currency entity.
    if (
        not code
        or len(code) != 3
        or not currency_name
    ):

        return (
            source_was_new,
            False,
        )


    currency_result = (
        connection.execute(
            """
            INSERT INTO currencies (
                code,
                numeric_code,
                name,
                symbol,
                decimal_places,
                is_active,
                metadata
            )
            VALUES (
                %s,
                %s,
                %s,
                NULL,
                %s,
                TRUE,
                %s
            )
            ON CONFLICT (code)
            DO UPDATE SET
                numeric_code =
                    EXCLUDED.numeric_code,
                name =
                    EXCLUDED.name,
                decimal_places =
                    EXCLUDED.decimal_places,
                is_active =
                    TRUE,
                metadata =
                    currencies.metadata
                    || EXCLUDED.metadata,
                updated_at =
                    NOW()
            RETURNING id
            """,
            (
                code.upper(),
                numeric_code,
                currency_name,
                minor_unit,
                Jsonb(
                    {
                        "standard":
                            "ISO 4217",
                        "minor_unit_raw":
                            record[
                                "minor_unit_raw"
                            ],
                    }
                ),
            ),
        ).fetchone()
    )


    if currency_result is None:

        raise RuntimeError(
            f"Unable to normalize "
            f"currency {code}."
        )


    currency_id = str(
        currency_result[0]
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
            'currency',
            %s,
            'official_reference',
            1.0000,
            %s
        )
        ON CONFLICT DO NOTHING
        """,
        (
            source_record_id,
            currency_id,
            Jsonb(
                {
                    "source":
                        SOURCE_CODE,
                    "standard":
                        "ISO 4217",
                    "entity":
                        entity,
                }
            ),
        ),
    )


    return (
        source_was_new,
        True,
    )


def main() -> None:

    database_url = os.environ.get(
        "DATABASE_URL"
    )

    if not database_url:

        raise RuntimeError(
            "DATABASE_URL is missing."
        )


    content, snapshot = (
        download_source()
    )

    snapshot_hash = (
        sha256_bytes(
            content
        )
    )


    records, published = (
        parse_xml(
            content
        )
    )


    print(
        f"ISO 4217 entity rows parsed: "
        f"{len(records)}"
    )

    print(
        f"Published: {published}"
    )

    print(
        f"Snapshot SHA-256: "
        f"{snapshot_hash}"
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
                    published,
                )
            )

            run_id = (
                start_run(
                    connection,
                    source_id,
                    snapshot,
                    snapshot_hash,
                    published,
                )
            )


        raw_new = 0
        raw_reused = 0
        normalized_rows = 0
        skipped_no_code = 0


        try:

            with connection.transaction():

                for record in records:

                    (
                        source_was_new,
                        normalized,
                    ) = ingest_entry(
                        connection,
                        source_id,
                        run_id,
                        record,
                    )

                    if source_was_new:
                        raw_new += 1
                    else:
                        raw_reused += 1

                    if normalized:
                        normalized_rows += 1
                    else:
                        skipped_no_code += 1


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
                                "normalized_entries":
                                    normalized_rows,
                                "rows_without_code":
                                    skipped_no_code,
                                "published":
                                    published,
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
                        status =
                            'failed',
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


        currency_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM currencies
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
                        'iso4217_entry'
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
                        'currency'
                """
            ).fetchone()[0]
        )


        inr = (
            connection.execute(
                """
                SELECT
                    code,
                    numeric_code,
                    name,
                    decimal_places
                FROM currencies
                WHERE code = 'INR'
                """
            ).fetchone()
        )


        eur = (
            connection.execute(
                """
                SELECT
                    code,
                    numeric_code,
                    name,
                    decimal_places
                FROM currencies
                WHERE code = 'EUR'
                """
            ).fetchone()
        )


        print(
            json.dumps(
                {
                    "ok": True,
                    "source":
                        SOURCE_CODE,
                    "published":
                        published,
                    "rows_parsed":
                        len(records),
                    "raw_records_new":
                        raw_new,
                    "raw_records_reused":
                        raw_reused,
                    "normalized_entry_links":
                        normalized_rows,
                    "rows_without_code":
                        skipped_no_code,
                    "distinct_currency_codes":
                        currency_count,
                    "source_records":
                        source_count,
                    "currency_provenance_links":
                        link_count,
                    "INR":
                        list(inr)
                        if inr else None,
                    "EUR":
                        list(eur)
                        if eur else None,
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
