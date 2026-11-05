# PM1 Page Manager successor generation launch — 2026-11-05

## Scope

This batch launches only the immutable candidate-child RTL generation required
by the characterized saved-DDC replacement screen.  It does not invoke DC and
does not modify or relaunch the active RD1 paired full-top run.

The candidate is the full-profile `route_a_page_manager_pm1` with external
descriptor backing retained and the exact banked lowest-index selector enabled.
The generation script requires the candidate and frozen predecessor Page
Manager port headers to be identical after changing only the module name.

## Frozen inputs

- source revision: `7b34b38`
- baseline successor root:
  `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/rd1_shared_e5d3107_p15`
- output root:
  `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/pm1_page_manager_7b34b38_p18`
- tmux window: `kvzap-control-refine:p18-pm1-child-freeze`
- log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/pm1_page_manager_p18_generation_20261105.log`
- terminal outer marker:
  `KVZAP_PM1_PAGE_MANAGER_P18_GENERATION_EXIT=<code>`

Before launch, the three candidate Scala inputs and the generation script were
verified byte-for-byte between the local checkout and remote workspace.  Their
SHA-256 values are respectively:

- `41f4e19d6d9ebe064d50b8056ac3c50ace9ebddfd0625595b6834365b572a0b2`
- `e996a010466b98d2e2eb70e721da9cb258a8f6a56529c3fd1b34c9dc71f96a0a`
- `a0d4886784de6230b8d806ba079a273827fa0ed7552fc53db9bd5bff39b9c977`
- `a327a556b0a0f82a4bfd2f7fce3d7915a03cf89fd71fba132c0a00d98aa6c3e0`

The output root was absent before launch and the remote filesystem had about
587 GiB free.

## Launch state

The window entered `runMain kvpress.routea.top.EmitPM1PageManagerChirrtl` and
the corresponding shell, Java/sbt process and log were all live.  The existing
`kvzap-control-refine:p16-rd1-dc` window remained live and untouched.

This is a launch/liveness record only.  Completion requires exit zero, the
outer exit marker, the exact port-identity pass marker, the successor pass
marker, non-empty CHIRRTL and split SystemVerilog, and recorded hashes.  No
mapped-area or timing conclusion follows from this launch.

## Completion update

The run later ended with outer exit 1 at the exact port-identity gate.  The
standalone emitter retained 74 ports that were contextually removed when the
frozen child was lowered below its real parent.  See
[`dc_pm1_page_manager_successor_generation_result_20261105.md`](dc_pm1_page_manager_successor_generation_result_20261105.md)
for the completed disposition and required contextual successor.  This input
is rejected and no saved-DDC replacement DC is authorized from it.
