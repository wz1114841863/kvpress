# PM1 characterized replacement launch — 2026-11-05

## Run identity

- run ID: `pm1_characterized_replacement_20261105_r1`;
- tmux: `kvzap-control-refine:p20-pm1-characterized-dc`;
- result root:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/pm1_characterized_replacement_20261105_r1`;
- outer log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/pm1_characterized_p20_dc_20261105.log`;
- runner-native terminal marker:
  `KVZAP_PM1_CHARACTERIZED_REPLACEMENT_OUTER_EXIT=<code>`;
- tmux-wrapper terminal marker:
  `KVZAP_PM1_CHARACTERIZED_P20_OUTER_EXIT=<code>`.

## Frozen inputs

The launch uses:

- accepted entry-id-repair DDC SHA-256
  `29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326`;
- accepted p19 contextual child SHA-256
  `dfaf40814b0372962b1720c7c9289271d6dc60158fc0d2b09238e3bbe0496671`;
- p19 hash manifest with all four entries independently rechecked;
- `dc_feasibility_fair_v1` target library and stored library integrity gate;
- runner SHA-256
  `e03e2a8a5964c9afa7858f067a0c6945aee6a3edb3f09a4334fb8923487e16fe`;
- Tcl SHA-256
  `9d210958e95d618c8cfe8c232e90204615b54167c43c7b39d19d5cebc18f35a3`.

The result root was absent before launch and the remote filesystem had about
585 GiB free.

## Launch state

`KVZAP_PM1_CHARACTERIZED_INPUT_PASS` is present.  The runner, DC process and
p20 tmux window are live, and DC is reading the accepted baseline DDC.  The
separate RD1 paired DC remains live in `kvzap-control-refine:p16-rd1-dc` and
was not modified.

Completion requires both outer exits zero, the native
`KVZAP_PM1_CHARACTERIZED_REPLACEMENT_PASS` marker, 62,000 baseline/candidate
precompile/candidate postcompile registers, one characterized clock, one
retained R5 availability proxy, candidate DDC/mapped HDL and non-empty baseline,
candidate and relinked-top native reports.

This launch is not a result.  Even a passing screen is a bottom-up diagnostic
comparison and remains provisional until a complete same-fair-v1 integrated
Route-A successor run.
