from __future__ import annotations

import hashlib
import json
import os

from collections import Counter
from pathlib import Path
from typing import Any

import psycopg

from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from inspect_hs2022 import (
    CLASSIFICATION,
    NOMENCLATURE,
    SOURCE_PROVIDER,
    SOURCE_URL,
    expected_parent,
    find_record_list,
    normalize_record,
)


ROOT = Path(__file__).resolve().parents[4]

load_dotenv(
    ROOT / ".env"
)


SOURCE_CODE = (
    "unsd_uncomtrade_hs2022_h6"
)

SOURCE_NAME = (
    "Harmonized System 2022 "
    "Classification - H6"
)

VALID_FROM = "2022-01-01"


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
        default=str,
    )

    return hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()


def normalize_boolean(
    value: Any,
) -> bool | None:

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return value

    if isinstance(
        value,
        int,
    ):
        if value == 1:
            return True

        if value == 0:
            return False

    text = str(
        value
    ).strip().casefold()

    if text in {
        "true",
        "1",
        "yes",
        "y",
    }:
        return True

    if text in {
        "false",
        "0",
        "no",
        "n",
    }:
        return False

    return None


def find_latest_snapshot() -> Path:

    snapshot_root = (
        ROOT
        / "storage"
        / "imports"
        / "hs2022"
    )

    snapshots = sorted(
        snapshot_root.glob(
            "*/H6.json"
        ),
        key=lambda path:
            path.stat().st_mtime,
        reverse=True,
    )

    if not snapshots:

        raise RuntimeError(
            "No inspected HS 2022 H6 snapshot exists. "
            "Run inspect_hs2022.py first."
        )

    return snapshots[0]


def load_records(
    snapshot: Path,
) -> tuple[
    list[dict[str, Any]],
    bytes,
]:

    content = (
        snapshot.read_bytes()
    )

    document = json.loads(
        content.decode(
            "utf-8-sig"
        )
    )

    raw_records = (
        find_record_list(
            document
        )
    )

    if not raw_records:

        raise RuntimeError(
            "No HS records were found "
            "inside the H6 snapshot."
        )

    normalized = [
        normalize_record(
            raw
        )
        for raw in raw_records
    ]

    records: list[
        dict[str, Any]
    ] = []

    for record in normalized:

        code = record[
            "code"
        ]

        if not code:
            continue

        if not code.isdigit():
            continue

        if len(code) not in (
            2,
            4,
            6,
        ):
            continue

        description = (
            record[
                "description"
            ]
        )

        if not description:

            raise RuntimeError(
                f"HS code {code} has "
                "no description."
            )

        record[
            "level"
        ] = len(code)

        record[
            "is_leaf_normalized"
        ] = normalize_boolean(
            record[
                "is_leaf"
            ]
        )

        standard_unit = (
            record[
                "standard_unit"
            ]
        )

        if standard_unit is not None:

            standard_unit = str(
                standard_unit
            ).strip()

            if not standard_unit:
                standard_unit = None

        record[
            "standard_unit_normalized"
        ] = standard_unit

        records.append(
            record
        )

    if len(records) < 6_000:

        raise RuntimeError(
            "Too few valid HS 2022 "
            "2/4/6-digit records."
        )

    counts = Counter(
        record["code"]
        for record in records
    )

    duplicates = [
        code
        for code, count
        in counts.items()
        if count > 1
    ]

    if duplicates:

        raise RuntimeError(
            "Duplicate HS codes detected: "
            + ", ".join(
                sorted(
                    duplicates
                )[:20]
            )
        )

    return (
        records,
        content,
    )


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
            'official_json_snapshot',
            %s,
            %s,
            'revision',
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
            SOURCE_URL,
            (
                "United Nations Statistics Division / "
                "UN Comtrade"
            ),
            Jsonb(
                {
                    "classification":
                        CLASSIFICATION,
                    "nomenclature":
                        NOMENCLATURE,
                    "snapshot":
                        str(snapshot),
                    "snapshot_sha256":
                        snapshot_hash,
                    "edition":
                        2022,
                }
            ),
        ),
    ).fetchone()

    if result is None:

        raise RuntimeError(
            "Unable to register "
            "HS 2022 source."
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
                    "classification":
                        CLASSIFICATION,
                    "nomenclature":
                        NOMENCLATURE,
                    "snapshot":
                        str(snapshot),
                    "snapshot_sha256":
                        snapshot_hash,
                    "source_url":
                        SOURCE_URL,
                }
            ),
        ),
    ).fetchone()

    if result is None:

        raise RuntimeError(
            "Unable to create "
            "HS ingestion run."
        )

    return str(
        result[0]
    )


def preserve_source_record(
    connection: psycopg.Connection,
    source_id: str,
    run_id: str,
    record: dict[str, Any],
) -> tuple[
    str,
    bool,
]:

    code = record[
        "code"
    ]

    raw = record[
        "raw"
    ]

    content_hash = (
        sha256_payload(
            raw
        )
    )

    result = connection.execute(
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
            'hs_code',
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
            code,
            content_hash,
            Jsonb(
                raw
            ),
            Jsonb(
                {
                    "classification":
                        CLASSIFICATION,
                    "nomenclature":
                        NOMENCLATURE,
                    "code":
                        code,
                    "level":
                        record[
                            "level"
                        ],
                }
            ),
        ),
    ).fetchone()

    source_was_new = (
        result is not None
    )

    if result is None:

        result = connection.execute(
            """
            SELECT id
            FROM source_records
            WHERE
                data_source_id = %s
                AND record_type =
                    'hs_code'
                AND external_id = %s
                AND content_hash = %s
            """,
            (
                source_id,
                code,
                content_hash,
            ),
        ).fetchone()

    if result is None:

        raise RuntimeError(
            f"Unable to obtain "
            f"source record for "
            f"HS {code}."
        )

    source_record_id = str(
        result[0]
    )

    connection.execute(
        """
        INSERT INTO ingestion_run_records (
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
            run_id,
            source_record_id,
        ),
    )

    return (
        source_record_id,
        source_was_new,
    )


def upsert_hs_code(
    connection: psycopg.Connection,
    record: dict[str, Any],
    source_record_id: str,
) -> str:

    source_parent = (
        record[
            "parent"
        ]
    )

    result = connection.execute(
        """
        INSERT INTO hs_codes (
            nomenclature,
            code,
            level,
            parent_id,
            description,
            valid_from,
            valid_to,
            is_leaf,
            standard_unit,
            metadata,
            canonical_source_record_id
        )
        VALUES (
            %s,
            %s,
            %s,
            NULL,
            %s,
            %s,
            NULL,
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (
            nomenclature,
            code
        )
        DO UPDATE SET
            level =
                EXCLUDED.level,
            parent_id =
                NULL,
            description =
                EXCLUDED.description,
            valid_from =
                EXCLUDED.valid_from,
            valid_to =
                NULL,
            is_leaf =
                EXCLUDED.is_leaf,
            standard_unit =
                EXCLUDED.standard_unit,
            metadata =
                EXCLUDED.metadata,
            canonical_source_record_id =
                EXCLUDED.canonical_source_record_id
        RETURNING id
        """,
        (
            NOMENCLATURE,
            record[
                "code"
            ],
            record[
                "level"
            ],
            record[
                "description"
            ],
            VALID_FROM,
            record[
                "is_leaf_normalized"
            ],
            record[
                "standard_unit_normalized"
            ],
            Jsonb(
                {
                    "classification":
                        CLASSIFICATION,
                    "source_parent":
                        source_parent,
                    "source_aggregation_level":
                        record[
                            "aggregation_level"
                        ],
                    "source_is_leaf":
                        record[
                            "is_leaf"
                        ],
                }
            ),
            source_record_id,
        ),
    ).fetchone()

    if result is None:

        raise RuntimeError(
            f"Unable to normalize "
            f"HS {record['code']}."
        )

    hs_code_id = str(
        result[0]
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
            'hs_code',
            %s,
            'official_reference',
            1.0000,
            %s
        )
        ON CONFLICT DO NOTHING
        """,
        (
            source_record_id,
            hs_code_id,
            Jsonb(
                {
                    "source":
                        SOURCE_CODE,
                    "nomenclature":
                        NOMENCLATURE,
                }
            ),
        ),
    )

    return hs_code_id


def attach_hierarchy(
    connection: psycopg.Connection,
    records: list[
        dict[str, Any]
    ],
    code_to_id: dict[
        str,
        str,
    ],
) -> int:

    relationships = 0

    for record in records:

        code = record[
            "code"
        ]

        parent_code = (
            expected_parent(
                code
            )
        )

        parent_id = None

        if parent_code:

            parent_id = (
                code_to_id.get(
                    parent_code
                )
            )

            if not parent_id:

                raise RuntimeError(
                    f"Missing parent "
                    f"{parent_code} "
                    f"for HS {code}."
                )

            relationships += 1

        connection.execute(
            """
            UPDATE hs_codes
            SET parent_id = %s
            WHERE id = %s
            """,
            (
                parent_id,
                code_to_id[
                    code
                ],
            ),
        )

    return relationships


def mark_failed(
    connection: psycopg.Connection,
    run_id: str,
    records_seen: int,
    error: Exception,
) -> None:

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
            records_seen,
            str(error),
            run_id,
        ),
    )


def main() -> None:

    database_url = (
        os.environ.get(
            "DATABASE_URL"
        )
    )

    if not database_url:

        raise RuntimeError(
            "DATABASE_URL missing."
        )

    snapshot = (
        find_latest_snapshot()
    )

    records, snapshot_bytes = (
        load_records(
            snapshot
        )
    )

    snapshot_hash = (
        sha256_bytes(
            snapshot_bytes
        )
    )

    level_counts = Counter(
        record[
            "level"
        ]
        for record in records
    )

    print(
        "Origin Hut HS 2022 importer"
    )

    print(
        f"Snapshot: {snapshot}"
    )

    print(
        f"Snapshot SHA-256: "
        f"{snapshot_hash}"
    )

    print(
        f"Valid HS records: "
        f"{len(records):,}"
    )

    print(
        f"Levels: "
        f"{dict(sorted(level_counts.items()))}"
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

        new_source_records = 0
        reused_source_records = 0

        code_to_id: dict[
            str,
            str,
        ] = {}

        try:

            with connection.transaction():

                for record in records:

                    (
                        source_record_id,
                        source_was_new,
                    ) = (
                        preserve_source_record(
                            connection,
                            source_id,
                            run_id,
                            record,
                        )
                    )

                    if source_was_new:
                        new_source_records += 1
                    else:
                        reused_source_records += 1

                    hs_code_id = (
                        upsert_hs_code(
                            connection,
                            record,
                            source_record_id,
                        )
                    )

                    code_to_id[
                        record[
                            "code"
                        ]
                    ] = (
                        hs_code_id
                    )

                hierarchy_links = (
                    attach_hierarchy(
                        connection,
                        records,
                        code_to_id,
                    )
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
                        new_source_records,
                        reused_source_records,
                        Jsonb(
                            {
                                "normalized_hs_codes":
                                    len(records),
                                "hierarchy_links":
                                    hierarchy_links,
                                "levels":
                                    dict(
                                        level_counts
                                    ),
                            }
                        ),
                        run_id,
                    ),
                )

        except Exception as error:

            with connection.transaction():

                mark_failed(
                    connection,
                    run_id,
                    len(records),
                    error,
                )

            raise

        database_level_counts = dict(
            connection.execute(
                """
                SELECT
                    level,
                    COUNT(*)
                FROM hs_codes
                WHERE nomenclature = %s
                GROUP BY level
                ORDER BY level
                """,
                (
                    NOMENCLATURE,
                ),
            ).fetchall()
        )

        total_hs_codes = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM hs_codes
                WHERE nomenclature = %s
                """,
                (
                    NOMENCLATURE,
                ),
            ).fetchone()[0]
        )

        orphan_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM hs_codes
                WHERE
                    nomenclature = %s
                    AND level IN (
                        4,
                        6
                    )
                    AND parent_id
                        IS NULL
                """,
                (
                    NOMENCLATURE,
                ),
            ).fetchone()[0]
        )

        source_record_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM source_records
                WHERE
                    data_source_id = %s
                    AND record_type =
                        'hs_code'
                """,
                (
                    source_id,
                ),
            ).fetchone()[0]
        )

        run_record_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM ingestion_run_records
                WHERE ingestion_run_id = %s
                """,
                (
                    run_id,
                ),
            ).fetchone()[0]
        )

        provenance_link_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM entity_source_links
                WHERE
                    entity_type =
                        'hs_code'
                    AND metadata ->>
                        'nomenclature'
                        = %s
                """,
                (
                    NOMENCLATURE,
                ),
            ).fetchone()[0]
        )

        result = {

            "ok":
                (
                    total_hs_codes
                    == len(records)
                    and orphan_count
                    == 0
                ),

            "source":
                SOURCE_CODE,

            "classification":
                CLASSIFICATION,

            "nomenclature":
                NOMENCLATURE,

            "snapshot":
                str(snapshot),

            "snapshot_sha256":
                snapshot_hash,

            "records_parsed":
                len(records),

            "source_records_new":
                new_source_records,

            "source_records_reused":
                reused_source_records,

            "hs_codes":
                total_hs_codes,

            "database_levels":
                database_level_counts,

            "hierarchy_links":
                hierarchy_links,

            "orphan_codes":
                orphan_count,

            "source_records":
                source_record_count,

            "run_records":
                run_record_count,

            "provenance_links":
                provenance_link_count,

            "ingestion_run_id":
                run_id,
        }

        print()
        print(
            "============================================================"
        )

        print(
            " HS 2022 INGESTION RESULT"
        )

        print(
            "============================================================"
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

        if not result[
            "ok"
        ]:

            raise RuntimeError(
                "HS 2022 ingestion "
                "verification failed."
            )

        print()
        print(
            "PASS: Official HS 2022 "
            "reference ingested successfully."
        )


if __name__ == "__main__":
    main()
