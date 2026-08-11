"""
Approval Edge consumer (Redis Streams → wait + SLA race).
Simulates the human-gated Approval → Execution path without requiring Temporal yet.
When Temporal is later bound, this logic moves into a workflow activity.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import redis
import psycopg2
import psycopg2.extras
import httpx

psycopg2.extras.register_uuid()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://dag:dag_substrate@localhost:5432/dag_substrate"
)
INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8000")
STREAM = "dag:edges"
GROUP = "approval-workers"
CONSUMER = f"worker-{uuid.uuid4().hex[:8]}"


def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True)


def ensure_group(r):
    try:
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def sla_hours_for(wo_id: str) -> float:
    """Read current SLA_horizon Bucket (versioned fact)."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT constraint_body->>'max_hours'
        FROM buckets
        WHERE bucket_name = 'SLA_horizon' AND effective_to IS NULL
        ORDER BY version DESC LIMIT 1
        """
    )
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row and row[0] else 48.0


def process_approval_requested(edge_id: str, to_node_id: str, correlation_id: str | None):
    """
    Domain behavior:
    - Enter wait for human Approval Edge
    - Race against SLA timeout
    - On timeout emit a system Timeout Edge (still append-only)
    """
    hours = sla_hours_for(to_node_id)
    deadline = datetime.now(timezone.utc) + timedelta(hours=hours)
    print(f"[approval] WO {to_node_id} entered wait; SLA deadline {deadline.isoformat()}")

    # Poll Projection until status leaves PendingApproval or deadline passes
    client = httpx.Client(base_url=INGEST_URL, timeout=10.0)
    while datetime.now(timezone.utc) < deadline:
        try:
            r = client.get(f"/work-orders/{to_node_id}")
            if r.status_code == 200:
                status = r.json().get("status")
                if status in ("Approved", "Rejected", "Cancelled", "InExecution", "Completed"):
                    print(f"[approval] WO {to_node_id} resolved to {status}")
                    return
        except Exception as e:
            print(f"[approval] poll error: {e}")
        time.sleep(5)

    # SLA breach → emit Timeout Edge (append-only)
    print(f"[approval] SLA timeout for WO {to_node_id}; emitting Timeout")
    # Need a system node as from; use ApprovalGate if present
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT id FROM nodes WHERE node_type='ApprovalGate' LIMIT 1")
    row = cur.fetchone()
    from_id = str(row[0]) if row else to_node_id
    conn.close()

    payload = {
        "edge_type": "Timeout",
        "from_node_id": from_id,
        "to_node_id": to_node_id,
        "props": {"reason": "SLA_horizon exceeded", "hours": hours},
        "correlation_id": correlation_id,
        "bucket_names": [],  # system timeout bypasses business Buckets
    }
    try:
        r = client.post("/edges/emit", json=payload)
        print(f"[approval] Timeout emit → {r.status_code} {r.text}")
    except Exception as e:
        print(f"[approval] Timeout emit failed: {e}")


def main():
    r = get_redis()
    ensure_group(r)
    print(f"[approval] consumer {CONSUMER} listening on {STREAM}")

    while True:
        messages = r.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=10, block=5000)
        if not messages:
            continue
        for stream, entries in messages:
            for msg_id, fields in entries:
                edge_type = fields.get("edge_type")
                if edge_type == "ApprovalRequested":
                    process_approval_requested(
                        fields.get("edge_id"),
                        fields.get("to"),
                        fields.get("correlation_id") or None,
                    )
                r.xack(STREAM, GROUP, msg_id)


if __name__ == "__main__":
    main()
