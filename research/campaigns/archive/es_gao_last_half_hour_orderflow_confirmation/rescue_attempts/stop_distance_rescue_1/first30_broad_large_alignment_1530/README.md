# first30_broad_large_alignment_1530 rescue2

User-authorized second rescue for `es_gao_last_half_hour_orderflow_confirmation / first30_broad_large_alignment_1530`.

Normal methodology allows one rescue per failed variant; this is logged as a one-off explicit override.

Only stop-loss distance and take-profit R-multiple were changed from rescue1. Entry module, entry thresholds, signal time, first-window length, flow mode, data, costs, sessions, and validation gates are unchanged.

- `sl.params.stop_pct`: `[0.0025, 0.003, 0.0035]`
- `tp.params.target_r_multiple`: `[1.25, 1.5, 2.0]`
- fixed config defaults: `stop_pct=0.003`, `target_r_multiple=1.5`


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_gao_last_half_hour_orderflow_confirmation/first30_broad_large_alignment_1530/rescue2`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
