#!/usr/bin/env python3
"""
Generate complete 250-node / 501-edge / 90-matrix 05_seed.sql from ledger-set-dag.json.
Enriches all symbol nodes (18 phase glyphs, 6 composite emblems, 2 special symbols)
with standalone SVG geometry, SVG viewBoxes, and base64 data URIs.
Preserves strict source-to-derivative topological direction across all 7 layers.
"""

import json
import uuid
import sys
import os
import re
import base64

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "ledger-set-dag.json")
OUTPUT_SQL = os.path.join(SCRIPT_DIR, "05_seed.sql")
ASSETS_DIR = os.path.join(SCRIPT_DIR, "..", "visualizer", "assets", "glyphs")

LEDGER_NS = uuid.UUID("a1000000-0000-4000-8000-000000000000")

def get_node_uuid(node_id: str) -> uuid.UUID:
    return uuid.uuid5(LEDGER_NS, f"node:{node_id}")

def get_edge_uuid(source: str, target: str, rel: str) -> uuid.UUID:
    return uuid.uuid5(LEDGER_NS, f"edge:{source}->{target}:{rel}")

def get_event_uuid(source: str, target: str, rel: str) -> uuid.UUID:
    return uuid.uuid5(LEDGER_NS, f"event:{source}->{target}:{rel}")

def escape_sql_str(val: str) -> str:
    return val.replace("'", "''")

def symbol_to_standalone_svg(sym_text: str, stroke_color: str = "#5ffbf1", bg_color: str = "#0a0512") -> tuple[str, str, str]:
    if not sym_text:
        return "", "", "0 0 100 100"
    vb_match = re.search(r"viewBox=[\"\']([^\"\']+)[\"\']", sym_text)
    viewBox = vb_match.group(1) if vb_match else "0 0 100 100"
    inner = re.sub(r"<\/?symbol[^>]*>", "", sym_text).strip()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewBox}">
<style>
.ln {{ fill:none; stroke:{stroke_color}; stroke-width:2.5; stroke-linecap:round; stroke-linejoin:round; }}
.ln-thin {{ fill:none; stroke:{stroke_color}; stroke-width:1.5; stroke-linecap:round; }}
.dot-open {{ fill:{bg_color}; stroke:{stroke_color}; stroke-width:2; }}
.dot-fill {{ fill:{stroke_color}; stroke:none; }}
.dot-echo {{ fill:none; stroke:{stroke_color}; stroke-width:2; stroke-dasharray:3 3; }}
.spine-reinforced {{ stroke:#9d5cff; stroke-width:3; stroke-linecap:round; }}
.spine-crack {{ stroke:#ff79c6; stroke-width:2.5; }}
.spine-faint {{ stroke:rgba(95,251,241,0.6); stroke-width:1.5; stroke-dasharray:2 2; }}
</style>
{inner}
</svg>"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    data_uri = f"data:image/svg+xml;base64,{b64}"
    return svg, data_uri, viewBox

def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    print(f"Processing {len(nodes)} nodes and {len(edges)} edges from ledger-set-dag.json...")

    symbol_map = {}
    for n in nodes:
        sym_geom = n.get("svg_geometry")
        if sym_geom:
            sym_id = n.get("svg_symbol_id") or n["id"]
            stroke = "#ffb86c" if n.get("type") == "object_symbol" else ("#ff79c6" if "master" in n.get("type", "") else "#5ffbf1")
            svg_str, data_uri, vb = symbol_to_standalone_svg(sym_geom, stroke_color=stroke)
            n["svg_standalone"] = svg_str
            n["svg_data_uri"] = data_uri
            n["svg_viewbox"] = vb
            symbol_map[sym_id] = {"svg": svg_str, "data_uri": data_uri}
            
            # Save SVG file for Graphviz and static file renderers
            svg_filename = f"{sym_id}.svg"
            svg_filepath = os.path.join(ASSETS_DIR, svg_filename)
            with open(svg_filepath, "w", encoding="utf-8") as sf:
                sf.write(svg_str)

    # Enrich matrix entries with their linked glyph/emblem data URIs
    for n in nodes:
        if n.get("type") == "matrix_entry":
            phase_sym = n.get("svg_phase_symbol_id")
            obj_sym = n.get("svg_object_symbol_id")
            if phase_sym in symbol_map:
                n["svg_phase_data_uri"] = symbol_map[phase_sym]["data_uri"]
            if obj_sym in symbol_map:
                n["svg_object_data_uri"] = symbol_map[obj_sym]["data_uri"]

    sql_lines = []
    sql_lines.append("-- ==========================================================================")
    sql_lines.append("-- Complete Ledger Set Seed (250 Nodes, 501 Edges, 90 Matrix, 18 Glyphs, 6 Emblems)")
    sql_lines.append("-- Sole seed of the substrate. Symbol-centric representation.")
    sql_lines.append("-- Topological Layers 0-6 enforced. Index functions are immutable rank surfaces.")
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
    sql_lines.append("ON CONFLICT (id) DO UPDATE SET props = EXCLUDED.props, external_ref = EXCLUDED.external_ref, node_type = EXCLUDED.node_type;\n")

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

    # 3. Insert Events
    sql_lines.append("-- 3. EVENTS INSERTION (Append-only occurrence log)")
    sql_lines.append("INSERT INTO events (event_id, event_type, edge_id, node_id, payload, correlation_id, occurred_at) VALUES")
    event_tuples = []
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

    # 4. Buckets
    sql_lines.append("-- 4. BUCKET CONSTRAINTS")
    sql_lines.append("""INSERT INTO buckets (bucket_name, version, constraint_body) VALUES
    ('rank_classification', 1, '{"allowed_ranks":["Prime","Core","Echo"],"immutable_representation":true,"index_only_functions":["Vector","Pivot","Draft"]}'::jsonb),
    ('topological_layer',   1, '{"direction":"source_to_derivative","acyclic":true,"max_layers":7}'::jsonb),
    ('content_mutation',    1, '{"content_mutable":true,"representation_immutable":true}'::jsonb),
    ('SLA_horizon',         1, '{"max_hours":48}'::jsonb),
    ('residual_capacity',   1, '{"remaining":100}'::jsonb),
    ('permission_set',      1, '{"allowed":["admin","agent_autogen","agent_adk","operator"]}'::jsonb)
ON CONFLICT (bucket_name, version) DO UPDATE SET constraint_body = EXCLUDED.constraint_body;
""")

    # 5. Fragment Recognition
    sql_lines.append("-- 5. FRAGMENT RECOGNITION")
    sql_lines.append(f"""
DO $$
DECLARE
    root_nid UUID := '{root_node_uuid}';
    frag_id  UUID;
BEGIN
    INSERT INTO fragments (root_node_id, creation_edge_id, event_slice_start, props)
    VALUES (root_nid, NULL, 1, '{{"title":"The Ledger Set / Typhen Root Fragment","seed":true,"matrix_entries":90,"glyph_count":18,"emblem_count":6}}'::jsonb)
    ON CONFLICT (root_node_id) DO UPDATE SET props = EXCLUDED.props
    RETURNING id INTO frag_id;
END $$;
""")

    # 6. Build Projections
    sql_lines.append("-- 6. BUILD PROJECTIONS")
    sql_lines.append("""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'replay_ledger_projection') THEN
        PERFORM replay_ledger_projection();
    END IF;
END $$;
""")

    sql_lines.append("COMMIT;\n")

    with open(OUTPUT_SQL, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines))

    print(f"Successfully generated {OUTPUT_SQL} with SVG symbol metadata.")

if __name__ == "__main__":
    main()
