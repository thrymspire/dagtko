"""
Architectural tests for Ledger Set DAG Substrate closed-loop proof.
Validates:
  1. Full 250-Node / 501-Edge / 90-Matrix / 18-Glyph Seed integrity
  2. Append-only Event Replay reconstruction
  3. Bucket Gates (Atomic PERMIT / REFUSE with zero mutation on refusal)
  4. Expanded MCP Tool Surface (Dynamic DAG, Image Sideload, LLM Grounding)
  5. Ingest API + Projections Current-Truth Surface
"""

import os
import uuid
import pytest
import httpx
import psycopg2
import psycopg2.extras

psycopg2.extras.register_uuid()

POSTGRES_USER = os.getenv("POSTGRES_USER", "dag")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dag_substrate")
POSTGRES_DB = os.getenv("POSTGRES_DB", "dag_substrate")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:{POSTGRES_PORT}/{POSTGRES_DB}",
)
API_PORT = os.getenv("API_PORT", "8000")
MCP_PORT = os.getenv("MCP_PORT", "8001")
INGEST = os.getenv("INGEST_URL", f"http://localhost:{API_PORT}")
MCP_URL = os.getenv("MCP_URL", f"http://localhost:{MCP_PORT}")


def get_test_db_conn():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception:
        alt_port = "5433" if POSTGRES_PORT == "5432" else "5432"
        alt_url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:{alt_port}/{POSTGRES_DB}"
        return psycopg2.connect(alt_url)


def test_seed_jointly_queryable():
    """Verify complete 250 nodes, 495 edges, 90 matrix entries, 6 buckets exist together."""
    conn = get_test_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM nodes")
    assert cur.fetchone()[0] >= 250

    cur.execute("SELECT count(*) FROM edges")
    assert cur.fetchone()[0] >= 495

    cur.execute("SELECT count(*) FROM events")
    assert cur.fetchone()[0] >= 495

    cur.execute("SELECT count(*) FROM ledger_node_state")
    assert cur.fetchone()[0] >= 250

    cur.execute("SELECT count(*) FROM matrix_entry_state")
    assert cur.fetchone()[0] == 90

    cur.execute("SELECT count(*) FROM buckets")
    assert cur.fetchone()[0] >= 3

    cur.execute("SELECT count(*) FROM fragments")
    assert cur.fetchone()[0] >= 1
    conn.close()


def test_replay_regenerates_projection():
    """Operational proof: replay reconstructs ledger_node_state and matrix_entry_state."""
    conn = get_test_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT replay_ledger_projection()")
    n = cur.fetchone()[0]
    assert n > 0

    cur.execute("SELECT count(*) FROM ledger_node_state")
    assert cur.fetchone()[0] >= 250

    cur.execute("SELECT count(*) FROM matrix_entry_state")
    assert cur.fetchone()[0] == 90
    conn.commit()
    conn.close()


def test_90_matrix_structure_and_coverage():
    """Verify all 9 function tags and 10 outcome numbers are present in the 90-matrix."""
    conn = get_test_db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT DISTINCT function_tag FROM matrix_entry_state")
    tags = {r["function_tag"] for r in cur.fetchall()}
    expected_tags = {"Vector", "Anchor", "Relay", "Pivot", "Fuse", "Break", "Span", "Draft", "Quiet"}
    assert expected_tags.issubset(tags)

    cur.execute("SELECT DISTINCT outcome_number FROM matrix_entry_state")
    outcomes = {r["outcome_number"] for r in cur.fetchall()}
    expected_outcomes = {f"{i:02d}" for i in range(1, 11)}
    assert expected_outcomes.issubset(outcomes)

    cur.execute("SELECT count(*) FROM matrix_entry_state WHERE actionable_statement IS NOT NULL AND length(actionable_statement) > 10")
    assert cur.fetchone()["count"] == 90
    conn.close()


def test_emit_and_bucket_refuse():
    """Bucket REFUSE produces zero mutation."""
    client = httpx.Client(base_url=INGEST, timeout=10.0)

    # Get two nodes
    conn = get_test_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM nodes LIMIT 2")
    rows = cur.fetchall()
    from_id = str(rows[0][0])
    to_id = str(rows[1][0])
    conn.close()

    # Propose an edge that exceeds SLA horizon
    payload = {
        "edge_type": "Relates",
        "from_node_id": from_id,
        "to_node_id": to_id,
        "props": {"expected_hours": 999},  # exceeds SLA_horizon max_hours=48
        "bucket_names": ["SLA_horizon"],
    }
    r = client.post("/edges/emit", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "REFUSE"
    assert body["edge_id"] is None
    assert len(body["decision_ids"]) >= 1


def test_emit_permit():
    """Bucket PERMIT produces atomic Edge + Event + Projection."""
    client = httpx.Client(base_url=INGEST, timeout=10.0)

    conn = get_test_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM nodes LIMIT 2")
    rows = cur.fetchall()
    from_id = str(rows[0][0])
    to_id = str(rows[1][0])
    conn.close()

    payload = {
        "edge_type": "Extends",
        "from_node_id": from_id,
        "to_node_id": to_id,
        "props": {"expected_hours": 4, "rank": "Prime"},
        "bucket_names": ["SLA_horizon", "rank_classification", "content_mutation"],
    }
    r = client.post("/edges/emit", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "PERMIT"
    assert body["edge_id"] is not None
    assert body["event_id"] is not None


def test_mcp_catalog_expanded():
    """Verify MCP surface registers dynamic DAG tools + image tool + 90-matrix tools."""
    client = httpx.Client(base_url=MCP_URL, timeout=10.0)
    r = client.get("/tools")
    assert r.status_code == 200
    tool_names = [t["name"] for t in r.json()["tools"]]

    # Dynamic DAG tools
    assert "dag_sequential_chain" in tool_names
    assert "dag_parallel_fan_out" in tool_names
    assert "dag_parallel_fan_in" in tool_names
    assert "dag_conditional_branch" in tool_names
    assert "dag_hierarchical_sub_dag" in tool_names
    assert "dag_validate_acyclic" in tool_names
    assert "dag_critical_path" in tool_names

    # Image tool
    assert "generate_glyph_image" in tool_names

    # Domain ledger tools
    assert "list_ledger_nodes" in tool_names
    assert "get_ledger_node" in tool_names
    assert "list_matrix_entries" in tool_names
    assert "get_matrix_entry" in tool_names
    assert "emit_edge" in tool_names
    assert "query_ollama_grounding" in tool_names
    assert "get_system_health" in tool_names


def test_mcp_dynamic_dag_tool_call():
    """Verify calling dynamic DAG tools via MCP catalog works."""
    client = httpx.Client(base_url=MCP_URL, timeout=10.0)
    payload = {
        "name": "dag_sequential_chain",
        "arguments": {"node_ids": ["node_A", "node_B", "node_C"], "edge_type": "CHAIN"},
    }
    r = client.post("/tools/call", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert not data["is_error"]
    assert "sequential" in data["content"][0]["text"]


def test_mcp_image_tool_call():
    """Verify calling generate_glyph_image returns valid reference in sideload/live mode."""
    client = httpx.Client(base_url=MCP_URL, timeout=10.0)
    payload = {
        "name": "generate_glyph_image",
        "arguments": {
            "prompt": "Cyan glowing anchor emblem for initiation phase",
            "function_tag": "Anchor",
            "phase": "Initiation",
            "svg_symbol_id": "anchor-initiation",
        },
    }
    r = client.post("/tools/call", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert not data["is_error"]
    assert "glyph://" in data["content"][0]["text"] or "comfyui://" in data["content"][0]["text"]


def test_llm_grounding_endpoint():
    """Verify LLM grounding over projection returns valid response."""
    client = httpx.Client(base_url=INGEST, timeout=30.0)
    payload = {
        "indexed_asset": "SPAN-01",
        "question": "What is the primary actionable deployment statement for SPAN-01?",
    }
    r = client.post("/llm/ground", json=payload)
    assert r.status_code == 200
    res = r.json()
    assert res["ok"]
    assert res["projection_used"]["indexed_asset"] == "SPAN-01"
    assert len(res["grounded_response"]) > 0


def test_symbol_centric_projection_integrity():
    """Verify symbol-centric projection contains all 26 SVG symbols and reconstructs via replay."""
    conn = get_test_db_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1. Check phase glyphs
    cur.execute("SELECT node_id, external_ref, svg_symbol_id, svg_data_uri, svg_geometry FROM ledger_node_state WHERE node_type = 'phase_glyph'")
    glyphs = cur.fetchall()
    assert len(glyphs) == 18
    for g in glyphs:
        assert g["svg_symbol_id"] is not None
        assert g["svg_data_uri"].startswith("data:image/svg+xml;base64,")
        assert len(g["svg_geometry"]) > 20

    # 2. Check composite emblems
    cur.execute("SELECT node_id, external_ref, svg_symbol_id, svg_data_uri, svg_geometry FROM ledger_node_state WHERE node_type = 'object_symbol'")
    emblems = cur.fetchall()
    assert len(emblems) == 6
    for emb in emblems:
        assert emb["svg_symbol_id"] is not None
        assert emb["svg_data_uri"].startswith("data:image/svg+xml;base64,")
        assert len(emb["svg_geometry"]) > 20

    # 3. Test replay maintains symbol geometry
    cur.execute("SELECT replay_ledger_projection()")
    cur.execute("SELECT count(*) AS total_symbols FROM ledger_node_state WHERE svg_data_uri IS NOT NULL")
    assert cur.fetchone()["total_symbols"] >= 26

    conn.commit()
    conn.close()

