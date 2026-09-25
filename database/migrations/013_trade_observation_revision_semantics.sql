BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 013
-- TRADE OBSERVATION REVISION SEMANTICS
-- ============================================================
--
-- is_provisional is tri-state:
--
-- TRUE  = provider explicitly identifies the observation
--         as provisional.
--
-- FALSE = provider explicitly identifies the observation
--         as non-provisional / final.
--
-- NULL  = provider revision status is unknown.
--
-- Never convert unknown provider state into FALSE.
-- ============================================================


ALTER TABLE trade_flows
ALTER COLUMN is_provisional
DROP DEFAULT;


ALTER TABLE trade_flows
ALTER COLUMN is_provisional
DROP NOT NULL;


-- ------------------------------------------------------------
-- EXISTING UN COMTRADE CANONICAL FACTS
--
-- The previously ingested Comtrade observation did not expose
-- a reliable per-record provisional/final indicator.
-- Correct the earlier FALSE assumption to unknown.
-- ------------------------------------------------------------

UPDATE trade_flows
SET is_provisional = NULL
WHERE
    metadata ->> 'sourceSystem'
        = 'un_comtrade';


-- ------------------------------------------------------------
-- BACKFILL SOURCE-ACCESS SEMANTICS ON EXISTING COMTRADE FACTS
-- ------------------------------------------------------------

UPDATE trade_flows tf
SET metadata =
    tf.metadata
    ||
    jsonb_build_object(
        'sourceAccessMode',
        CASE

            WHEN
                sr.metadata ->> 'requestUrl'
                LIKE '%/public/v1/preview/%'
            THEN
                'public_preview'

            WHEN
                sr.metadata ->> 'requestUrl'
                LIKE '%/public/%'
            THEN
                'public_api'

            ELSE
                'unknown'

        END,

        'providerRevisionStatus',
        'unknown'
    )

FROM source_records sr

WHERE
    tf.canonical_source_record_id =
        sr.id

    AND tf.metadata ->> 'sourceSystem'
        = 'un_comtrade';


COMMENT ON COLUMN trade_flows.is_provisional IS
'Provider revision state: TRUE=explicitly provisional, FALSE=explicitly non-provisional, NULL=unknown or not supplied.';


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '013',
    'trade_observation_revision_semantics'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;
