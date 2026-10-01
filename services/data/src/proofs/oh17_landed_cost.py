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
    "originhut_oh17_landed_cost_test_"
    + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    + "_"
    + str(os.getpid())
)

API_PORT = 4170
API_BASE = f"http://127.0.0.1:{API_PORT}"
PRODUCT_NAME = "Activated Carbon"
HS_CODE = "380210"


class ProofError(RuntimeError):
    pass


def stop(message: str) -> None:
    raise ProofError(message)


def database_url_with_name(
    value: str,
    database_name: str,
) -> str:

    parts = urlsplit(value)

    if (
        parts.scheme
        not in {
            "postgres",
            "postgresql",
        }
        or not parts.netloc
    ):
        stop(
            "DATABASE_URL must be a valid PostgreSQL URL."
        )

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            "/" + database_name,
            parts.query,
            parts.fragment,
        )
    )


def resolve_executable(
    command: str,
) -> str:

    candidate = Path(command)

    if candidate.is_file():
        return str(candidate)

    resolved = shutil.which(
        command
    )

    if (
        resolved is None
        and os.name == "nt"
    ):
        resolved = shutil.which(
            command + ".cmd"
        )

    if resolved is None:
        stop(
            "Required executable was not found on PATH: "
            + command
        )

    return resolved


def safe_command_text(
    arguments: list[str],
) -> str:

    return " ".join(
        "[DATABASE_URL]"
        if argument.startswith(
            (
                "postgres://",
                "postgresql://",
            )
        )
        else argument
        for argument in arguments
    )


def run_command(
    arguments: list[str],
    *,
    env: dict[str, str] | None = None,
) -> str:

    resolved_arguments = [
        resolve_executable(
            arguments[0]
        ),
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
        print(
            result.stdout.rstrip()
        )

    if result.stderr:
        print(
            result.stderr.rstrip()
        )

    if result.returncode != 0:
        stop(
            "Command failed with exit code "
            + str(
                result.returncode
            )
            + ": "
            + safe_command_text(
                arguments
            )
        )

    return result.stdout


def production_baseline(
    database_url: str,
) -> str:

    with psycopg.connect(
        database_url
    ) as connection:

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
        stop(
            "Unable to read production baseline."
        )

    return str(
        row[0]
    )


def create_database(
    production_url: str,
    test_url: str,
) -> None:

    admin_url = database_url_with_name(
        production_url,
        "postgres",
    )

    with psycopg.connect(
        admin_url,
        autocommit=True,
    ) as connection:

        connection.execute(
            sql.SQL(
                "CREATE DATABASE {}"
            ).format(
                sql.Identifier(
                    TEST_DATABASE_NAME
                )
            )
        )

    with psycopg.connect(
        test_url
    ) as connection:

        connection.execute(
            "CREATE EXTENSION IF NOT EXISTS pgcrypto"
        )

        connection.execute(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm"
        )

        connection.execute(
            "CREATE EXTENSION IF NOT EXISTS postgis"
        )


def drop_database(
    production_url: str,
) -> None:

    admin_url = database_url_with_name(
        production_url,
        "postgres",
    )

    last_error: Exception | None = None

    for attempt in range(
        1,
        4,
    ):

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
                        sql.Identifier(
                            TEST_DATABASE_NAME
                        )
                    )
                )

            return

        except Exception as error:
            last_error = error

            if attempt < 3:
                time.sleep(
                    float(
                        attempt
                    )
                )

    assert (
        last_error
        is not None
    )

    raise last_error


def apply_migrations(
    test_url: str,
) -> None:

    migrations = sorted(
        (
            PROJECT_ROOT
            / "database"
            / "migrations"
        ).glob(
            "*.sql"
        )
    )

    for migration in migrations:

        print(
            "Applying",
            migration.name,
        )

        run_command(
            [
                "psql",
                test_url,
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(
                    migration
                ),
            ]
        )

    with psycopg.connect(
        test_url
    ) as connection:

        row = connection.execute(
            """
            SELECT MAX(
                LPAD(
                    version,
                    10,
                    '0'
                )
            )
            FROM schema_migrations
            """
        ).fetchone()

    if (
        row is None
        or row[0]
           != "0000000026"
    ):
        stop(
            "Migration head is not 026."
        )


def seed_reference_data(
    test_url: str,
) -> str:

    with psycopg.connect(
        test_url
    ) as connection:

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
                iso3 =
                    EXCLUDED.iso3,
                numeric_code =
                    EXCLUDED.numeric_code,
                name =
                    EXCLUDED.name,
                official_name =
                    EXCLUDED.official_name,
                is_active =
                    TRUE
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
            VALUES
                (
                    'USD',
                    '840',
                    'US Dollar',
                    '$',
                    2,
                    TRUE
                ),
                (
                    'AED',
                    '784',
                    'UAE Dirham',
                    'AED',
                    2,
                    TRUE
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
                    TRUE
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
                level =
                    EXCLUDED.level,
                description =
                    EXCLUDED.description,
                is_leaf =
                    TRUE,
                valid_from =
                    EXCLUDED.valid_from
            """
        )

        connection.execute(
            """
            INSERT INTO trade_locations (
                unlocode,
                country_id,
                country_code,
                location_code,
                name,
                function_codes,
                status,
                marked_for_deletion
            )
            SELECT
                'AEJEA',
                c.id,
                'AE',
                'JEA',
                'Jebel Ali',
                '1-------',
                'AA',
                FALSE
            FROM countries c
            WHERE c.iso2 = 'AE'
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
                function_codes =
                    EXCLUDED.function_codes,
                marked_for_deletion =
                    FALSE
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
                'oh17_landed_cost_proof_source',
                'OH17 Landed Cost Proof Source',
                'Origin Hut Proof',
                'commercial_intelligence',
                'synthetic_proof',
                FALSE,
                '{"proofOnly":true}'::jsonb
            )
            ON CONFLICT (code)
            DO UPDATE SET
                name =
                    EXCLUDED.name
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
                'landed_cost_proof_evidence',
                repeat('d', 64),
                '{"synthetic":true,"purpose":"OH17 landed-cost architecture proof"}'::jsonb,
                '{"proofOnly":true}'::jsonb
            )
            RETURNING id::text
            """,
            (
                source_id,
                ingestion_run_id,
                (
                    "oh17-landed-cost-proof-"
                    + TEST_DATABASE_NAME
                ),
            ),
        ).fetchone()[0]

    return str(
        source_record_id
    )


def wait_for_api(
    process: subprocess.Popen[str],
    stdout_path: Path,
    stderr_path: Path,
) -> None:

    for _ in range(
        40
    ):

        if (
            process.poll()
            is not None
        ):
            break

        try:

            response = httpx.get(
                API_BASE
                + "/api/health",
                timeout=2.0,
            )

            if (
                response.status_code
                == 200
                and response.json().get(
                    "ok"
                )
                is True
            ):
                return

        except (
            httpx.HTTPError,
            ValueError,
        ):
            pass

        time.sleep(
            0.5
        )

    print(
        "=== API STDOUT ==="
    )

    if stdout_path.exists():
        print(
            stdout_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )

    print(
        "=== API STDERR ==="
    )

    if stderr_path.exists():
        print(
            stderr_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )

    stop(
        "Origin Hut API did not become healthy."
    )


def request_json(
    method: str,
    path: str,
    *,
    payload:
        dict[str, Any]
        | None = None,
    params:
        dict[str, Any]
        | None = None,
) -> dict[str, Any]:

    response = httpx.request(
        method,
        API_BASE
        + path,
        json=payload,
        params=params,
        timeout=30.0,
    )

    try:
        body = response.json()
    except ValueError:
        stop(
            f"{method} {path} returned non-JSON."
        )

    if response.status_code >= 400:
        stop(
            f"{method} {path} failed status={response.status_code}: "
            + json.dumps(
                body,
                sort_keys=True,
            )
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


def assert_close(
    actual: float,
    expected: float,
    message: str,
) -> None:

    if abs(
        actual
        - expected
    ) > 0.000001:

        stop(
            message
            + f" expected={expected!r} actual={actual!r}"
        )


def main() -> int:

    load_dotenv(
        PROJECT_ROOT
        / ".env",
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
    print(
        "=== OH17 LANDED COST ENGINE PROOF ==="
    )

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

    if branch != "work/oh17":
        stop(
            "OH17 proof must run from work/oh17."
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
            "Working tree must be clean before OH17 proof."
        )

    api_process: subprocess.Popen[str] | None = None

    api_stdout_handle = None
    api_stderr_handle = None

    with tempfile.TemporaryDirectory(
        prefix="originhut-oh17-"
    ) as directory:

        temp = Path(
            directory
        )

        api_stdout_path = (
            temp
            / "api.stdout.log"
        )

        api_stderr_path = (
            temp
            / "api.stderr.log"
        )

        try:

            create_database(
                production_url,
                test_url,
            )

            apply_migrations(
                test_url
            )

            source_record_id = (
                seed_reference_data(
                    test_url
                )
            )

            runtime_env = dict(
                os.environ
            )

            runtime_env.update(
                {
                    "DATABASE_URL":
                        test_url,
                    "NODE_ENV":
                        "test",
                    "API_HOST":
                        "127.0.0.1",
                    "API_PORT":
                        str(
                            API_PORT
                        ),
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

            api_stdout_handle = (
                api_stdout_path.open(
                    "w",
                    encoding="utf-8",
                )
            )

            api_stderr_handle = (
                api_stderr_path.open(
                    "w",
                    encoding="utf-8",
                )
            )

            api_process = subprocess.Popen(
                [
                    resolve_executable(
                        "node"
                    ),
                    "apps/api/dist/server.js",
                ],
                cwd=PROJECT_ROOT,
                env=runtime_env,
                stdout=
                    api_stdout_handle,
                stderr=
                    api_stderr_handle,
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

            seller = request_json(
                "POST",
                "/api/organizations",
                payload={
                    "legalName":
                        "OH17 Proof Seller Private Limited",
                    "tradingName":
                        "OH17 Proof Seller",
                    "country":
                        "IN",
                    "roles":
                        [
                            "supplier",
                            "exporter",
                        ],
                    "metadata": {
                        "proof":
                            "OH17",
                    },
                },
            )["organization"]

            buyer = request_json(
                "POST",
                "/api/organizations",
                payload={
                    "legalName":
                        "OH17 Proof Buyer LLC",
                    "tradingName":
                        "OH17 Proof Buyer",
                    "country":
                        "AE",
                    "roles":
                        [
                            "buyer",
                            "importer",
                        ],
                    "metadata": {
                        "proof":
                            "OH17",
                    },
                },
            )["organization"]

            manufacturer = request_json(
                "POST",
                "/api/organizations",
                payload={
                    "legalName":
                        "OH17 Proof Manufacturer Private Limited",
                    "tradingName":
                        "OH17 Proof Manufacturer",
                    "country":
                        "IN",
                    "roles":
                        [
                            "manufacturer",
                        ],
                    "metadata": {
                        "proof":
                            "OH17",
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
                            "OH17",
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
                        "OH17 synthetic landed-cost proof.",
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
                        "OH17 Proof Activated Carbon Grade AC-1000",
                    "brand":
                        "OH17 Proof Carbon",
                    "grade":
                        "AC-1000",
                    "sku":
                        "OH17-AC1000-25",
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
                manufacturer_product[
                    "id"
                ]
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

            offer = request_json(
                "POST",
                "/api/commercial-offers",
                payload={
                    "sellerId":
                        seller["id"],
                    "buyerId":
                        buyer["id"],
                    "manufacturerProductId":
                        manufacturer_product_id,
                    "packagingConfigurationId":
                        packaging["id"],
                    "offerReference":
                        "OH17-PROOF-CIF-001",
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
                },
            )["offer"]

            offer_id = str(
                offer["id"]
            )

            offer_before = {
                key:
                    offer[key]
                for key in [
                    "unitPrice",
                    "currencyCode",
                    "priceUomCode",
                    "incotermEdition",
                    "incotermCode",
                    "namedTradeLocationUnlocode",
                ]
            }

            print(
                "PASS: source CIF Commercial Offer created."
            )

            scenario = request_json(
                "POST",
                "/api/landed-cost/scenarios",
                payload={
                    "commercialOfferId":
                        offer_id,
                    "scenarioReference":
                        "OH17-LANDED-USD-001",
                    "status":
                        "calculated",
                    "targetQuantity":
                        20,
                    "targetUomCode":
                        "TNE",
                    "scenarioCurrencyCode":
                        "USD",
                    "destinationCountry":
                        "AE",
                    "destinationTradeLocationUnlocode":
                        "AEJEA",
                    "destinationPlaceText":
                        "Jebel Ali, United Arab Emirates",
                    "notes":
                        "Synthetic landed-cost proof only",
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
            )["scenario"]

            scenario_id = str(
                scenario["id"]
            )

            assert_close(
                scenario[
                    "offerAmountSourceCurrency"
                ],
                23000.0,
                "Offer amount in source currency is incorrect.",
            )

            assert_close(
                scenario[
                    "offerAmountScenarioCurrency"
                ],
                23000.0,
                "Offer amount in scenario currency is incorrect.",
            )

            assert_close(
                scenario[
                    "landedCostTotalScenarioCurrency"
                ],
                23000.0,
                "Initial landed cost must equal the source offer amount.",
            )

            assert_close(
                scenario[
                    "landedCostPerTargetUom"
                ],
                1150.0,
                "Initial per-UOM landed cost is incorrect.",
            )

            print(
                "PASS: offer amount normalized to target quantity."
            )

            scenario = request_json(
                "POST",
                (
                    "/api/landed-cost/scenarios/"
                    + scenario_id
                    + "/components"
                ),
                payload={
                    "componentTypeCode":
                        "insurance",
                    "description":
                        "Synthetic CIF insurance breakout",
                    "includedInOffer":
                        True,
                    "calculationMethod":
                        "fixed_amount",
                    "sourceAmount":
                        500,
                    "sourceCurrencyCode":
                        "USD",
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
            )["scenario"]

            assert_close(
                scenario[
                    "includedComponentTotalScenarioCurrency"
                ],
                500.0,
                "Included insurance breakout was not retained.",
            )

            assert_close(
                scenario[
                    "landedCostTotalScenarioCurrency"
                ],
                23000.0,
                "Included insurance was double-counted.",
            )

            print(
                "PASS: included CIF cost does not double-count."
            )

            scenario = request_json(
                "POST",
                (
                    "/api/landed-cost/scenarios/"
                    + scenario_id
                    + "/components"
                ),
                payload={
                    "componentTypeCode":
                        "destination_handling",
                    "description":
                        "Synthetic destination handling",
                    "includedInOffer":
                        False,
                    "calculationMethod":
                        "fixed_amount",
                    "sourceAmount":
                        600,
                    "sourceCurrencyCode":
                        "USD",
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
            )["scenario"]

            assert_close(
                scenario[
                    "addedComponentTotalScenarioCurrency"
                ],
                600.0,
                "Added destination handling total is incorrect.",
            )

            assert_close(
                scenario[
                    "landedCostTotalScenarioCurrency"
                ],
                23600.0,
                "Landed cost after destination handling is incorrect.",
            )

            print(
                "PASS: added fixed destination cost."
            )

            scenario = request_json(
                "POST",
                (
                    "/api/landed-cost/scenarios/"
                    + scenario_id
                    + "/components"
                ),
                payload={
                    "componentTypeCode":
                        "import_duty",
                    "description":
                        "Synthetic 5 percent proof duty",
                    "includedInOffer":
                        False,
                    "calculationMethod":
                        "percentage",
                    "percentageRate":
                        5,
                    "taxableBaseScenarioCurrency":
                        23600,
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
            )["scenario"]

            assert_close(
                scenario[
                    "addedComponentTotalScenarioCurrency"
                ],
                1780.0,
                "Added-cost total after duty is incorrect.",
            )

            assert_close(
                scenario[
                    "landedCostTotalScenarioCurrency"
                ],
                24780.0,
                "Final landed-cost total is incorrect.",
            )

            assert_close(
                scenario[
                    "landedCostPerTargetUom"
                ],
                1239.0,
                "Final landed cost per TNE is incorrect.",
            )

            print(
                "PASS: explicit percentage duty base and final landed cost."
            )

            component_types = {
                component[
                    "componentTypeCode"
                ]:
                    component
                for component in scenario[
                    "components"
                ]
            }

            assert_close(
                component_types[
                    "import_duty"
                ][
                    "amountScenarioCurrency"
                ],
                1180.0,
                "Percentage duty amount is incorrect.",
            )

            assert_close(
                component_types[
                    "insurance"
                ][
                    "amountScenarioCurrency"
                ],
                500.0,
                "Insurance breakout amount is incorrect.",
            )

            cross_currency = request_json(
                "POST",
                "/api/landed-cost/scenarios",
                payload={
                    "commercialOfferId":
                        offer_id,
                    "scenarioReference":
                        "OH17-LANDED-AED-001",
                    "status":
                        "calculated",
                    "targetQuantity":
                        20,
                    "targetUomCode":
                        "TNE",
                    "scenarioCurrencyCode":
                        "AED",
                    "destinationCountry":
                        "AE",
                    "destinationTradeLocationUnlocode":
                        "AEJEA",
                    "offerFxRateToScenario":
                        3.67,
                    "offerFxRateDate":
                        "2026-10-01",
                    "offerFxSource":
                        "synthetic_proof_rate",
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
            )["scenario"]

            assert_close(
                cross_currency[
                    "offerAmountScenarioCurrency"
                ],
                84410.0,
                "Cross-currency offer amount is incorrect.",
            )

            assert_equal(
                cross_currency[
                    "offerFxSource"
                ],
                "synthetic_proof_rate",
                "Cross-currency FX source was not retained.",
            )

            assert_equal(
                cross_currency[
                    "offerFxRateDate"
                ],
                "2026-10-01",
                "Cross-currency FX date was not retained.",
            )

            print(
                "PASS: explicit cross-currency FX provenance."
            )

            discovered = request_json(
                "GET",
                "/api/landed-cost/scenarios",
                params={
                    "productId":
                        product_id,
                    "destinationCountry":
                        "AE",
                    "limit":
                        100,
                },
            )

            assert_equal(
                discovered[
                    "pagination"
                ][
                    "total"
                ],
                2,
                "Product-scoped landed-cost scenario discovery is incorrect.",
            )

            print(
                "PASS: Product-scoped landed-cost discovery."
            )

            offer_after = request_json(
                "GET",
                (
                    "/api/commercial-offers/"
                    + offer_id
                ),
            )["offer"]

            for (
                key,
                expected_value
            ) in offer_before.items():

                assert_equal(
                    offer_after[
                        key
                    ],
                    expected_value,
                    (
                        "Commercial Offer changed during landed-cost calculation: "
                        + key
                    ),
                )

            print(
                "PASS: source Commercial Offer remained immutable."
            )

            with psycopg.connect(
                test_url
            ) as connection:

                scenario_links = connection.execute(
                    """
                    SELECT COUNT(*)::int
                    FROM entity_source_links
                    WHERE
                        source_record_id = %s
                        AND entity_type =
                            'landed_cost_scenario'
                    """,
                    (
                        source_record_id,
                    ),
                ).fetchone()[0]

                component_links = connection.execute(
                    """
                    SELECT COUNT(*)::int
                    FROM entity_source_links
                    WHERE
                        source_record_id = %s
                        AND entity_type =
                            'landed_cost_component'
                    """,
                    (
                        source_record_id,
                    ),
                ).fetchone()[0]

            assert_equal(
                scenario_links,
                2,
                "Scenario provenance links are incomplete.",
            )

            assert_equal(
                component_links,
                3,
                "Component provenance links are incomplete.",
            )

            print(
                "PASS: landed-cost scenario and component provenance."
            )

            production_after = production_baseline(
                production_url
            )

            assert_equal(
                production_after,
                production_before,
                "Production database changed during OH17 proof.",
            )

            print("")
            print(
                "=================================================="
            )
            print(
                "OH17 LANDED COST ENGINE PROOF PASSED"
            )
            print(
                "SCHEMA HEAD 026 PASS"
            )
            print(
                "PRODUCT WORKBENCH BUILD PASS"
            )
            print(
                "SOURCE COMMERCIAL OFFER IMMUTABILITY PASS"
            )
            print(
                "OFFER AMOUNT NORMALIZATION PASS"
            )
            print(
                "INCLUDED COST NO DOUBLE COUNT PASS"
            )
            print(
                "ADDED FIXED COST PASS"
            )
            print(
                "PERCENTAGE DUTY BASE PASS"
            )
            print(
                "LANDED COST TOTAL 24780 USD PASS"
            )
            print(
                "LANDED COST PER TNE 1239 USD PASS"
            )
            print(
                "CROSS-CURRENCY FX PROVENANCE PASS"
            )
            print(
                "LANDED COST PROVENANCE PASS"
            )
            print(
                "PRODUCT-SCOPED SCENARIO DISCOVERY PASS"
            )
            print(
                "PRODUCTION DATABASE UNCHANGED"
            )
            print(
                "=================================================="
            )

            return 0

        finally:

            if (
                api_process
                is not None
                and api_process.poll()
                    is None
            ):

                api_process.terminate()

                try:
                    api_process.wait(
                        timeout=10
                    )

                except subprocess.TimeoutExpired:
                    api_process.kill()

            if (
                api_stdout_handle
                is not None
            ):
                api_stdout_handle.close()

            if (
                api_stderr_handle
                is not None
            ):
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
            "OH17 PROOF FAILED:",
            error,
        )

        raise SystemExit(
            1
        )
