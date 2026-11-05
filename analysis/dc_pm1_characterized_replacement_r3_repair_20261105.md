# PM1 characterized replacement r3 gate repair — 2026-11-05

## Cause and bounded correction

The completed same-layer legacy probe establishes that both the frozen legacy
raw Page Manager and contextual PM1 raw Page Manager contain exactly 62,002
registers after DC analyze/elaborate/link.  The accepted saved Page Manager
contains 62,000 sequential cells after compile.  PM1 r2 failed because one
constant was incorrectly used for both stages.

The r3 screen now keeps two independent fail-closed expectations:

- candidate precompile registers: 62,002;
- accepted baseline and candidate postcompile registers: 62,000.

The result summary records both expected values as well as all three observed
counts.  The input manifest records the same two-stage contract instead of the
ambiguous single `expected_page_manager_registers` field.

No RTL, candidate hash, port mapping, clock, constraint, proxy treatment,
characterization operation or compile effort changes.  `change_link` remains
without `-force` and without an invented pin map; the accepted top remains
uncompiled by this screen.

## Static validation

Shell syntax, runner `--help`, Tcl structural completeness, exact occurrence
checks for the two stage-specific constants and `git diff --check` pass.  A
remote rerun must use a new result root and must retain unlimited stack.

Any successful r3 result remains a characterized bottom-up diagnostic.  It is
not a complete same-fair-v1 Route-A successor result, PPA, external-service
cost, system acceleration or hardware net-benefit evidence.
