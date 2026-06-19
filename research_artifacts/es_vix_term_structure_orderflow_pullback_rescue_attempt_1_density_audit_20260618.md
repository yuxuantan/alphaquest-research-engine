# es_vix_term_structure_orderflow_pullback Rescue 1 Density Audit

Pre-PnL density check for parameter-space-only rescue. No PnL, stops, targets, fills, or future returns were used.

Resolved limited-core subset: `{'start_date': '2011-02-22', 'end_date': '2012-09-06', 'session_labels': ['RTH']}`

                                       variant_id  best_full_signals  best_full_trades_per_year  best_limited_core_signals  best_limited_core_trades_per_year  density_gate_pass
backwardation_surge_signed_vwap_reject_short_1500                975                  63.186435                         92                          59.791815               True
          contango_large10_vwap_reclaim_long_1500               1061                  68.759803                        102                          66.290925               True
   contango_morning_signed_vwap_reclaim_long_1300                926                  60.010912                         82                          53.292705               True
   curve_flattening_signed_vwap_reject_short_1500                927                  60.075719                         80                          51.992883               True
      front_stress_large10_vwap_reject_short_1500               1104                  71.546487                         90                          58.491993               True

Summary CSV: `research_artifacts/es_vix_term_structure_orderflow_pullback_rescue_attempt_1_density_summary_20260618.csv`
