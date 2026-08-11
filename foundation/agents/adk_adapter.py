"""
Google ADK adapter — thin client over the shared MCP / native tool surface.
Identical contract to the AutoGen adapter so both frameworks share one history.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Optional

import httpx

MCP_URL = os.getenv("MCP_URL", "http://localhost:8001")
INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8000")


class ADKSubstrateAdapter:
    """Minimal ADK-compatible tool bridge.

    In a full ADK installation the methods below are exposed as ADK Tools
    or registered via the ADK tool registry.
    """

    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.client = httpx.Client(timeout=30.0)

    def list_tools(self) -> list[dict[str, Any]]:
        r = self.client.get(f"{MCP_URL}/tools")
        r.raise_for_status()
        return r.json()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {"name": name, "arguments": arguments}
        r = self.client.post(f"{MCP_URL}/call", json=payload)
        r.raise_for_status()
        return r.json()

    def emit_edge(
        self,
        edge_type: str,
        from_node_id: str,
        to_node_id: str,
        props: Optional[dict[str, Any]] = None,
        bucket_names: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        body = {
            "edge_type": edge_type,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "props": props or {},
            "correlation_id": self.correlation_id,
            "bucket_names": bucket_names or ["content_mutation", "topological_layer"],
        }
        r = self.client.post(f"{INGEST_URL}/edges/emit", json=body)
        r.raise_for_status()
        return r.json()

    def get_projection(self, node_id: str) -> dict[str, Any]:
        r = self.client.get(f"{INGEST_URL}/projections/{node_id}")
        r.raise_for_status()
        return r.json()


# Example ADK registration sketch (requires Google ADK installed):
#
# from google.adk.tools import FunctionTool
# adapter = ADKSubstrateAdapter()
# emit_tool = FunctionTool(adapter.emit_edge)
# # register with ADK agent / runner
