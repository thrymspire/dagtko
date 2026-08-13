# Burn-in and flattened-data inspection

Do not replace the DAG with flattened data. Flattening is an inspection/reconciliation
layer; the DAG remains the structural/event model.

Pipeline:
SOURCE DATA -> FLATTEN -> INSPECT -> LLM PROPOSALS -> VALIDATE -> BURN-IN EVENTS -> FOUNDATION DAG

Flatten each candidate record with:
`source_id`, `source_path`, `source_type`, `label`, `text`, `properties`,
`relationships`, `source_hash`.

Give the LLM the flattened records plus a current graph export. It may propose
placements, but it must not mutate the DAG or invent facts.

Require JSONL proposals containing:
`source_id`, `action`, `target_node_id`, `proposed_node`, `proposed_edges`,
`rationale`, `confidence`, `provenance`.

Allowed actions:
`new_node`, `existing_node`, `merge_candidate`, `duplicate`, `ambiguous`, `reject`.

Inspection loop:
list nodes -> select candidate -> read projection -> inspect edges ->
compare provenance -> classify discrepancy -> reconcile -> rebuild -> inspect again.

The validator decides what becomes an event.

Dynamic agent loop:
select_node -> read_projection -> propose_content -> validate_mutation ->
commit_event -> rebuild_projection -> verify.

ADK and AutoGen must use the same substrate API. Agents never receive direct DB-write access.
