from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import psycopg

from dotenv import load_dotenv
from psycopg import sql


SOURCE_FILE = Path(__file__).resolve()
PROJECT_ROOT = SOURCE_FILE.parents[4]

TEST_DATABASE_NAME = (
    "originhut_oh15_product_master_test_"
    + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    + "_"
    + str(os.getpid())
)

API_PORT = 4150
API_BASE = f"http://127.0.0.1:{API_PORT}"
PRODUCT_NAME = "Activated Carbon"
HS_CODE = "380210"


class ProofError(RuntimeError):
    pass


def stop(message: str) -> None:
    raise ProofError(message)


def database_url_with_name(value: str, database_name: str) -> str:
    parts = urlsplit(value)

    if parts.scheme not in {"postgres", "postgresql"} or not parts.netloc:
        stop("DATABASE_URL must be a valid PostgreSQL URL.")

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            "/" + database_name,
            parts.query,
            parts.fragment,
        )
    )


def resolve_executable(command: str) -> str:
    candidate = Path(command)

    if candidate.is_file():
        return str(candidate)

    resolved = shutil.which(command)

    if resolved is None and os.name == "nt":
        resolved = shutil.which(command + ".cmd")

    if resolved is None:
        stop("Required executable was not found on PATH: " + command)

    return resolved


def safe_command_text(arguments: list[str]) -> str:
    return " ".join(
        "[DATABASE_URL]"
        if argument.startswith(("postgres://", "postgresql://"))
        else argument
        for argument in arguments
    )


def run_command(
    arguments: list[str],
    *,
    env: dict[str, str] | None = None,
) -> str:

    resolved_arguments = [
        resolve_executable(arguments[0]),
        *arguments[1:],
    ]

    result = subprocess.run(
        resolved_arguments,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout.rstrip())

    if result.stderr:
        print(result.stderr.rstrip())

    if result.returncode != 0:
        stop(
            "Command failed with exit code "
            + str(result.returncode)
            + ": "
            + safe_command_text(arguments)
        )

    return result.stdout


def production_baseline(database_url: str) -> str:
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM ingestion_runs)::text
                || '|'
                || (SELECT COUNT(*) FROM source_records)::text
                || '|'
                || (SELECT COUNT(*) FROM trade_flows)::text
            """
        ).fetchone()

    if row is None:
        stop("Unable to read production baseline.")

    return str(row[0])


def create_database(production_url: str, test_url: str) -> None:
    admin_url = database_url_with_name(production_url, "postgres")

    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(TEST_DATABASE_NAME)
            )
        )

    with psycopg.connect(test_url) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        connection.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        connection.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def drop_database(production_url: str) -> None:
    admin_url = database_url_with_name(production_url, "postgres")

    last_error: Exception | None = None

    for attempt in range(1, 4):

        try:
            with psycopg.connect(
                admin_url,
                autocommit=True,
            ) as connection:

                connection.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE
                        datname = %s
                        AND pid <> pg_backend_pid()
                    """,
                    (
                        TEST_DATABASE_NAME,
                    ),
                )

                connection.execute(
                    sql.SQL(
                        "DROP DATABASE IF EXISTS {} WITH (FORCE)"
                    ).format(
                        sql.Identifier(TEST_DATABASE_NAME)
                    )
                )

            return

        except Exception as error:
            last_error = error

            if attempt < 3:
                time.sleep(float(attempt))

    assert last_error is not None
    raise last_error


def apply_migrations(test_url: str) -> None:
    migrations = sorted(
        (PROJECT_ROOT / "database" / "migrations").glob("*.sql")
    )

    for migration in migrations:
        print("Applying", migration.name)
        run_command(
            [
                "psql",
                test_url,
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(migration),
            ]
        )

    with psycopg.connect(test_url) as connection:
        row = connection.execute(
            """
            SELECT MAX(LPAD(version, 10, '0'))
            FROM schema_migrations
            """
        ).fetchone()

    if row is None or row[0] != "0000000022":
        stop("Migration head is not 022.")


def seed_reference_data(test_url: str) -> str:
    with psycopg.connect(test_url) as connection:

        connection.execute(
            """
            INSERT INTO countries (
                iso2,
                iso3,
                numeric_code,
                name,
                official_name,
                is_active
            )
            VALUES (
                'IN',
                'IND',
                '356',
                'India',
                'Republic of India',
                TRUE
            )
            ON CONFLICT (iso2)
            DO UPDATE SET
                iso3 = EXCLUDED.iso3,
                numeric_code = EXCLUDED.numeric_code,
                name = EXCLUDED.name,
                official_name = EXCLUDED.official_name,
                is_active = TRUE
            """
        )

        connection.execute(
            """
            INSERT INTO hs_codes (
                nomenclature,
                code,
                level,
                description,
                is_leaf,
                valid_from
            )
            VALUES (
                'HS2022',
                '380210',
                6,
                'Carbon; activated',
                TRUE,
                DATE '2022-01-01'
            )
            ON CONFLICT (
                nomenclature,
                code
            )
            DO UPDATE SET
                level = EXCLUDED.level,
                description = EXCLUDED.description,
                is_leaf = TRUE,
                valid_from = EXCLUDED.valid_from
            """
        )

        source_id = connection.execute(
            """
            INSERT INTO data_sources (
                code,
                name,
                provider,
                category,
                access_method,
                is_official,
                metadata
            )
            VALUES (
                'oh15_product_master_proof_source',
                'OH15 Product Master Proof Source',
                'Origin Hut Proof',
                'product_intelligence',
                'synthetic_proof',
                FALSE,
                '{"proofOnly":true}'::jsonb
            )
            ON CONFLICT (code)
            DO UPDATE SET
                name = EXCLUDED.name
            RETURNING id
            """
        ).fetchone()[0]

        ingestion_run_id = connection.execute(
            """
            INSERT INTO ingestion_runs (
                data_source_id,
                status,
                finished_at,
                records_seen,
                records_inserted,
                metadata
            )
            VALUES (
                %s,
                'completed',
                NOW(),
                1,
                1,
                '{"proofOnly":true}'::jsonb
            )
            RETURNING id
            """,
            (
                source_id,
            ),
        ).fetchone()[0]

        source_record_id = connection.execute(
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
                'product_master_proof_evidence',
                repeat('b', 64),
                '{"synthetic":true,"purpose":"OH15 architecture proof"}'::jsonb,
                '{"proofOnly":true}'::jsonb
            )
            RETURNING id::text
            """,
            (
                source_id,
                ingestion_run_id,
                (
                    "oh15-product-master-proof-"
                    + TEST_DATABASE_NAME
                ),
            ),
        ).fetchone()[0]

    return str(source_record_id)


def wait_for_api(
    process: subprocess.Popen[str],
    stdout_path: Path,
    stderr_path: Path,
) -> None:

    for _ in range(40):

        if process.poll() is not None:
            break

        try:
            response = httpx.get(
                API_BASE + "/api/health",
                timeout=2.0,
            )

            if (
                response.status_code == 200
                and response.json().get("ok") is True
            ):
                return

        except (
            httpx.HTTPError,
            ValueError,
        ):
            pass

        time.sleep(0.5)

    print("=== API STDOUT ===")
    if stdout_path.exists():
        print(
            stdout_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )

    print("=== API STDERR ===")
    if stderr_path.exists():
        print(
            stderr_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )

    stop("Origin Hut API did not become healthy.")


def request_json(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:

    response = httpx.request(
        method,
        API_BASE + path,
        json=payload,
        params=params,
        timeout=30.0,
    )

    try:
        body = response.json()
    except ValueError:
        stop(f"{method} {path} returned non-JSON.")

    if response.status_code >= 400:
        stop(
            f"{method} {path} failed status={response.status_code}: "
            + json.dumps(body, sort_keys=True)
        )

    return body


def assert_equal(
    actual: Any,
    expected: Any,
    message: str,
) -> None:

    if actual != expected:
        stop(
            message
            + f" expected={expected!r} actual={actual!r}"
        )


def main() -> int:
    load_dotenv(
        PROJECT_ROOT / ".env",
        override=False,
    )

    production_url = os.environ.get(
        "DATABASE_URL",
        "",
    ).strip()

    if not production_url:
        stop(
            "DATABASE_URL is required through the environment "
            "or active checkout .env."
        )

    test_url = database_url_with_name(
        production_url,
        TEST_DATABASE_NAME,
    )

    print("")
    print("=== OH15 PRODUCT TRADE MASTER PROOF ===")

    production_before = production_baseline(
        production_url
    )

    print(
        "Production baseline:",
        production_before,
    )

    print(
        "Disposable database:",
        TEST_DATABASE_NAME,
    )

    branch = run_command(
        [
            "git",
            "branch",
            "--show-current",
        ]
    ).strip()

    if branch != "work/oh15":
        stop(
            "OH15 proof must run from work/oh15."
        )

    status = run_command(
        [
            "git",
            "status",
            "--porcelain",
        ]
    ).strip()

    if status:
        stop(
            "Working tree must be clean before OH15 proof."
        )

    api_process: subprocess.Popen[str] | None = None
    api_stdout_handle = None
    api_stderr_handle = None

    with tempfile.TemporaryDirectory(
        prefix="originhut-oh15-"
    ) as directory:

        temp = Path(directory)
        api_stdout_path = temp / "api.stdout.log"
        api_stderr_path = temp / "api.stderr.log"

        try:
            create_database(
                production_url,
                test_url,
            )

            apply_migrations(
                test_url
            )

            source_record_id = seed_reference_data(
                test_url
            )

            runtime_env = dict(os.environ)

            runtime_env.update(
                {
                    "DATABASE_URL":
                        test_url,
                    "NODE_ENV":
                        "test",
                    "API_HOST":
                        "127.0.0.1",
                    "API_PORT":
                        str(API_PORT),
                    "NEXT_PUBLIC_API_BASE_URL":
                        API_BASE,
                }
            )

            run_command(
                [
                    "npm",
                    "run",
                    "typecheck",
                ],
                env=runtime_env,
            )

            run_command(
                [
                    "npm",
                    "run",
                    "build:api",
                ],
                env=runtime_env,
            )

            run_command(
                [
                    "npm",
                    "run",
                    "build:web",
                ],
                env=runtime_env,
            )

            print(
                "PASS: API typecheck/build and Product Workbench build."
            )

            api_stdout_handle = api_stdout_path.open(
                "w",
                encoding="utf-8",
            )

            api_stderr_handle = api_stderr_path.open(
                "w",
                encoding="utf-8",
            )

            api_process = subprocess.Popen(
                [
                    resolve_executable("node"),
                    "apps/api/dist/server.js",
                ],
                cwd=PROJECT_ROOT,
                env=runtime_env,
                stdout=api_stdout_handle,
                stderr=api_stderr_handle,
                text=True,
            )

            wait_for_api(
                api_process,
                api_stdout_path,
                api_stderr_path,
            )

            print(
                "PASS: disposable API is healthy."
            )

            organization = request_json(
                "POST",
                "/api/organizations",
                payload={
                    "legalName":
                        "OH15 Proof Carbon Manufacturer Private Limited",
                    "tradingName":
                        "OH15 Proof Carbon",
                    "country":
                        "IN",
                    "roles":
                        [
                            "manufacturer",
                        ],
                    "metadata": {
                        "proof":
                            "OH15",
                    },
                },
            )["organization"]

            manufacturer_id = str(
                organization["id"]
            )

            product = request_json(
                "POST",
                "/api/products",
                payload={
                    "name":
                        PRODUCT_NAME,
                    "description":
                        "Generic activated carbon trade Product.",
                    "baseUomCode":
                        "KGM",
                    "attributes": {
                        "proof":
                            "OH15",
                    },
                    "metadata": {
                        "productScope":
                            "generic_trade_product",
                    },
                },
            )["product"]

            product_id = str(
                product["id"]
            )

            assert_equal(
                product["baseUomCode"],
                "KGM",
                "Product base UOM was not persisted.",
            )

            classification = request_json(
                "POST",
                "/api/intelligence/hs/classify",
                payload={
                    "description":
                        "Activated carbon used for purification.",
                    "productName":
                        PRODUCT_NAME,
                    "productId":
                        product_id,
                    "country":
                        "IN",
                    "attributes": {
                        "material":
                            "activated carbon",
                    },
                    "limit":
                        5,
                },
            )

            request_id = str(
                classification[
                    "request"
                ][
                    "id"
                ]
            )

            confirmation = request_json(
                "POST",
                (
                    "/api/intelligence/hs/classifications/"
                    + request_id
                    + "/confirm"
                ),
                payload={
                    "hsCode":
                        HS_CODE,
                    "productId":
                        product_id,
                    "notes":
                        "OH15 Product Master proof classification.",
                },
            )

            if not confirmation[
                "confirmation"
            ][
                "persistedToProduct"
            ]:
                stop(
                    "HS confirmation was not persisted."
                )

            print(
                "PASS: generic Product + KGM + HS2022 380210."
            )

            conversion = request_json(
                "POST",
                "/api/reference/units/convert",
                payload={
                    "value":
                        1,
                    "fromCode":
                        "TNE",
                    "toCode":
                        "KGM",
                },
            )

            assert_equal(
                conversion[
                    "conversion"
                ][
                    "output"
                ][
                    "value"
                ],
                1000,
                "TNE to KGM conversion failed.",
            )

            print(
                "PASS: canonical UOM conversion."
            )

            manufacturer_product = request_json(
                "POST",
                (
                    f"/api/products/{product_id}"
                    "/manufacturer-products"
                ),
                payload={
                    "manufacturerId":
                        manufacturer_id,
                    "originCountry":
                        "IN",
                    "name":
                        "OH15 Proof Activated Carbon Grade AC-1000",
                    "brand":
                        "OH15 Proof Carbon",
                    "grade":
                        "AC-1000",
                    "modelCode":
                        "AC1000",
                    "sku":
                        "OH15-AC1000-25",
                    "description":
                        "Synthetic manufacturer-grade identity for OH15 proof.",
                    "sourceType":
                        "synthetic_proof",
                    "sourceRecordId":
                        source_record_id,
                    "confidence":
                        1.0,
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )["manufacturerProduct"]

            manufacturer_product_id = str(
                manufacturer_product["id"]
            )

            assert_equal(
                manufacturer_product[
                    "originCountryIso2"
                ],
                "IN",
                "Manufacturer Product origin was not explicit.",
            )

            assert_equal(
                manufacturer_product[
                    "canonicalSourceRecordId"
                ],
                source_record_id,
                "Manufacturer Product source record was not retained.",
            )

            if (
                manufacturer_product[
                    "evidenceCount"
                ]
                < 1
            ):
                stop(
                    "Manufacturer Product provenance link is missing."
                )

            print(
                "PASS: Manufacturer Product identity + origin + provenance."
            )

            request_json(
                "POST",
                "/api/specifications/definitions",
                payload={
                    "code":
                        "raw_material",
                    "name":
                        "Raw Material",
                    "category":
                        "material",
                    "valueType":
                        "text",
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )

            request_json(
                "POST",
                "/api/specifications/definitions",
                payload={
                    "code":
                        "particle_size",
                    "name":
                        "Particle Size",
                    "category":
                        "physical",
                    "valueType":
                        "numeric",
                    "dimensionCode":
                        "length",
                    "defaultUomCode":
                        "MMT",
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )

            request_json(
                "POST",
                f"/api/products/{product_id}/specifications",
                payload={
                    "definitionCode":
                        "raw_material",
                    "textValue":
                        "Synthetic coconut-shell example",
                    "sourceType":
                        "synthetic_proof",
                    "sourceRecordId":
                        source_record_id,
                    "confidence":
                        1.0,
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )

            request_json(
                "POST",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/specifications"
                ),
                payload={
                    "definitionCode":
                        "particle_size",
                    "qualifier":
                        "range",
                    "minimumValue":
                        0.6,
                    "maximumValue":
                        2.36,
                    "uomCode":
                        "MMT",
                    "sourceType":
                        "synthetic_proof",
                    "sourceRecordId":
                        source_record_id,
                    "confidence":
                        1.0,
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )

            generic_specs = request_json(
                "GET",
                f"/api/products/{product_id}/specifications",
            )["specifications"]

            manufacturer_specs = request_json(
                "GET",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/specifications"
                ),
            )["specifications"]

            if len(generic_specs) != 1 or len(manufacturer_specs) != 1:
                stop(
                    "Expected generic and manufacturer specifications."
                )

            print(
                "PASS: structured generic + manufacturer specifications."
            )

            packaging = request_json(
                "POST",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/packaging"
                ),
                payload={
                    "packageTypeCode":
                        "5H",
                    "name":
                        "25 kg woven plastic bag",
                    "packagingLevel":
                        "primary",
                    "packagingMaterial":
                        "woven plastic",
                    "contentQuantity":
                        25,
                    "contentUomCode":
                        "KGM",
                    "netWeight":
                        25,
                    "grossWeight":
                        25.4,
                    "weightUomCode":
                        "KGM",
                    "length":
                        80,
                    "width":
                        50,
                    "height":
                        15,
                    "dimensionUomCode":
                        "CMT",
                    "isDefault":
                        True,
                    "sourceType":
                        "synthetic_proof",
                    "sourceRecordId":
                        source_record_id,
                    "confidence":
                        1.0,
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )["packaging"]

            assert_equal(
                packaging[
                    "packageTypeCode"
                ],
                "5H",
                "Packaging type was not retained.",
            )

            print(
                "PASS: manufacturer packaging + physical UOM."
            )

            site = request_json(
                "POST",
                f"/api/organizations/{manufacturer_id}/sites",
                payload={
                    "name":
                        "OH15 Proof India Manufacturing Site",
                    "siteType":
                        "manufacturing",
                    "country":
                        "IN",
                    "address": {
                        "proofOnly":
                            True,
                    },
                    "sourceType":
                        "synthetic_proof",
                    "sourceRecordId":
                        source_record_id,
                    "confidence":
                        1.0,
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )["site"]

            site_id = str(
                site["id"]
            )

            request_json(
                "POST",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/sites"
                ),
                payload={
                    "siteId":
                        site_id,
                    "relationshipType":
                        "manufactured_at",
                    "sourceType":
                        "synthetic_proof",
                    "sourceRecordId":
                        source_record_id,
                    "confidence":
                        1.0,
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )

            sites = request_json(
                "GET",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/sites"
                ),
            )["sites"]

            if (
                len(sites) != 1
                or sites[0][
                    "relationshipType"
                ] != "manufactured_at"
            ):
                stop(
                    "Manufacturer Product manufacturing-site link failed."
                )

            print(
                "PASS: explicit manufacturing site and country separation."
            )

            document = request_json(
                "POST",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/documents"
                ),
                payload={
                    "typeCode":
                        "tds",
                    "issuerOrganizationId":
                        manufacturer_id,
                    "title":
                        "OH15 Proof Technical Data Sheet",
                    "documentNumber":
                        "OH15-TDS-001",
                    "verificationStatus":
                        "source_backed",
                    "sourceType":
                        "synthetic_proof",
                    "sourceRecordId":
                        source_record_id,
                    "confidence":
                        1.0,
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )["document"]

            document_id = str(
                document["id"]
            )

            request_json(
                "POST",
                "/api/compliance/frameworks",
                payload={
                    "code":
                        "oh15_proof_framework",
                    "name":
                        "OH15 Synthetic Proof Framework",
                    "authority":
                        "Origin Hut Proof",
                    "jurisdictionCountry":
                        "IN",
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )

            request_json(
                "POST",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/compliance"
                ),
                payload={
                    "frameworkCode":
                        "oh15_proof_framework",
                    "requirementCode":
                        "architecture_proof",
                    "complianceStatus":
                        "claimed",
                    "evidenceDocumentId":
                        document_id,
                    "sourceType":
                        "synthetic_proof",
                    "sourceRecordId":
                        source_record_id,
                    "confidence":
                        1.0,
                    "metadata": {
                        "proofOnly":
                            True,
                    },
                },
            )

            documents = request_json(
                "GET",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/documents"
                ),
            )["documents"]

            compliance = request_json(
                "GET",
                (
                    "/api/manufacturer-products/"
                    f"{manufacturer_product_id}"
                    "/compliance"
                ),
            )["compliance"]

            if len(documents) != 1 or len(compliance) != 1:
                stop(
                    "Document/compliance Product subject chain failed."
                )

            assert_equal(
                compliance[0][
                    "evidenceDocumentId"
                ],
                document_id,
                "Compliance evidence document was not retained.",
            )

            print(
                "PASS: documents + compliance evidence chain."
            )

            with psycopg.connect(test_url) as connection:

                entity_types = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT DISTINCT entity_type
                        FROM entity_source_links
                        WHERE source_record_id = %s
                        """,
                        (
                            source_record_id,
                        ),
                    ).fetchall()
                }

            expected_entity_types = {
                "manufacturer_product",
                "product_specification",
                "packaging_configuration",
                "organization_site",
                "manufacturer_product_site",
                "product_document",
                "product_compliance_record",
            }

            missing = (
                expected_entity_types
                - entity_types
            )

            if missing:
                stop(
                    "OH15 provenance links missing entity types: "
                    + ", ".join(
                        sorted(missing)
                    )
                )

            print(
                "PASS: unified OH15 entity_source_links provenance."
            )

            product_detail = request_json(
                "GET",
                f"/api/products/{product_id}",
            )["product"]

            assert_equal(
                product_detail[
                    "manufacturerProductCount"
                ],
                1,
                "Product did not expose Manufacturer Product count.",
            )

            assert_equal(
                product_detail[
                    "baseUomCode"
                ],
                "KGM",
                "Product detail lost base UOM.",
            )

            production_after = production_baseline(
                production_url
            )

            assert_equal(
                production_after,
                production_before,
                "Production database changed during OH15 proof.",
            )

            print("")
            print("==================================================")
            print("OH15 PRODUCT TRADE MASTER PROOF PASSED")
            print("SCHEMA HEAD 022 PASS")
            print("PRODUCT WORKBENCH BUILD PASS")
            print("GENERIC PRODUCT + BASE UOM PASS")
            print("PRODUCT -> HS2022 380210 PASS")
            print("UOM CONVERSION PASS")
            print("MANUFACTURER PRODUCT + ORIGIN PASS")
            print("STRUCTURED SPECIFICATIONS PASS")
            print("PACKAGING PASS")
            print("MANUFACTURING SITE PASS")
            print("DOCUMENTS + COMPLIANCE PASS")
            print("PRODUCT PROVENANCE PASS")
            print("PRODUCTION DATABASE UNCHANGED")
            print("==================================================")

            return 0

        finally:

            if (
                api_process is not None
                and api_process.poll() is None
            ):

                api_process.terminate()

                try:
                    api_process.wait(
                        timeout=10
                    )

                except subprocess.TimeoutExpired:
                    api_process.kill()

            if api_stdout_handle is not None:
                api_stdout_handle.close()

            if api_stderr_handle is not None:
                api_stderr_handle.close()

            try:
                drop_database(
                    production_url
                )

            except Exception as error:
                print(
                    "WARNING: unable to drop disposable database:",
                    error,
                )


if __name__ == "__main__":

    try:
        raise SystemExit(
            main()
        )

    except ProofError as error:
        print(
            "OH15 PROOF FAILED:",
            error,
        )
        raise SystemExit(1)
