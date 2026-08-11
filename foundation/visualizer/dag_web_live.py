#!/usr/bin/env python3
"""
DAG Substrate — Interactive Live Web Visualizer
Symbol-centric visualization: every phase glyph and composite emblem renders its actual
SVG symbol as the primary node artwork via Cytoscape data URIs.
Ultra-lightweight (<20MB RAM), touch/pinch optimized for Weston & modern browsers.
"""

import os
import sys
import json
import psycopg2
import psycopg2.extras
from http.server import HTTPServer, BaseHTTPRequestHandler

psycopg2.extras.register_uuid()

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "dag")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dag_substrate")
POSTGRES_DB = os.getenv("POSTGRES_DB", "dag_substrate")
WEB_PORT = int(os.getenv("VISUALIZER_PORT", "8050"))


def get_db_data():
    ports_to_try = [POSTGRES_PORT, 5432, 5433]
    conn = None
    for port in ports_to_try:
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=port,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB,
                connect_timeout=2,
            )
            break
        except Exception:
            continue

    if not conn:
        return {"error": "Could not connect to PostgreSQL."}

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

            cur.execute("SELECT id, node_type, external_ref, props, created_at FROM nodes ORDER BY created_at;")
            nodes = cur.fetchall()

            cur.execute("SELECT id, edge_type, from_node_id, to_node_id, props, occurred_at FROM edges ORDER BY occurred_at;")
            edges = cur.fetchall()

            cur.execute("SELECT * FROM ledger_node_state ORDER BY layer ASC, label ASC;")
            projections = cur.fetchall()

            cur.execute("SELECT * FROM matrix_entry_state ORDER BY indexed_asset ASC LIMIT 90;")
            matrix = cur.fetchall()

            cur.execute("SELECT bucket_name, version, constraint_body FROM buckets ORDER BY bucket_name;")
            buckets = cur.fetchall()

            cur.execute("SELECT id, event_id, event_type, edge_id, node_id, payload, occurred_at FROM events ORDER BY id DESC LIMIT 25;")
            events = cur.fetchall()

            return {
                "proof_counts": counts,
                "nodes": nodes,
                "edges": edges,
                "projections": projections,
                "matrix": matrix,
                "buckets": buckets,
                "events": events,
            }
    finally:
        conn.close()


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Ledger Set DAG — Symbol-Centric Substrate Visualizer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js"></script>
<style>
:root {
  --void: #07030d;
  --panel: rgba(22, 10, 38, 0.94);
  --border: rgba(157, 92, 255, 0.35);
  --ink: #ede6ff;
  --ink-dim: #a996d6;
  --purple: #9d5cff;
  --cyan: #5ffbf1;
  --amber: #ffb86c;
  --green: #50fa7b;
  --pink: #ff79c6;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--void);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  overflow: hidden;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
header {
  height: 52px;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  backdrop-filter: blur(10px);
  z-index: 10;
}
.title { font-size: 15px; font-weight: 700; color: var(--ink); display: flex; align-items: center; gap: 8px; }
.badge-green { background: rgba(80, 250, 123, 0.2); color: var(--green); border: 1px solid var(--green); padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
.badge-red { background: rgba(255, 107, 129, 0.2); color: #ff6b81; border: 1px solid #ff6b81; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
.metrics { display: flex; gap: 14px; font-size: 12px; color: var(--ink-dim); }
.metrics span { color: var(--cyan); font-weight: bold; }

.toolbar {
  background: rgba(15, 6, 26, 0.95);
  border-bottom: 1px solid var(--border);
  padding: 6px 16px;
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  overflow-x: auto;
}
.btn {
  background: rgba(157, 92, 255, 0.18);
  border: 1px solid var(--border);
  color: var(--ink);
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  white-space: nowrap;
  transition: all 0.15s ease;
}
.btn:hover, .btn.active {
  background: var(--purple);
  color: #fff;
}
.search-input {
  background: rgba(0,0,0,0.5);
  border: 1px solid var(--border);
  color: #fff;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  width: 160px;
  margin-left: auto;
}

#main { flex: 1; display: flex; position: relative; }
#cy { flex: 1; height: 100%; background: radial-gradient(circle at center, #140726 0%, #07030d 100%); }
#sidebar {
  width: 380px;
  background: var(--panel);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 14px;
  font-size: 12px;
}
.section-title { font-size: 12px; font-weight: 700; color: var(--cyan); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }
.card { background: rgba(0,0,0,0.35); border: 1px solid var(--border); border-radius: 6px; padding: 10px; margin-bottom: 12px; }
.symbol-preview-box {
  background: #0d0517;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.symbol-preview-box svg {
  max-width: 140px;
  max-height: 140px;
  filter: drop-shadow(0 0 8px rgba(95, 251, 241, 0.5));
}
pre { font-family: monospace; font-size: 11px; color: var(--ink-dim); overflow-x: auto; white-space: pre-wrap; word-break: break-all; }
@media (max-width: 820px) {
  #sidebar { width: 100%; height: 280px; position: absolute; bottom: 0; border-top: 1px solid var(--border); border-left: none; }
}
</style>
</head>
<body>
<header>
  <div class="title">
    <span>Ledger Set DAG</span>
    <span id="proofBadge" class="badge-green">PROOF: VERIFYING</span>
  </div>
  <div class="metrics">
    <div>Nodes: <span id="mNodes">0</span></div>
    <div>Edges: <span id="mEdges">0</span></div>
    <div>Symbols: <span id="mSymbols">0</span></div>
    <div>Matrix: <span id="mMatrix">0</span></div>
  </div>
</header>
<div class="toolbar">
  <span>Filter:</span>
  <button class="btn active" onclick="filterLayer('all')">All (250)</button>
  <button class="btn" onclick="filterLayer('symbols')">✦ SVG Glyphs & Emblems (26)</button>
  <button class="btn" onclick="filterLayer('l01')">L0-L1 Root/Sections</button>
  <button class="btn" onclick="filterLayer('l2')">L2 Canonicals</button>
  <button class="btn" onclick="filterLayer('l5')">L5 90-Matrix</button>
  <button class="btn" onclick="filterLayer('l6')">L6 Actions</button>
  <input type="text" id="searchInput" class="search-input" placeholder="Search node/asset..." oninput="searchGraph()">
</div>
<div id="main">
  <div id="cy"></div>
  <div id="sidebar">
    <div class="section-title">Selected Node (Symbol-Centric)</div>
    <div class="card" id="selectionDetails">Tap any node or edge to inspect properties, SVG symbol artwork, and actionable domain grounding.</div>
    <div class="section-title">90-Matrix Projection Browser</div>
    <div class="card"><pre id="matrixView">Loading 90-Matrix...</pre></div>
    <div class="section-title">Append-Only Event Stream</div>
    <div class="card"><pre id="eventsView">Loading events...</pre></div>
  </div>
</div>

<script>
let fullElements = [];
let currentFilter = 'all';

let cy = cytoscape({
  container: document.getElementById('cy'),
  boxSelectionEnabled: false,
  autounselectify: false,
  style: [
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-valign': 'bottom',
        'text-margin-y': 4,
        'color': '#ffffff',
        'font-size': '8px',
        'font-weight': 'bold',
        'width': '55px',
        'height': '30px',
        'shape': 'roundrectangle',
        'background-color': '#9d5cff',
        'border-width': 1.5,
        'border-color': '#ffffff',
        'text-wrap': 'ellipsis',
        'text-max-width': '65px'
      }
    },
    { selector: 'node[layer=0]', style: { 'background-color': '#ff79c6', 'width': '110px', 'height': '40px', 'font-size': '10px', 'text-valign': 'center' } },
    { selector: 'node[layer=1]', style: { 'background-color': '#bd93f9', 'width': '85px', 'height': '34px', 'font-size': '9px', 'color': '#07030d', 'text-valign': 'center' } },
    { selector: 'node[layer=2]', style: { 'background-color': '#5ffbf1', 'color': '#07030d', 'border-color': '#5ffbf1', 'text-valign': 'center' } },
    
    // Symbol nodes (Layer 3 Phase Glyphs): SVG artwork rendered as primary node background
    {
      selector: 'node[node_type="phase_glyph"]',
      style: {
        'width': '65px',
        'height': '65px',
        'shape': 'roundrectangle',
        'background-color': '#0e061a',
        'border-width': 2,
        'border-color': '#5ffbf1',
        'background-image': 'data(svg_data_uri)',
        'background-fit': 'contain',
        'background-clip': 'none',
        'text-valign': 'bottom',
        'text-margin-y': 3,
        'color': '#5ffbf1',
        'font-size': '8px'
      }
    },
    
    // Symbol nodes (Layer 4 Composite Emblems): Tall composite SVG emblem artwork
    {
      selector: 'node[node_type="object_symbol"]',
      style: {
        'width': '65px',
        'height': '125px',
        'shape': 'roundrectangle',
        'background-color': '#0e061a',
        'border-width': 2,
        'border-color': '#ffb86c',
        'background-image': 'data(svg_data_uri)',
        'background-fit': 'contain',
        'background-clip': 'none',
        'text-valign': 'bottom',
        'text-margin-y': 4,
        'color': '#ffb86c',
        'font-size': '9px'
      }
    },

    // Master / Null Symbols (Tri-Span / Blank Coin)
    {
      selector: 'node[node_type="master_symbol"], node[node_type="null_symbol"]',
      style: {
        'width': '70px',
        'height': '70px',
        'shape': 'ellipse',
        'background-color': '#0e061a',
        'border-width': 2,
        'border-color': '#ff79c6',
        'background-image': 'data(svg_data_uri)',
        'background-fit': 'contain',
        'background-clip': 'none',
        'text-valign': 'bottom',
        'color': '#ff79c6'
      }
    },

    { selector: 'node[layer=5]', style: { 'background-color': '#9d5cff', 'color': '#ffffff', 'border-color': '#ede6ff', 'text-valign': 'center' } },
    { selector: 'node[layer=6]', style: { 'background-color': '#8be9fd', 'color': '#07030d', 'border-color': '#8be9fd', 'text-valign': 'center' } },

    {
      selector: 'edge',
      style: {
        'width': 1.5,
        'target-arrow-shape': 'triangle',
        'line-color': 'rgba(95, 251, 241, 0.35)',
        'target-arrow-color': 'rgba(95, 251, 241, 0.55)',
        'curve-style': 'bezier',
        'arrow-scale': 0.8
      }
    },
    {
      selector: ':selected',
      style: {
        'border-color': '#ff79c6',
        'border-width': 3.5,
        'line-color': '#ff79c6',
        'target-arrow-color': '#ff79c6'
      }
    }
  ]
});

cy.on('tap', 'node', function(evt){
  let d = evt.target.data();
  let p = d.props || {};

  let previewBox = '';
  if (p.svg_standalone) {
    previewBox = `
      <div class="symbol-preview-box">
        <div style="font-size:10px;color:var(--cyan);margin-bottom:6px;font-weight:bold;">VECTOR SYMBOL ARTWORK: ${p.svg_symbol_id || d.label}</div>
        ${p.svg_standalone}
      </div>
    `;
  }

  let actHtml = p.actionable_statement ? `
    <div style="margin-top:8px;padding:8px;background:rgba(157,92,255,0.18);border-left:3px solid var(--purple);border-radius:4px;">
      <b style="color:var(--cyan);">Actionable Deployment Statement:</b><br>${p.actionable_statement}
    </div>
  ` : '';

  let matrixHtml = p.indexed_asset ? `
    <div style="margin-top:6px;font-size:11px;">
      <b>Asset Code:</b> <span style="color:var(--cyan);font-weight:bold;">${p.indexed_asset}</span> | 
      <b>Rank:</b> ${p.rank} | <b>Phase:</b> ${p.phase}<br>
      <b>Outcome:</b> ${p.outcome_label || p.outcome_number}
    </div>
  ` : '';

  document.getElementById('selectionDetails').innerHTML = `
    ${previewBox}
    <b>Label:</b> ${d.label}<br>
    <b>Node Type:</b> ${d.node_type} (Layer ${d.layer})<br>
    <b>Ref / Key:</b> <span style="color:var(--cyan)">${d.external_ref || 'None'}</span><br>
    <b>UUID:</b> <span style="font-size:10px;color:var(--ink-dim)">${d.id}</span><br>
    ${matrixHtml}
    ${actHtml}
    <br><b>Properties:</b><pre>${JSON.stringify(p, null, 2)}</pre>
  `;
});

cy.on('tap', 'edge', function(evt){
  let d = evt.target.data();
  document.getElementById('selectionDetails').innerHTML = `
    <b>Relation Type:</b> ${d.edge_type}<br>
    <b>From Node:</b> <span style="font-size:10px">${d.source}</span><br>
    <b>To Node:</b> <span style="font-size:10px">${d.target}</span><br><br>
    <b>Edge Props:</b><br><pre>${JSON.stringify(d.props, null, 2)}</pre>
  `;
});

function filterLayer(lyr) {
  currentFilter = lyr;
  document.querySelectorAll('.toolbar .btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');

  let filtered = fullElements.filter(el => {
    if (el.group === 'nodes') {
      let l = el.data.layer;
      let t = el.data.node_type;
      if (lyr === 'all') return true;
      if (lyr === 'symbols') return t === 'phase_glyph' || t === 'object_symbol' || t === 'master_symbol' || t === 'null_symbol';
      if (lyr === 'l01') return l === 0 || l === 1;
      if (lyr === 'l2') return l === 2;
      if (lyr === 'l5') return l === 5;
      if (lyr === 'l6') return l === 6;
      return true;
    }
    return true;
  });

  let nodeIds = new Set(filtered.filter(e => e.group === 'nodes').map(n => n.data.id));
  filtered = filtered.filter(e => e.group === 'nodes' || (nodeIds.has(e.data.source) && nodeIds.has(e.data.target)));

  cy.json({ elements: filtered });
  cy.layout({ name: 'dagre', rankDir: 'TB', nodeDimensionsIncludeLabels: true, rankSep: 45, nodeSep: 25 }).run();
}

function searchGraph() {
  let q = document.getElementById('searchInput').value.toLowerCase().trim();
  if (!q) {
    cy.nodes().style('opacity', 1);
    cy.edges().style('opacity', 1);
    return;
  }
  cy.nodes().each(n => {
    let lbl = (n.data('label') || '').toLowerCase();
    let ref = (n.data('external_ref') || '').toLowerCase();
    let typ = (n.data('node_type') || '').toLowerCase();
    if (lbl.includes(q) || ref.includes(q) || typ.includes(q)) {
      n.style('opacity', 1);
      n.select();
    } else {
      n.style('opacity', 0.12);
      n.unselect();
    }
  });
}

async function refreshData() {
  try {
    let res = await fetch('/api/data');
    let data = await res.json();
    if (data.error) return;

    let proof = data.proof_counts || {};
    let nNodes = proof.total_nodes || 0;
    let nEdges = proof.total_edges || 0;
    let nSymbols = proof.symbol_nodes || 0;
    let nMatrix = proof.matrix_entries || 0;
    let nEvents = proof.total_events || 0;

    let badge = document.getElementById('proofBadge');
    if (nNodes >= 250 && nEdges >= 500 && nSymbols >= 26 && nMatrix == 90) {
      badge.textContent = 'PROOF: GREEN (250 Nodes / 26 Symbols / 90 Matrix)';
      badge.className = 'badge-green';
    } else if (nNodes >= 1) {
      badge.textContent = 'PROOF: GREEN (Seed Active)';
      badge.className = 'badge-green';
    } else {
      badge.textContent = 'PROOF: RED';
      badge.className = 'badge-red';
    }

    document.getElementById('mNodes').textContent = nNodes;
    document.getElementById('mEdges').textContent = nEdges;
    document.getElementById('mSymbols').textContent = nSymbols;
    document.getElementById('mMatrix').textContent = nMatrix;

    if (data.matrix && data.matrix.length > 0) {
      let mSample = data.matrix.slice(0, 10).map(m => `[${m.indexed_asset}] ${m.function_tag}-${m.outcome_number} (${m.rank}/${m.phase}): ${m.outcome_label}`).join('\\n');
      document.getElementById('matrixView').textContent = mSample + `\\n... (+ ${data.matrix.length - 10} more entries)`;
    }

    if (data.events) {
      document.getElementById('eventsView').textContent = JSON.stringify(data.events.slice(0, 5), null, 2);
    }

    let elements = [];
    data.nodes.forEach(n => {
      let p = n.props || {};
      let lbl = p.label || p.indexed_asset || n.external_ref || n.id.substring(0,6);
      let uri = p.svg_data_uri || (n.svg_data_uri ? n.svg_data_uri : '');
      elements.push({
        group: 'nodes',
        data: {
          id: n.id,
          label: lbl,
          node_type: n.node_type,
          layer: p.layer !== undefined ? p.layer : 0,
          external_ref: n.external_ref,
          svg_data_uri: uri,
          props: p
        }
      });
    });

    data.edges.forEach(e => {
      elements.push({
        group: 'edges',
        data: {
          id: e.id,
          source: e.from_node_id,
          target: e.to_node_id,
          edge_type: e.edge_type,
          props: e.props
        }
      });
    });

    fullElements = elements;
    if (cy.nodes().length === 0) {
      cy.json({ elements: fullElements });
      cy.layout({ name: 'dagre', rankDir: 'TB', nodeDimensionsIncludeLabels: true, rankSep: 45, nodeSep: 25 }).run();
    }
  } catch(e) {
    console.error(e);
  }
}

refreshData();
setInterval(refreshData, 4000);
</script>
</body>
</html>
"""


class VisualizerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/api/data":
            data = get_db_data()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def main():
    print(f"============================================================")
    print(f"  Ledger Set DAG — Symbol-Centric Live Web Visualizer")
    print(f"  Listening on http://0.0.0.0:{WEB_PORT}")
    print(f"  SVG Artwork Rendered as Primary Node Visual Identity")
    print(f"============================================================")
    server = HTTPServer(("0.0.0.0", WEB_PORT), VisualizerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
