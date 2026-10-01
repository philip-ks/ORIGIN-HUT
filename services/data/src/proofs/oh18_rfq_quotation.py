from __future__ import annotations

import json
import os
import subprocess
import tempfile

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from dotenv import load_dotenv

import oh17_landed_cost as base


SOURCE_FILE = Path(__file__).resolve()
PROJECT_ROOT = SOURCE_FILE.parents[4]

TEST_DATABASE_NAME = (
    "originhut_oh18_rfq_quotation_test_"
    + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    + "_"
    + str(os.getpid())
)

API_PORT = 4180
API_BASE = f"http://127.0.0.1:{API_PORT}"

base.TEST_DATABASE_NAME = TEST_DATABASE_NAME
base.API_PORT = API_PORT
base.API_BASE = API_BASE


ProofError = base.ProofError
stop = base.stop
database_url_with_name = base.database_url_with_name
resolve_executable = base.resolve_executable
run_command = base.run_command
production_baseline = base.production_baseline
create_database = base.create_database
drop_database = base.drop_database
wait_for_api = base.wait_for_api
request_json = base.request_json
assert_equal = base.assert_equal
assert_close = base.assert_close


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
           != "0000000030"
    ):
        stop(
            "Migration head is not 030."
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
                country_id = EXCLUDED.country_id,
                country_code = EXCLUDED.country_code,
                location_code = EXCLUDED.location_code,
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
                'oh18_rfq_quotation_proof_source',
                'OH18 RFQ Quotation Proof Source',
                'Origin Hut Proof',
                'commercial_workflow',
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
                'rfq_quotation_proof_evidence',
                repeat('e', 64),
                '{"synthetic":true,"purpose":"OH18 RFQ quotation architecture proof"}'::jsonb,
                '{"proofOnly":true}'::jsonb
            )
            RETURNING id::text
            """,
            (
                source_id,
                ingestion_run_id,
                (
                    "oh18-rfq-quotation-proof-"
                    + TEST_DATABASE_NAME
                ),
            ),
        ).fetchone()[0]

    return str(
        source_record_id
    )


def snapshot_json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        sort_keys=True,
        default=str,
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
        "=== OH18 RFQ + QUOTATION WORKFLOW PROOF ==="
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

    if branch != "work/oh18":
        stop(
            "OH18 proof must run from work/oh18."
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
            "Working tree must be clean before OH18 proof."
        )

    api_process: subprocess.Popen[str] | None = None
    api_stdout_handle = None
    api_stderr_handle = None

    with tempfile.TemporaryDirectory(
        prefix="originhut-oh18-"
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
                "PASS: API typecheck/build and web build."
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

            def create_org(
                legal_name: str,
                country: str,
                roles: list[str],
            ) -> dict[str, Any]:

                return request_json(
                    "POST",
                    "/api/organizations",
                    payload={
                        "legalName":
                            legal_name,
                        "country":
                            country,
                        "roles":
                            roles,
                        "metadata": {
                            "proof":
                                "OH18",
                        },
                    },
                )[
                    "organization"
                ]

            issuer = create_org(
                "OH18 Proof Issuer Private Limited",
                "IN",
                [
                    "supplier",
                    "exporter",
                ],
            )

            buyer = create_org(
                "OH18 Proof Buyer LLC",
                "AE",
                [
                    "buyer",
                    "importer",
                ],
            )

            supplier_a = create_org(
                "OH18 Proof Supplier A Private Limited",
                "IN",
                [
                    "manufacturer",
                    "supplier",
                    "exporter",
                ],
            )

            supplier_b = create_org(
                "OH18 Proof Supplier B Private Limited",
                "IN",
                [
                    "manufacturer",
                    "supplier",
                    "exporter",
                ],
            )

            product = request_json(
                "POST",
                "/api/products",
                payload={
                    "name":
                        "Activated Carbon",
                    "description":
                        "Generic activated carbon trade Product.",
                    "baseUomCode":
                        "KGM",
                    "metadata": {
                        "proof":
                            "OH18",
                    },
                },
            )[
                "product"
            ]

            product_id = str(
                product[
                    "id"
                ]
            )

            classification = request_json(
                "POST",
                "/api/intelligence/hs/classify",
                payload={
                    "description":
                        "Activated carbon used for purification.",
                    "productName":
                        "Activated Carbon",
                    "productId":
                        product_id,
                    "country":
                        "IN",
                    "limit":
                        5,
                },
            )

            request_json(
                "POST",
                (
                    "/api/intelligence/hs/classifications/"
                    + str(
                        classification[
                            "request"
                        ][
                            "id"
                        ]
                    )
                    + "/confirm"
                ),
                payload={
                    "hsCode":
                        "380210",
                    "productId":
                        product_id,
                    "notes":
                        "OH18 synthetic workflow proof.",
                },
            )

            print(
                "PASS: canonical Activated Carbon Product + HS2022 380210."
            )

            def create_manufacturer_product(
                supplier: dict[str, Any],
                suffix: str,
            ) -> dict[str, Any]:

                return request_json(
                    "POST",
                    (
                        f"/api/products/{product_id}"
                        "/manufacturer-products"
                    ),
                    payload={
                        "manufacturerId":
                            supplier[
                                "id"
                            ],
                        "originCountry":
                            "IN",
                        "name":
                            (
                                "OH18 Activated Carbon "
                                + suffix
                            ),
                        "brand":
                            (
                                "OH18 Carbon "
                                + suffix
                            ),
                        "grade":
                            suffix,
                        "sku":
                            (
                                "OH18-"
                                + suffix
                                + "-25"
                            ),
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
                )[
                    "manufacturerProduct"
                ]

            mp_a = create_manufacturer_product(
                supplier_a,
                "A1000",
            )

            mp_b = create_manufacturer_product(
                supplier_b,
                "B1000",
            )

            def create_packaging(
                manufacturer_product_id: str,
                suffix: str,
            ) -> dict[str, Any]:

                return request_json(
                    "POST",
                    (
                        "/api/manufacturer-products/"
                        + manufacturer_product_id
                        + "/packaging"
                    ),
                    payload={
                        "packageTypeCode":
                            "5H",
                        "name":
                            (
                                "25 kg woven bag "
                                + suffix
                            ),
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
                )[
                    "packaging"
                ]

            packaging_a = create_packaging(
                str(
                    mp_a[
                        "id"
                    ]
                ),
                "A",
            )

            packaging_b = create_packaging(
                str(
                    mp_b[
                        "id"
                    ]
                ),
                "B",
            )

            rfq = request_json(
                "POST",
                "/api/rfqs",
                payload={
                    "rfqReference":
                        "OH18-PROOF-RFQ-001",
                    "buyerId":
                        buyer[
                            "id"
                        ],
                    "destinationCountry":
                        "AE",
                    "destinationTradeLocationUnlocode":
                        "AEJEA",
                    "destinationPlaceText":
                        "Jebel Ali, United Arab Emirates",
                    "requestedCurrencyCode":
                        "USD",
                    "requestedIncotermEdition":
                        2020,
                    "requestedIncotermCode":
                        "CIF",
                    "incotermFlexible":
                        True,
                    "issueDate":
                        "2026-10-01",
                    "responseDueAt":
                        "2026-10-15T12:00:00+00:00",
                    "status":
                        "issued",
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
            )[
                "rfq"
            ]

            rfq_id = str(
                rfq[
                    "id"
                ]
            )

            rfq = request_json(
                "POST",
                (
                    "/api/rfqs/"
                    + rfq_id
                    + "/lines"
                ),
                payload={
                    "lineNumber":
                        1,
                    "productId":
                        product_id,
                    "requestedQuantity":
                        20,
                    "requestedUomCode":
                        "TNE",
                    "targetDeliveryDate":
                        "2026-11-15",
                    "specificationRequirements": {
                        "proofRequirement":
                            "synthetic activated carbon"
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
            )[
                "rfq"
            ]

            rfq_line_id = str(
                rfq[
                    "lines"
                ][
                    0
                ][
                    "id"
                ]
            )

            for supplier in [
                supplier_a,
                supplier_b,
            ]:

                rfq = request_json(
                    "POST",
                    (
                        "/api/rfqs/"
                        + rfq_id
                        + "/suppliers"
                    ),
                    payload={
                        "supplierId":
                            supplier[
                                "id"
                            ],
                        "status":
                            "invited",
                        "invitedAt":
                            "2026-10-01T12:00:00+00:00",
                        "responseDueAt":
                            "2026-10-15T12:00:00+00:00",
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
                )[
                    "rfq"
                ]

            invitations = {
                item[
                    "supplierId"
                ]:
                    item[
                        "id"
                    ]
                for item in rfq[
                    "suppliers"
                ]
            }

            assert_equal(
                len(
                    invitations
                ),
                2,
                "RFQ did not retain both supplier invitations.",
            )

            print(
                "PASS: RFQ + Product line + two supplier invitations."
            )

            def create_offer(
                supplier: dict[str, Any],
                manufacturer_product: dict[str, Any],
                packaging: dict[str, Any],
                reference: str,
                price: float,
            ) -> dict[str, Any]:

                return request_json(
                    "POST",
                    "/api/commercial-offers",
                    payload={
                        "sellerId":
                            supplier[
                                "id"
                            ],
                        "buyerId":
                            buyer[
                                "id"
                            ],
                        "manufacturerProductId":
                            manufacturer_product[
                                "id"
                            ],
                        "packagingConfigurationId":
                            packaging[
                                "id"
                            ],
                        "offerReference":
                            reference,
                        "status":
                            "active",
                        "unitPrice":
                            price,
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
                )[
                    "offer"
                ]

            offer_a = create_offer(
                supplier_a,
                mp_a,
                packaging_a,
                "OH18-PROOF-OFFER-A",
                1150,
            )

            offer_b = create_offer(
                supplier_b,
                mp_b,
                packaging_b,
                "OH18-PROOF-OFFER-B",
                1100,
            )

            def create_scenario(
                offer: dict[str, Any],
                reference: str,
                added_destination_cost: float,
            ) -> dict[str, Any]:

                scenario = request_json(
                    "POST",
                    "/api/landed-cost/scenarios",
                    payload={
                        "commercialOfferId":
                            offer[
                                "id"
                            ],
                        "scenarioReference":
                            reference,
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
                )[
                    "scenario"
                ]

                return request_json(
                    "POST",
                    (
                        "/api/landed-cost/scenarios/"
                        + str(
                            scenario[
                                "id"
                            ]
                        )
                        + "/components"
                    ),
                    payload={
                        "componentTypeCode":
                            "destination_handling",
                        "description":
                            "Synthetic destination cost",
                        "includedInOffer":
                            False,
                        "calculationMethod":
                            "fixed_amount",
                        "sourceAmount":
                            added_destination_cost,
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
                )[
                    "scenario"
                ]

            scenario_a = create_scenario(
                offer_a,
                "OH18-PROOF-LANDED-A",
                600,
            )

            scenario_b = create_scenario(
                offer_b,
                "OH18-PROOF-LANDED-B",
                2500,
            )

            assert_close(
                scenario_a[
                    "landedCostPerTargetUom"
                ],
                1180.0,
                "Supplier A landed cost is incorrect.",
            )

            assert_close(
                scenario_b[
                    "landedCostPerTargetUom"
                ],
                1225.0,
                "Supplier B landed cost is incorrect.",
            )

            print(
                "PASS: two supplier offers + normalized Landed Cost scenarios."
            )

            for (
                supplier,
                offer
            ) in [
                (
                    supplier_a,
                    offer_a,
                ),
                (
                    supplier_b,
                    offer_b,
                ),
            ]:

                request_json(
                    "POST",
                    (
                        "/api/rfqs/"
                        + rfq_id
                        + "/responses"
                    ),
                    payload={
                        "rfqLineId":
                            rfq_line_id,
                        "rfqSupplierId":
                            invitations[
                                supplier[
                                    "id"
                                ]
                            ],
                        "commercialOfferId":
                            offer[
                                "id"
                            ],
                        "status":
                            "submitted",
                        "respondedAt":
                            "2026-10-05T12:00:00+00:00",
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

            rfq_after_responses = request_json(
                "GET",
                (
                    "/api/rfqs/"
                    + rfq_id
                ),
            )[
                "rfq"
            ]

            assert_equal(
                rfq_after_responses[
                    "status"
                ],
                "responded",
                "RFQ status did not reach responded.",
            )

            comparison = request_json(
                "GET",
                (
                    "/api/rfqs/"
                    + rfq_id
                    + "/comparison"
                ),
            )

            responses = comparison[
                "lines"
            ][
                0
            ][
                "responses"
            ]

            assert_equal(
                len(
                    responses
                ),
                2,
                "RFQ comparison did not contain two responses.",
            )

            assert_equal(
                responses[
                    0
                ][
                    "supplierId"
                ],
                supplier_a[
                    "id"
                ],
                "RFQ comparison did not order lower landed cost first.",
            )

            assert_close(
                responses[
                    0
                ][
                    "landedCostPerRequestedUom"
                ],
                1180.0,
                "Supplier A normalized landed cost is incorrect.",
            )

            assert_close(
                responses[
                    1
                ][
                    "landedCostPerRequestedUom"
                ],
                1225.0,
                "Supplier B normalized landed cost is incorrect.",
            )

            if not all(
                item[
                    "isComparable"
                ]
                for item in responses
            ):
                stop(
                    "Both supplier responses should be comparison-ready."
                )

            print(
                "PASS: RFQ comparison proves lower offer price is not automatically lower landed cost."
            )

            rfq_snapshot = snapshot_json(
                rfq_after_responses
            )

            offer_a_snapshot = snapshot_json(
                request_json(
                    "GET",
                    (
                        "/api/commercial-offers/"
                        + str(
                            offer_a[
                                "id"
                            ]
                        )
                    ),
                )[
                    "offer"
                ]
            )

            offer_b_snapshot = snapshot_json(
                request_json(
                    "GET",
                    (
                        "/api/commercial-offers/"
                        + str(
                            offer_b[
                                "id"
                            ]
                        )
                    ),
                )[
                    "offer"
                ]
            )

            scenario_a_snapshot = snapshot_json(
                request_json(
                    "GET",
                    (
                        "/api/landed-cost/scenarios/"
                        + str(
                            scenario_a[
                                "id"
                            ]
                        )
                    ),
                )[
                    "scenario"
                ]
            )

            quotation = request_json(
                "POST",
                "/api/quotations",
                payload={
                    "quotationReference":
                        "OH18-PROOF-QUOTE-001",
                    "issuerId":
                        issuer[
                            "id"
                        ],
                    "customerId":
                        buyer[
                            "id"
                        ],
                    "sourceRfqId":
                        rfq_id,
                    "currencyCode":
                        "USD",
                    "issueDate":
                        "2026-10-06",
                    "validUntil":
                        "2026-10-31",
                    "status":
                        "issued",
                    "paymentTerms":
                        "Synthetic buyer quotation terms",
                    "incotermEdition":
                        2020,
                    "incotermCode":
                        "CIF",
                    "namedPlaceText":
                        "Jebel Ali, United Arab Emirates",
                    "namedTradeLocationUnlocode":
                        "AEJEA",
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
            )[
                "quotation"
            ]

            quotation = request_json(
                "POST",
                (
                    "/api/quotations/"
                    + str(
                        quotation[
                            "id"
                        ]
                    )
                    + "/lines"
                ),
                payload={
                    "lineNumber":
                        1,
                    "productId":
                        product_id,
                    "manufacturerProductId":
                        mp_a[
                            "id"
                        ],
                    "packagingConfigurationId":
                        packaging_a[
                            "id"
                        ],
                    "sourceRfqLineId":
                        rfq_line_id,
                    "sourceCommercialOfferId":
                        offer_a[
                            "id"
                        ],
                    "sourceLandedCostScenarioId":
                        scenario_a[
                            "id"
                        ],
                    "quantity":
                        20,
                    "uomCode":
                        "TNE",
                    "pricingMethod":
                        "markup_percent",
                    "pricingRate":
                        10,
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
            )[
                "quotation"
            ]

            line = quotation[
                "lines"
            ][
                0
            ]

            assert_close(
                line[
                    "internalCostUnitPrice"
                ],
                1180.0,
                "Quotation internal cost basis is incorrect.",
            )

            assert_close(
                line[
                    "quotedUnitPrice"
                ],
                1298.0,
                "10 percent markup quotation unit price is incorrect.",
            )

            assert_close(
                line[
                    "quotedLineTotal"
                ],
                25960.0,
                "Quotation line total is incorrect.",
            )

            assert_close(
                quotation[
                    "quotedTotal"
                ],
                25960.0,
                "Quotation total is incorrect.",
            )

            print(
                "PASS: buyer Quotation cites selected RFQ / Offer / Landed Cost basis with explicit markup."
            )

            assert_equal(
                snapshot_json(
                    request_json(
                        "GET",
                        (
                            "/api/rfqs/"
                            + rfq_id
                        ),
                    )[
                        "rfq"
                    ]
                ),
                rfq_snapshot,
                "RFQ changed while creating the Quotation.",
            )

            assert_equal(
                snapshot_json(
                    request_json(
                        "GET",
                        (
                            "/api/commercial-offers/"
                            + str(
                                offer_a[
                                    "id"
                                ]
                            )
                        ),
                    )[
                        "offer"
                    ]
                ),
                offer_a_snapshot,
                "Selected Commercial Offer changed while creating the Quotation.",
            )

            assert_equal(
                snapshot_json(
                    request_json(
                        "GET",
                        (
                            "/api/commercial-offers/"
                            + str(
                                offer_b[
                                    "id"
                                ]
                            )
                        ),
                    )[
                        "offer"
                    ]
                ),
                offer_b_snapshot,
                "Alternate Commercial Offer changed while creating the Quotation.",
            )

            assert_equal(
                snapshot_json(
                    request_json(
                        "GET",
                        (
                            "/api/landed-cost/scenarios/"
                            + str(
                                scenario_a[
                                    "id"
                                ]
                            )
                        ),
                    )[
                        "scenario"
                    ]
                ),
                scenario_a_snapshot,
                "Selected Landed Cost Scenario changed while creating the Quotation.",
            )

            print(
                "PASS: RFQ / Offers / Landed Cost remain immutable after Quotation."
            )

            with psycopg.connect(
                test_url
            ) as connection:

                counts = dict(
                    connection.execute(
                        """
                        SELECT
                            entity_type,
                            COUNT(*)::int
                        FROM entity_source_links
                        WHERE
                            source_record_id = %s
                            AND entity_type IN (
                                'rfq',
                                'rfq_line',
                                'rfq_supplier',
                                'rfq_response',
                                'quotation',
                                'quotation_line'
                            )
                        GROUP BY entity_type
                        """,
                        (
                            source_record_id,
                        ),
                    ).fetchall()
                )

            expected_counts = {
                "rfq":
                    1,
                "rfq_line":
                    1,
                "rfq_supplier":
                    2,
                "rfq_response":
                    2,
                "quotation":
                    1,
                "quotation_line":
                    1,
            }

            assert_equal(
                counts,
                expected_counts,
                "OH18 workflow provenance links are incomplete.",
            )

            print(
                "PASS: RFQ + supplier response + Quotation provenance."
            )

            production_after = production_baseline(
                production_url
            )

            assert_equal(
                production_after,
                production_before,
                "Production database changed during OH18 proof.",
            )

            print("")
            print(
                "=================================================="
            )
            print(
                "OH18 RFQ + QUOTATION WORKFLOW PROOF PASSED"
            )
            print(
                "SCHEMA HEAD 030 PASS"
            )
            print(
                "API + WEB BUILD PASS"
            )
            print(
                "ACTIVATED CARBON PRODUCT + HS380210 PASS"
            )
            print(
                "RFQ + PRODUCT LINE PASS"
            )
            print(
                "TWO SUPPLIER INVITATIONS PASS"
            )
            print(
                "TWO CANONICAL COMMERCIAL OFFER RESPONSES PASS"
            )
            print(
                "TWO LANDED COST SCENARIOS PASS"
            )
            print(
                "NORMALIZED RFQ OFFER COMPARISON PASS"
            )
            print(
                "LOWER OFFER != LOWER LANDED COST PASS"
            )
            print(
                "BUYER QUOTATION + EXPLICIT 10 PERCENT MARKUP PASS"
            )
            print(
                "RFQ / OFFER / LANDED COST IMMUTABILITY PASS"
            )
            print(
                "RFQ + QUOTATION PROVENANCE PASS"
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
            "OH18 PROOF FAILED:",
            error,
        )

        raise SystemExit(
            1
        )
