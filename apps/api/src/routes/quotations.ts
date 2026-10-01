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


const currencyCodeSchema =
  z.string()
    .trim()
    .length(3)
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


const incotermCodeSchema =
  z.string()
    .trim()
    .length(3)
    .transform(
      value =>
        value.toUpperCase()
    );


const unlocodeSchema =
  z.string()
    .trim()
    .length(5)
    .transform(
      value =>
        value.toUpperCase()
    );


const paramsSchema =
  z.object({
    id:
      uuidSchema
  });


const listSchema =
  z.object({

    issuerId:
      uuidSchema
        .optional(),

    customerId:
      uuidSchema
        .optional(),

    sourceRfqId:
      uuidSchema
        .optional(),

    status: z
      .enum([
        "draft",
        "issued",
        "accepted",
        "rejected",
        "expired",
        "cancelled"
      ])
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


const createSchema =
  z.object({

    quotationReference: z
      .string()
      .trim()
      .min(1)
      .max(200),

    issuerId:
      uuidSchema,

    customerId:
      uuidSchema,

    sourceRfqId:
      uuidSchema
        .nullable()
        .optional(),

    currencyCode:
      currencyCodeSchema,

    issueDate: z
      .string()
      .date()
      .nullable()
      .optional(),

    validUntil: z
      .string()
      .date()
      .nullable()
      .optional(),

    status: z
      .enum([
        "draft",
        "issued"
      ])
      .default("draft"),

    paymentTerms: z
      .string()
      .trim()
      .min(1)
      .max(2000)
      .nullable()
      .optional(),

    incotermEdition: z
      .number()
      .int()
      .positive()
      .default(2020),

    incotermCode:
      incotermCodeSchema
        .nullable()
        .optional(),

    namedPlaceText: z
      .string()
      .trim()
      .min(1)
      .max(500)
      .nullable()
      .optional(),

    namedTradeLocationUnlocode:
      unlocodeSchema
        .nullable()
        .optional(),

    namedOrganizationSiteId:
      uuidSchema
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

  })
  .superRefine(
    (
      value,
      ctx
    ) => {

      if (
        value.issuerId
        === value.customerId
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "customerId"
            ],
          message:
            "issuerId and customerId must differ."
        });

      }


      if (
        value.issueDate
        && value.validUntil
        && value.validUntil
           < value.issueDate
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "validUntil"
            ],
          message:
            "validUntil cannot be earlier than issueDate."
        });

      }

    }
  );


const createLineSchema =
  z.object({

    lineNumber: z
      .number()
      .int()
      .positive(),

    productId:
      uuidSchema,

    manufacturerProductId:
      uuidSchema
        .nullable()
        .optional(),

    packagingConfigurationId:
      uuidSchema
        .nullable()
        .optional(),

    sourceRfqLineId:
      uuidSchema
        .nullable()
        .optional(),

    sourceCommercialOfferId:
      uuidSchema
        .nullable()
        .optional(),

    sourceLandedCostScenarioId:
      uuidSchema
        .nullable()
        .optional(),

    quantity: z
      .number()
      .positive(),

    uomCode:
      uomCodeSchema,

    internalCostUnitPrice: z
      .number()
      .min(0)
      .nullable()
      .optional(),

    pricingMethod: z
      .enum([
        "manual",
        "markup_percent",
        "margin_percent"
      ])
      .default("manual"),

    pricingRate: z
      .number()
      .min(0)
      .nullable()
      .optional(),

    quotedUnitPrice: z
      .number()
      .positive()
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

  })
  .superRefine(
    (
      value,
      ctx
    ) => {

      if (
        value.sourceLandedCostScenarioId
        && !value.sourceCommercialOfferId
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "sourceCommercialOfferId"
            ],
          message:
            "sourceCommercialOfferId is required when sourceLandedCostScenarioId is supplied."
        });

      }


      if (
        value.pricingMethod
        === "manual"
        && value.quotedUnitPrice
           == null
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "quotedUnitPrice"
            ],
          message:
            "Manual pricing requires quotedUnitPrice."
        });

      }


      if (
        value.pricingMethod
        !== "manual"
        && value.pricingRate
           == null
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "pricingRate"
            ],
          message:
            "Derived pricing requires pricingRate."
        });

      }


      if (
        value.pricingMethod
        === "margin_percent"
        && value.pricingRate
           != null
        && value.pricingRate
           >= 100
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "pricingRate"
            ],
          message:
            "Margin percentage must be below 100."
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


async function resolveId(
  table: string,
  condition: string,
  value: unknown
): Promise<string | null> {

  const result =
    await database.query(
      `
      SELECT id::text
      FROM ${table}
      WHERE ${condition}
      LIMIT 1
      `,
      [
        value
      ]
    );


  return (
    result.rows[0]?.id
    ?? null
  );

}


async function loadQuotation(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        q.id::text,

        q.quotation_reference
          AS "quotationReference",

        q.issuer_organization_id::text
          AS "issuerId",

        issuer.legal_name
          AS "issuerLegalName",

        q.customer_organization_id::text
          AS "customerId",

        customer.legal_name
          AS "customerLegalName",

        q.source_rfq_id::text
          AS "sourceRfqId",

        rfq.rfq_reference
          AS "sourceRfqReference",

        currency.code
          AS "currencyCode",

        TO_CHAR(
          q.issue_date,
          'YYYY-MM-DD'
        ) AS "issueDate",

        TO_CHAR(
          q.valid_until,
          'YYYY-MM-DD'
        ) AS "validUntil",

        q.status,

        q.payment_terms
          AS "paymentTerms",

        incoterm.edition
          AS "incotermEdition",

        incoterm.code
          AS "incotermCode",

        incoterm.name
          AS "incotermName",

        q.named_place_text
          AS "namedPlaceText",

        trade_location.unlocode
          AS "namedTradeLocationUnlocode",

        trade_location.name
          AS "namedTradeLocationName",

        site.id::text
          AS "namedOrganizationSiteId",

        site.name
          AS "namedOrganizationSiteName",

        q.notes,

        q.source_type
          AS "sourceType",

        q.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        q.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'quotation'
            AND esl.entity_id =
              q.id
        ) AS "evidenceCount",

        q.metadata,

        q.created_at
          AS "createdAt",

        q.updated_at
          AS "updatedAt"

      FROM quotations q

      JOIN organizations issuer
        ON issuer.id =
           q.issuer_organization_id

      JOIN organizations customer
        ON customer.id =
           q.customer_organization_id

      LEFT JOIN rfqs rfq
        ON rfq.id =
           q.source_rfq_id

      JOIN currencies currency
        ON currency.id =
           q.currency_id

      LEFT JOIN incoterm_rules incoterm
        ON incoterm.id =
           q.incoterm_rule_id

      LEFT JOIN trade_locations trade_location
        ON trade_location.id =
           q.named_trade_location_id

      LEFT JOIN organization_sites site
        ON site.id =
           q.named_organization_site_id

      WHERE q.id =
            $1::uuid
      `,
      [
        id
      ]
    );


  if (!result.rows[0]) {
    return null;
  }


  const lines =
    await database.query(
      `
      SELECT
        ql.id::text,

        ql.line_number
          AS "lineNumber",

        ql.product_id::text
          AS "productId",

        product.name
          AS "productName",

        ql.manufacturer_product_id::text
          AS "manufacturerProductId",

        manufacturer_product.name
          AS "manufacturerProductName",

        ql.packaging_configuration_id::text
          AS "packagingConfigurationId",

        packaging.name
          AS "packagingName",

        ql.source_rfq_line_id::text
          AS "sourceRfqLineId",

        ql.source_commercial_offer_id::text
          AS "sourceCommercialOfferId",

        offer.offer_reference
          AS "sourceCommercialOfferReference",

        ql.source_landed_cost_scenario_id::text
          AS "sourceLandedCostScenarioId",

        ql.quantity::double precision
          AS quantity,

        uom.code
          AS "uomCode",

        ql.internal_cost_unit_price::double precision
          AS "internalCostUnitPrice",

        ql.pricing_method
          AS "pricingMethod",

        ql.pricing_rate::double precision
          AS "pricingRate",

        ql.quoted_unit_price::double precision
          AS "quotedUnitPrice",

        ql.quoted_line_total::double precision
          AS "quotedLineTotal",

        ql.notes,

        ql.source_type
          AS "sourceType",

        ql.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        ql.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'quotation_line'
            AND esl.entity_id =
              ql.id
        ) AS "evidenceCount",

        ql.metadata,

        ql.created_at
          AS "createdAt",

        ql.updated_at
          AS "updatedAt"

      FROM quotation_lines ql

      JOIN products product
        ON product.id =
           ql.product_id

      LEFT JOIN manufacturer_products manufacturer_product
        ON manufacturer_product.id =
           ql.manufacturer_product_id

      LEFT JOIN packaging_configurations packaging
        ON packaging.id =
           ql.packaging_configuration_id

      LEFT JOIN commercial_offers offer
        ON offer.id =
           ql.source_commercial_offer_id

      JOIN units_of_measure uom
        ON uom.id =
           ql.uom_id

      WHERE ql.quotation_id =
            $1::uuid

      ORDER BY
        ql.line_number,
        ql.id
      `,
      [
        id
      ]
    );


  const total =
    lines.rows.reduce(
      (
        sum,
        line
      ) =>
        sum
        + Number(
            line.quotedLineTotal
          ),
      0
    );


  return {
    ...result.rows[0],
    quotedTotal:
      total,
    lines:
      lines.rows
  };

}


export async function quotationRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/quotations",
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
            q.id::text,
            COUNT(*) OVER()::int
              AS "totalCount"

          FROM quotations q

          WHERE
            (
              $1::uuid IS NULL
              OR q.issuer_organization_id =
                 $1::uuid
            )

            AND (
              $2::uuid IS NULL
              OR q.customer_organization_id =
                 $2::uuid
            )

            AND (
              $3::uuid IS NULL
              OR q.source_rfq_id =
                 $3::uuid
            )

            AND (
              $4::text IS NULL
              OR q.status =
                 $4
            )

          ORDER BY
            q.updated_at DESC,
            q.id

          LIMIT $5
          OFFSET $6
          `,
          [
            parsed.data.issuerId
              ?? null,

            parsed.data.customerId
              ?? null,

            parsed.data.sourceRfqId
              ?? null,

            parsed.data.status
              ?? null,

            parsed.data.limit,
            parsed.data.offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const quotations =
        [] as Record<
          string,
          unknown
        >[];


      for (
        const row
        of result.rows
      ) {

        const quotation =
          await loadQuotation(
            row.id
          );


        if (quotation) {
          quotations.push(
            quotation
          );
        }

      }


      return {

        ok: true,

        quotations,

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


  app.post(
    "/api/quotations",
    async (
      request,
      reply
    ) => {

      const body =
        createSchema.safeParse(
          request.body
        );


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      const [
        issuerId,
        customerId,
        sourceRfqId,
        currencyId,
        namedTradeLocationId,
        namedOrganizationSiteId
      ] =
        await Promise.all([

          resolveId(
            "organizations",
            "id = $1::uuid",
            body.data.issuerId
          ),

          resolveId(
            "organizations",
            "id = $1::uuid",
            body.data.customerId
          ),

          body.data.sourceRfqId
            ? resolveId(
                "rfqs",
                "id = $1::uuid",
                body.data.sourceRfqId
              )
            : Promise.resolve(null),

          resolveId(
            "currencies",
            "code = $1 AND is_active = TRUE",
            body.data.currencyCode
          ),

          body.data.namedTradeLocationUnlocode
            ? resolveId(
                "trade_locations",
                "unlocode = $1 AND marked_for_deletion = FALSE",
                body.data.namedTradeLocationUnlocode
              )
            : Promise.resolve(null),

          body.data.namedOrganizationSiteId
            ? resolveId(
                "organization_sites",
                "id = $1::uuid AND status = 'active'",
                body.data.namedOrganizationSiteId
              )
            : Promise.resolve(null)

        ]);


      for (
        const [
          value,
          error
        ] of [
          [
            issuerId,
            "issuer_not_found"
          ],
          [
            customerId,
            "customer_not_found"
          ],
          [
            currencyId,
            "currency_not_found"
          ]
        ] as const
      ) {

        if (!value) {

          reply.code(404);

          return {
            ok: false,
            error
          };

        }

      }


      if (
        body.data.sourceRfqId
        && !sourceRfqId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "source_rfq_not_found"
        };

      }


      if (
        body.data.namedTradeLocationUnlocode
        && !namedTradeLocationId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "named_trade_location_not_found"
        };

      }


      if (
        body.data.namedOrganizationSiteId
        && !namedOrganizationSiteId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "named_organization_site_not_found"
        };

      }


      let incotermRuleId:
        string | null =
          null;


      if (
        body.data.incotermCode
      ) {

        const result =
          await database.query(
            `
            SELECT id::text
            FROM incoterm_rules
            WHERE
                edition = $1
                AND code = $2
                AND is_active = TRUE
            LIMIT 1
            `,
            [
              body.data.incotermEdition,
              body.data.incotermCode
            ]
          );


        incotermRuleId =
          result.rows[0]?.id
          ?? null;


        if (!incotermRuleId) {

          reply.code(404);

          return {
            ok: false,
            error:
              "incoterm_not_found"
          };

        }

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO quotations (
                quotation_reference,
                issuer_organization_id,
                customer_organization_id,
                source_rfq_id,
                currency_id,
                issue_date,
                valid_until,
                status,
                payment_terms,
                incoterm_rule_id,
                named_place_text,
                named_trade_location_id,
                named_organization_site_id,
                notes,
                source_type,
                canonical_source_record_id,
                confidence,
                metadata
            )
            VALUES (
                $1,
                $2::uuid,
                $3::uuid,
                $4::uuid,
                $5::uuid,
                $6::date,
                $7::date,
                $8,
                $9,
                $10::uuid,
                $11,
                $12::uuid,
                $13::uuid,
                $14,
                $15,
                $16::uuid,
                $17,
                $18::jsonb
            )
            RETURNING id::text
            `,
            [
              body.data.quotationReference,
              issuerId,
              customerId,
              sourceRfqId,
              currencyId,
              body.data.issueDate
                ?? null,
              body.data.validUntil
                ?? null,
              body.data.status,
              body.data.paymentTerms
                ?? null,
              incotermRuleId,
              body.data.namedPlaceText
                ?? null,
              namedTradeLocationId,
              namedOrganizationSiteId,
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


        reply.code(201);

        return {
          ok: true,
          quotation:
            await loadQuotation(
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
              "quotation_reference_conflict"
          };

        }


        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "quotation_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );


  app.get(
    "/api/quotations/:id",
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


      const quotation =
        await loadQuotation(
          params.data.id
        );


      if (!quotation) {

        reply.code(404);

        return {
          ok: false,
          error:
            "quotation_not_found"
        };

      }


      return {
        ok: true,
        quotation
      };

    }
  );


  app.post(
    "/api/quotations/:id/lines",
    async (
      request,
      reply
    ) => {

      const params =
        paramsSchema.safeParse(
          request.params
        );

      const body =
        createLineSchema.safeParse(
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


      const [
        quotationId,
        productId,
        manufacturerProductId,
        packagingConfigurationId,
        sourceRfqLineId,
        sourceCommercialOfferId,
        sourceLandedCostScenarioId,
        uomId
      ] =
        await Promise.all([

          resolveId(
            "quotations",
            "id = $1::uuid",
            params.data.id
          ),

          resolveId(
            "products",
            "id = $1::uuid AND is_active = TRUE",
            body.data.productId
          ),

          body.data.manufacturerProductId
            ? resolveId(
                "manufacturer_products",
                "id = $1::uuid AND status = 'active'",
                body.data.manufacturerProductId
              )
            : Promise.resolve(null),

          body.data.packagingConfigurationId
            ? resolveId(
                "packaging_configurations",
                "id = $1::uuid AND status = 'active'",
                body.data.packagingConfigurationId
              )
            : Promise.resolve(null),

          body.data.sourceRfqLineId
            ? resolveId(
                "rfq_lines",
                "id = $1::uuid",
                body.data.sourceRfqLineId
              )
            : Promise.resolve(null),

          body.data.sourceCommercialOfferId
            ? resolveId(
                "commercial_offers",
                "id = $1::uuid",
                body.data.sourceCommercialOfferId
              )
            : Promise.resolve(null),

          body.data.sourceLandedCostScenarioId
            ? resolveId(
                "landed_cost_scenarios",
                "id = $1::uuid AND status = 'calculated'",
                body.data.sourceLandedCostScenarioId
              )
            : Promise.resolve(null),

          resolveId(
            "units_of_measure",
            "code = $1 AND is_active = TRUE",
            body.data.uomCode
          )

        ]);


      for (
        const [
          value,
          error
        ] of [
          [
            quotationId,
            "quotation_not_found"
          ],
          [
            productId,
            "product_not_found"
          ],
          [
            uomId,
            "uom_not_found"
          ]
        ] as const
      ) {

        if (!value) {

          reply.code(404);

          return {
            ok: false,
            error
          };

        }

      }


      const optionalReferences = [
        [
          body.data.manufacturerProductId,
          manufacturerProductId,
          "manufacturer_product_not_found"
        ],
        [
          body.data.packagingConfigurationId,
          packagingConfigurationId,
          "packaging_configuration_not_found"
        ],
        [
          body.data.sourceRfqLineId,
          sourceRfqLineId,
          "source_rfq_line_not_found"
        ],
        [
          body.data.sourceCommercialOfferId,
          sourceCommercialOfferId,
          "source_commercial_offer_not_found"
        ],
        [
          body.data.sourceLandedCostScenarioId,
          sourceLandedCostScenarioId,
          "source_landed_cost_scenario_not_found"
        ]
      ] as const;


      for (
        const [
          supplied,
          resolved,
          error
        ] of optionalReferences
      ) {

        if (
          supplied
          && !resolved
        ) {

          reply.code(404);

          return {
            ok: false,
            error
          };

        }

      }


      try {

        await database.query(
          `
          INSERT INTO quotation_lines (
              quotation_id,
              line_number,
              product_id,
              manufacturer_product_id,
              packaging_configuration_id,
              source_rfq_line_id,
              source_commercial_offer_id,
              source_landed_cost_scenario_id,
              quantity,
              uom_id,
              internal_cost_unit_price,
              pricing_method,
              pricing_rate,
              quoted_unit_price,
              notes,
              source_type,
              canonical_source_record_id,
              confidence,
              metadata
          )
          VALUES (
              $1::uuid,
              $2,
              $3::uuid,
              $4::uuid,
              $5::uuid,
              $6::uuid,
              $7::uuid,
              $8::uuid,
              $9,
              $10::uuid,
              $11,
              $12,
              $13,
              $14,
              $15,
              $16,
              $17::uuid,
              $18,
              $19::jsonb
          )
          `,
          [
            params.data.id,
            body.data.lineNumber,
            productId,
            manufacturerProductId,
            packagingConfigurationId,
            sourceRfqLineId,
            sourceCommercialOfferId,
            sourceLandedCostScenarioId,
            body.data.quantity,
            uomId,
            body.data.internalCostUnitPrice
              ?? null,
            body.data.pricingMethod,
            body.data.pricingRate
              ?? null,
            body.data.quotedUnitPrice
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


        reply.code(201);

        return {
          ok: true,
          quotation:
            await loadQuotation(
              params.data.id
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
              "quotation_line_number_conflict"
          };

        }


        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "quotation_line_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );

}
