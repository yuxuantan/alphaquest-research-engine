# ES prior-session flip retest orderflow campaign summary

Decision: FAIL

All five original variants failed limited_core_grid_test with 0.0 profitable-combo rate. Each failed variant received exactly one parameter-space/fixed-parameter rescue preserving the prior-session S/R flip retest plus retest-bar orderflow mechanic. All five rescues also failed limited_core_grid_test; no run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best run: `afternoon_large10_aligned_two_sided_flip/rescue1` top net `-38.75`, PF `0.9977064220183486`, trades/year `90.98917839163146`, terminal stage `limited_core_grid_test`.

No candidate strategy report was created.
