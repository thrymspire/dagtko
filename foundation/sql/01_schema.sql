-- DAG Substrate Core Schema
-- Character: append-only Events + Edges; Projections are derived only.
-- No mutation of historical rows. Replay reconstructs every Projection.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- NODES  (identifiable participants)
-- ============================================================
CREATE TABLE IF NOT EXISTS nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type       TEXT NOT NULL,                    -- WorkOrder, Technician, ApprovalGate, Status, Customer, ...
    external_ref    TEXT,                             -- optional business key
    props           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- stable identity; never updated in place for process progress
    CONSTRAINT nodes_type_check CHECK (node_type <> '')
);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes (node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_external ON nodes (external_ref) WHERE external_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_nodes_props ON nodes USING GIN (props);

-- ============================================================
-- EDGES  (typed directed relations = every business action)
-- ============================================================
CREATE TABLE IF NOT EXISTS edges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edge_type       TEXT NOT NULL,                    -- Creates, Approves, Assigns, Consumes, Updates, Notifies, ...
    from_node_id    UUID NOT NULL REFERENCES nodes(id),
    to_node_id      UUID NOT NULL REFERENCES nodes(id),
    props           JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id  UUID,                             -- links related edges / saga
    causation_id    UUID,                             -- parent edge that caused this one
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- historical; never updated or deleted
    CONSTRAINT edges_type_check CHECK (edge_type <> ''),
    CONSTRAINT edges_no_self CHECK (from_node_id <> to_node_id)
);

CREATE INDEX IF NOT EXISTS idx_edges_type ON edges (edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges (from_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges (to_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_correlation ON edges (correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_edges_occurred ON edges (occurred_at);

-- ============================================================
-- EVENTS  (append-only occurrence log)
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL PRIMARY KEY,            -- total order
    event_id        UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    event_type      TEXT NOT NULL,                    -- mirrors edge_type or system events
    edge_id         UUID REFERENCES edges(id),        -- the Edge that produced this Event (nullable for pure system)
    node_id         UUID REFERENCES nodes(id),        -- primary subject
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id  UUID,
    causation_id    UUID,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    -- NEVER UPDATE OR DELETE. Replay source of truth.
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_edge ON events (edge_id) WHERE edge_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_node ON events (node_id) WHERE node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_correlation ON events (correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_recorded ON events (recorded_at);

-- ============================================================
-- Helper: enforce append-only character at DB level
-- ============================================================
CREATE OR REPLACE FUNCTION refuse_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'DAG substrate invariant violation: historical rows (%, %) are append-only. Use new Edges/Events.',
        TG_TABLE_NAME, COALESCE(OLD.id::text, 'unknown');
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edges_no_update ON edges;
CREATE TRIGGER trg_edges_no_update
    BEFORE UPDATE OR DELETE ON edges
    FOR EACH ROW EXECUTE FUNCTION refuse_mutation();

DROP TRIGGER IF EXISTS trg_events_no_update ON events;
CREATE TRIGGER trg_events_no_update
    BEFORE UPDATE OR DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION refuse_mutation();

-- Nodes may receive property enrichment only via new Edges; direct prop mutation for process state is forbidden by convention.
-- (We leave nodes updatable for non-process metadata; domain code must never use it for progress.)

COMMENT ON TABLE nodes IS 'Identifiable participants. Process progress is expressed only by Edges.';
COMMENT ON TABLE edges IS 'Typed directed relations. Every business action becomes an Edge.';
COMMENT ON TABLE events IS 'Append-only occurrence log. Sole source for Projection reconstruction.';
