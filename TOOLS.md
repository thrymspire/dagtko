# DAG Toolkit Open Source (`dagtko`) — Software & Tooling Stack

This repository provides a 100% open-source, turnkey realization of the **Node · Edge · Event · Projection** DAG Substrate.

Every component is chosen specifically to run with minimal footprint, high performance, and zero proprietary dependencies on **ARM64 Debian Linux under Weston** (such as a Pixel 10 Pro XL Linux VM environment).

---

## 1. Complete Software & Tooling Inventory

| Component | Software / Tool | License | Role & Rationale | Memory Footprint |
|-----------|-----------------|---------|------------------|------------------|
| **Core Database** | PostgreSQL 16+ | PostgreSQL License | ACID-compliant event-sourced append-only storage, triggers, and JSON projections. | ~30 MB idle |
| **Pub/Sub Broker** | Redis 7+ | BSD-3-Clause | Ultra-fast in-memory streaming broker for Approval consumer and SLA events. | ~10 MB idle |
| **Ingest API** | FastAPI + Uvicorn | MIT / BSD | Async, typed REST API for Edge emission and WorkOrder state queries. | ~35 MB |
| **Tool Protocol** | Model Context Protocol (MCP) | MIT | Standardized tool exposure allowing LLMs to ground reasoning in live DB projections. | ~30 MB |
| **MATLAB Alternative 1** | GNU Octave | GNU GPLv3 | 100% open-source numerical and plotting environment running `.m` scripts natively. | ~40 MB on run |
| **MATLAB Alternative 2** | Python + NetworkX + Matplotlib | BSD / PSF | Direct DAG graph layout engine, node coloring, critical path metrics, and PNG/SVG export. | ~45 MB on run |
| **MATLAB Alternative 3** | Cytoscape.js + Dagre (Web UI) | MIT | Live interactive touch-friendly graph visualizer for high-DPI screens under Weston. | ~15 MB server |
| **MATLAB Alternative 4** | Graphviz (`dot`) | CPL | Deterministic hierarchical directed graph layout and vector rendering. | CLI utility |
| **Test Suite** | Pytest + HTTPX | MIT / BSD | Automated closed-loop architectural integrity and regression test suite. | Ephemeral |
| **Compositor Support** | Wayland / Weston | MIT | Native windowing support without heavy X11 desktop environments. | Native OS |

---

## 2. Why These Tools Are Optimized for Pixel 10 Pro XL & Weston

1. **ARM64 Native Execution**:
   - All tools run natively compiled on `aarch64` without emulation penalties.
2. **Zero Proprietary Licenses**:
   - Replaces proprietary MATLAB with GNU Octave and lightweight Python/Web visualizers.
3. **Dual Turnkey Bring-up**:
   - **Native Mode (`./scripts/up_native.sh`)**: Runs directly on system services with zero containerization overhead. Starts the entire 5-tier stack in under 2 seconds.
   - **Docker Mode (`./scripts/up.sh`)**: Runs isolated containers via Docker Compose when containers are available.
4. **Touch & High-DPI Display Support**:
   - The interactive web visualizer (`foundation/visualizer/dag_web_live.py`) runs at `http://localhost:8050` with full pinch-to-zoom, tap-to-inspect, and smooth responsive canvas rendering tailored for mobile and touch screens.
5. **Headless & GUI Resilience**:
   - The Python graph visualizer automatically detects `WAYLAND_DISPLAY` / `DISPLAY`. If no display server is active, it falls back to high-res `Agg` headless rendering to produce crisp `dag_graph.png` and `dag_graph.svg`.

---

## 3. Visualization Tools Comparison

| Feature | GNU Octave (`.m`) | Python NetworkX/Matplotlib | Live Web Visualizer | Graphviz (`dot`) |
|---------|-------------------|----------------------------|---------------------|------------------|
| **Script Path** | `foundation/matlab/octave_visualizer.m` | `foundation/visualizer/dag_visualizer.py` | `foundation/visualizer/dag_web_live.py` | `foundation/visualizer/dag_cli.py` |
| **GUI Window** | Yes (Qt/gnuplot) | Yes (Tk/Qt/Wayland) | Browser / WebView | Static file viewer |
| **Headless Output** | Terminal log | PNG + SVG | REST JSON / HTML | DOT + PNG + SVG |
| **Touch Gesture Pan/Zoom** | No | Basic mouse | Full Touch / Pinch | No |
| **Live Real-Time Polling** | Manual | On Execution | Automatic (every 3s) | On Execution |
| **Proprietary Software Needed** | None | None | None | None |

---

## 4. Turnkey Verification Checklist

When you run `./scripts/up_native.sh` or `make up-native`, the system automatically proves:
- [x] **Node**: WorkOrder nodes registered with UUIDs and JSON payloads.
- [x] **Edge**: Typed `Creates` edges connecting WorkOrders to Specs and Fragments.
- [x] **Event**: Append-only `WorkOrderCreated` events logged with immutable audit trail.
- [x] **Projection**: `wo_current_state` projection updated automatically via DB triggers.
- [x] **Bucket Gate**: Refusal prevents mutation; approval permits edge emission.
- [x] **MCP Catalog**: LLM tool definitions exposed at `/tools`.
- [x] **Visualizer**: Real-time DAG layout and closed-loop green status badge.
