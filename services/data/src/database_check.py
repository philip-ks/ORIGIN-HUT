import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[3]

load_dotenv(ROOT / ".env")


database_url = os.environ["DATABASE_URL"]


with psycopg.connect(database_url) as connection:

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT
                current_database(),
                current_setting('server_version'),
                PostGIS_Version()
            """
        )

        database_name, postgres_version, postgis_version = (
            cursor.fetchone()
        )


        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            """
        )

        table_count = cursor.fetchone()[0]


        print(
            {
                "ok": True,
                "database": database_name,
                "postgres_version": postgres_version,
                "postgis_version": postgis_version,
                "public_table_count": table_count,
            }
        )
