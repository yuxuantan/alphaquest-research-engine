# Campaign Test Summary: nq_vix_expiration_pressure

Decision: FAIL

Terminal stage: pre_pnl_data_quality_event_density_screen

Rejected before staged NQ PnL: all five VIX settlement-pressure variants had sufficient calendar frequency (185 events, 11.98/year) but at least one configured event signal-time bar was absent from the local NQ RTH cache. Missing dates include 2011-02-16, 2011-03-15, 2011-04-21, 2011-10-18, 2011-10-19, 2014-03-17, and 2020-03-18 depending on signal type. Because this is a sparse event-calendar strategy and one missing date is a 2020 VIX settlement session, staged PnL was not run and the edge is closed as a data-quality failure rather than allowing the engine to silently skip event days.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.
