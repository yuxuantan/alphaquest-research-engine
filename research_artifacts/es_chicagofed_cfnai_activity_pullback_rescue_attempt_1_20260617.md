# ES Chicago Fed CFNAI activity pullback rescue attempt 1 - 2026-06-17

Campaign: `es_chicagofed_cfnai_activity_pullback`

Trigger: all five original variants failed `limited_core_grid_test`.

Original limited-core results:

| variant | combos | profitable combo rate | benchmark-passing combos | apex violations |
|---|---:|---:|---:|---:|
| `diffusion_weak_pullback_long_1200` | 81 | 0.0000 | 0 | 0 |
| `employment_hours_weak_pullback_long_1330` | 81 | 0.0000 | 0 | 0 |
| `headline_activity_weak_pullback_long_1100` | 81 | 0.4444 | 8 | 0 |
| `ma3_activity_weak_pullback_long_1130` | 81 | 0.0000 | 0 | 0 |
| `production_income_weak_pullback_long_1100` | 81 | 0.2840 | 12 | 0 |

Allowed rescue scope:

- fixed/default parameters inside the existing strategy modules;
- predeclared parameter-space ranges only.

Forbidden rescue changes:

- CFNAI availability rule;
- CFNAI driver column for each variant;
- direction;
- entry time;
- entry module;
- stop module;
- target module;
- data window;
- timeframe;
- costs;
- fill assumptions;
- staged validation criteria.

Rescue density audit:

| variant | rescue driver grid | rescue pullback grid bps | lowest rescue grid-corner frequency |
|---|---:|---:|---:|
| `diffusion_weak_pullback_long_1200` | 0.15, 0.25, 0.35 | -5, -10, -15 | 57.5/year |
| `employment_hours_weak_pullback_long_1330` | 0.1, 0.2, 0.3 | -5, -10, -15 | 61.4/year |
| `headline_activity_weak_pullback_long_1100` | 0.15, 0.25, 0.35 | 0, -5, -10 | 64.4/year |
| `ma3_activity_weak_pullback_long_1130` | 0.0, 0.1, 0.2 | 0, -5, -10 | 58.6/year |
| `production_income_weak_pullback_long_1100` | 0.1, 0.2, 0.3 | -5, -10, -15 | 56.4/year |

Decision: run one `rescue1` per failed variant. If a rescue fails, that
variant is rejected for this campaign; no additional rescue is allowed.
