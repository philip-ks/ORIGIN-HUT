import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const codeSchema =
  z.string()
    .trim()
    .length(3)
    .transform(
      value =>
        value.toUpperCase()
    );


const paramsSchema =
  z.object({

    edition: z.coerce
      .number()
      .int()
      .positive(),

    code:
      codeSchema

  });


const listSchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .optional(),

    edition: z.coerce
      .number()
      .int()
      .positive()
      .optional(),

    transportScope: z
      .enum([
        "any_mode",
        "sea_inland_waterway"
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
      .max(100)
      .default(50),

    offset: z.coerce
      .number()
      .int()
      .min(0)
      .default(0)

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


export async function incotermRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/reference/incoterms",
    async (
      request,
      reply
    ) => {

      const parsed =
        listSchema.safeParse(
          request.query
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
            id::text,
            edition,
            code,
            name,

            transport_scope
              AS "transportScope",

            named_location_role
              AS "namedLocationRole",

            is_active
              AS "isActive",

            metadata,

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM incoterm_rules

          WHERE
            (
              $1::text IS NULL
              OR code ILIKE
                 '%' || $1 || '%'
              OR name ILIKE
                 '%' || $1 || '%'
            )

            AND (
              $2::integer IS NULL
              OR edition =
                 $2
            )

            AND (
              $3::text IS NULL
              OR transport_scope =
                 $3
            )

            AND (
              $4::boolean IS NULL
              OR is_active =
                 $4
            )

          ORDER BY
            edition DESC,
            CASE transport_scope
              WHEN 'any_mode'
              THEN 1
              ELSE 2
            END,
            code

          LIMIT $5
          OFFSET $6
          `,
          [
            parsed.data.q
              ?? null,

            parsed.data.edition
              ?? null,

            parsed.data.transportScope
              ?? null,

            parsed.data.active
              ?? null,

            parsed.data.limit,
            parsed.data.offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      return {

        ok: true,

        incoterms:
          result.rows.map(
            row => {

              const {
                totalCount: _totalCount,
                ...incoterm
              } = row;

              return incoterm;

            }
          ),

        pagination: {
          total,
          limit:
            parsed.data.limit,
          offset:
            parsed.data.offset
        }

      };

    }
  );


  app.get(
    "/api/reference/incoterms/:edition/:code",
    async (
      request,
      reply
    ) => {

      const params =
        paramsSchema.safeParse(
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
            edition,
            code,
            name,

            transport_scope
              AS "transportScope",

            named_location_role
              AS "namedLocationRole",

            is_active
              AS "isActive",

            metadata,

            created_at
              AS "createdAt",

            updated_at
              AS "updatedAt"

          FROM incoterm_rules

          WHERE
            edition = $1
            AND code = $2
          `,
          [
            params.data.edition,
            params.data.code
          ]
        );


      if (!result.rows[0]) {

        reply.code(404);

        return {

          ok: false,

          error:
            "incoterm_not_found",

          edition:
            params.data.edition,

          code:
            params.data.code

        };

      }


      return {

        ok: true,

        incoterm:
          result.rows[0]

      };

    }
  );

}
