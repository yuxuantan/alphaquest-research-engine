# thirty_min_divergence_fade_1000

This variant tests the ES/NQ relative-value reversion edge at 10:00 ET using completed 30-minute return-spread features. It fades ES-specific divergence: long ES after negative ES underperformance versus NQ, or short ES after positive ES outperformance versus NQ.

Entry uses `es_nq_relative_value_reversion`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.min_spread_bps`; stop and target each have one tunable.
