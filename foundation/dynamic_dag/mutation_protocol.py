"""Two-layer DAG mutation protocol: immutable foundation + append-only dynamic events."""
from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping

IMMUTABLE_FIELDS = frozenset({
    "id", "node_id", "identity", "external_ref", "canonical_type",
    "node_type", "rank", "layer", "fragment_id",
})
MUTABLE_FIELDS = frozenset({
    "content", "description", "statement", "metadata", "external_refs", "embedding",
})

@dataclass(frozen=True)
class MutationProposal:
    node_id: str
    content: Mapping[str, Any]
    reason: str
    actor: Mapping[str, Any] = field(default_factory=dict)
    expected_content_hash: str | None = None

@dataclass(frozen=True)
class ValidationResult:
    allowed: bool
    reasons: tuple[str, ...] = ()
    identity_preserved: bool = True
    topology_preserved: bool = True
    content_only: bool = True

    def as_dict(self):
        return {"allowed": self.allowed, "reasons": list(self.reasons),
                "identity_preserved": self.identity_preserved,
                "topology_preserved": self.topology_preserved,
                "content_only": self.content_only}

def canonical_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

def validate_mutation(projection: Mapping[str, Any], proposal: MutationProposal) -> ValidationResult:
    reasons = []
    if str(projection.get("node_id", projection.get("id", ""))) != proposal.node_id:
        reasons.append("node_id_mismatch")
    if proposal.expected_content_hash is not None:
        current = projection.get("content", projection.get("props", {}))
        if canonical_hash(current) != proposal.expected_content_hash:
            reasons.append("stale_projection")
    forbidden = IMMUTABLE_FIELDS.intersection(proposal.content.keys())
    if forbidden:
        reasons.append("immutable_fields:" + ",".join(sorted(forbidden)))
    unknown = set(proposal.content).difference(MUTABLE_FIELDS)
    if unknown:
        reasons.append("unsupported_fields:" + ",".join(sorted(unknown)))
    return ValidationResult(
        allowed=not reasons,
        reasons=tuple(reasons),
        identity_preserved=not any(r.startswith("immutable_fields") for r in reasons),
        topology_preserved=True,
        content_only=not any(r.startswith("unsupported_fields") for r in reasons),
    )

def build_content_mutation_event(projection, proposal, validation, *, correlation_id=None, causation_id=None):
    if not validation.allowed:
        raise ValueError("cannot build event from refused mutation: " + ";".join(validation.reasons))
    previous = projection.get("content", projection.get("props", {}))
    return {
        "event_type": "content_mutation",
        "node_id": proposal.node_id,
        "payload": {
            "previous_content_hash": canonical_hash(previous),
            "content": dict(proposal.content),
            "reason": proposal.reason,
            "actor": dict(proposal.actor),
            "validation": validation.as_dict(),
        },
        "correlation_id": correlation_id,
        "causation_id": causation_id,
    }

def apply_content_projection(projection, event):
    if event.get("event_type") != "content_mutation":
        raise ValueError("unsupported event type")
    result = dict(projection)
    result["content"] = dict(event.get("payload", {}).get("content", {}))
    result["content_hash"] = canonical_hash(result["content"])
    return result
