#!/usr/bin/env bash
# Turnkey bring-up + closed-loop proof
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=============================================="
echo "  DAG Substrate — Turnkey Foundation Bring-up"
echo "=============================================="

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Desktop / Engine first."
  exit 1
fi

# Load .env if present
if [ -f .env ]; then
  # export non-comment variables
  export $(grep -v '^#' .env | xargs)
fi

API_PORT="${API_PORT:-8000}"
MCP_PORT="${MCP_PORT:-8001}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_USER="${POSTGRES_USER:-dag}"
POSTGRES_DB="${POSTGRES_DB:-dag_substrate}"

echo ""
echo "==> 1. Building and starting all services (postgres, redis, api, mcp)"
docker compose up -d --build

echo ""
echo "==> 2. Waiting for full stack health"
for i in {1..60}; do
  PG_OK=0; RD_OK=0; API_OK=0; MCP_OK=0
  docker compose exec -T postgres pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1 && PG_OK=1
  docker compose exec -T redis redis-cli ping >/dev/null 2>&1 && RD_OK=1
  curl -sf "http://localhost:${API_PORT}/health" >/dev/null 2>&1 && API_OK=1
  curl -sf "http://localhost:${MCP_PORT}/health" >/dev/null 2>&1 && MCP_OK=1

  if [[ $PG_OK -eq 1 && $RD_OK -eq 1 && $API_OK -eq 1 && $MCP_OK -eq 1 ]]; then
    echo "    All services healthy."
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "ERROR: Timed out waiting for health."
    docker compose ps
    exit 1
  fi
  sleep 2
done

echo ""
echo "==> 3. Closed-loop proof (Node + Edge + Event + Projection jointly queryable)"
docker compose exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "
SELECT
  (SELECT count(*) FROM nodes WHERE node_type='WorkOrder') AS work_orders,
  (SELECT count(*) FROM edges WHERE edge_type='Creates') AS create_edges,
  (SELECT count(*) FROM events WHERE event_type='WorkOrderCreated') AS create_events,
  (SELECT count(*) FROM wo_current_state) AS projected_rows,
  (SELECT count(*) FROM buckets) AS buckets;
"

echo ""
echo "==> 4. API health + open WorkOrders"
curl -s "http://localhost:${API_PORT}/health" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:${API_PORT}/health"
echo ""
curl -s "http://localhost:${API_PORT}/work-orders" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:${API_PORT}/work-orders"
echo ""

echo "==> 5. MCP tools catalog"
curl -s "http://localhost:${MCP_PORT}/tools" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:${MCP_PORT}/tools"
echo ""

echo "=============================================="
echo "  TURNKEY FOUNDATION IS LIVE"
echo "=============================================="
echo "  API:     http://localhost:${API_PORT}"
echo "  MCP:     http://localhost:${MCP_PORT}"
echo "  Postgres: localhost:${POSTGRES_PORT}  (user=${POSTGRES_USER} / db=${POSTGRES_DB})"
echo "  Redis:    localhost:${REDIS_PORT}"
echo ""
echo "  Optional Approval consumer:"
echo "    docker compose --profile approval up -d"
echo ""
echo "  Tear down:  docker compose down"
echo "  Full wipe:  docker compose down -v"
echo "=============================================="

