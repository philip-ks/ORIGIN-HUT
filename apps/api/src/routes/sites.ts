import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const uuidSchema =
  z.string()
    .uuid();


const countryIso2Schema =
  z.string()
    .trim()
    .length(2)
    .transform(
      value =>
        value.toUpperCase()
    );


const unlocodeSchema =
  z.string()
    .trim()
    .length(5)
    .transform(
      value =>
        value.toUpperCase()
    );


const siteParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const organizationParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const manufacturerProductParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const createSiteSchema =
  z.object({

    name: z
      .string()
      .trim()
      .min(1)
      .max(300),

    siteType: z
      .enum([
        "manufacturing",
        "packaging",
        "warehouse",
        "distribution_center",
        "office",
        "laboratory",
        "other"
      ]),

    country:
      countryIso2Schema
        .nullable()
        .optional(),

    unlocode:
      unlocodeSchema
        .nullable()
        .optional(),

    address: z
      .record(
        z.string(),
        z.unknown()
      )
      .default({}),

    latitude: z
      .number()
      .min(-90)
      .max(90)
      .nullable()
      .optional(),

    longitude: z
      .number()
      .min(-180)
      .max(180)
      .nullable()
      .optional(),

    sourceType: z
      .string()
      .trim()
      .min(1)
      .max(100)
      .default("manual"),

    sourceRecordId:
      uuidSchema
        .nullable()
        .optional(),

    confidence: z
      .number()
      .min(0)
      .max(1)
      .nullable()
      .optional(),

    identifiers: z
      .record(
        z.string(),
        z.unknown()
      )
      .default({}),

    metadata: z
      .record(
        z.string(),
        z.unknown()
      )
      .default({})

  })
  .superRefine(
    (
      value,
      ctx
    ) => {

      if (
        (
          value.latitude == null
        )
        !== (
          value.longitude == null
        )
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "longitude"
            ],
          message:
            "latitude and longitude must be supplied together."
        });

      }

    }
  );


const createProductSiteSchema =
  z.object({

    siteId:
      uuidSchema,

    relationshipType: z
      .enum([
        "manufactured_at",
        "packaged_at",
        "stored_at",
        "distributed_from"
      ]),

    validFrom: z
      .string()
      .date()
      .nullable()
      .optional(),

    validTo: z
      .string()
      .date()
      .nullable()
      .optional(),

    sourceType: z
      .string()
      .trim()
      .min(1)
      .max(100)
      .default("manual"),

    sourceRecordId:
      uuidSchema
        .nullable()
        .optional(),

    confidence: z
      .number()
      .min(0)
      .max(1)
      .nullable()
      .optional(),

    metadata: z
      .record(
        z.string(),
        z.unknown()
      )
      .default({})

  })
  .superRefine(
    (
      value,
      ctx
    ) => {

      if (
        value.validFrom
        && value.validTo
        && value.validTo
           < value.validFrom
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "validTo"
            ],
          message:
            "validTo cannot be earlier than validFrom."
        });

      }

    }
  );


function validationError(
  issues: z.core.$ZodIssue[]
) {

  return {

    ok: false,

    error:
      "invalid_request",

    issues:
      issues.map(
        issue => ({

          path:
            issue.path.join("."),

          message:
            issue.message

        })
      )

  };

}


async function organizationExists(
  id: string
): Promise<boolean> {

  const result =
    await database.query(
      `
      SELECT EXISTS (
        SELECT 1
        FROM organizations
        WHERE id = $1::uuid
      ) AS exists
      `,
      [
        id
      ]
    );


  return Boolean(
    result.rows[0]?.exists
  );

}


async function manufacturerProductExists(
  id: string
): Promise<boolean> {

  const result =
    await database.query(
      `
      SELECT EXISTS (
        SELECT 1
        FROM manufacturer_products
        WHERE
          id = $1::uuid
          AND status = 'active'
      ) AS exists
      `,
      [
        id
      ]
    );


  return Boolean(
    result.rows[0]?.exists
  );

}


async function resolveCountryId(
  iso2: string | null | undefined
) {

  if (!iso2) {
    return null;
  }


  const result =
    await database.query(
      `
      SELECT id::text
      FROM countries
      WHERE
        iso2 = $1
        AND is_active = TRUE
      `,
      [
        iso2
      ]
    );


  return (
    result.rows[0]?.id
    ?? null
  );

}


async function resolveTradeLocationId(
  unlocode: string | null | undefined
) {

  if (!unlocode) {
    return null;
  }


  const result =
    await database.query(
      `
      SELECT id::text
      FROM trade_locations
      WHERE
        unlocode = $1
        AND marked_for_deletion = FALSE
      `,
      [
        unlocode
      ]
    );


  return (
    result.rows[0]?.id
    ?? null
  );

}


async function loadSite(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        os.id::text,

        os.organization_id::text
          AS "organizationId",

        o.legal_name
          AS "organizationLegalName",

        os.name,

        os.site_type
          AS "siteType",

        c.iso2
          AS "countryIso2",

        c.iso3
          AS "countryIso3",

        c.name
          AS "countryName",

        tl.unlocode,

        tl.name
          AS "tradeLocationName",

        os.address,

        CASE
          WHEN os.geography IS NULL
          THEN NULL
          ELSE ST_Y(
            os.geography::geometry
          )
        END AS latitude,

        CASE
          WHEN os.geography IS NULL
          THEN NULL
          ELSE ST_X(
            os.geography::geometry
          )
        END AS longitude,

        os.status,

        os.source_type
          AS "sourceType",

        os.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        os.confidence::double precision
          AS confidence,

        os.identifiers,
        os.metadata,

        os.created_at
          AS "createdAt",

        os.updated_at
          AS "updatedAt"

      FROM organization_sites os

      JOIN organizations o
        ON o.id =
           os.organization_id

      LEFT JOIN countries c
        ON c.id =
           os.country_id

      LEFT JOIN trade_locations tl
        ON tl.id =
           os.trade_location_id

      WHERE os.id =
            $1::uuid
      `,
      [
        id
      ]
    );


  return (
    result.rows[0]
    ?? null
  );

}


export async function siteRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/organizations/:id/sites",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      if (
        !await organizationExists(
          params.data.id
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "organization_not_found"

        };

      }


      const result =
        await database.query(
          `
          SELECT id::text
          FROM organization_sites
          WHERE organization_id =
                $1::uuid
          ORDER BY
            status = 'active' DESC,
            site_type,
            name
          `,
          [
            params.data.id
          ]
        );


      const sites =
        [] as Record<
          string,
          unknown
        >[];


      for (
        const row
        of result.rows
      ) {

        const site =
          await loadSite(
            row.id
          );


        if (site) {
          sites.push(
            site
          );
        }

      }


      return {

        ok: true,

        organizationId:
          params.data.id,

        sites

      };

    }
  );


  app.post(
    "/api/organizations/:id/sites",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const body =
        createSiteSchema.safeParse(
          request.body
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      if (
        !await organizationExists(
          params.data.id
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "organization_not_found"

        };

      }


      const [
        countryId,
        tradeLocationId
      ] =
        await Promise.all([

          resolveCountryId(
            body.data.country
          ),

          resolveTradeLocationId(
            body.data.unlocode
          )

        ]);


      if (
        body.data.country
        && !countryId
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "country_not_found"

        };

      }


      if (
        body.data.unlocode
        && !tradeLocationId
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "trade_location_not_found"

        };

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO organization_sites (
                organization_id,
                name,
                site_type,
                country_id,
                trade_location_id,
                address,
                geography,
                status,
                source_type,
                canonical_source_record_id,
                confidence,
                identifiers,
                metadata
            )
            VALUES (
                $1::uuid,
                $2,
                $3,
                $4::uuid,
                $5::uuid,
                $6::jsonb,
                CASE
                  WHEN $7::double precision IS NULL
                  THEN NULL
                  ELSE ST_SetSRID(
                    ST_MakePoint(
                      $8::double precision,
                      $7::double precision
                    ),
                    4326
                  )::geography
                END,
                'active',
                $9,
                $10::uuid,
                $11,
                $12::jsonb,
                $13::jsonb
            )
            RETURNING id::text
            `,
            [
              params.data.id,
              body.data.name,
              body.data.siteType,
              countryId,
              tradeLocationId,
              JSON.stringify(
                body.data.address
              ),
              body.data.latitude ?? null,
              body.data.longitude ?? null,
              body.data.sourceType,
              body.data.sourceRecordId ?? null,
              body.data.confidence ?? null,
              JSON.stringify(
                body.data.identifiers
              ),
              JSON.stringify(
                body.data.metadata
              )
            ]
          );


        reply.code(201);


        return {

          ok: true,

          site:
            await loadSite(
              result.rows[0].id
            )

        };

      }
      catch (error) {

        const code =
          (
            error as {
              code?: string;
            }
          ).code;


        if (
          code === "23505"
        ) {

          reply.code(409);

          return {

            ok: false,

            error:
              "organization_site_conflict"

          };

        }


        throw error;

      }

    }
  );


  app.get(
    "/api/sites/:id",
    async (
      request,
      reply
    ) => {

      const params =
        siteParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const site =
        await loadSite(
          params.data.id
        );


      if (!site) {

        reply.code(404);

        return {

          ok: false,

          error:
            "site_not_found"

        };

      }


      return {

        ok: true,

        site

      };

    }
  );


  app.get(
    "/api/manufacturer-products/:id/sites",
    async (
      request,
      reply
    ) => {

      const params =
        manufacturerProductParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      if (
        !await manufacturerProductExists(
          params.data.id
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "manufacturer_product_not_found"

        };

      }


      const result =
        await database.query(
          `
          SELECT
            mps.id::text AS id,

            mps.relationship_type
              AS "relationshipType",

            mps.status,

            TO_CHAR(
              mps.valid_from,
              'YYYY-MM-DD'
            ) AS "validFrom",

            TO_CHAR(
              mps.valid_to,
              'YYYY-MM-DD'
            ) AS "validTo",

            mps.source_type
              AS "sourceType",

            mps.canonical_source_record_id::text
              AS "canonicalSourceRecordId",

            mps.confidence::double precision
              AS confidence,

            mps.metadata,

            os.id::text
              AS "siteId",

            os.name
              AS "siteName",

            os.site_type
              AS "siteType",

            o.id::text
              AS "siteOrganizationId",

            o.legal_name
              AS "siteOrganizationLegalName",

            c.iso2
              AS "siteCountryIso2",

            c.name
              AS "siteCountryName"

          FROM manufacturer_product_sites mps

          JOIN organization_sites os
            ON os.id =
               mps.organization_site_id

          JOIN organizations o
            ON o.id =
               os.organization_id

          LEFT JOIN countries c
            ON c.id =
               os.country_id

          WHERE
            mps.manufacturer_product_id =
              $1::uuid

          ORDER BY
            mps.status = 'active' DESC,
            mps.relationship_type,
            os.name
          `,
          [
            params.data.id
          ]
        );


      return {

        ok: true,

        manufacturerProductId:
          params.data.id,

        sites:
          result.rows

      };

    }
  );


  app.post(
    "/api/manufacturer-products/:id/sites",
    async (
      request,
      reply
    ) => {

      const params =
        manufacturerProductParamsSchema.safeParse(
          request.params
        );


      const body =
        createProductSiteSchema.safeParse(
          request.body
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      if (
        !await manufacturerProductExists(
          params.data.id
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "manufacturer_product_not_found"

        };

      }


      if (
        !await loadSite(
          body.data.siteId
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "site_not_found"

        };

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO manufacturer_product_sites (
                manufacturer_product_id,
                organization_site_id,
                relationship_type,
                status,
                valid_from,
                valid_to,
                source_type,
                canonical_source_record_id,
                confidence,
                metadata
            )
            VALUES (
                $1::uuid,
                $2::uuid,
                $3,
                'active',
                $4::date,
                $5::date,
                $6,
                $7::uuid,
                $8,
                $9::jsonb
            )
            RETURNING id::text
            `,
            [
              params.data.id,
              body.data.siteId,
              body.data.relationshipType,
              body.data.validFrom ?? null,
              body.data.validTo ?? null,
              body.data.sourceType,
              body.data.sourceRecordId ?? null,
              body.data.confidence ?? null,
              JSON.stringify(
                body.data.metadata
              )
            ]
          );


        reply.code(201);


        return {

          ok: true,

          manufacturerProductSiteId:
            result.rows[0].id

        };

      }
      catch (error) {

        const code =
          (
            error as {
              code?: string;
            }
          ).code;


        if (
          code === "23505"
        ) {

          reply.code(409);

          return {

            ok: false,

            error:
              "manufacturer_product_site_conflict"

          };

        }


        throw error;

      }

    }
  );

}
