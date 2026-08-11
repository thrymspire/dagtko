"""Register dynamic DAG tools into the MCP catalog and as native callables."""
from __future__ import annotations

from .tools import (
    MCP_TOOL_SPECS,
    sequential_chain,
    parallel_fan_out,
    parallel_fan_in,
    conditional_branch,
    hierarchical_sub_dag,
    validate_acyclic,
    critical_path_length,
)

NATIVE_TOOLS = {
    "dag_sequential_chain": sequential_chain,
    "dag_parallel_fan_out": parallel_fan_out,
    "dag_parallel_fan_in": parallel_fan_in,
    "dag_conditional_branch": conditional_branch,
    "dag_hierarchical_sub_dag": hierarchical_sub_dag,
    "dag_validate_acyclic": validate_acyclic,
    "dag_critical_path": critical_path_length,
}

def get_mcp_specs():
    return MCP_TOOL_SPECS

def get_native_registry():
    return NATIVE_TOOLS
