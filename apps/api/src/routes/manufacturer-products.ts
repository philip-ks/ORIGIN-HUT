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


const normalizedStatusSchema =
  z.string()
    .trim()
    .min(1)
    .max(100)
    .transform(
      value =>
        value
          .toLowerCase()
          .replace(
            /[\s-]+/g,
            "_"
          )
    );


const manufacturerProductParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const productManufacturerProductsParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const listQuerySchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .max(500)
      .optional(),

    productId:
      uuidSchema
        .optional(),

    manufacturerId:
      uuidSchema
        .optional(),

    originCountry:
      countryIso2Schema
        .optional(),

    status:
      normalizedStatusSchema
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


const createSchema =
  z.object({

    manufacturerId:
      uuidSchema,

    originCountry:
      countryIso2Schema
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

    grade: z
      .string()
      .trim()
      .min(1)
      .max(300)
      .nullable()
      .optional(),

    modelCode: z
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

    status:
      normalizedStatusSchema
        .default("active"),

    identifiers:
      jsonObjectSchema
        .default({}),

    attributes:
      jsonObjectSchema
        .default({}),

    metadata:
      jsonObjectSchema
        .default({})

  });


const updateSchema =
  z.object({

    manufacturerId:
      uuidSchema
        .optional(),

    originCountry:
      countryIso2Schema
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

    grade: z
      .string()
      .trim()
      .min(1)
      .max(300)
      .nullable()
      .optional(),

    modelCode: z
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

    status:
      normalizedStatusSchema
        .optional(),

    identifiers:
      jsonObjectSchema
        .optional(),

    attributes:
      jsonObjectSchema
        .optional(),

    metadata:
      jsonObjectSchema
        .optional()

  })
  .refine(
    value =>
      Object.keys(value).length > 0,
    {
      message:
        "At least one manufacturer product field is required."
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


async function productExists(
  id: string
): Promise<boolean> {

  const result =
    await database.query(
      `
      SELECT EXISTS (
        SELECT 1
        FROM products
        WHERE
          id = $1::uuid
          AND is_active = TRUE
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


async function manufacturerEligibility(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT

        EXISTS (
          SELECT 1
          FROM organizations
          WHERE id = $1::uuid
        ) AS exists,

        EXISTS (
          SELECT 1
          FROM organization_roles
          WHERE
            organization_id = $1::uuid
            AND role_code = 'manufacturer'
        ) AS "hasManufacturerRole"
      `,
      [
        id
      ]
    );


  return {

    exists:
      Boolean(
        result.rows[0]?.exists
      ),

    hasManufacturerRole:
      Boolean(
        result.rows[0]?.hasManufacturerRole
      )

  };

}


async function resolveCountryId(
  iso2: string | null | undefined
): Promise<string | null> {

  if (
    iso2 === null
    || iso2 === undefined
  ) {

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


async function loadManufacturerProduct(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        mp.id::text AS id,

        mp.product_id::text
          AS "productId",

        p.name
          AS "productName",

        mp.manufacturer_id::text
          AS "manufacturerId",

        o.legal_name
          AS "manufacturerLegalName",

        o.trading_name
          AS "manufacturerTradingName",

        mp.country_of_origin_id::text
          AS "countryOfOriginId",

        origin.iso2
          AS "originCountryIso2",

        origin.iso3
          AS "originCountryIso3",

        origin.name
          AS "originCountryName",

        mp.name,
        mp.brand,
        mp.grade,

        mp.model_code
          AS "modelCode",

        mp.sku,
        mp.gtin,
        mp.description,
        mp.status,
        mp.identifiers,
        mp.attributes,
        mp.metadata,

        mp.created_at
          AS "createdAt",

        mp.updated_at
          AS "updatedAt"

      FROM manufacturer_products mp

      JOIN products p
        ON p.id =
           mp.product_id

      JOIN organizations o
        ON o.id =
           mp.manufacturer_id

      LEFT JOIN countries origin
        ON origin.id =
           mp.country_of_origin_id

      WHERE mp.id =
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


function conflictResponse(
  error: unknown
) {

  const code =
    (
      error as {
        code?: string;
      }
    ).code;


  if (
    code === "23505"
  ) {

    return {

      statusCode:
        409,

      body: {

        ok: false,

        error:
          "manufacturer_product_identity_conflict"

      }

    };

  }


  return null;

}


export async function manufacturerProductRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/manufacturer-products",
    async (
      request,
      reply
    ) => {

      const parsed =
        listQuerySchema.safeParse(
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
        productId,
        manufacturerId,
        originCountry,
        status,
        limit,
        offset
      } = parsed.data;


      const result =
        await database.query(
          `
          SELECT
            mp.id::text AS id,

            mp.product_id::text
              AS "productId",

            p.name
              AS "productName",

            mp.manufacturer_id::text
              AS "manufacturerId",

            o.legal_name
              AS "manufacturerLegalName",

            o.trading_name
              AS "manufacturerTradingName",

            origin.iso2
              AS "originCountryIso2",

            origin.name
              AS "originCountryName",

            mp.name,
            mp.brand,
            mp.grade,

            mp.model_code
              AS "modelCode",

            mp.sku,
            mp.gtin,
            mp.description,
            mp.status,
            mp.identifiers,
            mp.attributes,
            mp.metadata,

            mp.created_at
              AS "createdAt",

            mp.updated_at
              AS "updatedAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM manufacturer_products mp

          JOIN products p
            ON p.id =
               mp.product_id

          JOIN organizations o
            ON o.id =
               mp.manufacturer_id

          LEFT JOIN countries origin
            ON origin.id =
               mp.country_of_origin_id

          WHERE
            (
              $1::text IS NULL

              OR mp.name ILIKE
                 '%' || $1 || '%'

              OR mp.brand ILIKE
                 '%' || $1 || '%'

              OR mp.grade ILIKE
                 '%' || $1 || '%'

              OR mp.model_code ILIKE
                 '%' || $1 || '%'

              OR mp.sku ILIKE
                 '%' || $1 || '%'

              OR mp.gtin ILIKE
                 '%' || $1 || '%'

              OR p.name ILIKE
                 '%' || $1 || '%'

              OR o.legal_name ILIKE
                 '%' || $1 || '%'

              OR o.trading_name ILIKE
                 '%' || $1 || '%'
            )

            AND (
              $2::uuid IS NULL
              OR mp.product_id =
                 $2::uuid
            )

            AND (
              $3::uuid IS NULL
              OR mp.manufacturer_id =
                 $3::uuid
            )

            AND (
              $4::text IS NULL
              OR origin.iso2 =
                 $4
            )

            AND (
              $5::text IS NULL
              OR mp.status =
                 $5
            )

          ORDER BY
            mp.updated_at DESC,
            mp.name,
            mp.id

          LIMIT $6
          OFFSET $7
          `,
          [
            q ?? null,
            productId ?? null,
            manufacturerId ?? null,
            originCountry ?? null,
            status ?? null,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      return {

        ok: true,

        manufacturerProducts:
          result.rows.map(
            row => {

              const {
                totalCount: _totalCount,
                ...payload
              } = row;

              return payload;

            }
          ),

        pagination: {
          total,
          limit,
          offset
        }

      };

    }
  );


  app.get(
    "/api/products/:id/manufacturer-products",
    async (
      request,
      reply
    ) => {

      const params =
        productManufacturerProductsParamsSchema.safeParse(
          request.params
        );


      const query =
        listQuerySchema.safeParse(
          request.query
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      if (!query.success) {

        reply.code(400);

        return validationError(
          query.error.issues
        );

      }


      if (
        !await productExists(
          params.data.id
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "product_not_found"

        };

      }


      const search =
        new URLSearchParams();


      if (query.data.q) {
        search.set(
          "q",
          query.data.q
        );
      }

      search.set(
        "productId",
        params.data.id
      );

      if (query.data.manufacturerId) {
        search.set(
          "manufacturerId",
          query.data.manufacturerId
        );
      }

      if (query.data.originCountry) {
        search.set(
          "originCountry",
          query.data.originCountry
        );
      }

      if (query.data.status) {
        search.set(
          "status",
          query.data.status
        );
      }

      search.set(
        "limit",
        String(
          query.data.limit
        )
      );

      search.set(
        "offset",
        String(
          query.data.offset
        )
      );


      const result =
        await database.query(
          `
          SELECT
            mp.id::text AS id,

            mp.product_id::text
              AS "productId",

            mp.manufacturer_id::text
              AS "manufacturerId",

            o.legal_name
              AS "manufacturerLegalName",

            o.trading_name
              AS "manufacturerTradingName",

            origin.iso2
              AS "originCountryIso2",

            origin.name
              AS "originCountryName",

            mp.name,
            mp.brand,
            mp.grade,

            mp.model_code
              AS "modelCode",

            mp.sku,
            mp.gtin,
            mp.description,
            mp.status,
            mp.identifiers,
            mp.attributes,
            mp.metadata,

            mp.created_at
              AS "createdAt",

            mp.updated_at
              AS "updatedAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM manufacturer_products mp

          JOIN organizations o
            ON o.id =
               mp.manufacturer_id

          LEFT JOIN countries origin
            ON origin.id =
               mp.country_of_origin_id

          WHERE
            mp.product_id =
              $1::uuid

            AND (
              $2::text IS NULL

              OR mp.name ILIKE
                 '%' || $2 || '%'

              OR mp.brand ILIKE
                 '%' || $2 || '%'

              OR mp.grade ILIKE
                 '%' || $2 || '%'

              OR mp.model_code ILIKE
                 '%' || $2 || '%'

              OR mp.sku ILIKE
                 '%' || $2 || '%'

              OR mp.gtin ILIKE
                 '%' || $2 || '%'
            )

            AND (
              $3::uuid IS NULL
              OR mp.manufacturer_id =
                 $3::uuid
            )

            AND (
              $4::text IS NULL
              OR origin.iso2 =
                 $4
            )

            AND (
              $5::text IS NULL
              OR mp.status =
                 $5
            )

          ORDER BY
            mp.updated_at DESC,
            mp.name,
            mp.id

          LIMIT $6
          OFFSET $7
          `,
          [
            params.data.id,
            query.data.q ?? null,
            query.data.manufacturerId ?? null,
            query.data.originCountry ?? null,
            query.data.status ?? null,
            query.data.limit,
            query.data.offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      return {

        ok: true,

        productId:
          params.data.id,

        manufacturerProducts:
          result.rows.map(
            row => {

              const {
                totalCount: _totalCount,
                ...payload
              } = row;

              return payload;

            }
          ),

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


  app.post(
    "/api/products/:id/manufacturer-products",
    async (
      request,
      reply
    ) => {

      const params =
        productManufacturerProductsParamsSchema.safeParse(
          request.params
        );


      const body =
        createSchema.safeParse(
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
        !await productExists(
          params.data.id
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "product_not_found"

        };

      }


      const manufacturer =
        await manufacturerEligibility(
          body.data.manufacturerId
        );


      if (!manufacturer.exists) {

        reply.code(404);

        return {

          ok: false,

          error:
            "manufacturer_not_found"

        };

      }


      if (
        !manufacturer.hasManufacturerRole
      ) {

        reply.code(409);

        return {

          ok: false,

          error:
            "manufacturer_role_required",

          requiredRole:
            "manufacturer"

        };

      }


      const originCountryId =
        await resolveCountryId(
          body.data.originCountry
        );


      if (
        body.data.originCountry
        && !originCountryId
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "origin_country_not_found",

          originCountry:
            body.data.originCountry

        };

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO manufacturer_products (
                product_id,
                manufacturer_id,
                country_of_origin_id,
                name,
                brand,
                grade,
                model_code,
                sku,
                gtin,
                description,
                status,
                identifiers,
                attributes,
                metadata
            )
            VALUES (
                $1::uuid,
                $2::uuid,
                $3::uuid,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11,
                $12::jsonb,
                $13::jsonb,
                $14::jsonb
            )
            RETURNING
                id::text
            `,
            [
              params.data.id,
              body.data.manufacturerId,
              originCountryId,
              body.data.name,
              body.data.brand ?? null,
              body.data.grade ?? null,
              body.data.modelCode ?? null,
              body.data.sku ?? null,
              body.data.gtin ?? null,
              body.data.description ?? null,
              body.data.status,
              JSON.stringify(
                body.data.identifiers
              ),
              JSON.stringify(
                body.data.attributes
              ),
              JSON.stringify(
                body.data.metadata
              )
            ]
          );


        const manufacturerProduct =
          await loadManufacturerProduct(
            result.rows[0].id
          );


        reply.code(201);


        return {

          ok: true,

          manufacturerProduct

        };

      }
      catch (error) {

        const conflict =
          conflictResponse(
            error
          );


        if (conflict) {

          reply.code(
            conflict.statusCode
          );

          return conflict.body;

        }


        request.log.error(
          error
        );

        reply.code(500);

        return {

          ok: false,

          error:
            "manufacturer_product_create_failed"

        };

      }

    }
  );


  app.get(
    "/api/manufacturer-products/:id",
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


      const manufacturerProduct =
        await loadManufacturerProduct(
          params.data.id
        );


      if (!manufacturerProduct) {

        reply.code(404);

        return {

          ok: false,

          error:
            "manufacturer_product_not_found"

        };

      }


      return {

        ok: true,

        manufacturerProduct

      };

    }
  );


  app.patch(
    "/api/manufacturer-products/:id",
    async (
      request,
      reply
    ) => {

      const params =
        manufacturerProductParamsSchema.safeParse(
          request.params
        );


      const body =
        updateSchema.safeParse(
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
        !== undefined
      ) {

        const manufacturer =
          await manufacturerEligibility(
            body.data.manufacturerId
          );


        if (!manufacturer.exists) {

          reply.code(404);

          return {

            ok: false,

            error:
              "manufacturer_not_found"

          };

        }


        if (
          !manufacturer.hasManufacturerRole
        ) {

          reply.code(409);

          return {

            ok: false,

            error:
              "manufacturer_role_required",

            requiredRole:
              "manufacturer"

          };

        }

      }


      let originCountryId:
        string | null | undefined =
          undefined;


      if (
        body.data.originCountry
        !== undefined
      ) {

        originCountryId =
          await resolveCountryId(
            body.data.originCountry
          );


        if (
          body.data.originCountry
          && !originCountryId
        ) {

          reply.code(404);

          return {

            ok: false,

            error:
              "origin_country_not_found",

            originCountry:
              body.data.originCountry

          };

        }

      }


      const updates: string[] = [];
      const values: unknown[] = [];


      function addValue(
        column: string,
        value: unknown
      ) {

        values.push(
          value
        );

        updates.push(
          `${column} = $${values.length}`
        );

      }


      if (
        body.data.manufacturerId
        !== undefined
      ) {
        addValue(
          "manufacturer_id",
          body.data.manufacturerId
        );
      }

      if (
        originCountryId
        !== undefined
      ) {
        addValue(
          "country_of_origin_id",
          originCountryId
        );
      }

      if (
        body.data.name
        !== undefined
      ) {
        addValue(
          "name",
          body.data.name
        );
      }

      if (
        body.data.brand
        !== undefined
      ) {
        addValue(
          "brand",
          body.data.brand
        );
      }

      if (
        body.data.grade
        !== undefined
      ) {
        addValue(
          "grade",
          body.data.grade
        );
      }

      if (
        body.data.modelCode
        !== undefined
      ) {
        addValue(
          "model_code",
          body.data.modelCode
        );
      }

      if (
        body.data.sku
        !== undefined
      ) {
        addValue(
          "sku",
          body.data.sku
        );
      }

      if (
        body.data.gtin
        !== undefined
      ) {
        addValue(
          "gtin",
          body.data.gtin
        );
      }

      if (
        body.data.description
        !== undefined
      ) {
        addValue(
          "description",
          body.data.description
        );
      }

      if (
        body.data.status
        !== undefined
      ) {
        addValue(
          "status",
          body.data.status
        );
      }


      for (
        const [
          column,
          value
        ] of [
          [
            "identifiers",
            body.data.identifiers
          ],
          [
            "attributes",
            body.data.attributes
          ],
          [
            "metadata",
            body.data.metadata
          ]
        ] as const
      ) {

        if (
          value
          !== undefined
        ) {

          values.push(
            JSON.stringify(
              value
            )
          );

          updates.push(
            `${column} =
               ${column}
               || $${values.length}::jsonb`
          );

        }

      }


      values.push(
        params.data.id
      );


      try {

        const result =
          await database.query(
            `
            UPDATE manufacturer_products
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
              "manufacturer_product_not_found"

          };

        }


        const manufacturerProduct =
          await loadManufacturerProduct(
            params.data.id
          );


        return {

          ok: true,

          manufacturerProduct

        };

      }
      catch (error) {

        const conflict =
          conflictResponse(
            error
          );


        if (conflict) {

          reply.code(
            conflict.statusCode
          );

          return conflict.body;

        }


        request.log.error(
          error
        );

        reply.code(500);

        return {

          ok: false,

          error:
            "manufacturer_product_update_failed"

        };

      }

    }
  );

}
