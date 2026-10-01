BEGIN;

-- ============================================================
-- ORIGIN HUT
-- MIGRATION 028
-- RFQ SUPPLIER RESPONSE -> COMMERCIAL OFFER LINKAGE
-- ============================================================
--
-- Supplier responses do not duplicate price/Incoterm/packaging data.
-- They link a specific RFQ line and invited supplier to a canonical
-- Commercial Offer.
-- ============================================================


CREATE TABLE rfq_responses (

    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    rfq_id UUID NOT NULL
        REFERENCES rfqs(id)
        ON DELETE CASCADE,

    rfq_line_id UUID NOT NULL
        REFERENCES rfq_lines(id)
        ON DELETE CASCADE,

    rfq_supplier_id UUID NOT NULL
        REFERENCES rfq_suppliers(id)
        ON DELETE CASCADE,

    commercial_offer_id UUID NOT NULL
        REFERENCES commercial_offers(id)
        ON DELETE RESTRICT,

    status TEXT NOT NULL
        DEFAULT 'submitted',

    responded_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    notes TEXT,

    source_type TEXT NOT NULL
        DEFAULT 'manual',

    canonical_source_record_id UUID
        REFERENCES source_records(id)
        ON DELETE SET NULL,

    confidence NUMERIC(5,4),

    metadata JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),


    CONSTRAINT
        rfq_responses_status
    CHECK (
        status IN (
            'submitted',
            'withdrawn',
            'superseded'
        )
    ),


    CONSTRAINT
        rfq_responses_notes_not_blank
    CHECK (
        notes IS NULL
        OR BTRIM(notes) <> ''
    ),


    CONSTRAINT
        rfq_responses_source_type_not_blank
    CHECK (
        BTRIM(source_type) <> ''
    ),


    CONSTRAINT
        rfq_responses_confidence_range
    CHECK (
        confidence IS NULL
        OR (
            confidence >= 0
            AND confidence <= 1
        )
    ),


    UNIQUE (
        rfq_line_id,
        commercial_offer_id
    )

);


CREATE INDEX
idx_rfq_responses_rfq
ON rfq_responses (
    rfq_id,
    status,
    responded_at DESC
);


CREATE INDEX
idx_rfq_responses_line
ON rfq_responses (
    rfq_line_id,
    status,
    responded_at DESC
);


CREATE INDEX
idx_rfq_responses_supplier
ON rfq_responses (
    rfq_supplier_id,
    status,
    responded_at DESC
);


CREATE INDEX
idx_rfq_responses_offer
ON rfq_responses (
    commercial_offer_id
);


CREATE INDEX
idx_rfq_responses_source_record
ON rfq_responses (
    canonical_source_record_id
)
WHERE canonical_source_record_id IS NOT NULL;


CREATE INDEX
idx_rfq_responses_metadata_gin
ON rfq_responses
USING GIN (
    metadata
);


CREATE OR REPLACE FUNCTION
originhut_validate_rfq_response()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_line RECORD;
    v_supplier RECORD;
    v_offer RECORD;
    v_rfq_buyer_id UUID;
BEGIN

    SELECT
        rl.rfq_id,
        rl.product_id,
        rl.manufacturer_product_id,
        rl.packaging_configuration_id
    INTO v_line
    FROM rfq_lines rl
    WHERE rl.id =
          NEW.rfq_line_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'RFQ response line does not exist.';
    END IF;


    IF
        v_line.rfq_id
        <> NEW.rfq_id
    THEN
        RAISE EXCEPTION
            'RFQ response line must belong to the response RFQ.';
    END IF;


    SELECT
        rs.rfq_id,
        rs.supplier_organization_id
    INTO v_supplier
    FROM rfq_suppliers rs
    WHERE rs.id =
          NEW.rfq_supplier_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'RFQ supplier invitation does not exist.';
    END IF;


    IF
        v_supplier.rfq_id
        <> NEW.rfq_id
    THEN
        RAISE EXCEPTION
            'RFQ supplier invitation must belong to the response RFQ.';
    END IF;


    SELECT buyer_organization_id
    INTO v_rfq_buyer_id
    FROM rfqs
    WHERE id =
          NEW.rfq_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'RFQ does not exist.';
    END IF;


    SELECT
        co.seller_organization_id,
        co.buyer_organization_id,
        co.manufacturer_product_id,
        co.packaging_configuration_id,
        mp.product_id,
        co.status
    INTO v_offer
    FROM commercial_offers co
    JOIN manufacturer_products mp
      ON mp.id =
         co.manufacturer_product_id
    WHERE co.id =
          NEW.commercial_offer_id;


    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Commercial Offer does not exist.';
    END IF;


    IF
        v_offer.status
        NOT IN (
            'draft',
            'active'
        )
    THEN
        RAISE EXCEPTION
            'Commercial Offer is not available for RFQ response.';
    END IF;


    IF
        v_offer.seller_organization_id
        <> v_supplier.supplier_organization_id
    THEN
        RAISE EXCEPTION
            'Commercial Offer seller must match the invited RFQ supplier.';
    END IF;


    IF
        v_offer.buyer_organization_id IS NOT NULL
        AND v_offer.buyer_organization_id
            <> v_rfq_buyer_id
    THEN
        RAISE EXCEPTION
            'Buyer-specific Commercial Offer must match the RFQ buyer.';
    END IF;


    IF
        v_offer.product_id
        <> v_line.product_id
    THEN
        RAISE EXCEPTION
            'Commercial Offer Product must match the RFQ line Product.';
    END IF;


    IF
        v_line.manufacturer_product_id IS NOT NULL
        AND v_offer.manufacturer_product_id
            <> v_line.manufacturer_product_id
    THEN
        RAISE EXCEPTION
            'Commercial Offer Manufacturer Product must match the RFQ line restriction.';
    END IF;


    IF
        v_line.packaging_configuration_id IS NOT NULL
        AND v_offer.packaging_configuration_id
            IS DISTINCT FROM
            v_line.packaging_configuration_id
    THEN
        RAISE EXCEPTION
            'Commercial Offer packaging must match the RFQ line restriction.';
    END IF;


    RETURN NEW;

END;
$$;


CREATE OR REPLACE FUNCTION
originhut_refresh_rfq_response_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_rfq_id UUID;
    v_supplier_id UUID;
    v_total_suppliers INTEGER;
    v_terminal_suppliers INTEGER;
    v_responded_suppliers INTEGER;
BEGIN

    v_rfq_id :=
        COALESCE(
            NEW.rfq_id,
            OLD.rfq_id
        );

    v_supplier_id :=
        COALESCE(
            NEW.rfq_supplier_id,
            OLD.rfq_supplier_id
        );


    IF
        TG_OP <> 'DELETE'
        AND NEW.status = 'submitted'
    THEN

        UPDATE rfq_suppliers
        SET
            status =
                'responded',

            responded_at =
                COALESCE(
                    responded_at,
                    NEW.responded_at
                )

        WHERE id =
              NEW.rfq_supplier_id;

    END IF;


    SELECT
        COUNT(*)::int,

        COUNT(*) FILTER (
            WHERE status IN (
                'responded',
                'declined',
                'withdrawn'
            )
        )::int,

        COUNT(*) FILTER (
            WHERE status =
                  'responded'
        )::int

    INTO
        v_total_suppliers,
        v_terminal_suppliers,
        v_responded_suppliers

    FROM rfq_suppliers
    WHERE rfq_id =
          v_rfq_id;


    IF v_responded_suppliers > 0 THEN

        UPDATE rfqs
        SET status =
            CASE
                WHEN
                    v_total_suppliers > 0
                    AND v_terminal_suppliers
                        = v_total_suppliers
                THEN 'responded'
                ELSE 'partially_responded'
            END

        WHERE
            id = v_rfq_id
            AND status NOT IN (
                'closed',
                'cancelled'
            );

    END IF;


    RETURN
        COALESCE(
            NEW,
            OLD
        );

END;
$$;


CREATE TRIGGER
trg_rfq_responses_validate
BEFORE INSERT OR UPDATE
ON rfq_responses
FOR EACH ROW
EXECUTE FUNCTION
originhut_validate_rfq_response();


CREATE TRIGGER
trg_rfq_responses_updated_at
BEFORE UPDATE
ON rfq_responses
FOR EACH ROW
EXECUTE FUNCTION
originhut_set_updated_at();


CREATE TRIGGER
trg_rfq_responses_source_link
AFTER INSERT OR UPDATE OF canonical_source_record_id
ON rfq_responses
FOR EACH ROW
EXECUTE FUNCTION
originhut_link_canonical_source_record(
    'rfq_response',
    'supplier_response_evidence'
);


CREATE TRIGGER
trg_rfq_responses_refresh_status
AFTER INSERT OR UPDATE OR DELETE
ON rfq_responses
FOR EACH ROW
EXECUTE FUNCTION
originhut_refresh_rfq_response_status();


INSERT INTO schema_migrations (
    version,
    name
)
VALUES (
    '028',
    'rfq_supplier_commercial_offer_responses'
)
ON CONFLICT (version)
DO NOTHING;


COMMIT;
