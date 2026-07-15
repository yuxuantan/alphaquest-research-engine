# sixty_min_divergence_fade_1030

This variant tests the ES/NQ relative-value reversion edge at 10:30 ET using completed 60-minute return-spread features. It is a slower-window expression of the same ES-specific divergence fade.

Entry uses `es_nq_relative_value_reversion`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.min_spread_bps`; stop and target each have one tunable.
