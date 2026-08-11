-- Bucket language: versioned constraint facts that gate Edge emission.
-- Evaluation precedes write. Refusal leaves history untouched.
-- Prior versions remain reconstructible.

CREATE TABLE IF NOT EXISTS buckets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bucket_name     TEXT NOT NULL,                    -- SLA_horizon, residual_capacity, permission_set, rank_classification, ...
    version         INTEGER NOT NULL DEFAULT 1,
    constraint_body JSONB NOT NULL,                   -- machine-evaluable facts
    effective_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
    effective_to    TIMESTAMPTZ,                      -- null = current
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (bucket_name, version)
);

CREATE INDEX IF NOT EXISTS idx_buckets_name ON buckets (bucket_name);
CREATE INDEX IF NOT EXISTS idx_buckets_current ON buckets (bucket_name) WHERE effective_to IS NULL;

-- Decision trace (itself historical fact; never alters prior Events)
CREATE TABLE IF NOT EXISTS bucket_decisions (
    id              BIGSERIAL PRIMARY KEY,
    decision_id     UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    bucket_id       UUID NOT NULL REFERENCES buckets(id),
    proposed_edge   JSONB NOT NULL,                   -- the Edge that was evaluated
    outcome         TEXT NOT NULL CHECK (outcome IN ('PERMIT', 'REFUSE')),
    reason          TEXT,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    correlation_id  UUID
);

CREATE INDEX IF NOT EXISTS idx_bucket_decisions_bucket ON bucket_decisions (bucket_id);
CREATE INDEX IF NOT EXISTS idx_bucket_decisions_outcome ON bucket_decisions (outcome);

-- Deterministic evaluator for Buckets
CREATE OR REPLACE FUNCTION evaluate_bucket(
    p_bucket_name TEXT,
    p_proposed_edge JSONB,
    p_projection JSONB DEFAULT '{}'::jsonb
) RETURNS TEXT AS $$
DECLARE
    b RECORD;
    body JSONB;
    sla_hours NUMERIC;
    residual NUMERIC;
    required_perm TEXT;
    target_rank TEXT;
    from_layer INT;
    to_layer INT;
BEGIN
    SELECT * INTO b
    FROM buckets
    WHERE bucket_name = p_bucket_name AND effective_to IS NULL
    ORDER BY version DESC
    LIMIT 1;

    IF NOT FOUND THEN
        -- Unknown bucket = refuse by default (fail closed)
        RETURN 'REFUSE';
    END IF;

    body := b.constraint_body;

    -- 1. SLA horizon
    IF p_bucket_name = 'SLA_horizon' THEN
        sla_hours := COALESCE((body->>'max_hours')::NUMERIC, 24);
        IF (p_proposed_edge->'props'->>'expected_hours')::NUMERIC > sla_hours THEN
            RETURN 'REFUSE';
        END IF;
        RETURN 'PERMIT';
    END IF;

    -- 2. Residual capacity
    IF p_bucket_name = 'residual_capacity' THEN
        residual := COALESCE((body->>'remaining')::NUMERIC, 0);
        IF residual <= 0 THEN
            RETURN 'REFUSE';
        END IF;
        RETURN 'PERMIT';
    END IF;

    -- 3. Permission set
    IF p_bucket_name = 'permission_set' THEN
        required_perm := p_proposed_edge->'props'->>'required_permission';
        IF required_perm IS NOT NULL AND NOT (body->'allowed' ? required_perm) THEN
            RETURN 'REFUSE';
        END IF;
        RETURN 'PERMIT';
    END IF;

    -- 4. Rank classification
    IF p_bucket_name = 'rank_classification' THEN
        target_rank := p_proposed_edge->'props'->>'rank';
        IF target_rank IS NOT NULL AND NOT (body->'allowed_ranks' ? target_rank) THEN
            RETURN 'REFUSE';
        END IF;
        RETURN 'PERMIT';
    END IF;

    -- 5. Topological layer (source to derivative rule)
    IF p_bucket_name = 'topological_layer' THEN
        IF (p_proposed_edge->'props'->>'violates_layer')::BOOLEAN = true THEN
            RETURN 'REFUSE';
        END IF;
        RETURN 'PERMIT';
    END IF;

    -- 6. Content mutation vs representational identity
    IF p_bucket_name = 'content_mutation' THEN
        -- Identity cannot be changed, only dynamic content
        IF (p_proposed_edge->'props'->>'mutates_identity')::BOOLEAN = true THEN
            RETURN 'REFUSE';
        END IF;
        RETURN 'PERMIT';
    END IF;

    -- Default permit
    RETURN 'PERMIT';
END;
$$ LANGUAGE plpgsql;

-- Atomic gate: evaluate -> record decision -> return outcome
CREATE OR REPLACE FUNCTION gate_edge(
    p_bucket_names TEXT[],
    p_proposed_edge JSONB,
    p_projection JSONB DEFAULT '{}'::jsonb,
    p_correlation_id UUID DEFAULT NULL
) RETURNS TABLE(outcome TEXT, decision_ids UUID[]) AS $$
DECLARE
    bname TEXT;
    res TEXT;
    bid UUID;
    did UUID;
    all_permit BOOLEAN := TRUE;
    ids UUID[] := '{}';
BEGIN
    FOREACH bname IN ARRAY p_bucket_names
    LOOP
        res := evaluate_bucket(bname, p_proposed_edge, p_projection);
        SELECT id INTO bid FROM buckets
        WHERE bucket_name = bname AND effective_to IS NULL
        ORDER BY version DESC LIMIT 1;

        IF bid IS NULL THEN
            all_permit := FALSE;
            res := 'REFUSE';
        END IF;

        INSERT INTO bucket_decisions (bucket_id, proposed_edge, outcome, reason, correlation_id)
        VALUES (COALESCE(bid, '00000000-0000-0000-0000-000000000000'::uuid),
                p_proposed_edge, res,
                CASE WHEN res = 'REFUSE' THEN 'constraint_failed:' || bname ELSE 'ok' END,
                p_correlation_id)
        RETURNING decision_id INTO did;

        ids := array_append(ids, did);
        IF res = 'REFUSE' THEN
            all_permit := FALSE;
        END IF;
    END LOOP;

    IF all_permit THEN
        outcome := 'PERMIT';
    ELSE
        outcome := 'REFUSE';
    END IF;
    decision_ids := ids;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE buckets IS 'Versioned constraint domains. Facts, not process steps. Gate emission only.';
COMMENT ON TABLE bucket_decisions IS 'Historical decision traces. Never rewrite prior Events.';
COMMENT ON FUNCTION evaluate_bucket IS 'Deterministic: same version + proposed Edge + Projection -> same permit/refuse.';
COMMENT ON FUNCTION gate_edge IS 'Atomic evaluation boundary. REFUSE produces no Edge/Event/Projection change.';
