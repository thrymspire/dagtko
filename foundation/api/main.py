"""
DAG Substrate Ingest API
Emits typed Edges + Events atomically, updates Projections, gates via Buckets.
Exposes Ledger Set 90-Matrix domain, LLM grounding, and ComfyUI side-load endpoints.
Character: append-only. Refusal produces zero mutation.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import redis
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

# Local modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm.ollama_adapter import OllamaGroundingAdapter
from llm.image_mcp_tool import check_backend_status as check_image_status, generate_glyph

psycopg2.extras.register_uuid()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://dag:dag_substrate@localhost:5432/dag_substrate",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = FastAPI(
    title="DAG Substrate Ingest & Domain API",
    version="1.0.0",
    description="Typed Edge + Event emission. Ledger Set 90-Matrix domain. Bucket-gated. Ollama/ComfyUI wired.",
)

ollama = OllamaGroundingAdapter()

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class EdgeEmit(BaseModel):
    edge_type: str = Field(..., min_length=1, description="Relation type (Creates, Specifies, Classifies, ...)")
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    props: dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[uuid.UUID] = None
    causation_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    bucket_names: list[str] = Field(
        default_factory=list,
        description="Buckets that must PERMIT before emission (e.g. topological_layer, content_mutation, SLA_horizon)",
    )


class EmitResult(BaseModel):
    outcome: str  # PERMIT | REFUSE
    edge_id: Optional[uuid.UUID] = None
    event_id: Optional[uuid.UUID] = None
    decision_ids: list[uuid.UUID] = Field(default_factory=list)
    message: str = ""


class NodeCreate(BaseModel):
    node_type: str
    external_ref: Optional[str] = None
    props: dict[str, Any] = Field(default_factory=dict)


class GroundingRequest(BaseModel):
    node_id: Optional[str] = None
    indexed_asset: Optional[str] = None
    question: str
    system_prompt: Optional[str] = None


class GlyphGenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = "blurry, text, low quality"
    width: int = 512
    height: int = 512
    seed: Optional[int] = None
    function_tag: Optional[str] = None
    phase: Optional[str] = None


# ---------------------------------------------------------------------------
# DB / Redis helpers
# ---------------------------------------------------------------------------
def get_conn():
    return psycopg2.connect(DATABASE_URL)


def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True)


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM nodes")
                node_cnt = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM edges")
                edge_cnt = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM events")
                ev_cnt = cur.fetchone()[0]

        r = get_redis()
        r.ping()
        ollama_status = ollama.check_health()
        image_status = check_image_status()

        return {
            "status": "ok",
            "postgres": "up",
            "redis": "up",
            "counts": {
                "nodes": node_cnt,
                "edges": edge_cnt,
                "events": ev_cnt,
            },
            "ollama": ollama_status,
            "comfyui_sideload": image_status,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------------------------------------------------------------------
# Node Creation
# ---------------------------------------------------------------------------
@app.post("/nodes", status_code=status.HTTP_201_CREATED)
def create_node(body: NodeCreate):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO nodes (node_type, external_ref, props)
                VALUES (%s, %s, %s)
                RETURNING id, node_type, external_ref, props, created_at
                """,
                (body.node_type, body.external_ref, psycopg2.extras.Json(body.props)),
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row)


# ---------------------------------------------------------------------------
# Core: Emit Edge (Bucket-gated, Atomic Edge + Event + Projection)
# ---------------------------------------------------------------------------
@app.post("/edges/emit", response_model=EmitResult)
def emit_edge(body: EdgeEmit):
    proposed = {
        "edge_type": body.edge_type,
        "from_node_id": str(body.from_node_id),
        "to_node_id": str(body.to_node_id),
        "props": body.props,
        "correlation_id": str(body.correlation_id) if body.correlation_id else None,
    }

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            decision_ids: list[uuid.UUID] = []
            if body.bucket_names:
                cur.execute(
                    "SELECT * FROM gate_edge(%s, %s, %s, %s)",
                    (
                        body.bucket_names,
                        psycopg2.extras.Json(proposed),
                        psycopg2.extras.Json({}),
                        body.correlation_id,
                    ),
                )
                gate = cur.fetchone()
                decision_ids = list(gate["decision_ids"] or [])
                if gate["outcome"] == "REFUSE":
                    conn.commit()
                    return EmitResult(
                        outcome="REFUSE",
                        decision_ids=decision_ids,
                        message="One or more Buckets refused the proposed Edge. History untouched.",
                    )

            edge_id = uuid.uuid4()
            event_uuid = uuid.uuid4()
            subject = body.node_id or body.to_node_id

            cur.execute(
                """
                INSERT INTO edges (id, edge_type, from_node_id, to_node_id, props,
                                  correlation_id, causation_id, occurred_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    edge_id,
                    body.edge_type,
                    body.from_node_id,
                    body.to_node_id,
                    psycopg2.extras.Json(body.props),
                    body.correlation_id,
                    body.causation_id,
                    datetime.now(timezone.utc),
                ),
            )

            cur.execute(
                """
                INSERT INTO events (event_id, event_type, edge_id, node_id, payload,
                                   correlation_id, causation_id, occurred_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    event_uuid,
                    body.edge_type,
                    edge_id,
                    subject,
                    psycopg2.extras.Json(body.props),
                    body.correlation_id,
                    body.causation_id,
                    datetime.now(timezone.utc),
                ),
            )
            event_pk = cur.fetchone()["id"]

            # Update projections
            try:
                cur.execute("SELECT project_ledger_event(%s)", (event_pk,))
            except Exception:
                pass
            try:
                cur.execute("SELECT project_wo_event(%s)", (event_pk,))
            except Exception:
                pass

            conn.commit()

            try:
                r = get_redis()
                r.xadd(
                    "dag:edges",
                    {
                        "edge_id": str(edge_id),
                        "edge_type": body.edge_type,
                        "from": str(body.from_node_id),
                        "to": str(body.to_node_id),
                        "correlation_id": str(body.correlation_id or ""),
                    },
                    maxlen=100000,
                    approximate=True,
                )
            except Exception:
                pass

            return EmitResult(
                outcome="PERMIT",
                edge_id=edge_id,
                event_id=event_uuid,
                decision_ids=decision_ids,
                message="Edge + Event emitted; Projection updated.",
            )


# ---------------------------------------------------------------------------
# Ledger Domain Projections (Sole Current-Truth Surface)
# ---------------------------------------------------------------------------
@app.get("/ledger/nodes")
def list_ledger_nodes(
    layer: Optional[int] = Query(None, description="Filter by layer (0-6)"),
    node_type: Optional[str] = Query(None, description="Filter by node_type"),
    limit: int = 300,
):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = "SELECT * FROM ledger_node_state WHERE 1=1"
            params = []
            if layer is not None:
                query += " AND layer = %s"
                params.append(layer)
            if node_type:
                query += " AND node_type = %s"
                params.append(node_type)
            query += " ORDER BY layer ASC, label ASC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]


@app.get("/ledger/nodes/{node_id}")
def get_ledger_node(node_id: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check UUID or external_ref
            cur.execute(
                "SELECT * FROM ledger_node_state WHERE node_id::text = %s OR external_ref = %s",
                (node_id, node_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, f"Node {node_id} not found in Ledger Projection")
            return dict(row)


@app.get("/ledger/matrix")
def list_matrix_entries(
    function_tag: Optional[str] = None,
    rank: Optional[str] = None,
    phase: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 100,
):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = "SELECT * FROM matrix_entry_state WHERE 1=1"
            params = []
            if function_tag:
                query += " AND function_tag ILIKE %s"
                params.append(function_tag)
            if rank:
                query += " AND rank ILIKE %s"
                params.append(rank)
            if phase:
                query += " AND phase ILIKE %s"
                params.append(phase)
            if outcome:
                query += " AND outcome_number = %s"
                params.append(outcome)
            query += " ORDER BY indexed_asset ASC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]


@app.get("/ledger/matrix/{entry_id}")
def get_matrix_entry(entry_id: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM matrix_entry_state WHERE entry_id::text = %s OR indexed_asset ILIKE %s",
                (entry_id, entry_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, f"Matrix entry {entry_id} not found")
            return dict(row)


@app.get("/ledger/critical-path/{root_id}")
def get_critical_path(root_id: uuid.UUID):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT compute_critical_path_len(%s)", (root_id,))
            length = cur.fetchone()[0]
            conn.commit()
            return {"root_node_id": root_id, "critical_path_len": length}


@app.get("/projections/{node_id}")
def get_projection(node_id: str):
    return get_ledger_node(node_id)


# ---------------------------------------------------------------------------
# Replay & Administrative
# ---------------------------------------------------------------------------
@app.post("/admin/replay")
def replay_projections():
    """Operational proof: reconstruct Projection exclusively from Event log."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT replay_ledger_projection()")
            ledger_cnt = cur.fetchone()[0]
            cur.execute("SELECT replay_wo_projection()")
            wo_cnt = cur.fetchone()[0]
            conn.commit()
            return {
                "ledger_events_replayed": ledger_cnt,
                "wo_events_replayed": wo_cnt,
                "message": "All Projections reconstructed from append-only Event stream.",
            }


# ---------------------------------------------------------------------------
# LLM & Image Endpoints
# ---------------------------------------------------------------------------
@app.get("/llm/health")
def llm_health():
    return ollama.check_health()


@app.post("/llm/ground")
def ground_llm(body: GroundingRequest):
    projection = {}
    if body.node_id:
        projection = get_ledger_node(body.node_id)
    elif body.indexed_asset:
        projection = get_matrix_entry(body.indexed_asset)

    response = ollama.ground_over_projection(
        projection=projection,
        question=body.question,
        system_prompt=body.system_prompt,
    )
    return {
        "ok": True,
        "question": body.question,
        "grounded_response": response,
        "projection_used": projection,
    }


@app.get("/image/health")
def image_health():
    return check_image_status()


@app.post("/image/generate")
def generate_glyph_endpoint(body: GlyphGenerateRequest):
    return generate_glyph(
        prompt=body.prompt,
        negative_prompt=body.negative_prompt,
        width=body.width,
        height=body.height,
        seed=body.seed,
        function_tag=body.function_tag,
        phase=body.phase,
    )


# ---------------------------------------------------------------------------
# Fragments & Contracts
# ---------------------------------------------------------------------------
@app.get("/fragments")
def list_fragments():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM fragments ORDER BY created_at")
            return [dict(r) for r in cur.fetchall()]


@app.post("/fragments/recognize/{root_node_id}")
def recognize_fragment(root_node_id: uuid.UUID):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT recognize_seed_fragment(%s)", (root_node_id,))
            frag_id = cur.fetchone()[0]
            conn.commit()
            cur.execute("SELECT * FROM fragments WHERE id = %s", (frag_id,))
            return dict(cur.fetchone())


@app.get("/contracts")
def list_contracts(published_only: bool = False):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if published_only:
                cur.execute("SELECT * FROM contracts WHERE published = true ORDER BY created_at")
            else:
                cur.execute("SELECT * FROM contracts ORDER BY created_at")
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Legacy Work-Order Compatibility Endpoints
# ---------------------------------------------------------------------------
@app.get("/work-orders")
def list_open_work_orders(status_filter: Optional[str] = None):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if status_filter:
                cur.execute("SELECT * FROM wo_current_state WHERE status = %s ORDER BY updated_at DESC", (status_filter,))
            else:
                cur.execute("SELECT * FROM wo_current_state ORDER BY updated_at DESC")
            return [dict(r) for r in cur.fetchall()]


@app.get("/work-orders/{work_order_id}")
def get_work_order_state(work_order_id: uuid.UUID):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM wo_current_state WHERE work_order_id = %s", (work_order_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "WorkOrder not found in Projection")
            return dict(row)


@app.post("/work-orders/{work_order_id}/critical-path")
def compute_wo_critical_path(work_order_id: uuid.UUID):
    return get_critical_path(work_order_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
