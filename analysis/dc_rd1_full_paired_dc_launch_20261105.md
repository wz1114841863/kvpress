# RD1 complete paired-DC launch — 2026-11-05

## Authorized comparison

This run measures the frozen RD1 bank-local M/S/O member-record read-sharing
successor against the byte-identical Full-KV control projection under the
unchanged `dc_feasibility_fair_v1` contract.  It retains the accepted
`r3_entry_id_driver_v1` synthesis policy and the same five typed array proxies.

It does not include PM1 or any other Page Manager change.  It does not relax
the Route-A clock, enlarge Full-KV, black-box parent control, delete state or
change pruning, admission, publication, authority or arbitration semantics.

## Remote run

```text
run ID: dc_feasibility_fair_rd1_shared_20261105_r1
tmux:   kvzap-control-refine:p16-rd1-dc
log:    /home/yaz80/wz_project/chisel_projects/kvpress/logs/
          rd1_shared_p16_dc_20261105.log
root:   /home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/
          dc_feasibility_fair_rd1_shared_20261105_r1/
```

The predecessor `p15-rd1-freeze` dead window was removed only after its log,
reports and immutable artifacts were accepted.  No prior result directory was
deleted.

## Launch evidence

At the launch snapshot:

- the tmux pane is live;
- exactly one native DC process is active for the paired runner;
- `KVZAP_DC_PROXY_EVIDENCE_PASS boundaries=5` is present;
- the unchanged fair-v1 static coverage gate passes;
- Full-KV analyzed, linked and applied the 2.0-ns constraint contract;
- the new run root contains the frozen manifest, input hashes, constraint Tcl,
  entry_id preservation Tcl and `synthesis_interface_policy.txt`;
- Full-KV native `dc_shell.log`, precompile design/timing/constraint reports,
  command log and SVF have begun to populate.

This is launch/liveness evidence only.  It is not a synthesis result.

## Completion gate

After the user reports completion, inspect without restarting or duplicating
the run.  Acceptance requires:

1. Full-KV and Route-A native exits zero;
2. `KVZAP_DC_FEASIBILITY_RUN_PASS` and outer
   `KVZAP_RD1_P16_DC_EXIT=0`;
3. archive, library, constraint, proxy, manifest and policy identities;
4. DDC, mapped HDL, QoR, hierarchy area, timing, constraints and design checks
   for both sides;
5. all 48 reconstructed entry_id output bits have real drivers, with zero
   LINT-3/LINT-5 regression;
6. matched comparison against accepted compact/entry_id result
   `dc_feasibility_fair_m2p3_entryid_repair_20261104_r1` and immutable baseline
   `dc_feasibility_fair_r5desc_20261029_r1`;
7. wrapper/read-network area, sequential/combinational area, WNS/TNS/path
   count, fanout and lint causes reported separately.

No PPA, external-service-zero-cost, system acceleration or hardware net
benefit conclusion follows from this launch or later logic-only DC result.

## Completed result

Both exits, RUN_PASS and the outer exit close.  RD1 reduces full Route-A area
6.454% and wrapper area 9.502% versus accepted compact/entry-id, but setup WNS
worsens to -0.36 ns, TNS to -9,774.02 ns, and warning lines increase three.
Sequential cells and clock-alias load are unchanged; all 48 entry-id bits
retain real drivers.  Complete evidence is in
[`dc_rd1_full_paired_dc_result_20261106.md`](dc_rd1_full_paired_dc_result_20261106.md).
