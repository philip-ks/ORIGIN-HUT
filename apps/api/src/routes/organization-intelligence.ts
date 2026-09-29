import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const organizationParamsSchema =
  z.object({

    id: z
      .string()
      .uuid()

  });


const countryIso2Schema =
  z.string()
    .trim()
    .length(2)
    .transform(
      value =>
        value.toUpperCase()
    );


const activityTypeSchema =
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


const statusSchema =
  z.string()
    .trim()
    .min(1)
    .max(50)
    .transform(
      value =>
        value.toLowerCase()
    );


const aliasTypeSchema =
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


const organizationTradeActivitiesQuerySchema =
  z.object({

    activityType:
      activityTypeSchema
        .optional(),

    marketCountry:
      countryIso2Schema
        .optional(),

    productId: z
      .string()
      .uuid()
      .optional(),

    hsCode: z
      .string()
      .trim()
      .regex(
        /^\d{2,6}$/,
        "HS code must contain 2 to 6 digits."
      )
      .optional(),

    hsNomenclature: z
      .string()
      .trim()
      .min(1)
      .max(20)
      .transform(
        value =>
          value.toUpperCase()
      )
      .default("HS2022"),

    status:
      statusSchema
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
      .default(50),

    offset: z.coerce
      .number()
      .int()
      .min(0)
      .default(0)

  });


const organizationAliasesQuerySchema =
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

    aliasType:
      aliasTypeSchema
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


const organizationEvidenceQuerySchema =
  z.object({

    entityType: z
      .enum([
        "organization",
        "organization_alias",
        "organization_trade_activity"
      ])
      .optional(),

    sourceCode: z
      .string()
      .trim()
      .min(1)
      .max(200)
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


async function loadOrganizationBrief(
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

        o.website,

        o.status,

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
        END AS country

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


export async function organizationIntelligenceRoutes(
  app: FastifyInstance
) {


  // ==========================================================
  // ORGANIZATION INTELLIGENCE SUMMARY
  // ==========================================================

  app.get(
    "/api/organizations/:id/intelligence",
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


      const organization =
        await loadOrganizationBrief(
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
          WITH related_entities AS (

            SELECT
              'organization'::text
                AS entity_type,
              o.id
                AS entity_id

            FROM organizations o

            WHERE o.id =
                  $1::uuid


            UNION ALL


            SELECT
              'organization_alias'::text,
              oa.id

            FROM organization_aliases oa

            WHERE oa.organization_id =
                  $1::uuid


            UNION ALL


            SELECT
              'organization_trade_activity'::text,
              ota.id

            FROM organization_trade_activities ota

            WHERE ota.organization_id =
                  $1::uuid

          ),

          related_evidence AS (

            SELECT
              esl.id,
              esl.source_record_id

            FROM entity_source_links esl

            JOIN related_entities re
              ON re.entity_type =
                 esl.entity_type

             AND re.entity_id =
                 esl.entity_id

          )

          SELECT

            (
              SELECT COUNT(*)::int
              FROM organization_roles r
              WHERE r.organization_id =
                    $1::uuid
            ) AS "roleCount",

            (
              SELECT COUNT(*)::int
              FROM products p
              WHERE p.manufacturer_id =
                    $1::uuid
            ) AS "productCount",

            (
              SELECT COUNT(*)::int
              FROM organization_trade_activities ota
              WHERE ota.organization_id =
                    $1::uuid
            ) AS "tradeActivityCount",

            (
              SELECT COUNT(*)::int
              FROM organization_trade_activities ota
              WHERE
                ota.organization_id =
                  $1::uuid
                AND ota.status =
                    'active'
                AND ota.valid_to IS NULL
            ) AS "activeTradeActivityCount",

            (
              SELECT COUNT(*)::int
              FROM organization_aliases oa
              WHERE oa.organization_id =
                    $1::uuid
            ) AS "aliasCount",

            (
              SELECT COUNT(*)::int
              FROM organization_aliases oa
              WHERE
                oa.organization_id =
                  $1::uuid
                AND oa.is_active =
                    TRUE
            ) AS "activeAliasCount",

            (
              SELECT COUNT(*)::int
              FROM organization_relationships rel
              WHERE
                rel.source_organization_id =
                  $1::uuid
                OR rel.target_organization_id =
                   $1::uuid
            ) AS "relationshipCount",

            (
              SELECT COUNT(*)::int
              FROM related_evidence
            ) AS "evidenceCount",

            (
              SELECT COUNT(
                DISTINCT sr.data_source_id
              )::int
              FROM related_evidence evidence
              JOIN source_records sr
                ON sr.id =
                   evidence.source_record_id
            ) AS "sourceCoverageCount",

            (
              SELECT MAX(sr.fetched_at)
              FROM related_evidence evidence
              JOIN source_records sr
                ON sr.id =
                   evidence.source_record_id
            ) AS "lastEvidenceAt",

            COALESCE(
              (
                SELECT jsonb_agg(
                  activity_type
                  ORDER BY activity_type
                )
                FROM (
                  SELECT DISTINCT
                    ota.activity_type
                  FROM organization_trade_activities ota
                  WHERE
                    ota.organization_id =
                      $1::uuid
                    AND ota.status =
                        'active'
                ) activity_types
              ),
              '[]'::jsonb
            ) AS "activeActivityTypes"
          `,
          [
            params.data.id
          ]
        );


      return {

        ok: true,

        organization,

        intelligence:
          result.rows[0]

      };

    }
  );


  // ==========================================================
  // ORGANIZATION TRADE ACTIVITIES
  // ==========================================================

  app.get(
    "/api/organizations/:id/trade-activities",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const query =
        organizationTradeActivitiesQuerySchema.safeParse(
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
        await loadOrganizationBrief(
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
        activityType,
        marketCountry,
        productId,
        hsCode,
        hsNomenclature,
        status,
        minimumConfidence,
        limit,
        offset
      } = query.data;


      const result =
        await database.query(
          `
          SELECT
            ota.id::text AS id,

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
              SELECT COUNT(*)::int
              FROM entity_source_links esl
              WHERE
                esl.entity_type =
                  'organization_trade_activity'
                AND esl.entity_id =
                    ota.id
            ) AS "evidenceCount",

            (
              SELECT COUNT(
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
            ) AS "sourceCoverageCount",

            ota.created_at
              AS "createdAt",

            ota.updated_at
              AS "updatedAt",

            COUNT(*) OVER()::int
              AS "totalCount"

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
              $1::uuid

            AND (
              $2::text IS NULL
              OR ota.activity_type =
                 $2
            )

            AND (
              $3::text IS NULL
              OR mc.iso2 =
                 $3
            )

            AND (
              $4::uuid IS NULL
              OR ota.product_id =
                 $4::uuid
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

            AND ota.status =
                $7

            AND (
              $8::numeric IS NULL
              OR ota.confidence >=
                 $8::numeric
            )

          ORDER BY
            ota.confidence DESC NULLS LAST,
            ota.updated_at DESC,
            ota.id

          LIMIT $9
          OFFSET $10
          `,
          [
            params.data.id,
            activityType ?? null,
            marketCountry ?? null,
            productId ?? null,
            hsCode ?? null,
            hsNomenclature,
            status,
            minimumConfidence ?? null,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const activities =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...activity
            } = row;

            return activity;

          }
        );


      return {

        ok: true,

        organization,

        filters: {
          activityType:
            activityType ?? null,

          marketCountry:
            marketCountry ?? null,

          productId:
            productId ?? null,

          hsCode:
            hsCode ?? null,

          hsNomenclature,

          status,

          minimumConfidence:
            minimumConfidence ?? null
        },

        activities,

        pagination: {
          total,
          limit,
          offset
        }

      };

    }
  );


  // ==========================================================
  // ORGANIZATION ALIASES
  // ==========================================================

  app.get(
    "/api/organizations/:id/aliases",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const query =
        organizationAliasesQuerySchema.safeParse(
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
        await loadOrganizationBrief(
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
            oa.id::text AS id,

            oa.alias,

            oa.normalized_alias
              AS "normalizedAlias",

            oa.alias_type
              AS "aliasType",

            oa.language_code
              AS "languageCode",

            oa.is_active
              AS "isActive",

            oa.metadata,

            CASE
              WHEN sr.id IS NULL
              THEN NULL
              ELSE jsonb_build_object(
                'sourceRecordId',
                sr.id::text,
                'externalId',
                sr.external_id,
                'recordType',
                sr.record_type,
                'fetchedAt',
                sr.fetched_at,
                'source',
                CASE
                  WHEN ds.id IS NULL
                  THEN NULL
                  ELSE jsonb_build_object(
                    'code',
                    ds.code,
                    'name',
                    ds.name,
                    'provider',
                    ds.provider,
                    'isOfficial',
                    ds.is_official
                  )
                END
              )
            END AS "firstObservedSource",

            (
              SELECT COUNT(*)::int
              FROM entity_source_links esl
              WHERE
                esl.entity_type =
                  'organization_alias'
                AND esl.entity_id =
                    oa.id
            ) AS "evidenceCount",

            (
              SELECT COUNT(
                DISTINCT evidence_record.data_source_id
              )::int
              FROM entity_source_links evidence_link
              JOIN source_records evidence_record
                ON evidence_record.id =
                   evidence_link.source_record_id
              WHERE
                evidence_link.entity_type =
                  'organization_alias'
                AND evidence_link.entity_id =
                    oa.id
            ) AS "sourceCoverageCount",

            oa.created_at
              AS "createdAt",

            oa.updated_at
              AS "updatedAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM organization_aliases oa

          LEFT JOIN source_records sr
            ON sr.id =
               oa.source_record_id

          LEFT JOIN data_sources ds
            ON ds.id =
               sr.data_source_id

          WHERE
            oa.organization_id =
              $1::uuid

            AND (
              $2::boolean IS NULL
              OR oa.is_active =
                 $2::boolean
            )

            AND (
              $3::text IS NULL
              OR oa.alias_type =
                 $3
            )

          ORDER BY
            oa.is_active DESC,
            oa.alias_type,
            oa.alias,
            oa.id

          LIMIT $4
          OFFSET $5
          `,
          [
            params.data.id,
            query.data.active ?? null,
            query.data.aliasType ?? null,
            query.data.limit,
            query.data.offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const aliases =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...alias
            } = row;

            return alias;

          }
        );


      return {

        ok: true,

        organization,

        aliases,

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
  // ORGANIZATION EVIDENCE / SOURCES
  // ==========================================================

  app.get(
    "/api/organizations/:id/evidence",
    async (
      request,
      reply
    ) => {

      const params =
        organizationParamsSchema.safeParse(
          request.params
        );


      const query =
        organizationEvidenceQuerySchema.safeParse(
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
        await loadOrganizationBrief(
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
          WITH related_entities AS (

            SELECT
              'organization'::text
                AS entity_type,
              o.id
                AS entity_id

            FROM organizations o

            WHERE o.id =
                  $1::uuid


            UNION ALL


            SELECT
              'organization_alias'::text,
              oa.id

            FROM organization_aliases oa

            WHERE oa.organization_id =
                  $1::uuid


            UNION ALL


            SELECT
              'organization_trade_activity'::text,
              ota.id

            FROM organization_trade_activities ota

            WHERE ota.organization_id =
                  $1::uuid

          )

          SELECT
            esl.id::text AS id,

            esl.entity_type
              AS "entityType",

            esl.entity_id::text
              AS "entityId",

            esl.relationship_type
              AS "relationshipType",

            esl.confidence::double precision
              AS confidence,

            esl.metadata,

            jsonb_build_object(
              'id',
              sr.id::text,
              'externalId',
              sr.external_id,
              'recordType',
              sr.record_type,
              'sourceTimestamp',
              sr.source_timestamp,
              'fetchedAt',
              sr.fetched_at,
              'contentHash',
              sr.content_hash,
              'metadata',
              sr.metadata
            ) AS "sourceRecord",

            jsonb_build_object(
              'id',
              ds.id::text,
              'code',
              ds.code,
              'name',
              ds.name,
              'provider',
              ds.provider,
              'category',
              ds.category,
              'accessMethod',
              ds.access_method,
              'baseUrl',
              ds.base_url,
              'license',
              ds.license,
              'termsUrl',
              ds.terms_url,
              'attribution',
              ds.attribution,
              'isOfficial',
              ds.is_official
            ) AS source,

            esl.created_at
              AS "createdAt",

            COUNT(*) OVER()::int
              AS "totalCount"

          FROM entity_source_links esl

          JOIN related_entities re
            ON re.entity_type =
               esl.entity_type

           AND re.entity_id =
               esl.entity_id

          JOIN source_records sr
            ON sr.id =
               esl.source_record_id

          JOIN data_sources ds
            ON ds.id =
               sr.data_source_id

          WHERE
            (
              $2::text IS NULL
              OR esl.entity_type =
                 $2
            )

            AND (
              $3::text IS NULL
              OR ds.code =
                 $3
            )

          ORDER BY
            sr.fetched_at DESC,
            esl.created_at DESC,
            esl.id

          LIMIT $4
          OFFSET $5
          `,
          [
            params.data.id,
            query.data.entityType ?? null,
            query.data.sourceCode ?? null,
            query.data.limit,
            query.data.offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const evidence =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...item
            } = row;

            return item;

          }
        );


      return {

        ok: true,

        organization,

        filters: {
          entityType:
            query.data.entityType
            ?? null,

          sourceCode:
            query.data.sourceCode
            ?? null
        },

        evidence,

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
