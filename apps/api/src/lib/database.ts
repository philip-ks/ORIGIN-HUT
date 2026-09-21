import pg from "pg";

import { env } from "../config/env.js";

const { Pool } = pg;

export const database = new Pool({

  connectionString: env.DATABASE_URL,

  max: 10,

  idleTimeoutMillis: 30_000,

  connectionTimeoutMillis: 5_000

});


export type DatabaseHealth = {

  connected: boolean;

  database?: string;

  postgresVersion?: string;

  postgisVersion?: string;

  error?: string;

};


export async function checkDatabase(): Promise<DatabaseHealth> {

  try {

    const result = await database.query<{
      database: string;
      postgres_version: string;
      postgis_version: string;
    }>(`
      SELECT
        current_database() AS database,
        current_setting('server_version') AS postgres_version,
        PostGIS_Version() AS postgis_version
    `);

    const row = result.rows[0];

    return {

      connected: true,

      database: row.database,

      postgresVersion: row.postgres_version,

      postgisVersion: row.postgis_version

    };

  }
  catch (error) {

    return {

      connected: false,

      error:
        error instanceof Error
          ? error.message
          : "Unknown database error"

    };

  }

}
