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


const packageCodeSchema =
  z.string()
    .trim()
    .min(1)
    .max(3)
    .transform(
      value =>
        value.toUpperCase()
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


const subjectParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const packagingParamsSchema =
  z.object({

    id:
      uuidSchema

  });


const packageTypeListSchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .max(200)
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


const createPackagingSchema =
  z.object({

    packageTypeCode:
      packageCodeSchema,

    name: z
      .string()
      .trim()
      .min(1)
      .max(300),

    packagingLevel: z
      .enum([
        "primary",
        "secondary",
        "tertiary",
        "logistics"
      ]),

    packagingMaterial: z
      .string()
      .trim()
      .min(1)
      .max(300)
      .nullable()
      .optional(),

    contentQuantity: z
      .number()
      .positive()
      .nullable()
      .optional(),

    contentUomCode:
      uomCodeSchema
        .nullable()
        .optional(),

    innerPackagingId:
      uuidSchema
        .nullable()
        .optional(),

    innerPackageCount: z
      .number()
      .int()
      .positive()
      .nullable()
      .optional(),

    netWeight: z
      .number()
      .positive()
      .nullable()
      .optional(),

    grossWeight: z
      .number()
      .positive()
      .nullable()
      .optional(),

    weightUomCode:
      uomCodeSchema
        .nullable()
        .optional(),

    length: z
      .number()
      .positive()
      .nullable()
      .optional(),

    width: z
      .number()
      .positive()
      .nullable()
      .optional(),

    height: z
      .number()
      .positive()
      .nullable()
      .optional(),

    dimensionUomCode:
      uomCodeSchema
        .nullable()
        .optional(),

    isDefault: z
      .boolean()
      .default(false),

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

      const contentQuantity =
        value.contentQuantity != null;

      const contentUom =
        value.contentUomCode != null;


      if (
        contentQuantity
        !== contentUom
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "contentUomCode"
            ],
          message:
            "contentQuantity and contentUomCode must be supplied together."
        });

      }


      const innerId =
        value.innerPackagingId != null;

      const innerCount =
        value.innerPackageCount != null;


      if (
        innerId
        !== innerCount
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "innerPackageCount"
            ],
          message:
            "innerPackagingId and innerPackageCount must be supplied together."
        });

      }


      if (
        !contentQuantity
        && !innerId
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "contentQuantity"
            ],
          message:
            "Packaging must define product content or an inner packaging configuration."
        });

      }


      const hasWeight =
        value.netWeight != null
        || value.grossWeight != null;


      if (
        hasWeight
        !== (
          value.weightUomCode != null
        )
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "weightUomCode"
            ],
          message:
            "weightUomCode is required when netWeight or grossWeight is supplied."
        });

      }


      if (
        value.netWeight != null
        && value.grossWeight != null
        && value.grossWeight
           < value.netWeight
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "grossWeight"
            ],
          message:
            "grossWeight cannot be below netWeight."
        });

      }


      const dimensionCount =
        [
          value.length,
          value.width,
          value.height
        ]
        .filter(
          item =>
            item != null
        )
        .length;


      if (
        dimensionCount !== 0
        && dimensionCount !== 3
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "length"
            ],
          message:
            "length, width and height must be supplied together."
        });

      }


      if (
        (
          dimensionCount === 3
        )
        !== (
          value.dimensionUomCode != null
        )
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "dimensionUomCode"
            ],
          message:
            "dimensionUomCode is required with package dimensions."
        });

      }


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


async function loadUom(
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
        symbol,
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


async function loadPackageType(
  code: string
) {

  const result =
    await database.query(
      `
      SELECT
        id::text,
        code,
        name,
        standard,
        is_active
          AS "isActive"
      FROM package_types
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


async function loadPackaging(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        pc.id::text,

        pc.manufacturer_product_id::text
          AS "manufacturerProductId",

        pt.code
          AS "packageTypeCode",

        pt.name
          AS "packageTypeName",

        pc.name,

        pc.packaging_level
          AS "packagingLevel",

        pc.packaging_material
          AS "packagingMaterial",

        pc.content_quantity::double precision
          AS "contentQuantity",

        content_uom.code
          AS "contentUomCode",

        pc.inner_packaging_id::text
          AS "innerPackagingId",

        inner_pc.name
          AS "innerPackagingName",

        pc.inner_package_count
          AS "innerPackageCount",

        pc.net_weight::double precision
          AS "netWeight",

        pc.gross_weight::double precision
          AS "grossWeight",

        weight_uom.code
          AS "weightUomCode",

        pc.length::double precision
          AS length,

        pc.width::double precision
          AS width,

        pc.height::double precision
          AS height,

        dimension_uom.code
          AS "dimensionUomCode",

        pc.is_default
          AS "isDefault",

        pc.status,

        TO_CHAR(
          pc.valid_from,
          'YYYY-MM-DD'
        ) AS "validFrom",

        TO_CHAR(
          pc.valid_to,
          'YYYY-MM-DD'
        ) AS "validTo",

        pc.source_type
          AS "sourceType",

        pc.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        pc.confidence::double precision
          AS confidence,

        pc.metadata,

        pc.created_at
          AS "createdAt",

        pc.updated_at
          AS "updatedAt"

      FROM packaging_configurations pc

      JOIN package_types pt
        ON pt.id =
           pc.package_type_id

      LEFT JOIN units_of_measure content_uom
        ON content_uom.id =
           pc.content_uom_id

      LEFT JOIN packaging_configurations inner_pc
        ON inner_pc.id =
           pc.inner_packaging_id

      LEFT JOIN units_of_measure weight_uom
        ON weight_uom.id =
           pc.weight_uom_id

      LEFT JOIN units_of_measure dimension_uom
        ON dimension_uom.id =
           pc.dimension_uom_id

      WHERE pc.id =
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


export async function packagingRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/reference/package-types",
    async (
      request,
      reply
    ) => {

      const parsed =
        packageTypeListSchema.safeParse(
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
        active,
        limit,
        offset
      } = parsed.data;


      const result =
        await database.query(
          `
          SELECT
            id::text,
            code,
            name,
            standard,
            is_active
              AS "isActive",
            metadata,
            COUNT(*) OVER()::int
              AS "totalCount"
          FROM package_types
          WHERE
            (
              $1::text IS NULL
              OR code ILIKE
                 '%' || $1 || '%'
              OR name ILIKE
                 '%' || $1 || '%'
            )
            AND (
              $2::boolean IS NULL
              OR is_active =
                 $2
            )
          ORDER BY
            name,
            code
          LIMIT $3
          OFFSET $4
          `,
          [
            q ?? null,
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

        packageTypes:
          result.rows.map(
            row => {

              const {
                totalCount: _totalCount,
                ...packageType
              } = row;

              return packageType;

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
    "/api/manufacturer-products/:id/packaging",
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
          SELECT id::text
          FROM packaging_configurations
          WHERE manufacturer_product_id =
                $1::uuid
          ORDER BY
            CASE packaging_level
              WHEN 'primary' THEN 1
              WHEN 'secondary' THEN 2
              WHEN 'tertiary' THEN 3
              ELSE 4
            END,
            is_default DESC,
            name
          `,
          [
            params.data.id
          ]
        );


      const packaging =
        [] as Record<
          string,
          unknown
        >[];


      for (
        const row
        of result.rows
      ) {

        const item =
          await loadPackaging(
            row.id
          );


        if (item) {
          packaging.push(
            item
          );
        }

      }


      return {

        ok: true,

        manufacturerProductId:
          params.data.id,

        packaging

      };

    }
  );


  app.post(
    "/api/manufacturer-products/:id/packaging",
    async (
      request,
      reply
    ) => {

      const params =
        subjectParamsSchema.safeParse(
          request.params
        );


      const body =
        createPackagingSchema.safeParse(
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


      const packageType =
        await loadPackageType(
          body.data.packageTypeCode
        );


      if (
        !packageType
        || !packageType.isActive
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "package_type_not_found"

        };

      }


      const [
        contentUom,
        weightUom,
        dimensionUom
      ] =
        await Promise.all([

          loadUom(
            body.data.contentUomCode
          ),

          loadUom(
            body.data.weightUomCode
          ),

          loadUom(
            body.data.dimensionUomCode
          )

        ]);


      if (
        body.data.contentUomCode
        && (
          !contentUom
          || !contentUom.isActive
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "content_uom_not_found"

        };

      }


      if (
        body.data.weightUomCode
        && (
          !weightUom
          || !weightUom.isActive
          || weightUom.dimensionCode
             !== "mass"
        )
      ) {

        reply.code(409);

        return {

          ok: false,

          error:
            "weight_uom_must_be_mass"

        };

      }


      if (
        body.data.dimensionUomCode
        && (
          !dimensionUom
          || !dimensionUom.isActive
          || dimensionUom.dimensionCode
             !== "length"
        )
      ) {

        reply.code(409);

        return {

          ok: false,

          error:
            "dimension_uom_must_be_length"

        };

      }


      if (
        body.data.innerPackagingId
      ) {

        const inner =
          await loadPackaging(
            body.data.innerPackagingId
          );


        if (!inner) {

          reply.code(404);

          return {

            ok: false,

            error:
              "inner_packaging_not_found"

          };

        }


        if (
          inner.manufacturerProductId
          !== params.data.id
        ) {

          reply.code(409);

          return {

            ok: false,

            error:
              "inner_packaging_product_mismatch"

          };

        }

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO packaging_configurations (
                manufacturer_product_id,
                package_type_id,
                name,
                packaging_level,
                packaging_material,
                content_quantity,
                content_uom_id,
                inner_packaging_id,
                inner_package_count,
                net_weight,
                gross_weight,
                weight_uom_id,
                length,
                width,
                height,
                dimension_uom_id,
                is_default,
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
                $4,
                $5,
                $6,
                $7::uuid,
                $8::uuid,
                $9,
                $10,
                $11,
                $12::uuid,
                $13,
                $14,
                $15,
                $16::uuid,
                $17,
                'active',
                $18::date,
                $19::date,
                $20,
                $21::uuid,
                $22,
                $23::jsonb
            )
            RETURNING id::text
            `,
            [
              params.data.id,
              packageType.id,
              body.data.name,
              body.data.packagingLevel,
              body.data.packagingMaterial ?? null,
              body.data.contentQuantity ?? null,
              contentUom?.id ?? null,
              body.data.innerPackagingId ?? null,
              body.data.innerPackageCount ?? null,
              body.data.netWeight ?? null,
              body.data.grossWeight ?? null,
              weightUom?.id ?? null,
              body.data.length ?? null,
              body.data.width ?? null,
              body.data.height ?? null,
              dimensionUom?.id ?? null,
              body.data.isDefault,
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

          packaging:
            await loadPackaging(
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
              "packaging_configuration_conflict"

          };

        }


        request.log.error(
          error
        );

        reply.code(500);

        return {

          ok: false,

          error:
            "packaging_create_failed"

        };

      }

    }
  );


  app.get(
    "/api/packaging/:id",
    async (
      request,
      reply
    ) => {

      const params =
        packagingParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const packaging =
        await loadPackaging(
          params.data.id
        );


      if (!packaging) {

        reply.code(404);

        return {

          ok: false,

          error:
            "packaging_not_found"

        };

      }


      return {

        ok: true,

        packaging

      };

    }
  );

}
