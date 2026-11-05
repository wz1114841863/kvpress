# PM1 stale-collection and postcheck repair — 2026-11-06

## Cause closed in source

The r3 mapped artifacts completed, but the final top relink invalidated the
saved `baseline_registers` and `proxy_cells` DC collection handles.  Reusing
those handles while writing `summary.tsv` caused two `SEL-001` errors and two
blank values.  DC did not propagate those command errors through the outer Tcl
`catch`, so the old runner still emitted PASS and exit zero.

The replacement screen now snapshots plain integer values while each
collection is valid:

- baseline mapped Page Manager registers;
- candidate precompile proxy instances;
- candidate postcompile proxy instances.

Only the integer snapshots are used after relink.  No RTL, candidate input,
port mapping, characterization, compile effort, constraint, clock or proxy
treatment changes.

## Fail-closed postcheck

The runner now accepts native exit zero only after a separate postcheck:

1. every required baseline/candidate/relinked-top report, DDC, mapped HDL and
   summary file is non-empty;
2. the native log contains no line beginning with `Error:` or `Fatal:`;
3. every summary row has a non-empty value;
4. the exact design identities, 4,289 boundary pins, 62,002/62,000 stage
   counts, one clock and both one-proxy observations match.

A postcheck failure converts the outer exit to 8.  Success adds
`KVZAP_PM1_CHARACTERIZED_POSTCHECK_PASS` before the final exit-zero marker.

Shell syntax, runner help, Tcl structural completeness, exact static value
checks and `git diff --check` pass.  This repair is not itself a synthesis
result.  The next bounded action is a saved-DDC-only validation of the existing
r3 mapped child, without analyze, characterize or compile.
