#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# DAG Substrate Foundation — Native Turnkey Bring-up
# Zero-container, high-performance, lightweight execution across Linux & ARM64.
# Full 250-Node / 501-Edge / 90-Matrix Ledger Set Substrate
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOUNDATION_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${FOUNDATION_DIR}"

echo "=============================================="
echo "  DAG Substrate Foundation — Native Bring-up"
echo "  Ledger Set Domain: 250 Nodes / 90 Matrix"
echo "=============================================="

# 1. Load .env if present
if [ -f .env ]; then
  echo "==> Loading environment from .env"
  export $(grep -v '^#' .env | xargs)
elif [ -f .env.example ]; then
  echo "==> No .env found, copying from .env.example"
  cp .env.example .env
  export $(grep -v '^#' .env | xargs)
fi

POSTGRES_USER="${POSTGRES_USER:-dag}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-dag_substrate}"
POSTGRES_DB="${POSTGRES_DB:-dag_substrate}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
API_PORT="${API_PORT:-8000}"
MCP_PORT="${MCP_PORT:-8001}"
VISUALIZER_PORT="${VISUALIZER_PORT:-8050}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"

export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}"
export REDIS_URL="redis://localhost:${REDIS_PORT}/0"
export INGEST_URL="http://localhost:${API_PORT}"
export MCP_PORT
export API_PORT
export VISUALIZER_PORT

# 2. Start PostgreSQL service
echo ""
echo "==> 1. Ensuring PostgreSQL is running"
if command -v service >/dev/null 2>&1; then
  sudo service postgresql start || true
elif command -v systemctl >/dev/null 2>&1; then
  sudo systemctl start postgresql || true
fi

# 3. Create DB role & database
echo "==> 2. Initializing Database and Role"
sudo -u postgres psql -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_USER}') THEN CREATE ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${POSTGRES_PASSWORD}' SUPERUSER; END IF; END \$\$;" >/dev/null 2>&1 || true
sudo -u postgres psql -c "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" 2>/dev/null | grep -q 1 || sudo -u postgres createdb -O "${POSTGRES_USER}" "${POSTGRES_DB}" || true

# 4. Run SQL migrations in exact order
echo "==> 3. Running SQL migrations (01 -> 05 with 250-node seed)"
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h localhost -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -f sql/01_schema.sql >/dev/null
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h localhost -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -f sql/02_projections.sql >/dev/null
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h localhost -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -f sql/03_constraints.sql >/dev/null
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h localhost -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -f sql/04_fragments_contracts.sql >/dev/null

# Generate & apply seed
python3 sql/generate_seed.py >/dev/null
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h localhost -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -f sql/05_seed.sql >/dev/null

# 5. Start Redis service
echo "==> 4. Ensuring Redis is running"
if command -v service >/dev/null 2>&1; then
  sudo service redis-server start || true
elif command -v systemctl >/dev/null 2>&1; then
  sudo systemctl start redis || true
fi

# 6. Start Ollama daemon if installed
if command -v ollama >/dev/null 2>&1; then
  if ! curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
    echo "==> 5. Launching Ollama LLM Service"
    nohup ollama serve > /tmp/ollama.log 2>&1 &
  fi
fi

# 7. Kill any existing instances on our ports
echo "==> 6. Launching Ingest API, MCP Server, and Live Web Visualizer"
fuser -k "${API_PORT}/tcp" >/dev/null 2>&1 || true
fuser -k "${MCP_PORT}/tcp" >/dev/null 2>&1 || true
fuser -k "${VISUALIZER_PORT}/tcp" >/dev/null 2>&1 || true

# Start Ingest API
PYTHONPATH="${FOUNDATION_DIR}" setsid python3 -m uvicorn api.main:app --host 0.0.0.0 --port "${API_PORT}" --app-dir "${FOUNDATION_DIR}" </dev/null > /tmp/dag_api.log 2>&1 &
API_PID=$!
echo ${API_PID} > /tmp/dag_api.pid

# Start MCP Server
PYTHONPATH="${FOUNDATION_DIR}" setsid python3 "${FOUNDATION_DIR}/mcp/server.py" </dev/null > /tmp/dag_mcp.log 2>&1 &
MCP_PID=$!
echo ${MCP_PID} > /tmp/dag_mcp.pid

# Start Live Web Visualizer
PYTHONPATH="${FOUNDATION_DIR}" setsid python3 "${FOUNDATION_DIR}/visualizer/dag_web_live.py" </dev/null > /tmp/dag_web.log 2>&1 &
WEB_PID=$!
echo ${WEB_PID} > /tmp/dag_web.pid

# 8. Wait for health
echo "==> 7. Waiting for stack health"
for i in {1..30}; do
  API_OK=0; MCP_OK=0; WEB_OK=0
  curl -sf "http://localhost:${API_PORT}/health" >/dev/null 2>&1 && API_OK=1
  curl -sf "http://localhost:${MCP_PORT}/tools" >/dev/null 2>&1 && MCP_OK=1
  curl -sf "http://localhost:${VISUALIZER_PORT}/api/data" >/dev/null 2>&1 && WEB_OK=1

  if [[ $API_OK -eq 1 && $MCP_OK -eq 1 && $WEB_OK -eq 1 ]]; then
    echo "    All services healthy."
    break
  fi
  sleep 0.5
done

# 9. Closed-loop proof
echo ""
echo "==> 8. Closed-loop proof (Node · Edge · Event · Projection counts)"
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h localhost -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "
SELECT
  (SELECT count(*) FROM nodes) AS total_nodes,
  (SELECT count(*) FROM edges) AS total_edges,
  (SELECT count(*) FROM events) AS total_events,
  (SELECT count(*) FROM ledger_node_state) AS projected_nodes,
  (SELECT count(*) FROM matrix_entry_state) AS matrix_entries,
  (SELECT count(*) FROM buckets) AS buckets,
  (SELECT count(*) FROM fragments) AS fragments;
"

# 10. Generate static graph visualization (PNG & SVG)
echo "==> 9. Generating static DAG visualizations (dag_graph.png / dag_graph.svg)"
python3 "${FOUNDATION_DIR}/visualizer/dag_visualizer.py" || true

echo ""
echo "=============================================="
echo "  TURNKEY FOUNDATION IS LIVE & OPERATIONAL"
echo "=============================================="
echo "  Ingest API:   http://localhost:${API_PORT}"
echo "  MCP Server:   http://localhost:${MCP_PORT}/tools"
echo "  Live Web UI:  http://localhost:${VISUALIZER_PORT}"
echo "  Postgres:     localhost:${POSTGRES_PORT} (db=${POSTGRES_DB})"
echo "  Redis:        localhost:${REDIS_PORT}"
echo "  High-Res PNG: ${FOUNDATION_DIR}/dag_graph.png"
echo "  Vector SVG:   ${FOUNDATION_DIR}/dag_graph.svg"
echo "=============================================="
