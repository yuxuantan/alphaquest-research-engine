# Strategy Modules

This exact variant uses shared repo modules rather than variant-local copied code:

- Entry: `src/propstack/strategy_modules/entry/pdh_pdl_vap_absorption_sweep.py`
- Stop: `sweep_extreme`
- Target: `fixed_r`

The generated feature cache is built by `tools/build_es_pdh_pdl_vap_absorption_sweep_cache.py`.
The cache preserves a 1-minute source timeframe and places 3-minute intrabar release features
on the 3-minute anchor row so the backtest engine can use 3-minute structure with 1-minute
stop/target detail data.
