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


const rfqParamsSchema =
  z.object({
    id:
      uuidSchema
  });


const listSchema =
  z.object({

    rfqLineId:
      uuidSchema
        .optional(),

    rfqSupplierId:
      uuidSchema
        .optional(),

    supplierId:
      uuidSchema
        .optional(),

    status: z
      .enum([
        "submitted",
        "withdrawn",
        "superseded"
      ])
      .optional(),

    limit: z.coerce
      .number()
      .int()
      .min(1)
      .max(100)
      .default(100),

    offset: z.coerce
      .number()
      .int()
      .min(0)
      .default(0)

  });


const createSchema =
  z.object({

    rfqLineId:
      uuidSchema,

    rfqSupplierId:
      uuidSchema,

    commercialOfferId:
      uuidSchema,

    status: z
      .enum([
        "submitted"
      ])
      .default("submitted"),

    respondedAt: z
      .string()
      .datetime({
        offset: true
      })
      .nullable()
      .optional(),

    notes: z
      .string()
      .trim()
      .min(1)
      .max(5000)
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

    metadata: z
      .record(
        z.string(),
        z.unknown()
      )
      .default({})

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


async function loadResponses(
  rfqId: string,
  options: {
    rfqLineId?: string;
    rfqSupplierId?: string;
    supplierId?: string;
    status?: string;
    limit: number;
    offset: number;
  }
) {

  const result =
    await database.query(
      `
      SELECT
        rr.id::text,

        rr.rfq_id::text
          AS "rfqId",

        rr.rfq_line_id::text
          AS "rfqLineId",

        rl.line_number
          AS "lineNumber",

        rl.product_id::text
          AS "productId",

        p.name
          AS "productName",

        rr.rfq_supplier_id::text
          AS "rfqSupplierId",

        rs.supplier_organization_id::text
          AS "supplierId",

        supplier.legal_name
          AS "supplierLegalName",

        rr.commercial_offer_id::text
          AS "commercialOfferId",

        co.offer_reference
          AS "commercialOfferReference",

        co.status
          AS "commercialOfferStatus",

        co.unit_price::double precision
          AS "unitPrice",

        currency.code
          AS "currencyCode",

        price_uom.code
          AS "priceUomCode",

        incoterm.edition
          AS "incotermEdition",

        incoterm.code
          AS "incotermCode",

        co.named_place_text
          AS "namedPlaceText",

        trade_location.unlocode
          AS "namedTradeLocationUnlocode",

        co.minimum_order_quantity::double precision
          AS "minimumOrderQuantity",

        moq_uom.code
          AS "minimumOrderUomCode",

        co.lead_time_days
          AS "leadTimeDays",

        co.payment_terms
          AS "paymentTerms",

        rr.status,

        rr.responded_at
          AS "respondedAt",

        rr.notes,

        rr.source_type
          AS "sourceType",

        rr.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        rr.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'rfq_response'
            AND esl.entity_id =
              rr.id
        ) AS "evidenceCount",

        rr.metadata,

        rr.created_at
          AS "createdAt",

        rr.updated_at
          AS "updatedAt",

        COUNT(*) OVER()::int
          AS "totalCount"

      FROM rfq_responses rr

      JOIN rfq_lines rl
        ON rl.id =
           rr.rfq_line_id

      JOIN products p
        ON p.id =
           rl.product_id

      JOIN rfq_suppliers rs
        ON rs.id =
           rr.rfq_supplier_id

      JOIN organizations supplier
        ON supplier.id =
           rs.supplier_organization_id

      JOIN commercial_offers co
        ON co.id =
           rr.commercial_offer_id

      JOIN currencies currency
        ON currency.id =
           co.currency_id

      JOIN units_of_measure price_uom
        ON price_uom.id =
           co.price_uom_id

      LEFT JOIN units_of_measure moq_uom
        ON moq_uom.id =
           co.minimum_order_uom_id

      JOIN incoterm_rules incoterm
        ON incoterm.id =
           co.incoterm_rule_id

      LEFT JOIN trade_locations trade_location
        ON trade_location.id =
           co.named_trade_location_id

      WHERE
        rr.rfq_id =
          $1::uuid

        AND (
          $2::uuid IS NULL
          OR rr.rfq_line_id =
             $2::uuid
        )

        AND (
          $3::uuid IS NULL
          OR rr.rfq_supplier_id =
             $3::uuid
        )

        AND (
          $4::uuid IS NULL
          OR rs.supplier_organization_id =
             $4::uuid
        )

        AND (
          $5::text IS NULL
          OR rr.status =
             $5
        )

      ORDER BY
        rl.line_number,
        rr.responded_at DESC,
        rr.id

      LIMIT $6
      OFFSET $7
      `,
      [
        rfqId,
        options.rfqLineId
          ?? null,
        options.rfqSupplierId
          ?? null,
        options.supplierId
          ?? null,
        options.status
          ?? null,
        options.limit,
        options.offset
      ]
    );


  const total =
    result.rows[0]?.totalCount
    ?? 0;


  return {

    responses:
      result.rows.map(
        row => {

          const {
            totalCount: _totalCount,
            ...response
          } = row;

          return response;

        }
      ),

    total

  };

}


export async function rfqResponseRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/rfqs/:id/responses",
    async (
      request,
      reply
    ) => {

      const params =
        rfqParamsSchema.safeParse(
          request.params
        );

      const query =
        listSchema.safeParse(
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


      const rfq =
        await database.query(
          `
          SELECT id::text
          FROM rfqs
          WHERE id =
                $1::uuid
          `,
          [
            params.data.id
          ]
        );


      if (!rfq.rows[0]) {

        reply.code(404);

        return {
          ok: false,
          error:
            "rfq_not_found"
        };

      }


      const loaded =
        await loadResponses(
          params.data.id,
          {
            rfqLineId:
              query.data.rfqLineId,
            rfqSupplierId:
              query.data.rfqSupplierId,
            supplierId:
              query.data.supplierId,
            status:
              query.data.status,
            limit:
              query.data.limit,
            offset:
              query.data.offset
          }
        );


      return {

        ok: true,

        responses:
          loaded.responses,

        pagination: {
          total:
            loaded.total,
          limit:
            query.data.limit,
          offset:
            query.data.offset
        }

      };

    }
  );


  app.post(
    "/api/rfqs/:id/responses",
    async (
      request,
      reply
    ) => {

      const params =
        rfqParamsSchema.safeParse(
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


      try {

        const result =
          await database.query(
            `
            INSERT INTO rfq_responses (
                rfq_id,
                rfq_line_id,
                rfq_supplier_id,
                commercial_offer_id,
                status,
                responded_at,
                notes,
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
                COALESCE(
                    $6::timestamptz,
                    NOW()
                ),
                $7,
                $8,
                $9::uuid,
                $10,
                $11::jsonb
            )
            RETURNING id::text
            `,
            [
              params.data.id,
              body.data.rfqLineId,
              body.data.rfqSupplierId,
              body.data.commercialOfferId,
              body.data.status,
              body.data.respondedAt
                ?? null,
              body.data.notes
                ?? null,
              body.data.sourceType,
              body.data.sourceRecordId
                ?? null,
              body.data.confidence
                ?? null,
              JSON.stringify(
                body.data.metadata
              )
            ]
          );


        const loaded =
          await loadResponses(
            params.data.id,
            {
              limit:
                100,
              offset:
                0
            }
          );


        const response =
          loaded.responses.find(
            item =>
              item.id
              === result.rows[0].id
          );


        reply.code(201);

        return {
          ok: true,
          response
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
              "rfq_response_conflict"
          };

        }


        if (
          code === "23503"
        ) {

          reply.code(404);

          return {
            ok: false,
            error:
              "rfq_response_reference_not_found"
          };

        }


        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "rfq_response_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );

}
