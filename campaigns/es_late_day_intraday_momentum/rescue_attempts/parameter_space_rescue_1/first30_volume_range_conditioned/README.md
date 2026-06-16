# first30_volume_range_conditioned

This variant keeps the first-30-minute-to-last-30-minute momentum mechanic and adds a predeclared volume/range condition motivated by the source paper's stronger high-volume and high-volatility effect. The signal still uses only completed opening-window data before 15:30 ET.

Tunable parameters are fixed before testing: two entry thresholds, one percent stop, and one fixed-R target.
