import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const jsonObjectSchema =
  z.record(
    z.string(),
    z.unknown()
  );


const productParamsSchema =
  z.object({

    id: z
      .string()
      .uuid()

  });


const productListQuerySchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .optional(),

    manufacturerId: z
      .string()
      .uuid()
      .optional(),

    active: z
      .enum([
        "true",
        "false"
      ])
      .transform(
        value =>
          value === "true"
      )
      .optional(),

    limit: z.coerce
      .number()
      .int()
      .min(1)
      .max(100)
      .default(50),

    offset: z.coerce
      .number()
      .int()
      .min(0)
      .default(0)

  });


const createProductSchema =
  z.object({

    manufacturerId: z
      .string()
      .uuid()
      .nullable()
      .optional(),

    name: z
      .string()
      .trim()
      .min(1)
      .max(300),

    brand: z
      .string()
      .trim()
      .min(1)
      .max(300)
      .nullable()
      .optional(),

    sku: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .nullable()
      .optional(),

    gtin: z
      .string()
      .trim()
      .min(1)
      .max(64)
      .nullable()
      .optional(),

    description: z
      .string()
      .trim()
      .min(1)
      .max(5000)
      .nullable()
      .optional(),

    attributes:
      jsonObjectSchema
        .default({}),

    metadata:
      jsonObjectSchema
        .default({}),

    isActive: z
      .boolean()
      .default(true)

  });


const updateProductSchema =
  z.object({

    manufacturerId: z
      .string()
      .uuid()
      .nullable()
      .optional(),

    name: z
      .string()
      .trim()
      .min(1)
      .max(300)
      .optional(),

    brand: z
      .string()
      .trim()
      .min(1)
      .max(300)
      .nullable()
      .optional(),

    sku: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .nullable()
      .optional(),

    gtin: z
      .string()
      .trim()
      .min(1)
      .max(64)
      .nullable()
      .optional(),

    description: z
      .string()
      .trim()
      .min(1)
      .max(5000)
      .nullable()
      .optional(),

    attributes:
      jsonObjectSchema
        .optional(),

    metadata:
      jsonObjectSchema
        .optional(),

    isActive: z
      .boolean()
      .optional()

  })
  .refine(
    value =>
      Object.keys(value).length > 0,
    {
      message:
        "At least one product field is required."
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


async function manufacturerExists(
  id: string
) {

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


async function loadProduct(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        p.id::text AS id,
        p.manufacturer_id::text
          AS "manufacturerId",
        p.name,
        p.brand,
        p.sku,
        p.gtin,
        p.description,
        p.attributes,
        p.metadata,
        p.is_active
          AS "isActive",
        p.created_at
          AS "createdAt",
        p.updated_at
          AS "updatedAt",

        o.legal_name
          AS "manufacturerLegalName",

        o.trading_name
          AS "manufacturerTradingName",

        (
          SELECT COUNT(*)::int
          FROM product_hs_classifications phc
          WHERE phc.product_id = p.id
        ) AS "classificationCount",

        (
          SELECT COUNT(*)::int
          FROM hs_classification_requests hcr
          WHERE hcr.product_id = p.id
        ) AS "classificationRequestCount"

      FROM products p

      LEFT JOIN organizations o
        ON o.id =
           p.manufacturer_id

      WHERE p.id =
            $1::uuid
      `,
      [
        id
      ]
    );


  return result.rows[0] ?? null;

}


export async function productRoutes(
  app: FastifyInstance
) {


  // ==========================================================
  // PRODUCT LIST / SEARCH
  // ==========================================================

  app.get(
    "/api/products",
    async (
      request,
      reply
    ) => {

      const query =
        productListQuerySchema.safeParse(
          request.query
        );


      if (!query.success) {

        reply.code(400);

        return validationError(
          query.error.issues
        );

      }


      const q =
        query.data.q ?? null;

      const manufacturerId =
        query.data.manufacturerId ?? null;

      const active =
        query.data.active ?? null;


      const result =
        await database.query(
          `
          SELECT
            p.id::text AS id,

            p.manufacturer_id::text
              AS "manufacturerId",

            p.name,
            p.brand,
            p.sku,
            p.gtin,
            p.description,
            p.attributes,
            p.metadata,

            p.is_active
              AS "isActive",

            p.created_at
              AS "createdAt",

            p.updated_at
              AS "updatedAt",

            o.legal_name
              AS "manufacturerLegalName",

            o.trading_name
              AS "manufacturerTradingName",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM products p

          LEFT JOIN organizations o
            ON o.id =
               p.manufacturer_id

          WHERE
            (
              $1::text IS NULL

              OR p.name ILIKE
                 '%' || $1 || '%'

              OR p.brand ILIKE
                 '%' || $1 || '%'

              OR p.sku ILIKE
                 '%' || $1 || '%'

              OR p.gtin ILIKE
                 '%' || $1 || '%'

              OR p.description ILIKE
                 '%' || $1 || '%'

              OR o.legal_name ILIKE
                 '%' || $1 || '%'

              OR o.trading_name ILIKE
                 '%' || $1 || '%'
            )

            AND (
              $2::uuid IS NULL
              OR p.manufacturer_id =
                 $2::uuid
            )

            AND (
              $3::boolean IS NULL
              OR p.is_active =
                 $3::boolean
            )

          ORDER BY

            CASE
              WHEN $1::text IS NOT NULL
              THEN
                GREATEST(
                  similarity(
                    LOWER(
                      COALESCE(
                        p.name,
                        ''
                      )
                    ),
                    LOWER($1)
                  ),
                  similarity(
                    LOWER(
                      COALESCE(
                        p.brand,
                        ''
                      )
                    ),
                    LOWER($1)
                  ),
                  similarity(
                    LOWER(
                      COALESCE(
                        p.sku,
                        ''
                      )
                    ),
                    LOWER($1)
                  )
                )
              ELSE 0
            END DESC,

            p.updated_at DESC

          LIMIT $4
          OFFSET $5
          `,
          [
            q,
            manufacturerId,
            active,
            query.data.limit,
            query.data.offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const products =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...product
            } = row;

            return product;

          }
        );


      return {

        ok: true,

        products,

        pagination: {

          total,

          limit:
            query.data.limit,

          offset:
            query.data.offset

        }

      };

    }
  );


  // ==========================================================
  // CREATE PRODUCT
  // ==========================================================

  app.post(
    "/api/products",
    async (
      request,
      reply
    ) => {

      const body =
        createProductSchema.safeParse(
          request.body
        );


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      const manufacturerId =
        body.data.manufacturerId
        ?? null;


      if (
        manufacturerId
        && !await manufacturerExists(
          manufacturerId
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "manufacturer_not_found",

          manufacturerId

        };

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO products (
                manufacturer_id,
                name,
                brand,
                sku,
                gtin,
                description,
                attributes,
                metadata,
                is_active
            )
            VALUES (
                $1::uuid,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7::jsonb,
                $8::jsonb,
                $9
            )
            RETURNING
                id::text
            `,
            [
              manufacturerId,
              body.data.name,
              body.data.brand ?? null,
              body.data.sku ?? null,
              body.data.gtin ?? null,
              body.data.description ?? null,
              JSON.stringify(
                body.data.attributes
              ),
              JSON.stringify(
                body.data.metadata
              ),
              body.data.isActive
            ]
          );


        const product =
          await loadProduct(
            result.rows[0].id
          );


        reply.code(201);


        return {

          ok: true,

          product

        };

      }
      catch (error) {

        request.log.error(
          error
        );

        reply.code(500);

        return {

          ok: false,

          error:
            "product_create_failed"

        };

      }

    }
  );


  // ==========================================================
  // PRODUCT DETAIL
  // ==========================================================

  app.get(
    "/api/products/:id",
    async (
      request,
      reply
    ) => {

      const params =
        productParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const product =
        await loadProduct(
          params.data.id
        );


      if (!product) {

        reply.code(404);

        return {

          ok: false,

          error:
            "product_not_found"

        };

      }


      return {

        ok: true,

        product

      };

    }
  );


  // ==========================================================
  // UPDATE PRODUCT
  // ==========================================================

  app.patch(
    "/api/products/:id",
    async (
      request,
      reply
    ) => {

      const params =
        productParamsSchema.safeParse(
          request.params
        );


      const body =
        updateProductSchema.safeParse(
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
        body.data.manufacturerId
        && !await manufacturerExists(
          body.data.manufacturerId
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "manufacturer_not_found",

          manufacturerId:
            body.data.manufacturerId

        };

      }


      const updates: string[] = [];

      const values: unknown[] = [];


      function addValue(
        expression: string,
        value: unknown
      ) {

        values.push(
          value
        );

        updates.push(
          `${expression} $${values.length}`
        );

      }


      if (
        body.data.manufacturerId
        !== undefined
      ) {

        addValue(
          "manufacturer_id =",
          body.data.manufacturerId
        );

      }


      if (
        body.data.name
        !== undefined
      ) {

        addValue(
          "name =",
          body.data.name
        );

      }


      if (
        body.data.brand
        !== undefined
      ) {

        addValue(
          "brand =",
          body.data.brand
        );

      }


      if (
        body.data.sku
        !== undefined
      ) {

        addValue(
          "sku =",
          body.data.sku
        );

      }


      if (
        body.data.gtin
        !== undefined
      ) {

        addValue(
          "gtin =",
          body.data.gtin
        );

      }


      if (
        body.data.description
        !== undefined
      ) {

        addValue(
          "description =",
          body.data.description
        );

      }


      if (
        body.data.isActive
        !== undefined
      ) {

        addValue(
          "is_active =",
          body.data.isActive
        );

      }


      if (
        body.data.attributes
        !== undefined
      ) {

        values.push(
          JSON.stringify(
            body.data.attributes
          )
        );

        updates.push(
          `attributes =
             attributes
             || $${values.length}::jsonb`
        );

      }


      if (
        body.data.metadata
        !== undefined
      ) {

        values.push(
          JSON.stringify(
            body.data.metadata
          )
        );

        updates.push(
          `metadata =
             metadata
             || $${values.length}::jsonb`
        );

      }


      values.push(
        params.data.id
      );


      const result =
        await database.query(
          `
          UPDATE products
          SET
            ${updates.join(",\n")}
          WHERE id =
                $${values.length}::uuid
          RETURNING id::text
          `,
          values
        );


      if (!result.rows[0]) {

        reply.code(404);

        return {

          ok: false,

          error:
            "product_not_found"

        };

      }


      const product =
        await loadProduct(
          params.data.id
        );


      return {

        ok: true,

        product

      };

    }
  );


  // ==========================================================
  // ACCEPTED HS CLASSIFICATIONS
  // ==========================================================

  app.get(
    "/api/products/:id/classifications",
    async (
      request,
      reply
    ) => {

      const params =
        productParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const product =
        await loadProduct(
          params.data.id
        );


      if (!product) {

        reply.code(404);

        return {

          ok: false,

          error:
            "product_not_found"

        };

      }


      const result =
        await database.query(
          `
          SELECT
            phc.id::text AS id,

            phc.hs_code_id::text
              AS "hsCodeId",

            h.code
              AS "hsCode",

            h.description
              AS "hsDescription",

            h.level,

            phc.country_id::text
              AS "countryId",

            c.iso2
              AS "countryIso2",

            c.name
              AS "countryName",

            phc.is_primary
              AS "isPrimary",

            phc.confidence::double precision
              AS confidence,

            TO_CHAR(
              phc.valid_from,
              'YYYY-MM-DD'
            ) AS "validFrom",

            TO_CHAR(
              phc.valid_to,
              'YYYY-MM-DD'
            ) AS "validTo",

            phc.classification_request_id::text
              AS "classificationRequestId",

            phc.decision_method
              AS "decisionMethod",

            phc.decision_notes
              AS "decisionNotes",

            phc.metadata,

            phc.created_at
              AS "createdAt",

            phc.updated_at
              AS "updatedAt"

          FROM product_hs_classifications phc

          JOIN hs_codes h
            ON h.id =
               phc.hs_code_id

          LEFT JOIN countries c
            ON c.id =
               phc.country_id

          WHERE phc.product_id =
                $1::uuid

          ORDER BY
            phc.is_primary DESC,
            phc.updated_at DESC
          `,
          [
            params.data.id
          ]
        );


      return {

        ok: true,

        product: {

          id:
            product.id,

          name:
            product.name

        },

        classifications:
          result.rows

      };

    }
  );


  // ==========================================================
  // CLASSIFICATION REQUEST HISTORY
  // ==========================================================

  app.get(
    "/api/products/:id/classification-history",
    async (
      request,
      reply
    ) => {

      const params =
        productParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const product =
        await loadProduct(
          params.data.id
        );


      if (!product) {

        reply.code(404);

        return {

          ok: false,

          error:
            "product_not_found"

        };

      }


      const result =
        await database.query(
          `
          SELECT
            r.id::text AS id,

            r.nomenclature,

            r.status,

            r.input_text
              AS "inputText",

            r.normalized_text
              AS "normalizedText",

            r.retrieval_version
              AS "retrievalVersion",

            r.candidate_limit
              AS "candidateLimit",

            r.selected_candidate_id::text
              AS "selectedCandidateId",

            selected_hs.code
              AS "selectedHsCode",

            selected_hs.description
              AS "selectedHsDescription",

            r.decision_notes
              AS "decisionNotes",

            r.decided_at
              AS "decidedAt",

            r.metadata,

            r.country_id::text
              AS "countryId",

            country.iso2
              AS "countryIso2",

            country.name
              AS "countryName",

            (
              SELECT COUNT(*)::int
              FROM hs_classification_candidates candidate
              WHERE candidate.request_id =
                    r.id
            ) AS "candidateCount",

            (
              SELECT classification.id::text
              FROM product_hs_classifications classification
              WHERE
                classification.classification_request_id =
                r.id
              LIMIT 1
            ) AS "productClassificationId",

            r.created_at
              AS "createdAt",

            r.updated_at
              AS "updatedAt"

          FROM hs_classification_requests r

          LEFT JOIN hs_classification_candidates selected
            ON selected.id =
               r.selected_candidate_id

          LEFT JOIN hs_codes selected_hs
            ON selected_hs.id =
               selected.hs_code_id

          LEFT JOIN countries country
            ON country.id =
               r.country_id

          WHERE r.product_id =
                $1::uuid

          ORDER BY
            r.created_at DESC
          `,
          [
            params.data.id
          ]
        );


      return {

        ok: true,

        product: {

          id:
            product.id,

          name:
            product.name

        },

        history:
          result.rows

      };

    }
  );

}
