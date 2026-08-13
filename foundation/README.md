# DAG Substrate Foundation (Open Source)

Event-sourced, append-only **Node · Edge · Event · Projection** substrate with Bucket gates, MCP surface, and open-source visualizers (GNU Octave, Python NetworkX, Cytoscape.js Live Web UI).

## Start here

**→ See [TURNKEY.md](TURNKEY.md) for the exact one-command bring-up order.**

```bash
cd foundation

# Option A: Native Mode (Fastest, zero container overhead)
./scripts/up_native.sh

# Option B: Docker Mode
./scripts/up.sh
```

That builds and starts Postgres, Redis, Ingest API, MCP, and Live Web Visualizer, then proves the closed loop.

## Package layout

```
foundation/
├── TURNKEY.md                 # ordered bring-up + verification
├── docker-compose.yml         # full stack
├── .env.example
├── Makefile
├── api/                       # Ingest API (Dockerfile + FastAPI)
├── mcp/                       # MCP tool server + LLM adapter
├── visualizer/                # Open-Source Visualizers (Python GUI, Web UI, CLI)
│   ├── dag_visualizer.py
│   ├── dag_web_live.py
│   └── dag_cli.py
├── sql/                       # 01→05 init order (do not reorder)
├── scripts/
│   ├── up_native.sh           # native turnkey bring-up
│   ├── down_native.sh         # native shutdown
│   ├── up.sh                  # docker turnkey bring-up
│   └── approval_consumer.py
├── tests/                     # closed-loop architectural tests
└── matlab/                    # GNU Octave & MATLAB analytics / visualizers
    ├── octave_visualizer.m
    ├── connect_and_pull.m
    ├── dag_turnkey_present.m
    └── postgresql-42.7.3.jar
```

## Character (non-negotiable)

- Every business action becomes a typed Edge.
- Projections are the sole current-truth surface.
- Events remain append-only; historical Edges are never rewritten.
- Buckets gate Edge emission; refusal produces zero mutation.
- Replay from the Event stream regenerates every Projection.
- Fragment birth occurs through creation Edge + Event only.
- Contracts are the sole legal Fragment crossing points.

## Endpoints

| Surface | URL |
|---------|-----|
| Ingest API | http://localhost:8000 |
| MCP tools | http://localhost:8001 |
| Live Visualizer | http://localhost:8050 |
| Postgres | localhost:5432 (dag / dag_substrate) |
| Redis | localhost:6379 |

## Optional Commands

```bash
make test       # host-side pytest against live stack
make visualize  # generate high-res PNG and SVG graph plots
make web        # run live interactive touch visualizer
make octave     # run GNU Octave analytics visualizer
make cli        # ASCII terminal summary + Graphviz DOT
make down-native # stop native services
```

---

## Dual Agentic + Dynamic DAG Extension

See root `README.md` Capability Statement.

- `agents/` — AutoGen and ADK thin adapters sharing one substrate.
- `dynamic_dag/` — NetworkX-powered tools for sequential, parallel, conditional, hierarchical DAGs, and `mutation_protocol.py` for two-layer immutable foundation / append-only dynamic events.
- `llm/` — Local Ollama grounding + MCP image-generation stub.
- `matlab/analysis/` — Full-scale MATLAB / Octave analysis framework.

Seed is now the Ledger Set (WorkOrder language removed). Content is dynamically mutable after burn-in; representational identity is not. Details: [side_project/burnin_inspection/README.md](../side_project/burnin_inspection/README.md).
