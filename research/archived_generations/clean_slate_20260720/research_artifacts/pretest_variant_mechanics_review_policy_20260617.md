# Pre-test variant mechanics review policy - 2026-06-17

Decision: every new variant config created after this note must include a
pre-test mechanics review before staged testing.

The review must be written before the first PnL test of the variant. If the
mechanics are not convincing at this stage, the variant must be reformulated
before testing. Reformulation before testing is allowed; changing mechanics
after seeing results is still forbidden except for the existing one allowed
parameter-space/fixed-parameter rescue rule.

Required config fields for new variants:

```yaml
research_metadata:
  mechanics_review_required: true
  mechanics_review:
    mechanic_expresses_edge: "..."
    entry_logic_rationale: "..."
    stop_loss_rationale: "..."
    target_exit_rationale: "..."
    profitability_rationale: "..."
    known_failure_modes: "..."
    pre_test_decision: approve_for_testing
```

Preflight enforces these fields when
`research_metadata.mechanics_review_required` or
`research_metadata.mechanics_review_version` is set. Legacy configs are warned
but not retroactively invalidated solely because this new field is absent.

The staged campaign runner now requires the same review before any staged test
starts. A config without `mechanics_review_required: true`, detailed rationale
fields, and `pre_test_decision: approve_for_testing` fails before a run
directory is created.

Minimum review standard:

- explain how the entry expresses the edge;
- explain why the stop and target are realistic expressions of the hypothesis,
  not arbitrary curve-fit exits;
- explain why the trade might be profitable after costs;
- list failure modes that would lead to rejection;
- explicitly approve the variant for testing before any results are observed.

This policy applies to single-edge and composite-edge campaigns.
