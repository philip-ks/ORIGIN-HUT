import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const paramsSchema =
  z.object({
    id:
      z.string()
        .uuid()
  });


export async function rfqComparisonRoutes(
  app: FastifyInstance
) {


  app.get(
    "/api/rfqs/:id/comparison",
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

        return {

          ok: false,

          error:
            "invalid_request",

          issues:
            params.error.issues.map(
              issue => ({

                path:
                  issue.path.join("."),

                message:
                  issue.message

              })
            )

        };

      }


      const rfq =
        await database.query(
          `
          SELECT
            id::text,

            rfq_reference
              AS "rfqReference"

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


      const result =
        await database.query(
          `
          SELECT
            comparison.rfq_response_id::text
              AS "rfqResponseId",

            comparison.rfq_line_id::text
              AS "rfqLineId",

            comparison.line_number
              AS "lineNumber",

            comparison.product_id::text
              AS "productId",

            product.name
              AS "productName",

            comparison.supplier_organization_id::text
              AS "supplierId",

            supplier.legal_name
              AS "supplierLegalName",

            comparison.commercial_offer_id::text
              AS "commercialOfferId",

            comparison.requested_quantity::double precision
              AS "requestedQuantity",

            comparison.requested_uom_code
              AS "requestedUomCode",

            comparison.requested_currency_code
              AS "requestedCurrencyCode",

            comparison.unit_price::double precision
              AS "offerUnitPrice",

            comparison.offer_currency_code
              AS "offerCurrencyCode",

            comparison.offer_price_uom_code
              AS "offerPriceUomCode",

            comparison.offer_price_per_requested_uom_offer_currency::double precision
              AS "offerPricePerRequestedUomOfferCurrency",

            comparison.minimum_order_quantity::double precision
              AS "minimumOrderQuantity",

            moq_uom.code
              AS "minimumOrderUomCode",

            comparison.lead_time_days
              AS "leadTimeDays",

            comparison.payment_terms
              AS "paymentTerms",

            comparison.incoterm_edition
              AS "incotermEdition",

            comparison.incoterm_code
              AS "incotermCode",

            comparison.named_place_text
              AS "namedPlaceText",

            comparison.offer_named_trade_location_unlocode
              AS "namedTradeLocationUnlocode",

            comparison.landed_cost_scenario_id::text
              AS "landedCostScenarioId",

            comparison.scenario_currency_code
              AS "scenarioCurrencyCode",

            comparison.landed_cost_target_quantity::double precision
              AS "landedCostTargetQuantity",

            comparison.landed_cost_target_uom_code
              AS "landedCostTargetUomCode",

            comparison.landed_cost_total::double precision
              AS "landedCostTotal",

            comparison.landed_cost_per_target_uom::double precision
              AS "landedCostPerTargetUom",

            comparison.landed_cost_per_requested_uom::double precision
              AS "landedCostPerRequestedUom",

            comparison.is_comparable
              AS "isComparable",

            comparison.comparison_reason
              AS "comparisonReason"

          FROM rfq_response_comparison comparison

          JOIN products product
            ON product.id =
               comparison.product_id

          JOIN organizations supplier
            ON supplier.id =
               comparison.supplier_organization_id

          LEFT JOIN units_of_measure moq_uom
            ON moq_uom.id =
               comparison.minimum_order_uom_id

          WHERE comparison.rfq_id =
                $1::uuid

          ORDER BY
            comparison.line_number,
            comparison.is_comparable DESC,
            comparison.landed_cost_per_requested_uom
                ASC NULLS LAST,
            supplier.legal_name,
            comparison.rfq_response_id
          `,
          [
            params.data.id
          ]
        );


      const lines =
        new Map<
          number,
          {
            lineNumber: number;
            productId: string;
            productName: string;
            requestedQuantity: number;
            requestedUomCode: string;
            requestedCurrencyCode:
              string | null;
            responses:
              Record<
                string,
                unknown
              >[];
          }
        >();


      for (
        const row
        of result.rows
      ) {

        if (
          !lines.has(
            row.lineNumber
          )
        ) {

          lines.set(
            row.lineNumber,
            {
              lineNumber:
                row.lineNumber,
              productId:
                row.productId,
              productName:
                row.productName,
              requestedQuantity:
                row.requestedQuantity,
              requestedUomCode:
                row.requestedUomCode,
              requestedCurrencyCode:
                row.requestedCurrencyCode
                ?? null,
              responses:
                []
            }
          );

        }


        const {
          lineNumber: _lineNumber,
          productId: _productId,
          productName: _productName,
          requestedQuantity: _requestedQuantity,
          requestedUomCode: _requestedUomCode,
          requestedCurrencyCode: _requestedCurrencyCode,
          ...response
        } = row;


        lines.get(
          row.lineNumber
        )?.responses.push(
          response
        );

      }


      return {

        ok: true,

        rfq:
          rfq.rows[0],

        lines:
          Array.from(
            lines.values()
          )

      };

    }
  );

}
