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

const codeSchema =
  z.string()
    .trim()
    .min(1)
    .max(100)
    .transform(
      value =>
        value
          .toLowerCase()
          .replace(/[\s-]+/g, "_")
    );

const subjectParamsSchema =
  z.object({
    id:
      uuidSchema
  });

const documentParamsSchema =
  z.object({
    id:
      uuidSchema
  });

const frameworkListSchema =
  z.object({
    q: z.string().trim().min(1).max(300).optional(),
    country: z.string().trim().length(2).transform(v => v.toUpperCase()).optional(),
    limit: z.coerce.number().int().min(1).max(200).default(100),
    offset: z.coerce.number().int().min(0).default(0)
  });

const documentListSchema =
  z.object({
    typeCode:
      codeSchema.optional(),
    status: z.string().trim().min(1).max(50).optional()
  });

const createDocumentSchema =
  z.object({
    typeCode:
      codeSchema,
    issuerOrganizationId:
      uuidSchema.nullable().optional(),
    title: z.string().trim().min(1).max(500),
    documentNumber: z.string().trim().min(1).max(300).nullable().optional(),
    issueDate: z.string().date().nullable().optional(),
    expiryDate: z.string().date().nullable().optional(),
    status: z.enum([
      "draft",
      "active",
      "superseded",
      "expired",
      "revoked"
    ]).default("active"),
    verificationStatus: z.enum([
      "unverified",
      "source_backed",
      "verified",
      "rejected"
    ]).default("unverified"),
    fileName: z.string().trim().min(1).max(500).nullable().optional(),
    mimeType: z.string().trim().min(1).max(200).nullable().optional(),
    storageUri: z.string().trim().min(1).max(3000).nullable().optional(),
    contentSha256: z.string()
      .trim()
      .regex(/^[0-9a-fA-F]{64}$/)
      .transform(v => v.toLowerCase())
      .nullable()
      .optional(),
    sourceType: z.string().trim().min(1).max(100).default("manual"),
    sourceRecordId:
      uuidSchema.nullable().optional(),
    confidence: z.number().min(0).max(1).nullable().optional(),
    metadata: z.record(z.string(), z.unknown()).default({})
  })
  .superRefine(
    (
      value,
      ctx
    ) => {

      if (
        value.issueDate
        && value.expiryDate
        && value.expiryDate < value.issueDate
      ) {

        ctx.addIssue({
          code: "custom",
          path: ["expiryDate"],
          message: "expiryDate cannot be earlier than issueDate."
        });

      }

    }
  );

const createFrameworkSchema =
  z.object({
    code:
      codeSchema,
    name: z.string().trim().min(1).max(500),
    authority: z.string().trim().min(1).max(500).nullable().optional(),
    jurisdictionCountry: z.string()
      .trim()
      .length(2)
      .transform(v => v.toUpperCase())
      .nullable()
      .optional(),
    website: z.string().trim().url().max(3000).nullable().optional(),
    metadata: z.record(z.string(), z.unknown()).default({})
  });

const createComplianceSchema =
  z.object({
    frameworkCode:
      codeSchema,
    requirementCode: z.string().trim().min(1).max(300).nullable().optional(),
    registrationNumber: z.string().trim().min(1).max(300).nullable().optional(),
    complianceStatus: z.enum([
      "unknown",
      "claimed",
      "compliant",
      "non_compliant",
      "not_applicable",
      "expired"
    ]).default("claimed"),
    evidenceDocumentId:
      uuidSchema.nullable().optional(),
    validFrom: z.string().date().nullable().optional(),
    validTo: z.string().date().nullable().optional(),
    sourceType: z.string().trim().min(1).max(100).default("manual"),
    sourceRecordId:
      uuidSchema.nullable().optional(),
    confidence: z.number().min(0).max(1).nullable().optional(),
    metadata: z.record(z.string(), z.unknown()).default({})
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
          code: "custom",
          path: ["validTo"],
          message: "validTo cannot be earlier than validFrom."
        });

      }

    }
  );


function validationError(
  issues: z.core.$ZodIssue[]
) {

  return {
    ok: false,
    error: "invalid_request",
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


async function subjectExists(
  subject:
    "product"
    | "manufacturer_product",
  id: string
) {

  const query =
    subject === "product"
      ? `
          SELECT EXISTS (
            SELECT 1
            FROM products
            WHERE id = $1::uuid
              AND is_active = TRUE
          ) AS exists
        `
      : `
          SELECT EXISTS (
            SELECT 1
            FROM manufacturer_products
            WHERE id = $1::uuid
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


async function resolveDocumentType(
  code: string
) {

  const result =
    await database.query(
      `
      SELECT id::text, code, name, category
      FROM product_document_types
      WHERE code = $1
        AND is_active = TRUE
      `,
      [
        code
      ]
    );

  return result.rows[0] ?? null;

}


async function resolveFramework(
  code: string
) {

  const result =
    await database.query(
      `
      SELECT
        cf.id::text,
        cf.code,
        cf.name,
        cf.authority,
        c.iso2 AS "jurisdictionCountryIso2",
        cf.website,
        cf.status,
        cf.metadata
      FROM compliance_frameworks cf
      LEFT JOIN countries c
        ON c.id = cf.jurisdiction_country_id
      WHERE cf.code = $1
      `,
      [
        code
      ]
    );

  return result.rows[0] ?? null;

}


async function loadDocument(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        pd.id::text,
        pd.product_id::text AS "productId",
        pd.manufacturer_product_id::text AS "manufacturerProductId",
        dt.code AS "typeCode",
        dt.name AS "typeName",
        dt.category,
        pd.issuer_organization_id::text AS "issuerOrganizationId",
        issuer.legal_name AS "issuerLegalName",
        pd.title,
        pd.document_number AS "documentNumber",
        TO_CHAR(pd.issue_date, 'YYYY-MM-DD') AS "issueDate",
        TO_CHAR(pd.expiry_date, 'YYYY-MM-DD') AS "expiryDate",
        pd.status,
        pd.verification_status AS "verificationStatus",
        pd.file_name AS "fileName",
        pd.mime_type AS "mimeType",
        pd.storage_uri AS "storageUri",
        pd.content_sha256 AS "contentSha256",
        pd.source_type AS "sourceType",
        pd.canonical_source_record_id::text AS "canonicalSourceRecordId",
        pd.confidence::double precision AS confidence,
        pd.metadata,
        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type = 'product_document'
            AND esl.entity_id = pd.id
        ) AS "evidenceCount",
        pd.created_at AS "createdAt",
        pd.updated_at AS "updatedAt"
      FROM product_documents pd
      JOIN product_document_types dt
        ON dt.id = pd.document_type_id
      LEFT JOIN organizations issuer
        ON issuer.id = pd.issuer_organization_id
      WHERE pd.id = $1::uuid
      `,
      [
        id
      ]
    );

  return result.rows[0] ?? null;

}


async function listDocuments(
  subjectColumn:
    "product_id"
    | "manufacturer_product_id",
  subjectId: string,
  typeCode: string | undefined,
  status: string | undefined
) {

  const result =
    await database.query(
      `
      SELECT pd.id::text
      FROM product_documents pd
      JOIN product_document_types dt
        ON dt.id = pd.document_type_id
      WHERE
        pd.${subjectColumn} = $1::uuid
        AND (
          $2::text IS NULL
          OR dt.code = $2
        )
        AND (
          $3::text IS NULL
          OR pd.status = $3
        )
      ORDER BY
        pd.issue_date DESC NULLS LAST,
        pd.updated_at DESC
      `,
      [
        subjectId,
        typeCode ?? null,
        status ?? null
      ]
    );

  const documents:
    Record<string, unknown>[] =
      [];

  for (
    const row
    of result.rows
  ) {

    const document =
      await loadDocument(
        row.id
      );

    if (document) {
      documents.push(document);
    }

  }

  return documents;

}


async function createDocument(
  subject:
    "product"
    | "manufacturer_product",
  subjectId: string,
  body: z.infer<typeof createDocumentSchema>
) {

  const type =
    await resolveDocumentType(
      body.typeCode
    );

  if (!type) {

    return {
      statusCode: 404,
      body: {
        ok: false,
        error: "document_type_not_found"
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
        INSERT INTO product_documents (
            document_type_id,
            product_id,
            manufacturer_product_id,
            issuer_organization_id,
            title,
            document_number,
            issue_date,
            expiry_date,
            status,
            verification_status,
            file_name,
            mime_type,
            storage_uri,
            content_sha256,
            source_type,
            canonical_source_record_id,
            confidence,
            metadata
        )
        VALUES (
            $1::uuid,
            $2::uuid,
            $3::uuid,
            $4::uuid,
            $5,
            $6,
            $7::date,
            $8::date,
            $9,
            $10,
            $11,
            $12,
            $13,
            $14,
            $15,
            $16::uuid,
            $17,
            $18::jsonb
        )
        RETURNING id::text
        `,
        [
          type.id,
          productId,
          manufacturerProductId,
          body.issuerOrganizationId ?? null,
          body.title,
          body.documentNumber ?? null,
          body.issueDate ?? null,
          body.expiryDate ?? null,
          body.status,
          body.verificationStatus,
          body.fileName ?? null,
          body.mimeType ?? null,
          body.storageUri ?? null,
          body.contentSha256 ?? null,
          body.sourceType,
          body.sourceRecordId ?? null,
          body.confidence ?? null,
          JSON.stringify(body.metadata)
        ]
      );


    const id =
      result.rows[0].id;


    if (
      body.sourceRecordId
    ) {

      await database.query(
        `
        INSERT INTO entity_source_links (
            source_record_id,
            entity_type,
            entity_id,
            relationship_type,
            confidence,
            metadata
        )
        VALUES (
            $1::uuid,
            'product_document',
            $2::uuid,
            'documentary_evidence',
            $3,
            '{"createdBy":"product_documents_api"}'::jsonb
        )
        ON CONFLICT DO NOTHING
        `,
        [
          body.sourceRecordId,
          id,
          body.confidence ?? null
        ]
      );

    }


    return {
      statusCode: 201,
      body: {
        ok: true,
        document:
          await loadDocument(id)
      }
    };

  }
  catch (error) {

    const code =
      (error as { code?: string }).code;

    if (code === "23503") {

      return {
        statusCode: 404,
        body: {
          ok: false,
          error: "document_reference_not_found"
        }
      };

    }

    throw error;

  }

}


async function listCompliance(
  subjectColumn:
    "product_id"
    | "manufacturer_product_id",
  subjectId: string
) {

  const result =
    await database.query(
      `
      SELECT
        pcr.id::text,
        cf.code AS "frameworkCode",
        cf.name AS "frameworkName",
        cf.authority,
        country.iso2 AS "jurisdictionCountryIso2",
        pcr.requirement_code AS "requirementCode",
        pcr.registration_number AS "registrationNumber",
        pcr.compliance_status AS "complianceStatus",
        pcr.evidence_document_id::text AS "evidenceDocumentId",
        TO_CHAR(pcr.valid_from, 'YYYY-MM-DD') AS "validFrom",
        TO_CHAR(pcr.valid_to, 'YYYY-MM-DD') AS "validTo",
        pcr.source_type AS "sourceType",
        pcr.canonical_source_record_id::text AS "canonicalSourceRecordId",
        pcr.confidence::double precision AS confidence,
        pcr.metadata,
        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type = 'product_compliance_record'
            AND esl.entity_id = pcr.id
        ) AS "evidenceCount",
        pcr.created_at AS "createdAt",
        pcr.updated_at AS "updatedAt"
      FROM product_compliance_records pcr
      JOIN compliance_frameworks cf
        ON cf.id = pcr.framework_id
      LEFT JOIN countries country
        ON country.id = cf.jurisdiction_country_id
      WHERE pcr.${subjectColumn} = $1::uuid
      ORDER BY
        cf.name,
        pcr.requirement_code NULLS FIRST,
        pcr.updated_at DESC
      `,
      [
        subjectId
      ]
    );

  return result.rows;

}


async function createCompliance(
  subject:
    "product"
    | "manufacturer_product",
  subjectId: string,
  body: z.infer<typeof createComplianceSchema>
) {

  const framework =
    await resolveFramework(
      body.frameworkCode
    );

  if (!framework) {

    return {
      statusCode: 404,
      body: {
        ok: false,
        error: "compliance_framework_not_found"
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
        INSERT INTO product_compliance_records (
            framework_id,
            product_id,
            manufacturer_product_id,
            requirement_code,
            registration_number,
            compliance_status,
            evidence_document_id,
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
            $7::uuid,
            $8::date,
            $9::date,
            $10,
            $11::uuid,
            $12,
            $13::jsonb
        )
        RETURNING id::text
        `,
        [
          framework.id,
          productId,
          manufacturerProductId,
          body.requirementCode ?? null,
          body.registrationNumber ?? null,
          body.complianceStatus,
          body.evidenceDocumentId ?? null,
          body.validFrom ?? null,
          body.validTo ?? null,
          body.sourceType,
          body.sourceRecordId ?? null,
          body.confidence ?? null,
          JSON.stringify(body.metadata)
        ]
      );


    const id =
      result.rows[0].id;


    if (body.sourceRecordId) {

      await database.query(
        `
        INSERT INTO entity_source_links (
            source_record_id,
            entity_type,
            entity_id,
            relationship_type,
            confidence,
            metadata
        )
        VALUES (
            $1::uuid,
            'product_compliance_record',
            $2::uuid,
            'compliance_evidence',
            $3,
            '{"createdBy":"product_compliance_api"}'::jsonb
        )
        ON CONFLICT DO NOTHING
        `,
        [
          body.sourceRecordId,
          id,
          body.confidence ?? null
        ]
      );

    }


    return {
      statusCode: 201,
      body: {
        ok: true,
        complianceRecordId:
          id
      }
    };

  }
  catch (error) {

    const code =
      (error as { code?: string }).code;

    if (code === "23505") {

      return {
        statusCode: 409,
        body: {
          ok: false,
          error: "active_compliance_record_conflict"
        }
      };

    }

    if (
      code === "23503"
      || code === "P0001"
    ) {

      return {
        statusCode: 409,
        body: {
          ok: false,
          error: "compliance_evidence_invalid"
        }
      };

    }

    throw error;

  }

}


export async function documentComplianceRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/reference/document-types",
    async () => {

      const result =
        await database.query(
          `
          SELECT
            id::text,
            code,
            name,
            category,
            is_active AS "isActive",
            metadata
          FROM product_document_types
          ORDER BY category, name
          `
        );

      return {
        ok: true,
        documentTypes:
          result.rows
      };

    }
  );


  app.get(
    "/api/compliance/frameworks",
    async (
      request,
      reply
    ) => {

      const parsed =
        frameworkListSchema.safeParse(
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
            cf.id::text,
            cf.code,
            cf.name,
            cf.authority,
            country.iso2 AS "jurisdictionCountryIso2",
            country.name AS "jurisdictionCountryName",
            cf.website,
            cf.status,
            cf.metadata,
            COUNT(*) OVER()::int AS "totalCount"
          FROM compliance_frameworks cf
          LEFT JOIN countries country
            ON country.id = cf.jurisdiction_country_id
          WHERE
            (
              $1::text IS NULL
              OR cf.code ILIKE '%' || $1 || '%'
              OR cf.name ILIKE '%' || $1 || '%'
              OR cf.authority ILIKE '%' || $1 || '%'
            )
            AND (
              $2::text IS NULL
              OR country.iso2 = $2
            )
          ORDER BY cf.name
          LIMIT $3
          OFFSET $4
          `,
          [
            parsed.data.q ?? null,
            parsed.data.country ?? null,
            parsed.data.limit,
            parsed.data.offset
          ]
        );

      const total =
        result.rows[0]?.totalCount ?? 0;

      return {
        ok: true,
        frameworks:
          result.rows.map(
            row => {
              const {
                totalCount: _totalCount,
                ...framework
              } = row;
              return framework;
            }
          ),
        pagination: {
          total,
          limit: parsed.data.limit,
          offset: parsed.data.offset
        }
      };

    }
  );


  app.post(
    "/api/compliance/frameworks",
    async (
      request,
      reply
    ) => {

      const body =
        createFrameworkSchema.safeParse(
          request.body
        );

      if (!body.success) {
        reply.code(400);
        return validationError(
          body.error.issues
        );
      }


      let countryId:
        string | null =
          null;


      if (
        body.data.jurisdictionCountry
      ) {

        const country =
          await database.query(
            `
            SELECT id::text
            FROM countries
            WHERE
              iso2 = $1
              AND is_active = TRUE
            `,
            [
              body.data.jurisdictionCountry
            ]
          );

        if (!country.rows[0]) {
          reply.code(404);
          return {
            ok: false,
            error: "country_not_found"
          };
        }

        countryId =
          country.rows[0].id;

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO compliance_frameworks (
                code,
                name,
                authority,
                jurisdiction_country_id,
                website,
                metadata
            )
            VALUES (
                $1,
                $2,
                $3,
                $4::uuid,
                $5,
                $6::jsonb
            )
            RETURNING id::text
            `,
            [
              body.data.code,
              body.data.name,
              body.data.authority ?? null,
              countryId,
              body.data.website ?? null,
              JSON.stringify(body.data.metadata)
            ]
          );

        reply.code(201);

        return {
          ok: true,
          id:
            result.rows[0].id,
          framework:
            await resolveFramework(
              body.data.code
            )
        };

      }
      catch (error) {

        if (
          (error as { code?: string }).code
          === "23505"
        ) {
          reply.code(409);
          return {
            ok: false,
            error: "compliance_framework_conflict"
          };
        }

        throw error;

      }

    }
  );


  for (
    const definition
    of [
      {
        prefix: "/api/products",
        subject: "product" as const,
        subjectColumn: "product_id" as const,
        notFound: "product_not_found"
      },
      {
        prefix: "/api/manufacturer-products",
        subject: "manufacturer_product" as const,
        subjectColumn: "manufacturer_product_id" as const,
        notFound: "manufacturer_product_not_found"
      }
    ]
  ) {

    app.get(
      `${definition.prefix}/:id/documents`,
      async (
        request,
        reply
      ) => {

        const params =
          subjectParamsSchema.safeParse(
            request.params
          );

        const query =
          documentListSchema.safeParse(
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
          !await subjectExists(
            definition.subject,
            params.data.id
          )
        ) {
          reply.code(404);
          return {
            ok: false,
            error:
              definition.notFound
          };
        }

        return {
          ok: true,
          documents:
            await listDocuments(
              definition.subjectColumn,
              params.data.id,
              query.data.typeCode,
              query.data.status
            )
        };

      }
    );


    app.post(
      `${definition.prefix}/:id/documents`,
      async (
        request,
        reply
      ) => {

        const params =
          subjectParamsSchema.safeParse(
            request.params
          );

        const body =
          createDocumentSchema.safeParse(
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
            definition.subject,
            params.data.id
          )
        ) {
          reply.code(404);
          return {
            ok: false,
            error:
              definition.notFound
          };
        }

        const result =
          await createDocument(
            definition.subject,
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
      `${definition.prefix}/:id/compliance`,
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
            definition.subject,
            params.data.id
          )
        ) {
          reply.code(404);
          return {
            ok: false,
            error:
              definition.notFound
          };
        }

        return {
          ok: true,
          compliance:
            await listCompliance(
              definition.subjectColumn,
              params.data.id
            )
        };

      }
    );


    app.post(
      `${definition.prefix}/:id/compliance`,
      async (
        request,
        reply
      ) => {

        const params =
          subjectParamsSchema.safeParse(
            request.params
          );

        const body =
          createComplianceSchema.safeParse(
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
            definition.subject,
            params.data.id
          )
        ) {
          reply.code(404);
          return {
            ok: false,
            error:
              definition.notFound
          };
        }

        const result =
          await createCompliance(
            definition.subject,
            params.data.id,
            body.data
          );

        reply.code(
          result.statusCode
        );

        return result.body;

      }
    );

  }


  app.get(
    "/api/documents/:id",
    async (
      request,
      reply
    ) => {

      const params =
        documentParamsSchema.safeParse(
          request.params
        );

      if (!params.success) {
        reply.code(400);
        return validationError(
          params.error.issues
        );
      }

      const document =
        await loadDocument(
          params.data.id
        );

      if (!document) {
        reply.code(404);
        return {
          ok: false,
          error: "document_not_found"
        };
      }

      return {
        ok: true,
        document
      };

    }
  );

}
