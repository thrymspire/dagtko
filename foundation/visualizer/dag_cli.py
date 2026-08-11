#!/usr/bin/env python3
"""
DAG Substrate — Terminal ASCII & Graphviz DOT CLI Visualizer
Fast zero-overhead terminal inspection of the full 250-node Ledger Set DAG.
"""

import os
import sys
import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "dag")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dag_substrate")
POSTGRES_DB = os.getenv("POSTGRES_DB", "dag_substrate")


def main():
    ports = [POSTGRES_PORT, 5432, 5433]
    conn = None
    for p in ports:
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=p,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB,
                connect_timeout=2,
            )
            break
        except Exception:
            continue

    if not conn:
        print("Error: Could not connect to PostgreSQL database.")
        sys.exit(1)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, node_type, external_ref, props FROM nodes ORDER BY created_at;")
        nodes = cur.fetchall()

        cur.execute("SELECT from_node_id, to_node_id, edge_type FROM edges ORDER BY occurred_at;")
        edges = cur.fetchall()

        cur.execute("SELECT * FROM matrix_entry_state ORDER BY indexed_asset ASC LIMIT 10;")
        matrix_sample = cur.fetchall()

        cur.execute("SELECT count(*) FROM matrix_entry_state;")
        matrix_total = cur.fetchone()["count"]

    node_map = {}
    for n in nodes:
        nid = str(n["id"])
        props = n.get("props") or {}
        ref = props.get("label") or props.get("indexed_asset") or n.get("external_ref") or nid[:8]
        node_map[nid] = f"{n['node_type']}:{ref}"

    print("\n" + "=" * 65)
    print("      LEDGER SET DAG SUBSTRATE — TOPOLOGY SUMMARY")
    print("=" * 65)
    print(f"  Total Nodes in DAG       : {len(nodes)}")
    print(f"  Total Directed Edges     : {len(edges)}")
    print(f"  Complete 90-Matrix Set   : {matrix_total} entries")
    print("-" * 65)

    print("Sample Layer Relationships:")
    for e in edges[:12]:
        src = node_map.get(str(e["from_node_id"]), str(e["from_node_id"])[:8])
        dst = node_map.get(str(e["to_node_id"]), str(e["to_node_id"])[:8])
        print(f"  [{src}]  ──({e['edge_type']})──>  [{dst}]")
    print(f"  ... (+ {len(edges)-12} more edges across 7 layers)")

    print("\n" + "=" * 65)
    print("      PROJECTION SAMPLE: matrix_entry_state (90-Matrix)")
    print("=" * 65)
    for row in matrix_sample:
        print(f"  [{row['indexed_asset']}] {row['function_tag']}-{row['outcome_number']} | Rank: {row['rank']} | Phase: {row['phase']}")
        print(f"     Outcome: {row['outcome_label']}")
        print(f"     Action : {row['actionable_statement'][:85]}...")
        print("-" * 65)

    # Generate Graphviz DOT
    dot = [
        "digraph LedgerSetDAG {",
        '  rankdir="TB";',
        '  bgcolor="#0a0512";',
        '  node [shape=box, style="filled,rounded", fontname="Helvetica", color="#ffffff", fontcolor="#ffffff", fontsize=8];',
        '  edge [color="#5ffbf1", fontcolor="#d8c6ff", fontsize=7];',
    ]

    LAYER_COLORS = {
        0: "#ff79c6",
        1: "#bd93f9",
        2: "#5ffbf1",
        3: "#50fa7b",
        4: "#ffb86c",
        5: "#9d5cff",
        6: "#8be9fd",
    }

    for n in nodes:
        nid = str(n["id"])
        props = n.get("props") or {}
        lyr = props.get("layer", 0)
        lbl = node_map[nid].replace('"', '\\"')
        col = LAYER_COLORS.get(lyr, "#bd93f9")
        text_col = "#000000" if lyr in (1, 2, 3, 4, 6) else "#ffffff"
        dot.append(f'  "{nid}" [label="{lbl}", fillcolor="{col}", fontcolor="{text_col}"];')

    for e in edges:
        dot.append(f'  "{e["from_node_id"]}" -> "{e["to_node_id"]}" [label="{e["edge_type"]}"];')

    dot.append("}")
    dot_content = "\n".join(dot)

    with open("dag.dot", "w") as f:
        f.write(dot_content)
    print("\nExported Graphviz DOT representation to dag.dot")

    if os.system("which dot >/dev/null 2>&1") == 0:
        os.system("dot -Tpng dag.dot -o dag_dot.png 2>/dev/null || true")
        os.system("dot -Tsvg dag.dot -o dag_dot.svg 2>/dev/null || true")
        print("Rendered: dag_dot.png, dag_dot.svg")

    conn.close()


if __name__ == "__main__":
    main()
