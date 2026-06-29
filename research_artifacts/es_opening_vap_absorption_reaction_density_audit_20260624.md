# ES opening VAP absorption reaction density audit

Pre-PnL signal-density audit only. No trade outcomes, stops, targets, or PnL were inspected.

- Data: `data/cache/orderflow/es_sierra_footprint_opening_vap_1m_20110103_20260609_rth_ny.parquet`
- Date span: 2011-01-03 09:30:00 to 2026-06-09 15:59:00
- Approx years: 15.43
- Entry grid approved for testing: min_probe_ticks=[0, 1]; min_orderflow_imbalance=[0.0, 0.01, 0.03]
- Fixed footprint threshold audited: min_footprint_imbalance_volume=20
- One signal session counted at most once per variant/grid corner.
- Decision: approve all eight variants for staged testing before PnL because every strict corner exceeds 50 signals/year.

| variant_id | setup_mode | prefix | start_time | end_time | min_signal_sessions | median_signal_sessions | max_signal_sessions | min_signals_per_year | median_signals_per_year | max_signals_per_year | strict_corner_probe_ticks | strict_corner_min_orderflow_imbalance | strict_corner_bar_signals | default_probe_ticks | default_min_orderflow_imbalance | default_bar_signals | default_signal_sessions | default_long_bar_signals | default_short_bar_signals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ovap30_value_trap_1500 | opening30_value_trap_two_sided | opening30_vap | 10:05:00 | 15:00:00 | 1026 | 1223 | 1417 | 66.491572 | 79.258472 | 91.830953 | 1 | 0.03 | 1533 | 1 | 0.01 | 1788 | 1164 | 888 | 900 |
| ovap60_value_trap_1500 | opening60_value_trap_two_sided | opening60_vap | 10:35:00 | 15:00:00 | 936 | 1132 | 1342 | 60.658978 | 73.393475 | 86.970458 | 1 | 0.03 | 1309 | 1 | 0.01 | 1516 | 1056 | 705 | 811 |
| ovap30_poc_reclaim_1500 | opening30_poc_reclaim_two_sided | opening30_vap | 10:05:00 | 15:00:00 | 977 | 1153 | 1332 | 63.316049 | 74.754414 | 86.322392 | 1 | 0.03 | 1572 | 1 | 0.01 | 1812 | 1109 | 886 | 926 |
| ovap60_poc_reclaim_1500 | opening60_poc_reclaim_two_sided | opening60_vap | 10:35:00 | 15:00:00 | 912 | 1067 | 1235 | 59.10362 | 69.148643 | 80.036152 | 1 | 0.03 | 1445 | 1 | 0.01 | 1652 | 1017 | 821 | 831 |
| ovap30_lvn_trap_1500 | opening30_lvn_trap_two_sided | opening30_vap | 10:05:00 | 15:00:00 | 936 | 1140 | 1356 | 60.658978 | 73.911928 | 87.87775 | 1 | 0.03 | 1247 | 1 | 0.01 | 1460 | 1068 | 677 | 783 |
| ovap60_lvn_trap_1500 | opening60_lvn_trap_two_sided | opening60_vap | 10:35:00 | 15:00:00 | 833 | 1014 | 1201 | 53.983898 | 65.746296 | 77.832727 | 1 | 0.03 | 1089 | 1 | 0.01 | 1260 | 936 | 563 | 697 |
| ovap30_value_acceptance_1500 | opening30_value_acceptance_two_sided | opening30_vap | 10:05:00 | 15:00:00 | 3816 | 3816 | 3816 | 247.301987 | 247.301987 | 247.301987 | 0 | 0.0 | 278639 | 1 | 0.01 | 269279 | 3816 | 142250 | 127029 |
| ovap60_value_acceptance_1500 | opening60_value_acceptance_two_sided | opening60_vap | 10:35:00 | 15:00:00 | 3804 | 3806 | 3808 | 246.524308 | 246.653921 | 246.783534 | 1 | 0.0 | 223772 | 1 | 0.01 | 218843 | 3804 | 116549 | 102294 |

Detail CSV: `research_artifacts/es_opening_vap_absorption_reaction_density_audit_20260624.csv`
