# RD1+PM1 frozen full paired DC launch

Run ID: `dc_feasibility_fair_rd1_pm1_20261106_r1`.
State: **launched, not accepted; user will notify completion**.
tmux: `kvzap-rd1-pm1:paired-dc` (independent new session).
Preparation commit: `b6aa5ed`.
Preparation: `dc_rd1_pm1_parallel_launch_20261106.md`.
Machine-readable snapshot: `dc_rd1_pm1_full_paired_launch_20261106.json`.

All pre-synthesis gates passed: exact accepted PM1 child/header, 47 unchanged
Route-A units, byte-identical Full-KV/filelists, 48-file source closure,
16 required typed port families, 12 production owners, and per-module state
capacity/object identity. Logical raw state remains 13,144,071 bits. The R5
source checker and all five paired array proxy checks pass; no real parent
controller is black-boxed. Neither WCG1 nor RD2 is in the frozen input.

| Frozen artifact | SHA-256 |
| --- | --- |
| Paired raw HDL archive | `0f21d81dbce8576de64f37a6b6e097a93d089fac51381047a2f9283d8574b6c5` |
| Proxy manifest | `6fa694d1694692c829e438378343e023f850359ad1362501ab7a6254c3fdf8df` |
| Independent proxy check | `6f2b2389bcbcc95d7bf77fb1da9bb0f040a7ca6331f73ea35e44bfa82d951bc2` |
| Composition record | `ee6736a92e1b705ae60ce5e70b74a9e137673bc98e87966988509bffe82bf2da` |
| Fair profile | `7da868376ef05233d567a29d453944306523c543e488a9f77a6f38e04574b9d1` |
| Frozen scripts archive | `ceedaf62e11b28f1bd60596f7d5a21fea080567bb86f5f280a56e72b46ed3a75` |

The profile retains every `dc_feasibility_fair_v1` numerical value, including
2-ns clock. The original constraint Tcl/library and entry_id driver preservation
remain unchanged. This run uses the original full-paired timing/mapping policy;
WCG1 propagated-clock/hold supplements are not introduced into this baseline.

Remote input stem:
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/rd1_pm1_20261106_r1`.
The archive, proxy manifest and proxy directory are its `_paired_input.tar.gz`,
`_dc_array_proxy_manifest.json` and `_dc_array_proxy_r1` siblings.
Frozen scripts are in
`/home/yaz80/wz_project/chisel_projects/kvpress/bundles/rd1_pm1_full_dc_20261106_r1/`.

Total log:
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd1_pm1_full_dc_20261106_r1.log`.
Result root:
`/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/dc_feasibility_fair_rd1_pm1_20261106_r1/`.
Full-KV and Route-A native logs are `full_kv/dc_shell.log` and
`route_a/dc_shell.log`. Initial observation confirms the full freeze/start
marker, static coverage gate and Full-KV mapping. Unlimited stack and nice 10
are active. Before launch the server had 42,106 MiB available and 582 GiB disk.

Required final gates: both native side exits 0, side/native PASS,
`KVZAP_DC_FEASIBILITY_RUN_PASS`, wrapper
`KVZAP_RD1_PM1_FREEZE_DC_OUTER_EXIT=0`, unchanged input/library/proxy hashes,
DDC/mapped HDL/reports, five proxy instances and 48 driven entry_id bits.
Check native area hierarchy and sequential/combinational area, setup/hold,
TNS/path counts, fanout and lint independently. Full-KV must reproduce the
accepted baseline under unchanged constraints. The retained predecessor
Full-KV verification-include diagnostic is not a new waiver for other errors.

Neither the existing RD1 setup failure nor PM1's local hold violation is
considered closed by launch or native exit 0. No mapped improvement, complete
timing/structural closure, PPA, service zero cost, system speedup or hardware
net benefit is claimed. The user has been notified to await this long run;
do not restart it to incorporate WCG1 edits.
