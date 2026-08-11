"""
LLM grounding adapter — answers only from MCP tools / Projections.
Never invents schema or historical truth. Domain pure.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

MCP_URL = os.getenv("MCP_URL", "http://localhost:8001")


class GroundedClient:
    def __init__(self, mcp_base: str = MCP_URL):
        self.mcp_base = mcp_base

    async def list_tools(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.mcp_base}/tools")
            r.raise_for_status()
            return r.json()["tools"]

    async def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.mcp_base}/tools/call",
                json={"name": name, "arguments": arguments or {}},
            )
            r.raise_for_status()
            return r.json()

    async def answer(self, question: str) -> str:
        """
        Extremely thin routing: map natural-language intent to a single tool call.
        Production systems replace this with an MCP-capable LLM that selects tools.
        Here we keep the contract: only Projection-derived answers.
        """
        q = question.lower()
        if "open" in q or "list" in q and "work" in q:
            result = await self.call("list_open_work_orders")
        elif "pending" in q and "approval" in q:
            result = await self.call("list_pending_approvals")
        elif "critical path" in q or "longest path" in q:
            # Requires a WO id in a real system; here we list first
            result = await self.call("list_open_work_orders")
            result["note"] = "Call get_critical_path with a specific work_order_id"
        else:
            result = await self.call("list_open_work_orders")
            result["note"] = "Defaulted to list_open_work_orders; refine question for other tools"

        return json.dumps(result, indent=2, default=str)


# CLI helper
if __name__ == "__main__":
    import asyncio
    import sys

    q = " ".join(sys.argv[1:]) or "list open work orders"
    client = GroundedClient()
    print(asyncio.run(client.answer(q)))
