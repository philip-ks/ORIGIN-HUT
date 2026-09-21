import type { FastifyInstance } from "fastify";

import { database } from "../lib/database.js";


export async function databaseRoutes(
  app: FastifyInstance
) {

  app.get(
    "/api/system/database",
    async () => {

      const summary = await database.query<{
        countries: string;
        currencies: string;
        hs_codes: string;
        trade_locations: string;
        organizations: string;
        products: string;
        data_sources: string;
        ingestion_runs: string;
        source_records: string;
      }>(`
        SELECT
          (SELECT COUNT(*) FROM countries)::text
            AS countries,

          (SELECT COUNT(*) FROM currencies)::text
            AS currencies,

          (SELECT COUNT(*) FROM hs_codes)::text
            AS hs_codes,

          (SELECT COUNT(*) FROM trade_locations)::text
            AS trade_locations,

          (SELECT COUNT(*) FROM organizations)::text
            AS organizations,

          (SELECT COUNT(*) FROM products)::text
            AS products,

          (SELECT COUNT(*) FROM data_sources)::text
            AS data_sources,

          (SELECT COUNT(*) FROM ingestion_runs)::text
            AS ingestion_runs,

          (SELECT COUNT(*) FROM source_records)::text
            AS source_records
      `);

      return {

        ok: true,

        database: "originhut",

        counts: summary.rows[0],

        timestamp: new Date().toISOString()

      };

    }
  );

}
