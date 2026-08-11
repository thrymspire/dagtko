"""
AutoGen adapter — thin client over the shared MCP / native tool surface.
Emits only typed Edges; reads only Projections; respects Bucket gates.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Optional

import httpx

MCP_URL = os.getenv("MCP_URL", "http://localhost:8001")
INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8000")


class AutoGenSubstrateAdapter:
    """Minimal AutoGen-compatible tool bridge.

    In a full AutoGen installation this class is registered as a set of
    FunctionTools or used inside a ConversableAgent tool map.
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


# Example AutoGen registration sketch (requires `pyautogen` installed):
#
# from autogen import ConversableAgent, register_function
# adapter = AutoGenSubstrateAdapter()
# register_function(
#     adapter.emit_edge,
#     caller=user_proxy,
#     executor=assistant,
#     name="emit_edge",
#     description="Emit a typed Edge through the shared substrate under Bucket gates.",
# )
