import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const countryIso2Schema =
  z.string()
    .trim()
    .length(2)
    .transform(
      value =>
        value.toUpperCase()
    );


const normalizedCodeSchema =
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
          "Value must begin with a letter and contain only letters, numbers or underscores."
      }
    );


const hsCodeSchema =
  z.string()
    .trim()
    .refine(
      value =>
        /^\d{2,6}$/.test(
          value
        ),
      {
        message:
          "HS code must contain 2 to 6 digits."
      }
    );


const nomenclatureSchema =
  z.string()
    .trim()
    .min(1)
    .max(32)
    .transform(
      value =>
        value.toUpperCase()
    );


const counterpartyQuerySchema =
  z.object({

    q: z
      .string()
      .trim()
      .min(1)
      .max(500)
      .optional(),

    country:
      countryIso2Schema
        .optional(),

    marketCountry:
      countryIso2Schema
        .optional(),

    activityType:
      normalizedCodeSchema
        .optional(),

    hsCode:
      hsCodeSchema
        .optional(),

    hsNomenclature:
      nomenclatureSchema
        .default("HS2022"),

    productId: z
      .string()
      .uuid()
      .optional(),

    status:
      normalizedCodeSchema
        .default("active"),

    minimumConfidence: z.coerce
      .number()
      .min(0)
      .max(1)
      .optional(),

    limit: z.coerce
      .number()
      .int()
      .min(1)
      .max(100)
      .default(25),

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


export async function counterpartyIntelligenceRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/intelligence/counterparties",
    async (
      request,
      reply
    ) => {

      const parsed =
        counterpartyQuerySchema.safeParse(
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
        marketCountry,
        activityType,
        hsCode,
        hsNomenclature,
        productId,
        status,
        minimumConfidence,
        limit,
        offset
      } = parsed.data;


      const filterValues = [

        q ?? null,
        country ?? null,
        marketCountry ?? null,
        activityType ?? null,
        hsCode ?? null,
        hsNomenclature,
        productId ?? null,
        status,
        minimumConfidence ?? null

      ];


      const activityFilter = `
        FROM organization_trade_activities ota

        JOIN organizations o
          ON o.id =
             ota.organization_id

        LEFT JOIN countries organization_country
          ON organization_country.id =
             o.country_id

        LEFT JOIN countries market_country
          ON market_country.id =
             ota.market_country_id

        LEFT JOIN hs_codes h
          ON h.id =
             ota.hs_code_id

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

            OR EXISTS (
              SELECT 1
              FROM organization_aliases alias_filter
              WHERE
                alias_filter.organization_id =
                  o.id

                AND alias_filter.is_active =
                  TRUE

                AND (
                  alias_filter.alias ILIKE
                    '%' || $1 || '%'

                  OR alias_filter.normalized_alias ILIKE
                    '%' ||
                    NULLIF(
                      originhut_normalize_organization_name(
                        $1
                      ),
                      ''
                    )
                    || '%'
                )
            )
          )

          AND (
            $2::text IS NULL
            OR organization_country.iso2 =
               $2
          )

          AND (
            $3::text IS NULL
            OR market_country.iso2 =
               $3
          )

          AND (
            $4::text IS NULL
            OR ota.activity_type =
               $4
          )

          AND (
            $5::text IS NULL

            OR (
              h.nomenclature =
                $6

              AND h.code LIKE
                  $5 || '%'
            )
          )

          AND (
            $7::uuid IS NULL
            OR ota.product_id =
               $7::uuid
          )

          AND ota.status =
              $8

          AND (
            $9::numeric IS NULL
            OR ota.confidence >=
               $9::numeric
          )
      `;


      const countResult =
        await database.query(
          `
          SELECT
            COUNT(
              DISTINCT ota.organization_id
            )::int AS total

          ${activityFilter}
          `,
          filterValues
        );


      const total =
        countResult.rows[0]?.total
        ?? 0;


      if (total === 0) {

        return {

          ok: true,

          filters: {
            q:
              q ?? null,

            country:
              country ?? null,

            marketCountry:
              marketCountry ?? null,

            activityType:
              activityType ?? null,

            hsCode:
              hsCode ?? null,

            hsNomenclature,

            productId:
              productId ?? null,

            status,

            minimumConfidence:
              minimumConfidence ?? null
          },

          organizations: [],

          pagination: {
            total: 0,
            limit,
            offset
          }

        };

      }


      const pageResult =
        await database.query(
          `
          SELECT
            ota.organization_id::text
              AS "organizationId",

            COUNT(*)::int
              AS "matchedActivityCount",

            MAX(
              ota.updated_at
            ) AS "lastActivityAt",

            MIN(
              o.legal_name
            ) AS "legalName"

          ${activityFilter}

          GROUP BY
            ota.organization_id

          ORDER BY
            MAX(
              ota.updated_at
            ) DESC,

            MIN(
              o.legal_name
            ),

            ota.organization_id

          LIMIT $10
          OFFSET $11
          `,
          [
            ...filterValues,
            limit,
            offset
          ]
        );


      const organizationIds =
        pageResult.rows.map(
          row =>
            row.organizationId
        );


      if (organizationIds.length === 0) {

        return {

          ok: true,

          filters: {
            q:
              q ?? null,

            country:
              country ?? null,

            marketCountry:
              marketCountry ?? null,

            activityType:
              activityType ?? null,

            hsCode:
              hsCode ?? null,

            hsNomenclature,

            productId:
              productId ?? null,

            status,

            minimumConfidence:
              minimumConfidence ?? null
          },

          organizations: [],

          pagination: {
            total,
            limit,
            offset
          }

        };

      }


      const [
        organizationResult,
        activityResult
      ] =
        await Promise.all([


          database.query(
            `
            SELECT
              o.id::text AS id,

              o.legal_name
                AS "legalName",

              o.trading_name
                AS "tradingName",

              o.registration_number
                AS "registrationNumber",

              o.lei,

              o.tax_identifier
                AS "taxIdentifier",

              o.website,

              o.status,

              o.address,

              o.identifiers,

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

              COALESCE(
                (
                  SELECT jsonb_agg(
                    r.role_code
                    ORDER BY r.role_code
                  )
                  FROM organization_roles r
                  WHERE
                    r.organization_id =
                      o.id
                ),
                '[]'::jsonb
              ) AS roles,

              o.metadata,

              o.created_at
                AS "createdAt",

              o.updated_at
                AS "updatedAt"

            FROM organizations o

            LEFT JOIN countries c
              ON c.id =
                 o.country_id

            WHERE
              o.id =
              ANY(
                $1::uuid[]
              )
            `,
            [
              organizationIds
            ]
          ),


          database.query(
            `
            SELECT
              ota.id::text AS id,

              ota.organization_id::text
                AS "organizationId",

              ota.activity_type
                AS "activityType",

              ota.status,

              ota.confidence::double precision
                AS confidence,

              TO_CHAR(
                ota.valid_from,
                'YYYY-MM-DD'
              ) AS "validFrom",

              TO_CHAR(
                ota.valid_to,
                'YYYY-MM-DD'
              ) AS "validTo",

              ota.source_type
                AS "sourceType",

              ota.metadata,

              CASE
                WHEN p.id IS NULL
                THEN NULL
                ELSE jsonb_build_object(
                  'id',
                  p.id::text,
                  'name',
                  p.name,
                  'brand',
                  p.brand,
                  'sku',
                  p.sku
                )
              END AS product,

              CASE
                WHEN h.id IS NULL
                THEN NULL
                ELSE jsonb_build_object(
                  'id',
                  h.id::text,
                  'nomenclature',
                  h.nomenclature,
                  'code',
                  h.code,
                  'level',
                  h.level,
                  'description',
                  h.description
                )
              END AS "hsCode",

              CASE
                WHEN mc.id IS NULL
                THEN NULL
                ELSE jsonb_build_object(
                  'id',
                  mc.id::text,
                  'iso2',
                  mc.iso2,
                  'iso3',
                  mc.iso3,
                  'name',
                  mc.name
                )
              END AS "marketCountry",

              CASE
                WHEN csr.id IS NULL
                THEN NULL
                ELSE jsonb_build_object(
                  'sourceRecordId',
                  csr.id::text,
                  'externalId',
                  csr.external_id,
                  'recordType',
                  csr.record_type,
                  'fetchedAt',
                  csr.fetched_at,
                  'source',
                  CASE
                    WHEN cds.id IS NULL
                    THEN NULL
                    ELSE jsonb_build_object(
                      'code',
                      cds.code,
                      'name',
                      cds.name,
                      'provider',
                      cds.provider,
                      'isOfficial',
                      cds.is_official
                    )
                  END
                )
              END AS "canonicalSource",

              (
                SELECT
                  COUNT(*)::int

                FROM entity_source_links esl

                WHERE
                  esl.entity_type =
                    'organization_trade_activity'

                  AND esl.entity_id =
                    ota.id
              ) AS "evidenceCount",

              (
                SELECT
                  COUNT(
                    DISTINCT evidence_record.data_source_id
                  )::int

                FROM entity_source_links evidence_link

                JOIN source_records evidence_record
                  ON evidence_record.id =
                     evidence_link.source_record_id

                WHERE
                  evidence_link.entity_type =
                    'organization_trade_activity'

                  AND evidence_link.entity_id =
                    ota.id
              ) AS "sourceCoverageCount"

            FROM organization_trade_activities ota

            LEFT JOIN products p
              ON p.id =
                 ota.product_id

            LEFT JOIN hs_codes h
              ON h.id =
                 ota.hs_code_id

            LEFT JOIN countries mc
              ON mc.id =
                 ota.market_country_id

            LEFT JOIN source_records csr
              ON csr.id =
                 ota.canonical_source_record_id

            LEFT JOIN data_sources cds
              ON cds.id =
                 csr.data_source_id

            WHERE
              ota.organization_id =
              ANY(
                $1::uuid[]
              )

              AND (
                $2::text IS NULL
                OR mc.iso2 =
                   $2
              )

              AND (
                $3::text IS NULL
                OR ota.activity_type =
                   $3
              )

              AND (
                $4::text IS NULL

                OR (
                  h.nomenclature =
                    $5

                  AND h.code LIKE
                      $4 || '%'
                )
              )

              AND (
                $6::uuid IS NULL
                OR ota.product_id =
                   $6::uuid
              )

              AND ota.status =
                  $7

              AND (
                $8::numeric IS NULL
                OR ota.confidence >=
                   $8::numeric
              )

            ORDER BY
              ota.organization_id,
              ota.confidence DESC NULLS LAST,
              ota.updated_at DESC,
              ota.id
            `,
            [
              organizationIds,
              marketCountry ?? null,
              activityType ?? null,
              hsCode ?? null,
              hsNomenclature,
              productId ?? null,
              status,
              minimumConfidence ?? null
            ]
          )

        ]);


      const organizationsById =
        new Map<
          string,
          Record<string, unknown>
        >();


      for (
        const organization
        of organizationResult.rows
      ) {

        organizationsById.set(
          organization.id,
          organization
        );

      }


      const activitiesByOrganization =
        new Map<
          string,
          unknown[]
        >();


      for (
        const activity
        of activityResult.rows
      ) {

        const existing =
          activitiesByOrganization.get(
            activity.organizationId
          )
          ?? [];


        const {
          organizationId: _organizationId,
          ...activityPayload
        } = activity;


        existing.push(
          activityPayload
        );


        activitiesByOrganization.set(
          activity.organizationId,
          existing
        );

      }


      const organizations =
        pageResult.rows.map(
          pageRow => {

            const organization =
              organizationsById.get(
                pageRow.organizationId
              );


            return {

              ...organization,

              matchedActivityCount:
                pageRow.matchedActivityCount,

              matchedActivities:
                activitiesByOrganization.get(
                  pageRow.organizationId
                )
                ?? [],

              lastActivityAt:
                pageRow.lastActivityAt

            };

          }
        );


      return {

        ok: true,

        filters: {
          q:
            q ?? null,

          country:
            country ?? null,

          marketCountry:
            marketCountry ?? null,

          activityType:
            activityType ?? null,

          hsCode:
            hsCode ?? null,

          hsNomenclature,

          productId:
            productId ?? null,

          status,

          minimumConfidence:
            minimumConfidence ?? null
        },

        organizations,

        pagination: {
          total,
          limit,
          offset
        }

      };

    }
  );

}
