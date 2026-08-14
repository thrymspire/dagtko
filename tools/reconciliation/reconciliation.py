#!/usr/bin/env python3
"""
DAGTKO Ledger Set Reconciliation
================================

This script reads the canonical Ledger Set and creates three
non-destructive candidate DAG representations:

    1. MATRIX
    2. PHASE
    3. COMBINED

It never modifies the canonical Ledger Set.

Run from repository root:

    python tools/reconciliation/reconciliation.py
"""

# ======================================================================
# BEGIN: IMPORTS
# DO NOT EDIT
# ======================================================================

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys

from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any


# ======================================================================
# END: IMPORTS
# ======================================================================


# ======================================================================
# BEGIN: USER CONFIGURATION
#
# THIS IS THE ONLY BLOCK INTENDED FOR NORMAL MANUAL EDITING.
#
# If an LLM is used to repair syntax, it must preserve every other
# block exactly.
# ======================================================================

SCRIPT_VERSION = "3.1.0"

LEDGER_DIRECTORY = Path("domain-docs/ledger")

OUTPUT_DIRECTORY = Path("_reconciliation_output")

MASTER_JSON_NAME = "ledger-set-dag.json"

SOURCE_SEARCH_DIRECTORIES = [
    Path("domain-docs"),
    Path("foundation"),
]

EXPECTED_COUNTS = {
    "function_tags": 9,
    "outcomes": 10,
    "matrix_entries": 90,
    "phases": 3,
    "physical_phase_glyphs": 18,
    "physical_emblems": 6,
    "objects": 6,
    "field_specs": 6,
    "nodes": 250,
    "edges": 501,
}

EXPECTED_EXTERNAL_SOURCES = {
    "guide_html": "ledger-set-guide.html",
    "system_svg": "ledger-set-system.svg",
}


# ======================================================================
# END: USER CONFIGURATION
# ======================================================================


# ======================================================================
# BEGIN: CORE UTILITIES
# DO NOT EDIT GRAPH LOGIC IN THIS BLOCK.
# ======================================================================


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def read_json(path: Path) -> Any:
    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )


def stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(
        payload
    ).hexdigest()


def relative_path(
    path: Path,
    root: Path,
) -> str:
    try:
        return str(
            path.resolve().relative_to(
                root.resolve()
            )
        )
    except ValueError:
        return str(path)


def normalize_id(value: Any) -> str:
    return str(value).strip()


def node_id(node: dict[str, Any]) -> str:
    return normalize_id(
        node.get("id", "")
    )


def node_type(node: dict[str, Any]) -> str:
    return str(
        node.get("type", "")
    )


def node_layer(
    node: dict[str, Any],
) -> int | None:
    value = node.get("layer")

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def edge_source(
    edge: dict[str, Any],
) -> str:
    for key in (
        "source",
        "from",
        "source_id",
        "sourceId",
    ):
        if key in edge:
            return normalize_id(
                edge[key]
            )

    return ""


def edge_target(
    edge: dict[str, Any],
) -> str:
    for key in (
        "target",
        "to",
        "target_id",
        "targetId",
    ):
        if key in edge:
            return normalize_id(
                edge[key]
            )

    return ""


def edge_relation(
    edge: dict[str, Any],
) -> str:
    for key in (
        "relation",
        "type",
        "kind",
        "label",
    ):
        if key in edge:
            return str(
                edge[key]
            )

    return ""


def find_repository_root() -> Path:
    candidates = [
        Path.cwd().resolve(),
        Path(__file__).resolve(),
    ]

    for candidate in candidates:
        current = (
            candidate
            if candidate.is_dir()
            else candidate.parent
        )

        while current != current.parent:
            if (
                (current / ".git").exists()
                or (
                    (current / "domain-docs").is_dir()
                    and (
                        current / "foundation"
                    ).is_dir()
                )
            ):
                return current

            current = current.parent

    raise RuntimeError(
        "Could not locate DAGTKO repository root."
    )


def find_master_json(
    repo_root: Path,
) -> Path:
    direct = (
        repo_root
        / LEDGER_DIRECTORY
        / MASTER_JSON_NAME
    )

    if direct.exists():
        return direct

    matches = sorted(
        repo_root.rglob(
            MASTER_JSON_NAME
        )
    )

    if not matches:
        raise FileNotFoundError(
            f"Could not find {MASTER_JSON_NAME}"
        )

    return matches[0]


# ======================================================================
# END: CORE UTILITIES
# ======================================================================


# ======================================================================
# BEGIN: SOURCE INVENTORY
# DO NOT EDIT
# ======================================================================


def inspect_html(
    path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    text = read_text(path)

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    title = (
        title_match.group(1).strip()
        if title_match
        else path.stem
    )

    return {
        "path": relative_path(
            path,
            repo_root,
        ),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
        "title": title,
    }


def inspect_svg(
    path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    text = read_text(path)

    symbol_ids = re.findall(
        r'\bid=["\']([^"\']+)["\']',
        text,
    )

    return {
        "path": relative_path(
            path,
            repo_root,
        ),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
        "symbol_ids": sorted(
            set(symbol_ids)
        ),
        "symbol_count": len(
            set(symbol_ids)
        ),
    }


def discover_repository_sources(
    repo_root: Path,
) -> dict[str, Any]:

    discovered = {}

    for directory in SOURCE_SEARCH_DIRECTORIES:
        root = repo_root / directory

        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            relative = relative_path(
                path,
                repo_root,
            )

            discovered[relative] = {
                "path": relative,
                "suffix": path.suffix.lower(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }

    html = []
    svg = []

    for relative in sorted(discovered):
        path = repo_root / relative

        if path.suffix.lower() in (
            ".html",
            ".htm",
        ):
            html.append(
                inspect_html(
                    path,
                    repo_root,
                )
            )

        elif path.suffix.lower() == ".svg":
            svg.append(
                inspect_svg(
                    path,
                    repo_root,
                )
            )

    manifest_sources = {}

    for key, filename in (
        EXPECTED_EXTERNAL_SOURCES.items()
    ):
        matches = []

        for path in repo_root.rglob(filename):
            matches.append(
                relative_path(
                    path,
                    repo_root,
                )
            )

        manifest_sources[key] = {
            "declared_name": filename,
            "found": bool(matches),
            "locations": sorted(matches),
        }

    return {
        "schema":
            "dagtko.ledger-set.source-inventory.v3",

        "files":
            [
                discovered[key]
                for key in sorted(discovered)
            ],

        "html":
            html,

        "svg":
            svg,

        "expected_external_sources":
            manifest_sources,
    }


# ======================================================================
# END: SOURCE INVENTORY
# ======================================================================


# ======================================================================
# BEGIN: MASTER GRAPH EXTRACTION
# DO NOT EDIT
# ======================================================================


def get_nodes(
    master_data: dict[str, Any],
) -> list[dict[str, Any]]:

    nodes = master_data.get(
        "nodes",
        [],
    )

    if not isinstance(nodes, list):
        raise ValueError(
            "Master graph 'nodes' must be a list."
        )

    return copy.deepcopy(nodes)


def get_edges(
    master_data: dict[str, Any],
) -> list[dict[str, Any]]:

    edges = master_data.get(
        "edges",
        [],
    )

    if not isinstance(edges, list):
        raise ValueError(
            "Master graph 'edges' must be a list."
        )

    return copy.deepcopy(edges)


def classify_nodes(
    nodes: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:

    groups = {
        "functions": [],
        "outcomes": [],
        "phases": [],
        "matrix": [],
        "glyphs": [],
        "emblems": [],
        "objects": [],
        "fields": [],
        "symbols": [],
        "statements": [],
        "sections": [],
        "root": [],
        "other": [],
    }

    for node in nodes:
        kind = node_type(
            node
        ).lower()

        layer = node_layer(
            node
        )

        if kind == "function_tag":
            groups["functions"].append(node)

        elif kind == "outcome_number":
            groups["outcomes"].append(node)

        elif kind == "phase":
            groups["phases"].append(node)

        elif "matrix" in kind:
            groups["matrix"].append(node)

        elif (
            "glyph" in kind
            or (
                "physical" in kind
                and "phase" in kind
            )
        ):
            groups["glyphs"].append(node)

        elif (
            "emblem" in kind
            or kind == "object_symbol"
            or "composite" in kind
        ):
            groups["emblems"].append(node)

        elif kind == "object":
            groups["objects"].append(node)

        elif (
            "field" in kind
            or "field_spec" in kind
        ):
            groups["fields"].append(node)

        elif "symbol" in kind:
            groups["symbols"].append(node)

        elif (
            "statement" in kind
            or layer == 6
        ):
            groups["statements"].append(node)

        elif kind == "section":
            groups["sections"].append(node)

        elif kind == "root":
            groups["root"].append(node)

        else:
            groups["other"].append(node)

    return groups


def select_edges_for_nodes(
    edges: list[dict[str, Any]],
    selected_ids: set[str],
) -> list[dict[str, Any]]:

    result = []

    for edge in edges:
        source = edge_source(edge)
        target = edge_target(edge)

        if (
            source in selected_ids
            and target in selected_ids
        ):
            result.append(
                copy.deepcopy(edge)
            )

    return result


# ======================================================================
# END: MASTER GRAPH EXTRACTION
# ======================================================================


# ======================================================================
# BEGIN: MATRIX RECONCILIATION
# DO NOT EDIT
# ======================================================================


def build_matrix_reconciliation(
    master_data: dict[str, Any],
) -> dict[str, Any]:

    nodes = get_nodes(
        master_data
    )

    edges = get_edges(
        master_data
    )

    groups = classify_nodes(
        nodes
    )

    selected = (
        groups["functions"]
        + groups["outcomes"]
        + groups["matrix"]
    )

    selected_ids = {
        node_id(node)
        for node in selected
        if node_id(node)
    }

    selected_edges = (
        select_edges_for_nodes(
            edges,
            selected_ids,
        )
    )

    return make_candidate_graph(
        name="ledger_set_matrix_reconciliation",
        strategy="source_function_outcome_matrix",
        source_master=master_data,
        nodes=selected,
        edges=selected_edges,
    )


# ======================================================================
# END: MATRIX RECONCILIATION
# ======================================================================


# ======================================================================
# BEGIN: PHASE RECONCILIATION
# DO NOT EDIT
# ======================================================================


def build_phase_reconciliation(
    master_data: dict[str, Any],
) -> dict[str, Any]:

    nodes = get_nodes(
        master_data
    )

    edges = get_edges(
        master_data
    )

    groups = classify_nodes(
        nodes
    )

    selected = (
        groups["phases"]
        + groups["glyphs"]
        + groups["emblems"]
        + groups["functions"]
        + groups["objects"]
        + groups["outcomes"]
        + groups["symbols"]
    )

    selected_ids = {
        node_id(node)
        for node in selected
        if node_id(node)
    }

    selected_edges = (
        select_edges_for_nodes(
            edges,
            selected_ids,
        )
    )

    return make_candidate_graph(
        name="ledger_set_phase_reconciliation",
        strategy="source_phase_glyph_emblem",
        source_master=master_data,
        nodes=selected,
        edges=selected_edges,
    )


# ======================================================================
# END: PHASE RECONCILIATION
# ======================================================================


# ======================================================================
# BEGIN: COMBINED RECONCILIATION
# DO NOT EDIT
# ======================================================================


def build_combined_reconciliation(
    matrix: dict[str, Any],
    phase: dict[str, Any],
    master_data: dict[str, Any],
) -> dict[str, Any]:

    master_nodes = get_nodes(
        master_data
    )

    master_edges = get_edges(
        master_data
    )

    selected_ids = {
        node_id(node)
        for node in (
            matrix["nodes"]
            + phase["nodes"]
        )
        if node_id(node)
    }

    # Use canonical master node objects wherever possible.
    master_index = {
        node_id(node): node
        for node in master_nodes
        if node_id(node)
    }

    nodes = [
        copy.deepcopy(
            master_index[
                identifier
            ]
        )
        for identifier in sorted(
            selected_ids
        )
        if identifier in master_index
    ]

    edges = select_edges_for_nodes(
        master_edges,
        selected_ids,
    )

    return make_candidate_graph(
        name="ledger_set_combined_reconciliation",
        strategy="canonical_union_of_matrix_and_phase_views",
        source_master=master_data,
        nodes=nodes,
        edges=edges,
    )


# ======================================================================
# END: COMBINED RECONCILIATION
# ======================================================================


# ======================================================================
# BEGIN: GRAPH VALIDATION
# DO NOT EDIT
# ======================================================================


def validate_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:

    node_ids = [
        node_id(node)
        for node in nodes
        if node_id(node)
    ]

    unique_ids = set(
        node_ids
    )

    duplicates = sorted(
        {
            identifier
            for identifier in node_ids
            if node_ids.count(identifier) > 1
        }
    )

    adjacency = defaultdict(list)

    indegree = {
        identifier: 0
        for identifier in unique_ids
    }

    dangling = []
    invalid_edges = []

    for edge in edges:

        source = edge_source(edge)
        target = edge_target(edge)

        if not source or not target:
            invalid_edges.append(
                copy.deepcopy(edge)
            )
            continue

        if source not in unique_ids:
            dangling.append({
                "type": "missing_source",
                "source": source,
                "target": target,
            })
            continue

        if target not in unique_ids:
            dangling.append({
                "type": "missing_target",
                "source": source,
                "target": target,
            })
            continue

        adjacency[
            source
        ].append(target)

        indegree[
            target
        ] += 1

    queue = deque(
        sorted(
            identifier
            for identifier, degree
            in indegree.items()
            if degree == 0
        )
    )

    visited = 0

    while queue:
        current = queue.popleft()
        visited += 1

        for target in adjacency[current]:
            indegree[target] -= 1

            if indegree[target] == 0:
                queue.append(target)

    cycle_nodes = sorted(
        identifier
        for identifier, degree
        in indegree.items()
        if degree > 0
    )

    return {
        "valid": (
            not duplicates
            and not dangling
            and not invalid_edges
            and not cycle_nodes
        ),

        "node_count": len(nodes),

        "edge_count": len(edges),

        "unique_node_count":
            len(unique_ids),

        "duplicate_node_ids":
            duplicates,

        "dangling_edges":
            dangling,

        "invalid_edges":
            invalid_edges,

        "acyclic":
            not cycle_nodes,

        "cycle_nodes":
            cycle_nodes,

        "topological_nodes_visited":
            visited,
    }


def make_candidate_graph(
    name: str,
    strategy: str,
    source_master: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:

    graph_identity = {
        "name": name,
        "strategy": strategy,
        "nodes": [
            node_id(node)
            for node in nodes
        ],
        "edges": [
            (
                edge_source(edge),
                edge_target(edge),
                edge_relation(edge),
            )
            for edge in edges
        ],
    }

    return {
        "schema":
            "dagtko.ledger-set.candidate-dag.v3",

        "generator": {
            "name":
                "ledger-set-reconciliation",

            "version":
                SCRIPT_VERSION,
        },

        "candidate": True,

        "canonical_source_modified":
            False,

        "graph": {
            "id":
                stable_hash(
                    graph_identity
                )[:20],

            "name":
                name,

            "strategy":
                strategy,

            "directed":
                True,
        },

        "source": {
            "master_sha256":
                stable_hash(
                    source_master
                ),
        },

        "validation":
            validate_graph(
                nodes,
                edges,
            ),

        "nodes":
            nodes,

        "edges":
            edges,
    }


# ======================================================================
# END: GRAPH VALIDATION
# ======================================================================


# ======================================================================
# BEGIN: MASTER AUDIT
# DO NOT EDIT
# ======================================================================


def audit_master_graph(
    master_data: dict[str, Any],
) -> dict[str, Any]:

    nodes = get_nodes(
        master_data
    )

    edges = get_edges(
        master_data
    )

    groups = classify_nodes(
        nodes
    )

    actual = {
        "function_tags":
            len(groups["functions"]),

        "outcomes":
            len(groups["outcomes"]),

        "matrix_entries":
            len(groups["matrix"]),

        "phases":
            len(groups["phases"]),

        "physical_phase_glyphs":
            len(groups["glyphs"]),

        "physical_emblems":
            len(groups["emblems"]),

        "objects":
            len(groups["objects"]),

        "field_specs":
            len(groups["fields"]),

        "nodes":
            len(nodes),

        "edges":
            len(edges),
    }

    comparison = {}

    for key, expected in (
        EXPECTED_COUNTS.items()
    ):
        if key in actual:
            comparison[key] = {
                "expected":
                    expected,

                "actual":
                    actual[key],

                "matches":
                    expected == actual,
            }

    declared_functions = set(
        master_data
        .get("semantics", {})
        .get("function_tags", {})
        .keys()
    )

    actual_functions = {
        str(
            node.get("label", "")
        )
        for node in groups["functions"]
    }

    return {
        "schema":
            "dagtko.ledger-set.master-audit.v3",

        "actual_counts":
            actual,

        "integrity_comparison":
            comparison,

        "function_semantics": {
            "declared":
                sorted(
                    declared_functions
                ),

            "actual":
                sorted(
                    actual_functions
                ),

            "missing":
                sorted(
                    declared_functions
                    - actual_functions
                ),

            "unexpected":
                sorted(
                    actual_functions
                    - declared_functions
                ),
        },

        "graph_validation":
            validate_graph(
                nodes,
                edges,
            ),
    }


# ======================================================================
# END: MASTER AUDIT
# ======================================================================


# ======================================================================
# BEGIN: OUTPUT GENERATION
# DO NOT EDIT
# ======================================================================


def build_dot(
    graph: dict[str, Any],
) -> str:

    lines = [
        "digraph DAGTKO {",
        "    rankdir=TB;",
        "    node [shape=box];",
    ]

    for node in graph["nodes"]:

        identifier = node_id(node)

        label = str(
            node.get(
                "label",
                identifier,
            )
        )

        label = (
            label
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )

        lines.append(
            f'    "{identifier}" '
            f'[label="{label}"];'
        )

    for edge in graph["edges"]:

        source = edge_source(edge)
        target = edge_target(edge)

        lines.append(
            f'    "{source}" -> "{target}";'
        )

    lines.append(
        "}"
    )

    return "\n".join(
        lines
    ) + "\n"


def write_graph(
    directory: Path,
    graph: dict[str, Any],
) -> None:

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_json(
        directory / "dag.json",
        graph,
    )

    write_json(
        directory / "nodes.json",
        graph["nodes"],
    )

    write_json(
        directory / "edges.json",
        graph["edges"],
    )

    (
        directory / "dag.dot"
    ).write_text(
        build_dot(graph),
        encoding="utf-8",
    )


def build_report(
    master_path: Path,
    inventory: dict[str, Any],
    audit: dict[str, Any],
    matrix: dict[str, Any],
    phase: dict[str, Any],
    combined: dict[str, Any],
) -> dict[str, Any]:

    return {
        "schema":
            "dagtko.ledger-set.reconciliation-report.v3",

        "script_version":
            SCRIPT_VERSION,

        "canonical_source_modified":
            False,

        "master_source": {
            "path":
                str(master_path),

            "sha256":
                sha256_file(
                    master_path
                ),
        },

        "source_inventory":
            inventory,

        "master_audit":
            audit,

        "reconciliations": {
            "matrix": {
                "graph_id":
                    matrix["graph"]["id"],

                "nodes":
                    len(matrix["nodes"]),

                "edges":
                    len(matrix["edges"]),

                "valid":
                    matrix["validation"]["valid"],
            },

            "phase": {
                "graph_id":
                    phase["graph"]["id"],

                "nodes":
                    len(phase["nodes"]),

                "edges":
                    len(phase["edges"]),

                "valid":
                    phase["validation"]["valid"],
            },

            "combined": {
                "graph_id":
                    combined["graph"]["id"],

                "nodes":
                    len(combined["nodes"]),

                "edges":
                    len(combined["edges"]),

                "valid":
                    combined["validation"]["valid"],
            },
        },

        "promotion": {
            "automatic":
                False,

            "canonical_modified":
                False,

            "manual_review_required":
                True,
        },
    }


# ======================================================================
# END: OUTPUT GENERATION
# ======================================================================


# ======================================================================
# BEGIN: MAIN FUNCTION
# DO NOT EDIT
# ======================================================================


def main() -> int:

    print()
    print(
        "DAGTKO Ledger Set Reconciliation "
        f"v{SCRIPT_VERSION}"
    )
    print("=" * 64)

    repo_root = find_repository_root()

    master_path = find_master_json(
        repo_root
    )

    master_data = read_json(
        master_path
    )

    if not isinstance(
        master_data,
        dict,
    ):
        raise ValueError(
            "Canonical Ledger Set must be a JSON object."
        )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H%M%S"
    )

    output_root = (
        repo_root
        / OUTPUT_DIRECTORY
        / timestamp
    )

    output_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    print(
        f"Repository : {repo_root}"
    )

    print(
        "Master     : "
        f"{relative_path(master_path, repo_root)}"
    )

    print(
        "Output     : "
        f"{output_root}"
    )

    print()

    print(
        "[1/6] Building source inventory..."
    )

    inventory = (
        discover_repository_sources(
            repo_root
        )
    )

    write_json(
        output_root
        / "source_inventory.json",
        inventory,
    )

    print(
        "[2/6] Auditing canonical master..."
    )

    audit = audit_master_graph(
        master_data
    )

    write_json(
        output_root
        / "source_audit.json",
        audit,
    )

    print(
        "[3/6] Building matrix reconciliation..."
    )

    matrix = build_matrix_reconciliation(
        master_data
    )

    write_graph(
        output_root / "matrix",
        matrix,
    )

    print(
        "[4/6] Building phase reconciliation..."
    )

    phase = build_phase_reconciliation(
        master_data
    )

    write_graph(
        output_root / "phase",
        phase,
    )

    print(
        "[5/6] Building combined reconciliation..."
    )

    combined = build_combined_reconciliation(
        matrix,
        phase,
        master_data,
    )

    write_graph(
        output_root / "combined",
        combined,
    )

    print(
        "[6/6] Writing reconciliation report..."
    )

    report = build_report(
        master_path,
        inventory,
        audit,
        matrix,
        phase,
        combined,
    )

    write_json(
        output_root / "report.json",
        report,
    )

    print()
    print("=" * 64)
    print("RECONCILIATION COMPLETE")
    print("=" * 64)

    print()

    print("MASTER")
    print(
        f"  Nodes : "
        f"{len(master_data.get('nodes', []))}"
    )
    print(
        f"  Edges : "
        f"{len(master_data.get('edges', []))}"
    )

    print()

    for name, graph in (
        ("MATRIX", matrix),
        ("PHASE", phase),
        ("COMBINED", combined),
    ):

        validation = graph[
            "validation"
        ]

        print(name)

        print(
            f"  Nodes : "
            f"{validation['node_count']}"
        )

        print(
            f"  Edges : "
            f"{validation['edge_count']}"
        )

        print(
            f"  Acyclic : "
            f"{validation['acyclic']}"
        )

        print(
            f"  Valid : "
            f"{validation['valid']}"
        )

        print()

    print("MASTER INTEGRITY")

    for key, result in audit[
        "integrity_comparison"
    ].items():

        status = (
            "OK"
            if result["matches"]
            else "MISMATCH"
        )

        print(
            f"  {key:<25}"
            f"{result['actual']} / "
            f"{result['expected']} "
            f"[{status}]"
        )

    print()

    print("EXTERNAL SOURCES")

    for key, result in inventory[
        "expected_external_sources"
    ].items():

        status = (
            "FOUND"
            if result["found"]
            else "MISSING"
        )

        print(
            f"  {key:<20}"
            f"[{status}] "
            f"{result['declared_name']}"
        )

    print()

    print(
        "SAFE OUTPUT:"
    )

    print(
        f"  {output_root}"
    )

    print()

    print(
        "Canonical Ledger Set was NOT modified."
    )

    print(
        "No candidate DAG was promoted automatically."
    )

    print()

    return 0


# ======================================================================
# END: MAIN FUNCTION
# ======================================================================


# ======================================================================
# BEGIN: SELF-CHECK
# DO NOT EDIT
# ======================================================================


REQUIRED_FUNCTIONS = (
    "find_repository_root",
    "find_master_json",
    "discover_repository_sources",
    "classify_nodes",
    "build_matrix_reconciliation",
    "build_phase_reconciliation",
    "build_combined_reconciliation",
    "validate_graph",
    "audit_master_graph",
    "build_dot",
    "write_graph",
    "build_report",
    "main",
)


def self_check() -> None:

    missing = [
        name
        for name in REQUIRED_FUNCTIONS
        if name not in globals()
    ]

    if missing:
        raise RuntimeError(
            "Reconciliation script is incomplete. "
            "Missing functions: "
            + ", ".join(missing)
        )


# ======================================================================
# END: SELF-CHECK
# ======================================================================


# ======================================================================
# BEGIN: ENTRY POINT
# DO NOT EDIT
# ======================================================================


if __name__ == "__main__":

    try:

        self_check()

        raise SystemExit(
            main()
        )

    except KeyboardInterrupt:

        print(
            "\nInterrupted.",
            file=sys.stderr,
        )

        raise SystemExit(130)

    except Exception as exc:

        print(
            "\nERROR:",
            str(exc),
            file=sys.stderr,
        )

        raise SystemExit(1)


# ======================================================================
# END: ENTRY POINT
# ======================================================================
