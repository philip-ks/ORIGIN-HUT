import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const uomCodeSchema =
  z.string()
    .trim()
    .min(1)
    .max(3)
    .transform(
      value =>
        value.toUpperCase()
    );


const unitParamsSchema =
  z.object({

    code:
      uomCodeSchema

  });


const unitListQuerySchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .optional(),

    dimension: z
      .string()
      .trim()
      .min(1)
      .max(100)
      .transform(
        value =>
          value.toLowerCase()
      )
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


const conversionSchema =
  z.object({

    value: z.coerce
      .number()
      .finite(),

    fromCode:
      uomCodeSchema,

    toCode:
      uomCodeSchema

  });


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


export async function unitRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/reference/units",
    async (
      request,
      reply
    ) => {

      const parsed =
        unitListQuerySchema.safeParse(
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
        dimension,
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
            symbol,

            dimension_code
              AS "dimensionCode",

            standard,

            scale_to_base::double precision
              AS "scaleToBase",

            offset_to_base::double precision
              AS "offsetToBase",

            is_dimension_base
              AS "isDimensionBase",

            is_linear_convertible
              AS "isLinearConvertible",

            is_active
              AS "isActive",

            metadata,

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM units_of_measure

          WHERE
            (
              $1::text IS NULL
              OR code ILIKE
                 '%' || $1 || '%'
              OR name ILIKE
                 '%' || $1 || '%'
              OR symbol ILIKE
                 '%' || $1 || '%'
            )

            AND (
              $2::text IS NULL
              OR dimension_code =
                 $2
            )

            AND (
              $3::boolean IS NULL
              OR is_active =
                 $3
            )

          ORDER BY
            dimension_code,
            code

          LIMIT $4
          OFFSET $5
          `,
          [
            q ?? null,
            dimension ?? null,
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

        units:
          result.rows.map(
            row => {

              const {
                totalCount: _totalCount,
                ...unit
              } = row;

              return unit;

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
    "/api/reference/units/:code",
    async (
      request,
      reply
    ) => {

      const params =
        unitParamsSchema.safeParse(
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
            id::text,
            code,
            name,
            symbol,

            dimension_code
              AS "dimensionCode",

            standard,

            scale_to_base::double precision
              AS "scaleToBase",

            offset_to_base::double precision
              AS "offsetToBase",

            is_dimension_base
              AS "isDimensionBase",

            is_linear_convertible
              AS "isLinearConvertible",

            is_active
              AS "isActive",

            metadata

          FROM units_of_measure

          WHERE code = $1
          `,
          [
            params.data.code
          ]
        );


      if (!result.rows[0]) {

        reply.code(404);

        return {

          ok: false,

          error:
            "unit_not_found"

        };

      }


      return {

        ok: true,

        unit:
          result.rows[0]

      };

    }
  );


  app.post(
    "/api/reference/units/convert",
    async (
      request,
      reply
    ) => {

      const body =
        conversionSchema.safeParse(
          request.body
        );


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      try {

        const result =
          await database.query(
            `
            SELECT
              originhut_convert_uom(
                $1::numeric,
                $2,
                $3
              )::double precision
                AS value
            `,
            [
              body.data.value,
              body.data.fromCode,
              body.data.toCode
            ]
          );


        return {

          ok: true,

          conversion: {

            input: {
              value:
                body.data.value,

              unit:
                body.data.fromCode
            },

            output: {
              value:
                result.rows[0].value,

              unit:
                body.data.toCode
            }

          }

        };

      }
      catch (error) {

        const message =
          (
            error as Error
          ).message;


        reply.code(409);

        return {

          ok: false,

          error:
            "uom_conversion_not_available",

          message

        };

      }

    }
  );

}
