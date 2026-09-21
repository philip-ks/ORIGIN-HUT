import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const paginationSchema = z.object({

  limit: z.coerce
    .number()
    .int()
    .min(1)
    .max(200)
    .default(50),

  offset: z.coerce
    .number()
    .int()
    .min(0)
    .default(0)

});


const countriesQuerySchema =
  paginationSchema.extend({

    q: z
      .string()
      .trim()
      .min(1)
      .optional()

  });


const currenciesQuerySchema =
  paginationSchema.extend({

    q: z
      .string()
      .trim()
      .min(1)
      .optional()

  });


const locationsQuerySchema =
  paginationSchema.extend({

    q: z
      .string()
      .trim()
      .min(1)
      .optional(),

    country: z
      .string()
      .trim()
      .length(2)
      .transform(
        value => value.toUpperCase()
      )
      .optional()

  });


const hsQuerySchema =
  paginationSchema.extend({

    q: z
      .string()
      .trim()
      .min(1)
      .optional(),

    level: z.coerce
      .number()
      .int()
      .refine(
        value =>
          value === 2
          || value === 4
          || value === 6,
        {
          message:
            "HS level must be 2, 4 or 6."
        }
      )
      .optional()

  });


const hsSearchQuerySchema =
  paginationSchema.extend({

    q: z
      .string()
      .trim()
      .min(
        2,
        "Search requires at least 2 characters."
      ),

    level: z.coerce
      .number()
      .int()
      .refine(
        value =>
          value === 2
          || value === 4
          || value === 6,
        {
          message:
            "HS level must be 2, 4 or 6."
        }
      )
      .optional()

  });


const hsCodeParamsSchema =
  z.object({

    code: z
      .string()
      .trim()
      .min(2)
      .max(20)

  });


const locationParamsSchema =
  z.object({

    unlocode: z
      .string()
      .trim()
      .length(5)
      .transform(
        value => value.toUpperCase()
      )

  });


const countryParamsSchema =
  z.object({

    iso2: z
      .string()
      .trim()
      .length(2)
      .transform(
        value => value.toUpperCase()
      )

  });


function validationError(
  issues: z.core.$ZodIssue[]
) {

  return {

    ok: false,

    error: "invalid_request",

    issues: issues.map(
      issue => ({

        path:
          issue.path.join("."),

        message:
          issue.message

      })
    )

  };

}


export async function referenceRoutes(
  app: FastifyInstance
) {


  // ==========================================================
  // REFERENCE CATALOGUE
  // ==========================================================

  app.get(
    "/api/reference",
    async () => {

      const result =
        await database.query(`
          SELECT

            (
              SELECT COUNT(*)::int
              FROM countries
            ) AS countries,

            (
              SELECT COUNT(*)::int
              FROM currencies
            ) AS currencies,

            (
              SELECT COUNT(*)::int
              FROM trade_locations
              WHERE marked_for_deletion = FALSE
            ) AS trade_locations,

            (
              SELECT COUNT(*)::int
              FROM hs_codes
              WHERE nomenclature = 'HS2022'
            ) AS hs2022_codes
        `);

      return {

        ok: true,

        service:
          "origin-hut-reference",

        datasets: result.rows[0],

        endpoints: {

          countries:
            "/api/reference/countries",

          currencies:
            "/api/reference/currencies",

          locations:
            "/api/reference/locations",

          hs:
            "/api/reference/hs",

          hsSearch:
            "/api/reference/hs/search?q=coffee",

          hsCode:
            "/api/reference/hs/300490"

        },

        timestamp:
          new Date().toISOString()

      };

    }
  );


  // ==========================================================
  // COUNTRIES
  // ==========================================================

  app.get(
    "/api/reference/countries",
    async (
      request,
      reply
    ) => {

      const parsed =
        countriesQuerySchema.safeParse(
          request.query
        );

      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }

      const {
        q,
        limit,
        offset
      } = parsed.data;


      const parameters = [
        q ?? null,
        limit,
        offset
      ];


      const [
        rows,
        count
      ] = await Promise.all([

        database.query(
          `
          SELECT
            id::text,
            iso2,
            iso3,
            numeric_code,
            name,
            official_name,
            region,
            subregion,
            is_active
          FROM countries
          WHERE
            (
              $1::text IS NULL
              OR iso2 ILIKE '%' || $1 || '%'
              OR iso3 ILIKE '%' || $1 || '%'
              OR name ILIKE '%' || $1 || '%'
              OR official_name ILIKE '%' || $1 || '%'
            )
          ORDER BY name
          LIMIT $2
          OFFSET $3
          `,
          parameters
        ),

        database.query(
          `
          SELECT COUNT(*)::int AS total
          FROM countries
          WHERE
            (
              $1::text IS NULL
              OR iso2 ILIKE '%' || $1 || '%'
              OR iso3 ILIKE '%' || $1 || '%'
              OR name ILIKE '%' || $1 || '%'
              OR official_name ILIKE '%' || $1 || '%'
            )
          `,
          [
            q ?? null
          ]
        )

      ]);


      return {

        ok: true,

        data:
          rows.rows,

        pagination: {

          total:
            count.rows[0].total,

          limit,

          offset

        }

      };

    }
  );


  app.get(
    "/api/reference/countries/:iso2",
    async (
      request,
      reply
    ) => {

      const parsed =
        countryParamsSchema.safeParse(
          request.params
        );

      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const result =
        await database.query(
          `
          SELECT
            c.id::text,
            c.iso2,
            c.iso3,
            c.numeric_code,
            c.name,
            c.official_name,
            c.region,
            c.subregion,
            c.is_active,

            COALESCE(
              jsonb_agg(
                DISTINCT jsonb_build_object(
                  'code',
                  cur.code,
                  'name',
                  cur.name,
                  'numericCode',
                  cur.numeric_code,
                  'decimalPlaces',
                  cur.decimal_places,
                  'isPrimary',
                  cc.is_primary,
                  'isFund',
                  cc.is_fund
                )
              )
              FILTER (
                WHERE cur.id IS NOT NULL
              ),
              '[]'::jsonb
            ) AS currencies

          FROM countries c

          LEFT JOIN country_currencies cc
            ON cc.country_id = c.id

          LEFT JOIN currencies cur
            ON cur.id = cc.currency_id

          WHERE c.iso2 = $1

          GROUP BY c.id
          `,
          [
            parsed.data.iso2
          ]
        );


      if (!result.rows[0]) {

        reply.code(404);

        return {

          ok: false,

          error:
            "country_not_found"

        };

      }


      return {

        ok: true,

        data:
          result.rows[0]

      };

    }
  );


  // ==========================================================
  // CURRENCIES
  // ==========================================================

  app.get(
    "/api/reference/currencies",
    async (
      request,
      reply
    ) => {

      const parsed =
        currenciesQuerySchema.safeParse(
          request.query
        );

      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const {
        q,
        limit,
        offset
      } = parsed.data;


      const [
        rows,
        count
      ] = await Promise.all([

        database.query(
          `
          SELECT
            cur.id::text,
            cur.code,
            cur.numeric_code,
            cur.name,
            cur.symbol,
            cur.decimal_places,
            cur.is_active,

            COALESCE(
              jsonb_agg(
                DISTINCT jsonb_build_object(
                  'iso2',
                  c.iso2,
                  'name',
                  c.name,
                  'isPrimary',
                  cc.is_primary,
                  'isFund',
                  cc.is_fund
                )
              )
              FILTER (
                WHERE c.id IS NOT NULL
              ),
              '[]'::jsonb
            ) AS countries

          FROM currencies cur

          LEFT JOIN country_currencies cc
            ON cc.currency_id = cur.id

          LEFT JOIN countries c
            ON c.id = cc.country_id

          WHERE
            (
              $1::text IS NULL
              OR cur.code ILIKE '%' || $1 || '%'
              OR cur.name ILIKE '%' || $1 || '%'
              OR cur.numeric_code ILIKE '%' || $1 || '%'
            )

          GROUP BY cur.id

          ORDER BY cur.code

          LIMIT $2
          OFFSET $3
          `,
          [
            q ?? null,
            limit,
            offset
          ]
        ),

        database.query(
          `
          SELECT COUNT(*)::int AS total
          FROM currencies
          WHERE
            (
              $1::text IS NULL
              OR code ILIKE '%' || $1 || '%'
              OR name ILIKE '%' || $1 || '%'
              OR numeric_code ILIKE '%' || $1 || '%'
            )
          `,
          [
            q ?? null
          ]
        )

      ]);


      return {

        ok: true,

        data:
          rows.rows,

        pagination: {

          total:
            count.rows[0].total,

          limit,

          offset

        }

      };

    }
  );


  // ==========================================================
  // TRADE LOCATIONS / UNLOCODE
  // ==========================================================

  app.get(
    "/api/reference/locations",
    async (
      request,
      reply
    ) => {

      const parsed =
        locationsQuerySchema.safeParse(
          request.query
        );

      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const {
        q,
        country,
        limit,
        offset
      } = parsed.data;


      const [
        rows,
        count
      ] = await Promise.all([

        database.query(
          `
          SELECT
            t.id::text,
            t.unlocode,
            t.country_code,
            t.location_code,
            t.name,
            t.name_without_diacritics,
            t.subdivision_code,
            t.function_codes,
            t.status,
            t.iata_code,
            t.release_date_code,
            t.latitude,
            t.longitude,
            t.source_release,
            t.is_active,

            c.iso2 AS country_iso2,
            c.iso3 AS country_iso3,
            c.name AS country_name

          FROM trade_locations t

          LEFT JOIN countries c
            ON c.id = t.country_id

          WHERE
            t.marked_for_deletion = FALSE

            AND (
              $1::text IS NULL
              OR t.country_code = $1
            )

            AND (
              $2::text IS NULL
              OR t.unlocode ILIKE '%' || $2 || '%'
              OR t.name ILIKE '%' || $2 || '%'
              OR t.name_without_diacritics
                    ILIKE '%' || $2 || '%'
              OR t.iata_code ILIKE '%' || $2 || '%'
            )

          ORDER BY
            t.country_code,
            t.name,
            t.unlocode

          LIMIT $3
          OFFSET $4
          `,
          [
            country ?? null,
            q ?? null,
            limit,
            offset
          ]
        ),

        database.query(
          `
          SELECT COUNT(*)::int AS total
          FROM trade_locations t
          WHERE
            t.marked_for_deletion = FALSE

            AND (
              $1::text IS NULL
              OR t.country_code = $1
            )

            AND (
              $2::text IS NULL
              OR t.unlocode ILIKE '%' || $2 || '%'
              OR t.name ILIKE '%' || $2 || '%'
              OR t.name_without_diacritics
                    ILIKE '%' || $2 || '%'
              OR t.iata_code ILIKE '%' || $2 || '%'
            )
          `,
          [
            country ?? null,
            q ?? null
          ]
        )

      ]);


      return {

        ok: true,

        data:
          rows.rows,

        pagination: {

          total:
            count.rows[0].total,

          limit,

          offset

        }

      };

    }
  );


  app.get(
    "/api/reference/locations/:unlocode",
    async (
      request,
      reply
    ) => {

      const parsed =
        locationParamsSchema.safeParse(
          request.params
        );

      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const result =
        await database.query(
          `
          SELECT
            t.id::text,
            t.unlocode,
            t.country_code,
            t.location_code,
            t.name,
            t.name_without_diacritics,
            t.subdivision_code,
            t.function_codes,
            t.status,
            t.iata_code,
            t.release_date_code,
            t.latitude,
            t.longitude,
            t.remarks,
            t.source_release,
            t.is_active,
            t.marked_for_deletion,
            t.metadata,

            c.iso2 AS country_iso2,
            c.iso3 AS country_iso3,
            c.name AS country_name,

            sr.id::text
              AS source_record_id,

            sr.content_hash
              AS source_content_hash,

            sr.fetched_at
              AS source_fetched_at,

            ds.code
              AS source_code,

            ds.name
              AS source_name,

            ds.provider
              AS source_provider,

            ds.base_url
              AS source_url

          FROM trade_locations t

          LEFT JOIN countries c
            ON c.id = t.country_id

          LEFT JOIN source_records sr
            ON sr.id =
               t.canonical_source_record_id

          LEFT JOIN data_sources ds
            ON ds.id =
               sr.data_source_id

          WHERE t.unlocode = $1
          `,
          [
            parsed.data.unlocode
          ]
        );


      if (!result.rows[0]) {

        reply.code(404);

        return {

          ok: false,

          error:
            "location_not_found"

        };

      }


      return {

        ok: true,

        data:
          result.rows[0]

      };

    }
  );


  // ==========================================================
  // HS 2022
  // ==========================================================

  app.get(
    "/api/reference/hs",
    async (
      request,
      reply
    ) => {

      const parsed =
        hsQuerySchema.safeParse(
          request.query
        );

      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const {
        q,
        level,
        limit,
        offset
      } = parsed.data;


      const [
        rows,
        count
      ] = await Promise.all([

        database.query(
          `
          SELECT
            h.id::text,
            h.code,
            h.nomenclature,
            h.level,
            h.description,
            h.is_leaf,
            h.standard_unit,
            p.code AS parent_code,
            p.description AS parent_description

          FROM hs_codes h

          LEFT JOIN hs_codes p
            ON p.id = h.parent_id

          WHERE
            h.nomenclature = 'HS2022'

            AND (
              $1::smallint IS NULL
              OR h.level = $1
            )

            AND (
              $2::text IS NULL
              OR h.code ILIKE $2 || '%'
              OR h.description
                    ILIKE '%' || $2 || '%'
            )

          ORDER BY h.code

          LIMIT $3
          OFFSET $4
          `,
          [
            level ?? null,
            q ?? null,
            limit,
            offset
          ]
        ),

        database.query(
          `
          SELECT COUNT(*)::int AS total
          FROM hs_codes h
          WHERE
            h.nomenclature = 'HS2022'

            AND (
              $1::smallint IS NULL
              OR h.level = $1
            )

            AND (
              $2::text IS NULL
              OR h.code ILIKE $2 || '%'
              OR h.description
                    ILIKE '%' || $2 || '%'
            )
          `,
          [
            level ?? null,
            q ?? null
          ]
        )

      ]);


      return {

        ok: true,

        nomenclature:
          "HS2022",

        data:
          rows.rows,

        pagination: {

          total:
            count.rows[0].total,

          limit,

          offset

        }

      };

    }
  );


  // Keep this static route before /:code for clarity.
  app.get(
    "/api/reference/hs/search",
    async (
      request,
      reply
    ) => {

      const parsed =
        hsSearchQuerySchema.safeParse(
          request.query
        );

      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const {
        q,
        level,
        limit,
        offset
      } = parsed.data;


      const result =
        await database.query(
          `
          SELECT
            h.id::text,
            h.code,
            h.nomenclature,
            h.level,
            h.description,
            h.is_leaf,
            h.standard_unit,
            p.code AS parent_code,
            p.description AS parent_description

          FROM hs_codes h

          LEFT JOIN hs_codes p
            ON p.id = h.parent_id

          WHERE
            h.nomenclature = 'HS2022'

            AND (
              $1::smallint IS NULL
              OR h.level = $1
            )

            AND (
              h.code ILIKE $2 || '%'
              OR h.description
                    ILIKE '%' || $2 || '%'
            )

          ORDER BY

            CASE
              WHEN h.code = $2
                THEN 0

              WHEN h.code LIKE $2 || '%'
                THEN 1

              ELSE 2
            END,

            h.code

          LIMIT $3
          OFFSET $4
          `,
          [
            level ?? null,
            q,
            limit,
            offset
          ]
        );


      return {

        ok: true,

        query:
          q,

        nomenclature:
          "HS2022",

        count:
          result.rows.length,

        data:
          result.rows,

        pagination: {

          limit,

          offset

        }

      };

    }
  );


  app.get(
    "/api/reference/hs/:code",
    async (
      request,
      reply
    ) => {

      const parsed =
        hsCodeParamsSchema.safeParse(
          request.params
        );

      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const normalizedCode =
        parsed.data.code.replace(
          /\D/g,
          ""
        );


      if (
        ![
          2,
          4,
          6
        ].includes(
          normalizedCode.length
        )
      ) {

        reply.code(400);

        return {

          ok: false,

          error:
            "invalid_hs_code",

          message:
            "Origin Hut currently accepts "
            + "2, 4 or 6 digit HS2022 codes."

        };

      }


      const result =
        await database.query(
          `
          SELECT

            h.id::text,
            h.code,
            h.nomenclature,
            h.level,
            h.description,
            h.notes,
            TO_CHAR(
              h.valid_from,
              'YYYY-MM-DD'
            ) AS valid_from,

            TO_CHAR(
              h.valid_to,
              'YYYY-MM-DD'
            ) AS valid_to,
            h.is_leaf,
            h.standard_unit,
            h.metadata,

            p.id::text
              AS parent_id,

            p.code
              AS parent_code,

            p.description
              AS parent_description,

            gp.code
              AS grandparent_code,

            gp.description
              AS grandparent_description,

            sr.id::text
              AS source_record_id,

            sr.content_hash
              AS source_content_hash,

            sr.fetched_at
              AS source_fetched_at,

            ds.code
              AS source_code,

            ds.name
              AS source_name,

            ds.provider
              AS source_provider,

            ds.base_url
              AS source_url

          FROM hs_codes h

          LEFT JOIN hs_codes p
            ON p.id = h.parent_id

          LEFT JOIN hs_codes gp
            ON gp.id = p.parent_id

          LEFT JOIN source_records sr
            ON sr.id =
               h.canonical_source_record_id

          LEFT JOIN data_sources ds
            ON ds.id =
               sr.data_source_id

          WHERE
            h.nomenclature = 'HS2022'
            AND h.code = $1
          `,
          [
            normalizedCode
          ]
        );


      const row =
        result.rows[0];


      if (!row) {

        reply.code(404);

        return {

          ok: false,

          error:
            "hs_code_not_found",

          code:
            normalizedCode

        };

      }


      const children =
        await database.query(
          `
          SELECT
            code,
            level,
            description,
            is_leaf,
            standard_unit
          FROM hs_codes
          WHERE
            nomenclature = 'HS2022'
            AND parent_id = $1::uuid
          ORDER BY code
          `,
          [
            row.id
          ]
        );


      const selfReference = {

        code:
          row.code,

        description:
          row.description,

        level:
          row.level

      };


      let parent = null;

      let chapter = null;


      if (row.level === 2) {

        chapter =
          selfReference;

      }


      if (row.level === 4) {

        parent = {

          code:
            row.parent_code,

          description:
            row.parent_description,

          level:
            2

        };

        chapter =
          parent;

      }


      if (row.level === 6) {

        parent = {

          code:
            row.parent_code,

          description:
            row.parent_description,

          level:
            4

        };

        chapter = {

          code:
            row.grandparent_code,

          description:
            row.grandparent_description,

          level:
            2

        };

      }


      return {

        ok: true,

        data: {

          id:
            row.id,

          code:
            row.code,

          nomenclature:
            row.nomenclature,

          level:
            row.level,

          description:
            row.description,

          notes:
            row.notes,

          validFrom:
            row.valid_from,

          validTo:
            row.valid_to,

          isLeaf:
            row.is_leaf,

          standardUnit:
            row.standard_unit,

          metadata:
            row.metadata,

          hierarchy: {

            chapter,

            parent,

            children:
              children.rows

          },

          provenance: {

            available:
              Boolean(
                row.source_record_id
              ),

            sourceRecordId:
              row.source_record_id,

            contentHash:
              row.source_content_hash,

            fetchedAt:
              row.source_fetched_at,

            source: {

              code:
                row.source_code,

              name:
                row.source_name,

              provider:
                row.source_provider,

              url:
                row.source_url

            }

          }

        }

      };

    }
  );


}
