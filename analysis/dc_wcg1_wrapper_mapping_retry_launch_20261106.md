# WCG1 real-wrapper mapping/STA — immutable r2 retry

Run ID: `wcg1_wrapper_mapping_sta_211f1e2_20261106_r2`.
Status: **paired export/static closure pass; native-binding preflight active,
with no native error observed in the latest snapshot; mapping/STA pending**.
Repair commit: `211f1e2d8212c5583a465e074d09c696dd0e16cd`.
Preparation: `dc_wcg1_wrapper_mapping_plan_20261106.md`.
Failure/repair authority:
[`dc_wcg1_wrapper_mapping_preflight_repair_20261106.md`](dc_wcg1_wrapper_mapping_preflight_repair_20261106.md).
The r1 archive, exit 7, logs and workspace are preserved. No formal mapping
ran in r1. Never reuse its startup/binding marker as successful preflight.

Independent tmux: **`kvzap-wcg1-wrapper-map-r2:paired-sta`**.
Total log:
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/wcg1_wrapper_mapping_sta_20261106_r2.log`.
Private workspace/result root:
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/wcg1_wrapper_mapping_sta_211f1e2_20261106_r2/`.

| Frozen item | SHA-256 |
|---|---|
| Source/script archive | `aebd5a0716e1899fef5ec56ad82cacd92367b4704d4cb4b63e799babe9cdfdd4` |
| Runner | `430a928183415656cf81d51bb27da557c61cf28d60c71681657720229ee23022` |
| Internal freeze manifest | `d3091216c9a783187eb6835a0bce555c66d6986424b5d053362edb66dc9794e1` |
| Internal SHA256SUMS | `f86e6492b6dfe9792b7acb1a3872454e39d756d06577fc7f4c88b578bfa6f011` |

The 130-file source/script package differs from r1 in **one file only**:
`screen_wcg1_wrapper_sta.tcl` applies size-only with documented
`-all_instances` and rejects a false command status. All 123 Chisel project
sources, parent controls, helper, table bits, IO, profile, runner and postcheck
are identical to r1. Existing tests are unchanged; two added local regression
cases are tool-preparation evidence, not remote functional cases.

All 36 local checks pass. The retry archive and versioned runner are rehashed
after transfer; destinations/session were checked new. Its guarded chain
regenerates paired real-wrapper RTL, verifies inline/field/header/state/P3
closure, then requires an error-free native preflight before reference and
gated mapping. A native binding marker without a clean log does not pass.

The latest startup snapshot contains both CHIRRTL PASS markers, successful
Scala compilation and `WCG1_WRAPPER_STATIC_INPUT_PASS bits=366336 gates=4608`,
followed by native-binding start. There is no outer exit/status file, no
native error observed and neither formal side has started at that snapshot.
Native-binding success is not inferred from the static gate count.

The original 2-ns numerical profile, root transition, propagated-clock policy,
48-bit driver retention and equal raw/hold-repair policy are unchanged.
Both side snapshots require complete native area/combinational/sequential,
setup/hold/gating, QoR WNS/TNS/path counts and structural reports. Final run
PASS certifies input/tool/artifact closure only; timing violations remain
measured outcomes. No reported area improvement is inferred from this retry.

Execution keeps the private 3-GiB/two-processor JVM, unlimited stack, nice 10,
single-threaded firtool, at most two DC cores and one DC process at a time.
The user is notified to wait and report completion. The runner requires
both native exits, both side PASS markers, postcheck, outer exit 0 and the
persisted zero status, with all source/input/DB hashes retained.

RD1+PM1 windows, inputs, logs, processes and scripts are not inspected or
modified. Production defaults stay unchanged, RD2 is excluded, and no full
paired WCG1+RD1+PM1 run is launched. No PPA, system acceleration or net
hardware-benefit conclusion is made.
