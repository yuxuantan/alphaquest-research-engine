# ES Treasury Rate Orderflow Confirmation Density Audit - 2026-06-20

Data sources: local Sierra ES RTH aggregate-orderflow cache and existing local Treasury yield feature file. No paid data was downloaded.

Availability rule: each ES session uses the latest Treasury daily observation strictly before the ES session date. ES confirmation uses completed 5-minute RTH bars only, with intended next-bar entry.

Density gate: selected variants must plausibly clear 50 trades/year before any PnL testing. Counts below use fixed pre-test settings: rate rank threshold 0.70, minimum ES move 2 ticks, max one trade per day, and signal decisions at 10:00, 10:30, 11:30, 12:30, 14:30, and 15:30 ET.

| variant | feature spec | min flow imbalance | full signals | full/year | limited-core/year |
|---|---:|---:|---:|---:|---:|
| teny_1d_signed_rate_confirmation_1530 | teny_1d_two_sided | 0.02 | 834 | 54.05 | 70.19 |
| twoy_1d_signed_rate_confirmation_1530 | twoy_1d_two_sided | 0.02 | 864 | 55.99 | 61.09 |
| teny_5d_signed_rate_confirmation_1530 | teny_5d_two_sided | 0.02 | 851 | 55.15 | 72.79 |
| curve_1d_signed_rate_confirmation_1530 | curve_1d_two_sided | 0.02 | 800 | 51.85 | 70.84 |
| teny_1d_large10_rate_confirmation_1530 | teny_1d_large10 | 0.04 | 897 | 58.13 | 52.64 |

Rejected drafts: morning-only versions and stricter flow/threshold combinations that fell below 50 signals/year, plus overly loose 0.55-0.65 rank-threshold drafts that weakened the rate-shock expression before PnL inspection.

Decision: PASS pre-PnL density gate for the five selected full-day variants.
