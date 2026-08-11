# DAG Substrate — Turnkey Order (Open Source)

One-command closed loop: **Node · Edge · Event · Projection** + Bucket gate + MCP surface + Open-Source Visualizers.

## Prerequisites

- Debian Linux / Ubuntu (ARM64 or x86_64)
- Packages: `postgresql`, `redis-server`, `python3`, `python3-pip`, `octave`, `graphviz` (or Docker / Docker Compose)

## Turnkey Order (exact sequence)

### 1. Place the package

```
foundation/
├── docker-compose.yml
├── .env.example
├── TURNKEY.md          ← this file
├── Makefile
├── README.md
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── mcp/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py
│   └── llm_adapter.py
├── visualizer/
│   ├── dag_visualizer.py
│   ├── dag_web_live.py
│   └── dag_cli.py
├── sql/
│   ├── 01_schema.sql
│   ├── 02_projections.sql
│   ├── 03_constraints.sql
│   ├── 04_fragments_contracts.sql
│   └── 05_seed.sql
├── scripts/
│   ├── up_native.sh
│   ├── down_native.sh
│   ├── up.sh
│   └── approval_consumer.py
├── tests/
│   └── test_closed_loop.py
└── matlab/
    ├── octave_visualizer.m
    ├── connect_and_pull.m
    ├── dag_turnkey_present.m
    └── postgresql-42.7.3.jar
```

### 2. (Optional) Environment Configuration

```bash
cp .env.example .env
# Defaults work out of the box for local turnkey
```

### 3. Bring Everything Up (Turn the Key)

```bash
cd foundation

# Option A: Native mode (recommended, fastest)
./scripts/up_native.sh
# or: make up-native

# Option B: Docker mode
./scripts/up.sh
# or: make up
```

What this does, in order:
1. Starts PostgreSQL and Redis.
2. Initializes DB role `dag` and database `dag_substrate`.
3. Runs SQL migrations in numeric order (schema → projections → constraints → fragments → seed).
4. Launches Ingest API (`http://localhost:8000`), MCP Server (`http://localhost:8001`), and Live Visualizer (`http://localhost:8050`).
5. Polls until all healthchecks pass.
6. Runs the closed-loop proof query (Node + Edge + Event + Projection counts).
7. Generates static high-res DAG plot (`dag_graph.png` and `dag_graph.svg`).

### 4. Verify the Closed Loop

```bash
# Pytest test suite
make test

# Hit Ingest API
curl http://localhost:8000/health
curl http://localhost:8000/work-orders

# Hit MCP tools catalog
curl http://localhost:8001/tools

# Open Live Visualizer in browser
# http://localhost:8050
```

### 5. Open-Source Visualizations

```bash
# Python NetworkX GUI & Plot
make visualize

# GNU Octave Visualizer
make octave

# CLI ASCII & DOT summary
make cli
```

### 6. Tear Down

```bash
# For native mode:
make down-native

# For docker mode:
make down
```
