import type {
  FastifyInstance
} from "fastify";

import { z } from "zod";

import {
  database
} from "../lib/database.js";


const classificationBodySchema =
  z.object({

    description: z
      .string()
      .trim()
      .min(
        2,
        "Product description is required."
      )
      .max(2000),

    productName: z
      .string()
      .trim()
      .min(1)
      .max(300)
      .optional(),

    productId: z
      .string()
      .uuid()
      .optional(),

    country: z
      .string()
      .trim()
      .length(2)
      .transform(
        value =>
          value.toUpperCase()
      )
      .optional(),

    attributes: z
      .record(
        z.string(),
        z.union([
          z.string(),
          z.number(),
          z.boolean(),
          z.null()
        ])
      )
      .optional(),

    limit: z
      .number()
      .int()
      .min(1)
      .max(20)
      .default(8)

  });


const requestParamsSchema =
  z.object({

    id: z
      .string()
      .uuid()

  });


const confirmationBodySchema =
  z.object({

    candidateId: z
      .string()
      .uuid()
      .optional(),

    hsCode: z
      .string()
      .trim()
      .regex(
        /^\d{6}$/,
        "A 6-digit HS2022 code is required."
      )
      .optional(),

    productId: z
      .string()
      .uuid()
      .optional(),

    notes: z
      .string()
      .trim()
      .max(4000)
      .optional()

  })
  .refine(
    value =>
      Boolean(value.candidateId)
      !== Boolean(value.hsCode),
    {
      message:
        "Provide exactly one of candidateId or hsCode."
    }
  );


type CandidateRow = {

  id: string;

  code: string;

  nomenclature: string;

  level: number;

  description: string;

  is_leaf: boolean | null;

  standard_unit: string | null;

  parent_code: string | null;

  parent_description: string | null;

  chapter_code: string | null;

  chapter_description: string | null;

  trigram_score: number | string;

};


type TextProfile = {

  normalized: string;

  positiveTerms: Set<string>;

  negativeTerms: Set<string>;

};


const STOP_WORDS =
  new Set([

    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "whether",
    "product",
    "products",
    "goods",
    "item",
    "items"

  ]);


const NEGATORS =
  new Set([

    "not",
    "without",
    "excluding",
    "except"

  ]);


function clamp(
  value: number
): number {

  return Math.max(
    0,
    Math.min(
      1,
      value
    )
  );

}


function roundScore(
  value: number
): number {

  return Number(
    value.toFixed(6)
  );

}


function normalizeText(
  value: string
): string {

  return value
    .normalize("NFKD")
    .toLowerCase()
    .replace(
      /[^\p{L}\p{N}]+/gu,
      " "
    )
    .replace(
      /\s+/g,
      " "
    )
    .trim();

}


function meaningfulToken(
  token: string
): boolean {

  return (
    token.length >= 2
    && !STOP_WORDS.has(
      token
    )
  );

}


function profileText(
  value: string
): TextProfile {

  const normalized =
    normalizeText(
      value
    );

  const tokens =
    normalized
      .split(" ")
      .filter(Boolean);

  const positiveTerms =
    new Set<string>();

  const negativeTerms =
    new Set<string>();


  for (
    let index = 0;
    index < tokens.length;
    index += 1
  ) {

    const token =
      tokens[index];


    if (
      NEGATORS.has(
        token
      )
    ) {

      const next =
        tokens[
          index + 1
        ];

      if (
        next
        && meaningfulToken(
          next
        )
      ) {

        negativeTerms.add(
          next
        );

        index += 1;

      }

      continue;

    }


    if (
      meaningfulToken(
        token
      )
    ) {

      positiveTerms.add(
        token
      );

    }

  }


  return {

    normalized,

    positiveTerms,

    negativeTerms

  };

}


function overlapRatio(
  expected: Set<string>,
  actual: Set<string>
): number {

  if (
    expected.size === 0
  ) {

    return 0;

  }

  let matches = 0;


  for (
    const term
    of expected
  ) {

    if (
      actual.has(
        term
      )
    ) {

      matches += 1;

    }

  }


  return (
    matches
    / expected.size
  );

}


function termsInBoth(
  left: Set<string>,
  right: Set<string>
): string[] {

  return [
    ...left
  ]
    .filter(
      term =>
        right.has(
          term
        )
    )
    .sort();

}


function scoreCandidate(
  query: TextProfile,
  row: CandidateRow
) {

  const candidate =
    profileText(
      row.description
    );


  const positiveMatchRatio =
    overlapRatio(
      query.positiveTerms,
      candidate.positiveTerms
    );


  const negativeMatchRatio =
    overlapRatio(
      query.negativeTerms,
      candidate.negativeTerms
    );


  const positiveContradictionRatio =
    overlapRatio(
      query.positiveTerms,
      candidate.negativeTerms
    );


  const negativeContradictionRatio =
    overlapRatio(
      query.negativeTerms,
      candidate.positiveTerms
    );


  const contradictionPenalty =
    clamp(

      (
        positiveContradictionRatio
        * 0.45
      )

      +

      (
        negativeContradictionRatio
        * 0.45
      )

    );


  let lexicalBase =
    positiveMatchRatio;


  if (
    query.negativeTerms.size > 0
  ) {

    lexicalBase = (

      positiveMatchRatio
      * 0.70

      +

      negativeMatchRatio
      * 0.30

    );

  }


  const lexicalScore =
    clamp(
      lexicalBase
      - contradictionPenalty
    );


  const trigramScore =
    clamp(
      Number(
        row.trigram_score
      ) || 0
    );


  const exactDescriptionBonus =
    (
      query.normalized.length > 0
      && normalizeText(
        row.description
      ).includes(
        query.normalized
      )
    )
      ? 0.05
      : 0;


  const numericInput =
    query.normalized
      .replace(
        /\D/g,
        ""
      );


  const exactCodeBonus =
    (
      numericInput.length > 0
      && numericInput === row.code
    )
      ? 0.25
      : 0;


  const retrievalScore =
    clamp(

      (
        trigramScore
        * 0.58
      )

      +

      (
        lexicalScore
        * 0.42
      )

      +

      exactDescriptionBonus

      +

      exactCodeBonus

    );


  return {

    ...row,

    retrievalScore:
      roundScore(
        retrievalScore
      ),

    trigramScore:
      roundScore(
        trigramScore
      ),

    lexicalScore:
      roundScore(
        lexicalScore
      ),

    contradictionPenalty:
      roundScore(
        contradictionPenalty
      ),

    evidence: {

      queryPositiveTerms:
        [
          ...query.positiveTerms
        ].sort(),

      queryNegativeTerms:
        [
          ...query.negativeTerms
        ].sort(),

      matchedPositiveTerms:
        termsInBoth(
          query.positiveTerms,
          candidate.positiveTerms
        ),

      matchedNegativeTerms:
        termsInBoth(
          query.negativeTerms,
          candidate.negativeTerms
        ),

      positiveContradictions:
        termsInBoth(
          query.positiveTerms,
          candidate.negativeTerms
        ),

      negativeContradictions:
        termsInBoth(
          query.negativeTerms,
          candidate.positiveTerms
        ),

      positiveMatchRatio:
        roundScore(
          positiveMatchRatio
        ),

      negativeMatchRatio:
        roundScore(
          negativeMatchRatio
        ),

      exactDescriptionBonus:
        exactDescriptionBonus > 0,

      exactCodeBonus:
        exactCodeBonus > 0

    }

  };

}


function classifyRetrievalQuality(
  candidates: Array<{
    retrievalScore: number;
    contradictionPenalty: number;
  }>
) {

  const top =
    candidates[0];

  if (!top) {

    return {
      quality: "no_signal",
      gap: null
    };

  }


  const second =
    candidates[1];

  const gap =
    second
      ? (
          top.retrievalScore
          - second.retrievalScore
        )
      : top.retrievalScore;


  if (
    top.retrievalScore >= 0.78
    && gap >= 0.06
    && top.contradictionPenalty === 0
  ) {

    return {

      quality:
        "high_signal",

      gap:
        roundScore(
          gap
        )

    };

  }


  if (
    top.retrievalScore >= 0.55
  ) {

    return {

      quality:
        "moderate_signal",

      gap:
        roundScore(
          gap
        )

    };

  }


  return {

    quality:
      "low_signal",

    gap:
      roundScore(
        gap
      )

  };

}


function buildWarnings(
  profile: TextProfile,
  candidates: Array<{
    retrievalScore: number;
  }>,
  quality: string,
  gap: number | null
): string[] {

  const warnings: string[] =
    [];


  if (
    profile.negativeTerms.size > 0
  ) {

    warnings.push(
      "Negation was detected and contradictory HS descriptions were penalized."
    );

  }


  if (
    gap !== null
    && gap < 0.05
    && candidates.length > 1
  ) {

    warnings.push(
      "The leading candidates are close. Additional product attributes may be required."
    );

  }


  if (
    quality === "low_signal"
  ) {

    warnings.push(
      "The description provides weak HS evidence. Add material, composition, intended use, processing state, dimensions, weight or presentation details where relevant."
    );

  }


  warnings.push(
    "Candidate retrieval is not an accepted customs classification or customs ruling."
  );


  return warnings;

}


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


export async function classificationRoutes(
  app: FastifyInstance
) {


  // ==========================================================
  // CREATE HS CLASSIFICATION REQUEST
  // ==========================================================

  app.post(
    "/api/intelligence/hs/classify",
    async (
      request,
      reply
    ) => {

      const parsed =
        classificationBodySchema.safeParse(
          request.body
        );


      if (!parsed.success) {

        reply.code(400);

        return validationError(
          parsed.error.issues
        );

      }


      const {

        description,
        productName,
        productId,
        country,
        attributes,
        limit

      } = parsed.data;


      const client =
        await database.connect();


      try {

        await client.query(
          "BEGIN"
        );


        let product:
          | {
              id: string;
              name: string;
              brand: string | null;
              description: string | null;
              attributes: Record<
                string,
                unknown
              >;
            }
          | null = null;


        if (
          productId
        ) {

          const productResult =
            await client.query(
              `
              SELECT
                id::text,
                name,
                brand,
                description,
                attributes
              FROM products
              WHERE id = $1::uuid
                AND is_active = TRUE
              `,
              [
                productId
              ]
            );


          if (
            !productResult.rows[0]
          ) {

            await client.query(
              "ROLLBACK"
            );

            reply.code(404);

            return {

              ok: false,

              error:
                "product_not_found",

              productId

            };

          }


          product =
            productResult.rows[0];

        }


        let countryId:
          string | null =
            null;


        let countryRecord:
          | {
              iso2: string;
              iso3: string | null;
              name: string;
            }
          | null = null;


        if (
          country
        ) {

          const countryResult =
            await client.query(
              `
              SELECT
                id::text,
                iso2,
                iso3,
                name
              FROM countries
              WHERE
                iso2 = $1
                AND is_active = TRUE
              `,
              [
                country
              ]
            );


          if (
            !countryResult.rows[0]
          ) {

            await client.query(
              "ROLLBACK"
            );

            reply.code(404);

            return {

              ok: false,

              error:
                "country_not_found",

              country

            };

          }


          countryId =
            countryResult
              .rows[0]
              .id;


          countryRecord = {

            iso2:
              countryResult
                .rows[0]
                .iso2,

            iso3:
              countryResult
                .rows[0]
                .iso3,

            name:
              countryResult
                .rows[0]
                .name

          };

        }


        const textParts: string[] =
          [];


        if (
          productName
        ) {

          textParts.push(
            productName
          );

        }


        if (
          product
        ) {

          textParts.push(
            product.name
          );

          if (
            product.brand
          ) {

            textParts.push(
              product.brand
            );

          }

          if (
            product.description
          ) {

            textParts.push(
              product.description
            );

          }

        }


        textParts.push(
          description
        );


        const mergedAttributes = {

          ...(product?.attributes ?? {}),

          ...(attributes ?? {})

        };


        for (
          const [
            key,
            value
          ]
          of Object.entries(
            mergedAttributes
          )
        ) {

          if (
            value === null
            || value === undefined
          ) {

            continue;

          }

          textParts.push(
            `${key} ${String(value)}`
          );

        }


        const inputText =
          [
            ...new Set(
              textParts
                .map(
                  value =>
                    value.trim()
                )
                .filter(Boolean)
            )
          ].join(
            " | "
          );


        const queryProfile =
          profileText(
            inputText
          );


        const requestResult =
          await client.query(
            `
            INSERT INTO hs_classification_requests (
                product_id,
                country_id,
                nomenclature,
                input_text,
                normalized_text,
                input_payload,
                status,
                retrieval_version,
                candidate_limit,
                metadata
            )
            VALUES (
                $1::uuid,
                $2::uuid,
                'HS2022',
                $3,
                $4,
                $5::jsonb,
                'pending',
                'trigram_polarity_v1',
                $6,
                $7::jsonb
            )
            RETURNING
                id::text,
                created_at
            `,
            [
              productId ?? null,
              countryId,
              inputText,
              queryProfile.normalized,
              JSON.stringify({

                description,

                productName:
                  productName ?? null,

                productId:
                  productId ?? null,

                country:
                  country ?? null,

                attributes:
                  mergedAttributes

              }),
              limit,
              JSON.stringify({

                source:
                  "origin_hut_internal",

                automaticDecision:
                  false

              })
            ]
          );


        const classificationRequest =
          requestResult.rows[0];


        const rawCandidates =
          await client.query<CandidateRow>(
            `
            SELECT

              h.id::text,
              h.code,
              h.nomenclature,
              h.level,
              h.description,
              h.is_leaf,
              h.standard_unit,

              p.code
                AS parent_code,

              p.description
                AS parent_description,

              gp.code
                AS chapter_code,

              gp.description
                AS chapter_description,

              word_similarity(
                LOWER($1),
                LOWER(h.description)
              )
                AS trigram_score

            FROM hs_codes h

            LEFT JOIN hs_codes p
              ON p.id =
                 h.parent_id

            LEFT JOIN hs_codes gp
              ON gp.id =
                 p.parent_id

            WHERE
              h.nomenclature =
                'HS2022'

              AND h.level = 6

            ORDER BY

              word_similarity(
                LOWER($1),
                LOWER(h.description)
              ) DESC,

              h.code

            LIMIT 150
            `,
            [
              queryProfile.normalized
            ]
          );


        const ranked =
          rawCandidates.rows

            .map(
              row =>
                scoreCandidate(
                  queryProfile,
                  row
                )
            )

            .sort(
              (
                left,
                right
              ) => {

                if (
                  right.retrievalScore
                  !== left.retrievalScore
                ) {

                  return (
                    right.retrievalScore
                    - left.retrievalScore
                  );

                }


                if (
                  right.trigramScore
                  !== left.trigramScore
                ) {

                  return (
                    right.trigramScore
                    - left.trigramScore
                  );

                }


                return (
                  left.code.localeCompare(
                    right.code
                  )
                );

              }
            )

            .slice(
              0,
              limit
            );


        for (
          let index = 0;
          index < ranked.length;
          index += 1
        ) {

          const candidate =
            ranked[index];


          await client.query(
            `
            INSERT INTO hs_classification_candidates (
                request_id,
                hs_code_id,
                rank,
                retrieval_score,
                trigram_score,
                lexical_score,
                contradiction_penalty,
                retrieval_method,
                evidence
            )
            VALUES (
                $1::uuid,
                $2::uuid,
                $3,
                $4,
                $5,
                $6,
                $7,
                'trigram_polarity_v1',
                $8::jsonb
            )
            `,
            [
              classificationRequest.id,
              candidate.id,
              index + 1,
              candidate.retrievalScore,
              candidate.trigramScore,
              candidate.lexicalScore,
              candidate.contradictionPenalty,
              JSON.stringify(
                candidate.evidence
              )
            ]
          );

        }


        const qualityResult =
          classifyRetrievalQuality(
            ranked
          );


        const warnings =
          buildWarnings(
            queryProfile,
            ranked,
            qualityResult.quality,
            qualityResult.gap
          );


        await client.query(
          `
          UPDATE hs_classification_requests
          SET
              status =
                  'candidates_generated',

              metadata =
                  metadata
                  || $2::jsonb

          WHERE id = $1::uuid
          `,
          [
            classificationRequest.id,
            JSON.stringify({

              retrievalQuality:
                qualityResult.quality,

              scoreGap:
                qualityResult.gap,

              candidateCount:
                ranked.length,

              warnings

            })
          ]
        );


        await client.query(
          "COMMIT"
        );


        return {

          ok: true,

          request: {

            id:
              classificationRequest.id,

            status:
              "candidates_generated",

            nomenclature:
              "HS2022",

            productId:
              productId ?? null,

            country:
              countryRecord,

            inputText,

            normalizedText:
              queryProfile.normalized,

            retrievalVersion:
              "trigram_polarity_v1",

            createdAt:
              classificationRequest.created_at

          },

          assessment: {

            automaticClassification:
              false,

            retrievalQuality:
              qualityResult.quality,

            scoreGap:
              qualityResult.gap,

            warnings,

            recommendedNextStep:
              qualityResult.quality
              === "high_signal"

                ? (
                    "Review the leading candidate and its HS hierarchy before confirmation."
                  )

                : (
                    "Provide additional product attributes and review multiple candidates before confirmation."
                  )

          },

          candidates:
            ranked.map(
              (
                candidate,
                index
              ) => ({

                rank:
                  index + 1,

                code:
                  candidate.code,

                level:
                  candidate.level,

                description:
                  candidate.description,

                standardUnit:
                  candidate.standard_unit,

                score: {

                  retrieval:
                    candidate.retrievalScore,

                  trigram:
                    candidate.trigramScore,

                  lexical:
                    candidate.lexicalScore,

                  contradictionPenalty:
                    candidate.contradictionPenalty

                },

                hierarchy: {

                  chapter: {

                    code:
                      candidate.chapter_code,

                    description:
                      candidate.chapter_description

                  },

                  heading: {

                    code:
                      candidate.parent_code,

                    description:
                      candidate.parent_description

                  }

                },

                evidence:
                  candidate.evidence

              })
            )

        };

      }
      catch (error) {

        await client.query(
          "ROLLBACK"
        );


        request.log.error(
          error
        );


        reply.code(500);


        return {

          ok: false,

          error:
            "classification_failed"

        };

      }
      finally {

        client.release();

      }

    }
  );


  // ==========================================================
  // READ CLASSIFICATION REQUEST
  // ==========================================================

  app.get(
    "/api/intelligence/hs/classifications/:id",
    async (
      request,
      reply
    ) => {

      const parsed =
        requestParamsSchema.safeParse(
          request.params
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
            r.nomenclature,
            r.input_text,
            r.normalized_text,
            r.status,
            r.retrieval_version,
            r.candidate_limit,
            r.decision_notes,
            r.decided_at,
            r.metadata,
            r.created_at,
            r.updated_at,

            p.id::text
              AS product_id,

            p.name
              AS product_name,

            c.iso2
              AS country_iso2,

            c.iso3
              AS country_iso3,

            c.name
              AS country_name

          FROM hs_classification_requests r

          LEFT JOIN products p
            ON p.id =
               r.product_id

          LEFT JOIN countries c
            ON c.id =
               r.country_id

          WHERE
            r.id = $1::uuid
          `,
          [
            parsed.data.id
          ]
        );


      const row =
        result.rows[0];


      if (!row) {

        reply.code(404);

        return {

          ok: false,

          error:
            "classification_request_not_found"

        };

      }


      const candidates =
        await database.query(
          `
          SELECT

            candidate.id::text,

            candidate.rank,

            candidate.retrieval_score,

            candidate.trigram_score,

            candidate.lexical_score,

            candidate.contradiction_penalty,

            candidate.retrieval_method,

            candidate.evidence,

            h.code,

            h.level,

            h.description,

            h.standard_unit,

            parent.code
              AS heading_code,

            parent.description
              AS heading_description,

            chapter.code
              AS chapter_code,

            chapter.description
              AS chapter_description

          FROM hs_classification_candidates candidate

          JOIN hs_codes h
            ON h.id =
               candidate.hs_code_id

          LEFT JOIN hs_codes parent
            ON parent.id =
               h.parent_id

          LEFT JOIN hs_codes chapter
            ON chapter.id =
               parent.parent_id

          WHERE
            candidate.request_id =
              $1::uuid

          ORDER BY
            candidate.rank
          `,
          [
            parsed.data.id
          ]
        );


      return {

        ok: true,

        request: row,

        candidates:
          candidates.rows

      };

    }
  );


  // ==========================================================
  // CONFIRM HS CLASSIFICATION
  // ==========================================================

  app.post(
    "/api/intelligence/hs/classifications/:id/confirm",
    async (
      request,
      reply
    ) => {

      const params =
        requestParamsSchema.safeParse(
          request.params
        );


      const body =
        confirmationBodySchema.safeParse(
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


      const client =
        await database.connect();


      try {

        await client.query(
          "BEGIN"
        );


        const requestResult =
          await client.query(
            `
            SELECT
              id::text,
              product_id::text,
              country_id::text,
              nomenclature,
              status,
              selected_candidate_id::text
            FROM hs_classification_requests
            WHERE id = $1::uuid
            FOR UPDATE
            `,
            [
              params.data.id
            ]
          );


        const classificationRequest =
          requestResult.rows[0];


        if (!classificationRequest) {

          await client.query(
            "ROLLBACK"
          );

          reply.code(404);

          return {

            ok: false,

            error:
              "classification_request_not_found"

          };

        }


        if (
          classificationRequest.nomenclature
          !== "HS2022"
        ) {

          await client.query(
            "ROLLBACK"
          );

          reply.code(409);

          return {

            ok: false,

            error:
              "unsupported_nomenclature"

          };

        }


        let productId =
          classificationRequest.product_id
          ?? body.data.productId
          ?? null;


        if (
          classificationRequest.product_id
          && body.data.productId
          && classificationRequest.product_id
             !== body.data.productId
        ) {

          await client.query(
            "ROLLBACK"
          );

          reply.code(409);

          return {

            ok: false,

            error:
              "product_mismatch"

          };

        }


        if (
          productId
        ) {

          const productResult =
            await client.query(
              `
              SELECT
                id::text,
                name
              FROM products
              WHERE
                id = $1::uuid
                AND is_active = TRUE
              `,
              [
                productId
              ]
            );


          if (
            !productResult.rows[0]
          ) {

            await client.query(
              "ROLLBACK"
            );

            reply.code(404);

            return {

              ok: false,

              error:
                "product_not_found",

              productId

            };

          }

        }


        let candidateId:
          string;

        let hsCodeId:
          string;

        let hsCode:
          string;

        let decisionMethod:
          string;


        if (
          body.data.candidateId
        ) {

          const candidateResult =
            await client.query(
              `
              SELECT
                candidate.id::text,
                candidate.hs_code_id::text,
                h.code
              FROM hs_classification_candidates candidate
              JOIN hs_codes h
                ON h.id =
                   candidate.hs_code_id
              WHERE
                candidate.id = $1::uuid
                AND candidate.request_id = $2::uuid
                AND h.nomenclature = 'HS2022'
                AND h.level = 6
              `,
              [
                body.data.candidateId,
                params.data.id
              ]
            );


          if (
            !candidateResult.rows[0]
          ) {

            await client.query(
              "ROLLBACK"
            );

            reply.code(404);

            return {

              ok: false,

              error:
                "classification_candidate_not_found"

            };

          }


          candidateId =
            candidateResult.rows[0].id;

          hsCodeId =
            candidateResult.rows[0].hs_code_id;

          hsCode =
            candidateResult.rows[0].code;

          decisionMethod =
            "candidate_confirmation";

        }
        else {

          const hsResult =
            await client.query(
              `
              SELECT
                id::text,
                code
              FROM hs_codes
              WHERE
                nomenclature = 'HS2022'
                AND level = 6
                AND code = $1
              `,
              [
                body.data.hsCode
              ]
            );


          if (
            !hsResult.rows[0]
          ) {

            await client.query(
              "ROLLBACK"
            );

            reply.code(404);

            return {

              ok: false,

              error:
                "hs_code_not_found",

              hsCode:
                body.data.hsCode

            };

          }


          hsCodeId =
            hsResult.rows[0].id;

          hsCode =
            hsResult.rows[0].code;


          const existingCandidate =
            await client.query(
              `
              SELECT id::text
              FROM hs_classification_candidates
              WHERE
                request_id = $1::uuid
                AND hs_code_id = $2::uuid
              `,
              [
                params.data.id,
                hsCodeId
              ]
            );


          if (
            existingCandidate.rows[0]
          ) {

            candidateId =
              existingCandidate
                .rows[0]
                .id;

          }
          else {

            const nextRank =
              await client.query(
                `
                SELECT
                  COALESCE(
                    MAX(rank),
                    0
                  ) + 1 AS next_rank
                FROM hs_classification_candidates
                WHERE
                  request_id = $1::uuid
                `,
                [
                  params.data.id
                ]
              );


            const manualCandidate =
              await client.query(
                `
                INSERT INTO hs_classification_candidates (
                    request_id,
                    hs_code_id,
                    rank,
                    retrieval_score,
                    trigram_score,
                    lexical_score,
                    contradiction_penalty,
                    retrieval_method,
                    evidence
                )
                VALUES (
                    $1::uuid,
                    $2::uuid,
                    $3,
                    0,
                    0,
                    0,
                    0,
                    'manual_reference_selection',
                    $4::jsonb
                )
                RETURNING id::text
                `,
                [
                  params.data.id,
                  hsCodeId,
                  nextRank.rows[0].next_rank,
                  JSON.stringify({

                    manualSelection:
                      true,

                    selectedHsCode:
                      hsCode,

                    reason:
                      "Operator selected HS code from the canonical HS2022 reference."

                  })
                ]
              );


            candidateId =
              manualCandidate
                .rows[0]
                .id;

          }


          decisionMethod =
            "manual_reference_selection";

        }


        await client.query(
          `
          UPDATE hs_classification_requests
          SET
              product_id =
                  COALESCE(
                    product_id,
                    $2::uuid
                  ),

              status =
                  'confirmed',

              selected_candidate_id =
                  $3::uuid,

              decision_notes =
                  $4,

              decided_at =
                  NOW(),

              metadata =
                  metadata
                  || $5::jsonb

          WHERE id = $1::uuid
          `,
          [
            params.data.id,
            productId,
            candidateId,
            body.data.notes ?? null,
            JSON.stringify({

              decisionMethod,

              selectedHsCode:
                hsCode,

              humanConfirmed:
                true

            })
          ]
        );


        let productClassificationId:
          string | null =
            null;


        if (
          productId
        ) {

          await client.query(
            `
            UPDATE product_hs_classifications
            SET
                is_primary = FALSE
            WHERE
                product_id = $1::uuid
                AND country_id
                    IS NOT DISTINCT FROM
                    $2::uuid
            `,
            [
              productId,
              classificationRequest.country_id
            ]
          );


          const classificationResult =
            await client.query(
              `
              INSERT INTO product_hs_classifications (
                  product_id,
                  hs_code_id,
                  country_id,
                  is_primary,
                  confidence,
                  classification_request_id,
                  decision_method,
                  decision_notes,
                  metadata
              )
              VALUES (
                  $1::uuid,
                  $2::uuid,
                  $3::uuid,
                  TRUE,
                  NULL,
                  $4::uuid,
                  $5,
                  $6,
                  $7::jsonb
              )
              ON CONFLICT (
                  product_id,
                  hs_code_id,
                  country_id
              )
              DO UPDATE SET
                  is_primary =
                      TRUE,

                  confidence =
                      NULL,

                  classification_request_id =
                      EXCLUDED.classification_request_id,

                  decision_method =
                      EXCLUDED.decision_method,

                  decision_notes =
                      EXCLUDED.decision_notes,

                  metadata =
                      product_hs_classifications.metadata
                      || EXCLUDED.metadata,

                  updated_at =
                      NOW()

              RETURNING id::text
              `,
              [
                productId,
                hsCodeId,
                classificationRequest.country_id,
                params.data.id,
                decisionMethod,
                body.data.notes ?? null,
                JSON.stringify({

                  nomenclature:
                    "HS2022",

                  confirmed:
                    true,

                  selectedCandidateId:
                    candidateId

                })
              ]
            );


          productClassificationId =
            classificationResult
              .rows[0]
              .id;

        }


        await client.query(
          "COMMIT"
        );


        return {

          ok: true,

          confirmation: {

            requestId:
              params.data.id,

            status:
              "confirmed",

            selectedCandidateId:
              candidateId,

            hsCode,

            decisionMethod,

            productId,

            productClassificationId,

            persistedToProduct:
              Boolean(
                productClassificationId
              ),

            notes:
              body.data.notes ?? null

          }

        };

      }
      catch (error) {

        await client.query(
          "ROLLBACK"
        );


        request.log.error(
          error
        );


        reply.code(500);


        return {

          ok: false,

          error:
            "classification_confirmation_failed"

        };

      }
      finally {

        client.release();

      }

    }
  );


}
