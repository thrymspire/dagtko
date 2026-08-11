-- Derived current-truth surfaces. Never authoritative history.
-- All consumers (MCP, Matlab, dashboards, future Contracts/Buckets) read only Projections.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. Ledger Node Current State (Full Topology Projection)
-- ============================================================
CREATE TABLE IF NOT EXISTS ledger_node_state (
    node_id             UUID PRIMARY KEY REFERENCES nodes(id),
    external_ref        TEXT,
    node_type           TEXT NOT NULL,
    layer               INTEGER NOT NULL DEFAULT 0,
    label               TEXT,
    status              TEXT NOT NULL DEFAULT 'Active',
    in_degree           INTEGER NOT NULL DEFAULT 0,
    out_degree          INTEGER NOT NULL DEFAULT 0,
    critical_path_len   NUMERIC DEFAULT 0,
    props               JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_edge_id        UUID,
    last_event_id       UUID,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ledger_node_type ON ledger_node_state (node_type);
CREATE INDEX IF NOT EXISTS idx_ledger_node_layer ON ledger_node_state (layer);
CREATE INDEX IF NOT EXISTS idx_ledger_node_status ON ledger_node_state (status);
CREATE INDEX IF NOT EXISTS idx_ledger_node_ref ON ledger_node_state (external_ref);

-- ============================================================
-- 2. 90-Matrix Entries Projection (Query & Reasoning Surface)
-- ============================================================
CREATE TABLE IF NOT EXISTS matrix_entry_state (
    entry_id            UUID PRIMARY KEY REFERENCES nodes(id),
    indexed_asset       TEXT NOT NULL,
    function_tag        TEXT NOT NULL,
    outcome_number      TEXT NOT NULL,
    outcome_label       TEXT,
    outcome_behavior    TEXT,
    rank                TEXT NOT NULL,
    phase               TEXT NOT NULL,
    actionable_statement TEXT,
    symbol_status       TEXT,
    svg_phase_symbol_id TEXT,
    svg_object_symbol_id TEXT,
    object_id           TEXT,
    props               JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_matrix_asset ON matrix_entry_state (indexed_asset);
CREATE INDEX IF NOT EXISTS idx_matrix_function ON matrix_entry_state (function_tag);
CREATE INDEX IF NOT EXISTS idx_matrix_outcome ON matrix_entry_state (outcome_number);
CREATE INDEX IF NOT EXISTS idx_matrix_rank ON matrix_entry_state (rank);
CREATE INDEX IF NOT EXISTS idx_matrix_phase ON matrix_entry_state (phase);

-- ============================================================
-- 3. WorkOrder current state (Compatibility Projection)
-- ============================================================
CREATE TABLE IF NOT EXISTS wo_current_state (
    work_order_id       UUID PRIMARY KEY REFERENCES nodes(id),
    external_ref        TEXT,
    status              TEXT NOT NULL DEFAULT 'Created',
    assigned_technician UUID REFERENCES nodes(id),
    approval_gate_id    UUID REFERENCES nodes(id),
    customer_id         UUID REFERENCES nodes(id),
    props               JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_edge_id        UUID,
    last_event_id       UUID,
    critical_path_len   NUMERIC,                      -- derived; never mutable business state
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wo_status ON wo_current_state (status);
CREATE INDEX IF NOT EXISTS idx_wo_tech ON wo_current_state (assigned_technician) WHERE assigned_technician IS NOT NULL;

-- ============================================================
-- Reducer: apply one Event to Projections
-- ============================================================
CREATE OR REPLACE FUNCTION project_ledger_event(p_event_id BIGINT)
RETURNS VOID AS $$
DECLARE
    e RECORD;
    n RECORD;
    in_deg INTEGER;
    out_deg INTEGER;
BEGIN
    SELECT * INTO e FROM events WHERE id = p_event_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Event % not found', p_event_id;
    END IF;

    IF e.node_id IS NOT NULL THEN
        SELECT * INTO n FROM nodes WHERE id = e.node_id;
        IF FOUND THEN
            SELECT count(*) INTO in_deg FROM edges WHERE to_node_id = n.id;
            SELECT count(*) INTO out_deg FROM edges WHERE from_node_id = n.id;

            INSERT INTO ledger_node_state (
                node_id, external_ref, node_type, layer, label, status,
                in_degree, out_degree, props, last_edge_id, last_event_id, updated_at
            )
            VALUES (
                n.id,
                n.external_ref,
                n.node_type,
                COALESCE((n.props->>'layer')::INTEGER, 0),
                COALESCE(n.props->>'label', n.external_ref, n.node_type),
                'Active',
                in_deg,
                out_deg,
                n.props,
                e.edge_id,
                e.event_id,
                now()
            )
            ON CONFLICT (node_id) DO UPDATE SET
                external_ref = EXCLUDED.external_ref,
                node_type = EXCLUDED.node_type,
                layer = EXCLUDED.layer,
                label = EXCLUDED.label,
                in_degree = EXCLUDED.in_degree,
                out_degree = EXCLUDED.out_degree,
                props = EXCLUDED.props,
                last_edge_id = EXCLUDED.last_edge_id,
                last_event_id = EXCLUDED.last_event_id,
                updated_at = now();

            IF n.node_type = 'matrix_entry' THEN
                INSERT INTO matrix_entry_state (
                    entry_id, indexed_asset, function_tag, outcome_number, outcome_label,
                    outcome_behavior, rank, phase, actionable_statement, symbol_status,
                    svg_phase_symbol_id, svg_object_symbol_id, object_id, props, updated_at
                )
                VALUES (
                    n.id,
                    COALESCE(n.props->>'indexed_asset', n.external_ref, ''),
                    COALESCE(n.props->>'function_tag', ''),
                    COALESCE(n.props->>'outcome_number', ''),
                    n.props->>'outcome_label',
                    n.props->>'outcome_behavior',
                    COALESCE(n.props->>'rank', 'Prime'),
                    COALESCE(n.props->>'phase', 'Initiation'),
                    n.props->>'actionable_statement',
                    n.props->>'symbol_status',
                    n.props->>'svg_phase_symbol_id',
                    n.props->>'svg_object_symbol_id',
                    n.props->>'object_id',
                    n.props,
                    now()
                )
                ON CONFLICT (entry_id) DO UPDATE SET
                    indexed_asset = EXCLUDED.indexed_asset,
                    function_tag = EXCLUDED.function_tag,
                    outcome_number = EXCLUDED.outcome_number,
                    outcome_label = EXCLUDED.outcome_label,
                    outcome_behavior = EXCLUDED.outcome_behavior,
                    rank = EXCLUDED.rank,
                    phase = EXCLUDED.phase,
                    actionable_statement = EXCLUDED.actionable_statement,
                    symbol_status = EXCLUDED.symbol_status,
                    svg_phase_symbol_id = EXCLUDED.svg_phase_symbol_id,
                    svg_object_symbol_id = EXCLUDED.svg_object_symbol_id,
                    object_id = EXCLUDED.object_id,
                    props = EXCLUDED.props,
                    updated_at = now();
            END IF;
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Deterministic reducer for WorkOrders
CREATE OR REPLACE FUNCTION project_wo_event(p_event_id BIGINT)
RETURNS VOID AS $$
DECLARE
    e RECORD;
    edge_rec RECORD;
    wo_id UUID;
BEGIN
    SELECT * INTO e FROM events WHERE id = p_event_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Event % not found', p_event_id;
    END IF;

    wo_id := e.node_id;
    IF wo_id IS NULL AND e.edge_id IS NOT NULL THEN
        SELECT from_node_id INTO wo_id FROM edges WHERE id = e.edge_id;
    END IF;
    IF wo_id IS NULL THEN
        RETURN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM nodes WHERE id = wo_id AND node_type = 'WorkOrder') THEN
        RETURN;
    END IF;

    INSERT INTO wo_current_state (work_order_id, external_ref, last_event_id, updated_at)
    SELECT wo_id, n.external_ref, e.event_id, now()
    FROM nodes n WHERE n.id = wo_id
    ON CONFLICT (work_order_id) DO UPDATE
        SET last_event_id = EXCLUDED.last_event_id,
            updated_at = now();

    IF e.event_type IN ('WorkOrderCreated', 'Creates') THEN
        UPDATE wo_current_state
        SET status = 'Created',
            props = COALESCE(e.payload, '{}'::jsonb),
            last_edge_id = e.edge_id
        WHERE work_order_id = wo_id;

    ELSIF e.event_type IN ('ApprovalRequested') THEN
        UPDATE wo_current_state
        SET status = 'PendingApproval',
            last_edge_id = e.edge_id
        WHERE work_order_id = wo_id;

    ELSIF e.event_type IN ('Approved', 'Approves') THEN
        UPDATE wo_current_state
        SET status = 'Approved',
            last_edge_id = e.edge_id
        WHERE work_order_id = wo_id;

    ELSIF e.event_type IN ('TechnicianAssigned', 'Assigns') THEN
        IF e.edge_id IS NOT NULL THEN
            SELECT to_node_id INTO edge_rec FROM edges WHERE id = e.edge_id;
            UPDATE wo_current_state
            SET status = 'Assigned',
                assigned_technician = edge_rec.to_node_id,
                last_edge_id = e.edge_id
            WHERE work_order_id = wo_id;
        END IF;

    ELSIF e.event_type IN ('ExecutionStarted') THEN
        UPDATE wo_current_state
        SET status = 'InExecution',
            last_edge_id = e.edge_id
        WHERE work_order_id = wo_id;

    ELSIF e.event_type IN ('Completed', 'Consumes') THEN
        UPDATE wo_current_state
        SET status = 'Completed',
            last_edge_id = e.edge_id
        WHERE work_order_id = wo_id;

    ELSIF e.event_type IN ('Rejected', 'Cancelled') THEN
        UPDATE wo_current_state
        SET status = e.event_type,
            last_edge_id = e.edge_id
        WHERE work_order_id = wo_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Full replay of Ledger Projections
CREATE OR REPLACE FUNCTION replay_ledger_projection()
RETURNS INTEGER AS $$
DECLARE
    ev RECORD;
    cnt INTEGER := 0;
BEGIN
    TRUNCATE ledger_node_state;
    TRUNCATE matrix_entry_state;
    FOR ev IN SELECT id FROM events ORDER BY id ASC
    LOOP
        PERFORM project_ledger_event(ev.id);
        cnt := cnt + 1;
    END LOOP;
    RETURN cnt;
END;
$$ LANGUAGE plpgsql;

-- Full replay of WorkOrder Projections
CREATE OR REPLACE FUNCTION replay_wo_projection()
RETURNS INTEGER AS $$
DECLARE
    ev RECORD;
    cnt INTEGER := 0;
BEGIN
    TRUNCATE wo_current_state;
    FOR ev IN SELECT id FROM events ORDER BY id ASC
    LOOP
        PERFORM project_wo_event(ev.id);
        cnt := cnt + 1;
    END LOOP;
    RETURN cnt;
END;
$$ LANGUAGE plpgsql;

-- Critical path computation
CREATE OR REPLACE FUNCTION compute_critical_path_len(p_root_id UUID)
RETURNS NUMERIC AS $$
DECLARE
    max_len NUMERIC := 0;
BEGIN
    WITH RECURSIVE paths AS (
        SELECT e.to_node_id AS node_id, 1 AS depth
        FROM edges e
        WHERE e.from_node_id = p_root_id
        UNION ALL
        SELECT e.to_node_id, p.depth + 1
        FROM paths p
        JOIN edges e ON e.from_node_id = p.node_id
        WHERE p.depth < 100
    )
    SELECT COALESCE(MAX(depth), 0) INTO max_len FROM paths;

    UPDATE ledger_node_state
    SET critical_path_len = max_len,
        updated_at = now()
    WHERE node_id = p_root_id;

    UPDATE wo_current_state
    SET critical_path_len = max_len,
        updated_at = now()
    WHERE work_order_id = p_root_id;

    RETURN max_len;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE ledger_node_state IS 'Sole readable current truth for all Ledger Set DAG nodes.';
COMMENT ON TABLE matrix_entry_state IS 'Query and reasoning projection for all 90 matrix entries.';
COMMENT ON TABLE wo_current_state IS 'Compatibility projection for WorkOrders.';
