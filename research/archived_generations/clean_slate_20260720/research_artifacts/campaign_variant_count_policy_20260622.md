# Campaign Variant Count Policy

Date: 2026-06-22

Default rule: one campaign should declare five planned trade-mechanics variants.

Expanded rule: a campaign may declare six to eight variants only when clearly better distinct mechanics exist within the same underlying edge. The expansion must be documented before PnL testing in `campaign.yaml` as `variant_expansion_rationale`.

Hard cap: more than eight variants in a single campaign fails `research.preflight`.

Guardrails:

- The campaign must still represent one potential edge, not a bundle of unrelated ideas.
- Variants six to eight must be predeclared mechanics, not post-result repairs.
- Tunable-parameter caps, total-combination caps, walk-forward discipline, holdout lock, and one-rescue rules remain unchanged.
- Historical reports that mention five variants should remain as evidence of the rule in force when those campaigns were authored.
