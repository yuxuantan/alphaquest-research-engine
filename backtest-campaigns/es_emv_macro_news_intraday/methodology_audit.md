# ES EMV Macro-News Intraday Methodology Audit

## Verdict

FAIL

## What Was Tested

Five predeclared variants tested lagged monthly FRED/Baker-Bloom-Davis EMV macro-news states on ES 1-minute RTH bars. EMV observations were made eligible only after observation month-end plus 21 calendar days. Signals used completed bars and next-bar-open execution.

## Stage Result

- Terminal stage: `limited_core_grid_test`
- Official combinations tested: `135`
- Profitable combinations: `7`
- Benchmark-passing combinations: `1`
- Apex-rule-violating combinations: `0`

## Variant Results

- `high_interest_news_short_1200`: 3/27 profitable, 0 benchmark-pass, top net `547.5`, top PF `1.0764`, top MAR `1.2445`, top trades `63`, top failure `preferred_min_total_trades;max_best_day_concentration`.
- `high_labor_news_short_1330`: 0/27 profitable, 0 benchmark-pass, top net `-4377.5`, top PF `0.7527`, top MAR `-0.7682`, top trades `178`, top failure `min_total_net_profit;max_consecutive_losses`.
- `high_macro_news_rebound_long_1130`: 1/27 profitable, 0 benchmark-pass, top net `5.0`, top PF `1.0003`, top MAR `0.0020`, top trades `164`, top failure `max_best_day_concentration`.
- `high_macro_news_short_1030`: 3/27 profitable, 1 benchmark-pass, top net `1615.0`, top PF `1.1073`, top MAR `1.1003`, top trades `102`, top failure `max_consecutive_losses`.
- `rising_macro_news_short_1000`: 0/27 profitable, 0 benchmark-pass, top net `-3105.0`, top PF `0.8328`, top MAR `-0.4860`, top trades `156`, top failure `min_total_net_profit;max_consecutive_losses`.

## Failure Interpretation

The edge fails closed because the limited-core grid did not show a robust profitable parameter neighborhood. A single benchmark-passing row in one variant is not sufficient when the profitable-combination rate is far below the configured 70% gate.

## Candidate Report

No `candidate_strategy_report.md` was created because no variant passed the first staged gate.
