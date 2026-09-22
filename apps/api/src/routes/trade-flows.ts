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


function isValidIsoDate(
  value: string
) {

  const match =
    /^(\d{4})-(\d{2})-(\d{2})$/.exec(
      value
    );


  if (!match) {
    return false;
  }


  const year =
    Number(match[1]);

  const month =
    Number(match[2]);

  const day =
    Number(match[3]);


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
    .trim()
    .refine(
      isValidIsoDate,
      {
        message:
          "Date must be a valid YYYY-MM-DD calendar date."
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


const currencyCodeSchema =
  z.string()
    .trim()
    .length(3)
    .transform(
      value =>
        value.toUpperCase()
    )
    .refine(
      value =>
        /^[A-Z]{3}$/.test(
          value
        ),
      {
        message:
          "Currency must be a 3-letter ISO 4217 code."
      }
    );


const unlocodeSchema =
  z.string()
    .trim()
    .transform(
      value =>
        value.toUpperCase()
    )
    .refine(
      value =>
        /^[A-Z]{2}[A-Z0-9]{3}$/.test(
          value
        ),
      {
        message:
          "UN/LOCODE must contain a 2-letter country code and 3-character location code."
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
        /^[a-z0-9][a-z0-9_]*$/.test(
          value
        ),
      {
        message:
          "Value may contain letters, numbers and underscores."
      }
    );


const optionalMeasureSchema =
  z.number()
    .finite()
    .nonnegative()
    .nullable()
    .optional();


const tradeFlowParamsSchema =
  z.object({

    id: z
      .string()
      .uuid()

  });


const tradeFlowListQuerySchema =
  z.object({

    reporterCountry:
      countryIso2Schema
        .optional(),

    partnerCountry:
      countryIso2Schema
        .optional(),

    flowDirection:
      normalizedCodeSchema
        .optional(),

    hsCode:
      hsCodeSchema
        .optional(),

    hsNomenclature:
      nomenclatureSchema
        .default("HS2022"),

    periodFrom:
      isoDateSchema
        .optional(),

    periodTo:
      isoDateSchema
        .optional(),

    currency:
      currencyCodeSchema
        .optional(),

    status:
      normalizedCodeSchema
        .optional(),

    isProvisional: z
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

  })
  .superRefine(
    (
      value,
      ctx
    ) => {

      if (
        value.periodFrom
        && value.periodTo
        && value.periodTo < value.periodFrom
      ) {

        ctx.addIssue({

          code:
            "custom",

          path:
            [
              "periodTo"
            ],

          message:
            "periodTo cannot be earlier than periodFrom."

        });

      }

    }
  );


const tradeFlowSummaryQuerySchema =
  z.object({

    reporterCountry:
      countryIso2Schema
        .optional(),

    partnerCountry:
      countryIso2Schema
        .optional(),

    flowDirection:
      normalizedCodeSchema
        .optional(),

    hsCode:
      hsCodeSchema
        .optional(),

    hsNomenclature:
      nomenclatureSchema
        .default("HS2022"),

    periodFrom:
      isoDateSchema
        .optional(),

    periodTo:
      isoDateSchema
        .optional(),

    currency:
      currencyCodeSchema
        .optional(),

    status:
      normalizedCodeSchema
        .optional(),

    isProvisional: z
      .enum([
        "true",
        "false"
      ])
      .transform(
        value =>
          value === "true"
      )
      .optional()

  })
  .superRefine(
    (
      value,
      ctx
    ) => {

      if (
        value.periodFrom
        && value.periodTo
        && value.periodTo < value.periodFrom
      ) {

        ctx.addIssue({

          code:
            "custom",

          path:
            [
              "periodTo"
            ],

          message:
            "periodTo cannot be earlier than periodFrom."

        });

      }

    }
  );


const createTradeFlowSchema =
  z.object({

    flowDirection:
      normalizedCodeSchema,

    reporterCountry:
      countryIso2Schema,

    partnerCountry:
      countryIso2Schema
        .nullable()
        .optional(),

    originCountry:
      countryIso2Schema
        .nullable()
        .optional(),

    destinationCountry:
      countryIso2Schema
        .nullable()
        .optional(),

    originLocation:
      unlocodeSchema
        .nullable()
        .optional(),

    destinationLocation:
      unlocodeSchema
        .nullable()
        .optional(),

    hsCode:
      hsCodeSchema
        .nullable()
        .optional(),

    hsNomenclature:
      nomenclatureSchema
        .default("HS2022"),

    productId: z
      .string()
      .uuid()
      .nullable()
      .optional(),

    periodStart:
      isoDateSchema,

    periodEnd:
      isoDateSchema,

    periodType:
      normalizedCodeSchema,

    quantity:
      optionalMeasureSchema,

    quantityUnit: z
      .string()
      .trim()
      .min(1)
      .max(32)
      .nullable()
      .optional(),

    netWeightKg:
      optionalMeasureSchema,

    grossWeightKg:
      optionalMeasureSchema,

    tradeValue:
      optionalMeasureSchema,

    fobValue:
      optionalMeasureSchema,

    cifValue:
      optionalMeasureSchema,

    currency:
      currencyCodeSchema
        .nullable()
        .optional(),

    transportMode:
      normalizedCodeSchema
        .nullable()
        .optional(),

    customsProcedure:
      normalizedCodeSchema
        .nullable()
        .optional(),

    status:
      normalizedCodeSchema
        .default("published"),

    isProvisional: z
      .boolean()
      .default(false),

    canonicalSourceRecordId: z
      .string()
      .uuid()
      .nullable()
      .optional(),

    metadata:
      jsonObjectSchema
        .default({})

  })
  .superRefine(
    (
      value,
      ctx
    ) => {

      if (
        value.periodEnd
        < value.periodStart
      ) {

        ctx.addIssue({

          code:
            "custom",

          path:
            [
              "periodEnd"
            ],

          message:
            "periodEnd cannot be earlier than periodStart."

        });

      }


      const hasMeasure =
        value.quantity != null
        || value.netWeightKg != null
        || value.grossWeightKg != null
        || value.tradeValue != null
        || value.fobValue != null
        || value.cifValue != null;


      if (!hasMeasure) {

        ctx.addIssue({

          code:
            "custom",

          path:
            [
              "quantity"
            ],

          message:
            "At least one measurable trade fact is required."

        });

      }


      const hasMonetaryValue =
        value.tradeValue != null
        || value.fobValue != null
        || value.cifValue != null;


      if (
        hasMonetaryValue
        && !value.currency
      ) {

        ctx.addIssue({

          code:
            "custom",

          path:
            [
              "currency"
            ],

          message:
            "Currency is required when a monetary value is supplied."

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


async function resolveCurrencyId(
  code: string
) {

  const result =
    await database.query(
      `
        SELECT
          id::text
        FROM currencies
        WHERE
          code = $1
          AND is_active = TRUE
        LIMIT 1
      `,
      [
        code
      ]
    );


  return (
    result.rows[0]?.id
    ?? null
  );

}


async function resolveHsCodeId(
  nomenclature: string,
  code: string
) {

  const result =
    await database.query(
      `
        SELECT
          id::text
        FROM hs_codes
        WHERE
          nomenclature = $1
          AND code = $2
        LIMIT 1
      `,
      [
        nomenclature,
        code
      ]
    );


  return (
    result.rows[0]?.id
    ?? null
  );

}


async function resolveTradeLocation(
  unlocode: string
) {

  const result =
    await database.query(
      `
        SELECT
          tl.id::text
            AS id,

          tl.country_id::text
            AS "countryId",

          c.iso2
            AS "countryIso2"

        FROM trade_locations tl

        LEFT JOIN countries c
          ON c.id =
             tl.country_id

        WHERE tl.unlocode = $1

        LIMIT 1
      `,
      [
        unlocode
      ]
    );


  return (
    result.rows[0]
    ?? null
  );

}


async function productExists(
  id: string
) {

  const result =
    await database.query(
      `
        SELECT EXISTS (
          SELECT 1
          FROM products
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


async function sourceRecordExists(
  id: string
) {

  const result =
    await database.query(
      `
        SELECT EXISTS (
          SELECT 1
          FROM source_records
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


async function loadTradeFlow(
  id: string
) {

  const result =
    await database.query(
      `
        SELECT
          tf.id::text
            AS id,

          tf.flow_direction
            AS "flowDirection",


          jsonb_build_object(
            'id',
            reporter.id::text,
            'iso2',
            reporter.iso2,
            'iso3',
            reporter.iso3,
            'name',
            reporter.name
          ) AS "reporterCountry",


          CASE
            WHEN partner.id IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'id',
              partner.id::text,
              'iso2',
              partner.iso2,
              'iso3',
              partner.iso3,
              'name',
              partner.name
            )
          END AS "partnerCountry",


          CASE
            WHEN origin_country.id IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'id',
              origin_country.id::text,
              'iso2',
              origin_country.iso2,
              'iso3',
              origin_country.iso3,
              'name',
              origin_country.name
            )
          END AS "originCountry",


          CASE
            WHEN destination_country.id IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'id',
              destination_country.id::text,
              'iso2',
              destination_country.iso2,
              'iso3',
              destination_country.iso3,
              'name',
              destination_country.name
            )
          END AS "destinationCountry",


          CASE
            WHEN origin_location.id IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'id',
              origin_location.id::text,
              'unlocode',
              origin_location.unlocode,
              'name',
              origin_location.name,
              'countryIso2',
              origin_location_country.iso2
            )
          END AS "originLocation",


          CASE
            WHEN destination_location.id IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'id',
              destination_location.id::text,
              'unlocode',
              destination_location.unlocode,
              'name',
              destination_location.name,
              'countryIso2',
              destination_location_country.iso2
            )
          END AS "destinationLocation",


          CASE
            WHEN hs.id IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'id',
              hs.id::text,
              'nomenclature',
              hs.nomenclature,
              'code',
              hs.code,
              'description',
              hs.description,
              'level',
              hs.level,
              'standardUnit',
              hs.standard_unit
            )
          END AS "hsCode",


          CASE
            WHEN product.id IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'id',
              product.id::text,
              'name',
              product.name,
              'brand',
              product.brand,
              'sku',
              product.sku
            )
          END AS product,


          TO_CHAR(
            tf.period_start,
            'YYYY-MM-DD'
          ) AS "periodStart",

          TO_CHAR(
            tf.period_end,
            'YYYY-MM-DD'
          ) AS "periodEnd",

          tf.period_type
            AS "periodType",


          tf.quantity::double precision
            AS quantity,

          tf.quantity_unit
            AS "quantityUnit",

          tf.net_weight_kg::double precision
            AS "netWeightKg",

          tf.gross_weight_kg::double precision
            AS "grossWeightKg",

          tf.trade_value::double precision
            AS "tradeValue",

          tf.fob_value::double precision
            AS "fobValue",

          tf.cif_value::double precision
            AS "cifValue",


          CASE
            WHEN currency.id IS NULL
            THEN NULL
            ELSE jsonb_build_object(
              'id',
              currency.id::text,
              'code',
              currency.code
            )
          END AS currency,


          tf.transport_mode
            AS "transportMode",

          tf.customs_procedure
            AS "customsProcedure",

          tf.status,

          tf.is_provisional
            AS "isProvisional",

          tf.canonical_source_record_id::text
            AS "canonicalSourceRecordId",

          tf.metadata,

          tf.created_at
            AS "createdAt",

          tf.updated_at
            AS "updatedAt"


        FROM trade_flows tf


        JOIN countries reporter
          ON reporter.id =
             tf.reporter_country_id


        LEFT JOIN countries partner
          ON partner.id =
             tf.partner_country_id


        LEFT JOIN countries origin_country
          ON origin_country.id =
             tf.origin_country_id


        LEFT JOIN countries destination_country
          ON destination_country.id =
             tf.destination_country_id


        LEFT JOIN trade_locations origin_location
          ON origin_location.id =
             tf.origin_location_id


        LEFT JOIN countries origin_location_country
          ON origin_location_country.id =
             origin_location.country_id


        LEFT JOIN trade_locations destination_location
          ON destination_location.id =
             tf.destination_location_id


        LEFT JOIN countries destination_location_country
          ON destination_location_country.id =
             destination_location.country_id


        LEFT JOIN hs_codes hs
          ON hs.id =
             tf.hs_code_id


        LEFT JOIN products product
          ON product.id =
             tf.product_id


        LEFT JOIN currencies currency
          ON currency.id =
             tf.currency_id


        WHERE tf.id =
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


export async function tradeFlowRoutes(
  app: FastifyInstance
) {


  // ==========================================================
  // TRADE FLOW LIST / SEARCH
  // ==========================================================

  app.get(
    "/api/trade-flows",
    async (
      request,
      reply
    ) => {

      const parsed =
        tradeFlowListQuerySchema.safeParse(
          request.query
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const {
        reporterCountry,
        partnerCountry,
        flowDirection,
        hsCode,
        hsNomenclature,
        periodFrom,
        periodTo,
        currency,
        status,
        isProvisional,
        limit,
        offset
      } = parsed.data;


      const result =
        await database.query(
          `
            SELECT
              tf.id::text
                AS id,

              tf.flow_direction
                AS "flowDirection",

              reporter.iso2
                AS "reporterCountry",

              reporter.name
                AS "reporterCountryName",

              partner.iso2
                AS "partnerCountry",

              partner.name
                AS "partnerCountryName",

              origin_country.iso2
                AS "originCountry",

              destination_country.iso2
                AS "destinationCountry",

              origin_location.unlocode
                AS "originLocation",

              destination_location.unlocode
                AS "destinationLocation",

              hs.nomenclature
                AS "hsNomenclature",

              hs.code
                AS "hsCode",

              hs.description
                AS "hsDescription",

              product.id::text
                AS "productId",

              product.name
                AS "productName",

              TO_CHAR(
                tf.period_start,
                'YYYY-MM-DD'
              ) AS "periodStart",

              TO_CHAR(
                tf.period_end,
                'YYYY-MM-DD'
              ) AS "periodEnd",

              tf.period_type
                AS "periodType",

              tf.quantity::double precision
                AS quantity,

              tf.quantity_unit
                AS "quantityUnit",

              tf.net_weight_kg::double precision
                AS "netWeightKg",

              tf.gross_weight_kg::double precision
                AS "grossWeightKg",

              tf.trade_value::double precision
                AS "tradeValue",

              tf.fob_value::double precision
                AS "fobValue",

              tf.cif_value::double precision
                AS "cifValue",

              curr.code
                AS currency,

              tf.transport_mode
                AS "transportMode",

              tf.customs_procedure
                AS "customsProcedure",

              tf.status,

              tf.is_provisional
                AS "isProvisional",

              tf.canonical_source_record_id::text
                AS "canonicalSourceRecordId",

              tf.metadata,

              tf.created_at
                AS "createdAt",

              tf.updated_at
                AS "updatedAt",

              COUNT(*) OVER()::int
                AS "totalCount"


            FROM trade_flows tf


            JOIN countries reporter
              ON reporter.id =
                 tf.reporter_country_id


            LEFT JOIN countries partner
              ON partner.id =
                 tf.partner_country_id


            LEFT JOIN countries origin_country
              ON origin_country.id =
                 tf.origin_country_id


            LEFT JOIN countries destination_country
              ON destination_country.id =
                 tf.destination_country_id


            LEFT JOIN trade_locations origin_location
              ON origin_location.id =
                 tf.origin_location_id


            LEFT JOIN trade_locations destination_location
              ON destination_location.id =
                 tf.destination_location_id


            LEFT JOIN hs_codes hs
              ON hs.id =
                 tf.hs_code_id


            LEFT JOIN products product
              ON product.id =
                 tf.product_id


            LEFT JOIN currencies curr
              ON curr.id =
                 tf.currency_id


            WHERE
              (
                $1::text IS NULL
                OR reporter.iso2 =
                   $1
              )

              AND (
                $2::text IS NULL
                OR partner.iso2 =
                   $2
              )

              AND (
                $3::text IS NULL
                OR tf.flow_direction =
                   $3
              )

              AND (
                $5::text IS NULL
                OR (
                  hs.nomenclature =
                  $4

                  AND hs.code LIKE
                      $5 || '%'
                )
              )

              AND (
                $6::date IS NULL
                OR tf.period_end >=
                   $6::date
              )

              AND (
                $7::date IS NULL
                OR tf.period_start <=
                   $7::date
              )

              AND (
                $8::text IS NULL
                OR curr.code =
                   $8
              )

              AND (
                $9::text IS NULL
                OR tf.status =
                   $9
              )

              AND (
                $10::boolean IS NULL
                OR tf.is_provisional =
                   $10::boolean
              )


            ORDER BY
              tf.period_start DESC,
              tf.created_at DESC


            LIMIT $11
            OFFSET $12
          `,
          [
            reporterCountry ?? null,
            partnerCountry ?? null,
            flowDirection ?? null,
            hsNomenclature,
            hsCode ?? null,
            periodFrom ?? null,
            periodTo ?? null,
            currency ?? null,
            status ?? null,
            isProvisional ?? null,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const tradeFlows =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...tradeFlow
            } = row;

            return tradeFlow;

          }
        );


      return {

        ok: true,

        tradeFlows,

        pagination: {

          total,

          limit,

          offset

        }

      };

    }
  );


  // ==========================================================
  // CREATE TRADE FLOW FACT
  // ==========================================================

  app.post(
    "/api/trade-flows",
    async (
      request,
      reply
    ) => {

      const parsed =
        createTradeFlowSchema.safeParse(
          request.body
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const body =
        parsed.data;


      const reporterCountryId =
        await resolveCountryId(
          body.reporterCountry
        );


      if (!reporterCountryId) {

        reply.code(404);

        return {

          ok: false,

          error:
            "reporter_country_not_found",

          country:
            body.reporterCountry

        };

      }


      let partnerCountryId:
        string | null =
          null;


      if (body.partnerCountry) {

        partnerCountryId =
          await resolveCountryId(
            body.partnerCountry
          );


        if (!partnerCountryId) {

          reply.code(404);

          return {

            ok: false,

            error:
              "partner_country_not_found",

            country:
              body.partnerCountry

          };

        }

      }


      let originCountryId:
        string | null =
          null;


      if (body.originCountry) {

        originCountryId =
          await resolveCountryId(
            body.originCountry
          );


        if (!originCountryId) {

          reply.code(404);

          return {

            ok: false,

            error:
              "origin_country_not_found",

            country:
              body.originCountry

          };

        }

      }


      let destinationCountryId:
        string | null =
          null;


      if (body.destinationCountry) {

        destinationCountryId =
          await resolveCountryId(
            body.destinationCountry
          );


        if (!destinationCountryId) {

          reply.code(404);

          return {

            ok: false,

            error:
              "destination_country_not_found",

            country:
              body.destinationCountry

          };

        }

      }


      let originLocationId:
        string | null =
          null;


      if (body.originLocation) {

        const location =
          await resolveTradeLocation(
            body.originLocation
          );


        if (!location) {

          reply.code(404);

          return {

            ok: false,

            error:
              "origin_location_not_found",

            unlocode:
              body.originLocation

          };

        }


        if (
          originCountryId
          && location.countryId
          && originCountryId
             !== location.countryId
        ) {

          reply.code(400);

          return {

            ok: false,

            error:
              "origin_location_country_mismatch",

            country:
              body.originCountry,

            location:
              body.originLocation,

            locationCountry:
              location.countryIso2

          };

        }


        originLocationId =
          location.id;


        if (
          !originCountryId
          && location.countryId
        ) {

          originCountryId =
            location.countryId;

        }

      }


      let destinationLocationId:
        string | null =
          null;


      if (body.destinationLocation) {

        const location =
          await resolveTradeLocation(
            body.destinationLocation
          );


        if (!location) {

          reply.code(404);

          return {

            ok: false,

            error:
              "destination_location_not_found",

            unlocode:
              body.destinationLocation

          };

        }


        if (
          destinationCountryId
          && location.countryId
          && destinationCountryId
             !== location.countryId
        ) {

          reply.code(400);

          return {

            ok: false,

            error:
              "destination_location_country_mismatch",

            country:
              body.destinationCountry,

            location:
              body.destinationLocation,

            locationCountry:
              location.countryIso2

          };

        }


        destinationLocationId =
          location.id;


        if (
          !destinationCountryId
          && location.countryId
        ) {

          destinationCountryId =
            location.countryId;

        }

      }


      let hsCodeId:
        string | null =
          null;


      if (body.hsCode) {

        hsCodeId =
          await resolveHsCodeId(
            body.hsNomenclature,
            body.hsCode
          );


        if (!hsCodeId) {

          reply.code(404);

          return {

            ok: false,

            error:
              "hs_code_not_found",

            nomenclature:
              body.hsNomenclature,

            hsCode:
              body.hsCode

          };

        }

      }


      if (
        body.productId
        && !await productExists(
          body.productId
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "product_not_found",

          productId:
            body.productId

        };

      }


      let currencyId:
        string | null =
          null;


      if (body.currency) {

        currencyId =
          await resolveCurrencyId(
            body.currency
          );


        if (!currencyId) {

          reply.code(404);

          return {

            ok: false,

            error:
              "currency_not_found",

            currency:
              body.currency

          };

        }

      }


      if (
        body.canonicalSourceRecordId
        && !await sourceRecordExists(
          body.canonicalSourceRecordId
        )
      ) {

        reply.code(404);

        return {

          ok: false,

          error:
            "source_record_not_found",

          sourceRecordId:
            body.canonicalSourceRecordId

        };

      }


      try {

        const result =
          await database.query(
            `
              INSERT INTO trade_flows (
                  flow_direction,

                  reporter_country_id,
                  partner_country_id,

                  origin_country_id,
                  destination_country_id,

                  origin_location_id,
                  destination_location_id,

                  hs_code_id,
                  product_id,

                  period_start,
                  period_end,
                  period_type,

                  quantity,
                  quantity_unit,

                  net_weight_kg,
                  gross_weight_kg,

                  trade_value,
                  fob_value,
                  cif_value,

                  currency_id,

                  transport_mode,
                  customs_procedure,

                  status,
                  is_provisional,

                  canonical_source_record_id,

                  metadata
              )
              VALUES (
                  $1,

                  $2::uuid,
                  $3::uuid,

                  $4::uuid,
                  $5::uuid,

                  $6::uuid,
                  $7::uuid,

                  $8::uuid,
                  $9::uuid,

                  $10::date,
                  $11::date,
                  $12,

                  $13,
                  $14,

                  $15,
                  $16,

                  $17,
                  $18,
                  $19,

                  $20::uuid,

                  $21,
                  $22,

                  $23,
                  $24,

                  $25::uuid,

                  $26::jsonb
              )
              RETURNING
                  id::text
            `,
            [
              body.flowDirection,

              reporterCountryId,
              partnerCountryId,

              originCountryId,
              destinationCountryId,

              originLocationId,
              destinationLocationId,

              hsCodeId,
              body.productId ?? null,

              body.periodStart,
              body.periodEnd,
              body.periodType,

              body.quantity ?? null,
              body.quantityUnit ?? null,

              body.netWeightKg ?? null,
              body.grossWeightKg ?? null,

              body.tradeValue ?? null,
              body.fobValue ?? null,
              body.cifValue ?? null,

              currencyId,

              body.transportMode ?? null,
              body.customsProcedure ?? null,

              body.status,
              body.isProvisional,

              body.canonicalSourceRecordId
              ?? null,

              JSON.stringify(
                body.metadata
              )
            ]
          );


        const tradeFlow =
          await loadTradeFlow(
            result.rows[0].id
          );


        reply.code(201);


        return {

          ok: true,

          tradeFlow

        };

      }
      catch (error) {

        request.log.error(
          error
        );


        const pgError =
          error as {
            code?: string;
            constraint?: string;
          };


        if (
          pgError.code === "23514"
        ) {

          reply.code(400);

          return {

            ok: false,

            error:
              "invalid_trade_flow",

            constraint:
              pgError.constraint
              ?? null

          };

        }


        reply.code(500);

        return {

          ok: false,

          error:
            "trade_flow_create_failed"

        };

      }

    }
  );


  // ==========================================================
  // TRADE FLOW DETAIL
  // ==========================================================

  app.get(
    "/api/trade-flows/:id",
    async (
      request,
      reply
    ) => {

      const parsed =
        tradeFlowParamsSchema.safeParse(
          request.params
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const tradeFlow =
        await loadTradeFlow(
          parsed.data.id
        );


      if (!tradeFlow) {

        reply.code(404);

        return {

          ok: false,

          error:
            "trade_flow_not_found"

        };

      }


      return {

        ok: true,

        tradeFlow

      };

    }
  );


  // ==========================================================
  // TRADE FLOW INTELLIGENCE SUMMARY
  //
  // Monetary values are grouped by currency.
  // Quantities are grouped by unit.
  //
  // This deliberately prevents unsafe aggregation of
  // heterogeneous currencies or physical units.
  // ==========================================================

  app.get(
    "/api/intelligence/trade-flows/summary",
    async (
      request,
      reply
    ) => {

      const parsed =
        tradeFlowSummaryQuerySchema.safeParse(
          request.query
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const {
        reporterCountry,
        partnerCountry,
        flowDirection,
        hsCode,
        hsNomenclature,
        periodFrom,
        periodTo,
        currency,
        status,
        isProvisional
      } = parsed.data;


      const filterValues = [
        reporterCountry ?? null,
        partnerCountry ?? null,
        flowDirection ?? null,
        hsNomenclature,
        hsCode ?? null,
        periodFrom ?? null,
        periodTo ?? null,
        currency ?? null,
        status ?? null,
        isProvisional ?? null
      ];


      const baseFilter = `
        WHERE
          (
            $1::text IS NULL
            OR reporter.iso2 =
               $1
          )

          AND (
            $2::text IS NULL
            OR partner.iso2 =
               $2
          )

          AND (
            $3::text IS NULL
            OR tf.flow_direction =
               $3
          )

          AND (
            $5::text IS NULL
            OR (
              hs.nomenclature =
              $4

              AND hs.code LIKE
                  $5 || '%'
            )
          )

          AND (
            $6::date IS NULL
            OR tf.period_end >=
               $6::date
          )

          AND (
            $7::date IS NULL
            OR tf.period_start <=
               $7::date
          )

          AND (
            $8::text IS NULL
            OR curr.code =
               $8
          )

          AND (
            $9::text IS NULL
            OR tf.status =
               $9
          )

          AND (
            $10::boolean IS NULL
            OR tf.is_provisional =
               $10::boolean
          )
      `;


      const joins = `
        FROM trade_flows tf

        JOIN countries reporter
          ON reporter.id =
             tf.reporter_country_id

        LEFT JOIN countries partner
          ON partner.id =
             tf.partner_country_id

        LEFT JOIN hs_codes hs
          ON hs.id =
             tf.hs_code_id

        LEFT JOIN currencies curr
          ON curr.id =
             tf.currency_id
      `;


      const overviewResult =
        await database.query(
          `
            SELECT
              COUNT(*)::int
                AS facts,

              TO_CHAR(
                MIN(tf.period_start),
                'YYYY-MM-DD'
              ) AS "periodStart",

              TO_CHAR(
                MAX(tf.period_end),
                'YYYY-MM-DD'
              ) AS "periodEnd",

              COALESCE(
                SUM(
                  tf.net_weight_kg
                ),
                0
              )::double precision
                AS "netWeightKg",

              COALESCE(
                SUM(
                  tf.gross_weight_kg
                ),
                0
              )::double precision
                AS "grossWeightKg"

            ${joins}

            ${baseFilter}
          `,
          filterValues
        );


      const valueResult =
        await database.query(
          `
            SELECT
              curr.code
                AS currency,

              SUM(
                tf.trade_value
              )::double precision
                AS "tradeValue",

              SUM(
                tf.fob_value
              )::double precision
                AS "fobValue",

              SUM(
                tf.cif_value
              )::double precision
                AS "cifValue",

              COUNT(*)::int
                AS facts

            ${joins}

            ${baseFilter}

            AND (
              tf.trade_value IS NOT NULL
              OR tf.fob_value IS NOT NULL
              OR tf.cif_value IS NOT NULL
            )

            GROUP BY
              curr.code

            ORDER BY
              curr.code NULLS LAST
          `,
          filterValues
        );


      const quantityResult =
        await database.query(
          `
            SELECT
              tf.quantity_unit
                AS unit,

              SUM(
                tf.quantity
              )::double precision
                AS quantity,

              COUNT(*)::int
                AS facts

            ${joins}

            ${baseFilter}

            AND tf.quantity IS NOT NULL

            GROUP BY
              tf.quantity_unit

            ORDER BY
              tf.quantity_unit NULLS LAST
          `,
          filterValues
        );


      return {

        ok: true,

        filters: {

          reporterCountry:
            reporterCountry ?? null,

          partnerCountry:
            partnerCountry ?? null,

          flowDirection:
            flowDirection ?? null,

          hsCode:
            hsCode ?? null,

          hsNomenclature,

          periodFrom:
            periodFrom ?? null,

          periodTo:
            periodTo ?? null,

          currency:
            currency ?? null,

          status:
            status ?? null,

          isProvisional:
            isProvisional ?? null

        },

        summary: {

          ...overviewResult.rows[0],

          values:
            valueResult.rows,

          quantities:
            quantityResult.rows

        }

      };

    }
  );

}
