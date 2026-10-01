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

    sellerId:
      uuidSchema
        .optional(),

    buyerId:
      uuidSchema
        .optional(),

    manufacturerProductId:
      uuidSchema
        .optional(),

    incotermCode:
      incotermCodeSchema
        .optional(),

    incotermEdition: z.coerce
      .number()
      .int()
      .positive()
      .optional(),

    status: z
      .enum([
        "draft",
        "active",
        "expired",
        "withdrawn",
        "superseded"
      ])
      .optional(),

    validOn: z
      .string()
      .date()
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

    sellerId:
      uuidSchema,

    buyerId:
      uuidSchema
        .nullable()
        .optional(),

    manufacturerProductId:
      uuidSchema,

    packagingConfigurationId:
      uuidSchema
        .nullable()
        .optional(),

    offerReference: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .nullable()
      .optional(),

    status: z
      .enum([
        "draft",
        "active"
      ])
      .default("draft"),

    unitPrice: z
      .number()
      .positive(),

    currencyCode:
      currencyCodeSchema,

    priceUomCode:
      uomCodeSchema,

    minimumOrderQuantity: z
      .number()
      .positive()
      .nullable()
      .optional(),

    minimumOrderUomCode:
      uomCodeSchema
        .nullable()
        .optional(),

    leadTimeDays: z
      .number()
      .int()
      .min(0)
      .nullable()
      .optional(),

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
      incotermCodeSchema,

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
        (
          value.minimumOrderQuantity
          != null
        )
        !== (
          value.minimumOrderUomCode
          != null
        )
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "minimumOrderUomCode"
            ],
          message:
            "minimumOrderQuantity and minimumOrderUomCode must be supplied together."
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


      if (
        !value.namedPlaceText
        && !value.namedTradeLocationUnlocode
        && !value.namedOrganizationSiteId
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "namedPlaceText"
            ],
          message:
            "A named place, trade location or organization site is required."
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


async function loadOffer(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        co.id::text AS id,

        co.seller_organization_id::text
          AS "sellerId",

        seller.legal_name
          AS "sellerLegalName",

        co.buyer_organization_id::text
          AS "buyerId",

        buyer.legal_name
          AS "buyerLegalName",

        co.manufacturer_product_id::text
          AS "manufacturerProductId",

        mp.name
          AS "manufacturerProductName",

        p.id::text
          AS "productId",

        p.name
          AS "productName",

        co.packaging_configuration_id::text
          AS "packagingConfigurationId",

        pc.name
          AS "packagingName",

        co.offer_reference
          AS "offerReference",

        co.status,

        co.unit_price::double precision
          AS "unitPrice",

        currency.code
          AS "currencyCode",

        currency.name
          AS "currencyName",

        price_uom.code
          AS "priceUomCode",

        price_uom.symbol
          AS "priceUomSymbol",

        co.minimum_order_quantity::double precision
          AS "minimumOrderQuantity",

        moq_uom.code
          AS "minimumOrderUomCode",

        co.lead_time_days
          AS "leadTimeDays",

        co.payment_terms
          AS "paymentTerms",

        ir.edition
          AS "incotermEdition",

        ir.code
          AS "incotermCode",

        ir.name
          AS "incotermName",

        ir.transport_scope
          AS "incotermTransportScope",

        ir.named_location_role
          AS "namedLocationRole",

        co.named_place_text
          AS "namedPlaceText",

        tl.id::text
          AS "namedTradeLocationId",

        tl.unlocode
          AS "namedTradeLocationUnlocode",

        tl.name
          AS "namedTradeLocationName",

        os.id::text
          AS "namedOrganizationSiteId",

        os.name
          AS "namedOrganizationSiteName",

        TO_CHAR(
          co.valid_from,
          'YYYY-MM-DD'
        ) AS "validFrom",

        TO_CHAR(
          co.valid_to,
          'YYYY-MM-DD'
        ) AS "validTo",

        co.source_type
          AS "sourceType",

        co.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        co.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'commercial_offer'
            AND esl.entity_id =
              co.id
        ) AS "evidenceCount",

        co.metadata,

        co.created_at
          AS "createdAt",

        co.updated_at
          AS "updatedAt"

      FROM commercial_offers co

      JOIN organizations seller
        ON seller.id =
           co.seller_organization_id

      LEFT JOIN organizations buyer
        ON buyer.id =
           co.buyer_organization_id

      JOIN manufacturer_products mp
        ON mp.id =
           co.manufacturer_product_id

      JOIN products p
        ON p.id =
           mp.product_id

      LEFT JOIN packaging_configurations pc
        ON pc.id =
           co.packaging_configuration_id

      JOIN currencies currency
        ON currency.id =
           co.currency_id

      JOIN units_of_measure price_uom
        ON price_uom.id =
           co.price_uom_id

      LEFT JOIN units_of_measure moq_uom
        ON moq_uom.id =
           co.minimum_order_uom_id

      JOIN incoterm_rules ir
        ON ir.id =
           co.incoterm_rule_id

      LEFT JOIN trade_locations tl
        ON tl.id =
           co.named_trade_location_id

      LEFT JOIN organization_sites os
        ON os.id =
           co.named_organization_site_id

      WHERE co.id =
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


export async function commercialOfferRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/commercial-offers",
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
            co.id::text,
            COUNT(*) OVER()::int
              AS "totalCount"

          FROM commercial_offers co

          JOIN incoterm_rules ir
            ON ir.id =
               co.incoterm_rule_id

          WHERE
            (
              $1::uuid IS NULL
              OR co.seller_organization_id =
                 $1::uuid
            )

            AND (
              $2::uuid IS NULL
              OR co.buyer_organization_id =
                 $2::uuid
            )

            AND (
              $3::uuid IS NULL
              OR co.manufacturer_product_id =
                 $3::uuid
            )

            AND (
              $4::text IS NULL
              OR ir.code = $4
            )

            AND (
              $5::integer IS NULL
              OR ir.edition = $5
            )

            AND (
              $6::text IS NULL
              OR co.status = $6
            )

            AND (
              $7::date IS NULL
              OR (
                (
                  co.valid_from IS NULL
                  OR co.valid_from <= $7::date
                )
                AND (
                  co.valid_to IS NULL
                  OR co.valid_to >= $7::date
                )
              )
            )

          ORDER BY
            co.updated_at DESC,
            co.id

          LIMIT $8
          OFFSET $9
          `,
          [
            parsed.data.sellerId
              ?? null,

            parsed.data.buyerId
              ?? null,

            parsed.data.manufacturerProductId
              ?? null,

            parsed.data.incotermCode
              ?? null,

            parsed.data.incotermEdition
              ?? null,

            parsed.data.status
              ?? null,

            parsed.data.validOn
              ?? null,

            parsed.data.limit,
            parsed.data.offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const offers =
        [] as Record<
          string,
          unknown
        >[];


      for (
        const row
        of result.rows
      ) {

        const offer =
          await loadOffer(
            row.id
          );


        if (offer) {
          offers.push(
            offer
          );
        }

      }


      return {

        ok: true,

        offers,

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
    "/api/commercial-offers",
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
        sellerId,
        buyerId,
        manufacturerProductId,
        packagingId,
        currencyId,
        priceUomId,
        moqUomId,
        incotermRuleId,
        tradeLocationId,
        siteId
      ] =
        await Promise.all([

          resolveId(
            "organizations",
            "id = $1::uuid",
            body.data.sellerId
          ),

          body.data.buyerId
            ? resolveId(
                "organizations",
                "id = $1::uuid",
                body.data.buyerId
              )
            : Promise.resolve(null),

          resolveId(
            "manufacturer_products",
            "id = $1::uuid AND status = 'active'",
            body.data.manufacturerProductId
          ),

          body.data.packagingConfigurationId
            ? resolveId(
                "packaging_configurations",
                "id = $1::uuid AND status = 'active'",
                body.data.packagingConfigurationId
              )
            : Promise.resolve(null),

          resolveId(
            "currencies",
            "code = $1 AND is_active = TRUE",
            body.data.currencyCode
          ),

          resolveId(
            "units_of_measure",
            "code = $1 AND is_active = TRUE",
            body.data.priceUomCode
          ),

          body.data.minimumOrderUomCode
            ? resolveId(
                "units_of_measure",
                "code = $1 AND is_active = TRUE",
                body.data.minimumOrderUomCode
              )
            : Promise.resolve(null),

          resolveId(
            "incoterm_rules",
            "edition = "
            + String(
                body.data.incotermEdition
              )
            + " AND code = $1 AND is_active = TRUE",
            body.data.incotermCode
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
            sellerId,
            "seller_not_found"
          ],
          [
            manufacturerProductId,
            "manufacturer_product_not_found"
          ],
          [
            currencyId,
            "currency_not_found"
          ],
          [
            priceUomId,
            "price_uom_not_found"
          ],
          [
            incotermRuleId,
            "incoterm_not_found"
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
        body.data.buyerId
        && !buyerId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "buyer_not_found"
        };

      }


      if (
        body.data.packagingConfigurationId
        && !packagingId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "packaging_not_found"
        };

      }


      if (
        body.data.minimumOrderUomCode
        && !moqUomId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "minimum_order_uom_not_found"
        };

      }


      if (
        body.data.namedTradeLocationUnlocode
        && !tradeLocationId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "trade_location_not_found"
        };

      }


      if (
        body.data.namedOrganizationSiteId
        && !siteId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "organization_site_not_found"
        };

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO commercial_offers (
                seller_organization_id,
                buyer_organization_id,
                manufacturer_product_id,
                packaging_configuration_id,
                offer_reference,
                status,
                unit_price,
                currency_id,
                price_uom_id,
                minimum_order_quantity,
                minimum_order_uom_id,
                lead_time_days,
                payment_terms,
                incoterm_rule_id,
                named_place_text,
                named_trade_location_id,
                named_organization_site_id,
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
                $4::uuid,
                $5,
                $6,
                $7,
                $8::uuid,
                $9::uuid,
                $10,
                $11::uuid,
                $12,
                $13,
                $14::uuid,
                $15,
                $16::uuid,
                $17::uuid,
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
              sellerId,
              buyerId,
              manufacturerProductId,
              packagingId,
              body.data.offerReference
                ?? null,
              body.data.status,
              body.data.unitPrice,
              currencyId,
              priceUomId,
              body.data.minimumOrderQuantity
                ?? null,
              moqUomId,
              body.data.leadTimeDays
                ?? null,
              body.data.paymentTerms
                ?? null,
              incotermRuleId,
              body.data.namedPlaceText
                ?? null,
              tradeLocationId,
              siteId,
              body.data.validFrom
                ?? null,
              body.data.validTo
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

          offer:
            await loadOffer(
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
              "commercial_offer_reference_conflict"
          };

        }


        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "commercial_offer_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );


  app.get(
    "/api/commercial-offers/:id",
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


      const offer =
        await loadOffer(
          params.data.id
        );


      if (!offer) {

        reply.code(404);

        return {
          ok: false,
          error:
            "commercial_offer_not_found"
        };

      }


      return {
        ok: true,
        offer
      };

    }
  );

}
