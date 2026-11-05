# PM1 saved-DDC short-validation implementation — 2026-11-06

## Purpose

The r3 mapping reports and artifacts are complete, but two stale collection
handles make its terminal log and summary formally unclean.  Repeating the
3.3-hour child compile is not the first response.  This validator reuses the
immutable accepted top DDC and r3 mapped candidate DDC to close the summary,
relink and report evidence without remapping.

## Operations and exclusions

`validate_pm1_saved_ddc_replacement.tcl` performs only:

1. read and link the accepted mapped top;
2. snapshot baseline instance, pin and register counts and native reports;
3. read and link the existing mapped PM1 child;
4. snapshot candidate register, clock and R5-proxy counts and reports;
5. use fail-closed `change_link` without `-force` or a pin map;
6. link and report the relinked top;
7. write an all-scalar, non-empty summary.

It contains no analyze, elaborate, characterize, compile, DDC write or mapped
HDL write operation.  It does not alter RTL, state, ports, clock, constraints,
proxy treatment or the accepted/r3 artifacts.

The runner fixes the accepted DDC, candidate DDC and mapped-HDL hashes, checks
the r3 provenance manifest and fair-v1 target library, and requires unlimited
stack.  Its postcheck rejects any native `Error:`/`Fatal:` line, missing or
empty artifact, blank/unexpected summary value, area mismatch, lint mismatch
or report parse failure.  It writes a structured `evidence.json` containing
area, setup/hold timing and lint counts.

## Static closure

Shell syntax, runner help, Tcl structural completeness, forbidden-operation
absence, exact expected-count coverage and `git diff --check` pass.  The
validator is ready for a new remote result root.  A launch is not a result;
even a pass validates only the existing bottom-up mapped diagnostic, not a
complete same-fair-v1 integrated Route-A successor, PPA or system benefit.
