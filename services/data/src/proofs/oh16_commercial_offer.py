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
    "originhut_oh16_commercial_offer_test_"
    + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    + "_"
    + str(os.getpid())
)

API_PORT = 4160
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

    if row is None or row[0] != "0000000025":
        stop("Migration head is not 025.")


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
            VALUES
                (
                    'IN',
                    'IND',
                    '356',
                    'India',
                    'Republic of India',
                    TRUE
                ),
                (
                    'AE',
                    'ARE',
                    '784',
                    'United Arab Emirates',
                    'United Arab Emirates',
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
            INSERT INTO currencies (
                code,
                numeric_code,
                name,
                symbol,
                decimal_places,
                is_active
            )
            VALUES (
                'USD',
                '840',
                'US Dollar',
                '$',
                2,
                TRUE
            )
            ON CONFLICT (code)
            DO UPDATE SET
                numeric_code = EXCLUDED.numeric_code,
                name = EXCLUDED.name,
                decimal_places = EXCLUDED.decimal_places,
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

        connection.execute(
            """
            INSERT INTO trade_locations (
                unlocode,
                country_id,
                country_code,
                location_code,
                subdivision_code,
                name,
                function_codes,
                status,
                marked_for_deletion
            )
            SELECT
                value.unlocode,
                country.id,
                value.country_code,
                value.location_code,
                value.subdivision_code,
                value.name,
                value.function_codes,
                'AA',
                FALSE
            FROM (
                VALUES
                    (
                        'INCOK',
                        'IN',
                        'COK',
                        'KL',
                        'Kochi',
                        '123456--'
                    ),
                    (
                        'AEJEA',
                        'AE',
                        'JEA',
                        NULL,
                        'Jebel Ali',
                        '1-------'
                    )
            ) AS value(
                unlocode,
                country_code,
                location_code,
                subdivision_code,
                name,
                function_codes
            )
            JOIN countries country
              ON country.iso2 = value.country_code
            ON CONFLICT (unlocode)
            DO UPDATE SET
                country_id = EXCLUDED.country_id,
                country_code = EXCLUDED.country_code,
                location_code = EXCLUDED.location_code,
                subdivision_code = EXCLUDED.subdivision_code,
                name = EXCLUDED.name,
                function_codes = EXCLUDED.function_codes,
                marked_for_deletion = FALSE
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
                'oh16_commercial_offer_proof_source',
                'OH16 Commercial Offer Proof Source',
                'Origin Hut Proof',
                'commercial_intelligence',
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
                'commercial_offer_proof_evidence',
                repeat('c', 64),
                '{"synthetic":true,"purpose":"OH16 commercial architecture proof"}'::jsonb,
                '{"proofOnly":true}'::jsonb
            )
            RETURNING id::text
            """,
            (
                source_id,
                ingestion_run_id,
                (
                    "oh16-commercial-offer-proof-"
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


def expect_status(
    method: str,
    path: str,
    status_code: int,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:

    response = httpx.request(
        method,
        API_BASE + path,
        json=payload,
        timeout=30.0,
    )

    if response.status_code != status_code:
        stop(
            f"{method} {path} expected status={status_code} "
            f"but received status={response.status_code}: "
            + response.text
        )

    try:
        return response.json()
    except ValueError:
        stop(
            f"{method} {path} returned non-JSON."
        )


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
    print("=== OH16 COMMERCIAL OFFER + INCOTERMS PROOF ===")

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

    if branch != "work/oh16":
        stop(
            "OH16 proof must run from work/oh16."
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
            "Working tree must be clean before OH16 proof."
        )

    api_process: subprocess.Popen[str] | None = None
    api_stdout_handle = None
    api_stderr_handle = None

    with tempfile.TemporaryDirectory(
        prefix="originhut-oh16-"
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

            incoterms = request_json(
                "GET",
                "/api/reference/incoterms",
                params={
                    "edition":
                        2020,
                    "limit":
                        50,
                },
            )

            assert_equal(
                incoterms[
                    "pagination"
                ][
                    "total"
                ],
                11,
                "Incoterms 2020 reference count is incorrect.",
            )

            cif = request_json(
                "GET",
                "/api/reference/incoterms/2020/CIF",
            )["incoterm"]

            assert_equal(
                cif[
                    "namedLocationRole"
                ],
                "destination_port",
                "CIF named-location role is incorrect.",
            )

            print(
                "PASS: Incoterms 2020 reference semantics."
            )

            seller = request_json(
                "POST",
                "/api/organizations",
                payload={
                    "legalName":
                        "OH16 Proof Seller Private Limited",
                    "tradingName":
                        "OH16 Proof Seller",
                    "country":
                        "IN",
                    "roles":
                        [
                            "supplier",
                            "exporter",
                        ],
                    "metadata": {
                        "proof":
                            "OH16",
                    },
                },
            )["organization"]

            buyer = request_json(
                "POST",
                "/api/organizations",
                payload={
                    "legalName":
                        "OH16 Proof Buyer LLC",
                    "tradingName":
                        "OH16 Proof Buyer",
                    "country":
                        "AE",
                    "roles":
                        [
                            "buyer",
                            "importer",
                        ],
                    "metadata": {
                        "proof":
                            "OH16",
                    },
                },
            )["organization"]

            manufacturer = request_json(
                "POST",
                "/api/organizations",
                payload={
                    "legalName":
                        "OH16 Proof Manufacturer Private Limited",
                    "tradingName":
                        "OH16 Proof Manufacturer",
                    "country":
                        "IN",
                    "roles":
                        [
                            "manufacturer",
                        ],
                    "metadata": {
                        "proof":
                            "OH16",
                    },
                },
            )["organization"]

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
                    "metadata": {
                        "proof":
                            "OH16",
                    },
                },
            )["product"]

            product_id = str(
                product["id"]
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
                    "limit":
                        5,
                },
            )

            classification_request_id = str(
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
                    + classification_request_id
                    + "/confirm"
                ),
                payload={
                    "hsCode":
                        HS_CODE,
                    "productId":
                        product_id,
                    "notes":
                        "OH16 synthetic Commercial Offer proof.",
                },
            )

            if not confirmation[
                "confirmation"
            ][
                "persistedToProduct"
            ]:
                stop(
                    "Product HS confirmation was not persisted."
                )

            manufacturer_product = request_json(
                "POST",
                (
                    f"/api/products/{product_id}"
                    "/manufacturer-products"
                ),
                payload={
                    "manufacturerId":
                        manufacturer["id"],
                    "originCountry":
                        "IN",
                    "name":
                        "OH16 Proof Activated Carbon Grade AC-1000",
                    "brand":
                        "OH16 Proof Carbon",
                    "grade":
                        "AC-1000",
                    "sku":
                        "OH16-AC1000-25",
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

            packaging_id = str(
                packaging["id"]
            )

            print(
                "PASS: Product -> Manufacturer Product -> packaging."
            )

            offer_payload = {
                "sellerId":
                    seller["id"],
                "buyerId":
                    buyer["id"],
                "manufacturerProductId":
                    manufacturer_product_id,
                "packagingConfigurationId":
                    packaging_id,
                "offerReference":
                    "OH16-PROOF-CIF-001",
                "status":
                    "active",
                "unitPrice":
                    1150,
                "currencyCode":
                    "USD",
                "priceUomCode":
                    "TNE",
                "minimumOrderQuantity":
                    20,
                "minimumOrderUomCode":
                    "TNE",
                "leadTimeDays":
                    21,
                "paymentTerms":
                    "Synthetic proof terms only",
                "incotermEdition":
                    2020,
                "incotermCode":
                    "CIF",
                "namedPlaceText":
                    "Jebel Ali, United Arab Emirates",
                "namedTradeLocationUnlocode":
                    "AEJEA",
                "validFrom":
                    "2026-10-01",
                "validTo":
                    "2026-10-31",
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
            }

            offer = request_json(
                "POST",
                "/api/commercial-offers",
                payload=offer_payload,
            )["offer"]

            offer_id = str(
                offer["id"]
            )

            assert_equal(
                offer[
                    "incotermCode"
                ],
                "CIF",
                "Commercial Offer lost Incoterm.",
            )

            assert_equal(
                offer[
                    "incotermEdition"
                ],
                2020,
                "Commercial Offer lost Incoterms edition.",
            )

            assert_equal(
                offer[
                    "namedTradeLocationUnlocode"
                ],
                "AEJEA",
                "Commercial Offer lost named destination port.",
            )

            assert_equal(
                offer[
                    "priceUomCode"
                ],
                "TNE",
                "Commercial Offer lost price basis UOM.",
            )

            if offer["evidenceCount"] < 1:
                stop(
                    "Commercial Offer provenance link is missing."
                )

            print(
                "PASS: CIF commercial offer + Jebel Ali + provenance."
            )

            offers = request_json(
                "GET",
                "/api/commercial-offers",
                params={
                    "manufacturerProductId":
                        manufacturer_product_id,
                    "incotermCode":
                        "CIF",
                    "incotermEdition":
                        2020,
                    "status":
                        "active",
                },
            )

            assert_equal(
                offers[
                    "pagination"
                ][
                    "total"
                ],
                1,
                "Commercial Offer list/filter did not return exactly one offer.",
            )

            assert_equal(
                offers[
                    "offers"
                ][
                    0
                ][
                    "id"
                ],
                offer_id,
                "Commercial Offer list returned the wrong offer.",
            )

            print(
                "PASS: Product-scoped Commercial Offer discovery."
            )

            invalid_maritime = dict(
                offer_payload
            )

            invalid_maritime.update(
                {
                    "offerReference":
                        "OH16-PROOF-FOB-INVALID",
                    "incotermCode":
                        "FOB",
                    "namedPlaceText":
                        "Some Port",
                    "namedTradeLocationUnlocode":
                        None,
                }
            )

            invalid_response = expect_status(
                "POST",
                "/api/commercial-offers",
                409,
                payload=invalid_maritime,
            )

            assert_equal(
                invalid_response[
                    "error"
                ],
                "commercial_offer_invalid",
                "Invalid maritime offer was not rejected correctly.",
            )

            print(
                "PASS: maritime Incoterm rejects free-text-only port."
            )

            invalid_dimension = dict(
                offer_payload
            )

            invalid_dimension.update(
                {
                    "offerReference":
                        "OH16-PROOF-BAD-UOM",
                    "incotermCode":
                        "CIF",
                    "priceUomCode":
                        "LTR",
                }
            )

            dimension_response = expect_status(
                "POST",
                "/api/commercial-offers",
                409,
                payload=invalid_dimension,
            )

            assert_equal(
                dimension_response[
                    "error"
                ],
                "commercial_offer_invalid",
                "Cross-dimension offer price was not rejected correctly.",
            )

            print(
                "PASS: offer price UOM respects Product dimension."
            )

            with psycopg.connect(test_url) as connection:

                evidence_count = connection.execute(
                    """
                    SELECT COUNT(*)::int
                    FROM entity_source_links
                    WHERE
                        source_record_id = %s
                        AND entity_type =
                            'commercial_offer'
                        AND entity_id = %s
                        AND relationship_type =
                            'offer_evidence'
                    """,
                    (
                        source_record_id,
                        offer_id,
                    ),
                ).fetchone()[0]

            assert_equal(
                evidence_count,
                1,
                "Commercial Offer canonical source link is missing.",
            )

            production_after = production_baseline(
                production_url
            )

            assert_equal(
                production_after,
                production_before,
                "Production database changed during OH16 proof.",
            )

            print("")
            print("==================================================")
            print("OH16 COMMERCIAL OFFER + INCOTERMS PROOF PASSED")
            print("SCHEMA HEAD 025 PASS")
            print("PRODUCT WORKBENCH BUILD PASS")
            print("INCOTERMS 2020 REFERENCE PASS")
            print("PRODUCT -> MANUFACTURER PRODUCT -> PACKAGING PASS")
            print("COMMERCIAL OFFER PRICE / CURRENCY / UOM PASS")
            print("MOQ / LEAD TIME / PAYMENT TERMS PASS")
            print("CIF + JEBEL ALI NAMED PORT PASS")
            print("MARITIME PORT VALIDATION PASS")
            print("COMMERCIAL OFFER PROVENANCE PASS")
            print("PRODUCT-SCOPED OFFER DISCOVERY PASS")
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
            "OH16 PROOF FAILED:",
            error,
        )
        raise SystemExit(1)
