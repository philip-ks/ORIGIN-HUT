from __future__ import annotations

import hashlib
import json
import os

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx
import psycopg

from dotenv import load_dotenv
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[4]

load_dotenv(
    ROOT / ".env"
)


SOURCE_CODE = (
    "six_iso4217_list_one"
)

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
    "market-reference-data/"
    "data-standards.html"
)


# ------------------------------------------------------------
# ISO ENTITY NAME -> ISO 3166-1 ALPHA-2
#
# Used only when SIX entity names differ from the canonical
# country/territory name stored from UN M49.
#
# Non-country monetary institutions and special ISO units are
# deliberately NOT included here.
# ------------------------------------------------------------

ENTITY_ISO2_ALIASES = {

    "BAHAMAS (THE)":
        "BS",

    "BRITISH INDIAN OCEAN TERRITORY (THE)":
        "IO",

    "CAYMAN ISLANDS (THE)":
        "KY",

    "CENTRAL AFRICAN REPUBLIC (THE)":
        "CF",

    "COCOS (KEELING) ISLANDS (THE)":
        "CC",

    "COMOROS (THE)":
        "KM",

    "CONGO (THE)":
        "CG",

    "CONGO (THE DEMOCRATIC REPUBLIC OF THE)":
        "CD",

    "COOK ISLANDS (THE)":
        "CK",

    "CÔTE D'IVOIRE":
        "CI",

    "DOMINICAN REPUBLIC (THE)":
        "DO",

    "FALKLAND ISLANDS (THE) [MALVINAS]":
        "FK",

    "FAROE ISLANDS (THE)":
        "FO",

    "FRENCH SOUTHERN TERRITORIES (THE)":
        "TF",

    "GAMBIA (THE)":
        "GM",

    "HOLY SEE (THE)":
        "VA",

    "HONG KONG":
        "HK",

    "KOREA (THE DEMOCRATIC PEOPLE’S REPUBLIC OF)":
        "KP",

    "KOREA (THE REPUBLIC OF)":
        "KR",

    "LAO PEOPLE’S DEMOCRATIC REPUBLIC (THE)":
        "LA",

    "MACAO":
        "MO",

    "MARSHALL ISLANDS (THE)":
        "MH",

    "MOLDOVA (THE REPUBLIC OF)":
        "MD",

    "NAURU":
        "NR",

    "NETHERLANDS (THE)":
        "NL",

    "NIGER (THE)":
        "NE",

    "NORTHERN MARIANA ISLANDS (THE)":
        "MP",

    "PHILIPPINES (THE)":
        "PH",

    "RUSSIAN FEDERATION (THE)":
        "RU",

    "SAINT HELENA, ASCENSION AND TRISTAN DA CUNHA":
        "SH",

    "SUDAN (THE)":
        "SD",

    "SVALBARD AND JAN MAYEN":
        "SJ",

    "TAIWAN (PROVINCE OF CHINA)":
        "TW",

    "TANZANIA, UNITED REPUBLIC OF":
        "TZ",

    "TURKS AND CAICOS ISLANDS (THE)":
        "TC",

    "UNITED ARAB EMIRATES (THE)":
        "AE",

    "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND (THE)":
        "GB",

    "UNITED STATES MINOR OUTLYING ISLANDS (THE)":
        "UM",

    "UNITED STATES OF AMERICA (THE)":
        "US",

    "VIRGIN ISLANDS (BRITISH)":
        "VG",

    "VIRGIN ISLANDS (U.S.)":
        "VI",

    "WALLIS AND FUTUNA":
        "WF",

}


SPECIAL_NON_COUNTRY_ENTITIES = {

    "ARAB MONETARY FUND",

    "EUROPEAN UNION",

    "INTERNATIONAL MONETARY FUND (IMF)",

    (
        "MEMBER COUNTRIES OF THE "
        "AFRICAN DEVELOPMENT BANK GROUP"
    ),

    (
        "SISTEMA UNITARIO DE COMPENSACION "
        'REGIONAL DE PAGOS "SUCRE"'
    ),

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
        default=str,
    )

    return hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()


def local_name(
    tag: str,
) -> str:

    if "}" in tag:
        return tag.split(
            "}",
            1,
        )[1]

    return tag


def child_element(
    element: ET.Element,
    name: str,
) -> ET.Element | None:

    for child in list(
        element
    ):

        if local_name(
            child.tag
        ) == name:

            return child

    return None


def child_text(
    element: ET.Element,
    name: str,
) -> str | None:

    child = child_element(
        element,
        name,
    )

    if child is None:
        return None

    value = (
        child.text or ""
    ).strip()

    return value or None


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

    return (
        content,
        path,
    )


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
        root.attrib.get(
            "Pblshd"
        )
        or root.attrib.get(
            "Published"
        )
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

        currency_element = (
            child_element(
                element,
                "CcyNm",
            )
        )

        currency_name = None
        is_fund = False

        if currency_element is not None:

            currency_name = (
                currency_element.text
                or ""
            ).strip() or None

            is_fund = (
                str(
                    currency_element.attrib.get(
                        "IsFund",
                        "",
                    )
                )
                .strip()
                .casefold()
                == "true"
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

                "entity":
                    entity,

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

                "is_fund":
                    is_fund,

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
            record[
                "alphabetic_code"
            ]
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

    return (
        records,
        published,
    )


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


def preserve_source_record(
    connection: psycopg.Connection,
    source_id: str,
    run_id: str,
    record: dict[str, Any],
) -> tuple[
    str,
    bool,
]:

    entity = (
        record[
            "entity"
        ]
        or "UNKNOWN"
    )

    code = record[
        "alphabetic_code"
    ]

    currency_name = record[
        "currency_name"
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
            Jsonb(
                record
            ),
            Jsonb(
                {

                    "entity":
                        entity,

                    "alphabetic_code":
                        code,

                    "is_fund":
                        record[
                            "is_fund"
                        ],

                }
            ),
        ),
    ).fetchone()

    was_new = (
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

    if result is None:

        raise RuntimeError(
            "Unable to preserve "
            f"ISO record {external_id}."
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
        was_new,
    )


def upsert_currency(
    connection: psycopg.Connection,
    record: dict[str, Any],
    source_record_id: str,
) -> str | None:

    code = record[
        "alphabetic_code"
    ]

    currency_name = record[
        "currency_name"
    ]

    if (
        not code
        or len(code) != 3
        or not currency_name
    ):

        return None

    result = connection.execute(
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
            record[
                "numeric_code"
            ],
            currency_name,
            record[
                "minor_unit"
            ],
            Jsonb(
                {

                    "standard":
                        "ISO 4217",

                    "minor_unit_raw":
                        record[
                            "minor_unit_raw"
                        ],

                    "is_fund":
                        record[
                            "is_fund"
                        ],

                }
            ),
        ),
    ).fetchone()

    if result is None:

        raise RuntimeError(
            f"Unable to normalize "
            f"currency {code}."
        )

    currency_id = str(
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
                        record[
                            "entity"
                        ],

                }
            ),
        ),
    )

    return currency_id


def resolve_country(
    connection: psycopg.Connection,
    entity: str,
) -> tuple[
    str,
    str,
] | None:

    result = connection.execute(
        """
        SELECT
            id,
            iso2
        FROM countries
        WHERE
            LOWER(name) =
                LOWER(%s)
            OR LOWER(
                COALESCE(
                    official_name,
                    ''
                )
            ) =
                LOWER(%s)
        LIMIT 1
        """,
        (
            entity,
            entity,
        ),
    ).fetchone()

    if result is not None:

        return (
            str(
                result[0]
            ),
            "exact_name",
        )

    iso2 = (
        ENTITY_ISO2_ALIASES.get(
            entity.upper()
        )
    )

    if iso2 is None:

        return None

    result = connection.execute(
        """
        SELECT id
        FROM countries
        WHERE iso2 = %s
        """,
        (
            iso2,
        ),
    ).fetchone()

    if result is None:

        return None

    return (
        str(
            result[0]
        ),
        "controlled_iso2_alias",
    )


def is_special_non_country(
    entity: str,
) -> bool:

    if entity in (
        SPECIAL_NON_COUNTRY_ENTITIES
    ):
        return True

    if entity.startswith(
        "ZZ"
    ):
        return True

    return False


def link_country_currency(
    connection: psycopg.Connection,
    record: dict[str, Any],
    source_record_id: str,
    currency_id: str,
) -> tuple[
    bool,
    str | None,
]:

    entity = (
        record[
            "entity"
        ]
        or ""
    ).strip()

    if not entity:

        return (
            False,
            "missing_entity",
        )

    if is_special_non_country(
        entity
    ):

        return (
            False,
            "special_non_country",
        )

    resolved = (
        resolve_country(
            connection,
            entity,
        )
    )

    if resolved is None:

        return (
            False,
            "country_not_resolved",
        )

    (
        country_id,
        match_method,
    ) = resolved

    connection.execute(
        """
        INSERT INTO country_currencies (
            country_id,
            currency_id,
            is_primary,
            valid_from,
            valid_to,
            is_fund,
            source_record_id,
            source_entity,
            metadata
        )
        VALUES (
            %s,
            %s,
            FALSE,
            NULL,
            NULL,
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (
            country_id,
            currency_id
        )
        DO UPDATE SET
            is_primary =
                FALSE,
            is_fund =
                EXCLUDED.is_fund,
            source_record_id =
                EXCLUDED.source_record_id,
            source_entity =
                EXCLUDED.source_entity,
            metadata =
                EXCLUDED.metadata
        """,
        (
            country_id,
            currency_id,
            record[
                "is_fund"
            ],
            source_record_id,
            entity,
            Jsonb(
                {

                    "source":
                        SOURCE_CODE,

                    "standard":
                        "ISO 4217",

                    "match_method":
                        match_method,

                    "authoritative_primary":
                        False,

                }
            ),
        ),
    )

    return (
        True,
        match_method,
    )


def main() -> None:

    database_url = (
        os.environ.get(
            "DATABASE_URL"
        )
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

    fund_rows = sum(
        1
        for record in records
        if record[
            "is_fund"
        ]
    )

    print(
        f"ISO 4217 entity rows parsed: "
        f"{len(records)}"
    )

    print(
        f"Fund rows: {fund_rows}"
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

        linked_rows = 0

        match_methods = Counter()

        skipped_special = []
        unresolved_entities = []

        try:

            with connection.transaction():

                # Rebuild relationships derived from
                # this official ISO source.
                connection.execute(
                    """
                    DELETE FROM country_currencies
                    WHERE
                        metadata ->> 'source'
                        = %s
                    """,
                    (
                        SOURCE_CODE,
                    ),
                )

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
                        raw_new += 1
                    else:
                        raw_reused += 1

                    currency_id = (
                        upsert_currency(
                            connection,
                            record,
                            source_record_id,
                        )
                    )

                    if currency_id is None:

                        skipped_no_code += 1
                        continue

                    normalized_rows += 1

                    (
                        linked,
                        reason,
                    ) = (
                        link_country_currency(
                            connection,
                            record,
                            source_record_id,
                            currency_id,
                        )
                    )

                    if linked:

                        linked_rows += 1

                        if reason:
                            match_methods[
                                reason
                            ] += 1

                    elif reason == (
                        "special_non_country"
                    ):

                        skipped_special.append(
                            {
                                "entity":
                                    record[
                                        "entity"
                                    ],
                                "code":
                                    record[
                                        "alphabetic_code"
                                    ],
                            }
                        )

                    elif reason == (
                        "country_not_resolved"
                    ):

                        unresolved_entities.append(
                            {
                                "entity":
                                    record[
                                        "entity"
                                    ],
                                "code":
                                    record[
                                        "alphabetic_code"
                                    ],
                            }
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

                                "normalized_entries":
                                    normalized_rows,

                                "rows_without_code":
                                    skipped_no_code,

                                "country_currency_links":
                                    linked_rows,

                                "fund_rows":
                                    fund_rows,

                                "match_methods":
                                    dict(
                                        match_methods
                                    ),

                                "special_non_country_rows":
                                    len(
                                        skipped_special
                                    ),

                                "unresolved_country_rows":
                                    len(
                                        unresolved_entities
                                    ),

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

        relationship_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM country_currencies
                """
            ).fetchone()[0]
        )

        fund_relationship_count = (
            connection.execute(
                """
                SELECT COUNT(*)
                FROM country_currencies
                WHERE is_fund = TRUE
                """
            ).fetchone()[0]
        )

        india = (
            connection.execute(
                """
                SELECT
                    c.iso2,
                    c.name,
                    cur.code,
                    cur.name,
                    cc.is_fund,
                    cc.is_primary
                FROM country_currencies cc
                JOIN countries c
                    ON c.id =
                       cc.country_id
                JOIN currencies cur
                    ON cur.id =
                       cc.currency_id
                WHERE c.iso2 = 'IN'
                ORDER BY cur.code
                """
            ).fetchall()
        )

        bhutan = (
            connection.execute(
                """
                SELECT
                    c.iso2,
                    c.name,
                    cur.code,
                    cur.name,
                    cc.is_fund,
                    cc.is_primary
                FROM country_currencies cc
                JOIN countries c
                    ON c.id =
                       cc.country_id
                JOIN currencies cur
                    ON cur.id =
                       cc.currency_id
                WHERE c.iso2 = 'BT'
                ORDER BY cur.code
                """
            ).fetchall()
        )

        result = {

            "ok":
                True,

            "source":
                SOURCE_CODE,

            "published":
                published,

            "rows_parsed":
                len(records),

            "fund_rows":
                fund_rows,

            "raw_records_new":
                raw_new,

            "raw_records_reused":
                raw_reused,

            "normalized_entries":
                normalized_rows,

            "rows_without_code":
                skipped_no_code,

            "distinct_currency_codes":
                currency_count,

            "country_currency_links":
                relationship_count,

            "fund_relationships":
                fund_relationship_count,

            "match_methods":
                dict(
                    match_methods
                ),

            "special_non_country_rows":
                len(
                    skipped_special
                ),

            "unresolved_country_rows":
                len(
                    unresolved_entities
                ),

            "unresolved_entities":
                unresolved_entities,

            "india":
                [
                    list(row)
                    for row in india
                ],

            "bhutan":
                [
                    list(row)
                    for row in bhutan
                ],

            "ingestion_run_id":
                run_id,

        }

        print()

        print(
            "============================================================"
        )

        print(
            " ISO 4217 INGESTION RESULT"
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

        print()

        print(
            "PASS: ISO 4217 currencies "
            "and country relationships "
            "ingested successfully."
        )


if __name__ == "__main__":
    main()
