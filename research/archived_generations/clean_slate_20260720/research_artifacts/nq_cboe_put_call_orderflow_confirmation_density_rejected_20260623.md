# NQ CBOE Put/Call Orderflow Confirmation Density Rejection

Date: 2026-06-23

Pre-PnL signal-density screen only. No PnL, stop/target result, WFA, monkey, or trade outcome was inspected.

Mechanic screened: original `nq_cboe_put_call_sentiment_intraday` daily-state variants with completed 30-minute native NQ orderflow alignment at the signal close.

Decision: FAIL. No source variant and flow-mode combination clears the 50 signals/year floor at every entry-parameter corner over 2011-01-03 through 2026-06-12. The highest strict grid-corner density was 29.66 signals/year (`low_equity_pc_long_1000` with large10 flow).

| source_variant | flow_mode | min_signals_per_year | max_signals_per_year |
| --- | --- | ---: | ---: |
| low_equity_pc_long_1000 | large10_imbalance | 29.660372 | 36.784043 |
| low_equity_pc_long_1000 | large20_imbalance | 29.595612 | 36.525000 |
| low_equity_pc_long_1000 | signed_imbalance | 29.530851 | 37.043085 |
| rising_total_pc_short_1200 | signed_imbalance | 27.847074 | 29.789894 |
| falling_total_pc_long_1130 | large10_imbalance | 27.328989 | 32.315559 |
| high_total_vs_equity_pc_short_1330 | signed_imbalance | 26.940426 | 32.315559 |
| high_equity_pc_short_1030 | signed_imbalance | 26.551862 | 30.372739 |
| falling_total_pc_long_1130 | signed_imbalance | 25.839495 | 30.696543 |
| rising_total_pc_short_1200 | large10_imbalance | 25.839495 | 27.328989 |
| falling_total_pc_long_1130 | large20_imbalance | 25.774734 | 30.826064 |
| high_total_vs_equity_pc_short_1330 | large10_imbalance | 25.386170 | 30.567021 |
| rising_total_pc_short_1200 | large20_imbalance | 25.321410 | 26.810904 |
| high_equity_pc_short_1030 | large20_imbalance | 25.127128 | 28.753723 |
| high_equity_pc_short_1030 | large10_imbalance | 24.609043 | 28.624202 |
| high_total_vs_equity_pc_short_1330 | large20_imbalance | 23.054787 | 27.199468 |
| low_equity_pc_long_1000 | signed_and_large20 | 18.068218 | 22.730984 |
| high_equity_pc_short_1030 | signed_and_large20 | 16.513963 | 19.104388 |
| rising_total_pc_short_1200 | signed_and_large20 | 16.319681 | 17.355851 |
| falling_total_pc_long_1130 | signed_and_large20 | 15.024468 | 17.938697 |
| high_total_vs_equity_pc_short_1330 | signed_and_large20 | 14.312101 | 17.226330 |

Detailed CSV: `research_artifacts/nq_cboe_put_call_orderflow_confirmation_density_rejected_20260623.csv`
