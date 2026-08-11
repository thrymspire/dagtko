#!/usr/bin/env python3
"""
DAG Substrate — Terminal CLI Inspector & Graphviz DOT Exporter
Symbol-centric inspection: Phase Glyphs and Composite Emblems embed their SVG symbol references.
Generates ASCII topology summary, 90-Matrix projection sample, and compiles dag.dot / dag_dot.png / dag_dot.svg.
"""

import os
import sys
import subprocess
import psycopg2
import psycopg2.extras

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "dag")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dag_substrate")
POSTGRES_DB = os.getenv("POSTGRES_DB", "dag_substrate")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets", "glyphs")
DOT_PATH = os.path.join(SCRIPT_DIR, "..", "dag.dot")
DOT_PNG = os.path.join(SCRIPT_DIR, "..", "dag_dot.png")
DOT_SVG = os.path.join(SCRIPT_DIR, "..", "dag_dot.svg")
ROOT_DOT = os.path.join(SCRIPT_DIR, "..", "..", "dag.dot")
ROOT_DOT_PNG = os.path.join(SCRIPT_DIR, "..", "..", "dag_dot.png")
ROOT_DOT_SVG = os.path.join(SCRIPT_DIR, "..", "..", "dag_dot.svg")


def main():
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
    )
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT count(*) AS total_nodes FROM nodes;")
            total_nodes = cur.fetchone()["total_nodes"]

            cur.execute("SELECT count(*) AS total_edges FROM edges;")
            total_edges = cur.fetchone()["total_edges"]

            cur.execute("SELECT count(*) AS symbol_nodes FROM ledger_node_state WHERE svg_symbol_id IS NOT NULL;")
            symbol_nodes = cur.fetchone()["symbol_nodes"]

            cur.execute("SELECT count(*) AS matrix_count FROM matrix_entry_state;")
            matrix_count = cur.fetchone()["matrix_count"]

            print("\n=================================================================")
            print("      LEDGER SET DAG SUBSTRATE — SYMBOL-CENTRIC TOPOLOGY")
            print("=================================================================")
            print(f"  Total Nodes in DAG       : {total_nodes}")
            print(f"  Total Directed Edges     : {total_edges}")
            print(f"  First-Class SVG Symbols  : {symbol_nodes} (18 Glyphs + 6 Emblems + 2 Specials)")
            print(f"  Complete 90-Matrix Set   : {matrix_count} entries")
            print("-----------------------------------------------------------------")
            print("Sample Layer Relationships:")

            cur.execute("""
                SELECT 
                    fn.props->>'label' AS from_label,
                    fn.node_type AS from_type,
                    e.edge_type,
                    tn.props->>'label' AS to_label,
                    tn.node_type AS to_type
                FROM edges e
                JOIN nodes fn ON e.from_node_id = fn.id
                JOIN nodes tn ON e.to_node_id = tn.id
                ORDER BY e.occurred_at ASC
                LIMIT 12;
            """)
            for row in cur.fetchall():
                fl = row["from_label"] or row["from_type"]
                tl = row["to_label"] or row["to_type"]
                print(f"  [{row['from_type']}:{fl}]  ──({row['edge_type']})──>  [{row['to_type']}:{tl}]")

            print(f"  ... (+ {total_edges - 12} more edges across 7 layers)")

            print("\n=================================================================")
            print("      PROJECTION SAMPLE: matrix_entry_state (90-Matrix)")
            print("=================================================================")
            cur.execute("""
                SELECT indexed_asset, function_tag, outcome_number, outcome_label,
                       rank, phase, actionable_statement, svg_phase_symbol_id
                FROM matrix_entry_state
                ORDER BY indexed_asset ASC
                LIMIT 6;
            """)
            for row in cur.fetchall():
                print(f"  [{row['indexed_asset']}] {row['function_tag']}-{row['outcome_number']} | Rank: {row['rank']} | Phase: {row['phase']} | Symbol: {row['svg_phase_symbol_id']}")
                print(f"     Outcome: {row['outcome_label']}")
                act = row['actionable_statement'] or ''
                if len(act) > 90:
                    act = act[:87] + "..."
                print(f"     Action : {act}")
                print("-----------------------------------------------------------------")

            # Generate Graphviz DOT with SVG symbol formatting
            cur.execute("SELECT node_id, external_ref, node_type, layer, label, svg_symbol_id FROM ledger_node_state;")
            nodes = cur.fetchall()

            cur.execute("SELECT from_node_id, to_node_id, edge_type FROM edges;")
            edges = cur.fetchall()

            dot_lines = []
            dot_lines.append("digraph LedgerSetDAG {")
            dot_lines.append('  graph [rankdir=TB, bgcolor="#07030d", pad="0.5", nodesep="0.4", ranksep="0.8", fontname="Helvetica"];')
            dot_lines.append('  node [fontname="Helvetica", style="filled", shape="box", margin="0.15,0.1", penwidth="1.5"];')
            dot_lines.append('  edge [color="#5ffbf155", arrowhead="vee", arrowsize="0.75", penwidth="0.8"];\n')

            layer_styles = {
                0: ('fillcolor="#ff79c6"', 'fontcolor="#ffffff"', 'color="#ffffff"'),
                1: ('fillcolor="#bd93f9"', 'fontcolor="#07030d"', 'color="#bd93f9"'),
                2: ('fillcolor="#5ffbf1"', 'fontcolor="#07030d"', 'color="#5ffbf1"'),
                3: ('fillcolor="#120626"', 'fontcolor="#5ffbf1"', 'color="#5ffbf1"'),
                4: ('fillcolor="#120626"', 'fontcolor="#ffb86c"', 'color="#ffb86c"'),
                5: ('fillcolor="#9d5cff"', 'fontcolor="#ffffff"', 'color="#ede6ff"'),
                6: ('fillcolor="#8be9fd"', 'fontcolor="#07030d"', 'color="#8be9fd"'),
            }

            for n in nodes:
                nid = str(n["node_id"]).replace("-", "_")
                lbl = (n["label"] or n["external_ref"] or "").replace('"', '\\"')
                layer = n.get("layer", 0)
                sym_id = n.get("svg_symbol_id")
                fill, font, border = layer_styles.get(layer, ('fillcolor="#9d5cff"', 'fontcolor="#ffffff"', 'color="#ffffff"'))

                if sym_id:
                    svg_file = os.path.join(ASSETS_DIR, f"{sym_id}.svg")
                    # Graphviz HTML-like label displaying symbol tag
                    dot_lines.append(f'  n_{nid} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" BGCOLOR="#120626" COLOR="{border.split("=")[1].strip(chr(34))}"><TR><TD><FONT COLOR="{font.split("=")[1].strip(chr(34))}" POINT-SIZE="8"><B>✦ {sym_id}</B></FONT></TD></TR><TR><TD><FONT COLOR="#ede6ff" POINT-SIZE="7">{lbl}</FONT></TD></TR></TABLE>>, shape="none"];')
                else:
                    dot_lines.append(f'  n_{nid} [label="{lbl}", {fill}, {font}, {border}];')

            for e in edges:
                fn = str(e["from_node_id"]).replace("-", "_")
                tn = str(e["to_node_id"]).replace("-", "_")
                dot_lines.append(f'  n_{fn} -> n_{tn};')

            dot_lines.append("}\n")
            dot_content = "\n".join(dot_lines)

            for target in (DOT_PATH, ROOT_DOT):
                with open(target, "w", encoding="utf-8") as df:
                    df.write(dot_content)

            print(f"\nExported Graphviz DOT representation to {DOT_PATH}")

            if subprocess.run(["which", "dot"], stdout=subprocess.PIPE).returncode == 0:
                subprocess.run(["dot", "-Tpng", DOT_PATH, "-o", DOT_PNG], check=False)
                subprocess.run(["dot", "-Tsvg", DOT_PATH, "-o", DOT_SVG], check=False)
                if os.path.exists(os.path.dirname(ROOT_DOT_PNG)):
                    subprocess.run(["dot", "-Tpng", DOT_PATH, "-o", ROOT_DOT_PNG], check=False)
                    subprocess.run(["dot", "-Tsvg", DOT_PATH, "-o", ROOT_DOT_SVG], check=False)
                print(f"Rendered: {DOT_PNG}, {DOT_SVG}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
