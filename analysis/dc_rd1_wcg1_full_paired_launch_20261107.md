# RD1+WCG1 full paired DC — guarded freeze and launch

Authorization: freeze RD1+WCG1, PM1 off, RD2 excluded, then run full paired
DC in independent tmux at original 2 ns. Preserve original-policy and
gated-clock STA/hold supplement results separately. The selected reference
is `dc_feasibility_fair_rd1_shared_20261105_r1`, not RD1+PM1.

Run ID: **`dc_feasibility_fair_rd1_wcg1_20261107_r1`**.
This document initially records preparation; consult the JSON/current
execution snapshot below for actual stage. No area/timing benefit is
inferred from a launch or a complete input freeze.

## Contextual source closure

Inspection found the earlier standalone wrapper has additional ports relative
to the context-pruned RD1 child. It is not directly substituted. The new
`EmitWCG1ContextualChirrtl` exports reference/gated variants under the full
real control-projection parent. Two new constructor arguments forward the
existing default-off WCG1 realization; production defaults stay false and
PM1 is explicitly false. This changes no interface, arbitration or ownership
contract. The accepted wrapper/helper/reader/parameter functional sources
remain pinned; the forwarding/emitter is the bounded integration change.

The freeze gate verifies the RD1 archive and every compiled baseline member,
requires the contextual reference wrapper to equal RD1 after comment/space
normalization that preserves string literals, then checks candidate typed
headers and all non-table state. All 2,304 member/suffix rows/fields and both
64-bit fields must retain 366,336 data bits. Keep 47 other Route-A units and
Full-KV byte-identical. Page Manager must match its old RD1 hash exactly;
PM1 and RD2 are excluded. Only the wrapper is replaced and the exact native
gate inline file is added: the new closure is **49 Route-A units**, not 48.

The helper string must equal accepted WCG1 inline SHA
`aeb38a91977e96c1ea8a7b686d712c39bcd902a4489aedfcb0bb4810b2c1fc28`.
R5/owner/port/state checks, five typed array-proxy checks and fair-v1 static
coverage precede native work. Gate-latch cost is not made zero by the raw
state parser: 4,608 characterized native gates are inventoried and charged
in mapped reports. No parent controller is black-boxed.

The first contextual export attempt exhausted its 3-GiB JVM while emitting
the second full design. sbt nevertheless returned success; the candidate
file was absent. The confirmed-failed chain's downstream reference firtool
was stopped to avoid redundant work, leaving exit 143 and the OOM log intact.
No DC ran in it. Corrected export r2 uses a separate 6-GiB JVM per side,
checks the actual FIR file and output markers, and preserves all old inputs.
It runs in **`kvzap-rd1-wcg1:export-r2`**, source archive SHA
`fcf677b698d582c47080a865d4a75d690188cb0f6f90a8210e8752f2dfe6ddf1`.

## Three native result tiers per complete top

The new native driver loads the exact original feasibility procedures,
retaining their compile, fair constraints and entry_id preservation. Native
gate identity sizing is the only additional precompile protection. Original
Tcl SHA is `9027bfde757823c23485f25931a462854226c3d3ae7f369e7a9704ec532dd282`;
constraint Tcl remains `3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007`.

1. `primary_raw`: original full-paired ideal-clock mapping policy and 2-ns
   numerical constraints; original reports/DDC are retained as well.
2. `propagated_raw`: the same mapped design, with actual clocks propagated
   and the same .05-ns root transition on both complete tops, before hold repair.
3. `propagated_hold_repaired`: identical `set_fix_hold` /
   `compile -only_hold_time` pass on both complete tops, with every cost charged.

Each tier has DDC, mapped HDL/SDC, area hierarchy, QoR, references, precision
setup/hold, constraints, lint/coverage and root-clock reports. Route-A adds
48-bit entry_id closure, table/gate inventory and E-pin setup/hold; propagated
tiers require positive actual native gate-Q capture delay. Timing failures
remain outcomes. Supplemental ratios use their own measured Full-KV area.
Neither supplemental policy is compared directly to historical ideal-clock
RD1 as a pure RTL delta. No exception or relaxed clock is introduced.

A separate full-top analyze/elaborate/link preflight must first close 4,608
native gates, all CP/E/TE/Q pins, the characterized cell and four Route-A
proxies. Clean native/redirected error scans are mandatory before either
formal compile. The native gate uses documented `-all_instances` sizing and
checks its return status. Full-KV's one exact retained VER-41 include message
is preserved; no other native error is whitelisted.

## Execution and acceptance

Scripts are frozen in a new 19-file bundle, SHA
`64bb25f65b38e69042f9e587aa4b6779f0e633d8df6e1c8a3ab7c89cec2d4e3b`.
The guarded pipeline waits for successful contextual export, runs every
source/proxy/profile gate, closes native binding, then runs Full-KV followed
by Route-A. An export or freeze failure stops the chain before synthesis;
there is no fallback, automatic retry or use of the standalone wrapper.
It uses unlimited stack, nice 10, at most two DC cores, one DC process at
a time and at least 32 GiB available before input preparation/native work.
All old runs, scripts and shared workspaces remain untouched.

Planned immutable stem:
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/rd1_wcg1_20261107_r1`.
Result root:
`/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/dc_feasibility_fair_rd1_wcg1_20261107_r1/`.
Total pipeline log:
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd1_wcg1_full_dc_20261107_r1.log`.
Independent tmux window: **`kvzap-rd1-wcg1:paired-dc`**.

Local 36 regressions pass: literal-preserving reference normalization,
original-procedure extraction, retained-error boundary, all three policies,
timing-failure-as-outcome and negative area/clock/data/gate/driver/coverage
cases. Shell syntax, Tcl completeness, CLI help and `git diff --check` pass.
Scala compilation and reference CHIRRTL emission pass remotely; contextual
split/whole-input closure is still pending in the preparation snapshot.

Final acceptance needs input/script/archive/library/proxy rehashes, both
native exits and all tier markers, postcheck, full RUN_PASS and persisted
outer exit 0. Full-KV primary area must reproduce 23,091.432498. Area, timing,
structural cleanliness and tool/input closure are separate verdicts. PPA,
external-service zero cost, speedup and hardware net benefit are not claimed.
