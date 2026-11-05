# PM1 legacy precompile-count result — 2026-11-05

## Disposition

Run `pm1_legacy_precompile_count_20261105_r1` completed successfully.  The
frozen legacy Page Manager has exactly 62,002 registers after the same
DC analyze/elaborate/link sequence used by the PM1 r2 candidate gate.  The
retained R5 availability proxy count is one.

Terminal evidence is complete:

- `KVZAP_PM1_LEGACY_PRECOMPILE_COUNT_PASS registers=62002`;
- `KVZAP_PM1_LEGACY_PRECOMPILE_COUNT_OUTER_EXIT=0`;
- `KVZAP_PM1_LEGACY_COUNT_P22_OUTER_EXIT=0`;
- no residual PM1 process and no native fatal/error line.

The summary records `precompile_registers=62002` and
`r5_proxy_instances=1`.  Presto compilation, elaboration and link completed;
the probe intentionally performed no compile, characterization, accepted-top
relink, constraint change or mapped-design write.

## Input closure

The remotely recomputed SHA-256 values match the recorded manifest:

- accepted entry-id DDC:
  `29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326`;
- frozen legacy child:
  `f5e3299f9af08b05ac1de3c2a09967303fa2294f4c31dc2b81f7dccb3bde97b4`;
- accepted contextual PM1 child:
  `dfaf40814b0372962b1720c7c9289271d6dc60158fc0d2b09238e3bbe0496671`;
- renamed legacy probe input:
  `894eddf6ff79566821413b91d1a417dcc2cca32234076954b87634ecf5939d05`;
- probe Tcl:
  `ceff91843df00103edbdad8e980a212ac9e49ac6283791dd22468443c3151fbb`;
- target library:
  `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.

The source-state cross-check remains exact: both children have 628,917
declared state objects, 1,678,810 raw declaration bits and 628,917
nonblocking-assignment targets, with zero additions, removals or width
mismatches.

## Diagnosis

The PM1 r2 failure was a mixed-stage acceptance-gate error.  Both the frozen
legacy raw child and PM1 raw child have 62,002 registers at the precompile
layer.  The accepted saved Page Manager has 62,000 sequential cells only
after compile.  The two-cell difference is therefore a stage transformation,
not PM1-added state.

The replacement screen must use separate fail-closed expectations:

- precompile legacy/candidate register count: 62,002;
- accepted and candidate postcompile sequential-cell count: 62,000.

Standalone-child LINT-52 constant-output warnings and the empty proxy-shell
LINT-55 remain visible in `check_design.rpt`; this count-only probe neither
waives them nor claims structural cleanliness.

## Operational note

The PM1 and RD1 panes had been joined into one tmux window.  The PM1 pane
closed after its clean exit, leaving the live RD1 pane under the PM1 window
label.  The remaining pane was verified by PID, TTY and process tree and its
label was restored to `p16-rd1-dc`; neither run was interrupted.

This result authorizes correction of the replacement-screen stage gates.  It
is not mapped-area, timing, PPA, external-service-cost or system-benefit
evidence.
