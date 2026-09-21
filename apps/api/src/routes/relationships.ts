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


const relationshipCodeSchema =
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
          "Relationship type must contain letters, numbers or underscores and begin with a letter."
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


const sourceTypeSchema =
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


function isValidIsoDate(
  value: string
) {

  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(
      value
    )
  ) {

    return false;

  }


  const [
    year,
    month,
    day
  ] =
    value
      .split("-")
      .map(Number);


  const date =
    new Date(
      Date.UTC(
        year,
        month - 1,
        day
      )
    );


  return (
    date.getUTCFullYear() === year
    && date.getUTCMonth() === month - 1
    && date.getUTCDate() === day
  );

}


const isoDateSchema =
  z.string()
    .refine(
      isValidIsoDate,
      {
        message:
          "Date must be a valid YYYY-MM-DD value."
      }
    );


const countryIso2Schema =
  z.string()
    .trim()
    .length(2)
    .transform(
      value =>
        value.toUpperCase()
    );


const relationshipParamsSchema =
  z.object({

    id: z
      .string()
      .uuid()

  });


const organizationParamsSchema =
  z.object({

    id: z
      .string()
      .uuid()

  });


const createRelationshipSchema =
  z.object({

    sourceOrganizationId: z
      .string()
      .uuid(),

    targetOrganizationId: z
      .string()
      .uuid(),

    relationshipType:
      relationshipCodeSchema,

    status:
      statusSchema
        .default("active"),

    validFrom:
      isoDateSchema
        .nullable()
        .optional(),

    validTo:
      isoDateSchema
        .nullable()
        .optional(),

    confidence: z
      .number()
      .min(0)
      .max(1)
      .nullable()
      .optional(),

    sourceType:
      sourceTypeSchema
        .default("manual"),

    notes: z
      .string()
      .trim()
      .max(10000)
      .nullable()
      .optional(),

    metadata:
      jsonObjectSchema
        .default({})

  })
  .superRefine(
    (
      value,
      context
    ) => {

      if (
        value.sourceOrganizationId
        === value.targetOrganizationId
      ) {

        context.addIssue({

          code:
            "custom",

          path:
            [
              "targetOrganizationId"
            ],

          message:
            "Source and target organizations must be different."

        });

      }


      if (
        value.validFrom
        && value.validTo
        && value.validTo < value.validFrom
      ) {

        context.addIssue({

          code:
            "custom",

          path:
            [
              "validTo"
            ],

          message:
            "validTo cannot be before validFrom."

        });

      }

    }
  );


const updateRelationshipSchema =
  z.object({

    relationshipType:
      relationshipCodeSchema
        .optional(),

    status:
      statusSchema
        .optional(),

    validFrom:
      isoDateSchema
        .nullable()
        .optional(),

    validTo:
      isoDateSchema
        .nullable()
        .optional(),

    confidence: z
      .number()
      .min(0)
      .max(1)
      .nullable()
      .optional(),

    sourceType:
      sourceTypeSchema
        .optional(),

    notes: z
      .string()
      .trim()
      .max(10000)
      .nullable()
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
        "At least one relationship field is required."
    }
  )
  .superRefine(
    (
      value,
      context
    ) => {

      if (
        value.validFrom
        && value.validTo
        && value.validTo < value.validFrom
      ) {

        context.addIssue({

          code:
            "custom",

          path:
            [
              "validTo"
            ],

          message:
            "validTo cannot be before validFrom."

        });

      }

    }
  );


const relationshipListQuerySchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .optional(),

    sourceOrganizationId: z
      .string()
      .uuid()
      .optional(),

    targetOrganizationId: z
      .string()
      .uuid()
      .optional(),

    relationshipType:
      relationshipCodeSchema
        .optional(),

    status:
      statusSchema
        .optional(),

    country:
      countryIso2Schema
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


const organizationRelationshipQuerySchema =
  z.object({

    direction: z
      .enum([
        "incoming",
        "outgoing",
        "both"
      ])
      .default("both"),

    relationshipType:
      relationshipCodeSchema
        .optional(),

    status:
      statusSchema
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


const counterpartyQuerySchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .optional(),

    direction: z
      .enum([
        "incoming",
        "outgoing",
        "both"
      ])
      .default("both"),

    relationshipType:
      relationshipCodeSchema
        .optional(),

    status:
      statusSchema
        .optional(),

    country:
      countryIso2Schema
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


type DatabaseError = {

  code?: string;

  constraint?: string;

};


function getDatabaseError(
  error: unknown
): DatabaseError {

  if (
    typeof error === "object"
    && error !== null
  ) {

    return error as DatabaseError;

  }


  return {};

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


async function loadOrganizationSummary(
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

        o.status,

        c.iso2
          AS "countryIso2",

        c.name
          AS "countryName",

        COALESCE(
          (
            SELECT jsonb_agg(
              role.role_code
              ORDER BY role.role_code
            )
            FROM organization_roles role
            WHERE role.organization_id = o.id
          ),
          '[]'::jsonb
        ) AS roles

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


async function loadRelationship(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        r.id::text AS id,

        r.source_organization_id::text
          AS "sourceOrganizationId",

        jsonb_build_object(
          'id',
          source_org.id::text,
          'legalName',
          source_org.legal_name,
          'tradingName',
          source_org.trading_name,
          'status',
          source_org.status,
          'countryIso2',
          source_country.iso2,
          'countryName',
          source_country.name
        ) AS "sourceOrganization",

        r.target_organization_id::text
          AS "targetOrganizationId",

        jsonb_build_object(
          'id',
          target_org.id::text,
          'legalName',
          target_org.legal_name,
          'tradingName',
          target_org.trading_name,
          'status',
          target_org.status,
          'countryIso2',
          target_country.iso2,
          'countryName',
          target_country.name
        ) AS "targetOrganization",

        r.relationship_type
          AS "relationshipType",

        r.status,

        TO_CHAR(
          r.valid_from,
          'YYYY-MM-DD'
        ) AS "validFrom",

        TO_CHAR(
          r.valid_to,
          'YYYY-MM-DD'
        ) AS "validTo",

        r.confidence::double precision
          AS confidence,

        r.source_type
          AS "sourceType",

        r.notes,

        r.metadata,

        r.created_at
          AS "createdAt",

        r.updated_at
          AS "updatedAt"

      FROM organization_relationships r

      JOIN organizations source_org
        ON source_org.id =
           r.source_organization_id

      JOIN organizations target_org
        ON target_org.id =
           r.target_organization_id

      LEFT JOIN countries source_country
        ON source_country.id =
           source_org.country_id

      LEFT JOIN countries target_country
        ON target_country.id =
           target_org.country_id

      WHERE r.id =
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


export async function relationshipRoutes(
  app: FastifyInstance
) {


  // ==========================================================
  // RELATIONSHIP LIST / SEARCH
  // ==========================================================

  app.get(
    "/api/organization-relationships",
    async (
      request,
      reply
    ) => {

      const query =
        relationshipListQuerySchema.safeParse(
          request.query
        );


      if (!query.success) {

        reply.code(400);

        return validationError(
          query.error.issues
        );

      }


      const {
        q,
        sourceOrganizationId,
        targetOrganizationId,
        relationshipType,
        status,
        country,
        limit,
        offset
      } = query.data;


      const result =
        await database.query(
          `
          SELECT
            r.id::text AS id,

            r.source_organization_id::text
              AS "sourceOrganizationId",

            source_org.legal_name
              AS "sourceLegalName",

            source_org.trading_name
              AS "sourceTradingName",

            source_country.iso2
              AS "sourceCountryIso2",

            r.target_organization_id::text
              AS "targetOrganizationId",

            target_org.legal_name
              AS "targetLegalName",

            target_org.trading_name
              AS "targetTradingName",

            target_country.iso2
              AS "targetCountryIso2",

            r.relationship_type
              AS "relationshipType",

            r.status,

            TO_CHAR(
              r.valid_from,
              'YYYY-MM-DD'
            ) AS "validFrom",

            TO_CHAR(
              r.valid_to,
              'YYYY-MM-DD'
            ) AS "validTo",

            r.confidence::double precision
              AS confidence,

            r.source_type
              AS "sourceType",

            r.notes,

            r.metadata,

            r.created_at
              AS "createdAt",

            r.updated_at
              AS "updatedAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM organization_relationships r

          JOIN organizations source_org
            ON source_org.id =
               r.source_organization_id

          JOIN organizations target_org
            ON target_org.id =
               r.target_organization_id

          LEFT JOIN countries source_country
            ON source_country.id =
               source_org.country_id

          LEFT JOIN countries target_country
            ON target_country.id =
               target_org.country_id

          WHERE
            (
              $1::uuid IS NULL
              OR r.source_organization_id =
                 $1::uuid
            )

            AND (
              $2::uuid IS NULL
              OR r.target_organization_id =
                 $2::uuid
            )

            AND (
              $3::text IS NULL
              OR r.relationship_type =
                 $3
            )

            AND (
              $4::text IS NULL
              OR r.status =
                 $4
            )

            AND (
              $5::text IS NULL
              OR source_country.iso2 =
                 $5
              OR target_country.iso2 =
                 $5
            )

            AND (
              $6::text IS NULL

              OR source_org.legal_name ILIKE
                 '%' || $6 || '%'

              OR source_org.trading_name ILIKE
                 '%' || $6 || '%'

              OR target_org.legal_name ILIKE
                 '%' || $6 || '%'

              OR target_org.trading_name ILIKE
                 '%' || $6 || '%'
            )

          ORDER BY
            r.updated_at DESC,
            r.created_at DESC

          LIMIT $7
          OFFSET $8
          `,
          [
            sourceOrganizationId ?? null,
            targetOrganizationId ?? null,
            relationshipType ?? null,
            status ?? null,
            country ?? null,
            q ?? null,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const relationships =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...relationship
            } = row;

            return relationship;

          }
        );


      return {

        ok: true,

        relationships,

        pagination: {

          total,

          limit,

          offset

        }

      };

    }
  );


  // ==========================================================
  // CREATE RELATIONSHIP
  // ==========================================================

  app.post(
    "/api/organization-relationships",
    async (
      request,
      reply
    ) => {

      const body =
        createRelationshipSchema.safeParse(
          request.body
        );


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      if (
        !await organizationExists(
          body.data.sourceOrganizationId
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "source_organization_not_found",

          sourceOrganizationId:
            body.data.sourceOrganizationId

        };

      }


      if (
        !await organizationExists(
          body.data.targetOrganizationId
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "target_organization_not_found",

          targetOrganizationId:
            body.data.targetOrganizationId

        };

      }


      try {

        const created =
          await database.query(
            `
            INSERT INTO organization_relationships (
              source_organization_id,
              target_organization_id,
              relationship_type,
              status,
              valid_from,
              valid_to,
              confidence,
              source_type,
              notes,
              metadata
            )
            VALUES (
              $1::uuid,
              $2::uuid,
              $3,
              $4,
              $5::date,
              $6::date,
              $7::numeric,
              $8,
              $9,
              $10::jsonb
            )
            RETURNING
              id::text
            `,
            [
              body.data.sourceOrganizationId,
              body.data.targetOrganizationId,
              body.data.relationshipType,
              body.data.status,
              body.data.validFrom ?? null,
              body.data.validTo ?? null,
              body.data.confidence ?? null,
              body.data.sourceType,
              body.data.notes ?? null,
              JSON.stringify(
                body.data.metadata
              )
            ]
          );


        const relationship =
          await loadRelationship(
            created.rows[0].id
          );


        reply.code(201);


        return {

          ok: true,

          relationship

        };

      }
      catch (error) {

        const databaseError =
          getDatabaseError(
            error
          );


        if (
          databaseError.constraint
          === "organization_relationships_active_open_unique"
        ) {

          reply.code(409);

          return {

            ok: false,

            error:
              "relationship_already_exists"

          };

        }


        if (
          databaseError.code === "23514"
        ) {

          reply.code(400);

          return {

            ok: false,

            error:
              "invalid_relationship",

            constraint:
              databaseError.constraint
              ?? null

          };

        }


        request.log.error(
          error
        );


        reply.code(500);


        return {

          ok: false,

          error:
            "relationship_create_failed"

        };

      }

    }
  );


  // ==========================================================
  // RELATIONSHIP DETAIL
  // ==========================================================

  app.get(
    "/api/organization-relationships/:id",
    async (
      request,
      reply
    ) => {

      const params =
        relationshipParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const relationship =
        await loadRelationship(
          params.data.id
        );


      if (!relationship) {

        reply.code(404);

        return {

          ok: false,

          error:
            "relationship_not_found"

        };

      }


      return {

        ok: true,

        relationship

      };

    }
  );


  // ==========================================================
  // UPDATE RELATIONSHIP
  // ==========================================================

  app.patch(
    "/api/organization-relationships/:id",
    async (
      request,
      reply
    ) => {

      const params =
        relationshipParamsSchema.safeParse(
          request.params
        );


      const body =
        updateRelationshipSchema.safeParse(
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
        body.data.relationshipType
        !== undefined
      ) {

        addValue(
          "relationship_type",
          body.data.relationshipType
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
        body.data.validFrom
        !== undefined
      ) {

        addValue(
          "valid_from",
          body.data.validFrom,
          "::date"
        );

      }


      if (
        body.data.validTo
        !== undefined
      ) {

        addValue(
          "valid_to",
          body.data.validTo,
          "::date"
        );

      }


      if (
        body.data.confidence
        !== undefined
      ) {

        addValue(
          "confidence",
          body.data.confidence,
          "::numeric"
        );

      }


      if (
        body.data.sourceType
        !== undefined
      ) {

        addValue(
          "source_type",
          body.data.sourceType
        );

      }


      if (
        body.data.notes
        !== undefined
      ) {

        addValue(
          "notes",
          body.data.notes
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


      try {

        const updated =
          await database.query(
            `
            UPDATE organization_relationships
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
              "relationship_not_found"

          };

        }


        const relationship =
          await loadRelationship(
            params.data.id
          );


        return {

          ok: true,

          relationship

        };

      }
      catch (error) {

        const databaseError =
          getDatabaseError(
            error
          );


        if (
          databaseError.constraint
          === "organization_relationships_active_open_unique"
        ) {

          reply.code(409);

          return {

            ok: false,

            error:
              "relationship_already_exists"

          };

        }


        if (
          databaseError.code === "23514"
        ) {

          reply.code(400);

          return {

            ok: false,

            error:
              "invalid_relationship",

            constraint:
              databaseError.constraint
              ?? null

          };

        }


        request.log.error(
          error
        );


        reply.code(500);


        return {

          ok: false,

          error:
            "relationship_update_failed"

        };

      }

    }
  );


  // ==========================================================
  // ORGANIZATION RELATIONSHIP VIEW
  // ==========================================================

  app.get(
    "/api/organizations/:id/relationships",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const query =
        organizationRelationshipQuerySchema.safeParse(
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
        await loadOrganizationSummary(
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


      const {
        direction,
        relationshipType,
        status,
        limit,
        offset
      } = query.data;


      const result =
        await database.query(
          `
          SELECT
            r.id::text AS id,

            CASE
              WHEN r.source_organization_id =
                   $1::uuid
              THEN 'outgoing'
              ELSE 'incoming'
            END AS direction,

            r.relationship_type
              AS "relationshipType",

            r.status,

            TO_CHAR(
              r.valid_from,
              'YYYY-MM-DD'
            ) AS "validFrom",

            TO_CHAR(
              r.valid_to,
              'YYYY-MM-DD'
            ) AS "validTo",

            r.confidence::double precision
              AS confidence,

            r.source_type
              AS "sourceType",

            r.notes,

            r.metadata,

            CASE
              WHEN r.source_organization_id =
                   $1::uuid
              THEN r.target_organization_id::text
              ELSE r.source_organization_id::text
            END AS "counterpartyId",

            CASE
              WHEN r.source_organization_id =
                   $1::uuid
              THEN target_org.legal_name
              ELSE source_org.legal_name
            END AS "counterpartyLegalName",

            CASE
              WHEN r.source_organization_id =
                   $1::uuid
              THEN target_org.trading_name
              ELSE source_org.trading_name
            END AS "counterpartyTradingName",

            CASE
              WHEN r.source_organization_id =
                   $1::uuid
              THEN target_country.iso2
              ELSE source_country.iso2
            END AS "counterpartyCountryIso2",

            r.created_at
              AS "createdAt",

            r.updated_at
              AS "updatedAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM organization_relationships r

          JOIN organizations source_org
            ON source_org.id =
               r.source_organization_id

          JOIN organizations target_org
            ON target_org.id =
               r.target_organization_id

          LEFT JOIN countries source_country
            ON source_country.id =
               source_org.country_id

          LEFT JOIN countries target_country
            ON target_country.id =
               target_org.country_id

          WHERE
            (
              r.source_organization_id =
                $1::uuid

              OR r.target_organization_id =
                 $1::uuid
            )

            AND (
              $2::text = 'both'

              OR (
                $2::text = 'outgoing'
                AND r.source_organization_id =
                    $1::uuid
              )

              OR (
                $2::text = 'incoming'
                AND r.target_organization_id =
                    $1::uuid
              )
            )

            AND (
              $3::text IS NULL
              OR r.relationship_type =
                 $3
            )

            AND (
              $4::text IS NULL
              OR r.status =
                 $4
            )

          ORDER BY
            r.updated_at DESC,
            r.created_at DESC

          LIMIT $5
          OFFSET $6
          `,
          [
            params.data.id,
            direction,
            relationshipType ?? null,
            status ?? null,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const relationships =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...relationship
            } = row;

            return relationship;

          }
        );


      return {

        ok: true,

        organization,

        relationships,

        pagination: {

          total,

          limit,

          offset

        }

      };

    }
  );


  // ==========================================================
  // COUNTERPARTY NETWORK VIEW
  // ==========================================================

  app.get(
    "/api/organizations/:id/counterparties",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const query =
        counterpartyQuerySchema.safeParse(
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
        await loadOrganizationSummary(
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


      const {
        q,
        direction,
        relationshipType,
        status,
        country,
        limit,
        offset
      } = query.data;


      const result =
        await database.query(
          `
          WITH edges AS (

            SELECT
              r.id,

              r.relationship_type,

              r.status,

              r.valid_from,

              r.valid_to,

              r.confidence,

              r.source_type,

              r.notes,

              r.metadata,

              r.created_at,

              r.updated_at,

              CASE
                WHEN r.source_organization_id =
                     $1::uuid
                THEN 'outgoing'
                ELSE 'incoming'
              END AS direction,

              CASE
                WHEN r.source_organization_id =
                     $1::uuid
                THEN r.target_organization_id
                ELSE r.source_organization_id
              END AS counterparty_id

            FROM organization_relationships r

            WHERE
              (
                r.source_organization_id =
                  $1::uuid

                OR r.target_organization_id =
                   $1::uuid
              )

              AND (
                $2::text = 'both'

                OR (
                  $2::text = 'outgoing'
                  AND r.source_organization_id =
                      $1::uuid
                )

                OR (
                  $2::text = 'incoming'
                  AND r.target_organization_id =
                      $1::uuid
                )
              )

              AND (
                $3::text IS NULL
                OR r.relationship_type =
                   $3
              )

              AND (
                $4::text IS NULL
                OR r.status =
                   $4
              )

          ),

          grouped AS (

            SELECT
              edge.counterparty_id,

              MAX(
                edge.updated_at
              ) AS latest_relationship_at,

              COUNT(*)::int
                AS relationship_count,

              jsonb_agg(
                jsonb_build_object(
                  'id',
                  edge.id::text,

                  'direction',
                  edge.direction,

                  'relationshipType',
                  edge.relationship_type,

                  'status',
                  edge.status,

                  'validFrom',
                  TO_CHAR(
                    edge.valid_from,
                    'YYYY-MM-DD'
                  ),

                  'validTo',
                  TO_CHAR(
                    edge.valid_to,
                    'YYYY-MM-DD'
                  ),

                  'confidence',
                  edge.confidence::double precision,

                  'sourceType',
                  edge.source_type,

                  'notes',
                  edge.notes,

                  'metadata',
                  edge.metadata,

                  'createdAt',
                  edge.created_at,

                  'updatedAt',
                  edge.updated_at
                )
                ORDER BY
                  edge.updated_at DESC
              ) AS relationships

            FROM edges edge

            GROUP BY
              edge.counterparty_id

          )

          SELECT
            counterparty.id::text
              AS id,

            counterparty.legal_name
              AS "legalName",

            counterparty.trading_name
              AS "tradingName",

            counterparty.status,

            country_ref.iso2
              AS "countryIso2",

            country_ref.name
              AS "countryName",

            COALESCE(
              (
                SELECT jsonb_agg(
                  role.role_code
                  ORDER BY role.role_code
                )
                FROM organization_roles role
                WHERE role.organization_id =
                      counterparty.id
              ),
              '[]'::jsonb
            ) AS roles,

            grouped.relationship_count
              AS "relationshipCount",

            grouped.relationships,

            grouped.latest_relationship_at
              AS "latestRelationshipAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM grouped

          JOIN organizations counterparty
            ON counterparty.id =
               grouped.counterparty_id

          LEFT JOIN countries country_ref
            ON country_ref.id =
               counterparty.country_id

          WHERE
            (
              $5::text IS NULL

              OR counterparty.legal_name ILIKE
                 '%' || $5 || '%'

              OR counterparty.trading_name ILIKE
                 '%' || $5 || '%'
            )

            AND (
              $6::text IS NULL
              OR country_ref.iso2 =
                 $6
            )

          ORDER BY
            grouped.latest_relationship_at DESC,
            counterparty.legal_name

          LIMIT $7
          OFFSET $8
          `,
          [
            params.data.id,
            direction,
            relationshipType ?? null,
            status ?? null,
            q ?? null,
            country ?? null,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const counterparties =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...counterparty
            } = row;

            return counterparty;

          }
        );


      return {

        ok: true,

        organization,

        counterparties,

        pagination: {

          total,

          limit,

          offset

        }

      };

    }
  );

}
