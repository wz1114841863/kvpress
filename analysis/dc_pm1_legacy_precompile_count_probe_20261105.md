# PM1 legacy precompile-count diagnosis — 2026-11-05

## Question

The unlimited-stack PM1 r2 screen elaborated 62,002 precompile registers, but
the gate compared that unmapped count with the accepted mapped Page Manager's
62,000 sequential cells.  Before changing the gate, the frozen legacy raw
child must be counted under the same DC analyze/elaborate/link layer.

## Source-state closure

A streaming comparison of the frozen legacy and accepted PM1 split children
extracts every `reg` declaration and every nonblocking-assignment target.
Both sides have exactly:

- 628,917 declared state objects;
- 1,678,810 declared raw bits before contextual elaboration cleanup;
- 628,917 nonblocking-assignment targets;
- zero added or removed declarations;
- zero width mismatches;
- zero added or removed nonblocking-assignment targets.

The PM1 selector helper itself contains no register or queue.  This proves that
the source change introduces no state, but it does not replace the required DC
precompile count comparison.

## Probe

`run_pm1_legacy_precompile_count_probe.sh` verifies the accepted DDC, frozen
legacy child, accepted PM1 child, fair-v1 profile and target library hashes. It
then creates one streaming copy of the legacy child with only its module name
changed to `route_a_page_manager_legacy_raw_probe`; the source body is otherwise
unchanged and its hash is recorded.

`probe_pm1_legacy_precompile_count.tcl` reads the accepted DDC only to recover
the existing R5 availability proxy reference, then analyzes, elaborates and
links the uniquely named legacy child under unlimited stack.  It records
`all_registers` and proxy counts.  It performs no compile, characterization,
top relink, constraint change or mapped-design write.

Acceptance requires 62,002 legacy precompile registers and exactly one R5
proxy.  A pass would establish that the r2 failure was a mixed-stage gate:
matched raw precompile count 62,002 versus accepted mapped/postcompile count
62,000.

Static checks pass for shell syntax, `--help`, Tcl structural completeness and
`git diff --check`.  Script SHA-256 values are:

- runner:
  `3aa4dde69d3417003e5cb0c0e7a0c72b92df914b0574950a9f2dbb6f2e5cc0a0`;
- Tcl:
  `ceff91843df00103edbdad8e980a212ac9e49ac6283791dd22468443c3151fbb`.

No main replacement gate is changed until this probe completes.
