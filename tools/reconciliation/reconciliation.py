#!/usr/bin/env python3
"""
DAGTKO LEDGER SET RECONCILIATION
================================


PURPOSE
-------
Read the existing Ledger Set master data and produce three
NON-DESTRUCTIVE candidate DAG representations:


    1. MATRIX
       Function-tag ↔ outcome/matrix reconciliation.


    2. PHASE
       Phase/glyph/emblem reconciliation.


    3. COMBINED
       Union of the two reconciliations.


IMPORTANT
---------
This program does NOT invent function names, outcome names,
phase names, node IDs, or source relationships.


The Ledger Set itself is authoritative.


The program reads source data and creates candidate outputs.
It NEVER modifies canonical source files.


OUTPUT
------
All generated data goes into:


    _reconciliation_output/YYYY-MM-DD_HHMMSS/


Nothing is written into domain-docs/ledger/.


DEPENDENCIES
------------
Python standard library only.


RUN
---
From repository root:


    python tools/reconciliation/reconciliation.py
"""




from __future__ import annotations




# ======================================================================
# BEGIN: IMPORTS
# Do not change this block unless Python itself requires it.
# ======================================================================


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
# If Copilot or another tool needs to fix syntax, preserve every
# block outside this configuration block exactly as written.
# ======================================================================


SCRIPT_VERSION = "3.0.0"


LEDGER_DIRECTORY = Path("domain-docs/ledger")


OUTPUT_DIRECTORY = Path("_reconciliation_output")


MASTER_JSON_NAME = "ledger-set-dag.json"


# Search these repository locations for source evidence.
SOURCE_SEARCH_DIRECTORIES = [
    Path("domain-docs"),
    Path("foundation"),
]


# Expected values come from the Ledger Set integrity declaration.
# These are VALIDATION EXPECTATIONS, not graph construction data.
EXPECTED_COUNTS = {
    "function_tags": 9,
    "outcomes": 10,
    "matrix_entries": 90,
    "physical_functions": 6,
    "index_only_functions": 3,
    "phases": 3,
    "physical_phase_glyphs": 18,
    "physical_emblems": 6,
    "special_symbols": 2,
    "objects": 6,
    "field_specs": 6,
    "deployment_kit_items": 4,
    "nodes": 250,
    "edges": 501,
}


# Manifest-declared source files.
# Missing files are reported. They are NEVER fabricated.
EXPECTED_EXTERNAL_SOURCES = {
    "guide_html": "ledger-set-guide.html",
    "system_svg": "ledger-set-system.svg",
}




# ======================================================================
# END: USER CONFIGURATION
# ======================================================================




# ======================================================================
# BEGIN: IMMUTABLE RECONCILIATION ENGINE
#
# DO NOT EDIT THIS BLOCK TO "FIX" THE GRAPH.
#
# Syntax-only repairs belong in the USER CONFIGURATION block whenever
# possible. If a syntax repair is absolutely necessary here, change
# syntax only. Do not alter graph logic.
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




def find_repository_root() -> Path:
    candidates = [
        Path(__file__).resolve(),
        Path.cwd().resolve(),
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
                    and (current / "foundation").is_dir()
                )
            ):
                return current


            current = current.parent


    raise RuntimeError(
        "Could not locate the DAGTKO repository root."
    )




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




def normalize_label(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value).strip(),
    ).lower()




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
            "Could not find "
            f"{MASTER_JSON_NAME}"
        )


    return matches[0]




def discover_repository_sources(
    repo_root: Path,
) -> dict[str, Any]:


    files = []


    for directory in SOURCE_SEARCH_DIRECTORIES:


        root = (
            repo_root
            / directory
        )


        if not root.exists():
            continue


        for path in sorted(
            root.rglob("*")
        ):


            if not path.is_file():
                continue


            files.append({
                "path": relative_path(
                    path,
                    repo_root,
                ),
                "suffix": path.suffix.lower(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            })


    # Remove duplicates while preserving deterministic order.
    unique = {
        item["path"]: item
        for item in files
    }


    return {
        "count": len(unique),
        "files": [
            unique[key]
            for key in sorted(unique)
        ],
    }




def inspect_svg(
    path: Path,
    repo_root: Path,
) -> dict[str, Any]:


    text = read_text(path)


    symbol_ids = re.findall(
        r'<(?:symbol|g|path|use|svg)[^>]*'
        r'\bid=["\']([^"\']+)["\']',
        text,
        flags=re.IGNORECASE,
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


    embedded_json_count = len(
        re.findall(
            r'<script[^>]+type=["\']'
            r'application/(?:ld\+)?json'
            r'["\'][^>]*>',
            text,
            flags=re.IGNORECASE,
        )
    )


    return {
        "path": relative_path(
            path,
            repo_root,
        ),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
        "title": title,
        "embedded_json_blocks":
            embedded_json_count,
    }




def build_source_inventory(
    repo_root: Path,
    master_path: Path,
    master_data: dict[str, Any],
) -> dict[str, Any]:


    discovered = discover_repository_sources(
        repo_root
    )


    manifest = (
        master_data
        .get("svg_manifest", {})
        .get("source_files", {})
    )


    expected_sources = {}


    for key, filename in (
        EXPECTED_EXTERNAL_SOURCES.items()
    ):


        expected_sources[key] = {
            "declared_name": filename,
            "locations": [],
        }


        for path in repo_root.rglob(
            filename
        ):


            expected_sources[key][
                "locations"
            ].append(
                relative_path(
                    path,
                    repo_root,
                )
            )


    html_inventory = []
    svg_inventory = []


    for item in discovered["files"]:


        suffix = item["suffix"]


        path = (
            repo_root
            / item["path"]
        )


        if suffix in {
            ".html",
            ".htm",
        }:


            html_inventory.append(
                inspect_html(
                    path,
                    repo_root,
                )
            )


        elif suffix == ".svg":


            svg_inventory.append(
                inspect_svg(
                    path,
                    repo_root,
                )
            )


    manifest_check = {}


    for key, declared in manifest.items():


        filename = declared.get(
            "name"
        )


        declared_hash = declared.get(
            "sha256"
        )


        matches = [
            item
            for item in (
                html_inventory
                + svg_inventory
            )
            if Path(
                item["path"]
            ).name == filename
        ]


        manifest_check[key] = {
            "declared_name": filename,
            "declared_sha256":
                declared_hash,
            "found": bool(matches),
            "matches": matches,
        }


    return {
        "schema":
            "dagtko.ledger-set.source-inventory.v2",


        "master": {
            "path": relative_path(
                master_path,
                repo_root,
            ),
            "sha256":
                sha256_file(master_path),
            "size":
                master_path.stat().st_size,
        },


        "repository_sources": discovered,


        "html": html_inventory,


        "svg": svg_inventory,


        "declared_manifest": manifest,


        "manifest_verification":
            manifest_check,


        "expected_external_sources":
            expected_sources,
    }




def get_nodes(
    master_data: dict[str, Any],
) -> list[dict[str, Any]]:


    nodes = master_data.get(
        "nodes",
        []
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
        []
    )


    if not isinstance(edges, list):
        raise ValueError(
            "Master graph 'edges' must be a list."
        )


    return copy.deepcopy(edges)




def node_type(
    node: dict[str, Any],
) -> str:


    return str(
        node.get(
            "type",
            ""
        )
    )




def node_layer(
    node: dict[str, Any],
) -> int | None:


    value = node.get(
        "layer"
    )


    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None




def node_id(
    node: dict[str, Any],
) -> str:


    return normalize_id(
        node.get(
            "id",
            ""
        )
    )




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




def build_node_index(
    nodes: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:


    result = {}


    for node in nodes:


        identifier = node_id(node)


        if not identifier:
            continue


        result[identifier] = node


    return result




def classify_nodes(
    nodes: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:


    result = {
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
            result["functions"].append(node)


        elif kind == "outcome_number":
            result["outcomes"].append(node)


        elif kind == "phase":
            result["phases"].append(node)


        elif (
            "matrix" in kind
            or (
                layer == 5
                and "statement" not in kind
            )
        ):
            result["matrix"].append(node)


        elif (
            "glyph" in kind
            or "physical" in kind
            and "phase" in kind
        ):
            result["glyphs"].append(node)


        elif (
            "emblem" in kind
            or "composite" in kind
        ):
            result["emblems"].append(node)


        elif kind == "object":
            result["objects"].append(node)


        elif (
            "field" in kind
            or "field_spec" in kind
        ):
            result["fields"].append(node)


        elif "symbol" in kind:
            result["symbols"].append(node)


        elif (
            "statement" in kind
            or layer == 6
        ):
            result["statements"].append(node)


        elif kind == "section":
            result["sections"].append(node)


        elif kind == "root":
            result["root"].append(node)


        else:
            result["other"].append(node)


    return result




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




def select_transitive_boundary_edges(
    edges: list[dict[str, Any]],
    selected_ids: set[str],
) -> list[dict[str, Any]]:


    result = []


    for edge in edges:


        source = edge_source(edge)
        target = edge_target(edge)


        if (
            source in selected_ids
            or target in selected_ids
        ):


            result.append(
                copy.deepcopy(edge)
            )


    return result




def make_graph(
    name: str,
    strategy: str,
    source_master: Path,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:


    node_ids = {
        node_id(node)
        for node in nodes
        if node_id(node)
    }


    validation = validate_graph(
        nodes,
        edges,
    )


    return {
        "schema":
            "dagtko.ledger-set.candidate-dag.v2",


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
            "id": stable_hash({
                "name": name,
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
            })[:20],


            "name": name,


            "strategy": strategy,


            "directed": True,
        },


        "source": {
            "master":
                str(source_master),


            "master_sha256":
                sha256_file(
                    source_master
                ),
        },


        "validation": validation,


        "nodes": nodes,


        "edges": edges,
    }




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


    # Matrix reconciliation is deliberately SOURCE-DRIVEN.
    #
    # We retain:
    #   function tags
    #   outcome numbers
    #   actual matrix entries
    #
    # and their direct relationships.
    #
    # We do NOT manufacture a 9x10 matrix if the master does
    # not contain one.


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


    return make_graph(
        name="ledger_set_matrix_reconciliation",
        strategy=(
            "source_function_outcome_matrix"
        ),
        source_master=Path(
            MASTER_JSON_NAME
        ),
        nodes=selected,
        edges=selected_edges,
    )




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


    # Phase reconciliation uses the actual phase structure
    # declared by the master data.
    #
    # Physical glyphs, emblems, and phase nodes are retained.
    # Function/object nodes are retained when they provide the
    # actual source relation for those phase structures.


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


    return make_graph(
        name="ledger_set_phase_reconciliation",
        strategy=(
            "source_phase_glyph_emblem"
        ),
        source_master=Path(
            MASTER_JSON_NAME
        ),
        nodes=selected,
        edges=selected_edges,
    )
# ======================================================================
# BEGIN: ENTRY POINT
# Do not edit.
# ======================================================================

if __name__ == "__main__":
    try:
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