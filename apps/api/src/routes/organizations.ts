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


const countryIso2Schema =
  z.string()
    .trim()
    .length(2)
    .transform(
      value =>
        value.toUpperCase()
    );


const roleCodeSchema =
  z.string()
    .trim()
    .min(1)
    .max(64)
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
          "Role must contain letters, numbers or underscores and begin with a letter."
      }
    );


const statusSchema =
  z.string()
    .trim()
    .min(1)
    .max(50)
    .transform(
      value =>
        value.toLowerCase()
    );


const leiSchema =
  z.string()
    .trim()
    .transform(
      value =>
        value.toUpperCase()
    )
    .refine(
      value =>
        /^[A-Z0-9]{20}$/.test(
          value
        ),
      {
        message:
          "LEI must contain exactly 20 alphanumeric characters."
      }
    );


const organizationParamsSchema =
  z.object({

    id: z
      .string()
      .uuid()

  });


const organizationRoleParamsSchema =
  z.object({

    id: z
      .string()
      .uuid(),

    role:
      roleCodeSchema

  });


const organizationListQuerySchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .optional(),

    country:
      countryIso2Schema
        .optional(),

    role:
      roleCodeSchema
        .optional(),

    status:
      statusSchema
        .optional(),

    registrationNumber: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .optional(),

    lei:
      leiSchema
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


const createOrganizationSchema =
  z.object({

    legalName: z
      .string()
      .trim()
      .min(1)
      .max(500),

    tradingName: z
      .string()
      .trim()
      .min(1)
      .max(500)
      .nullable()
      .optional(),

    country:
      countryIso2Schema
        .nullable()
        .optional(),

    registrationNumber: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .nullable()
      .optional(),

    lei:
      leiSchema
        .nullable()
        .optional(),

    taxIdentifier: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .nullable()
      .optional(),

    website: z
      .string()
      .trim()
      .max(500)
      .url()
      .nullable()
      .optional(),

    status:
      statusSchema
        .default("active"),

    address:
      jsonObjectSchema
        .default({}),

    identifiers:
      jsonObjectSchema
        .default({}),

    metadata:
      jsonObjectSchema
        .default({}),

    roles: z
      .array(
        roleCodeSchema
      )
      .max(50)
      .default([])
      .transform(
        values =>
          Array.from(
            new Set(values)
          )
      )

  });


const updateOrganizationSchema =
  z.object({

    legalName: z
      .string()
      .trim()
      .min(1)
      .max(500)
      .optional(),

    tradingName: z
      .string()
      .trim()
      .min(1)
      .max(500)
      .nullable()
      .optional(),

    country:
      countryIso2Schema
        .nullable()
        .optional(),

    registrationNumber: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .nullable()
      .optional(),

    lei:
      leiSchema
        .nullable()
        .optional(),

    taxIdentifier: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .nullable()
      .optional(),

    website: z
      .string()
      .trim()
      .max(500)
      .url()
      .nullable()
      .optional(),

    status:
      statusSchema
        .optional(),

    address:
      jsonObjectSchema
        .optional(),

    identifiers:
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
        "At least one organization field is required."
    }
  );


const addRoleSchema =
  z.object({

    role:
      roleCodeSchema

  });


const organizationProductsQuerySchema =
  z.object({

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


async function resolveCountryId(
  iso2: string
) {

  const result =
    await database.query(
      `
      SELECT
        id::text
      FROM countries
      WHERE
        iso2 = $1
        AND is_active = TRUE
      LIMIT 1
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


async function organizationExists(
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


async function loadRoles(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        role_code AS role,
        created_at AS "createdAt"
      FROM organization_roles
      WHERE organization_id = $1::uuid
      ORDER BY role_code
      `,
      [
        id
      ]
    );


  return result.rows;

}


async function loadOrganization(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        o.id::text AS id,

        o.legal_name
          AS "legalName",

        o.trading_name
          AS "tradingName",

        CASE
          WHEN c.id IS NULL
          THEN NULL
          ELSE jsonb_build_object(
            'id',
            c.id::text,
            'iso2',
            c.iso2,
            'iso3',
            c.iso3,
            'name',
            c.name
          )
        END AS country,

        o.registration_number
          AS "registrationNumber",

        o.lei,

        o.tax_identifier
          AS "taxIdentifier",

        o.website,

        o.status,

        o.address,

        o.identifiers,

        o.metadata,

        COALESCE(
          (
            SELECT jsonb_agg(
              r.role_code
              ORDER BY r.role_code
            )
            FROM organization_roles r
            WHERE r.organization_id = o.id
          ),
          '[]'::jsonb
        ) AS roles,

        (
          SELECT COUNT(*)::int
          FROM products p
          WHERE p.manufacturer_id = o.id
        ) AS "productCount",

        o.created_at
          AS "createdAt",

        o.updated_at
          AS "updatedAt"

      FROM organizations o

      LEFT JOIN countries c
        ON c.id =
           o.country_id

      WHERE o.id =
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


export async function organizationRoutes(
  app: FastifyInstance
) {


  // ==========================================================
  // ORGANIZATION LIST / SEARCH
  // ==========================================================

  app.get(
    "/api/organizations",
    async (
      request,
      reply
    ) => {

      const parsed =
        organizationListQuerySchema.safeParse(
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
        role,
        status,
        registrationNumber,
        lei,
        limit,
        offset
      } = parsed.data;


      const result =
        await database.query(
          `
          SELECT
            o.id::text AS id,

            o.legal_name
              AS "legalName",

            o.trading_name
              AS "tradingName",

            c.iso2
              AS "countryIso2",

            c.name
              AS "countryName",

            o.registration_number
              AS "registrationNumber",

            o.lei,

            o.tax_identifier
              AS "taxIdentifier",

            o.website,

            o.status,

            COALESCE(
              (
                SELECT jsonb_agg(
                  r.role_code
                  ORDER BY r.role_code
                )
                FROM organization_roles r
                WHERE r.organization_id = o.id
              ),
              '[]'::jsonb
            ) AS roles,

            (
              SELECT COUNT(*)::int
              FROM products p
              WHERE p.manufacturer_id = o.id
            ) AS "productCount",

            o.created_at
              AS "createdAt",

            o.updated_at
              AS "updatedAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM organizations o

          LEFT JOIN countries c
            ON c.id =
               o.country_id

          WHERE
            (
              $1::text IS NULL

              OR o.legal_name ILIKE
                 '%' || $1 || '%'

              OR o.trading_name ILIKE
                 '%' || $1 || '%'

              OR o.registration_number ILIKE
                 '%' || $1 || '%'

              OR o.lei ILIKE
                 '%' || $1 || '%'

              OR o.tax_identifier ILIKE
                 '%' || $1 || '%'

              OR o.website ILIKE
                 '%' || $1 || '%'
            )

            AND (
              $2::text IS NULL
              OR c.iso2 = $2
            )

            AND (
              $3::text IS NULL

              OR EXISTS (
                SELECT 1
                FROM organization_roles role_filter
                WHERE
                  role_filter.organization_id =
                    o.id

                  AND role_filter.role_code =
                    $3
              )
            )

            AND (
              $4::text IS NULL
              OR o.status = $4
            )

            AND (
              $5::text IS NULL
              OR o.registration_number = $5
            )

            AND (
              $6::text IS NULL
              OR UPPER(o.lei) = UPPER($6)
            )

          ORDER BY

            CASE
              WHEN $1::text IS NOT NULL
              THEN
                GREATEST(
                  similarity(
                    LOWER(
                      COALESCE(
                        o.legal_name,
                        ''
                      )
                    ),
                    LOWER($1)
                  ),
                  similarity(
                    LOWER(
                      COALESCE(
                        o.trading_name,
                        ''
                      )
                    ),
                    LOWER($1)
                  )
                )
              ELSE 0
            END DESC,

            o.updated_at DESC

          LIMIT $7
          OFFSET $8
          `,
          [
            q ?? null,
            country ?? null,
            role ?? null,
            status ?? null,
            registrationNumber ?? null,
            lei ?? null,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const organizations =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...organization
            } = row;

            return organization;

          }
        );


      return {

        ok: true,

        organizations,

        pagination: {

          total,

          limit,

          offset

        }

      };

    }
  );


  // ==========================================================
  // CREATE ORGANIZATION
  // ==========================================================

  app.post(
    "/api/organizations",
    async (
      request,
      reply
    ) => {

      const parsed =
        createOrganizationSchema.safeParse(
          request.body
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      let countryId:
        string | null = null;


      if (parsed.data.country) {

        countryId =
          await resolveCountryId(
            parsed.data.country
          );


        if (!countryId) {

          reply.code(404);

          return {

            ok: false,

            error:
              "country_not_found",

            country:
              parsed.data.country

          };

        }

      }


      const client =
        await database.connect();


      try {

        await client.query(
          "BEGIN"
        );


        const created =
          await client.query(
            `
            INSERT INTO organizations (
              legal_name,
              trading_name,
              country_id,
              registration_number,
              lei,
              tax_identifier,
              website,
              status,
              address,
              identifiers,
              metadata
            )
            VALUES (
              $1,
              $2,
              $3::uuid,
              $4,
              $5,
              $6,
              $7,
              $8,
              $9::jsonb,
              $10::jsonb,
              $11::jsonb
            )
            RETURNING
              id::text
            `,
            [
              parsed.data.legalName,
              parsed.data.tradingName ?? null,
              countryId,
              parsed.data.registrationNumber ?? null,
              parsed.data.lei ?? null,
              parsed.data.taxIdentifier ?? null,
              parsed.data.website ?? null,
              parsed.data.status,
              JSON.stringify(
                parsed.data.address
              ),
              JSON.stringify(
                parsed.data.identifiers
              ),
              JSON.stringify(
                parsed.data.metadata
              )
            ]
          );


        const organizationId =
          created.rows[0].id;


        for (
          const role
          of parsed.data.roles
        ) {

          await client.query(
            `
            INSERT INTO organization_roles (
              organization_id,
              role_code
            )
            VALUES (
              $1::uuid,
              $2
            )
            ON CONFLICT DO NOTHING
            `,
            [
              organizationId,
              role
            ]
          );

        }


        await client.query(
          "COMMIT"
        );


        const organization =
          await loadOrganization(
            organizationId
          );


        reply.code(201);


        return {

          ok: true,

          organization

        };

      }
      catch (error) {

        await client.query(
          "ROLLBACK"
        );


        request.log.error(
          error
        );


        reply.code(500);


        return {

          ok: false,

          error:
            "organization_create_failed"

        };

      }
      finally {

        client.release();

      }

    }
  );


  // ==========================================================
  // ORGANIZATION DETAIL
  // ==========================================================

  app.get(
    "/api/organizations/:id",
    async (
      request,
      reply
    ) => {

      const parsed =
        organizationParamsSchema.safeParse(
          request.params
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const organization =
        await loadOrganization(
          parsed.data.id
        );


      if (!organization) {

        reply.code(404);

        return {

          ok: false,

          error:
            "organization_not_found"

        };

      }


      return {

        ok: true,

        organization

      };

    }
  );


  // ==========================================================
  // UPDATE ORGANIZATION
  // ==========================================================

  app.patch(
    "/api/organizations/:id",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const body =
        updateOrganizationSchema.safeParse(
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


      let countryId:
        string | null | undefined =
          undefined;


      if (
        body.data.country
        !== undefined
      ) {

        if (
          body.data.country
          === null
        ) {

          countryId = null;

        }
        else {

          countryId =
            await resolveCountryId(
              body.data.country
            );


          if (!countryId) {

            reply.code(404);

            return {

              ok: false,

              error:
                "country_not_found",

              country:
                body.data.country

            };

          }

        }

      }


      const updates:
        string[] = [];

      const values:
        unknown[] = [];


      function addValue(
        column: string,
        value: unknown,
        cast = ""
      ) {

        values.push(
          value
        );

        updates.push(
          `${column} = $${values.length}${cast}`
        );

      }


      if (
        body.data.legalName
        !== undefined
      ) {

        addValue(
          "legal_name",
          body.data.legalName
        );

      }


      if (
        body.data.tradingName
        !== undefined
      ) {

        addValue(
          "trading_name",
          body.data.tradingName
        );

      }


      if (
        countryId
        !== undefined
      ) {

        addValue(
          "country_id",
          countryId,
          "::uuid"
        );

      }


      if (
        body.data.registrationNumber
        !== undefined
      ) {

        addValue(
          "registration_number",
          body.data.registrationNumber
        );

      }


      if (
        body.data.lei
        !== undefined
      ) {

        addValue(
          "lei",
          body.data.lei
        );

      }


      if (
        body.data.taxIdentifier
        !== undefined
      ) {

        addValue(
          "tax_identifier",
          body.data.taxIdentifier
        );

      }


      if (
        body.data.website
        !== undefined
      ) {

        addValue(
          "website",
          body.data.website
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


      if (
        body.data.address
        !== undefined
      ) {

        values.push(
          JSON.stringify(
            body.data.address
          )
        );

        updates.push(
          `address =
             address
             || $${values.length}::jsonb`
        );

      }


      if (
        body.data.identifiers
        !== undefined
      ) {

        values.push(
          JSON.stringify(
            body.data.identifiers
          )
        );

        updates.push(
          `identifiers =
             identifiers
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


      const updated =
        await database.query(
          `
          UPDATE organizations
          SET
            ${updates.join(",\n")}
          WHERE id =
                $${values.length}::uuid
          RETURNING
            id::text
          `,
          values
        );


      if (!updated.rows[0]) {

        reply.code(404);

        return {

          ok: false,

          error:
            "organization_not_found"

        };

      }


      const organization =
        await loadOrganization(
          params.data.id
        );


      return {

        ok: true,

        organization

      };

    }
  );


  // ==========================================================
  // ORGANIZATION ROLES
  // ==========================================================

  app.get(
    "/api/organizations/:id/roles",
    async (
      request,
      reply
    ) => {

      const parsed =
        organizationParamsSchema.safeParse(
          request.params
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      if (
        !await organizationExists(
          parsed.data.id
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "organization_not_found"

        };

      }


      return {

        ok: true,

        organizationId:
          parsed.data.id,

        roles:
          await loadRoles(
            parsed.data.id
          )

      };

    }
  );


  app.post(
    "/api/organizations/:id/roles",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const body =
        addRoleSchema.safeParse(
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


      await database.query(
        `
        INSERT INTO organization_roles (
          organization_id,
          role_code
        )
        VALUES (
          $1::uuid,
          $2
        )
        ON CONFLICT DO NOTHING
        `,
        [
          params.data.id,
          body.data.role
        ]
      );


      return {

        ok: true,

        organizationId:
          params.data.id,

        roles:
          await loadRoles(
            params.data.id
          )

      };

    }
  );


  app.delete(
    "/api/organizations/:id/roles/:role",
    async (
      request,
      reply
    ) => {

      const parsed =
        organizationRoleParamsSchema.safeParse(
          request.params
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      if (
        !await organizationExists(
          parsed.data.id
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "organization_not_found"

        };

      }


      if (
        parsed.data.role
        === "manufacturer"
      ) {

        const productCheck =
          await database.query(
            `
            SELECT COUNT(*)::int AS total
            FROM products
            WHERE manufacturer_id =
                  $1::uuid
            `,
            [
              parsed.data.id
            ]
          );


        if (
          productCheck.rows[0].total
          > 0
        ) {

          reply.code(409);

          return {

            ok: false,

            error:
              "organization_role_in_use",

            role:
              "manufacturer",

            productCount:
              productCheck.rows[0].total

          };

        }

      }


      const deleted =
        await database.query(
          `
          DELETE FROM organization_roles
          WHERE
            organization_id =
              $1::uuid

            AND role_code =
              $2
          RETURNING role_code
          `,
          [
            parsed.data.id,
            parsed.data.role
          ]
        );


      if (!deleted.rows[0]) {

        reply.code(404);

        return {

          ok: false,

          error:
            "organization_role_not_found",

          role:
            parsed.data.role

        };

      }


      return {

        ok: true,

        organizationId:
          parsed.data.id,

        removedRole:
          parsed.data.role,

        roles:
          await loadRoles(
            parsed.data.id
          )

      };

    }
  );


  // ==========================================================
  // ORGANIZATION PRODUCTS
  // ==========================================================

  app.get(
    "/api/organizations/:id/products",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const query =
        organizationProductsQuerySchema.safeParse(
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


      const organization =
        await loadOrganization(
          params.data.id
        );


      if (!organization) {

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
          SELECT
            p.id::text AS id,

            p.name,

            p.brand,

            p.sku,

            p.gtin,

            p.description,

            p.is_active
              AS "isActive",

            (
              SELECT COUNT(*)::int
              FROM product_hs_classifications phc
              WHERE phc.product_id = p.id
            ) AS "classificationCount",

            p.created_at
              AS "createdAt",

            p.updated_at
              AS "updatedAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM products p

          WHERE
            p.manufacturer_id =
              $1::uuid

            AND (
              $2::boolean IS NULL
              OR p.is_active =
                 $2::boolean
            )

          ORDER BY
            p.updated_at DESC

          LIMIT $3
          OFFSET $4
          `,
          [
            params.data.id,
            query.data.active ?? null,
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

        organization: {

          id:
            organization.id,

          legalName:
            organization.legalName,

          tradingName:
            organization.tradingName

        },

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

}
