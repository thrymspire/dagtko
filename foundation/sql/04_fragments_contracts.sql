-- Fragment formalization + Contract declaration surfaces
-- Birth only by creation Edge. Contracts are annotations until composition is required.

-- ============================================================
-- Fragments (primary unit of scale)
-- ============================================================
CREATE TABLE IF NOT EXISTS fragments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    root_node_id    UUID NOT NULL REFERENCES nodes(id) UNIQUE,
    creation_edge_id UUID REFERENCES edges(id),
    event_slice_start BIGINT,                         -- events.id lower bound
    event_slice_end   BIGINT,                         -- events.id upper bound (null = open)
    props           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fragments_root ON fragments (root_node_id);

-- Designate existing WorkOrder as first Fragment (seed recognition)
CREATE OR REPLACE FUNCTION recognize_seed_fragment(p_root_id UUID)
RETURNS UUID AS $$
DECLARE
    frag_id UUID;
    create_edge UUID;
    first_ev BIGINT;
BEGIN
    SELECT id INTO create_edge
    FROM edges
    WHERE to_node_id = p_root_id AND edge_type = 'Creates'
    ORDER BY occurred_at ASC
    LIMIT 1;

    SELECT MIN(id) INTO first_ev FROM events WHERE node_id = p_root_id;

    INSERT INTO fragments (root_node_id, creation_edge_id, event_slice_start, props)
    VALUES (p_root_id, create_edge, first_ev, '{"seed": true}'::jsonb)
    ON CONFLICT (root_node_id) DO UPDATE
        SET creation_edge_id = EXCLUDED.creation_edge_id
    RETURNING id INTO frag_id;

    RETURN frag_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Contracts (sole legal crossing points)
-- ============================================================
CREATE TABLE IF NOT EXISTS contracts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fragment_id     UUID NOT NULL REFERENCES fragments(id),
    contract_name   TEXT NOT NULL,
    boundary_node_ids UUID[] NOT NULL DEFAULT '{}',
    allowed_edge_types TEXT[] NOT NULL DEFAULT '{}',
    projection_shape JSONB NOT NULL DEFAULT '{}'::jsonb,  -- static required shape
    published       BOOLEAN NOT NULL DEFAULT false,
    props           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fragment_id, contract_name)
);

CREATE INDEX IF NOT EXISTS idx_contracts_fragment ON contracts (fragment_id);
CREATE INDEX IF NOT EXISTS idx_contracts_published ON contracts (published) WHERE published = true;

COMMENT ON TABLE fragments IS 'Bounded purposeful DAG. Birth by creation Edge only.';
COMMENT ON TABLE contracts IS 'Declared interface. Discoverable before join. Mismatch → non-destructive refusal.';
COMMENT ON FUNCTION recognize_seed_fragment IS 'Domain act: designate root, bind Event slice, confirm Projection surface.';
