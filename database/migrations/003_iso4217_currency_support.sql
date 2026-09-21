BEGIN;

-- ISO 4217 numeric currency code.
ALTER TABLE currencies
ADD COLUMN IF NOT EXISTS numeric_code VARCHAR(3);

-- Some ISO 4217 special codes use N.A. for minor units.
ALTER TABLE currencies
ALTER COLUMN decimal_places DROP NOT NULL;

-- Preserve additional normalized metadata without inventing
-- extra fixed columns prematurely.
ALTER TABLE currencies
ADD COLUMN IF NOT EXISTS metadata JSONB
NOT NULL
DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS
ux_currencies_numeric_code
ON currencies(numeric_code)
WHERE numeric_code IS NOT NULL;

INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '003',
    'iso4217_currency_support'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
