# RD2 isolated read-network synthesis launch — 2026-11-06

## Run identity

- Run ID: `rd2_read_network_screen_20261106_r1`;
- tmux: `kvzap-control-refine:p27-rd2-read-dc`;
- root:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/rd2_read_network_screen_20261106_r1`;
- total log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd2_read_screen_p27_dc_20261106.log`;
- wrapper terminal marker: `KVZAP_RD2_P27_READ_SCREEN_EXIT=<code>`.

Input identities and scope are frozen in
`dc_rd2_read_screen_input_freeze_20261106.md`.  Run sides are `rd1` and
`decoded`, with separate native DC processes run sequentially.  The existing
RD1 M/S/O shared reader remains present on both sides.

## Launch closure

Before launch, output-side directories, run manifest, total log and p27 window
were absent.  Nine pinned input/script/manifest hashes, five source snapshots,
two-case test XML and paired-port identity were rechecked.  Fair-v1 numerical
constraints and the copied constraint Tcl remain unchanged.

At launch:

- `KVZAP_RD2_SCREEN_INPUT_PASS` is present;
- `KVZAP_RD2_SCREEN_STACK_PASS` is present after establishing unlimited stack;
- the runner and one native DC process are live;
- the RD1-enabled baseline source has completed Presto analyze;
- native elaboration has begun with the expected LVT feasibility library;
- no native Error/Fatal or completion marker is present at this snapshot.

This is an isolated combinational read-network experiment.  It performs no
full Route-A/Full-KV compile and includes no storage cost.  RD1+PM1 complete
paired DC is not started by this launch.

## Completion acceptance

After user-reported completion, inspect without restarting:

1. `KVZAP_RD2_SCREEN_SIDE_EXIT side=rd1 code=0` and corresponding `decoded`
   exit-zero marker;
2. native `KVZAP_RD2_SCREEN_SIDE_PASS` for both sides;
3. `KVZAP_RD2_SCREEN_POSTCHECK_PASS` and
   `KVZAP_RD2_READ_NETWORK_SCREEN_PASS`;
4. `KVZAP_RD2_P27_READ_SCREEN_EXIT=0`;
5. all recorded source/script/input/library/constraint hashes and both exact
   zero-register summaries;
6. non-empty mapped DDC/HDL, area, QoR, precision setup/hold timing, clocks,
   constraints and design checks.

Report incremental area, path-delay/slack tradeoffs, fanout and lint
separately.  Keep negative outcomes.  A favorable screen still requires
out-of-range/ready equivalence and functional/generated closure before
production integration.  No PPA, system acceleration or hardware net benefit
follows from this run.
