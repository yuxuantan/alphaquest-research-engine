# ES Session-Extreme Cumulative-Delta Divergence Density Audit - 2026-06-18

Pre-PnL audit only. No profitability, stop, target, or outcome metrics were used to approve these mechanics.

Initial 2.5% max-delta-progress threshold was rejected before PnL because one afternoon-low corner fell below the 50 signals/year density target in the limited-core window. The declared grid now uses `[0.05, 0.1]` for `entry.params.max_delta_progress_ratio`.

Declared grid: `entry.params.min_extreme_break_ticks` in `[1, 2]`, `entry.params.max_delta_progress_ratio` in `[0.05, 0.1]`, stop grid 3 values, target grid 3 values, for 36 total combinations per variant.

The limited-core benchmark window resolves to `2011-02-22` through `2012-09-06`; WFA uses first 90% through `2024-11-22`; full local Sierra RTH cache ends `2026-06-09`.

## `afternoon_high_delta_divergence_short`
| window | min signals/year | median signals/year | max signals/year | sessions |
|---|---:|---:|---:|---:|
| full_available | 77.8 | 87.0 | 93.7 | 3817 |
| shortlist_random_10pct | 63.0 | 79.0 | 92.3 | 374 |
| wfa_first_90pct | 76.1 | 85.9 | 93.2 | 3438 |

## `afternoon_low_delta_divergence_long`
| window | min signals/year | median signals/year | max signals/year | sessions |
|---|---:|---:|---:|---:|
| full_available | 68.0 | 72.6 | 75.4 | 3817 |
| shortlist_random_10pct | 56.5 | 65.3 | 70.8 | 374 |
| wfa_first_90pct | 67.8 | 72.6 | 75.6 | 3438 |

## `midday_two_sided_delta_divergence`
| window | min signals/year | median signals/year | max signals/year | sessions |
|---|---:|---:|---:|---:|
| full_available | 186.6 | 201.2 | 210.7 | 3817 |
| shortlist_random_10pct | 156.0 | 183.9 | 202.8 | 374 |
| wfa_first_90pct | 183.6 | 199.6 | 210.0 | 3438 |

## `morning_high_delta_divergence_short`
| window | min signals/year | median signals/year | max signals/year | sessions |
|---|---:|---:|---:|---:|
| full_available | 134.6 | 147.3 | 155.9 | 3817 |
| shortlist_random_10pct | 113.7 | 137.5 | 154.0 | 374 |
| wfa_first_90pct | 132.3 | 146.2 | 155.5 | 3438 |

## `morning_low_delta_divergence_long`
| window | min signals/year | median signals/year | max signals/year | sessions |
|---|---:|---:|---:|---:|
| full_available | 126.8 | 138.1 | 144.8 | 3817 |
| shortlist_random_10pct | 113.7 | 137.5 | 148.2 | 374 |
| wfa_first_90pct | 125.2 | 137.5 | 144.9 | 3438 |

Decision: approve for staged PnL testing. All declared entry-grid corners for all five variants are at or above roughly 56 signals/year in the actual limited-core window and above 63 signals/year in the WFA/full windows, before stop/target effects.

CSV detail: `research_artifacts/es_session_extreme_delta_divergence_density_audit_20260618.csv`
