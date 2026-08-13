"""
Unit tests for the two-layer DAG mutation protocol:
immutable foundation + append-only dynamic events.
"""
import pytest
from foundation.dynamic_dag.mutation_protocol import (
    IMMUTABLE_FIELDS,
    MUTABLE_FIELDS,
    MutationProposal,
    ValidationResult,
    canonical_hash,
    validate_mutation,
    build_content_mutation_event,
    apply_content_projection,
)


def test_canonical_hash_consistency():
    d1 = {"a": 1, "b": 2}
    d2 = {"b": 2, "a": 1}
    assert canonical_hash(d1) == canonical_hash(d2)


def test_accepted_content_mutation():
    projection = {
        "node_id": "SPAN-01",
        "rank": "Prime",
        "layer": "foundation",
        "content": {"statement": "Initial operational statement."},
    }
    expected_hash = canonical_hash(projection["content"])
    proposal = MutationProposal(
        node_id="SPAN-01",
        content={"statement": "Updated dynamic operational statement.", "description": "Extended notes"},
        reason="Refining operational guidance during burn-in validation",
        actor={"agent": "autogen_reconciler", "session": "s-123"},
        expected_content_hash=expected_hash,
    )

    validation = validate_mutation(projection, proposal)
    assert validation.allowed
    assert validation.identity_preserved
    assert validation.topology_preserved
    assert validation.content_only
    assert len(validation.reasons) == 0

    event = build_content_mutation_event(
        projection,
        proposal,
        validation,
        correlation_id="corr-456",
        causation_id="cause-789",
    )
    assert event["event_type"] == "content_mutation"
    assert event["node_id"] == "SPAN-01"
    assert event["payload"]["previous_content_hash"] == expected_hash
    assert event["payload"]["content"]["statement"] == "Updated dynamic operational statement."
    assert event["correlation_id"] == "corr-456"

    updated_projection = apply_content_projection(projection, event)
    assert updated_projection["node_id"] == "SPAN-01"
    assert updated_projection["rank"] == "Prime"
    assert updated_projection["layer"] == "foundation"
    assert updated_projection["content"]["statement"] == "Updated dynamic operational statement."
    assert updated_projection["content_hash"] == canonical_hash(updated_projection["content"])


def test_immutable_field_refusal():
    projection = {
        "node_id": "SPAN-01",
        "rank": "Prime",
        "layer": "foundation",
        "content": {"statement": "Initial statement."},
    }
    proposal = MutationProposal(
        node_id="SPAN-01",
        content={"statement": "New statement", "rank": "OverrideRank", "layer": "modified_layer"},
        reason="Attempting unauthorized topology/rank mutation",
    )
    validation = validate_mutation(projection, proposal)
    assert not validation.allowed
    assert not validation.identity_preserved
    assert any("immutable_fields:layer,rank" in r or "immutable_fields" in r for r in validation.reasons)

    with pytest.raises(ValueError, match="cannot build event from refused mutation"):
        build_content_mutation_event(projection, proposal, validation)


def test_stale_projection_refusal():
    projection = {
        "node_id": "SPAN-01",
        "content": {"statement": "Current state"},
    }
    proposal = MutationProposal(
        node_id="SPAN-01",
        content={"statement": "New state"},
        reason="Stale update",
        expected_content_hash="stale_or_invalid_hash_000000000000",
    )
    validation = validate_mutation(projection, proposal)
    assert not validation.allowed
    assert "stale_projection" in validation.reasons


def test_node_id_mismatch_refusal():
    projection = {
        "node_id": "SPAN-01",
        "content": {"statement": "Current state"},
    }
    proposal = MutationProposal(
        node_id="SPAN-02",
        content={"statement": "New state"},
        reason="Mismatched target",
    )
    validation = validate_mutation(projection, proposal)
    assert not validation.allowed
    assert "node_id_mismatch" in validation.reasons
