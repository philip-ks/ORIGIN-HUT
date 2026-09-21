from __future__ import annotations

import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup


REQUIRED_HEADERS = {
    "country or area",
    "m49 code",
    "iso-alpha2 code",
    "iso-alpha3 code",
}


def clean(value: str) -> str:
    return " ".join(
        value.replace("\xa0", " ").split()
    ).strip()


def canonical(value: str) -> str:
    return clean(value).casefold()


def parse_table(table) -> tuple[list[str], list[dict[str, str]]]:

    all_rows = table.find_all("tr")

    for header_index, row in enumerate(all_rows):

        cells = row.find_all(
            ["th", "td"],
            recursive=True,
        )

        headers = [
            clean(
                cell.get_text(
                    " ",
                    strip=True,
                )
            )
            for cell in cells
        ]

        canonical_headers = {
            canonical(header)
            for header in headers
        }

        if not REQUIRED_HEADERS.issubset(
            canonical_headers
        ):
            continue

        records: list[dict[str, str]] = []

        for data_row in all_rows[
            header_index + 1:
        ]:

            data_cells = data_row.find_all(
                ["th", "td"],
                recursive=True,
            )

            values = [
                clean(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in data_cells
            ]

            if len(values) != len(headers):
                continue

            record = dict(
                zip(
                    headers,
                    values,
                )
            )

            normalized = {
                canonical(key): value
                for key, value in record.items()
            }

            country = normalized.get(
                "country or area",
                "",
            )

            m49 = normalized.get(
                "m49 code",
                "",
            )

            iso2 = normalized.get(
                "iso-alpha2 code",
                "",
            ).upper()

            iso3 = normalized.get(
                "iso-alpha3 code",
                "",
            ).upper()

            if (
                country
                and len(m49) == 3
                and m49.isdigit()
                and len(iso2) == 2
                and len(iso3) == 3
            ):
                records.append(record)

        return headers, records

    return [], []


def main() -> None:

    snapshot_path = Path(
        sys.argv[1]
    ).resolve()

    html = snapshot_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    tables = soup.find_all("table")

    print(
        json.dumps(
            {
                "snapshot": str(snapshot_path),
                "html_characters": len(html),
                "tables_found": len(tables),
            },
            indent=2,
        )
    )

    candidates = []

    for index, table in enumerate(tables):

        headers, rows = parse_table(
            table
        )

        if rows:

            india = None

            for row in rows:

                normalized = {
                    canonical(key): value
                    for key, value in row.items()
                }

                if (
                    normalized.get(
                        "iso-alpha2 code",
                        "",
                    ).upper()
                    == "IN"
                    and normalized.get(
                        "iso-alpha3 code",
                        "",
                    ).upper()
                    == "IND"
                ):
                    india = normalized
                    break

            candidates.append(
                {
                    "table_index": index,
                    "headers": headers,
                    "record_count": len(rows),
                    "india": india,
                    "rows": rows,
                }
            )

    print()
    print(
        f"M49 candidate tables found: {len(candidates)}"
    )

    for candidate in candidates:

        print()
        print(
            f"Table {candidate['table_index']}: "
            f"{candidate['record_count']} valid records"
        )

        print(
            "Headers:",
            candidate["headers"],
        )

        if candidate["india"]:

            print(
                "India record:",
                candidate["india"],
            )

    english_candidate = next(
        (
            candidate
            for candidate in candidates
            if candidate["india"]
            and candidate["india"].get(
                "country or area"
            )
            == "India"
        ),
        None,
    )

    if english_candidate is None:
        raise RuntimeError(
            "An English UN M49 table containing India / IN / IND "
            "could not be identified."
        )

    if (
        english_candidate["record_count"]
        < 200
    ):
        raise RuntimeError(
            "UN M49 parser found fewer than 200 valid "
            "country/area records."
        )

    print()
    print(
        "PASS: English UN M49 table identified."
    )

    print(
        f"Valid country/area records: "
        f"{english_candidate['record_count']}"
    )

    first_five = []

    for row in english_candidate[
        "rows"
    ][:5]:

        normalized = {
            canonical(key): value
            for key, value in row.items()
        }

        first_five.append(
            {
                "country": normalized.get(
                    "country or area"
                ),
                "m49": normalized.get(
                    "m49 code"
                ),
                "iso2": normalized.get(
                    "iso-alpha2 code"
                ),
                "iso3": normalized.get(
                    "iso-alpha3 code"
                ),
            }
        )

    print()
    print("First five records:")

    print(
        json.dumps(
            first_five,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
