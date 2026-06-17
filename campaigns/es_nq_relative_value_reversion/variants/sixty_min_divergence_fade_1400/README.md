# sixty_min_divergence_fade_1400

This variant tests the ES/NQ relative-value reversion edge at 14:00 ET using completed 60-minute return-spread features. It checks whether later-session ES divergence versus NQ mean-reverts before the 15:55 ET flatten.

Entry uses `es_nq_relative_value_reversion`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.min_spread_bps`; stop and target each have one tunable.
