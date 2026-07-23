# Campaign Test Summary: nq_implied_correlation_orderflow_confirmation

Decision: FAIL

No frozen variant passed the full staged validation flow. Two variants reached walk-forward analysis and failed OOS robustness; the other variants failed limited core or monkey.

## Terminal Stages

- `limited_core_grid_test`: 2
- `limited_monkey_test`: 1
- `walk_forward_analysis`: 2

## Variant Results

- `rising_corr_1330_large20_flow_short`: FAIL at `limited_core_grid_test`; core top net=2032.5; core PF=1.449171270718232; core benchmark pass=15/81.
- `rising_corr_1330_signed_flow_short`: FAIL at `limited_core_grid_test`; core top net=355.0; core PF=1.0756123535676252; core benchmark pass=0/81.
- `shortterm_corr_1200_signed_flow_short`: FAIL at `limited_monkey_test`; core top net=2255.0; core PF=1.2794299876084263; core benchmark pass=42/81; monkey net-beat=0.847375; monkey DD-beat=0.819625.
- `shortterm_corr_1330_large20_flow_short`: FAIL at `walk_forward_analysis`; core top net=4560.0; core PF=1.8283378746594006; core benchmark pass=54/81; monkey net-beat=0.98425; monkey DD-beat=0.98675; WFA profitable-window-rate=0.0; stitched net=-2900.0; stitched PF=0.7678142514011209; stitched maxDD%=0.02207153304081904.
- `shortterm_corr_1330_signed_flow_short`: FAIL at `walk_forward_analysis`; core top net=4975.0; core PF=1.720492396813903; core benchmark pass=48/81; monkey net-beat=0.973375; monkey DD-beat=0.937375; WFA profitable-window-rate=0.6; stitched net=-21280.0; stitched PF=0.8877429905309524; stitched maxDD%=0.24745524745524747.

No `candidate_strategy_report.md` was created.
