from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID


SOURCE_FILE = Path(__file__).resolve()
SRC_ROOT = SOURCE_FILE.parents[1]
PROJECT_ROOT = SOURCE_FILE.parents[4]


if str(SRC_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(SRC_ROOT),
    )


import httpx
import psycopg

from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

from connectors.comtrade_canonical import (
    database_url,
)

from identity.organizations import (
    IdentityResolutionError,
    organization_identity_lock_key,
    record_source_alias,
    resolve_organization_identity,
)

from storage.manifests import (
    artifact_descriptor,
    build_manifest,
    new_run_id,
    write_json_atomic,
)

STORAGE_ROOT = (
    PROJECT_ROOT
    / "storage"
    / "imports"
    / "company_web"
)

CONNECTOR_VERSION = (
    "company_web_v2"
)

RECORD_TYPE = (
    "company_official_web_page"
)


class CompanyWebError(
    RuntimeError
):
    pass


def stop(
    message: str,
) -> None:

    raise CompanyWebError(
        message
    )


def normalize_space(
    value: str,
) -> str:

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def html_to_text(
    raw: bytes,
) -> str:

    soup = BeautifulSoup(
        raw,
        "html.parser",
    )

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "template",
        ]
    ):
        tag.decompose()

    return normalize_space(
        soup.get_text(
            " ",
            strip=True,
        )
    )


def sha256_bytes(
    raw: bytes,
) -> str:

    return hashlib.sha256(
        raw
    ).hexdigest()


def fetch_page(
    url: str,
    *,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:

    retry_statuses = {
        429,
        500,
        502,
        503,
        504,
    }

    headers = {
        "Accept":
            "text/html,application/xhtml+xml",

        "Accept-Language":
            "en-US,en;q=0.9",

        "User-Agent":
            "OriginHut/0.1 Company-Web-Connector",
    }


    for attempt in range(
        1,
        4,
    ):

        try:

            response = httpx.get(
                url,
                headers=headers,
                timeout=timeout_seconds,
                follow_redirects=True,
            )

        except httpx.HTTPError as error:

            if attempt < 3:

                time.sleep(
                    min(
                        2 ** (attempt - 1),
                        4,
                    )
                )

                continue

            raise CompanyWebError(
                "Company web transport error: "
                + type(error).__name__
                + "."
            ) from None


        if (
            response.status_code
            in retry_statuses
            and attempt < 3
        ):

            time.sleep(
                min(
                    2 ** (attempt - 1),
                    4,
                )
            )

            continue


        if (
            response.status_code < 200
            or response.status_code >= 300
        ):

            raise CompanyWebError(
                "Company web HTTP error "
                f"status={response.status_code}."
            )


        raw = response.content


        return {
            "requestedUrl":
                url,

            "finalUrl":
                str(
                    response.url
                ),

            "httpStatus":
                int(
                    response.status_code
                ),

            "contentType":
                response.headers.get(
                    "content-type",
                    ""
                ),

            "fetchedAt":
                datetime.now(
                    timezone.utc
                )
                .isoformat()
                .replace(
                    "+00:00",
                    "Z",
                ),

            "sha256":
                sha256_bytes(
                    raw
                ),

            "raw":
                raw,

            "text":
                html_to_text(
                    raw
                ),
        }


    stop(
        "Company web request failed."
    )


def string_value(
    value: Any,
    *,
    field: str,
    required: bool = False,
) -> str | None:

    if value is None:

        if required:

            stop(
                field
                + " is required."
            )

        return None


    if not isinstance(
        value,
        str,
    ):

        stop(
            field
            + " must be a string."
        )


    result = value.strip()


    if (
        required
        and not result
    ):

        stop(
            field
            + " cannot be blank."
        )


    return (
        result
        or None
    )


def country_iso2(
    value: Any,
    *,
    field: str,
) -> str:

    result = string_value(
        value,
        field=field,
        required=True,
    )

    assert result is not None


    result = result.upper()


    if (
        len(result) != 2
        or not result.isalpha()
    ):

        stop(
            field
            + " must be an ISO-2 country code."
        )


    return result


def normalize_activity_type(
    value: Any,
) -> str:

    result = string_value(
        value,
        field="activityType",
        required=True,
    )

    assert result is not None


    normalized = (
        result
        .lower()
        .replace(
            "-",
            "_",
        )
        .replace(
            " ",
            "_",
        )
    )


    if not re.fullmatch(
        r"[a-z][a-z0-9_]*",
        normalized,
    ):

        stop(
            "activityType contains unsupported characters."
        )


    return normalized


def normalize_hs_code(
    value: Any,
) -> str:

    result = string_value(
        value,
        field="hsCode",
        required=True,
    )

    assert result is not None


    if not re.fullmatch(
        r"\d{2,6}",
        result,
    ):

        stop(
            "hsCode must contain 2 to 6 digits."
        )


    return result


def product_id_value(
    value: Any,
) -> str | None:

    if value is None:
        return None


    result = string_value(
        value,
        field="productId",
        required=True,
    )

    assert result is not None


    try:

        return str(
            UUID(
                result
            )
        )

    except ValueError:

        stop(
            "productId must be a valid UUID."
        )


def confidence_value(
    value: Any,
) -> float | None:

    if value is None:
        return None


    try:

        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as error:

        raise CompanyWebError(
            "confidence must be numeric."
        ) from error


    if (
        result < 0
        or result > 1
    ):

        stop(
            "confidence must be between 0 and 1."
        )


    return result


def normalize_term_list(
    value: Any,
    *,
    field: str,
) -> list[str]:

    if value is None:
        return []


    if not isinstance(
        value,
        list,
    ):

        stop(
            field
            + " must be an array."
        )


    result: list[str] = []


    for item in value:

        term = string_value(
            item,
            field=field,
            required=True,
        )

        assert term is not None

        result.append(
            normalize_space(
                term
            )
        )


    return result


def validate_config(
    payload: Any,
) -> dict[str, Any]:

    if not isinstance(
        payload,
        dict,
    ):

        stop(
            "Config root must be an object."
        )


    raw_sources = payload.get(
        "sources"
    )


    if not isinstance(
        raw_sources,
        list,
    ):

        stop(
            "sources must be an array."
        )


    if not raw_sources:

        stop(
            "sources cannot be empty."
        )


    sources: list[
        dict[str, Any]
    ] = []


    seen_codes: set[str] = set()


    for index, raw_source in enumerate(
        raw_sources
    ):

        if not isinstance(
            raw_source,
            dict,
        ):

            stop(
                f"sources[{index}] must be an object."
            )


        code = string_value(
            raw_source.get(
                "code"
            ),
            field=f"sources[{index}].code",
            required=True,
        )

        assert code is not None


        if not re.fullmatch(
            r"[a-z0-9][a-z0-9_]*",
            code,
        ):

            stop(
                "source code must contain lowercase "
                "letters, numbers and underscores."
            )


        if code in seen_codes:

            stop(
                "Duplicate source code: "
                + code
            )


        seen_codes.add(
            code
        )


        url = string_value(
            raw_source.get(
                "url"
            ),
            field=f"sources[{index}].url",
            required=True,
        )

        assert url is not None


        if not (
            url.startswith(
                "https://"
            )
            or url.startswith(
                "http://"
            )
        ):

            stop(
                "Company web URLs must be HTTP or HTTPS."
            )


        organization = raw_source.get(
            "organization"
        )


        if not isinstance(
            organization,
            dict,
        ):

            stop(
                f"sources[{index}].organization "
                "must be an object."
            )


        roles = normalize_term_list(
            organization.get(
                "roles"
            ),
            field=(
                f"sources[{index}]"
                ".organization.roles"
            ),
        )


        activities_raw = raw_source.get(
            "activities"
        )


        if not isinstance(
            activities_raw,
            list,
        ):

            stop(
                f"sources[{index}].activities "
                "must be an array."
            )


        if not activities_raw:

            stop(
                f"sources[{index}].activities "
                "cannot be empty."
            )


        activities: list[
            dict[str, Any]
        ] = []


        for activity_index, raw_activity in enumerate(
            activities_raw
        ):

            if not isinstance(
                raw_activity,
                dict,
            ):

                stop(
                    "activity must be an object."
                )


            activities.append(
                {
                    "activityType":
                        normalize_activity_type(
                            raw_activity.get(
                                "activityType"
                            )
                        ),

                    "hsCode":
                        normalize_hs_code(
                            raw_activity.get(
                                "hsCode"
                            )
                        ),

                    "productId":
                        product_id_value(
                            raw_activity.get(
                                "productId"
                            )
                        ),

                    "hsNomenclature":
                        (
                            string_value(
                                raw_activity.get(
                                    "hsNomenclature"
                                ),
                                field="hsNomenclature",
                            )
                            or "HS2022"
                        ).upper(),

                    "marketCountryIso2":
                        country_iso2(
                            raw_activity.get(
                                "marketCountryIso2"
                            ),
                            field=(
                                "marketCountryIso2"
                            ),
                        ),

                    "confidence":
                        confidence_value(
                            raw_activity.get(
                                "confidence"
                            )
                        ),

                    "allTerms":
                        normalize_term_list(
                            raw_activity.get(
                                "allTerms"
                            ),
                            field="allTerms",
                        ),

                    "anyTerms":
                        normalize_term_list(
                            raw_activity.get(
                                "anyTerms"
                            ),
                            field="anyTerms",
                        ),

                    "sourceClaim":
                        string_value(
                            raw_activity.get(
                                "sourceClaim"
                            ),
                            field="sourceClaim",
                        ),
                }
            )


        sources.append(
            {
                "code":
                    code,

                "name":
                    string_value(
                        raw_source.get(
                            "name"
                        ),
                        field="name",
                        required=True,
                    ),

                "provider":
                    string_value(
                        raw_source.get(
                            "provider"
                        ),
                        field="provider",
                        required=True,
                    ),

                "url":
                    url,

                "official":
                    bool(
                        raw_source.get(
                            "official",
                            False,
                        )
                    ),

                "organization":
                    {
                        "legalName":
                            string_value(
                                organization.get(
                                    "legalName"
                                ),
                                field="legalName",
                                required=True,
                            ),

                        "tradingName":
                            string_value(
                                organization.get(
                                    "tradingName"
                                ),
                                field="tradingName",
                            ),

                        "countryIso2":
                            country_iso2(
                                organization.get(
                                    "countryIso2"
                                ),
                                field="countryIso2",
                            ),

                        "registrationNumber":
                            string_value(
                                organization.get(
                                    "registrationNumber"
                                ),
                                field="registrationNumber",
                            ),

                        "lei":
                            string_value(
                                organization.get(
                                    "lei"
                                ),
                                field="lei",
                            ),

                        "taxIdentifier":
                            string_value(
                                organization.get(
                                    "taxIdentifier"
                                ),
                                field="taxIdentifier",
                            ),

                        "website":
                            (
                                string_value(
                                    organization.get(
                                        "website"
                                    ),
                                    field="website",
                                )
                                or url
                            ),

                        "roles":
                            sorted(
                                {
                                    role
                                    .lower()
                                    .replace(
                                        "-",
                                        "_",
                                    )
                                    .replace(
                                        " ",
                                        "_",
                                    )
                                    for role
                                    in roles
                                }
                            ),
                    },

                "activities":
                    activities,
            }
        )


    return {
        "sources":
            sources,
    }


def load_config(
    path: str | Path,
) -> dict[str, Any]:

    source = Path(
        path
    )


    try:

        payload = json.loads(
            source.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:

        raise CompanyWebError(
            "Unable to load company-web config: "
            + str(error)
        ) from error


    return validate_config(
        payload
    )


def evidence_result(
    text: str,
    activity: dict[str, Any],
) -> dict[str, Any]:

    normalized_text = (
        normalize_space(
            text
        )
        .casefold()
    )


    all_terms = [
        term.casefold()
        for term
        in activity[
            "allTerms"
        ]
    ]

    any_terms = [
        term.casefold()
        for term
        in activity[
            "anyTerms"
        ]
    ]


    missing_all = [
        term
        for term
        in all_terms
        if term
        not in normalized_text
    ]


    any_matches = [
        term
        for term
        in any_terms
        if term
        in normalized_text
    ]


    passed = (
        not missing_all
        and (
            not any_terms
            or bool(
                any_matches
            )
        )
    )


    return {
        "passed":
            passed,

        "requiredAll":
            all_terms,

        "missingAll":
            missing_all,

        "requiredAny":
            any_terms,

        "matchedAny":
            any_matches,
    }


def validate_source_evidence(
    source: dict[str, Any],
    fetched: dict[str, Any],
) -> list[
    dict[str, Any]
]:

    results: list[
        dict[str, Any]
    ] = []


    for activity in source[
        "activities"
    ]:

        result = evidence_result(
            fetched[
                "text"
            ],
            activity,
        )


        if not result[
            "passed"
        ]:

            stop(
                "Evidence requirements failed "
                f"for source={source['code']} "
                "activity="
                + activity[
                    "activityType"
                ]
                + "."
            )


        results.append(
            {
                "activityType":
                    activity[
                        "activityType"
                    ],

                "hsCode":
                    activity[
                        "hsCode"
                    ],

                "productId":
                    activity.get(
                        "productId"
                    ),

                **result,
            }
        )


    return results


def write_artifacts(
    source: dict[str, Any],
    fetched: dict[str, Any],
    evidence: list[
        dict[str, Any]
    ],
    *,
    run_id: str,
) -> dict[str, Path]:

    source_root = (
        STORAGE_ROOT
        / source[
            "code"
        ]
        / run_id
    )

    source_root.mkdir(
        parents=True,
        exist_ok=True,
    )


    raw_path = (
        source_root
        / "page.html"
    )

    raw_path.write_bytes(
        fetched[
            "raw"
        ]
    )


    manifest_path = (
        source_root
        / "manifest.json"
    )


    manifest = build_manifest(
        source_code=
            source[
                "code"
            ],

        run_id=
            run_id,

        request={
            "url":
                source[
                    "url"
                ],

            "finalUrl":
                fetched[
                    "finalUrl"
                ],

            "httpStatus":
                fetched[
                    "httpStatus"
                ],
        },

        raw_artifacts=[
            artifact_descriptor(
                raw_path,
                root=PROJECT_ROOT,
            )
        ],

        parquet_artifacts=[],

        record_count=1,

        schema_version=
            CONNECTOR_VERSION,

        metadata={
            "connectorVersion":
                CONNECTOR_VERSION,

            "organizationLegalName":
                source[
                    "organization"
                ][
                    "legalName"
                ],

            "evidenceChecks":
                evidence,
        },
    )


    write_json_atomic(
        manifest_path,
        manifest,
    )


    return {
        "raw":
            raw_path,

        "manifest":
            manifest_path,
    }


def relative_project_path(
    path: Path,
) -> str:

    try:

        return (
            path.resolve()
            .relative_to(
                PROJECT_ROOT.resolve()
            )
            .as_posix()
        )

    except ValueError:

        return str(
            path.resolve()
        )


def resolve_country(
    connection: psycopg.Connection,
    iso2: str,
) -> str:

    rows = connection.execute(
        """
        SELECT id
        FROM countries
        WHERE
            iso2 = %s
            AND is_active = TRUE
        """,
        (
            iso2,
        ),
    ).fetchall()


    if len(rows) != 1:

        stop(
            "Country ISO2 did not resolve uniquely: "
            + iso2
        )


    return str(
        rows[0][0]
    )


def resolve_hs_code(
    connection: psycopg.Connection,
    nomenclature: str,
    code: str,
) -> str:

    rows = connection.execute(
        """
        SELECT id
        FROM hs_codes
        WHERE
            nomenclature = %s
            AND code = %s
        """,
        (
            nomenclature,
            code,
        ),
    ).fetchall()


    if len(rows) != 1:

        stop(
            "HS code did not resolve uniquely: "
            + nomenclature
            + " "
            + code
        )


    return str(
        rows[0][0]
    )


def resolve_product_scope(
    connection: psycopg.Connection,
    product_id: str | None,
    hs_code_id: str,
) -> str | None:

    if product_id is None:
        return None


    row = connection.execute(
        """
        SELECT p.id
        FROM products p
        WHERE
            p.id = %s
            AND p.is_active = TRUE
        """,
        (
            product_id,
        ),
    ).fetchone()


    if row is None:

        stop(
            "Configured productId does not resolve "
            "to an active Origin Hut product: "
            + product_id
        )


    classification = connection.execute(
        """
        SELECT 1
        FROM product_hs_classifications
        WHERE
            product_id = %s
            AND hs_code_id = %s
        LIMIT 1
        """,
        (
            product_id,
            hs_code_id,
        ),
    ).fetchone()


    if classification is None:

        stop(
            "Configured productId is not classified "
            "to the configured HS code."
        )


    return str(
        row[0]
    )


def register_source(
    connection: psycopg.Connection,
    source: dict[str, Any],
) -> str:

    row = connection.execute(
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
            'company_intelligence',
            'public_web',
            %s,
            %s,
            'provider_defined',
            %s,
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
            is_official =
                EXCLUDED.is_official,
            is_active =
                TRUE,
            metadata =
                EXCLUDED.metadata,
            updated_at =
                NOW()
        RETURNING id
        """,
        (
            source[
                "code"
            ],

            source[
                "name"
            ],

            source[
                "provider"
            ],

            source[
                "url"
            ],

            source[
                "provider"
            ],

            source[
                "official"
            ],

            Jsonb(
                {
                    "connectorVersion":
                        CONNECTOR_VERSION,

                    "sourceSemantics":
                        "company_web_evidence",
                }
            ),
        ),
    ).fetchone()


    if row is None:

        stop(
            "Unable to register company-web data source."
        )


    return str(
        row[0]
    )


def start_ingestion(
    connection: psycopg.Connection,
    source_id: str,
    source: dict[str, Any],
    fetched: dict[str, Any],
    artifacts: dict[str, Path],
    *,
    run_id: str,
) -> str:

    row = connection.execute(
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
                        run_id,

                    "requestedUrl":
                        source[
                            "url"
                        ],

                    "finalUrl":
                        fetched[
                            "finalUrl"
                        ],

                    "rawArtifact":
                        relative_project_path(
                            artifacts[
                                "raw"
                            ]
                        ),

                    "manifestArtifact":
                        relative_project_path(
                            artifacts[
                                "manifest"
                            ]
                        ),

                    "connectorVersion":
                        CONNECTOR_VERSION,
                }
            ),
        ),
    ).fetchone()


    if row is None:

        stop(
            "Unable to create company-web ingestion run."
        )


    return str(
        row[0]
    )


def preserve_source_record(
    connection: psycopg.Connection,
    source_id: str,
    ingestion_run_id: str,
    source: dict[str, Any],
    fetched: dict[str, Any],
    evidence: list[
        dict[str, Any]
    ],
    artifacts: dict[str, Path],
) -> tuple[
    str,
    bool,
]:

    row = connection.execute(
        """
        INSERT INTO source_records (
            data_source_id,
            ingestion_run_id,
            external_id,
            record_type,
            source_timestamp,
            fetched_at,
            content_hash,
            payload,
            metadata
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            NULL,
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
            fetched[
                "finalUrl"
            ],
            RECORD_TYPE,
            datetime.fromisoformat(
                fetched[
                    "fetchedAt"
                ].replace(
                    "Z",
                    "+00:00",
                )
            ),
            fetched[
                "sha256"
            ],

            Jsonb(
                {
                    "requestedUrl":
                        fetched[
                            "requestedUrl"
                        ],

                    "finalUrl":
                        fetched[
                            "finalUrl"
                        ],

                    "httpStatus":
                        fetched[
                            "httpStatus"
                        ],

                    "contentType":
                        fetched[
                            "contentType"
                        ],

                    "text":
                        fetched[
                            "text"
                        ],

                    "sha256":
                        fetched[
                            "sha256"
                        ],
                }
            ),

            Jsonb(
                {
                    "connectorVersion":
                        CONNECTOR_VERSION,

                    "rawArtifact":
                        relative_project_path(
                            artifacts[
                                "raw"
                            ]
                        ),

                    "manifestArtifact":
                        relative_project_path(
                            artifacts[
                                "manifest"
                            ]
                        ),

                    "evidenceChecks":
                        evidence,
                }
            ),
        ),
    ).fetchone()


    was_new = (
        row is not None
    )


    if row is None:

        row = connection.execute(
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
                fetched[
                    "finalUrl"
                ],
                fetched[
                    "sha256"
                ],
            ),
        ).fetchone()


    if row is None:

        stop(
            "Unable to resolve immutable company-web source record."
        )


    source_record_id = str(
        row[0]
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


def resolve_or_create_organization(
    connection: psycopg.Connection,
    source: dict[str, Any],
    source_record_id: str,
) -> tuple[
    str,
    str,
    str,
]:

    organization = source[
        "organization"
    ]

    country_id = resolve_country(
        connection,
        organization[
            "countryIso2"
        ],
    )


    lock_identity = (
        organization_identity_lock_key(
            connection,
            organization,
            country_id,
        )
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


    try:

        resolution = resolve_organization_identity(
            connection,
            organization,
            country_id,
        )

    except IdentityResolutionError as error:

        raise CompanyWebError(
            str(
                error
            )
        ) from None


    if resolution.organization_id:

        organization_id = (
            resolution.organization_id
        )

        connection.execute(
            """
            UPDATE organizations
            SET
                trading_name =
                    COALESCE(
                        trading_name,
                        %s
                    ),
                website =
                    COALESCE(
                        website,
                        %s
                    ),
                registration_number =
                    COALESCE(
                        registration_number,
                        %s
                    ),
                lei =
                    COALESCE(
                        lei,
                        %s
                    ),
                tax_identifier =
                    COALESCE(
                        tax_identifier,
                        %s
                    ),
                status = 'active',
                metadata =
                    metadata
                    || %s
            WHERE id = %s
            """,
            (
                organization[
                    "tradingName"
                ],
                organization[
                    "website"
                ],
                organization[
                    "registrationNumber"
                ],
                organization[
                    "lei"
                ],
                organization[
                    "taxIdentifier"
                ],
                Jsonb(
                    {
                        "companyWebSourceCode":
                            source[
                                "code"
                            ],

                        "companyWebConnectorVersion":
                            CONNECTOR_VERSION,

                        "identityResolutionMethod":
                            resolution.method,

                        "supportingDomainCandidates":
                            list(
                                resolution
                                .supporting_domain_candidates
                            ),
                    }
                ),
                organization_id,
            ),
        )

        organization_action = (
            "reused"
        )

        resolution_method = (
            resolution.method
        )

    else:

        row = connection.execute(
            """
            INSERT INTO organizations (
                legal_name,
                trading_name,
                country_id,
                registration_number,
                lei,
                tax_identifier,
                website,
                status,
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
                'active',
                %s
            )
            RETURNING id
            """,
            (
                organization[
                    "legalName"
                ],
                organization[
                    "tradingName"
                ],
                country_id,
                organization[
                    "registrationNumber"
                ],
                organization[
                    "lei"
                ],
                organization[
                    "taxIdentifier"
                ],
                organization[
                    "website"
                ],
                Jsonb(
                    {
                        "companyWebSourceCode":
                            source[
                                "code"
                            ],

                        "companyWebConnectorVersion":
                            CONNECTOR_VERSION,

                        "identityResolutionMethod":
                            "created",

                        "supportingDomainCandidates":
                            list(
                                resolution
                                .supporting_domain_candidates
                            ),
                    }
                ),
            ),
        ).fetchone()


        if row is None:

            stop(
                "Unable to create organization."
            )


        organization_id = str(
            row[0]
        )

        organization_action = (
            "inserted"
        )

        resolution_method = (
            "created"
        )


    for role in organization[
        "roles"
    ]:

        connection.execute(
            """
            INSERT INTO organization_roles (
                organization_id,
                role_code
            )
            VALUES (
                %s,
                %s
            )
            ON CONFLICT DO NOTHING
            """,
            (
                organization_id,
                role,
            ),
        )


    for source_name in (
        organization[
            "legalName"
        ],
        organization[
            "tradingName"
        ],
    ):

        if not source_name:
            continue


        try:

            record_source_alias(
                connection,
                organization_id=
                    organization_id,
                alias=
                    source_name,
                source_record_id=
                    source_record_id,
                source_code=
                    source[
                        "code"
                    ],
            )

        except IdentityResolutionError as error:

            raise CompanyWebError(
                str(
                    error
                )
            ) from None


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
            'organization',
            %s,
            'official_reference',
            1.0000,
            %s
        )
        ON CONFLICT DO NOTHING
        """,
        (
            source_record_id,
            organization_id,
            Jsonb(
                {
                    "sourceCode":
                        source[
                            "code"
                        ],

                    "identityResolutionMethod":
                        resolution_method,
                }
            ),
        ),
    )


    return (
        organization_id,
        organization_action,
        resolution_method,
    )


def upsert_activity(
    connection: psycopg.Connection,
    source: dict[str, Any],
    organization_id: str,
    source_record_id: str,
    activity: dict[str, Any],
    evidence: dict[str, Any],
) -> tuple[
    str,
    str,
]:

    hs_code_id = resolve_hs_code(
        connection,
        activity[
            "hsNomenclature"
        ],
        activity[
            "hsCode"
        ],
    )

    product_id = resolve_product_scope(
        connection,
        activity.get(
            "productId"
        ),
        hs_code_id,
    )


    market_country_id = resolve_country(
        connection,
        activity[
            "marketCountryIso2"
        ],
    )


    identity = (
        "company_web_activity:"
        + organization_id
        + ":"
        + activity[
            "activityType"
        ]
        + ":"
        + (
            product_id
            or "no_product"
        )
        + ":"
        + hs_code_id
        + ":"
        + market_country_id
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
            identity,
        ),
    )


    rows = connection.execute(
        """
        SELECT id
        FROM organization_trade_activities
        WHERE
            organization_id = %s
            AND activity_type = %s
            AND product_id
                IS NOT DISTINCT FROM %s::uuid
            AND hs_code_id = %s
            AND market_country_id = %s
            AND status = 'active'
            AND valid_to IS NULL
        FOR UPDATE
        """,
        (
            organization_id,
            activity[
                "activityType"
            ],
            product_id,
            hs_code_id,
            market_country_id,
        ),
    ).fetchall()


    if len(rows) > 1:

        stop(
            "Multiple active canonical organization "
            "trade activities exist for one identity."
        )


    metadata = {
        "companyWebSourceCode":
            source[
                "code"
            ],

        "subject":
            (
                "product_hs"
                if product_id
                else "hs_code"
            ),

        "productId":
            product_id,

        "sourceClaim":
            activity[
                "sourceClaim"
            ],

        "evidence":
            evidence,

        "connectorVersion":
            CONNECTOR_VERSION,
    }


    if rows:

        activity_id = str(
            rows[0][0]
        )

        connection.execute(
            """
            UPDATE organization_trade_activities
            SET
                confidence =
                    COALESCE(
                        %s,
                        confidence
                    ),
                source_type =
                    'official_company_website',
                canonical_source_record_id =
                    %s,
                metadata = %s
            WHERE id = %s
            """,
            (
                activity[
                    "confidence"
                ],
                source_record_id,
                Jsonb(
                    metadata
                ),
                activity_id,
            ),
        )

        activity_action = (
            "updated"
        )

    else:

        row = connection.execute(
            """
            INSERT INTO organization_trade_activities (
                organization_id,
                activity_type,
                product_id,
                hs_code_id,
                market_country_id,
                status,
                confidence,
                source_type,
                canonical_source_record_id,
                metadata
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                'active',
                %s,
                'official_company_website',
                %s,
                %s
            )
            RETURNING id
            """,
            (
                organization_id,
                activity[
                    "activityType"
                ],
                product_id,
                hs_code_id,
                market_country_id,
                activity[
                    "confidence"
                ],
                source_record_id,
                Jsonb(
                    metadata
                ),
            ),
        ).fetchone()


        if row is None:

            stop(
                "Unable to create organization trade activity."
            )


        activity_id = str(
            row[0]
        )

        activity_action = (
            "inserted"
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
            'organization_trade_activity',
            %s,
            'official_reference',
            %s,
            %s
        )
        ON CONFLICT DO NOTHING
        """,
        (
            source_record_id,
            activity_id,
            activity[
                "confidence"
            ],
            Jsonb(
                {
                    "sourceCode":
                        source[
                            "code"
                        ],
                }
            ),
        ),
    )


    return (
        activity_id,
        activity_action,
    )


def finish_ingestion(
    connection: psycopg.Connection,
    ingestion_run_id: str,
    *,
    source_record_new: bool,
    activity_count: int,
) -> None:

    connection.execute(
        """
        UPDATE ingestion_runs
        SET
            status = 'completed',
            finished_at = NOW(),
            records_seen = 1,
            records_inserted = %s,
            records_updated = %s,
            metadata =
                metadata
                || %s
        WHERE id = %s
        """,
        (
            (
                1
                if source_record_new
                else 0
            ),
            (
                0
                if source_record_new
                else 1
            ),
            Jsonb(
                {
                    "activityCount":
                        activity_count,
                }
            ),
            ingestion_run_id,
        ),
    )


def apply_source(
    connection: psycopg.Connection,
    source: dict[str, Any],
    fetched: dict[str, Any],
    evidence_results: list[
        dict[str, Any]
    ],
    artifacts: dict[str, Path],
    *,
    run_id: str,
) -> dict[str, Any]:

    source_id = register_source(
        connection,
        source,
    )


    ingestion_run_id = start_ingestion(
        connection,
        source_id,
        source,
        fetched,
        artifacts,
        run_id=run_id,
    )


    (
        source_record_id,
        source_record_new,
    ) = preserve_source_record(
        connection,
        source_id,
        ingestion_run_id,
        source,
        fetched,
        evidence_results,
        artifacts,
    )


    (
        organization_id,
        organization_action,
        organization_resolution_method,
    ) = resolve_or_create_organization(
        connection,
        source,
        source_record_id,
    )


    activity_results: list[
        dict[str, Any]
    ] = []


    for activity, evidence in zip(
        source[
            "activities"
        ],
        evidence_results,
        strict=True,
    ):

        (
            activity_id,
            activity_action,
        ) = upsert_activity(
            connection,
            source,
            organization_id,
            source_record_id,
            activity,
            evidence,
        )


        activity_results.append(
            {
                "id":
                    activity_id,

                "activityType":
                    activity[
                        "activityType"
                    ],

                "productId":
                    activity.get(
                        "productId"
                    ),

                "hsCode":
                    activity[
                        "hsCode"
                    ],

                "action":
                    activity_action,
            }
        )


    finish_ingestion(
        connection,
        ingestion_run_id,
        source_record_new=
            source_record_new,
        activity_count=
            len(
                activity_results
            ),
    )


    return {
        "sourceCode":
            source[
                "code"
            ],

        "sourceRecordId":
            source_record_id,

        "sourceRecordAction":
            (
                "inserted"
                if source_record_new
                else "reused"
            ),

        "organizationId":
            organization_id,

        "organizationAction":
            organization_action,

        "organizationResolutionMethod":
            organization_resolution_method,

        "activities":
            activity_results,

        "ingestionRunId":
            ingestion_run_id,
    }


def execute_source(
    source: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:

    run_id = new_run_id()

    fetched = fetch_page(
        source[
            "url"
        ]
    )

    evidence = validate_source_evidence(
        source,
        fetched,
    )

    artifacts = write_artifacts(
        source,
        fetched,
        evidence,
        run_id=run_id,
    )


    result: dict[str, Any] = {
        "sourceCode":
            source[
                "code"
            ],

        "runId":
            run_id,

        "requestedUrl":
            source[
                "url"
            ],

        "finalUrl":
            fetched[
                "finalUrl"
            ],

        "httpStatus":
            fetched[
                "httpStatus"
            ],

        "sha256":
            fetched[
                "sha256"
            ],

        "evidence":
            evidence,

        "rawArtifact":
            relative_project_path(
                artifacts[
                    "raw"
                ]
            ),

        "manifestArtifact":
            relative_project_path(
                artifacts[
                    "manifest"
                ]
            ),

        "applied":
            apply,
    }


    if not apply:

        return result


    with psycopg.connect(
        database_url()
    ) as connection:

        with connection.transaction():

            applied = apply_source(
                connection,
                source,
                fetched,
                evidence,
                artifacts,
                run_id=run_id,
            )


    result[
        "canonical"
    ] = applied


    return result


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Origin Hut company-web intelligence connector."
        )
    )


    parser.add_argument(
        "--config",
        required=True,
        help=(
            "Path to company-web source configuration JSON."
        ),
    )


    parser.add_argument(
        "--source-code",
        action="append",
        default=[],
        help=(
            "Optional source code filter. "
            "May be supplied more than once."
        ),
    )


    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist source provenance, organization "
            "and organization trade activity to PostgreSQL."
        ),
    )


    return parser.parse_args()


def main() -> int:

    args = parse_args()

    config = load_config(
        args.config
    )


    requested = {
        code.strip()
        for code
        in args.source_code
        if code.strip()
    }


    sources = [
        source
        for source
        in config[
            "sources"
        ]
        if (
            not requested
            or source[
                "code"
            ]
            in requested
        )
    ]


    if requested:

        resolved = {
            source[
                "code"
            ]
            for source
            in sources
        }

        missing = (
            requested
            - resolved
        )


        if missing:

            stop(
                "Unknown requested source code(s): "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )


    results = [
        execute_source(
            source,
            apply=args.apply,
        )
        for source
        in sources
    ]


    print(
        json.dumps(
            {
                "ok":
                    True,

                "connectorVersion":
                    CONNECTOR_VERSION,

                "sourceCount":
                    len(
                        results
                    ),

                "applied":
                    args.apply,

                "results":
                    results,
            },
            indent=2,
            sort_keys=True,
        )
    )


    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
