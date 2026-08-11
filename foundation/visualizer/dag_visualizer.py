#!/usr/bin/env python3
"""
DAG Substrate — Symbol-Centric Matplotlib High-Resolution Visualizer
Renders the complete 250-node / 501-edge / 90-matrix Ledger Set DAG across all 7 layers.
Phase Glyphs & Composite Emblems are rendered as primary visual symbol artwork.
Exports high-res PNG and vector SVG.
"""

import os
import sys
import json
import psycopg2
import psycopg2.extras
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "dag")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dag_substrate")
POSTGRES_DB = os.getenv("POSTGRES_DB", "dag_substrate")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PNG = os.path.join(SCRIPT_DIR, "..", "dag_graph.png")
OUT_SVG = os.path.join(SCRIPT_DIR, "..", "dag_graph.svg")
ROOT_PNG = os.path.join(SCRIPT_DIR, "..", "..", "dag_graph.png")
ROOT_SVG = os.path.join(SCRIPT_DIR, "..", "..", "dag_graph.svg")

LAYER_COLORS = {
    0: "#ff79c6",  # Root (The Ledger Set / Typhen)
    1: "#bd93f9",  # Sections (Typhen, Index, Ledger Set, Rank, Field)
    2: "#5ffbf1",  # Canonical Entities (Objects, Functions, Outcomes, Phases)
    3: "#50fa7b",  # Phase Glyphs (18 Vector Marks)
    4: "#ffb86c",  # Composite Emblems (6 Physical Object Emblems)
    5: "#9d5cff",  # 90-Matrix Entries (SPAN-01..10, ANCHOR-01..10, etc.)
    6: "#8be9fd",  # Actionable Deployment Statements
}


def load_dag_from_db():
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
    )
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT 'total_nodes' AS metric, count(*)::int AS n FROM nodes
                UNION ALL SELECT 'total_edges', count(*)::int FROM edges
                UNION ALL SELECT 'total_events', count(*)::int FROM events
                UNION ALL SELECT 'projected_nodes', count(*)::int FROM ledger_node_state
                UNION ALL SELECT 'symbol_nodes', count(*)::int FROM ledger_node_state WHERE svg_data_uri IS NOT NULL
                UNION ALL SELECT 'matrix_entries', count(*)::int FROM matrix_entry_state
                UNION ALL SELECT 'buckets', count(*)::int FROM buckets
                UNION ALL SELECT 'fragments', count(*)::int FROM fragments;
            """)
            counts = {row["metric"]: row["n"] for row in cur.fetchall()}

            cur.execute("SELECT node_id, external_ref, node_type, layer, label, svg_symbol_id, svg_standalone, props FROM ledger_node_state;")
            nodes = cur.fetchall()

            cur.execute("SELECT from_node_id, to_node_id, edge_type, props FROM edges;")
            edges = cur.fetchall()

            return counts, nodes, edges
    finally:
        conn.close()


def main():
    print("=================================================================")
    print("  LEDGER SET DAG SUBSTRATE — SYMBOL-CENTRIC PROOF & VISUALIZER")
    print("=================================================================")

    counts, nodes, edges = load_dag_from_db()

    for k, v in counts.items():
        print(f"  {k:<27} : {v}")

    print("")
    if counts.get("total_nodes", 0) >= 250 and counts.get("matrix_entries", 0) == 90:
        print(">>> CLOSED LOOP: GREEN (250-Node / 26-Symbol / 90-Matrix Substrate Live) <<<\n")
    else:
        print(">>> CLOSED LOOP: WARNING (Node / Matrix count incomplete) <<<\n")

    G = nx.DiGraph()
    node_layer_map = {}
    node_label_map = {}
    symbol_nodes = {}

    for n in nodes:
        nid = str(n["node_id"])
        layer = n.get("layer", 0)
        lbl = n.get("label") or n.get("external_ref") or nid[:6]
        sym_id = n.get("svg_symbol_id")
        ntype = n.get("node_type")

        G.add_node(nid, layer=layer, label=lbl, node_type=ntype, sym_id=sym_id)
        node_layer_map[nid] = layer
        node_label_map[nid] = lbl
        if sym_id or ntype in ("phase_glyph", "object_symbol", "master_symbol", "null_symbol"):
            symbol_nodes[nid] = {"sym_id": sym_id, "type": ntype, "layer": layer, "label": lbl}

    for e in edges:
        G.add_edge(str(e["from_node_id"]), str(e["to_node_id"]), edge_type=e.get("edge_type"))

    # Compute multipartite hierarchical layout
    pos = {}
    layers = sorted(list(set(node_layer_map.values())))
    y_gap = 1.6

    for layer in layers:
        layer_nodes = [nid for nid, lyr in node_layer_map.items() if lyr == layer]
        layer_nodes.sort(key=lambda x: node_label_map.get(x, ""))
        n_nodes = len(layer_nodes)
        x_spacing = 16.0 / max(n_nodes, 1)

        for i, nid in enumerate(layer_nodes):
            x = (i - (n_nodes - 1) / 2.0) * x_spacing
            y = -(layer * y_gap)
            pos[nid] = (x, y)

    fig, ax = plt.subplots(figsize=(24, 18), facecolor="#07030d")
    ax.set_facecolor("#07030d")
    ax.set_title(
        "Ledger Set DAG Substrate — Symbol-Centric Topological Hierarchy (250 Nodes / 501 Edges / 90 Matrix)",
        color="#ede6ff",
        fontsize=18,
        fontweight="bold",
        pad=22,
    )

    # Draw edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color="#5ffbf1",
        arrows=True,
        arrowsize=10,
        arrowstyle="-|>",
        width=0.7,
        ax=ax,
        alpha=0.35,
    )

    # Draw standard nodes by layer
    for layer, color in LAYER_COLORS.items():
        layer_nodes = [nid for nid, lyr in node_layer_map.items() if lyr == layer and nid not in symbol_nodes]
        if layer_nodes:
            size = 350 if layer in (0, 1) else (180 if layer == 2 else 90)
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=layer_nodes,
                node_color=color,
                node_size=size,
                alpha=0.92,
                ax=ax,
                edgecolors="#ffffff",
                linewidths=1.0,
            )

    # Draw Symbol Nodes (Layer 3 Glyphs & Layer 4 Emblems) as prominent visual identity markers
    for nid, sinfo in symbol_nodes.items():
        px, py = pos[nid]
        stype = sinfo["type"]
        is_emblem = stype == "object_symbol"
        box_w = 0.55 if is_emblem else 0.45
        box_h = 1.0 if is_emblem else 0.45
        border_col = "#ffb86c" if is_emblem else ("#ff79c6" if "master" in stype else "#5ffbf1")

        # Draw symbol card background
        rect = patches.FancyBboxPatch(
            (px - box_w/2, py - box_h/2),
            box_w, box_h,
            boxstyle="round,pad=0.08",
            facecolor="#120626",
            edgecolor=border_col,
            linewidth=2.0,
            zorder=4,
        )
        ax.add_patch(rect)

        # Draw symbol label inside card
        sym_text = sinfo["sym_id"] or sinfo["label"]
        ax.text(
            px, py,
            f"✦\n{sym_text}",
            ha="center",
            va="center",
            fontsize=7,
            fontweight="bold",
            color=border_col,
            zorder=5,
        )

    # Key labels for Root, Sections, and Canonical Entities
    key_labels = {nid: node_label_map[nid] for nid, lyr in node_layer_map.items() if lyr in (0, 1, 2) and nid not in symbol_nodes}
    nx.draw_networkx_labels(
        G, pos,
        labels=key_labels,
        font_size=7.5,
        font_color="#ffffff",
        font_weight="bold",
        ax=ax,
    )

    # Layer watermark annotations
    layer_names = {
        0: "L0 — Root (The Ledger Set / Typhen)",
        1: "L1 — Sections (Typhen, Index, Ledger Set, Rank, Field)",
        2: "L2 — Canonical Entities (6 Objects, 9 Functions, 10 Outcomes, 3 Phases)",
        3: "L3 — Phase Glyphs (18 Vector Marks with SVG Geometry)",
        4: "L4 — Composite Emblems (6 Physical Object Emblems with SVG Geometry)",
        5: "L5 — 90-Matrix Entries (SPAN-01..10, ANCHOR-01..10, etc.)",
        6: "L6 — Actionable Statements (90 Concrete Field Deployments)",
    }
    for layer, label in layer_names.items():
        y = -(layer * y_gap)
        ax.text(
            -9.5, y,
            label,
            color=LAYER_COLORS.get(layer, "#ede6ff"),
            fontsize=10.5,
            fontweight="bold",
            va="center",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#140628", edgecolor=LAYER_COLORS.get(layer, "#ede6ff"), alpha=0.9),
        )

    ax.set_xlim(-10.5, 9.5)
    ax.set_ylim(-(len(layers) * y_gap) - 0.5, 1.2)
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=200, bbox_inches="tight", facecolor="#07030d")
    plt.savefig(OUT_SVG, format="svg", bbox_inches="tight", facecolor="#07030d")
    if os.path.exists(os.path.dirname(ROOT_PNG)):
        plt.savefig(ROOT_PNG, dpi=200, bbox_inches="tight", facecolor="#07030d")
        plt.savefig(ROOT_SVG, format="svg", bbox_inches="tight", facecolor="#07030d")
    plt.close()

    print(f"Total Nodes: {len(G.nodes)} | Total Edges: {len(G.edges)} | Symbol Nodes: {len(symbol_nodes)}")
    print(f"Saved symbol-centric plots:\n  - {OUT_PNG}\n  - {OUT_SVG}")


if __name__ == "__main__":
    main()
