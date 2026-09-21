"""Origin Hut data service."""

from datetime import datetime, timezone


def main() -> None:
    print(
        {
            "ok": True,
            "service": "origin-hut-data",
            "platform": "Origin Hut",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


if __name__ == "__main__":
    main()
