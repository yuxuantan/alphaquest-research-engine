# Target Reward:Risk Floor Active Config Audit

Date: 2026-06-20

User correction: TP should only be adjusted when an existing `target_r_multiple`
is below `1.0`; targets already at or above `1.0R` must not be widened. No
strategy test should allow a `target_r_multiple` below `1.0R`.

Actions:

- Floored active source YAML target fields under `campaigns/` only. Historical
  generated `backtest-campaigns/` result artifacts were not rewritten.
- Values below `1.0R` were changed to `1.0R`; values already at or above `1.0R`
  were left unchanged.
- Duplicate target-grid entries created by flooring, such as `[0.5, 0.75, 1.0]`,
  were deduplicated to `[1.0]` rather than expanded with new wider TP values.
- Strengthened `propstack.utils.target_rr` so nested target value mappings are
  checked, not just scalar/list target fields.
- Updated the TP-floor rescue helper date stamp to use the current run date.
- Adjusted preflight discovery so default validation checks active authored
  configs under `campaigns/` and `configs/campaigns/`, including rescue configs.
  Generated `backtest-campaigns/` result snapshots are inspected only when
  `--include-generated-results` is explicitly supplied.

Verification:

- Active source YAML RR audit: `checked_yaml 1725`, `violations 0`.
- Fresh active source YAML RR audit after the preflight-scope change:
  `checked_yaml 1483`, `violations 0`.
- Focused tests: `7 passed`.
- Focused regression tests after the preflight-scope change: `7 passed`.
- Explicit preflight after the preflight-scope change:
  `campaigns/es_prior_value_area_orderflow_rejection/variants/morning_signed_val_rejection_long/config.yaml`
  returned `Preflight PASS`.
- Sample preflight on a previously affected config:
  `campaigns/es_prior_value_area_orderflow_rejection/variants/morning_signed_val_rejection_long/config.yaml`
  returned `Preflight PASS`.
- Follow-up verification after the correction was restated:
  active source YAML audit returned `checked_yaml 1834`, `violations 0`.
- Focused guard tests returned `10 passed`.
- Explicit preflight on a stale generated result snapshot with sub-`1.0R`
  targets failed closed, including strategy, core-grid, and WFA target fields.
- Explicit preflight on an active authored config with valid `1.0R+` targets
  returned `Preflight PASS`.

Scope note:

This was a hygiene correction, not a performance rescue. It does not promote any
strategy and does not reinterpret old backtest results that used sub-1R targets.
Historical result snapshots remain useful as evidence of what was actually
tested before the rule change, but they are not valid source configs for future
runs unless re-authored and preflighted under the `1.0R` floor.
