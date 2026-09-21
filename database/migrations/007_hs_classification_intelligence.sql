BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 007
-- HS CLASSIFICATION INTELLIGENCE
-- ============================================================
--
-- Candidate retrieval is deliberately separated from an
-- accepted product classification.
--
-- A classification request may produce several candidates.
-- Only a later explicit decision may create/confirm a
-- product_hs_classifications record.
-- ============================================================


CREATE TABLE IF NOT EXISTS hs_classification_requests (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    product_id UUID
        REFERENCES products(id)
        ON DELETE SET NULL,

    country_id UUID
        REFERENCES countries(id)
        ON DELETE SET NULL,

    nomenclature VARCHAR(20)
        NOT NULL
        DEFAULT 'HS2022',

    input_text TEXT
        NOT NULL,

    normalized_text TEXT
        NOT NULL,

    input_payload JSONB
        NOT NULL
        DEFAULT '{}'::jsonb,

    status TEXT
        NOT NULL
        DEFAULT 'pending',

    retrieval_version TEXT
        NOT NULL
        DEFAULT 'lexical_v1',

    candidate_limit SMALLINT
        NOT NULL
        DEFAULT 8,

    selected_candidate_id UUID,

    decision_notes TEXT,

    decided_at TIMESTAMPTZ,

    metadata JSONB
        NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    CONSTRAINT chk_hs_classification_request_status
        CHECK (
            status IN (
                'pending',
                'candidates_generated',
                'confirmed',
                'rejected',
                'cancelled',
                'failed'
            )
        ),

    CONSTRAINT chk_hs_classification_candidate_limit
        CHECK (
            candidate_limit
            BETWEEN 1 AND 25
        )
);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_requests_product
ON hs_classification_requests(product_id);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_requests_country
ON hs_classification_requests(country_id);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_requests_status
ON hs_classification_requests(status);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_requests_created
ON hs_classification_requests(created_at DESC);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_requests_metadata
ON hs_classification_requests
USING GIN(metadata);


DROP TRIGGER IF EXISTS
trg_hs_classification_requests_updated_at
ON hs_classification_requests;


CREATE TRIGGER
trg_hs_classification_requests_updated_at

BEFORE UPDATE
ON hs_classification_requests

FOR EACH ROW
EXECUTE FUNCTION originhut_set_updated_at();


-- ------------------------------------------------------------
-- CLASSIFICATION CANDIDATES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS hs_classification_candidates (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    request_id UUID
        NOT NULL
        REFERENCES hs_classification_requests(id)
        ON DELETE CASCADE,

    hs_code_id UUID
        NOT NULL
        REFERENCES hs_codes(id)
        ON DELETE CASCADE,

    rank SMALLINT
        NOT NULL,

    retrieval_score NUMERIC(7,6)
        NOT NULL,

    trigram_score NUMERIC(7,6)
        NOT NULL,

    lexical_score NUMERIC(7,6)
        NOT NULL,

    contradiction_penalty NUMERIC(7,6)
        NOT NULL
        DEFAULT 0,

    retrieval_method TEXT
        NOT NULL
        DEFAULT 'trigram_polarity_v1',

    evidence JSONB
        NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    CONSTRAINT chk_hs_candidate_rank
        CHECK (
            rank > 0
        ),

    CONSTRAINT chk_hs_candidate_retrieval_score
        CHECK (
            retrieval_score
            BETWEEN 0 AND 1
        ),

    CONSTRAINT chk_hs_candidate_trigram_score
        CHECK (
            trigram_score
            BETWEEN 0 AND 1
        ),

    CONSTRAINT chk_hs_candidate_lexical_score
        CHECK (
            lexical_score
            BETWEEN 0 AND 1
        ),

    CONSTRAINT chk_hs_candidate_contradiction_penalty
        CHECK (
            contradiction_penalty
            BETWEEN 0 AND 1
        ),

    UNIQUE (
        request_id,
        hs_code_id
    ),

    UNIQUE (
        request_id,
        rank
    )
);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_candidates_request
ON hs_classification_candidates(
    request_id,
    rank
);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_candidates_hs
ON hs_classification_candidates(
    hs_code_id
);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_candidates_score
ON hs_classification_candidates(
    retrieval_score DESC
);


CREATE INDEX IF NOT EXISTS
idx_hs_classification_candidates_evidence
ON hs_classification_candidates
USING GIN(evidence);


-- ------------------------------------------------------------
-- SELECTED CANDIDATE FK
-- ------------------------------------------------------------

DO $$
BEGIN

    IF NOT EXISTS (

        SELECT 1
        FROM pg_constraint
        WHERE
            conname =
                'hs_classification_requests_selected_candidate_fkey'

    ) THEN

        ALTER TABLE hs_classification_requests

        ADD CONSTRAINT
        hs_classification_requests_selected_candidate_fkey

        FOREIGN KEY (
            selected_candidate_id
        )

        REFERENCES hs_classification_candidates(id)

        ON DELETE SET NULL;

    END IF;

END
$$;


-- ------------------------------------------------------------
-- MIGRATION HISTORY
-- ------------------------------------------------------------

INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '007',
    'hs_classification_intelligence'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
