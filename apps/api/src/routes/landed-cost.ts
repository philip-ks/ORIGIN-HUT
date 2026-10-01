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


const countryCodeSchema =
  z.string()
    .trim()
    .length(2)
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


const scenarioParamsSchema =
  z.object({
    id:
      uuidSchema
  });


const listSchema =
  z.object({

    commercialOfferId:
      uuidSchema
        .optional(),

    manufacturerProductId:
      uuidSchema
        .optional(),

    productId:
      uuidSchema
        .optional(),

    sellerId:
      uuidSchema
        .optional(),

    destinationCountry:
      countryCodeSchema
        .optional(),

    status: z
      .enum([
        "draft",
        "calculated",
        "archived"
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


const createScenarioSchema =
  z.object({

    commercialOfferId:
      uuidSchema,

    scenarioReference: z
      .string()
      .trim()
      .min(1)
      .max(200)
      .nullable()
      .optional(),

    status: z
      .enum([
        "draft",
        "calculated"
      ])
      .default("draft"),

    targetQuantity: z
      .number()
      .positive(),

    targetUomCode:
      uomCodeSchema,

    scenarioCurrencyCode:
      currencyCodeSchema,

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

    offerFxRateToScenario: z
      .number()
      .positive()
      .nullable()
      .optional(),

    offerFxRateDate: z
      .string()
      .date()
      .nullable()
      .optional(),

    offerFxSource: z
      .string()
      .trim()
      .min(1)
      .max(500)
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

    }
  );


const componentSchema =
  z.object({

    componentTypeCode: z
      .string()
      .trim()
      .min(1)
      .max(100)
      .transform(
        value =>
          value.toLowerCase()
      ),

    sequence: z
      .number()
      .int()
      .positive()
      .optional(),

    description: z
      .string()
      .trim()
      .min(1)
      .max(2000)
      .nullable()
      .optional(),

    includedInOffer: z
      .boolean()
      .default(false),

    calculationMethod: z
      .enum([
        "fixed_amount",
        "percentage"
      ])
      .default(
        "fixed_amount"
      ),

    sourceAmount: z
      .number()
      .min(0)
      .nullable()
      .optional(),

    sourceCurrencyCode:
      currencyCodeSchema
        .nullable()
        .optional(),

    exchangeRateToScenario: z
      .number()
      .positive()
      .nullable()
      .optional(),

    percentageRate: z
      .number()
      .min(0)
      .max(100)
      .nullable()
      .optional(),

    taxableBaseScenarioCurrency: z
      .number()
      .min(0)
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
        value.calculationMethod
        === "fixed_amount"
      ) {

        if (
          value.sourceAmount
          == null
          || !value.sourceCurrencyCode
        ) {

          ctx.addIssue({
            code:
              "custom",
            path:
              [
                "sourceAmount"
              ],
            message:
              "Fixed amount components require sourceAmount and sourceCurrencyCode."
          });

        }

      }
      else {

        if (
          value.percentageRate
          == null
          || value.taxableBaseScenarioCurrency
             == null
        ) {

          ctx.addIssue({
            code:
              "custom",
            path:
              [
                "percentageRate"
              ],
            message:
              "Percentage components require percentageRate and taxableBaseScenarioCurrency."
          });

        }

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


async function loadScenario(
  id: string
) {

  const result =
    await database.query(
      `
      SELECT
        lcs.id::text,

        lcs.commercial_offer_id::text
          AS "commercialOfferId",

        co.offer_reference
          AS "commercialOfferReference",

        co.seller_organization_id::text
          AS "sellerId",

        seller.legal_name
          AS "sellerLegalName",

        co.manufacturer_product_id::text
          AS "manufacturerProductId",

        mp.name
          AS "manufacturerProductName",

        p.id::text
          AS "productId",

        p.name
          AS "productName",

        ir.edition
          AS "incotermEdition",

        ir.code
          AS "incotermCode",

        co.named_place_text
          AS "offerNamedPlaceText",

        offer_location.unlocode
          AS "offerNamedTradeLocationUnlocode",

        lcs.scenario_reference
          AS "scenarioReference",

        lcs.status,

        lcs.target_quantity::double precision
          AS "targetQuantity",

        target_uom.code
          AS "targetUomCode",

        target_uom.symbol
          AS "targetUomSymbol",

        scenario_currency.code
          AS "scenarioCurrencyCode",

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

        lcs.destination_place_text
          AS "destinationPlaceText",

        lcs.offer_fx_rate_to_scenario::double precision
          AS "offerFxRateToScenario",

        TO_CHAR(
          lcs.offer_fx_rate_date,
          'YYYY-MM-DD'
        ) AS "offerFxRateDate",

        lcs.offer_fx_source
          AS "offerFxSource",

        lcs.offer_amount_source_currency::double precision
          AS "offerAmountSourceCurrency",

        offer_currency.code
          AS "offerCurrencyCode",

        lcs.offer_amount_scenario_currency::double precision
          AS "offerAmountScenarioCurrency",

        lcs.included_component_total_scenario_currency::double precision
          AS "includedComponentTotalScenarioCurrency",

        lcs.added_component_total_scenario_currency::double precision
          AS "addedComponentTotalScenarioCurrency",

        lcs.landed_cost_total_scenario_currency::double precision
          AS "landedCostTotalScenarioCurrency",

        lcs.landed_cost_per_target_uom::double precision
          AS "landedCostPerTargetUom",

        lcs.notes,

        lcs.source_type
          AS "sourceType",

        lcs.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        lcs.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'landed_cost_scenario'
            AND esl.entity_id =
              lcs.id
        ) AS "evidenceCount",

        lcs.metadata,

        lcs.calculated_at
          AS "calculatedAt",

        lcs.created_at
          AS "createdAt",

        lcs.updated_at
          AS "updatedAt"

      FROM landed_cost_scenarios lcs

      JOIN commercial_offers co
        ON co.id =
           lcs.commercial_offer_id

      JOIN organizations seller
        ON seller.id =
           co.seller_organization_id

      JOIN manufacturer_products mp
        ON mp.id =
           co.manufacturer_product_id

      JOIN products p
        ON p.id =
           mp.product_id

      JOIN incoterm_rules ir
        ON ir.id =
           co.incoterm_rule_id

      JOIN currencies offer_currency
        ON offer_currency.id =
           co.currency_id

      JOIN units_of_measure target_uom
        ON target_uom.id =
           lcs.target_uom_id

      JOIN currencies scenario_currency
        ON scenario_currency.id =
           lcs.scenario_currency_id

      JOIN countries destination_country
        ON destination_country.id =
           lcs.destination_country_id

      LEFT JOIN trade_locations destination_location
        ON destination_location.id =
           lcs.destination_trade_location_id

      LEFT JOIN organization_sites destination_site
        ON destination_site.id =
           lcs.destination_organization_site_id

      LEFT JOIN trade_locations offer_location
        ON offer_location.id =
           co.named_trade_location_id

      WHERE lcs.id =
            $1::uuid
      `,
      [
        id
      ]
    );


  if (!result.rows[0]) {
    return null;
  }


  const components =
    await database.query(
      `
      SELECT
        lcc.id::text,

        lcc.component_type_code
          AS "componentTypeCode",

        type.name
          AS "componentTypeName",

        type.category
          AS "componentCategory",

        lcc.sequence,

        lcc.description,

        lcc.included_in_offer
          AS "includedInOffer",

        lcc.calculation_method
          AS "calculationMethod",

        lcc.source_amount::double precision
          AS "sourceAmount",

        source_currency.code
          AS "sourceCurrencyCode",

        lcc.exchange_rate_to_scenario::double precision
          AS "exchangeRateToScenario",

        lcc.percentage_rate::double precision
          AS "percentageRate",

        lcc.taxable_base_scenario_currency::double precision
          AS "taxableBaseScenarioCurrency",

        lcc.amount_scenario_currency::double precision
          AS "amountScenarioCurrency",

        lcc.notes,

        lcc.source_type
          AS "sourceType",

        lcc.canonical_source_record_id::text
          AS "canonicalSourceRecordId",

        lcc.confidence::double precision
          AS confidence,

        (
          SELECT COUNT(*)::int
          FROM entity_source_links esl
          WHERE
            esl.entity_type =
              'landed_cost_component'
            AND esl.entity_id =
              lcc.id
        ) AS "evidenceCount",

        lcc.metadata,

        lcc.created_at
          AS "createdAt",

        lcc.updated_at
          AS "updatedAt"

      FROM landed_cost_components lcc

      JOIN landed_cost_component_types type
        ON type.code =
           lcc.component_type_code

      LEFT JOIN currencies source_currency
        ON source_currency.id =
           lcc.source_currency_id

      WHERE lcc.scenario_id =
            $1::uuid

      ORDER BY
        lcc.sequence,
        lcc.created_at,
        lcc.id
      `,
      [
        id
      ]
    );


  return {
    ...result.rows[0],
    components:
      components.rows
  };

}


export async function landedCostRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/landed-cost/component-types",
    async () => {

      const result =
        await database.query(
          `
          SELECT
            code,
            name,
            category,

            default_sequence
              AS "defaultSequence",

            is_active
              AS "isActive",

            metadata

          FROM landed_cost_component_types

          WHERE is_active = TRUE

          ORDER BY
            default_sequence,
            code
          `
        );


      return {
        ok: true,
        componentTypes:
          result.rows
      };

    }
  );


  app.get(
    "/api/landed-cost/scenarios",
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
            lcs.id::text,
            COUNT(*) OVER()::int
              AS "totalCount"

          FROM landed_cost_scenarios lcs

          JOIN commercial_offers co
            ON co.id =
               lcs.commercial_offer_id

          JOIN manufacturer_products mp
            ON mp.id =
               co.manufacturer_product_id

          JOIN countries destination_country
            ON destination_country.id =
               lcs.destination_country_id

          WHERE
            (
              $1::uuid IS NULL
              OR lcs.commercial_offer_id =
                 $1::uuid
            )

            AND (
              $2::uuid IS NULL
              OR co.manufacturer_product_id =
                 $2::uuid
            )

            AND (
              $3::uuid IS NULL
              OR mp.product_id =
                 $3::uuid
            )

            AND (
              $4::uuid IS NULL
              OR co.seller_organization_id =
                 $4::uuid
            )

            AND (
              $5::text IS NULL
              OR destination_country.iso2 =
                 $5
            )

            AND (
              $6::text IS NULL
              OR lcs.status =
                 $6
            )

          ORDER BY
            lcs.updated_at DESC,
            lcs.id

          LIMIT $7
          OFFSET $8
          `,
          [
            parsed.data.commercialOfferId
              ?? null,

            parsed.data.manufacturerProductId
              ?? null,

            parsed.data.productId
              ?? null,

            parsed.data.sellerId
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


      const scenarios =
        [] as Record<
          string,
          unknown
        >[];


      for (
        const row
        of result.rows
      ) {

        const scenario =
          await loadScenario(
            row.id
          );


        if (scenario) {
          scenarios.push(
            scenario
          );
        }

      }


      return {

        ok: true,

        scenarios,

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
    "/api/landed-cost/scenarios",
    async (
      request,
      reply
    ) => {

      const body =
        createScenarioSchema.safeParse(
          request.body
        );


      if (!body.success) {

        reply.code(400);

        return validationError(
          body.error.issues
        );

      }


      const [
        commercialOfferId,
        targetUomId,
        scenarioCurrencyId,
        destinationCountryId,
        destinationTradeLocationId,
        destinationOrganizationSiteId
      ] =
        await Promise.all([

          resolveId(
            "commercial_offers",
            "id = $1::uuid",
            body.data.commercialOfferId
          ),

          resolveId(
            "units_of_measure",
            "code = $1 AND is_active = TRUE",
            body.data.targetUomCode
          ),

          resolveId(
            "currencies",
            "code = $1 AND is_active = TRUE",
            body.data.scenarioCurrencyCode
          ),

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
            : Promise.resolve(null)

        ]);


      for (
        const [
          value,
          error
        ] of [
          [
            commercialOfferId,
            "commercial_offer_not_found"
          ],
          [
            targetUomId,
            "target_uom_not_found"
          ],
          [
            scenarioCurrencyId,
            "scenario_currency_not_found"
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


      try {

        const result =
          await database.query(
            `
            INSERT INTO landed_cost_scenarios (
                commercial_offer_id,
                scenario_reference,
                status,
                target_quantity,
                target_uom_id,
                scenario_currency_id,
                destination_country_id,
                destination_trade_location_id,
                destination_organization_site_id,
                destination_place_text,
                offer_fx_rate_to_scenario,
                offer_fx_rate_date,
                offer_fx_source,
                notes,
                source_type,
                canonical_source_record_id,
                confidence,
                metadata
            )
            VALUES (
                $1::uuid,
                $2,
                $3,
                $4,
                $5::uuid,
                $6::uuid,
                $7::uuid,
                $8::uuid,
                $9::uuid,
                $10,
                $11,
                $12::date,
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
              commercialOfferId,
              body.data.scenarioReference
                ?? null,
              body.data.status,
              body.data.targetQuantity,
              targetUomId,
              scenarioCurrencyId,
              destinationCountryId,
              destinationTradeLocationId,
              destinationOrganizationSiteId,
              body.data.destinationPlaceText
                ?? null,
              body.data.offerFxRateToScenario
                ?? null,
              body.data.offerFxRateDate
                ?? null,
              body.data.offerFxSource
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
          scenario:
            await loadScenario(
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
              "landed_cost_scenario_reference_conflict"
          };

        }


        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "landed_cost_scenario_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );


  app.get(
    "/api/landed-cost/scenarios/:id",
    async (
      request,
      reply
    ) => {

      const params =
        scenarioParamsSchema.safeParse(
          request.params
        );


      if (!params.success) {

        reply.code(400);

        return validationError(
          params.error.issues
        );

      }


      const scenario =
        await loadScenario(
          params.data.id
        );


      if (!scenario) {

        reply.code(404);

        return {
          ok: false,
          error:
            "landed_cost_scenario_not_found"
        };

      }


      return {
        ok: true,
        scenario
      };

    }
  );


  app.post(
    "/api/landed-cost/scenarios/:id/components",
    async (
      request,
      reply
    ) => {

      const params =
        scenarioParamsSchema.safeParse(
          request.params
        );

      const body =
        componentSchema.safeParse(
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


      const scenario =
        await database.query(
          `
          SELECT
            id::text,

            scenario_currency_id::text
              AS "scenarioCurrencyId"

          FROM landed_cost_scenarios

          WHERE id =
                $1::uuid
          `,
          [
            params.data.id
          ]
        );


      if (!scenario.rows[0]) {

        reply.code(404);

        return {
          ok: false,
          error:
            "landed_cost_scenario_not_found"
        };

      }


      const type =
        await database.query(
          `
          SELECT
            code,
            default_sequence
              AS "defaultSequence"

          FROM landed_cost_component_types

          WHERE
            code = $1
            AND is_active = TRUE
          `,
          [
            body.data.componentTypeCode
          ]
        );


      if (!type.rows[0]) {

        reply.code(404);

        return {
          ok: false,
          error:
            "landed_cost_component_type_not_found"
        };

      }


      let sourceCurrencyId:
        string | null =
          null;

      let exchangeRate =
        body.data.exchangeRateToScenario
        ?? null;


      if (
        body.data.calculationMethod
        === "fixed_amount"
      ) {

        sourceCurrencyId =
          await resolveId(
            "currencies",
            "code = $1 AND is_active = TRUE",
            body.data.sourceCurrencyCode
          );


        if (!sourceCurrencyId) {

          reply.code(404);

          return {
            ok: false,
            error:
              "component_source_currency_not_found"
          };

        }


        if (
          sourceCurrencyId
          === scenario.rows[0].scenarioCurrencyId
        ) {

          exchangeRate =
            1;

        }
        else if (
          exchangeRate == null
        ) {

          reply.code(400);

          return {
            ok: false,
            error:
              "component_exchange_rate_required"
          };

        }

      }


      try {

        const result =
          await database.query(
            `
            INSERT INTO landed_cost_components (
                scenario_id,
                component_type_code,
                sequence,
                description,
                included_in_offer,
                calculation_method,
                source_amount,
                source_currency_id,
                exchange_rate_to_scenario,
                percentage_rate,
                taxable_base_scenario_currency,
                notes,
                source_type,
                canonical_source_record_id,
                confidence,
                metadata
            )
            VALUES (
                $1::uuid,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8::uuid,
                $9,
                $10,
                $11,
                $12,
                $13,
                $14::uuid,
                $15,
                $16::jsonb
            )
            RETURNING id::text
            `,
            [
              params.data.id,
              body.data.componentTypeCode,
              body.data.sequence
                ?? type.rows[0].defaultSequence,
              body.data.description
                ?? null,
              body.data.includedInOffer,
              body.data.calculationMethod,
              body.data.sourceAmount
                ?? null,
              sourceCurrencyId,
              exchangeRate,
              body.data.percentageRate
                ?? null,
              body.data.taxableBaseScenarioCurrency
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
          await loadScenario(
            params.data.id
          );


        reply.code(201);

        return {
          ok: true,
          componentId:
            result.rows[0].id,
          scenario:
            loaded
        };

      }
      catch (error) {

        request.log.error(
          error
        );

        reply.code(409);

        return {
          ok: false,
          error:
            "landed_cost_component_invalid",

          message:
            (
              error as Error
            ).message
        };

      }

    }
  );

}
