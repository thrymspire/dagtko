# Dual-Runtime Adapter Protocol (AutoGen + ADK)

## Shared contract

Both adapters:

1. Discover tools only via the MCP catalog at `http://localhost:8001/tools` (or the optional native Python tool classes in `foundation/dynamic_dag`).
2. Emit state changes exclusively as typed Edges through the Ingest API (`POST /edges/emit`). Historical Events are never mutated.
3. Read current truth exclusively from Projections.
4. Subject every proposed Edge to Bucket evaluation before emission. Refusal produces zero mutation.
5. Share the identical Postgres event store and Redis pub/sub. No private histories, no divergent projections.

## Technique

- **Thin adapters**: each framework only translates its native tool-calling style into MCP calls (or direct native tool invocation). The substrate remains framework-agnostic.
- **Side-by-side execution**: both runtimes may be active concurrently. Correlation IDs and causation IDs keep their Event streams distinguishable for audit while sharing the same Node/Edge tables.
- **Content vs representation**: after node burn-in, adapters may mutate content properties of Nodes via new Edges; they must never alter the representational identity or rank-classification role of a node (enforced by the `content_mutation` and `rank_classification` Buckets).

## Registration order

1. Start substrate (Postgres + Redis + Ingest + MCP).
2. Register dynamic DAG tools and Ledger domain tools into the MCP catalog.
3. Launch AutoGen adapter (optional).
4. Launch ADK adapter (optional).
5. Both may call the same tools; the substrate serializes Edge emission.

## Failure classes (must remain distinct)

- Execution failure — implementation could not perform the call.
- Domain refusal — Bucket or Contract refused the transition (no mutation).
- Validation failure — resulting graph would violate acyclicity or layer rules.
- Evidence failure — state may exist but cannot be proven via Projection.
