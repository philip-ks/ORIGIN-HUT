from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import psycopg
from psycopg.types.json import Jsonb


class IdentityResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class OrganizationIdentityResolution:
    organization_id: str | None
    method: str
    matched_value: str | None = None
    supporting_domain_candidates: tuple[str, ...] = ()


def stop(message: str) -> None:
    raise IdentityResolutionError(message)


def normalize_domain(value: str | None) -> str | None:
    if value is None:
        return None

    text = value.strip()
    if not text:
        return None

    candidate = text if "://" in text else "https://" + text

    try:
        parts = urlsplit(candidate)
    except ValueError:
        return None

    hostname = (parts.hostname or "").strip().lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    hostname = hostname.rstrip(".")
    return hostname or None


def normalize_organization_name(
    connection: psycopg.Connection,
    value: str,
) -> str:
    row = connection.execute(
        """
        SELECT originhut_normalize_organization_name(%s)
        """,
        (value,),
    ).fetchone()

    if row is None or row[0] is None or not str(row[0]).strip():
        stop("Organization name could not be normalized.")

    return str(row[0])


def _single_match(
    rows: list[tuple[Any, ...]],
    *,
    label: str,
) -> str | None:
    values = {str(row[0]) for row in rows}

    if len(values) > 1:
        stop("Ambiguous organization identity for " + label + ".")

    return next(iter(values)) if values else None


def _lei_match(
    connection: psycopg.Connection,
    value: str,
) -> str | None:
    rows = connection.execute(
        """
        SELECT id
        FROM organizations
        WHERE
            lei IS NOT NULL
            AND UPPER(BTRIM(lei)) =
                UPPER(BTRIM(%s))
        """,
        (value,),
    ).fetchall()

    return _single_match(rows, label="LEI")


def _jurisdiction_identifier_match(
    connection: psycopg.Connection,
    *,
    country_id: str,
    column: str,
    value: str,
    label: str,
) -> str | None:
    allowed = {
        "registration_number",
        "tax_identifier",
    }

    if column not in allowed:
        stop("Unsupported organization identifier column.")

    rows = connection.execute(
        f"""
        SELECT id
        FROM organizations
        WHERE
            country_id = %s
            AND {column} IS NOT NULL
            AND UPPER(BTRIM({column})) =
                UPPER(BTRIM(%s))
        """,
        (country_id, value),
    ).fetchall()

    return _single_match(rows, label=label)


def _normalized_identifier(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text.upper() if text else None


def _candidate_identity(
    connection: psycopg.Connection,
    organization_id: str,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            id,
            lei,
            registration_number,
            tax_identifier,
            website
        FROM organizations
        WHERE id = %s
        """,
        (organization_id,),
    ).fetchone()

    if row is None:
        stop("Resolved organization no longer exists.")

    return {
        "id": str(row[0]),
        "lei": row[1],
        "registrationNumber": row[2],
        "taxIdentifier": row[3],
        "website": row[4],
    }


def _assert_identifier_compatibility(
    connection: psycopg.Connection,
    organization_id: str,
    organization: dict[str, Any],
) -> None:
    existing = _candidate_identity(connection, organization_id)

    pairs = [
        ("LEI", existing["lei"], organization.get("lei")),
        (
            "registration number",
            existing["registrationNumber"],
            organization.get("registrationNumber"),
        ),
        (
            "tax identifier",
            existing["taxIdentifier"],
            organization.get("taxIdentifier"),
        ),
    ]

    for label, old_value, new_value in pairs:
        old_normalized = _normalized_identifier(old_value)
        new_normalized = _normalized_identifier(new_value)

        if (
            old_normalized
            and new_normalized
            and old_normalized != new_normalized
        ):
            stop(
                "Organization identity conflict: "
                + label
                + " differs from the matched canonical organization."
            )


def _alias_match(
    connection: psycopg.Connection,
    *,
    country_id: str,
    normalized_alias: str,
) -> str | None:
    rows = connection.execute(
        """
        SELECT DISTINCT oa.organization_id
        FROM organization_aliases oa
        JOIN organizations o
          ON o.id = oa.organization_id
        WHERE
            o.country_id = %s
            AND oa.is_active = TRUE
            AND oa.normalized_alias = %s
        """,
        (country_id, normalized_alias),
    ).fetchall()

    return _single_match(
        rows,
        label="alias " + normalized_alias,
    )


def _supporting_domain_candidates(
    connection: psycopg.Connection,
    *,
    country_id: str,
    website: str | None,
) -> tuple[str, ...]:
    incoming_domain = normalize_domain(website)
    if incoming_domain is None:
        return ()

    rows = connection.execute(
        """
        SELECT id, website
        FROM organizations
        WHERE
            country_id = %s
            AND website IS NOT NULL
        """,
        (country_id,),
    ).fetchall()

    matches = {
        str(row[0])
        for row in rows
        if normalize_domain(row[1]) == incoming_domain
    }

    return tuple(sorted(matches))


def resolve_organization_identity(
    connection: psycopg.Connection,
    organization: dict[str, Any],
    country_id: str,
) -> OrganizationIdentityResolution:
    strong_matches: list[tuple[str, str, str]] = []

    lei = organization.get("lei")
    if lei:
        matched = _lei_match(connection, str(lei))
        if matched:
            strong_matches.append(("lei", matched, str(lei)))

    registration_number = organization.get("registrationNumber")
    if registration_number:
        matched = _jurisdiction_identifier_match(
            connection,
            country_id=country_id,
            column="registration_number",
            value=str(registration_number),
            label="registration number",
        )
        if matched:
            strong_matches.append(
                (
                    "registration_number",
                    matched,
                    str(registration_number),
                )
            )

    tax_identifier = organization.get("taxIdentifier")
    if tax_identifier:
        matched = _jurisdiction_identifier_match(
            connection,
            country_id=country_id,
            column="tax_identifier",
            value=str(tax_identifier),
            label="tax identifier",
        )
        if matched:
            strong_matches.append(
                (
                    "tax_identifier",
                    matched,
                    str(tax_identifier),
                )
            )

    if strong_matches:
        organization_ids = {item[1] for item in strong_matches}

        if len(organization_ids) != 1:
            stop(
                "Conflicting strong organization identifiers "
                "resolve to different canonical organizations."
            )

        organization_id = next(iter(organization_ids))

        _assert_identifier_compatibility(
            connection,
            organization_id,
            organization,
        )

        method = (
            strong_matches[0][0]
            if len(strong_matches) == 1
            else "strong_identifiers"
        )

        matched_value = (
            strong_matches[0][2]
            if len(strong_matches) == 1
            else None
        )

        return OrganizationIdentityResolution(
            organization_id=organization_id,
            method=method,
            matched_value=matched_value,
        )

    incoming_names: list[tuple[str, str]] = []

    for field_name in ("legalName", "tradingName"):
        value = organization.get(field_name)
        if not value:
            continue

        incoming_names.append(
            (
                field_name,
                normalize_organization_name(
                    connection,
                    str(value),
                ),
            )
        )

    alias_matches: list[tuple[str, str, str]] = []

    for field_name, normalized in incoming_names:
        matched = _alias_match(
            connection,
            country_id=country_id,
            normalized_alias=normalized,
        )
        if matched:
            alias_matches.append(
                (
                    field_name,
                    matched,
                    normalized,
                )
            )

    if alias_matches:
        organization_ids = {item[1] for item in alias_matches}

        if len(organization_ids) != 1:
            stop(
                "Incoming organization names resolve to "
                "different canonical organizations."
            )

        organization_id = next(iter(organization_ids))

        _assert_identifier_compatibility(
            connection,
            organization_id,
            organization,
        )

        return OrganizationIdentityResolution(
            organization_id=organization_id,
            method="alias",
            matched_value=alias_matches[0][2],
        )

    domain_candidates = _supporting_domain_candidates(
        connection,
        country_id=country_id,
        website=organization.get("website"),
    )

    return OrganizationIdentityResolution(
        organization_id=None,
        method="none",
        supporting_domain_candidates=domain_candidates,
    )


def organization_identity_lock_key(
    connection: psycopg.Connection,
    organization: dict[str, Any],
    country_id: str,
) -> str:
    lei = _normalized_identifier(organization.get("lei"))
    if lei:
        return "organization:lei:" + lei

    registration = _normalized_identifier(
        organization.get("registrationNumber")
    )
    if registration:
        return (
            "organization:registration:"
            + country_id
            + ":"
            + registration
        )

    tax_identifier = _normalized_identifier(
        organization.get("taxIdentifier")
    )
    if tax_identifier:
        return (
            "organization:tax:"
            + country_id
            + ":"
            + tax_identifier
        )

    legal_name = organization.get("legalName")
    if not legal_name:
        stop(
            "Organization legal name is required "
            "for identity locking."
        )

    return (
        "organization:name:"
        + country_id
        + ":"
        + normalize_organization_name(
            connection,
            str(legal_name),
        )
    )


def record_source_alias(
    connection: psycopg.Connection,
    *,
    organization_id: str,
    alias: str,
    source_record_id: str,
    source_code: str,
    alias_type: str = "source_name",
) -> str:
    normalized_alias = normalize_organization_name(
        connection,
        alias,
    )

    row = connection.execute(
        """
        INSERT INTO organization_aliases (
            organization_id,
            alias,
            normalized_alias,
            alias_type,
            is_active,
            source_record_id,
            metadata
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            TRUE,
            %s,
            %s
        )
        ON CONFLICT (
            organization_id,
            alias,
            alias_type
        )
        DO UPDATE SET
            normalized_alias =
                EXCLUDED.normalized_alias,
            is_active = TRUE,
            source_record_id =
                COALESCE(
                    organization_aliases.source_record_id,
                    EXCLUDED.source_record_id
                ),
            updated_at = NOW()
        RETURNING id
        """,
        (
            organization_id,
            alias,
            normalized_alias,
            alias_type,
            source_record_id,
            Jsonb(
                {
                    "firstSourceCode":
                        source_code,
                }
            ),
        ),
    ).fetchone()

    if row is None:
        stop("Unable to preserve organization source alias.")

    alias_id = str(row[0])

    connection.execute(
        """
        INSERT INTO entity_source_links (
            source_record_id,
            entity_type,
            entity_id,
            relationship_type,
            metadata
        )
        VALUES (
            %s,
            'organization_alias',
            %s,
            'source_name',
            %s
        )
        ON CONFLICT DO NOTHING
        """,
        (
            source_record_id,
            alias_id,
            Jsonb({"sourceCode": source_code}),
        ),
    )

    return alias_id
