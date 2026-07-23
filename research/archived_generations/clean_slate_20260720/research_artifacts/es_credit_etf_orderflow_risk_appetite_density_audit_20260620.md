# ES Credit ETF Orderflow Risk-Appetite Density Audit - 2026-06-20

Data sources: local Sierra ES RTH aggregate-orderflow cache, free Yahoo chart CSVs for HYG/LQD, and existing local SPY daily CSV.
Feature timing: each ES session uses the latest ETF daily close strictly before the ES session date.
Signal timing: completed 5-minute ES bars only; signal timestamp equals bar timestamp plus five minutes; one signal capped per session.
Density rule: retain only variants with at least 50 signals/year on both full configured data and the seeded limited-core reference window.

| variant | full signals/year | limited signals/year | pass |
|---|---:|---:|---|
| `hyg_1d_strength_signed_long_1230` | 52.36 | 52.64 | True |
| `hyg_1d_weakness_signed_short_1230` | 50.94 | 57.84 | True |
| `hyg_1d_two_sided_signed_1230` | 103.30 | 110.48 | True |
| `hyg_3d_two_sided_signed_1230` | 98.44 | 96.84 | True |
| `hyg_5d_two_sided_signed_1230` | 99.28 | 103.99 | True |

Decision: PASS for campaign authoring. All five proposed variants clear the 50/year density screen before PnL testing.
