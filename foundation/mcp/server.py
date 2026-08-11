"""
MCP Tool Server for DAG Substrate (Expanded)
Exposes:
  1. Ledger Set 90-Matrix + Canonical Topology Tools (Projections & Gated Edge Emission)
  2. NetworkX Dynamic DAG Toolkits (Sequential, Parallel, Conditional, Hierarchical, Acyclicity, Critical Path)
  3. ComfyUI / SD Sideload Image Generation Tool (Glyph / Emblem Reference Synthesis)
  4. Local LLM Grounding Tool (Ollama / llama.cpp Projections-first reasoning)
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Local modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dynamic_dag.registry import get_mcp_specs as get_dynamic_dag_specs, get_native_registry
from llm.image_mcp_tool import MCP_IMAGE_TOOL_SPEC, generate_glyph, check_backend_status
from llm.ollama_adapter import OllamaGroundingAdapter

INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8000")

app = FastAPI(title="DAG MCP Substrate Surface", version="1.0.0")

native_dag_tools = get_native_registry()
ollama_adapter = OllamaGroundingAdapter()


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    content: list[dict[str, Any]]
    is_error: bool = False


# Domain Ledger Tool Specs
DOMAIN_TOOLS = [
    {
        "name": "list_ledger_nodes",
        "description": "List nodes in the Ledger Set DAG with optional filter by topological layer (0-6) or node_type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layer": {"type": "integer", "description": "Topological layer 0 to 6"},
                "node_type": {"type": "string", "description": "root | section | object | function_tag | phase | phase_glyph | object_symbol | matrix_entry | actionable_statement"},
            },
        },
    },
    {
        "name": "get_ledger_node",
        "description": "Read the current Projection state of any Ledger node (sole current-truth surface).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "UUID or external_ref of the node (e.g. 'ledger_root', 'entry_span_01')"},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "list_matrix_entries",
        "description": "Query the 90-matrix entries with filters for function_tag, outcome_number, rank, or phase.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "function_tag": {"type": "string", "description": "Vector, Anchor, Relay, Pivot, Fuse, Break, Span, Draft, Quiet"},
                "rank": {"type": "string", "description": "Prime, Core, Echo"},
                "phase": {"type": "string", "description": "Initiation, Stabilization, Resolution"},
                "outcome_number": {"type": "string", "description": "01 through 10"},
            },
        },
    },
    {
        "name": "get_matrix_entry",
        "description": "Get detailed projection and actionable statement for a specific 90-matrix entry (e.g. 'SPAN-01').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "indexed_asset": {"type": "string", "description": "Indexed asset code (e.g. 'SPAN-01', 'ANCHOR-04')"},
            },
            "required": ["indexed_asset"],
        },
    },
    {
        "name": "emit_edge",
        "description": "Propose a typed Edge between nodes. Named Buckets evaluate first; REFUSE leaves history untouched.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "edge_type": {"type": "string", "description": "Creates | Specifies | Classifies | Relates | ..."},
                "from_node_id": {"type": "string", "format": "uuid"},
                "to_node_id": {"type": "string", "format": "uuid"},
                "props": {"type": "object"},
                "correlation_id": {"type": "string", "format": "uuid"},
                "bucket_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Buckets that must PERMIT (rank_classification, topological_layer, content_mutation, SLA_horizon, ...)",
                },
            },
            "required": ["edge_type", "from_node_id", "to_node_id"],
        },
    },
    {
        "name": "get_critical_path",
        "description": "Compute the critical-path length for a Fragment root and update Projection fact.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root_node_id": {"type": "string", "format": "uuid"},
            },
            "required": ["root_node_id"],
        },
    },
    {
        "name": "query_ollama_grounding",
        "description": "Ground an analytical or operational query exclusively over a node's Projection using local LLM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Target node or indexed asset to ground over"},
                "question": {"type": "string", "description": "Question to answer from Projection"},
                "system_prompt": {"type": "string"},
            },
            "required": ["node_id", "question"],
        },
    },
    {
        "name": "get_system_health",
        "description": "Get status of all connected substrate services: Postgres, Redis, API, Ollama, ComfyUI sideload.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # Compatibility tools
    {
        "name": "list_open_work_orders",
        "description": "List WorkOrders whose Projection status is not Completed or Cancelled.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status_filter": {"type": "string"}
            },
        },
    },
    {
        "name": "get_work_order_state",
        "description": "Read the current Projection for one WorkOrder.",
        "inputSchema": {
            "type": "object",
            "properties": {"work_order_id": {"type": "string", "format": "uuid"}},
            "required": ["work_order_id"],
        },
    },
]

# Combined Catalog
ALL_TOOLS = DOMAIN_TOOLS + get_dynamic_dag_specs() + [MCP_IMAGE_TOOL_SPEC]


@app.get("/tools")
def list_tools():
    return {"tools": ALL_TOOLS}


async def execute_tool_call(body: ToolCall) -> ToolResult:
    name = body.name
    args = body.arguments or {}

    # 1. Dynamic DAG Tool Execution (pure Python / NetworkX)
    if name in native_dag_tools:
        try:
            fn = native_dag_tools[name]
            result = fn(**args)
            return ToolResult(
                content=[{"type": "text", "text": json.dumps(result, default=str)}],
                is_error=not result.get("ok", True),
            )
        except Exception as e:
            return ToolResult(content=[{"type": "text", "text": f"Dynamic DAG error: {str(e)}"}], is_error=True)

    # 2. Image Generation Tool (ComfyUI / Sideload Reference)
    if name == "generate_glyph_image":
        try:
            res = generate_glyph(**args)
            return ToolResult(content=[{"type": "text", "text": json.dumps(res, default=str)}])
        except Exception as e:
            return ToolResult(content=[{"type": "text", "text": f"Image tool error: {str(e)}"}], is_error=True)

    # 3. LLM Grounding Tool
    if name == "query_ollama_grounding":
        try:
            async with httpx.AsyncClient(base_url=INGEST_URL, timeout=30.0) as client:
                r = await client.post(
                    "/llm/ground",
                    json={
                        "node_id": args.get("node_id"),
                        "question": args.get("question"),
                        "system_prompt": args.get("system_prompt"),
                    },
                )
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])
        except Exception as e:
            return ToolResult(content=[{"type": "text", "text": f"LLM grounding error: {str(e)}"}], is_error=True)

    # 4. System Health Tool
    if name == "get_system_health":
        try:
            async with httpx.AsyncClient(base_url=INGEST_URL, timeout=10.0) as client:
                r = await client.get("/health")
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])
        except Exception as e:
            return ToolResult(content=[{"type": "text", "text": f"Health check error: {str(e)}"}], is_error=True)

    # 5. Ingest API Invocations
    async with httpx.AsyncClient(base_url=INGEST_URL, timeout=30.0) as client:
        try:
            if name == "list_ledger_nodes":
                params = {}
                if "layer" in args and args["layer"] is not None:
                    params["layer"] = args["layer"]
                if args.get("node_type"):
                    params["node_type"] = args["node_type"]
                r = await client.get("/ledger/nodes", params=params)
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])

            if name == "get_ledger_node":
                node_id = args["node_id"]
                r = await client.get(f"/ledger/nodes/{node_id}")
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])

            if name == "list_matrix_entries":
                params = {k: v for k, v in args.items() if v is not None}
                r = await client.get("/ledger/matrix", params=params)
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])

            if name == "get_matrix_entry":
                asset = args["indexed_asset"]
                r = await client.get(f"/ledger/matrix/{asset}")
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])

            if name == "emit_edge":
                payload = {
                    "edge_type": args["edge_type"],
                    "from_node_id": args["from_node_id"],
                    "to_node_id": args["to_node_id"],
                    "props": args.get("props") or {},
                    "correlation_id": args.get("correlation_id"),
                    "bucket_names": args.get("bucket_names") or [],
                }
                r = await client.post("/edges/emit", json=payload)
                r.raise_for_status()
                result = r.json()
                is_err = result.get("outcome") == "REFUSE"
                return ToolResult(
                    content=[{"type": "text", "text": json.dumps(result, default=str)}],
                    is_error=is_err,
                )

            if name == "get_critical_path":
                root_id = args.get("root_node_id") or args.get("work_order_id")
                r = await client.get(f"/ledger/critical-path/{root_id}")
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])

            # Compatibility handlers
            if name == "list_open_work_orders":
                params = {}
                if args.get("status_filter"):
                    params["status_filter"] = args["status_filter"]
                r = await client.get("/work-orders", params=params)
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])

            if name == "get_work_order_state":
                wid = args["work_order_id"]
                r = await client.get(f"/work-orders/{wid}")
                r.raise_for_status()
                return ToolResult(content=[{"type": "text", "text": json.dumps(r.json(), default=str)}])

            raise HTTPException(404, f"Unknown tool: {name}")

        except httpx.HTTPStatusError as e:
            return ToolResult(
                content=[{"type": "text", "text": f"Upstream API error: {e.response.text}"}],
                is_error=True,
            )
        except Exception as e:
            return ToolResult(content=[{"type": "text", "text": str(e)}], is_error=True)


@app.post("/tools/call", response_model=ToolResult)
async def call_tool_standard(body: ToolCall):
    return await execute_tool_call(body)


@app.post("/call", response_model=ToolResult)
async def call_tool_alias(body: ToolCall):
    return await execute_tool_call(body)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "tools_registered": len(ALL_TOOLS),
        "categories": {
            "domain_ledger": len(DOMAIN_TOOLS),
            "dynamic_dag": len(get_dynamic_dag_specs()),
            "image_sideload": 1,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
