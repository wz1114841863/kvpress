# WCG1 real-wrapper export/binding/mapping/STA launch

Run ID: `wcg1_wrapper_mapping_sta_d860732_20261106_r1`.
Status: **launched; isolated Scala compile, paired RTL export and static input
closure pass. Native-binding preflight is active; mapping/STA are not accepted**.
Preparation commit: `d8607322807cf1bec005cfd06a6d633d368222d2`.
Plan: [`dc_wcg1_wrapper_mapping_plan_20261106.md`](dc_wcg1_wrapper_mapping_plan_20261106.md).
Machine-readable freeze: `dc_wcg1_wrapper_mapping_launch_20261106.json`.

Independent tmux: **`kvzap-wcg1-wrapper-map:paired-sta`**.
Total log:
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/wcg1_wrapper_mapping_sta_20261106_r1.log`.
New workspace/result root:
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/wcg1_wrapper_mapping_sta_d860732_20261106_r1/`.

| Frozen item | SHA-256 |
|---|---|
| Source/script archive | `5531bc6a8368f39c301f248f03f042f158483feccfbc080e95c8dea112abcc2e` |
| Versioned runner | `430a928183415656cf81d51bb27da557c61cf28d60c71681657720229ee23022` |
| Internal freeze manifest | `d1d84181c8d3a0ca967ca52685ffe46071b933ddfe4a29ba6b2684f7b42eadd5` |
| Source/script SHA256SUMS | `f223c55651829464289f95ba78726cd758a5c14b1051c052f7d0e06b7d906d76` |

The archive/runner are versioned files under the remote `kvpress/bundles/`
directory. All 122 accepted r2 project files retain their hashes; the new
emitter makes 123 project files, with seven copied tool/script dependencies.
The internal manifest pins all 130 files. RD2 files and generated/test outputs
are absent from the archive. Existing production RTL/defaults are unchanged.

## Guarded execution chain

1. Rehash archive/source/scripts and DB, verify all original fair-v1 numerical
   constraints and at least 16 GiB free memory; emit a fresh full-profile
   reference and candidate CHIRRTL, then split RTL with firtool 1.158.0.
2. Validate identical top interfaces, all 36×64×(79+80) data fields and every
   non-table register; explicitly close the frozen inline resource and proxy
   only the exact P3 byte-array child. Save `inputs/manifest.json` and hashes.
3. Run DC gated-side analyze/elaborate/link preflight in `native_binding/`.
   Require the native 4,608-gate/E-pin/characterization and one-P3-proxy marker
   with no native errors **before either formal mapping starts**.
4. Map reference then gated, one DC process at a time. Save `raw/` and equally
   hold-repaired snapshots for both, including actual gating setup/hold,
   propagated capture paths, native area hierarchy and 48-bit driver checks.
5. Independently postcheck native artifacts and precision timing, then rehash
   the entire source/script/input package and DB. Timing violations remain
   results; final RUN_PASS establishes tool/input/artifact closure only.

This chain uses the unmodified 2-ns fair profile plus the same propagated-
clock supplement on both sides. The root transition is .05 ns, reset is timed,
and no false/multicycle path, new clock or production pipeline is introduced.
It is not a full Full-KV/Route-A paired run. P3 storage remains separately
nonzero/unestimated, not a new free-array or net-benefit claim.

Local preparation passes 34 focused regressions, shell syntax, Tcl completeness,
CLI checks and `git diff --check`. Remote snapshots show all archived checksums
passing, successful compilation of 22 Scala main sources and both
`WCG1_WRAPPER_CHIRRTL_PASS` markers, followed by
`WCG1_WRAPPER_STATIC_INPUT_PASS bits=366336 gates=4608` and
`KVZAP_WCG1_WRAPPER_NATIVE_BINDING_START`. There is no outer exit marker or
`exit_status` yet. Native-link completion is not inferred from startup.
The prepared closure has two reference units and three candidate units,
including the explicit inline file. Top-header SHA is identical; every member/
suffix field and all other register declarations match. The declared-register
parser counts 400,499 parent bits on each side; this is declaration accounting,
not a newly mapped flop count or a replacement for prior NBA-state accounting.
Prepared manifest SHA is
`2e5101daa20fed6a1b134e5ed7a29a013a0f07778eea37484cbb64cef560e2e1`.
Prelaunch available memory was 86,174 MiB. The run uses nice 10,
unlimited stack, a three-GiB/two-processor JVM, single-threaded firtool and
at most two DC cores.

The user is notified to wait and report completion. Required final markers
are both `KVZAP_WCG1_WRAPPER_SIDE_RUN_PASS`, both native exits 0,
`KVZAP_WCG1_WRAPPER_POSTCHECK_PASS_TOOL_INPUT_ARTIFACT_ONLY`,
`KVZAP_WCG1_WRAPPER_MAPPING_RUN_PASS_TOOL_INPUT_ARTIFACT_ONLY`, outer
`KVZAP_WCG1_WRAPPER_MAPPING_OUTER_EXIT=0` and persisted `exit_status=0`.
DDC, mapped HDL/SDC, raw/repaired area/QoR/setup/hold/gating and structural
reports must pass independent inspection before any result is accepted.

No RD1+PM1 window, process, log, input, workspace or script is queried or
modified; no old window is cleared. WCG1's old r1/r2 functional artifacts
are unchanged. The preparation creates no full-wrapper area/timing conclusion,
PPA, final Route-A ratio, system speedup or net hardware-benefit result.
