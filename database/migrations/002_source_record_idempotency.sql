BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS
ux_source_records_source_type_external_hash
ON source_records (
    data_source_id,
    record_type,
    external_id,
    content_hash
)
WHERE external_id IS NOT NULL
  AND content_hash IS NOT NULL;

INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '002',
    'source_record_idempotency'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
