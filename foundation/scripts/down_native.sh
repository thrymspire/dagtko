#!/usr/bin/env bash
set -e

echo "==> Stopping native DAG services..."
if [ -f /tmp/dag_api.pid ]; then
  kill $(cat /tmp/dag_api.pid) 2>/dev/null || true
  rm -f /tmp/dag_api.pid
fi
if [ -f /tmp/dag_mcp.pid ]; then
  kill $(cat /tmp/dag_mcp.pid) 2>/dev/null || true
  rm -f /tmp/dag_mcp.pid
fi
if [ -f /tmp/dag_web.pid ]; then
  kill $(cat /tmp/dag_web.pid) 2>/dev/null || true
  rm -f /tmp/dag_web.pid
fi

fuser -k 8000/tcp >/dev/null 2>&1 || true
fuser -k 8001/tcp >/dev/null 2>&1 || true
fuser -k 8050/tcp >/dev/null 2>&1 || true

echo "DAG services stopped."
