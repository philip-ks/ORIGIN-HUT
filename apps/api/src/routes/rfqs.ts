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


const countryCodeSchema =
  z.string()
    .trim()
    .length(2)
    .transform(
      value =>
        value.toUpperCase()
    );


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


const unlocodeSchema =
  z.string()
    .trim()
    .length(5)
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


const rfqParamsSchema =
  z.object({
    id:
      uuidSchema
  });


const listSchema =
  z.object({

    buyerId:
      uuidSchema
        .optional(),

    supplierId:
      uuidSchema
        .optional(),

    productId:
      uuidSchema
        .optional(),

    destinationCountry:
      countryCodeSchema
        .optional(),

    status: z
      .enum([
        "draft",
        "issued",
        "partially_responded",
        "responded",
        "closed",
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


const createRfqSchema =
  z.object({

    rfqReference: z
      .string()
      .trim()
      .min(1)
      .max(200),

    buyerId:
      uuidSchema,

    requesterId:
      uuidSchema
        .nullable()
        .optional(),

    destinationCountry:
      countryCodeSchema,

    destinationTradeLocationUnlocode:
      unlocodeSchema
        .nullable()
        .optional(),

    destinationOrganizationSiteId:
      uuidSchema
        .nullable()
        .optional(),

    destinationPlaceText: z
      .string()
      .trim()
      .min(1)
      .max(500)
      .nullable()
      .optional(),

    requestedCurrencyCode:
      currencyCodeSchema
        .nullable()
        .optional(),

    requestedIncotermEdition: z
      .number()
      .int()
      .positive()
      .default(2020),

    requestedIncotermCode:
      incotermCodeSchema
        .nullable()
        .optional(),

    incotermFlexible: z
      .boolean()
      .default(true),

    issueDate: z
      .string()
      .date()
      .nullable()
      .optional(),

    responseDueAt: z
      .string()
      .datetime({
        offset: true
      })
      .nullable()
      .optional(),

    status: z
      .enum([
        "draft",
        "issued"
      ])
      .default("draft"),

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
        !value.destinationTradeLocationUnlocode
        && !value.destinationOrganizationSiteId
        && !value.destinationPlaceText
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "destinationPlaceText"
            ],
          message:
            "A destination place, trade location or organization site is required."
        });

      }


      if (
        value.requesterId
        && value.requesterId
           === value.buyerId
      ) {

        ctx.addIssue({
          code:
            "custom",
          path:
            [
              "requesterId"
            ],
          message:
            "requesterId must differ from buyerId when supplied."
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

    requestedQuantity: z
      .number()
      .positive(),

    requestedUomCode:
      uomCodeSchema,

    targetDeliveryDate: z
      .string()
      .date()
      .nullable()
      .optional(),

    specificationRequirements: z
      .record(
        z.string(),
        z.unknown()
      )
      .default({}),

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


const createSupplierSchema =
  z.object({

    supplierId:
      uuidSchema,

    status: z
      .enum([
        "invited",
        "acknowledged"
      ])
      .default("invited"),

    invitedAt: z
      .string()
      .datetime({
        offset: true
      })
      .nullable()
      .optional(),

    acknowledgedAt: z
      .string()
      .datetime({
        offset: true
      })
      .nullable()
      .optional(),

    responseDueAt: z
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


async function loadRfq(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        r.id::text,

        r.rfq_reference
          AS "rfqReference",

        r.buyer_organization_id::text
          AS "buyerId",

        buyer.legal_name
          AS "buyerLegalName",

        r.requester_organization_id::text
          AS "requesterId",

        requester.legal_name
          AS "requesterLegalName",

        destination_country.iso2
          AS "destinationCountryIso2",

        destination_country.name
          AS "destinationCountryName",

        destination_location.unlocode
          AS "destinationTradeLocationUnlocode",

        destination_location.name
          AS "destinationTradeLocationName",

        destination_site.id::text
          AS "destinationOrganizationSiteId",

        destination_site.name
          AS "destinationOrganizationSiteName",

        r.destination_place_text
          AS "destinationPlaceText",

        currency.code
          AS "requestedCurrencyCode",

        incoterm.edition
          AS "requestedIncotermEdition",

        incoterm.code
          AS "requestedIncotermCode",

        incoterm.name
          AS "requestedIncotermName",

        r.incoterm_flexible
          AS "incotermFlexible",

        TO_CHAR(
          r.issue_date,
          'YYYY-MM-DD'
        ) AS "issueDate",

        r.response_due_at
          AS "responseDueAt",

        r.status,

        r.notes,

        r.source_type
          AS "sourceType",

        r.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        r.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'rfq'
            AND esl.entity_id =
              r.id
        ) AS "evidenceCount",

        r.metadata,

        r.created_at
          AS "createdAt",

        r.updated_at
          AS "updatedAt"

      FROM rfqs r

      JOIN organizations buyer
        ON buyer.id =
           r.buyer_organization_id

      LEFT JOIN organizations requester
        ON requester.id =
           r.requester_organization_id

      JOIN countries destination_country
        ON destination_country.id =
           r.destination_country_id

      LEFT JOIN trade_locations destination_location
        ON destination_location.id =
           r.destination_trade_location_id

      LEFT JOIN organization_sites destination_site
        ON destination_site.id =
           r.destination_organization_site_id

      LEFT JOIN currencies currency
        ON currency.id =
           r.requested_currency_id

      LEFT JOIN incoterm_rules incoterm
        ON incoterm.id =
           r.requested_incoterm_rule_id

      WHERE r.id =
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
        rl.id::text,

        rl.line_number
          AS "lineNumber",

        rl.product_id::text
          AS "productId",

        p.name
          AS "productName",

        rl.manufacturer_product_id::text
          AS "manufacturerProductId",

        mp.name
          AS "manufacturerProductName",

        rl.packaging_configuration_id::text
          AS "packagingConfigurationId",

        pc.name
          AS "packagingName",

        rl.requested_quantity::double precision
          AS "requestedQuantity",

        uom.code
          AS "requestedUomCode",

        uom.symbol
          AS "requestedUomSymbol",

        TO_CHAR(
          rl.target_delivery_date,
          'YYYY-MM-DD'
        ) AS "targetDeliveryDate",

        rl.specification_requirements
          AS "specificationRequirements",

        rl.notes,

        rl.source_type
          AS "sourceType",

        rl.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        rl.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'rfq_line'
            AND esl.entity_id =
              rl.id
        ) AS "evidenceCount",

        rl.metadata,

        rl.created_at
          AS "createdAt",

        rl.updated_at
          AS "updatedAt"

      FROM rfq_lines rl

      JOIN products p
        ON p.id =
           rl.product_id

      LEFT JOIN manufacturer_products mp
        ON mp.id =
           rl.manufacturer_product_id

      LEFT JOIN packaging_configurations pc
        ON pc.id =
           rl.packaging_configuration_id

      JOIN units_of_measure uom
        ON uom.id =
           rl.requested_uom_id

      WHERE rl.rfq_id =
            $1::uuid

      ORDER BY
        rl.line_number,
        rl.id
      `,
      [
        id
      ]
    );


  const suppliers =
    await database.query(
      `
      SELECT
        rs.id::text,

        rs.supplier_organization_id::text
          AS "supplierId",

        supplier.legal_name
          AS "supplierLegalName",

        rs.status,

        rs.invited_at
          AS "invitedAt",

        rs.acknowledged_at
          AS "acknowledgedAt",

        rs.responded_at
          AS "respondedAt",

        rs.response_due_at
          AS "responseDueAt",

        rs.notes,

        rs.source_type
          AS "sourceType",

        rs.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        rs.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'rfq_supplier'
            AND esl.entity_id =
              rs.id
        ) AS "evidenceCount",

        rs.metadata,

        rs.created_at
          AS "createdAt",

        rs.updated_at
          AS "updatedAt"

      FROM rfq_suppliers rs

      JOIN organizations supplier
        ON supplier.id =
           rs.supplier_organization_id

      WHERE rs.rfq_id =
            $1::uuid

      ORDER BY
        supplier.legal_name,
        rs.id
      `,
      [
        id
      ]
    );


  return {
    ...result.rows[0],
    lines:
      lines.rows,
    suppliers:
      suppliers.rows
  };

}


export async function rfqRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/rfqs",
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
            r.id::text,
            r.updated_at,
            COUNT(*) OVER()::int
              AS "totalCount"

          FROM rfqs r

          JOIN countries destination_country
            ON destination_country.id =
               r.destination_country_id

          WHERE
            (
              $1::uuid IS NULL
              OR r.buyer_organization_id =
                 $1::uuid
            )

            AND (
              $2::uuid IS NULL
              OR EXISTS (
                SELECT 1
                FROM rfq_suppliers rs
                WHERE
                  rs.rfq_id = r.id
                  AND rs.supplier_organization_id =
                      $2::uuid
              )
            )

            AND (
              $3::uuid IS NULL
              OR EXISTS (
                SELECT 1
                FROM rfq_lines rl
                WHERE
                  rl.rfq_id = r.id
                  AND rl.product_id =
                      $3::uuid
              )
            )

            AND (
              $4::text IS NULL
              OR destination_country.iso2 =
                 $4
            )

            AND (
              $5::text IS NULL
              OR r.status =
                 $5
            )

          ORDER BY
            r.updated_at DESC,
            r.id

          LIMIT $6
          OFFSET $7
          `,
          [
            parsed.data.buyerId
              ?? null,

            parsed.data.supplierId
              ?? null,

            parsed.data.productId
              ?? null,

            parsed.data.destinationCountry
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


      const rfqs =
        [] as Record<
          string,
          unknown
        >[];


      for (
        const row
        of result.rows
      ) {

        const rfq =
          await loadRfq(
            row.id
          );


        if (rfq) {
          rfqs.push(
            rfq
          );
        }

      }


      return {

        ok: true,

        rfqs,

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
    "/api/rfqs",
    async (
      request,
      reply
    ) => {

      const body =
        createRfqSchema.safeParse(
          request.body
        );


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      const [
        buyerId,
        requesterId,
        destinationCountryId,
        destinationTradeLocationId,
        destinationOrganizationSiteId,
        requestedCurrencyId
      ] =
        await Promise.all([

          resolveId(
            "organizations",
            "id = $1::uuid",
            body.data.buyerId
          ),

          body.data.requesterId
            ? resolveId(
                "organizations",
                "id = $1::uuid",
                body.data.requesterId
              )
            : Promise.resolve(null),

          resolveId(
            "countries",
            "iso2 = $1 AND is_active = TRUE",
            body.data.destinationCountry
          ),

          body.data.destinationTradeLocationUnlocode
            ? resolveId(
                "trade_locations",
                "unlocode = $1 AND marked_for_deletion = FALSE",
                body.data.destinationTradeLocationUnlocode
              )
            : Promise.resolve(null),

          body.data.destinationOrganizationSiteId
            ? resolveId(
                "organization_sites",
                "id = $1::uuid AND status = 'active'",
                body.data.destinationOrganizationSiteId
              )
            : Promise.resolve(null),

          body.data.requestedCurrencyCode
            ? resolveId(
                "currencies",
                "code = $1 AND is_active = TRUE",
                body.data.requestedCurrencyCode
              )
            : Promise.resolve(null)

        ]);


      for (
        const [
          value,
          error
        ] of [
          [
            buyerId,
            "buyer_not_found"
          ],
          [
            destinationCountryId,
            "destination_country_not_found"
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
        body.data.requesterId
        && !requesterId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "requester_not_found"
        };

      }


      if (
        body.data.destinationTradeLocationUnlocode
        && !destinationTradeLocationId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "destination_trade_location_not_found"
        };

      }


      if (
        body.data.destinationOrganizationSiteId
        && !destinationOrganizationSiteId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "destination_organization_site_not_found"
        };

      }


      if (
        body.data.requestedCurrencyCode
        && !requestedCurrencyId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "requested_currency_not_found"
        };

      }


      let requestedIncotermRuleId:
        string | null =
          null;


      if (
        body.data.requestedIncotermCode
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
              body.data.requestedIncotermEdition,
              body.data.requestedIncotermCode
            ]
          );


        requestedIncotermRuleId =
          result.rows[0]?.id
          ?? null;


        if (!requestedIncotermRuleId) {

          reply.code(404);

          return {
            ok: false,
            error:
              "requested_incoterm_not_found"
          };

        }

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO rfqs (
                rfq_reference,
                buyer_organization_id,
                requester_organization_id,
                destination_country_id,
                destination_trade_location_id,
                destination_organization_site_id,
                destination_place_text,
                requested_currency_id,
                requested_incoterm_rule_id,
                incoterm_flexible,
                issue_date,
                response_due_at,
                status,
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
                $6::uuid,
                $7,
                $8::uuid,
                $9::uuid,
                $10,
                $11::date,
                $12::timestamptz,
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
              body.data.rfqReference,
              buyerId,
              requesterId,
              destinationCountryId,
              destinationTradeLocationId,
              destinationOrganizationSiteId,
              body.data.destinationPlaceText
                ?? null,
              requestedCurrencyId,
              requestedIncotermRuleId,
              body.data.incotermFlexible,
              body.data.issueDate
                ?? null,
              body.data.responseDueAt
                ?? null,
              body.data.status,
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
          rfq:
            await loadRfq(
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
              "rfq_reference_conflict"
          };

        }


        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "rfq_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );


  app.get(
    "/api/rfqs/:id",
    async (
      request,
      reply
    ) => {

      const params =
        rfqParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const rfq =
        await loadRfq(
          params.data.id
        );


      if (!rfq) {

        reply.code(404);

        return {
          ok: false,
          error:
            "rfq_not_found"
        };

      }


      return {
        ok: true,
        rfq
      };

    }
  );


  app.post(
    "/api/rfqs/:id/lines",
    async (
      request,
      reply
    ) => {

      const params =
        rfqParamsSchema.safeParse(
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


      const rfq =
        await resolveId(
          "rfqs",
          "id = $1::uuid",
          params.data.id
        );


      if (!rfq) {

        reply.code(404);

        return {
          ok: false,
          error:
            "rfq_not_found"
        };

      }


      const [
        productId,
        manufacturerProductId,
        packagingConfigurationId,
        requestedUomId
      ] =
        await Promise.all([

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

          resolveId(
            "units_of_measure",
            "code = $1 AND is_active = TRUE",
            body.data.requestedUomCode
          )

        ]);


      for (
        const [
          value,
          error
        ] of [
          [
            productId,
            "product_not_found"
          ],
          [
            requestedUomId,
            "requested_uom_not_found"
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
        body.data.manufacturerProductId
        && !manufacturerProductId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "manufacturer_product_not_found"
        };

      }


      if (
        body.data.packagingConfigurationId
        && !packagingConfigurationId
      ) {

        reply.code(404);

        return {
          ok: false,
          error:
            "packaging_configuration_not_found"
        };

      }


      try {

        await database.query(
          `
          INSERT INTO rfq_lines (
              rfq_id,
              line_number,
              product_id,
              manufacturer_product_id,
              packaging_configuration_id,
              requested_quantity,
              requested_uom_id,
              target_delivery_date,
              specification_requirements,
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
              $6,
              $7::uuid,
              $8::date,
              $9::jsonb,
              $10,
              $11,
              $12::uuid,
              $13,
              $14::jsonb
          )
          `,
          [
            params.data.id,
            body.data.lineNumber,
            productId,
            manufacturerProductId,
            packagingConfigurationId,
            body.data.requestedQuantity,
            requestedUomId,
            body.data.targetDeliveryDate
              ?? null,
            JSON.stringify(
              body.data.specificationRequirements
            ),
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
          rfq:
            await loadRfq(
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
              "rfq_line_number_conflict"
          };

        }


        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "rfq_line_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );


  app.post(
    "/api/rfqs/:id/suppliers",
    async (
      request,
      reply
    ) => {

      const params =
        rfqParamsSchema.safeParse(
          request.params
        );

      const body =
        createSupplierSchema.safeParse(
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
        rfqId,
        supplierId
      ] =
        await Promise.all([

          resolveId(
            "rfqs",
            "id = $1::uuid",
            params.data.id
          ),

          resolveId(
            "organizations",
            "id = $1::uuid",
            body.data.supplierId
          )

        ]);


      if (!rfqId) {

        reply.code(404);

        return {
          ok: false,
          error:
            "rfq_not_found"
        };

      }


      if (!supplierId) {

        reply.code(404);

        return {
          ok: false,
          error:
            "supplier_not_found"
        };

      }


      try {

        await database.query(
          `
          INSERT INTO rfq_suppliers (
              rfq_id,
              supplier_organization_id,
              status,
              invited_at,
              acknowledged_at,
              response_due_at,
              notes,
              source_type,
              canonical_source_record_id,
              confidence,
              metadata
          )
          VALUES (
              $1::uuid,
              $2::uuid,
              $3,
              COALESCE(
                $4::timestamptz,
                NOW()
              ),
              $5::timestamptz,
              $6::timestamptz,
              $7,
              $8,
              $9::uuid,
              $10,
              $11::jsonb
          )
          `,
          [
            params.data.id,
            supplierId,
            body.data.status,
            body.data.invitedAt
              ?? null,
            body.data.acknowledgedAt
              ?? null,
            body.data.responseDueAt
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
          rfq:
            await loadRfq(
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
              "rfq_supplier_conflict"
          };

        }


        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "rfq_supplier_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );

}
