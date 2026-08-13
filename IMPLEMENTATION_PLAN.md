# Implementation plan

1. Treat the current seed as burn-in input rather than unquestionable truth.
2. Flatten external/source data with provenance for inspection.
3. Reconcile discrepancies through explicit events.
4. Freeze foundation identity/topology/rank/layer only after burn-in validation.
5. Use `foundation/dynamic_dag/mutation_protocol.py` for dynamic content mutation.
6. Expose selection, projection reads, proposal, validation, commit, and verification as tools.
7. Keep ADK and AutoGen as adapters over the same substrate API.
8. Add tests for immutable-field refusal, stale projections, accepted mutations,
   provenance/hash preservation, replay, and unchanged topology.
9. Reduce README repetition and point details to `side_project/burnin_inspection/README.md`.
