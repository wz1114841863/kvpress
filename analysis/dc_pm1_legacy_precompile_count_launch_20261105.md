# PM1 legacy precompile-count probe launch — 2026-11-05

## Run identity

- run ID: `pm1_legacy_precompile_count_20261105_r1`;
- tmux: `kvzap-control-refine:p22-pm1-legacy-count`;
- result root:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/pm1_legacy_precompile_count_20261105_r1`;
- log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/pm1_legacy_count_p22_20261105.log`;
- runner-native terminal marker:
  `KVZAP_PM1_LEGACY_PRECOMPILE_COUNT_OUTER_EXIT=<code>`;
- tmux-wrapper terminal marker:
  `KVZAP_PM1_LEGACY_COUNT_P22_OUTER_EXIT=<code>`.

## Frozen inputs and scope

The run uses the accepted entry-id DDC, frozen legacy contextual child and
accepted p19 PM1 child.  Their hashes are fixed by the probe runner.  The
runner/Tcl hashes are respectively:

- `3aa4dde69d3417003e5cb0c0e7a0c72b92df914b0574950a9f2dbb6f2e5cc0a0`;
- `ceff91843df00103edbdad8e980a212ac9e49ac6283791dd22468443c3151fbb`.

The only generated input is a streaming copy of the frozen legacy child with
one module-name substitution.  The source body, ports and state logic are not
changed.  The probe performs analyze/elaborate/link/count only; it cannot
compile, characterize or relink the accepted top.

## Launch closure

Before launch, both scripts matched their local hashes, the result root was
absent, the RD1 DC remained live and about 584 GiB was free.

After launch:

- source-state equivalence and immutable input closure completed;
- `KVZAP_PM1_LEGACY_COUNT_INPUT_PASS` is present;
- `KVZAP_PM1_LEGACY_COUNT_STACK_PASS stack_kb=unlimited` is present;
- the DC process and p22 window are live and the accepted DDC is being read;
- `p16-rd1-dc` remains independent and untouched.

Completion requires native count PASS with exactly 62,002 legacy precompile
registers, one R5 proxy and both outer exits zero.  This is a gate diagnosis,
not an area, timing or mapped-result run.

## Completed result

The probe completed with exactly 62,002 precompile registers, one R5 proxy,
native PASS and both outer exits zero.  All recorded input hashes were
recomputed and match.  The accepted result and mixed-stage diagnosis are in
[`dc_pm1_legacy_precompile_count_result_20261105.md`](dc_pm1_legacy_precompile_count_result_20261105.md).
