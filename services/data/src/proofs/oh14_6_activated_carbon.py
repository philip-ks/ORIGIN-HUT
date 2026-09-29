from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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
SRC_ROOT = SOURCE_FILE.parents[1]
PROJECT_ROOT = SOURCE_FILE.parents[4]

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from connectors.company_web import execute_source, load_config


TEST_DATABASE_NAME = "originhut_oh14_6_product_test"
API_PORT = 4147
API_BASE = f"http://127.0.0.1:{API_PORT}"
HS_CODE = "380210"
PRODUCT_NAME = "Activated Carbon"


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
    result = subprocess.run(
        arguments,
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


def baseline(database_url: str) -> str:
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


def recreate_database(production_url: str, test_url: str) -> None:
    admin_url = database_url_with_name(production_url, "postgres")

    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(TEST_DATABASE_NAME)
            )
        )
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

    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(TEST_DATABASE_NAME)
            )
        )


def apply_migrations(test_url: str) -> None:
    psql = shutil.which("psql")

    if not psql:
        stop("psql is required on PATH for the OH14.6 proof.")

    migrations = sorted(
        (PROJECT_ROOT / "database" / "migrations").glob("*.sql")
    )

    for migration in migrations:
        print("Applying", migration.name)
        run_command(
            [
                psql,
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

    if row is None or row[0] != "0000000015":
        stop("Migration head is not 015.")


def seed_reference_data(test_url: str) -> None:
    with psycopg.connect(test_url) as connection:
        connection.execute(
            """
            INSERT INTO countries (
                iso2, iso3, numeric_code, name, official_name, is_active
            )
            VALUES
                ('IN', 'IND', '356', 'India', 'Republic of India', TRUE),
                ('AE', 'ARE', '784', 'United Arab Emirates',
                 'United Arab Emirates', TRUE)
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
                code, numeric_code, name, symbol, decimal_places, is_active
            )
            VALUES ('USD', '840', 'US Dollar', '$', 2, TRUE)
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
                nomenclature, code, level, description, is_leaf, valid_from
            )
            VALUES (
                'HS2022', '380210', 6, 'Carbon; activated',
                TRUE, DATE '2022-01-01'
            )
            ON CONFLICT (nomenclature, code)
            DO UPDATE SET
                level = EXCLUDED.level,
                description = EXCLUDED.description,
                is_leaf = TRUE,
                valid_from = EXCLUDED.valid_from
            """
        )


def wait_for_api(
    process: subprocess.Popen[str],
    stdout_path: Path,
    stderr_path: Path,
) -> None:
    for _ in range(40):
        if process.poll() is not None:
            break

        try:
            response = httpx.get(API_BASE + "/api/health", timeout=2.0)
            if response.status_code == 200 and response.json().get("ok") is True:
                return
        except (httpx.HTTPError, ValueError):
            pass

        time.sleep(0.5)

    print("=== API STDOUT ===")
    if stdout_path.exists():
        print(stdout_path.read_text(encoding="utf-8", errors="replace"))

    print("=== API STDERR ===")
    if stderr_path.exists():
        print(stderr_path.read_text(encoding="utf-8", errors="replace"))

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


def storage_files() -> set[Path]:
    root = PROJECT_ROOT / "storage"

    if not root.exists():
        return set()

    return {
        path.resolve()
        for path in root.rglob("*")
        if path.is_file()
    }


def remove_new_storage_files(before: set[Path]) -> None:
    root = PROJECT_ROOT / "storage"

    if not root.exists():
        return

    after = {
        path.resolve()
        for path in root.rglob("*")
        if path.is_file()
    }

    for path in sorted(after - before, reverse=True):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    production_url = os.environ.get("DATABASE_URL", "").strip()

    if not production_url:
        stop(
            "DATABASE_URL is required through the environment "
            "or the active checkout .env file."
        )

    if TEST_DATABASE_NAME in production_url:
        stop("Refusing to treat the proof database as production.")

    test_url = database_url_with_name(
        production_url,
        TEST_DATABASE_NAME,
    )

    print("")
    print("=== OH14.6 PRODUCT-FIRST ACTIVATED CARBON PROOF ===")

    production_before = baseline(production_url)
    print("Production baseline:", production_before)

    branch = run_command(["git", "branch", "--show-current"]).strip()
    if branch != "work/oh14":
        stop("OH14.6 proof must run from work/oh14.")

    status = run_command(["git", "status", "--porcelain"]).strip()
    if status:
        stop("Working tree must be clean before OH14.6 proof.")

    before_storage = storage_files()
    api_process: subprocess.Popen[str] | None = None
    api_stdout_handle = None
    api_stderr_handle = None

    with tempfile.TemporaryDirectory(prefix="originhut-oh14-6-") as directory:
        temp = Path(directory)
        api_stdout_path = temp / "api.stdout.log"
        api_stderr_path = temp / "api.stderr.log"

        try:
            recreate_database(production_url, test_url)
            apply_migrations(test_url)
            seed_reference_data(test_url)

            runtime_env = dict(os.environ)
            runtime_env.update(
                {
                    "DATABASE_URL": test_url,
                    "NODE_ENV": "test",
                    "API_HOST": "127.0.0.1",
                    "API_PORT": str(API_PORT),
                }
            )
            os.environ.update(runtime_env)

            run_command(["npm", "run", "typecheck"], env=runtime_env)
            run_command(["npm", "run", "build:api"], env=runtime_env)

            api_stdout_handle = api_stdout_path.open("w", encoding="utf-8")
            api_stderr_handle = api_stderr_path.open("w", encoding="utf-8")

            api_process = subprocess.Popen(
                ["node", "apps/api/dist/server.js"],
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
            print("PASS: disposable API is healthy.")

            product_response = request_json(
                "POST",
                "/api/products",
                payload={
                    "name": PRODUCT_NAME,
                    "description": (
                        "Activated carbon used for purification "
                        "and adsorption applications."
                    ),
                    "attributes": {
                        "material": "activated carbon",
                        "tradeCase": "OH14.6 India-UAE",
                    },
                    "metadata": {
                        "proof": "OH14.6",
                        "productScope": "generic_trade_product",
                    },
                },
            )

            product_id = str(product_response["product"]["id"])
            print("Product:", product_id, PRODUCT_NAME)

            classification_response = request_json(
                "POST",
                "/api/intelligence/hs/classify",
                payload={
                    "description": (
                        "Activated carbon used for purification "
                        "and adsorption applications."
                    ),
                    "productName": PRODUCT_NAME,
                    "productId": product_id,
                    "country": "IN",
                    "attributes": {
                        "material": "activated carbon",
                    },
                    "limit": 8,
                },
            )

            request_id = str(classification_response["request"]["id"])

            confirmation = request_json(
                "POST",
                (
                    "/api/intelligence/hs/classifications/"
                    + request_id
                    + "/confirm"
                ),
                payload={
                    "hsCode": HS_CODE,
                    "productId": product_id,
                    "notes": (
                        "OH14.6 explicit product-first "
                        "HS2022 confirmation."
                    ),
                },
            )

            if not confirmation["confirmation"]["persistedToProduct"]:
                stop("HS confirmation was not persisted to the Product.")

            classifications = request_json(
                "GET",
                f"/api/products/{product_id}/classifications",
            )

            if HS_CODE not in {
                item["hsCode"]
                for item in classifications["classifications"]
            }:
                stop("Product does not expose HS2022 380210.")

            print("PASS: Product -> HS2022 380210.")

            comtrade_run_id = (
                "oh14-6-"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            )

            run_command(
                [
                    sys.executable,
                    "services/data/src/connectors/comtrade.py",
                    "--access-mode", "preview",
                    "--reporter-code", "699",
                    "--period", "2024",
                    "--partner-code", "784",
                    "--cmd-code", HS_CODE,
                    "--flow-code", "X",
                    "--run-id", comtrade_run_id,
                    "--apply",
                ],
                env=runtime_env,
            )

            market = request_json(
                "GET",
                "/api/intelligence/trade-flows/markets",
                params={
                    "reporterCountry": "IN",
                    "flowDirection": "export",
                    "hsCode": HS_CODE,
                    "hsNomenclature": "HS2022",
                    "periodFrom": "2024-01-01",
                    "periodTo": "2024-12-31",
                    "currency": "USD",
                    "valueMetric": "trade_value",
                },
            )

            if len(
                [
                    item
                    for item in market["markets"]
                    if item["marketIso2"] == "AE"
                ]
            ) != 1:
                stop(
                    "India -> UAE HS380210 market fact "
                    "was not returned by the market API."
                )

            print(
                "PASS: Product classification -> "
                "India/UAE market intelligence."
            )

            source_path = (
                PROJECT_ROOT
                / "services/data/config/company_web_sources.example.json"
            )
            source_config = json.loads(
                source_path.read_text(encoding="utf-8")
            )

            for source in source_config["sources"]:
                for activity in source["activities"]:
                    activity["productId"] = product_id

            temp_config = temp / "company_web_product_scope.json"
            temp_config.write_text(
                json.dumps(source_config, indent=2),
                encoding="utf-8",
            )

            validated = load_config(temp_config)

            for source in validated["sources"]:
                result = execute_source(source, apply=True)
                print(
                    "PASS:",
                    result["sourceCode"],
                    "-> product-scoped activity.",
                )

            counterparties = request_json(
                "GET",
                "/api/intelligence/counterparties",
                params={
                    "productId": product_id,
                    "hsCode": HS_CODE,
                    "hsNomenclature": "HS2022",
                    "minimumConfidence": 0.90,
                },
            )

            if counterparties["pagination"]["total"] < 2:
                stop("Expected at least two product-scoped counterparties.")

            organizations = counterparties["organizations"]
            names = {
                str(organization["legalName"])
                for organization in organizations
            }

            expected_names = {
                "Jacobi Carbons India Private Limited",
                "Saiph Trading L.L.C-FZ",
            }

            if not expected_names.issubset(names):
                stop(
                    "Expected real companies were not both returned: "
                    + json.dumps(sorted(names))
                )

            for organization in organizations:
                for activity in organization["matchedActivities"]:
                    product = activity.get("product")
                    hs = activity.get("hsCode")

                    if not product or product.get("id") != product_id:
                        stop("Counterparty activity lost Product scope.")

                    if not hs or hs.get("code") != HS_CODE:
                        stop("Counterparty activity lost HS scope.")

                detail = request_json(
                    "GET",
                    f"/api/organizations/{organization['id']}/intelligence",
                )

                if detail["summary"]["evidenceCount"] < 1:
                    stop("Organization evidence coverage is missing.")

            print(
                "PASS: product-filtered counterparties "
                "and organization evidence."
            )

            with psycopg.connect(test_url) as connection:
                row = connection.execute(
                    """
                    SELECT COUNT(*)::int
                    FROM organization_trade_activities
                    WHERE
                        product_id = %s
                        AND status = 'active'
                    """,
                    (product_id,),
                ).fetchone()

            if row is None or row[0] < 2:
                stop("Product-scoped activities were not persisted.")

            production_after = baseline(production_url)

            if production_before != production_after:
                stop(
                    "Production database changed: "
                    + production_before
                    + " -> "
                    + production_after
                )

            print("")
            print("==================================================")
            print("OH14.6 PRODUCT-FIRST ACTIVATED CARBON PROOF PASSED")
            print("PRODUCT API PASS")
            print("PRODUCT -> HS2022 380210 PASS")
            print("INDIA -> UAE MARKET INTELLIGENCE PASS")
            print("JACOBI PRODUCT-SCOPED MANUFACTURING EVIDENCE PASS")
            print("SAIPH PRODUCT-SCOPED UAE SUPPLY EVIDENCE PASS")
            print("PRODUCT-FILTERED COUNTERPARTIES PASS")
            print("ORGANIZATION PROVENANCE PASS")
            print("MIGRATION HEAD REMAINS 015")
            print("PRODUCTION DATABASE UNCHANGED")
            print("==================================================")

            return 0

        finally:
            if api_process is not None and api_process.poll() is None:
                api_process.terminate()
                try:
                    api_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    api_process.kill()

            if api_stdout_handle is not None:
                api_stdout_handle.close()

            if api_stderr_handle is not None:
                api_stderr_handle.close()

            try:
                drop_database(production_url)
            except Exception as error:
                print(
                    "WARNING: unable to drop disposable database:",
                    error,
                )

            remove_new_storage_files(before_storage)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProofError as error:
        print("OH14.6 PROOF FAILED:", error, file=sys.stderr)
        raise SystemExit(1)
