# DAG Fragment Substrate Toolkit (Open Source)

Event-sourced, append-only **Node · Edge · Event · Projection** substrate with Bucket gates, dual agentic runtimes (AutoGen + Google ADK), Model Context Protocol (MCP) surface, dynamic DAG toolkits, local LLM grounding (Ollama), ComfyUI dynamic image sideloading, and full-scale MATLAB / GNU Octave analysis.

Designed for universal local-native open-source operation across ARM64 (Pixel 10 Pro XL / Debian under Weston / Raspberry Pi), standard x86_64 Linux, macOS, and cloud servers.

---

## 1. Capability Statement

This substrate implements the complete **Ledger Set** domain as a living, topologically layered DAG (250 Nodes, 501 Edges, 90 Matrix Entries, 18 Glyphs, 6 Emblems). After node burn-in, **content may be changed dynamically; representational identity and rank classification roles remain immutable**.

### What the system delivers

- **Full 250-Node / 501-Edge 90-Matrix Ledger Set Seed**: Root (`ledger_root`), 5 Sections, 40 Canonical Entities (6 physical objects, 9 function tags, 10 outcome numbers, 3 phases/ranks, 6 field specs, 4 deployment kit items, 2 special symbols), 18 Phase Glyphs with vector geometry, 6 Composite Emblems, 90 Matrix Entries (`SPAN-01`..`10`, `ANCHOR-01`..`10`, etc.), and 90 Actionable Deployment Statements.
- **Shared event-sourced store**: Append-only PostgreSQL event log + Redis pub/sub driven simultaneously by two agent frameworks (AutoGen and Google ADK) through thin adapter layers.
- **Expanded MCP Server (Port 8001)**:
  - **Dynamic DAG Tools**: `dag_sequential_chain`, `dag_parallel_fan_out`, `dag_parallel_fan_in`, `dag_conditional_branch`, `dag_hierarchical_sub_dag`, `dag_validate_acyclic`, `dag_critical_path`.
  - **Domain Ledger Tools**: `list_ledger_nodes`, `get_ledger_node`, `list_matrix_entries`, `get_matrix_entry`, `emit_edge` (Bucket-gated), `get_critical_path`.
  - **Local LLM Grounding Tool**: `query_ollama_grounding` (projections-first analytical grounding).
  - **Image Generation Tool**: `generate_glyph_image` (live ComfyUI workflow dispatch or standby procedural reference).
- **Live Local LLM (Ollama)**: Wired at `http://localhost:11434` with `smollm:135m` (or `llama3.2`) for local reasoning strictly grounded over Projection facts.
- **ComfyUI Dynamic Sideload Hook**: Treated as a side-load for compatible GPU hardware (NVIDIA CUDA / ROCm / Apple Silicon). Maintains zero-overhead operation on CPU-only/ARM64 devices while preserving live `/prompt` API compatibility when pulled onto GPU-equipped hardware.
- **Interactive Live Web Visualizer (Port 8050)**: Cytoscape-powered touch/pinch reactive visualizer with 7-layer filtering, search, and real-time projection inspection (<20MB RAM footprint).
- **GNU Octave / MATLAB Analysis Framework**: Full analytical suite (`ledger_full_analysis.m`, `octave_visualizer.m`) for topological density, acyclicity, critical path, and projection replay proofs.
- **Closed-Loop Proof**: Joint verification of Node · Edge · Event · Projection invariants.

---

## 2. Higher-Layer Fragment / Contract / Composition Interleaving

The substrate separates historical occurrence from derived truth. Higher layers interleave seamlessly according to the following simple patterns:

```
┌─────────────────────────────────────────────────────────────┐
│                   COMPOSITION LAYER (L3)                     │
│  Composes cross-fragment views via Projections & Reducers   │
│  (Read-only current truth; never invents historical facts)  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Reads only through
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    CONTRACT LAYER (L2)                      │
│  Sole legal crossing points between bounded Fragments       │
│  Declares boundary nodes, allowed edge types & static shapes │
│  Bucket gates evaluate & refuse non-conforming join proposals│
└──────────────────────────────┬──────────────────────────────┘
                               │ Bridges across
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    FRAGMENT LAYER (L1)                      │
│  Bounded purposeful DAG unit (Root Node + Event Slice)      │
│  Born strictly via creation Edge + Event; immutable history │
└──────────────────────────────┬──────────────────────────────┘
                               │ Evaluated against
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    SUBSTRATE LAYER (L0)                     │
│  Append-only Node · Edge · Event · Bucket persistence       │
└─────────────────────────────────────────────────────────────┘
```

### Simple Interleaving Rules & Suggestions

1. **Fragment Interleaving (Bounded Sub-DAGs)**:
   - **Suggestion**: Encapsulate distinct operational domains or agent sessions as independent Fragments.
   - **Rule**: A Fragment is born exclusively through a typed creation Edge and its corresponding Event. Never instantiate private databases or mutate prior historical events. Dynamic sub-DAGs attach under parent nodes using `dag_hierarchical_sub_dag` or `emit_edge`.

2. **Contract Interleaving (Crossing Boundaries)**:
   - **Suggestion**: When two Fragments must interact (e.g. an Agent-driven workflow consuming a Ledger matrix asset), publish a Contract.
   - **Rule**: Contracts are the **sole legal crossing points**. A Contract declares boundary node IDs, allowed edge types, and required projection shapes. Before any cross-Fragment edge is committed, Bucket gates evaluate the contract facts; an invalid contract proposal produces an atomic `REFUSE` with zero historical mutation.

3. **Composition Interleaving (Higher-Level Views)**:
   - **Suggestion**: Build dashboards, multi-agent orchestrations, and composite workflows as Compositions.
   - **Rule**: Composition is **strictly a Projection over existing historical Edges**. Higher languages may freely compose lower facts to compute critical paths, rollups, or synthetic views, but they may never invent historical truth that bypasses the append-only event log.

---

## 3. Quick Start (Universal Turnkey)

### Universal Auto-Installer (Any Hardware)
```bash
# From repository root
./install_all.sh
```
This script automatically detects your OS (Debian/Ubuntu, RHEL/Fedora, Arch, Alpine, macOS) and hardware architecture (ARM64, x86_64, GPU/CPU), installs all system packages, configures PostgreSQL & Redis, starts Ollama, burns in the complete 250-node 90-matrix seed, runs automated tests, and brings up all services.

### Presentation & GUI Bring-up
```bash
./setup_and_present.sh
```
Runs the environment doctor, launches native turnkey services, executes the architectural test suite, prints the terminal topology, and opens the graph in your GUI desktop (`feh` / browser).

### Native Foundation Services
```bash
cd foundation && ./scripts/up_native.sh
```

---

## 4. Live Endpoints & Port Reference

| Service | Port / URL | Description |
|---------|------------|-------------|
| **Ingest & Domain API** | `http://localhost:8000` | Append-only Edge/Event emission, 90-Matrix queries, Bucket gating, LLM grounding |
| **MCP Tool Server** | `http://localhost:8001/tools` | Expanded Model Context Protocol catalog (Dynamic DAG + Image + Ledger + Grounding) |
| **Live Web Visualizer** | `http://localhost:8050` | Interactive Cytoscape touch/pinch DAG visualizer with 7-layer filtering & search |
| **PostgreSQL 16/17** | `localhost:5432` | Append-only database (`dag_substrate`, user `dag`) |
| **Redis 7+** | `localhost:6379` | Event pub/sub and stream bus (`dag:edges`) |
| **Ollama Local LLM** | `http://localhost:11434` | Local LLM inference server (`smollm:135m` / `llama3.2`) |
| **ComfyUI Sideload** | `http://localhost:8188` | Dynamic sideload image synthesis (active on GPU; standby on edge devices) |

---

## 5. Topological Layer Architecture (250 Nodes / 501 Edges)

The Ledger Set DAG enforces strict source-to-derivative topological layering:

- **Layer 0 — Root**: `ledger_root` ("The Ledger Set / Typhen").
- **Layer 1 — Sections (5 nodes)**: `sec_typhen`, `sec_index`, `sec_ledger_set`, `sec_rank`, `sec_field`.
- **Layer 2 — Canonical Entities (40 nodes)**:
  - 6 Physical Objects: `graphite_ledger`, `tri_key_clasp`, `signal_baton`, `relay_node`, `matte_coin`, `industrial_cloth`.
  - 9 Function Tags: `Vector`, `Anchor`, `Relay`, `Pivot`, `Fuse`, `Break`, `Span`, `Draft`, `Quiet`.
  - 10 Outcome Numbers: `01` (Opening Gambit) through `10` (Blind Spot).
  - 3 Phases / Ranks: `Initiation` (Prime), `Stabilization` (Core), `Resolution` (Echo).
  - 6 Field Specs, 4 Deployment Kit Items, 2 Special Symbols (`Tri-Span`, `Blank Coin`).
- **Layer 3 — Phase Glyphs (18 nodes)**: Vector mark symbols with embedded SVG geometry (`glyph_anchor_initiation`, `glyph_span_stabilization`, etc.).
- **Layer 4 — Composite Emblems (6 nodes)**: Full composite object emblems combining 3 phase marks per physical function.
- **Layer 5 — 90-Matrix Entries (90 nodes)**: Complete 9 Function × 10 Outcome matrix (`SPAN-01`..`10`, `ANCHOR-01`..`10`, `VECTOR-01`..`10`, etc.).
- **Layer 6 — Actionable Statements (90 nodes)**: Concrete deployment and tactical field instructions.

---

## 6. ComfyUI Sideload Architecture

To ensure lightweight execution on edge devices (such as ARM64 Android VMs) while maintaining full capability when cloned onto high-performance GPU hardware:

- **Edge / CPU-only hosts**: The MCP image tool operates in **sideload standby mode**, generating valid content-addressed URI references and procedural vector graphics without consuming VRAM.
- **GPU-equipped hosts**: Run `./foundation/scripts/sideload_comfyui.sh start` to launch a local ComfyUI instance. The MCP tool automatically detects the live endpoint and routes glyph/emblem synthesis prompts through ComfyUI.
- **Remote GPU hosts**: Set `export COMFYUI_URL=http://<remote-ip>:8188` to outsource image generation across the network.

---

## 7. MATLAB & GNU Octave Analysis

```bash
# Run full analytical suite in GNU Octave (100% open-source)
octave foundation/matlab/analysis/ledger_full_analysis.m

# Or run interactive visualization
octave foundation/matlab/octave_visualizer.m
```

---

## 8. License & Character

100% Open-Source stack. Append-only event store invariants, Bucket gates, and immutable representational identity remain non-negotiable; adapters, tools, and visualizers are dynamically extensible.
