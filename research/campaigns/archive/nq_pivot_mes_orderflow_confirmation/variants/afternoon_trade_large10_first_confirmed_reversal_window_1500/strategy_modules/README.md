# Strategy Modules

- Entry: `nq_pivot_mes_orderflow_confirmation`
- Base entry: `market_structure_filtered_entry` wrapping `mes_participation_crowding`
- Stop loss: `percent_from_entry`
- Take profit: `fixed_r`

The executable entry module lives in `src/alphaquest/strategy_modules/entry/nq_pivot_mes_orderflow_confirmation.py`.
