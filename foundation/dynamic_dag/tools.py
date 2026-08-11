"""
Dynamic DAG tools powered by NetworkX.
Exposed both as native Python callables and via the MCP catalog.
All mutations ultimately become typed Edges through the Ingest API;
these helpers only construct valid topology proposals.
"""
from __future__ import annotations

from typing import Any, Optional

import networkx as nx


def sequential_chain(node_ids: list[str], edge_type: str = "SEQUENCE") -> dict[str, Any]:
    """Build a linear chain of directed edges."""
    if len(node_ids) < 2:
        return {"ok": False, "error": "need at least two nodes"}
    edges = [
        {"from": node_ids[i], "to": node_ids[i + 1], "edge_type": edge_type}
        for i in range(len(node_ids) - 1)
    ]
    return {"ok": True, "kind": "sequential", "edges": edges}


def parallel_fan_out(source: str, targets: list[str], edge_type: str = "FAN_OUT") -> dict[str, Any]:
    """One source to many targets."""
    edges = [{"from": source, "to": t, "edge_type": edge_type} for t in targets]
    return {"ok": True, "kind": "parallel_fan_out", "edges": edges}


def parallel_fan_in(sources: list[str], target: str, edge_type: str = "FAN_IN") -> dict[str, Any]:
    """Many sources into one target."""
    edges = [{"from": s, "to": target, "edge_type": edge_type} for s in sources]
    return {"ok": True, "kind": "parallel_fan_in", "edges": edges}


def conditional_branch(
    source: str,
    true_target: str,
    false_target: str,
    condition_props: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Two mutually exclusive outgoing edges with condition metadata."""
    props = condition_props or {}
    edges = [
        {"from": source, "to": true_target, "edge_type": "BRANCH_TRUE", "props": props},
        {"from": source, "to": false_target, "edge_type": "BRANCH_FALSE", "props": props},
    ]
    return {"ok": True, "kind": "conditional", "edges": edges}


def hierarchical_sub_dag(
    parent: str,
    child_root: str,
    child_nodes: list[str],
    relation: str = "CONTAINS",
) -> dict[str, Any]:
    """Attach a sub-DAG under a parent node (hierarchical injection)."""
    edges = [{"from": parent, "to": child_root, "edge_type": relation}]
    for n in child_nodes:
        if n != child_root:
            edges.append({"from": child_root, "to": n, "edge_type": "MEMBER"})
    return {"ok": True, "kind": "hierarchical", "edges": edges}


def validate_acyclic(edge_list: list[dict[str, str]]) -> dict[str, Any]:
    """Return whether the proposed edge set keeps the graph a DAG."""
    G = nx.DiGraph()
    for e in edge_list:
        G.add_edge(e["from"], e["to"])
    is_dag = nx.is_directed_acyclic_graph(G)
    return {
        "ok": is_dag,
        "kind": "acyclicity",
        "is_dag": is_dag,
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
    }


def critical_path_length(edge_list: list[dict[str, str]]) -> dict[str, Any]:
    """Longest path length on a DAG (critical-path measure)."""
    G = nx.DiGraph()
    for e in edge_list:
        G.add_edge(e["from"], e["to"])
    if not nx.is_directed_acyclic_graph(G):
        return {"ok": False, "error": "graph contains a cycle"}
    try:
        length = nx.dag_longest_path_length(G)
        path = nx.dag_longest_path(G)
        return {"ok": True, "kind": "critical_path", "length": length, "path": path}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# Tool catalog entries for MCP registration
MCP_TOOL_SPECS = [
    {
        "name": "dag_sequential_chain",
        "description": "Construct a linear sequential chain of directed edges.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_ids": {"type": "array", "items": {"type": "string"}},
                "edge_type": {"type": "string", "default": "SEQUENCE"},
            },
            "required": ["node_ids"],
        },
    },
    {
        "name": "dag_parallel_fan_out",
        "description": "One source to many targets (parallel fan-out).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "targets": {"type": "array", "items": {"type": "string"}},
                "edge_type": {"type": "string", "default": "FAN_OUT"},
            },
            "required": ["source", "targets"],
        },
    },
    {
        "name": "dag_parallel_fan_in",
        "description": "Many sources into one target (parallel fan-in).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sources": {"type": "array", "items": {"type": "string"}},
                "target": {"type": "string"},
                "edge_type": {"type": "string", "default": "FAN_IN"},
            },
            "required": ["sources", "target"],
        },
    },
    {
        "name": "dag_conditional_branch",
        "description": "Conditional two-way branch with condition metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "true_target": {"type": "string"},
                "false_target": {"type": "string"},
                "condition_props": {"type": "object"},
            },
            "required": ["source", "true_target", "false_target"],
        },
    },
    {
        "name": "dag_hierarchical_sub_dag",
        "description": "Inject a hierarchical sub-DAG under a parent node.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "parent": {"type": "string"},
                "child_root": {"type": "string"},
                "child_nodes": {"type": "array", "items": {"type": "string"}},
                "relation": {"type": "string", "default": "CONTAINS"},
            },
            "required": ["parent", "child_root", "child_nodes"],
        },
    },
    {
        "name": "dag_validate_acyclic",
        "description": "Validate that a proposed edge set remains a DAG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "edge_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                        },
                    },
                }
            },
            "required": ["edge_list"],
        },
    },
    {
        "name": "dag_critical_path",
        "description": "Compute longest-path (critical-path) length on a DAG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "edge_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                        },
                    },
                }
            },
            "required": ["edge_list"],
        },
    },
]
