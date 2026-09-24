from __future__ import annotations

import hashlib
import json
import os

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical_json_bytes(
    value: Any,
) -> bytes:

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")



def sha256_json(
    value: Any,
) -> str:

    return hashlib.sha256(
        canonical_json_bytes(
            value
        )
    ).hexdigest()


def sha256_file(
    path: str | Path,
    chunk_size: int = 1024 * 1024,
) -> str:

    source = Path(path)

    digest = hashlib.sha256()

    with source.open("rb") as handle:

        while True:

            chunk = handle.read(
                chunk_size
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def new_run_id(
    now: datetime | None = None,
) -> str:

    timestamp = (
        now
        or datetime.now(
            timezone.utc
        )
    )

    if timestamp.tzinfo is None:

        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

    timestamp = timestamp.astimezone(
        timezone.utc
    )

    return timestamp.strftime(
        "%Y%m%dT%H%M%S%fZ"
    )


def artifact_descriptor(
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:

    source = Path(path)

    if not source.is_file():

        raise FileNotFoundError(
            source
        )


    resolved = source.resolve()


    if root is None:

        display_path = source.as_posix()

    else:

        resolved_root = Path(
            root
        ).resolve()

        try:

            display_path = (
                resolved
                .relative_to(
                    resolved_root
                )
                .as_posix()
            )

        except ValueError as error:

            raise ValueError(
                "Artifact is outside the configured storage root."
            ) from error


    return {
        "path":
            display_path,

        "bytes":
            source.stat().st_size,

        "sha256":
            sha256_file(
                source
            ),
    }


def write_json_atomic(
    path: str | Path,
    payload: Any,
) -> Path:

    destination = Path(
        path
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    temporary = destination.with_name(
        destination.name
        + ".tmp"
    )


    data = (
        canonical_json_bytes(
            payload
        )
        + b"\n"
    )


    temporary.write_bytes(
        data
    )


    os.replace(
        temporary,
        destination,
    )


    return destination


def build_manifest(
    *,
    source_code: str,
    run_id: str,
    request: dict[str, Any],
    raw_artifacts: list[dict[str, Any]],
    parquet_artifacts: list[dict[str, Any]],
    record_count: int,
    schema_version: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:

    if not source_code.strip():

        raise ValueError(
            "source_code is required."
        )


    if not run_id.strip():

        raise ValueError(
            "run_id is required."
        )


    if record_count < 0:

        raise ValueError(
            "record_count cannot be negative."
        )


    return {
        "manifestVersion":
            "origin_hut_ingestion_manifest_v1",

        "sourceCode":
            source_code,

        "runId":
            run_id,

        "createdAt":
            datetime.now(
                timezone.utc
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            ),

        "schemaVersion":
            schema_version,

        "recordCount":
            record_count,

        "request":
            request,

        "rawArtifacts":
            raw_artifacts,

        "parquetArtifacts":
            parquet_artifacts,

        "metadata":
            metadata or {},
    }
