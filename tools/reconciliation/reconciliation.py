#!/usr/bin/env python3
"""
DAGTKO Ledger Set Reconciliation
=================================


Run from the DAGTKO repository root:


    python tools/reconciliation/reconcile_ledger_set.py


The script:


1. Locates the DAGTKO repository root.
2. Locates domain-docs/ledger/.
3. Reads Ledger Set source material without modifying it.
4. Builds:
       - Matrix reconciliation
       - Phase reconciliation
       - Combined reconciliation
5. Validates each result as a DAG.
6. Writes EVERYTHING to a timestamped quarantine directory:


       _reconciliation_output/YYYY-MM-DD_HHMMSS/


Nothing in domain-docs/ledger/ is modified.


No third-party Python packages are required.
"""


from __future__ import annotations


import copy
import hashlib
import html
import json
import re
import sys
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any




# ============================================================
# CONFIGURATION
# ============================================================


SCRIPT_VERSION = "2.0.0"


LEDGER_RELATIVE_PATH = Path("domain-docs/ledger")


OUTPUT_DIRECTORY = "_reconciliation_output"


FUNCTION_COUNT = 9
OUTCOME_COUNT = 10


FUNCTION_LABELS = {
    "F01": "Function 01",
    "F02": "Function 02",
    "F03": "Function 03",
    "F04": "Function 04",
    "F05": "Function 05",
    "F06": "Function 06",
    "F07": "Vector",
    "F08": "Pivot",
    "F09": "Draft",
}


FUNCTION_TYPES = {
    "F01": "physical",
    "F02": "physical",
    "F03": "physical",
    "F04": "physical",
    "F05": "physical",
    "F06": "physical",
    "F07": "index",
    "F08": "index",
    "F09": "index",
}


OUTCOME_LABELS = {
    i: f"Outcome {i:02d}"
    for i in range(1, OUTCOME_COUNT + 1)
}


PHASES = {
    "prime": {
        "label": "Prime / Initiation",
        "outcomes": [1, 2],
        "order": 0,
    },
    "core": {
        "label": "Core / Stabilization",
        "outcomes": [3, 4, 5, 6, 7, 8],
        "order": 1,
    },
    "echo": {
        "label": "Echo / Resolution",
        "outcomes": [9, 10],
        "order": 2,
    },
}




# ============================================================
# DATA TYPES
# ============================================================


@dataclass
class Node:
    id: str
    label: str
    kind: str
    layer: str


    source_id: str | None = None
    function_id: str | None = None
    outcome_id: int | None = None
    phase: str | None = None


    status: str = "generated"


    payload: dict[str, Any] | None = None
    source_files: list[str] | None = None


    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)


        if data["payload"] is None:
            data["payload"] = {}


        if data["source_files"] is None:
            data["source_files"] = []


        return data




@dataclass
class Edge:
    source: str
    target: str
    relation: str
    layer: str


    source_id: str | None = None
    payload: dict[str, Any] | None = None


    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)


        if data["payload"] is None:
            data["payload"] = {}


        return data




# ============================================================
# BASIC UTILITIES
# ============================================================


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()


    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)


    return digest.hexdigest()




def slug(value: Any) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)


    return value.strip("_")




def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:16]


    return f"{prefix}_{digest}"




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




def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )




# ============================================================
# REPOSITORY DISCOVERY
# ============================================================


def find_repo_root() -> Path:
    """
    Find repository root by walking upward from this script.


    This makes the script safe to execute from:
        repo root
        tools/
        tools/reconciliation/
        arbitrary cwd
    """


    candidates = [
        Path(__file__).resolve().parent,
        Path.cwd().resolve(),
    ]


    checked = set()


    for candidate in candidates:
        current = candidate


        while current != current.parent:
            if current in checked:
                break


            checked.add(current)


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
        "Could not locate DAGTKO repository root."
    )




# ============================================================
# SOURCE DISCOVERY
# ============================================================


def discover_source_files(
    ledger_root: Path,
) -> dict[str, list[Path]]:


    result = {
        "html": [],
        "svg": [],
        "json": [],
        "sql": [],
        "other": [],
    }


    if not ledger_root.exists():
        return result


    for path in sorted(ledger_root.rglob("*")):


        if not path.is_file():
            continue


        suffix = path.suffix.lower()


        if suffix in {".html", ".htm"}:
            result["html"].append(path)


        elif suffix == ".svg":
            result["svg"].append(path)


        elif suffix == ".json":
            result["json"].append(path)


        elif suffix == ".sql":
            result["sql"].append(path)


        else:
            result["other"].append(path)


    return result




# ============================================================
# HTML EXTRACTION
# ============================================================


def extract_embedded_json(
    text: str,
) -> list[Any]:


    results = []


    patterns = [
        r'<script[^>]+type=["\']application/json["\'][^>]*>'
        r'(.*?)</script>',


        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>'
        r'(.*?)</script>',


        r'<script[^>]*>(.*?)</script>',
    ]


    for pattern in patterns:


        for match in re.finditer(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL,
        ):


            candidate = html.unescape(
                match.group(1)
            ).strip()


            if not candidate:
                continue


            if not (
                candidate.startswith("{")
                or candidate.startswith("[")
            ):
                continue


            try:
                results.append(
                    json.loads(candidate)
                )
            except Exception:
                continue


    return results




def inspect_html(
    path: Path,
) -> dict[str, Any]:


    text = read_text(path)


    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        text,
        re.IGNORECASE | re.DOTALL,
    )


    title = (
        html.unescape(
            title_match.group(1)
        ).strip()
        if title_match
        else path.stem
    )


    return {
        "relative_path": str(path),
        "sha256": sha256_file(path),
        "title": title,
        "text_length": len(text),
        "embedded_json": extract_embedded_json(text),
    }




# ============================================================
# SVG INSPECTION
# ============================================================


def inspect_svg(
    path: Path,
) -> dict[str, Any]:


    text = read_text(path)


    element_ids = re.findall(
        r'\bid=["\']([^"\']+)["\']',
        text,
    )


    return {
        "relative_path": str(path),
        "sha256": sha256_file(path),
        "element_ids": sorted(
            set(element_ids)
        ),
        "element_count": len(element_ids),
    }




# ============================================================
# JSON INSPECTION
# ============================================================


def walk_json(
    value: Any,
    path: str = "$",
):


    yield path, value


    if isinstance(value, dict):


        for key, child in value.items():


            yield from walk_json(
                child,
                f"{path}.{key}",
            )


    elif isinstance(value, list):


        for index, child in enumerate(value):


            yield from walk_json(
                child,
                f"{path}[{index}]",
            )




def extract_node_like_objects(
    value: Any,
) -> list[dict[str, Any]]:


    found = []


    indicators = {
        "id",
        "node_id",
        "nodeid",
        "label",
        "name",
        "type",
        "kind",
        "data",
    }


    for _, item in walk_json(value):


        if not isinstance(item, dict):
            continue


        keys = {
            str(key).lower()
            for key in item.keys()
        }


        if keys.intersection(indicators):


            found.append(
                copy.deepcopy(item)
            )


    return found




def inspect_json(
    path: Path,
) -> list[dict[str, Any]]:


    try:
        data = read_json(path)


    except Exception:
        return []


    objects = extract_node_like_objects(data)


    result = []


    for obj in objects:


        source_id = (
            obj.get("id")
            or obj.get("node_id")
            or obj.get("nodeId")
        )


        label = (
            obj.get("label")
            or obj.get("name")
            or obj.get("title")
            or ""
        )


        if source_id is None and not label:
            continue


        result.append({
            "source_file": str(path),
            "source_id": (
                str(source_id)
                if source_id is not None
                else None
            ),
            "label": str(label),
            "payload": obj,
        })


    return result




# ============================================================
# SOURCE INVENTORY
# ============================================================


def build_source_inventory(
    repo_root: Path,
    ledger_root: Path,
) -> dict[str, Any]:


    files = discover_source_files(
        ledger_root
    )


    inventory = {
        "schema": (
            "dagtko.ledger-set.source-inventory.v1"
        ),


        "script_version": SCRIPT_VERSION,


        "repository_root": str(
            repo_root
        ),


        "ledger_root": str(
            ledger_root
        ),


        "files": {},


        "html": [],
        "svg": [],
        "json_objects": [],
    }


    for category, paths in files.items():


        inventory["files"][category] = []


        for path in paths:


            relative = str(
                path.relative_to(repo_root)
            )


            inventory["files"][category].append({
                "path": relative,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            })


    for path in files["html"]:


        data = inspect_html(path)


        data["relative_path"] = str(
            path.relative_to(repo_root)
        )


        inventory["html"].append(data)


    for path in files["svg"]:


        data = inspect_svg(path)


        data["relative_path"] = str(
            path.relative_to(repo_root)
        )


        inventory["svg"].append(data)


    for path in files["json"]:


        objects = inspect_json(path)


        for obj in objects:


            obj["source_file"] = str(
                Path(
                    obj["source_file"]
                ).relative_to(repo_root)
            )


            inventory["json_objects"].append(
                obj
            )


    return inventory




# ============================================================
# CANONICAL MODEL
# ============================================================


def phase_for_outcome(
    outcome_id: int,
) -> str:


    for phase, data in PHASES.items():


        if outcome_id in data["outcomes"]:
            return phase


    raise ValueError(
        f"Unknown outcome {outcome_id}"
    )




def function_node(
    function_id: str,
) -> Node:


    return Node(
        id=f"function_{function_id.lower()}",
        label=FUNCTION_LABELS[function_id],
        kind="function",
        layer="ontology",
        function_id=function_id,
        payload={
            "function_type":
                FUNCTION_TYPES[function_id]
        },
        status="canonical",
    )




def outcome_node(
    outcome_id: int,
) -> Node:


    return Node(
        id=f"outcome_{outcome_id:02d}",
        label=OUTCOME_LABELS[outcome_id],
        kind="outcome",
        layer="ontology",
        outcome_id=outcome_id,
        phase=phase_for_outcome(
            outcome_id
        ),
        status="canonical",
    )




def matrix_node(
    function_id: str,
    outcome_id: int,
) -> Node:


    return Node(
        id=(
            f"matrix_{function_id.lower()}"
            f"_o{outcome_id:02d}"
        ),


        label=(
            f"{FUNCTION_LABELS[function_id]}"
            f" × {OUTCOME_LABELS[outcome_id]}"
        ),


        kind="matrix_entry",


        layer="matrix",


        function_id=function_id,


        outcome_id=outcome_id,


        phase=phase_for_outcome(
            outcome_id
        ),


        payload={
            "matrix": {
                "function": function_id,
                "outcome": outcome_id,
            }
        },


        status="canonical",
    )




def phase_node(
    phase: str,
) -> Node:


    data = PHASES[phase]


    return Node(
        id=f"phase_{phase}",
        label=data["label"],
        kind="phase",
        layer="phase",
        phase=phase,
        payload={
            "order": data["order"],
            "outcomes": data["outcomes"],
        },
        status="canonical",
    )




# ============================================================
# SOURCE EVIDENCE
# ============================================================


def attach_evidence(
    nodes: list[Node],
    inventory: dict[str, Any],
) -> None:


    by_id = {}
    by_label = defaultdict(list)


    for item in inventory[
        "json_objects"
    ]:


        source_id = item.get(
            "source_id"
        )


        if source_id:
            by_id[source_id] = item


        label = slug(
            item.get("label", "")
        )


        if label:
            by_label[label].append(
                item
            )


    for node in nodes:


        matches = []


        if (
            node.source_id
            and node.source_id in by_id
        ):
            matches.append(
                by_id[node.source_id]
            )


        label_key = slug(
            node.label
        )


        for item in by_label.get(
            label_key,
            [],
        ):


            if item not in matches:
                matches.append(item)


        node.payload = node.payload or {}


        node.payload[
            "source_evidence"
        ] = []


        if matches:


            node.status = (
                "canonical_source_matched"
            )


            node.source_files = sorted({
                item["source_file"]
                for item in matches
            })


            node.payload[
                "source_evidence"
            ] = matches




# ============================================================
# EDGE MANAGEMENT
# ============================================================


def dedupe_edges(
    edges: list[Edge],
) -> list[Edge]:


    seen = set()
    result = []


    for edge in edges:


        key = (
            edge.source,
            edge.target,
            edge.relation,
            edge.layer,
        )


        if key in seen:
            continue


        seen.add(key)
        result.append(edge)


    return sorted(
        result,
        key=lambda edge: (
            edge.source,
            edge.target,
            edge.relation,
        ),
    )




# ============================================================
# RECONCILIATION A
# MATRIX
# ============================================================


def build_matrix_reconciliation(
    inventory: dict[str, Any],
) -> tuple[list[Node], list[Edge]]:


    nodes = []
    edges = []


    for function_id in FUNCTION_LABELS:


        nodes.append(
            function_node(
                function_id
            )
        )


    for outcome_id in range(
        1,
        OUTCOME_COUNT + 1,
    ):


        nodes.append(
            outcome_node(
                outcome_id
            )
        )


    for function_id in FUNCTION_LABELS:


        for outcome_id in range(
            1,
            OUTCOME_COUNT + 1,
        ):


            matrix = matrix_node(
                function_id,
                outcome_id,
            )


            nodes.append(matrix)


            edges.append(
                Edge(
                    source=(
                        f"function_"
                        f"{function_id.lower()}"
                    ),
                    target=matrix.id,
                    relation="defines",
                    layer="matrix",
                )
            )


            edges.append(
                Edge(
                    source=matrix.id,
                    target=(
                        f"outcome_"
                        f"{outcome_id:02d}"
                    ),
                    relation="resolves_to",
                    layer="matrix",
                )
            )


    attach_evidence(
        nodes,
        inventory,
    )


    return (
        nodes,
        dedupe_edges(edges),
    )




# ============================================================
# RECONCILIATION B
# PHASE
# ============================================================


def build_phase_reconciliation(
    inventory: dict[str, Any],
) -> tuple[list[Node], list[Edge]]:


    nodes = []
    edges = []


    for phase in sorted(
        PHASES,
        key=lambda p: PHASES[p]["order"],
    ):


        nodes.append(
            phase_node(phase)
        )


    for function_id in FUNCTION_LABELS:


        nodes.append(
            function_node(
                function_id
            )
        )


    for function_id in FUNCTION_LABELS:


        for outcome_id in range(
            1,
            OUTCOME_COUNT + 1,
        ):


            nodes.append(
                matrix_node(
                    function_id,
                    outcome_id,
                )
            )


    edges.extend([
        Edge(
            source="phase_prime",
            target="phase_core",
            relation="phase_transition",
            layer="phase",
        ),


        Edge(
            source="phase_core",
            target="phase_echo",
            relation="phase_transition",
            layer="phase",
        ),
    ])


    for function_id in FUNCTION_LABELS:


        function_id_lower = (
            function_id.lower()
        )


        for outcome_id in range(
            1,
            OUTCOME_COUNT + 1,
        ):


            matrix_id = (
                f"matrix_{function_id_lower}"
                f"_o{outcome_id:02d}"
            )


            phase_id = (
                f"phase_{phase_for_outcome(outcome_id)}"
            )

            edges.append(
                Edge(
                    source=(
                        f"function_"
                        f"{function_id_lower}"
                    ),
                    target=matrix_id,
                    relation="defines",
                    layer="phase",
                )
            )

            edges.append(
                Edge(
                    source=matrix_id,
                    target=phase_id,
                    relation="in_phase",
                    layer="phase",
                )
            )


    attach_evidence(
        nodes,
        inventory,
    )


    return (
        nodes,
        dedupe_edges(edges),
    )
# ============================================================
# ENTRYPOINT
# ============================================================


def _has_cycle(edges: list[Edge]) -> bool:
    adj = defaultdict(list)
    nodes_set = set()

    for e in edges:
        adj[e.source].append(e.target)
        nodes_set.add(e.source)
        nodes_set.add(e.target)

    visited: dict[str, int] = {}

    def dfs(n: str) -> bool:
        if visited.get(n) == 1:
            return True
        if visited.get(n) == 2:
            return False
        visited[n] = 1
        for nb in adj.get(n, []):
            if dfs(nb):
                return True
        visited[n] = 2
        return False

    for node in nodes_set:
        if visited.get(node) is None:
            if dfs(node):
                return True

    return False


if __name__ == "__main__":
    repo_root = find_repo_root()
    ledger_root = repo_root / LEDGER_RELATIVE_PATH

    print("Repository root:", repo_root)
    print("Ledger root:", ledger_root)

    inventory = build_source_inventory(repo_root, ledger_root)

    m_nodes, m_edges = build_matrix_reconciliation(inventory)
    p_nodes, p_edges = build_phase_reconciliation(inventory)

    # Combined reconciliation: union nodes by id and combined deduped edges
    combined_nodes_map: dict[str, Node] = {n.id: n for n in (m_nodes + p_nodes)}
    combined_nodes = list(combined_nodes_map.values())
    combined_edges = dedupe_edges(m_edges + p_edges)

    cycle_found = _has_cycle(combined_edges)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    outdir = repo_root / OUTPUT_DIRECTORY / timestamp
    outdir.mkdir(parents=True, exist_ok=True)

    # Write outputs
    write_json(outdir / "inventory.json", inventory)

    def dump(name: str, nodes: list[Node], edges: list[Edge]) -> None:
        write_json(
            outdir / f"{name}.json",
            {
                "nodes": [n.to_dict() for n in nodes],
                "edges": [e.to_dict() for e in edges],
            },
        )

    dump("matrix", m_nodes, m_edges)
    dump("phase", p_nodes, p_edges)
    dump("combined", combined_nodes, combined_edges)

    print("Wrote outputs to:", outdir)
    print("Cycle detected in combined graph:" , cycle_found)

