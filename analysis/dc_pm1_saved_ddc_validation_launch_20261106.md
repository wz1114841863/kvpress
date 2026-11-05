# PM1 saved-DDC short-validation launch — 2026-11-06

## Run identity

- run ID: `pm1_saved_ddc_validation_20261106_r1`;
- tmux: `kvzap-control-refine:p24-pm1-saved-ddc`;
- result root:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/pm1_saved_ddc_validation_20261106_r1`;
- outer log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/pm1_saved_ddc_p24_20261106.log`;
- runner marker: `KVZAP_PM1_SAVED_DDC_OUTER_EXIT=<code>`;
- tmux-wrapper marker: `KVZAP_PM1_SAVED_DDC_P24_OUTER_EXIT=<code>`.

The window is independent from the active RD1 pane and retains its shell after
completion.

## Frozen inputs and method

The validator fixes:

- accepted top DDC SHA-256
  `29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326`;
- r3 candidate DDC SHA-256
  `38038fb2c9edc434d6bc3059e9166c57c63cfed78269e2765a2f758e21fddb0e`;
- r3 mapped Verilog SHA-256
  `e98ef9cac40e87d40f5ed8426bc0f2dd09ac8b5eb2e51d508a31fe3179eb9aa2`;
- validation Tcl SHA-256
  `22f5fa1e84a823cb967fe44d7bed1e8b2663acb2ca415843246b88d629695144`;
- runner SHA-256
  `259cfc42e82cb03f7aa82a3debe24b2932053b91e8bec355dc848122d3f1bacd`.

The repaired full-screen Tcl/runner were also synchronized at hashes
`772f5cb955e8c756aa9bf4235e98681a6d680b3b9a60402f9337c224e7d43fe1`
and
`1d8aede84a733a8b7df58851d92a0106998b046d40984c484902932b7545471d`.
Their repaired postcheck directly rejects the old r3 root because both
`SEL-001` lines are present.

This short run contains no analyze, elaborate, characterize, compile or mapped
artifact write.  It reads the two saved DDCs, performs a no-`-force`, no-pin-map
relink, regenerates reports and applies the exact scalar/error/artifact/metric
postcheck.

## Launch closure

Before launch the result root, outer log and p24 window were absent; all inputs
were present and non-empty.  After launch:

- `KVZAP_PM1_SAVED_DDC_INPUT_PASS` is present;
- `KVZAP_PM1_SAVED_DDC_STACK_PASS stack_kb=unlimited` is present;
- the runner and native DC process are live and reading the accepted DDC;
- RD1 remains live with the same PID/process tree in `p16-rd1-dc`;
- approximately 42 GiB memory and 584 GiB filesystem capacity remain
  available.

This is launch evidence only.  Completion requires native PASS, postcheck PASS,
both outer exits zero, no native Error/Fatal line, exact non-empty summary,
complete reports and a matching `evidence.json`.  It remains bottom-up
logic-synthesis evidence, not integrated successor DC, PPA or system benefit.
