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


const definitionCodeSchema =
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
    )
    .refine(
      value =>
        /^[a-z][a-z0-9_]*$/.test(
          value
        ),
      {
        message:
          "Definition code must begin with a letter and contain only letters, numbers or underscores."
      }
    );


const uomCodeSchema =
  z.string()
    .trim()
    .min(1)
    .max(3)
    .transform(
      value =>
        value.toUpperCase()
    );


const definitionParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const specificationParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const subjectParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const definitionListQuerySchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .max(300)
      .optional(),

    category: z
      .string()
      .trim()
      .min(1)
      .max(100)
      .optional(),

    valueType: z
      .enum([
        "numeric",
        "text",
        "boolean"
      ])
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
      .max(200)
      .default(100),

    offset: z.coerce
      .number()
      .int()
      .min(0)
      .default(0)

  });


const createDefinitionSchema =
  z.object({

    code:
      definitionCodeSchema,

    name: z
      .string()
      .trim()
      .min(1)
      .max(300),

    category: z
      .string()
      .trim()
      .min(1)
      .max(100)
      .nullable()
      .optional(),

    description: z
      .string()
      .trim()
      .min(1)
      .max(5000)
      .nullable()
      .optional(),

    valueType: z
      .enum([
        "numeric",
        "text",
        "boolean"
      ]),

    dimensionCode: z
      .string()
      .trim()
      .min(1)
      .max(100)
      .transform(
        value =>
          value.toLowerCase()
      )
      .nullable()
      .optional(),

    defaultUomCode:
      uomCodeSchema
        .nullable()
        .optional(),

    metadata: z
      .record(
        z.string(),
        z.unknown()
      )
      .default({})

  });


const createSpecificationSchema =
  z.object({

    definitionCode:
      definitionCodeSchema,

    qualifier: z
      .enum([
        "exact",
        "nominal",
        "minimum",
        "maximum",
        "range"
      ])
      .default("exact"),

    numericValue: z
      .number()
      .finite()
      .nullable()
      .optional(),

    minimumValue: z
      .number()
      .finite()
      .nullable()
      .optional(),

    maximumValue: z
      .number()
      .finite()
      .nullable()
      .optional(),

    textValue: z
      .string()
      .trim()
      .min(1)
      .max(5000)
      .nullable()
      .optional(),

    booleanValue: z
      .boolean()
      .nullable()
      .optional(),

    uomCode:
      uomCodeSchema
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
        && value.validTo < value.validFrom
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


async function loadUnit(
  code: string | null | undefined
) {

  if (!code) {
    return null;
  }


  const result =
    await database.query(
      `
      SELECT
        id::text,
        code,
        name,
        dimension_code
          AS "dimensionCode",
        is_active
          AS "isActive"
      FROM units_of_measure
      WHERE code = $1
      `,
      [
        code
      ]
    );


  return (
    result.rows[0]
    ?? null
  );

}


async function loadDefinitionByCode(
  code: string
) {

  const result =
    await database.query(
      `
      SELECT
        sd.id::text,
        sd.code,
        sd.name,
        sd.category,
        sd.description,

        sd.value_type
          AS "valueType",

        sd.dimension_code
          AS "dimensionCode",

        sd.default_uom_id::text
          AS "defaultUomId",

        u.code
          AS "defaultUomCode",

        u.name
          AS "defaultUomName",

        sd.is_active
          AS "isActive",

        sd.metadata,

        sd.created_at
          AS "createdAt",

        sd.updated_at
          AS "updatedAt"

      FROM specification_definitions sd

      LEFT JOIN units_of_measure u
        ON u.id =
           sd.default_uom_id

      WHERE sd.code = $1
      `,
      [
        code
      ]
    );


  return (
    result.rows[0]
    ?? null
  );

}


async function subjectExists(
  table:
    "products"
    | "manufacturer_products",
  id: string
): Promise<boolean> {

  const query =
    table === "products"
      ? `
          SELECT EXISTS (
            SELECT 1
            FROM products
            WHERE
              id = $1::uuid
              AND is_active = TRUE
          ) AS exists
        `
      : `
          SELECT EXISTS (
            SELECT 1
            FROM manufacturer_products
            WHERE
              id = $1::uuid
              AND status = 'active'
          ) AS exists
        `;


  const result =
    await database.query(
      query,
      [
        id
      ]
    );


  return Boolean(
    result.rows[0]?.exists
  );

}


function validateSpecificationValue(
  definition: Record<
    string,
    unknown
  >,
  body: z.infer<
    typeof createSpecificationSchema
  >,
  uom: Record<
    string,
    unknown
  > | null
): string | null {

  const valueType =
    definition.valueType;


  if (
    valueType === "numeric"
  ) {

    const hasNumeric =
      body.numericValue !== undefined
      && body.numericValue !== null;

    const hasMinimum =
      body.minimumValue !== undefined
      && body.minimumValue !== null;

    const hasMaximum =
      body.maximumValue !== undefined
      && body.maximumValue !== null;


    if (
      !hasNumeric
      && !hasMinimum
      && !hasMaximum
    ) {

      return (
        "Numeric specification requires a numeric value or range."
      );

    }


    if (
      body.qualifier === "range"
      && (
        !hasMinimum
        || !hasMaximum
      )
    ) {

      return (
        "Range qualifier requires minimumValue and maximumValue."
      );

    }


    if (
      hasMinimum
      && hasMaximum
      && Number(
        body.maximumValue
      )
      < Number(
        body.minimumValue
      )
    ) {

      return (
        "maximumValue cannot be below minimumValue."
      );

    }


    const dimension =
      definition.dimensionCode;


    if (
      dimension
      && !uom
    ) {

      return (
        "A unit is required for this dimensional specification."
      );

    }


    if (
      dimension
      && uom
      && uom.dimensionCode
         !== dimension
    ) {

      return (
        "Specification unit dimension does not match the definition."
      );

    }


    if (
      body.textValue !== undefined
      && body.textValue !== null
    ) {

      return (
        "Numeric specification cannot contain textValue."
      );

    }


    if (
      body.booleanValue !== undefined
      && body.booleanValue !== null
    ) {

      return (
        "Numeric specification cannot contain booleanValue."
      );

    }


    return null;

  }


  if (
    valueType === "text"
  ) {

    if (
      body.textValue === undefined
      || body.textValue === null
    ) {

      return (
        "Text specification requires textValue."
      );

    }


    if (
      uom
      || body.numericValue != null
      || body.minimumValue != null
      || body.maximumValue != null
      || body.booleanValue != null
    ) {

      return (
        "Text specification cannot contain numeric, boolean or UOM values."
      );

    }


    return null;

  }


  if (
    body.booleanValue === undefined
    || body.booleanValue === null
  ) {

    return (
      "Boolean specification requires booleanValue."
    );

  }


  if (
    uom
    || body.numericValue != null
    || body.minimumValue != null
    || body.maximumValue != null
    || body.textValue != null
  ) {

    return (
      "Boolean specification cannot contain numeric, text or UOM values."
    );

  }


  return null;

}


async function listSpecifications(
  subjectColumn:
    "product_id"
    | "manufacturer_product_id",
  subjectId: string
) {

  const result =
    await database.query(
      `
      SELECT
        ps.id::text,
        sd.id::text
          AS "definitionId",
        sd.code
          AS "definitionCode",
        sd.name
          AS "definitionName",
        sd.category,
        sd.value_type
          AS "valueType",
        sd.dimension_code
          AS "dimensionCode",

        ps.qualifier,

        ps.numeric_value::double precision
          AS "numericValue",

        ps.minimum_value::double precision
          AS "minimumValue",

        ps.maximum_value::double precision
          AS "maximumValue",

        ps.text_value
          AS "textValue",

        ps.boolean_value
          AS "booleanValue",

        u.code
          AS "uomCode",

        u.name
          AS "uomName",

        u.symbol
          AS "uomSymbol",

        ps.status,

        TO_CHAR(
          ps.valid_from,
          'YYYY-MM-DD'
        ) AS "validFrom",

        TO_CHAR(
          ps.valid_to,
          'YYYY-MM-DD'
        ) AS "validTo",

        ps.source_type
          AS "sourceType",

        ps.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        ps.confidence::double precision
          AS confidence,

        ps.metadata,

        ps.created_at
          AS "createdAt",

        ps.updated_at
          AS "updatedAt"

      FROM product_specifications ps

      JOIN specification_definitions sd
        ON sd.id =
           ps.specification_definition_id

      LEFT JOIN units_of_measure u
        ON u.id =
           ps.uom_id

      WHERE
        ps.${subjectColumn} =
          $1::uuid

      ORDER BY
        sd.category NULLS LAST,
        sd.name,
        ps.updated_at DESC
      `,
      [
        subjectId
      ]
    );


  return result.rows;

}


async function createSpecification(
  subject:
    "product"
    | "manufacturer_product",
  subjectId: string,
  body: z.infer<
    typeof createSpecificationSchema
  >
) {

  const definition =
    await loadDefinitionByCode(
      body.definitionCode
    );


  if (
    !definition
    || !definition.isActive
  ) {

    return {
      statusCode: 404,
      body: {
        ok: false,
        error:
          "specification_definition_not_found"
      }
    };

  }


  const effectiveUomCode =
    (
      body.uomCode
      ?? definition.defaultUomCode
      ?? null
    );


  const uom =
    await loadUnit(
      effectiveUomCode
    );


  if (
    effectiveUomCode
    && (
      !uom
      || !uom.isActive
    )
  ) {

    return {
      statusCode: 404,
      body: {
        ok: false,
        error:
          "unit_not_found",
        uomCode:
          effectiveUomCode
      }
    };

  }


  const validation =
    validateSpecificationValue(
      definition,
      body,
      uom
    );


  if (validation) {

    return {
      statusCode: 409,
      body: {
        ok: false,
        error:
          "invalid_specification_value",
        message:
          validation
      }
    };

  }


  const productId =
    subject === "product"
      ? subjectId
      : null;

  const manufacturerProductId =
    subject === "manufacturer_product"
      ? subjectId
      : null;


  try {

    const result =
      await database.query(
        `
        INSERT INTO product_specifications (
            specification_definition_id,
            product_id,
            manufacturer_product_id,
            qualifier,
            numeric_value,
            minimum_value,
            maximum_value,
            text_value,
            boolean_value,
            uom_id,
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
            $3::uuid,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $10::uuid,
            'active',
            $11::date,
            $12::date,
            $13,
            $14::uuid,
            $15,
            $16::jsonb
        )
        RETURNING id::text
        `,
        [
          definition.id,
          productId,
          manufacturerProductId,
          body.qualifier,
          body.numericValue ?? null,
          body.minimumValue ?? null,
          body.maximumValue ?? null,
          body.textValue ?? null,
          body.booleanValue ?? null,
          uom?.id ?? null,
          body.validFrom ?? null,
          body.validTo ?? null,
          body.sourceType,
          body.sourceRecordId ?? null,
          body.confidence ?? null,
          JSON.stringify(
            body.metadata
          )
        ]
      );


    return {
      statusCode: 201,
      body: {
        ok: true,
        specificationId:
          result.rows[0].id
      }
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

      return {
        statusCode: 409,
        body: {
          ok: false,
          error:
            "active_specification_already_exists"
        }
      };

    }


    throw error;

  }

}


export async function specificationRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/specifications/definitions",
    async (
      request,
      reply
    ) => {

      const parsed =
        definitionListQuerySchema.safeParse(
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
        category,
        valueType,
        active,
        limit,
        offset
      } = parsed.data;


      const result =
        await database.query(
          `
          SELECT
            sd.id::text,
            sd.code,
            sd.name,
            sd.category,
            sd.description,

            sd.value_type
              AS "valueType",

            sd.dimension_code
              AS "dimensionCode",

            u.code
              AS "defaultUomCode",

            u.name
              AS "defaultUomName",

            sd.is_active
              AS "isActive",

            sd.metadata,

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM specification_definitions sd

          LEFT JOIN units_of_measure u
            ON u.id =
               sd.default_uom_id

          WHERE
            (
              $1::text IS NULL
              OR sd.code ILIKE
                 '%' || $1 || '%'
              OR sd.name ILIKE
                 '%' || $1 || '%'
              OR sd.description ILIKE
                 '%' || $1 || '%'
            )

            AND (
              $2::text IS NULL
              OR sd.category =
                 $2
            )

            AND (
              $3::text IS NULL
              OR sd.value_type =
                 $3
            )

            AND (
              $4::boolean IS NULL
              OR sd.is_active =
                 $4
            )

          ORDER BY
            sd.category NULLS LAST,
            sd.name,
            sd.code

          LIMIT $5
          OFFSET $6
          `,
          [
            q ?? null,
            category ?? null,
            valueType ?? null,
            active ?? null,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      return {

        ok: true,

        definitions:
          result.rows.map(
            row => {

              const {
                totalCount: _totalCount,
                ...definition
              } = row;

              return definition;

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


  app.post(
    "/api/specifications/definitions",
    async (
      request,
      reply
    ) => {

      const body =
        createDefinitionSchema.safeParse(
          request.body
        );


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      let defaultUom =
        await loadUnit(
          body.data.defaultUomCode
        );


      if (
        body.data.defaultUomCode
        && (
          !defaultUom
          || !defaultUom.isActive
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "unit_not_found",

          uomCode:
            body.data.defaultUomCode

        };

      }


      if (
        body.data.valueType !== "numeric"
        && (
          body.data.dimensionCode
          || defaultUom
        )
      ) {

        reply.code(409);

        return {

          ok: false,

          error:
            "non_numeric_definition_cannot_have_uom"

        };

      }


      const dimensionCode =
        (
          body.data.dimensionCode
          ?? defaultUom?.dimensionCode
          ?? null
        );


      if (
        defaultUom
        && body.data.dimensionCode
        && defaultUom.dimensionCode
           !== body.data.dimensionCode
      ) {

        reply.code(409);

        return {

          ok: false,

          error:
            "definition_uom_dimension_mismatch"

        };

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO specification_definitions (
                code,
                name,
                category,
                description,
                value_type,
                dimension_code,
                default_uom_id,
                metadata
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7::uuid,
                $8::jsonb
            )
            RETURNING id::text
            `,
            [
              body.data.code,
              body.data.name,
              body.data.category ?? null,
              body.data.description ?? null,
              body.data.valueType,
              dimensionCode,
              defaultUom?.id ?? null,
              JSON.stringify(
                body.data.metadata
              )
            ]
          );


        reply.code(201);


        return {

          ok: true,

          definition:
            await loadDefinitionByCode(
              body.data.code
            ),

          id:
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
              "specification_definition_conflict"

          };

        }


        throw error;

      }

    }
  );


  app.get(
    "/api/products/:id/specifications",
    async (
      request,
      reply
    ) => {

      const params =
        subjectParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      if (
        !await subjectExists(
          "products",
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


      return {

        ok: true,

        productId:
          params.data.id,

        specifications:
          await listSpecifications(
            "product_id",
            params.data.id
          )

      };

    }
  );


  app.post(
    "/api/products/:id/specifications",
    async (
      request,
      reply
    ) => {

      const params =
        subjectParamsSchema.safeParse(
          request.params
        );


      const body =
        createSpecificationSchema.safeParse(
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
        !await subjectExists(
          "products",
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


      const result =
        await createSpecification(
          "product",
          params.data.id,
          body.data
        );


      reply.code(
        result.statusCode
      );


      return result.body;

    }
  );


  app.get(
    "/api/manufacturer-products/:id/specifications",
    async (
      request,
      reply
    ) => {

      const params =
        subjectParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      if (
        !await subjectExists(
          "manufacturer_products",
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


      return {

        ok: true,

        manufacturerProductId:
          params.data.id,

        specifications:
          await listSpecifications(
            "manufacturer_product_id",
            params.data.id
          )

      };

    }
  );


  app.post(
    "/api/manufacturer-products/:id/specifications",
    async (
      request,
      reply
    ) => {

      const params =
        subjectParamsSchema.safeParse(
          request.params
        );


      const body =
        createSpecificationSchema.safeParse(
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
        !await subjectExists(
          "manufacturer_products",
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
        await createSpecification(
          "manufacturer_product",
          params.data.id,
          body.data
        );


      reply.code(
        result.statusCode
      );


      return result.body;

    }
  );


  app.get(
    "/api/specifications/:id",
    async (
      request,
      reply
    ) => {

      const params =
        specificationParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const result =
        await database.query(
          `
          SELECT
            ps.id::text,
            ps.product_id::text
              AS "productId",
            ps.manufacturer_product_id::text
              AS "manufacturerProductId",
            sd.code
              AS "definitionCode",
            sd.name
              AS "definitionName",
            sd.value_type
              AS "valueType",
            sd.dimension_code
              AS "dimensionCode",
            ps.qualifier,
            ps.numeric_value::double precision
              AS "numericValue",
            ps.minimum_value::double precision
              AS "minimumValue",
            ps.maximum_value::double precision
              AS "maximumValue",
            ps.text_value
              AS "textValue",
            ps.boolean_value
              AS "booleanValue",
            u.code
              AS "uomCode",
            u.symbol
              AS "uomSymbol",
            ps.status,
            ps.source_type
              AS "sourceType",
            ps.canonical_source_record_id::text
              AS "canonicalSourceRecordId",
            ps.confidence::double precision
              AS confidence,
            ps.metadata,
            ps.created_at
              AS "createdAt",
            ps.updated_at
              AS "updatedAt"
          FROM product_specifications ps
          JOIN specification_definitions sd
            ON sd.id =
               ps.specification_definition_id
          LEFT JOIN units_of_measure u
            ON u.id =
               ps.uom_id
          WHERE ps.id =
                $1::uuid
          `,
          [
            params.data.id
          ]
        );


      if (!result.rows[0]) {

        reply.code(404);

        return {

          ok: false,

          error:
            "specification_not_found"

        };

      }


      return {

        ok: true,

        specification:
          result.rows[0]

      };

    }
  );

}
