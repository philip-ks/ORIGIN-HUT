import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


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


const booleanQuerySchema =
  z.enum([
    "true",
    "false"
  ])
    .default("false")
    .transform(
      value =>
        value === "true"
    );


const valueMetricSchema =
  z.enum([
    "trade_value",
    "fob_value",
    "cif_value"
  ])
    .default("trade_value");


const commonQueryFields = {

  reporterCountry:
    countryIso2Schema,

  flowDirection:
    normalizedCodeSchema,

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

  valueMetric:
    valueMetricSchema,

  status:
    normalizedCodeSchema
      .default("published"),

  isProvisional:
    booleanQuerySchema

};


function validatePeriodWindow(
  value: {
    periodFrom?: string;
    periodTo?: string;
  },
  ctx: z.RefinementCtx
) {

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


const marketsQuerySchema =
  z.object({

    ...commonQueryFields,

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

  })
  .superRefine(
    validatePeriodWindow
  );


const timeSeriesQuerySchema =
  z.object({

    ...commonQueryFields,

    partnerCountry:
      countryIso2Schema
        .optional(),

    limit: z.coerce
      .number()
      .int()
      .min(1)
      .max(500)
      .default(120),

    offset: z.coerce
      .number()
      .int()
      .min(0)
      .default(0)

  })
  .superRefine(
    validatePeriodWindow
  );


const marketGrowthQuerySchema =
  z.object({

    reporterCountry:
      countryIso2Schema,

    flowDirection:
      normalizedCodeSchema,

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
      currencyCodeSchema,

    valueMetric:
      valueMetricSchema,

    periodType:
      normalizedCodeSchema,

    status:
      normalizedCodeSchema
        .default("published"),

    isProvisional:
      booleanQuerySchema,

    limit: z.coerce
      .number()
      .int()
      .min(1)
      .max(100)
      .default(25)

  })
  .superRefine(
    validatePeriodWindow
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


function metricExpression(
  metric:
    "trade_value"
    | "fob_value"
    | "cif_value"
) {

  switch (metric) {

    case "fob_value":
      return "tf.fob_value";

    case "cif_value":
      return "tf.cif_value";

    default:
      return "tf.trade_value";

  }

}


export async function marketIntelligenceRoutes(
  app: FastifyInstance
) {


  // ==========================================================
  // PARTNER MARKET RANKING
  //
  // Ranking and market share are calculated independently
  // inside each currency bucket.
  //
  // Reporter / partner semantics are deliberately preserved.
  // A partner is not automatically treated as physical origin
  // or destination.
  // ==========================================================

  app.get(
    "/api/intelligence/trade-flows/markets",
    async (
      request,
      reply
    ) => {

      const parsed =
        marketsQuerySchema.safeParse(
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
        flowDirection,
        hsCode,
        hsNomenclature,
        periodFrom,
        periodTo,
        currency,
        valueMetric,
        status,
        isProvisional,
        limit,
        offset
      } = parsed.data;


      const metric =
        metricExpression(
          valueMetric
        );


      const result =
        await database.query(
          `
            WITH aggregated AS (

              SELECT
                partner.id::text
                  AS "marketId",

                partner.iso2
                  AS "marketIso2",

                partner.iso3
                  AS "marketIso3",

                partner.name
                  AS "marketName",

                curr.code
                  AS currency,

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

                SUM(
                  ${metric}
                )::double precision
                  AS value,

                SUM(
                  tf.net_weight_kg
                )::double precision
                  AS "netWeightKg",

                SUM(
                  tf.gross_weight_kg
                )::double precision
                  AS "grossWeightKg"

              FROM trade_flows tf

              JOIN countries reporter
                ON reporter.id =
                   tf.reporter_country_id

              JOIN countries partner
                ON partner.id =
                   tf.partner_country_id

              LEFT JOIN hs_codes hs
                ON hs.id =
                   tf.hs_code_id

              LEFT JOIN currencies curr
                ON curr.id =
                   tf.currency_id

              WHERE
                reporter.iso2 =
                $1

                AND tf.flow_direction =
                    $2

                AND (
                  $4::text IS NULL

                  OR (
                    hs.nomenclature =
                    $3

                    AND hs.code LIKE
                        $4 || '%'
                  )
                )

                AND (
                  $5::date IS NULL
                  OR tf.period_end >=
                     $5::date
                )

                AND (
                  $6::date IS NULL
                  OR tf.period_start <=
                     $6::date
                )

                AND (
                  $7::text IS NULL
                  OR curr.code =
                     $7
                )

                AND tf.status =
                    $8

                AND tf.is_provisional =
                    $9

                AND ${metric}
                    IS NOT NULL

              GROUP BY
                partner.id,
                partner.iso2,
                partner.iso3,
                partner.name,
                curr.code

            ),

            ranked AS (

              SELECT
                aggregated.*,

                ROW_NUMBER() OVER (
                  PARTITION BY currency
                  ORDER BY
                    value DESC,
                    "marketIso2"
                )::int
                  AS rank,

                (
                  100.0
                  * value
                  / NULLIF(
                      SUM(value) OVER (
                        PARTITION BY currency
                      ),
                      0
                    )
                )::double precision
                  AS "marketSharePercent"

              FROM aggregated

            )

            SELECT
              ranked.*,

              COUNT(*) OVER()::int
                AS "totalCount"

            FROM ranked

            ORDER BY
              currency,
              rank

            LIMIT $10
            OFFSET $11
          `,
          [
            reporterCountry,
            flowDirection,
            hsNomenclature,
            hsCode ?? null,
            periodFrom ?? null,
            periodTo ?? null,
            currency ?? null,
            status,
            isProvisional,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const markets =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...market
            } = row;

            return market;

          }
        );


      return {

        ok: true,

        methodology: {

          dimension:
            "partner_country",

          valueMetric,

          ranking:
            "descending_value_within_currency",

          share:
            "share_of_selected_value_metric_within_currency",

          warning:
            "Reporter/partner statistical trade relationships are not automatically physical origin/destination routes or identified company transactions."

        },

        filters: {

          reporterCountry,

          flowDirection,

          hsCode:
            hsCode ?? null,

          hsNomenclature,

          periodFrom:
            periodFrom ?? null,

          periodTo:
            periodTo ?? null,

          currency:
            currency ?? null,

          status,

          isProvisional

        },

        markets,

        pagination: {

          total,

          limit,

          offset

        }

      };

    }
  );


  // ==========================================================
  // TRADE VALUE TIME SERIES
  //
  // Each period remains separate.
  // Currency remains a grouping dimension.
  // ==========================================================

  app.get(
    "/api/intelligence/trade-flows/timeseries",
    async (
      request,
      reply
    ) => {

      const parsed =
        timeSeriesQuerySchema.safeParse(
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
        valueMetric,
        status,
        isProvisional,
        limit,
        offset
      } = parsed.data;


      const metric =
        metricExpression(
          valueMetric
        );


      const result =
        await database.query(
          `
            SELECT
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

              curr.code
                AS currency,

              COUNT(*)::int
                AS facts,

              SUM(
                ${metric}
              )::double precision
                AS value,

              SUM(
                tf.net_weight_kg
              )::double precision
                AS "netWeightKg",

              SUM(
                tf.gross_weight_kg
              )::double precision
                AS "grossWeightKg",

              COUNT(*) OVER()::int
                AS "totalCount"

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

            WHERE
              reporter.iso2 =
              $1

              AND (
                $2::text IS NULL
                OR partner.iso2 =
                   $2
              )

              AND tf.flow_direction =
                  $3

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

              AND tf.status =
                  $9

              AND tf.is_provisional =
                  $10

              AND ${metric}
                  IS NOT NULL

            GROUP BY
              tf.period_start,
              tf.period_end,
              tf.period_type,
              curr.code

            ORDER BY
              tf.period_start,
              tf.period_end,
              curr.code

            LIMIT $11
            OFFSET $12
          `,
          [
            reporterCountry,
            partnerCountry ?? null,
            flowDirection,
            hsNomenclature,
            hsCode ?? null,
            periodFrom ?? null,
            periodTo ?? null,
            currency ?? null,
            status,
            isProvisional,
            limit,
            offset
          ]
        );


      const total =
        result.rows[0]?.totalCount
        ?? 0;


      const periods =
        result.rows.map(
          row => {

            const {
              totalCount: _totalCount,
              ...period
            } = row;

            return period;

          }
        );


      return {

        ok: true,

        methodology: {

          valueMetric,

          grouping:
            "period_and_currency",

          warning:
            "Values in different currencies are intentionally not combined."

        },

        filters: {

          reporterCountry,

          partnerCountry:
            partnerCountry ?? null,

          flowDirection,

          hsCode:
            hsCode ?? null,

          hsNomenclature,

          periodFrom:
            periodFrom ?? null,

          periodTo:
            periodTo ?? null,

          currency:
            currency ?? null,

          status,

          isProvisional

        },

        periods,

        pagination: {

          total,

          limit,

          offset

        }

      };

    }
  );


  // ==========================================================
  // MARKET GROWTH
  //
  // Uses the latest two observed periods for each partner
  // market inside the requested window.
  //
  // Currency and period type are REQUIRED so that growth is
  // only calculated between comparable observations.
  // ==========================================================

  app.get(
    "/api/intelligence/trade-flows/market-growth",
    async (
      request,
      reply
    ) => {

      const parsed =
        marketGrowthQuerySchema.safeParse(
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
        flowDirection,
        hsCode,
        hsNomenclature,
        periodFrom,
        periodTo,
        currency,
        valueMetric,
        periodType,
        status,
        isProvisional,
        limit
      } = parsed.data;


      const metric =
        metricExpression(
          valueMetric
        );


      const result =
        await database.query(
          `
            WITH period_values AS (

              SELECT
                partner.id::text
                  AS "marketId",

                partner.iso2
                  AS "marketIso2",

                partner.iso3
                  AS "marketIso3",

                partner.name
                  AS "marketName",

                tf.period_start
                  AS period_start,

                tf.period_end
                  AS period_end,

                SUM(
                  ${metric}
                )::double precision
                  AS value,

                COUNT(*)::int
                  AS facts

              FROM trade_flows tf

              JOIN countries reporter
                ON reporter.id =
                   tf.reporter_country_id

              JOIN countries partner
                ON partner.id =
                   tf.partner_country_id

              LEFT JOIN hs_codes hs
                ON hs.id =
                   tf.hs_code_id

              JOIN currencies curr
                ON curr.id =
                   tf.currency_id

              WHERE
                reporter.iso2 =
                $1

                AND tf.flow_direction =
                    $2

                AND (
                  $4::text IS NULL

                  OR (
                    hs.nomenclature =
                    $3

                    AND hs.code LIKE
                        $4 || '%'
                  )
                )

                AND (
                  $5::date IS NULL
                  OR tf.period_end >=
                     $5::date
                )

                AND (
                  $6::date IS NULL
                  OR tf.period_start <=
                     $6::date
                )

                AND curr.code =
                    $7

                AND tf.period_type =
                    $8

                AND tf.status =
                    $9

                AND tf.is_provisional =
                    $10

                AND ${metric}
                    IS NOT NULL

              GROUP BY
                partner.id,
                partner.iso2,
                partner.iso3,
                partner.name,
                tf.period_start,
                tf.period_end

            ),

            ranked_periods AS (

              SELECT
                period_values.*,

                ROW_NUMBER() OVER (
                  PARTITION BY "marketId"
                  ORDER BY
                    period_start DESC,
                    period_end DESC
                )::int
                  AS period_rank

              FROM period_values

            ),

            paired AS (

              SELECT
                "marketId",
                "marketIso2",
                "marketIso3",
                "marketName",

                MAX(period_start)
                  FILTER (
                    WHERE period_rank = 1
                  )
                    AS current_period_start,

                MAX(period_end)
                  FILTER (
                    WHERE period_rank = 1
                  )
                    AS current_period_end,

                MAX(value)
                  FILTER (
                    WHERE period_rank = 1
                  )
                    AS current_value,

                MAX(facts)
                  FILTER (
                    WHERE period_rank = 1
                  )
                    AS current_facts,

                MAX(period_start)
                  FILTER (
                    WHERE period_rank = 2
                  )
                    AS previous_period_start,

                MAX(period_end)
                  FILTER (
                    WHERE period_rank = 2
                  )
                    AS previous_period_end,

                MAX(value)
                  FILTER (
                    WHERE period_rank = 2
                  )
                    AS previous_value,

                MAX(facts)
                  FILTER (
                    WHERE period_rank = 2
                  )
                    AS previous_facts

              FROM ranked_periods

              WHERE period_rank <= 2

              GROUP BY
                "marketId",
                "marketIso2",
                "marketIso3",
                "marketName"

            )

            SELECT
              "marketId",
              "marketIso2",
              "marketIso3",
              "marketName",

              TO_CHAR(
                previous_period_start,
                'YYYY-MM-DD'
              ) AS "previousPeriodStart",

              TO_CHAR(
                previous_period_end,
                'YYYY-MM-DD'
              ) AS "previousPeriodEnd",

              previous_value
                AS "previousValue",

              previous_facts
                AS "previousFacts",

              TO_CHAR(
                current_period_start,
                'YYYY-MM-DD'
              ) AS "currentPeriodStart",

              TO_CHAR(
                current_period_end,
                'YYYY-MM-DD'
              ) AS "currentPeriodEnd",

              current_value
                AS "currentValue",

              current_facts
                AS "currentFacts",

              (
                current_value
                - previous_value
              )::double precision
                AS "absoluteChange",

              CASE
                WHEN previous_value = 0
                THEN NULL

                ELSE (
                  100.0
                  * (
                      current_value
                      - previous_value
                    )
                  / previous_value
                )::double precision
              END
                AS "growthPercent"

            FROM paired

            WHERE previous_value
                  IS NOT NULL

            ORDER BY
              "growthPercent" DESC NULLS LAST,
              "currentValue" DESC,
              "marketIso2"

            LIMIT $11
          `,
          [
            reporterCountry,
            flowDirection,
            hsNomenclature,
            hsCode ?? null,
            periodFrom ?? null,
            periodTo ?? null,
            currency,
            periodType,
            status,
            isProvisional,
            limit
          ]
        );


      return {

        ok: true,

        methodology: {

          comparison:
            "latest_two_observed_periods_per_partner_market",

          valueMetric,

          currency,

          periodType,

          warning:
            "Growth is descriptive of the selected trade observations and does not by itself establish market attractiveness, demand causation or future performance."

        },

        filters: {

          reporterCountry,

          flowDirection,

          hsCode:
            hsCode ?? null,

          hsNomenclature,

          periodFrom:
            periodFrom ?? null,

          periodTo:
            periodTo ?? null,

          currency,

          periodType,

          status,

          isProvisional

        },

        markets:
          result.rows

      };

    }
  );

}
