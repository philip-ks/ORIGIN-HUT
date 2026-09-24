from __future__ import annotations

import os

from pathlib import Path
from typing import Any, Sequence

import psycopg

from dotenv import load_dotenv
from psycopg.types.json import Jsonb


ROOT = (
    Path(__file__)
    .resolve()
    .parents[4]
)


SOURCE_CODE = (
    "un_comtrade_trade"
)

SOURCE_NAME = (
    "UN Comtrade International "
    "Merchandise Trade Statistics"
)

SOURCE_PROVIDER = (
    "United Nations Statistics Division / UN Comtrade"
)

SOURCE_URL = (
    "https://comtradeapi.un.org/"
)

RECORD_TYPE = (
    "trade_observation"
)

NORMALIZER_VERSION = (
    "un_comtrade_trade_v1"
)


class CanonicalizationError(
    RuntimeError
):
    pass


def stop(
    message: str,
) -> None:

    raise CanonicalizationError(
        message
    )


def database_url() -> str:

    load_dotenv(
        ROOT / ".env"
    )

    value = os.environ.get(
        "DATABASE_URL"
    )

    if not value:

        stop(
            "DATABASE_URL missing."
        )

    return value


def relative_path(
    path: Path,
) -> str:

    resolved = path.resolve()

    try:

        return (
            resolved
            .relative_to(
                ROOT.resolve()
            )
            .as_posix()
        )

    except ValueError:

        return str(
            resolved
        )


def canonical_transport_mode(
    value: Any,
) -> str | None:

    if value is None:
        return None

    text = str(
        value
    ).strip()

    if text in {
        "",
        "0",
    }:
        return None

    return text


def canonical_customs_procedure(
    value: Any,
) -> str | None:

    if value is None:
        return None

    text = str(
        value
    ).strip()

    if text in {
        "",
        "0",
        "C00",
    }:
        return None

    return text


def register_source(
    connection: psycopg.Connection,
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
            'trade_statistics',
            'public_api',
            %s,
            %s,
            'provider_defined',
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
            SOURCE_PROVIDER,
            Jsonb(
                {
                    "dataset":
                        "international_merchandise_trade",

                    "canonicalizerVersion":
                        NORMALIZER_VERSION,

                    "sourceSemantics":
                        "statistical_aggregate",
                }
            ),
        ),
    ).fetchone()


    if result is None:

        stop(
            "Unable to register "
            "UN Comtrade data source."
        )


    return str(
        result[0]
    )


def start_ingestion(
    connection: psycopg.Connection,
    source_id: str,
    *,
    artifact_run_id: str,
    request_url: str,
    raw_path: Path,
    parquet_paths: Sequence[Path],
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
                    "artifactRunId":
                        artifact_run_id,

                    "requestUrl":
                        request_url,

                    "rawArtifact":
                        relative_path(
                            raw_path
                        ),

                    "parquetArtifacts":
                        [
                            relative_path(
                                path
                            )
                            for path
                            in parquet_paths
                        ],

                    "canonicalizerVersion":
                        NORMALIZER_VERSION,
                }
            ),
        ),
    ).fetchone()


    if result is None:

        stop(
            "Unable to create "
            "UN Comtrade ingestion run."
        )


    return str(
        result[0]
    )


def preserve_source_record(
    connection: psycopg.Connection,
    source_id: str,
    ingestion_run_id: str,
    raw_record: dict[str, Any],
    normalized: dict[str, Any],
    *,
    artifact_run_id: str,
    request_url: str,
    raw_path: Path,
    parquet_paths: Sequence[Path],
) -> tuple[
    str,
    bool,
]:

    external_id = normalized[
        "sourceExternalId"
    ]

    content_hash = normalized[
        "sourceContentHash"
    ]


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
            %s,
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
            ingestion_run_id,
            external_id,
            RECORD_TYPE,
            content_hash,
            Jsonb(
                raw_record
            ),
            Jsonb(
                {
                    "artifactRunId":
                        artifact_run_id,

                    "requestUrl":
                        request_url,

                    "rawArtifact":
                        relative_path(
                            raw_path
                        ),

                    "parquetArtifacts":
                        [
                            relative_path(
                                path
                            )
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

                    "hsCode":
                        normalized[
                            "hsCode"
                        ],

                    "canonicalizerVersion":
                        NORMALIZER_VERSION,
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
                AND record_type = %s
                AND external_id = %s
                AND content_hash = %s
            """,
            (
                source_id,
                RECORD_TYPE,
                external_id,
                content_hash,
            ),
        ).fetchone()


    if result is None:

        stop(
            "Unable to obtain immutable "
            "Comtrade source record."
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
            ingestion_run_id,
            source_record_id,
        ),
    )


    return (
        source_record_id,
        was_new,
    )


def resolve_country(
    connection: psycopg.Connection,
    iso3: str,
) -> str:

    rows = connection.execute(
        """
        SELECT id
        FROM countries
        WHERE
            iso3 = %s
            AND is_active = TRUE
        """,
        (
            iso3,
        ),
    ).fetchall()


    if len(rows) != 1:

        stop(
            "Country ISO3 did not "
            f"resolve uniquely: {iso3}"
        )


    return str(
        rows[0][0]
    )


def resolve_references(
    connection: psycopg.Connection,
    normalized: dict[str, Any],
) -> dict[str, str | None]:

    reporter_id = resolve_country(
        connection,
        normalized[
            "reporterISO3"
        ],
    )


    partner_iso3 = normalized[
        "partnerISO3"
    ]


    partner_id = (
        resolve_country(
            connection,
            partner_iso3,
        )
        if partner_iso3
        else None
    )


    hs_rows = connection.execute(
        """
        SELECT id
        FROM hs_codes
        WHERE
            nomenclature = 'HS2022'
            AND code = %s
            AND level = 6
        """,
        (
            normalized[
                "hsCode"
            ],
        ),
    ).fetchall()


    if len(hs_rows) != 1:

        stop(
            "HS2022 code did not "
            "resolve uniquely."
        )


    currency_rows = connection.execute(
        """
        SELECT id
        FROM currencies
        WHERE
            code = 'USD'
            AND is_active = TRUE
        """
    ).fetchall()


    if len(currency_rows) != 1:

        stop(
            "USD currency did not "
            "resolve uniquely."
        )


    return {
        "reporterCountryId":
            reporter_id,

        "partnerCountryId":
            partner_id,

        "hsCodeId":
            str(
                hs_rows[0][0]
            ),

        "currencyId":
            str(
                currency_rows[0][0]
            ),
    }


def trade_metadata(
    raw_record: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any]:

    return {
        "sourceSystem":
            "un_comtrade",

        "sourceCode":
            SOURCE_CODE,

        "sourceExternalId":
            normalized[
                "sourceExternalId"
            ],

        "sourceContentHash":
            normalized[
                "sourceContentHash"
            ],

        "normalizerVersion":
            NORMALIZER_VERSION,

        "classificationCode":
            normalized[
                "classificationCode"
            ],

        "reporterISO3":
            normalized[
                "reporterISO3"
            ],

        "partnerISO3":
            normalized[
                "partnerISO3"
            ],

        "sourceReporterCode":
            raw_record.get(
                "reporterCode"
            ),

        "sourcePartnerCode":
            raw_record.get(
                "partnerCode"
            ),

        "sourcePartner2Code":
            raw_record.get(
                "partner2Code"
            ),

        "sourcePartner2ISO":
            raw_record.get(
                "partner2ISO"
            ),

        "sourceCustomsCode":
            raw_record.get(
                "customsCode"
            ),

        "sourceTransportModeCode":
            raw_record.get(
                "motCode"
            ),

        "sourceAggregateLevel":
            raw_record.get(
                "aggrLevel"
            ),

        "isAggregate":
            raw_record.get(
                "isAggregate"
            ),

        "isReported":
            raw_record.get(
                "isReported"
            ),

        "isQtyEstimated":
            raw_record.get(
                "isQtyEstimated"
            ),

        "isNetWeightEstimated":
            raw_record.get(
                "isNetWgtEstimated"
            ),

        "isGrossWeightEstimated":
            raw_record.get(
                "isGrossWgtEstimated"
            ),
    }


def upsert_trade_flow(
    connection: psycopg.Connection,
    source_record_id: str,
    raw_record: dict[str, Any],
    normalized: dict[str, Any],
    references: dict[str, str | None],
) -> tuple[
    str,
    str,
]:

    external_id = normalized[
        "sourceExternalId"
    ]


    lock_identity = (
        SOURCE_CODE
        + ":"
        + external_id
    )


    connection.execute(
        """
        SELECT pg_advisory_xact_lock(
            hashtextextended(
                %s,
                0
            )
        )
        """,
        (
            lock_identity,
        ),
    )


    rows = connection.execute(
        """
        SELECT
            id,
            canonical_source_record_id,
            metadata
        FROM trade_flows
        WHERE
            metadata ->> 'sourceSystem'
                = 'un_comtrade'
            AND metadata ->> 'sourceExternalId'
                = %s
        FOR UPDATE
        """,
        (
            external_id,
        ),
    ).fetchall()


    if len(rows) > 1:

        stop(
            "Multiple canonical trade flows "
            "exist for one Comtrade identity."
        )


    metadata = trade_metadata(
        raw_record,
        normalized,
    )


    transport_mode = (
        canonical_transport_mode(
            raw_record.get(
                "motCode"
            )
        )
    )

    customs_procedure = (
        canonical_customs_procedure(
            raw_record.get(
                "customsCode"
            )
        )
    )


    values = (
        normalized[
            "flowDirection"
        ],

        references[
            "reporterCountryId"
        ],

        references[
            "partnerCountryId"
        ],

        references[
            "hsCodeId"
        ],

        normalized[
            "periodStart"
        ],

        normalized[
            "periodEnd"
        ],

        normalized[
            "periodType"
        ],

        normalized[
            "quantity"
        ],

        normalized[
            "quantityUnit"
        ],

        normalized[
            "netWeightKg"
        ],

        normalized[
            "grossWeightKg"
        ],

        normalized[
            "tradeValueUsd"
        ],

        normalized[
            "fobValueUsd"
        ],

        normalized[
            "cifValueUsd"
        ],

        references[
            "currencyId"
        ],

        transport_mode,

        customs_procedure,

        source_record_id,

        Jsonb(
            metadata
        ),
    )


    if not rows:

        result = connection.execute(
            """
            INSERT INTO trade_flows (
                flow_direction,
                reporter_country_id,
                partner_country_id,
                hs_code_id,
                period_start,
                period_end,
                period_type,
                quantity,
                quantity_unit,
                net_weight_kg,
                gross_weight_kg,
                trade_value,
                fob_value,
                cif_value,
                currency_id,
                transport_mode,
                customs_procedure,
                status,
                is_provisional,
                canonical_source_record_id,
                metadata
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'published',
                FALSE,
                %s,
                %s
            )
            RETURNING id
            """,
            values,
        ).fetchone()


        if result is None:

            stop(
                "Unable to insert canonical "
                "trade flow."
            )


        return (
            str(
                result[0]
            ),
            "inserted",
        )


    existing_id = str(
        rows[0][0]
    )

    existing_metadata = (
        rows[0][2]
        or {}
    )


    same_content = (
        existing_metadata.get(
            "sourceContentHash"
        )
        == normalized[
            "sourceContentHash"
        ]
    )

    same_normalizer = (
        existing_metadata.get(
            "normalizerVersion"
        )
        == NORMALIZER_VERSION
    )


    if (
        same_content
        and same_normalizer
    ):

        return (
            existing_id,
            "reused",
        )


    connection.execute(
        """
        UPDATE trade_flows
        SET
            flow_direction = %s,
            reporter_country_id = %s,
            partner_country_id = %s,
            hs_code_id = %s,
            period_start = %s,
            period_end = %s,
            period_type = %s,
            quantity = %s,
            quantity_unit = %s,
            net_weight_kg = %s,
            gross_weight_kg = %s,
            trade_value = %s,
            fob_value = %s,
            cif_value = %s,
            currency_id = %s,
            transport_mode = %s,
            customs_procedure = %s,
            status = 'published',
            is_provisional = FALSE,
            canonical_source_record_id = %s,
            metadata = %s
        WHERE id = %s
        """,
        values
        + (
            existing_id,
        ),
    )


    return (
        existing_id,
        "updated",
    )


def link_provenance(
    connection: psycopg.Connection,
    source_record_id: str,
    trade_flow_id: str,
) -> None:

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
            'trade_flow',
            %s,
            'official_reference',
            1.0000,
            %s
        )
        ON CONFLICT DO NOTHING
        """,
        (
            source_record_id,
            trade_flow_id,
            Jsonb(
                {
                    "source":
                        SOURCE_CODE,

                    "canonicalizerVersion":
                        NORMALIZER_VERSION,
                }
            ),
        ),
    )


def complete_run(
    connection: psycopg.Connection,
    ingestion_run_id: str,
    *,
    source_was_new: bool,
    trade_flow_action: str,
    trade_flow_id: str,
) -> None:

    connection.execute(
        """
        UPDATE ingestion_runs
        SET
            status =
                'completed',
            finished_at =
                NOW(),
            records_seen =
                1,
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
            1
            if source_was_new
            else 0,

            0
            if source_was_new
            else 1,

            Jsonb(
                {
                    "tradeFlowId":
                        trade_flow_id,

                    "tradeFlowAction":
                        trade_flow_action,

                    "sourceRecordAction":
                        (
                            "inserted"
                            if source_was_new
                            else "reused"
                        ),
                }
            ),

            ingestion_run_id,
        ),
    )


def mark_failed(
    connection: psycopg.Connection,
    ingestion_run_id: str,
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
                1,
            records_rejected =
                1,
            error_message =
                %s
        WHERE id = %s
        """,
        (
            str(error),
            ingestion_run_id,
        ),
    )


def verify_result(
    connection: psycopg.Connection,
    *,
    source_id: str,
    ingestion_run_id: str,
    source_record_id: str,
    trade_flow_id: str,
    external_id: str,
) -> dict[str, int | str | bool]:

    logical_trade_flows = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM trade_flows
            WHERE
                metadata ->> 'sourceSystem'
                    = 'un_comtrade'
                AND metadata ->> 'sourceExternalId'
                    = %s
            """,
            (
                external_id,
            ),
        ).fetchone()[0]
    )


    run_records = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM ingestion_run_records
            WHERE ingestion_run_id = %s
            """,
            (
                ingestion_run_id,
            ),
        ).fetchone()[0]
    )


    provenance_links = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM entity_source_links esl

            JOIN source_records sr
                ON sr.id =
                   esl.source_record_id

            WHERE
                esl.entity_type =
                    'trade_flow'
                AND esl.entity_id =
                    %s
                AND sr.data_source_id =
                    %s
            """,
            (
                trade_flow_id,
                source_id,
            ),
        ).fetchone()[0]
    )


    canonical_source = (
        connection.execute(
            """
            SELECT
                canonical_source_record_id
            FROM trade_flows
            WHERE id = %s
            """,
            (
                trade_flow_id,
            ),
        ).fetchone()
    )


    if canonical_source is None:

        stop(
            "Canonical trade flow vanished "
            "during verification."
        )


    canonical_source_record_id = str(
        canonical_source[0]
    )


    if logical_trade_flows != 1:

        stop(
            "Expected exactly one canonical "
            "trade flow for source identity."
        )


    if run_records != 1:

        stop(
            "Expected exactly one source record "
            "linked to this ingestion run."
        )


    if (
        canonical_source_record_id
        != source_record_id
    ):

        stop(
            "Canonical source-record pointer "
            "does not match current source revision."
        )


    return {
        "logicalTradeFlowCount":
            int(
                logical_trade_flows
            ),

        "runRecordCount":
            int(
                run_records
            ),

        "provenanceLinkCount":
            int(
                provenance_links
            ),

        "canonicalSourceMatches":
            True,
    }


def canonicalize_trade_observation(
    raw_record: dict[str, Any],
    normalized: dict[str, Any],
    *,
    artifact_run_id: str,
    request_url: str,
    raw_path: Path,
    parquet_paths: Sequence[Path],
) -> dict[str, Any]:

    with psycopg.connect(
        database_url()
    ) as connection:


        with connection.transaction():

            source_id = register_source(
                connection
            )

            ingestion_run_id = start_ingestion(
                connection,
                source_id,
                artifact_run_id=
                    artifact_run_id,
                request_url=
                    request_url,
                raw_path=
                    raw_path,
                parquet_paths=
                    parquet_paths,
            )


        try:

            with connection.transaction():

                (
                    source_record_id,
                    source_was_new,
                ) = preserve_source_record(
                    connection,
                    source_id,
                    ingestion_run_id,
                    raw_record,
                    normalized,
                    artifact_run_id=
                        artifact_run_id,
                    request_url=
                        request_url,
                    raw_path=
                        raw_path,
                    parquet_paths=
                        parquet_paths,
                )


                references = resolve_references(
                    connection,
                    normalized,
                )


                (
                    trade_flow_id,
                    trade_flow_action,
                ) = upsert_trade_flow(
                    connection,
                    source_record_id,
                    raw_record,
                    normalized,
                    references,
                )


                link_provenance(
                    connection,
                    source_record_id,
                    trade_flow_id,
                )


                verification = verify_result(
                    connection,
                    source_id=
                        source_id,
                    ingestion_run_id=
                        ingestion_run_id,
                    source_record_id=
                        source_record_id,
                    trade_flow_id=
                        trade_flow_id,
                    external_id=
                        normalized[
                            "sourceExternalId"
                        ],
                )


                complete_run(
                    connection,
                    ingestion_run_id,
                    source_was_new=
                        source_was_new,
                    trade_flow_action=
                        trade_flow_action,
                    trade_flow_id=
                        trade_flow_id,
                )


        except Exception as error:

            with connection.transaction():

                mark_failed(
                    connection,
                    ingestion_run_id,
                    error,
                )

            raise


        return {
            "applied":
                True,

            "dataSourceId":
                source_id,

            "ingestionRunId":
                ingestion_run_id,

            "sourceRecordId":
                source_record_id,

            "sourceRecordAction":
                (
                    "inserted"
                    if source_was_new
                    else "reused"
                ),

            "tradeFlowId":
                trade_flow_id,

            "tradeFlowAction":
                trade_flow_action,

            **verification,
        }
