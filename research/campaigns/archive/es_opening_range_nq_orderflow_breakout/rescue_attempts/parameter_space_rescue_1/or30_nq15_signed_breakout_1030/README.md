# or30_nq15_signed_breakout_1030 rescue1

Single allowed parameter-space/fixed-parameter rescue for `es_opening_range_nq_orderflow_breakout`.

This rescue preserves the entry module `opening_range_nq_orderflow_breakout`, stop module `opening_range_edge`, target module `fixed_r`, local ES/NQ completed-bar cache, costs, fills, sessions, and staged benchmarks.

The only fixed-parameter narrowing is long-only ES opening-range breakout continuation with NQ leadership and ES aggregate signed-flow confirmation. This remains the same continuation edge, but rejects short breakout continuation after the original run showed that short breakouts were consistently the weaker side.
