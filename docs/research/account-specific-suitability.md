# Account-specific suitability

AlphaQuest keeps three decisions separate:

1. Scientific validity decides whether the mechanics and evidence are trustworthy enough to support any promotion decision.
2. Generic investment quality decides whether the valid strategy meets repository-owned return and risk objectives without assuming a particular destination account.
3. A governed account assessment replays the same valid unseen evidence against one versioned challenge, funded, or live-account rule profile.

Scientific validity must pass first. Candidate-review eligibility then requires either generic investment-quality `PASS` or `PASS` for one named account profile. An account `PASS` applies only to the recorded profile ID, version, hash, costs, trade evidence, and Monte Carlo seed. No verdict authorizes deployment.

A generic objective miss does not halt later unseen-evidence stages. A scientific-validity failure or unresolved validity evidence does halt closed. This lets a strategy that is unattractive as a general investment remain reviewable for a bounded prop-account payoff without weakening data, leakage, mechanics, stability, or evidence-sufficiency requirements.

## Migration contract

New Studio drafts may select a primary target account and comparison accounts. Compilation freezes the complete profile snapshot and canonical SHA-256 into every variant config. Preflight rejects unknown versions, profile hash drift, duplicate bindings, and a synthetic profile used as the primary deployment target. Historical configs without account bindings remain readable and are not rewritten.

The former `configured_local_profile` remains only as a synthetic compatibility simulator. The generic backtest metric is `execution_compliance_violations`; `apex_rule_violations` remains a deprecated reporting alias, but Apex rule violations are no longer a Step 6 promotion gate. They are evaluated by the selected Apex profile in Step 7.

`ResultBundleV2` records scientific-validity and generic-objective verdicts separately. `ResultBundleV3` binds those verdicts to zero or more account assessments and explicitly lists which destination profiles are candidate-review eligible. It always records that universal tradeability and deployment authorization are false.

Historical bundles are immutable. A bundle without repository-owned decision-role metadata is not retroactively classified; Studio reports its scientific validity as `NEEDS MANUAL REVIEW` until a methodology rerun creates fresh evidence.

## Apex 50K EOD profiles

The catalog contains separate reviewed profiles for:

- `apex/eod_50k/evaluation@2026-03-01`
- `apex/eod_50k/funded@2026-03-01`

The funded profile is the Apex simulated Performance Account, not a live brokerage account. It models the $2,000 EOD drawdown, intraday threshold enforcement, the $50,100 funded threshold lock, tiered contract and daily-loss limits, payout consistency and caps, and rolling inactivity. Rules that require evidence outside one account's trade log remain explicit manual attestations.

The profile's acceptance policy is deliberately stricter than mere rule compliance. For the funded account it requires at least 126 source sessions and 8,000 five-session-block paths over a 126-session horizon, with:

- no historical account closure, DLL lock, position-size rejection, or close-deadline violation;
- simulated account-closure probability no greater than 5%;
- simulated DLL-lock probability no greater than 10%;
- first-payout probability at least 70%;
- two-payout probability at least 50%;
- expected payouts after acquisition/replacement costs greater than zero;
- expected payout-to-cost ratio at least 3; and
- 95th-percentile maximum drawdown no greater than $1,500, preserving a modeled $500 buffer.

These thresholds are AlphaQuest risk policy, not Apex rules. They can be reviewed as repository methodology, but must not be tuned after seeing one strategy's results.

## Required trade evidence

The CSV or Parquet input requires `session_date`, `net_pnl`, and `contracts`. Every trade must also establish:

- path-relative adverse excursion using `intratrade_min_pnl`, `mae_currency`, or `max_adverse_excursion` with `point_value`; an absolute `intraday_min_equity` is accepted for deterministic replay only when `account_equity_before_entry` also permits a relative Monte Carlo excursion; and
- close compliance using `exit_timestamp` or `forced_flatten_compliant`.

Missing intraday or close evidence produces `NEEDS MANUAL REVIEW`; AlphaQuest does not infer compliance from closing PnL.

## Run an assessment

List available profiles:

```bash
alphaquest account list --project-root .
```

Assess a funded-account destination after the variant has frozen WFA/acceptance trade evidence:

```bash
alphaquest account assess apex/eod_50k/funded \
  --profile-version 2026-03-01 \
  --project-root . \
  --trades /absolute/path/to/stitched_oos_trades.csv \
  --config /absolute/path/to/effective_config.yaml \
  --campaign-id CAMPAIGN_ID \
  --variant-id v01 \
  --attempt-id ATTEMPT_ID \
  --data-sha256 DATA_SHA256 \
  --strategy-implementation-sha256 STRATEGY_SHA256 \
  --evaluation-price CURRENT_CHECKOUT_PRICE \
  --activation-fee CURRENT_ACTIVATION_FEE \
  --cost-source "Apex checkout screenshot or receipt" \
  --cost-observed-at 2026-08-14T12:00:00+08:00 \
  --attest no_prohibited_trading_activity_or_cross_account_hedging
```

The default output is the repository-owned `research_artifacts/account_evaluations/` tree. Each assessment is immutable and binds profile, config, data, strategy, trades, costs, attestations, run count, and seed. Studio shows hash-valid assessments alongside—but separately from—the scientific result.

## Why challenge price belongs in the decision

For an evaluation, AlphaQuest reports pass probability and expected evaluation fees per successful pass (`checkout price / pass probability`). For a newly acquired funded account, evaluation price plus activation fee is subtracted from expected approved payouts for full-lifecycle economics. For an account already held, the report also shows expected replacement cost (`closure probability × current reacquisition cost`) and net payouts after that probability-weighted cost. This prevents a strategy with frequent account replacement from appearing attractive solely because gross payouts ignore the cost of getting back to funded status; already-paid fees can still be treated correctly as sunk costs.

Prices are intentionally not hardcoded because Apex checkout prices and promotions can change. Every assessment must record the price, source, and observation timestamp used.
