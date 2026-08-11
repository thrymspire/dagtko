#!/usr/bin/env python3
import json
import uuid
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "ledger-set-dag.json")
OUTPUT_SQL = os.path.join(SCRIPT_DIR, "05_seed.sql")

LEDGER_NS = uuid.UUID("a1000000-0000-4000-8000-000000000000")

def get_node_uuid(node_id: str) -> uuid.UUID:
    return uuid.uuid5(LEDGER_NS, f"node:{node_id}")

def get_edge_uuid(source: str, target: str, rel: str) -> uuid.UUID:
    return uuid.uuid5(LEDGER_NS, f"edge:{source}->{target}:{rel}")

def get_event_uuid(source: str, target: str, rel: str) -> uuid.UUID:
    return uuid.uuid5(LEDGER_NS, f"event:{source}->{target}:{rel}")

def escape_sql_str(val: str) -> str:
    return val.replace("'", "''")

def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    print(f"Generating 05_seed.sql with {len(nodes)} nodes and {len(edges)} edges...")

    sql_lines = []
    sql_lines.append("-- ==========================================================================")
    sql_lines.append("-- Ledger Set Seed (Complete 90-Matrix + Glyphs + Emblems + Canonicals)")
    sql_lines.append("-- Auto-generated from ledger-set-dag.json (Full 250 nodes, 501 edges)")
    sql_lines.append("-- Implements immutable representational identity + dynamic mutable content")
    sql_lines.append("-- ==========================================================================\n")
    sql_lines.append("BEGIN;\n")

    # 1. Insert Nodes
    sql_lines.append("-- 1. NODES INSERTION (250 Nodes)")
    sql_lines.append("INSERT INTO nodes (id, node_type, external_ref, props, created_at) VALUES")
    node_tuples = []
    for n in nodes:
        nid = get_node_uuid(n["id"])
        ntype = n.get("type", "node")
        ext_ref = n["id"]
        props_json = json.dumps(n)
        node_tuples.append(f"('{nid}', '{escape_sql_str(ntype)}', '{escape_sql_str(ext_ref)}', '{escape_sql_str(props_json)}'::jsonb, now() - interval '2 hours')")
    sql_lines.append(",\n".join(node_tuples))
    sql_lines.append("ON CONFLICT (id) DO UPDATE SET props = EXCLUDED.props, external_ref = EXCLUDED.external_ref;\n")

    # 2. Insert Edges
    sql_lines.append("-- 2. EDGES INSERTION (501 Edges)")
    sql_lines.append("INSERT INTO edges (id, edge_type, from_node_id, to_node_id, props, correlation_id, occurred_at) VALUES")
    edge_tuples = []
    corr_id = uuid.uuid5(LEDGER_NS, "correlation:seed")
    for e in edges:
        eid = get_edge_uuid(e["source"], e["target"], e["relation"])
        from_id = get_node_uuid(e["source"])
        to_id = get_node_uuid(e["target"])
        etype = e.get("relation", "relates_to")
        props_json = json.dumps(e)
        edge_tuples.append(f"('{eid}', '{escape_sql_str(etype)}', '{from_id}', '{to_id}', '{escape_sql_str(props_json)}'::jsonb, '{corr_id}', now() - interval '1 hour')")
    sql_lines.append(",\n".join(edge_tuples))
    sql_lines.append("ON CONFLICT (id) DO NOTHING;\n")

    # 3. Insert Events for every initial edge/node
    sql_lines.append("-- 3. EVENTS INSERTION (Append-only occurrence log)")
    sql_lines.append("INSERT INTO events (event_id, event_type, edge_id, node_id, payload, correlation_id, occurred_at) VALUES")
    event_tuples = []
    # Root event
    root_node_uuid = get_node_uuid("ledger_root")
    root_ev_uuid = uuid.uuid5(LEDGER_NS, "event:root_creation")
    root_payload = json.dumps({"source": "ledger_set_seed", "action": "LedgerRootInitialized", "schema": data.get("schema", "ledger-set-dag/v1")})
    event_tuples.append(f"('{root_ev_uuid}', 'LedgerRootInitialized', NULL, '{root_node_uuid}', '{escape_sql_str(root_payload)}'::jsonb, '{corr_id}', now() - interval '2 hours')")

    for e in edges:
        ev_uuid = get_event_uuid(e["source"], e["target"], e["relation"])
        eid = get_edge_uuid(e["source"], e["target"], e["relation"])
        to_id = get_node_uuid(e["target"])
        etype = e.get("relation", "relates_to")
        payload_json = json.dumps({"event": etype, "source": e["source"], "target": e["target"], "props": e})
        event_tuples.append(f"('{ev_uuid}', '{escape_sql_str(etype)}', '{eid}', '{to_id}', '{escape_sql_str(payload_json)}'::jsonb, '{corr_id}', now() - interval '1 hour')")
    sql_lines.append(",\n".join(event_tuples))
    sql_lines.append("ON CONFLICT (event_id) DO NOTHING;\n")

    # 4. Insert Buckets
    sql_lines.append("-- 4. BUCKET CONSTRAINTS")
    sql_lines.append("""INSERT INTO buckets (bucket_name, version, constraint_body) VALUES
    ('rank_classification', 1, '{"allowed_ranks":["Prime","Core","Echo"],"immutable_representation":true}'::jsonb),
    ('topological_layer',   1, '{"direction":"source_to_derivative","acyclic":true,"max_layers":7}'::jsonb),
    ('content_mutation',    1, '{"content_mutable":true,"representation_immutable":true}'::jsonb),
    ('SLA_horizon',         1, '{"max_hours":48}'::jsonb),
    ('residual_capacity',   1, '{"remaining":100}'::jsonb),
    ('permission_set',      1, '{"allowed":["admin","agent_autogen","agent_adk","operator"]}'::jsonb)
ON CONFLICT (bucket_name, version) DO UPDATE SET constraint_body = EXCLUDED.constraint_body;
""")

    # 5. Recognize Root Fragment
    sql_lines.append("-- 5. FRAGMENT RECOGNITION")
    sql_lines.append(f"""
DO $$
DECLARE
    root_nid UUID := '{root_node_uuid}';
    frag_id  UUID;
BEGIN
    INSERT INTO fragments (root_node_id, creation_edge_id, event_slice_start, props)
    VALUES (root_nid, NULL, 1, '{{"title":"The Ledger Set / Typhen Root Fragment","seed":true,"matrix_entries":90,"glyph_count":18}}'::jsonb)
    ON CONFLICT (root_node_id) DO UPDATE SET props = EXCLUDED.props
    RETURNING id INTO frag_id;
END $$;
""")

    # 6. Replay and build projections
    sql_lines.append("-- 6. BUILD PROJECTIONS")
    sql_lines.append("""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'replay_ledger_projection') THEN
        PERFORM replay_ledger_projection();
    END IF;
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'replay_wo_projection') THEN
        PERFORM replay_wo_projection();
    END IF;
END $$;
""")

    sql_lines.append("COMMIT;\n")

    with open(OUTPUT_SQL, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines))

    print(f"Successfully generated {OUTPUT_SQL} ({len(sql_lines)} lines)")

if __name__ == "__main__":
    main()
