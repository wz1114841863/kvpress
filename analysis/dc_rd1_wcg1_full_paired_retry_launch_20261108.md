# RD1+WCG1 full paired DC r2 — repaired freeze and reused export

Run ID: **`dc_feasibility_fair_rd1_wcg1_20261108_r2`**.
Authorization: repair the hash gate, add regression coverage, reuse the completed
RTL export, then start a new independent-tmux full pair at the original 2 ns,
PM1 disabled and RD2 excluded. Repair commit: `d680550`.

## Actual execution

The corrected real input composition and all pre-native source/proxy/profile
checks pass. Native binding is admitted and active in the startup snapshot;
the same guarded pipeline automatically runs Full-KV followed by Route-A
after error-free binding. Exact current markers and process state are saved
in the [launch JSON](dc_rd1_wcg1_full_paired_retry_launch_20261108.json), not
inferred from tmux existence. No completed mapped result is claimed here.

Current independent tmux: **`kvzap-rd1-wcg1-r2q1:paired-dc`**.

```bash
tmux attach -t kvzap-rd1-wcg1-r2q1
```

Full pipeline log:
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd1_wcg1_full_dc_20261108_r2q1.log`.
Result root:
`/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/dc_feasibility_fair_rd1_wcg1_20261108_r2/`.
The current native log is under `native_binding/`, then `full_kv/` and
`route_a/`. Panes remain as idle bash on completion for inspection.

A first dispatch stopped at the resource-admission check with exit 9 because
two unrelated DC processes appeared after the initial server check. It ran
no freeze or native tool and created no formal run result. Its pipeline root,
script, log and idle tmux are preserved. A separate q1 dispatcher performs
input preparation, then gates every native invocation on no other DC process
and at least 32 GiB available. It prints a transition when waiting/admitted,
then execs the exact installed DC binary with the original arguments. The
other experiments were not interrupted or modified. They subsequently exited,
and the current snapshot confirms this run's native preflight active.

The resource event log is
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd1_wcg1_dc_resource_20261108_r2q1.log`;
queue/pipeline status is retained under
`artifacts/rd1_wcg1_full_pipeline_20261108_r2q1/`.
Resource scheduling changes no Tcl, constraint, compile or hold policy. The
formal result directory/run ID was unused before q1; no failed output is
resumed or overwritten. There is no automatic retry after an actual failure.

## Reused RTL and corrected identities

The immutable `rd1_wcg1_contextual_20261107_r2` export remains unchanged:
reference 48 SV units, gated 49; source archive SHA
`fcf677b698d582c47080a865d4a75d690188cb0f6f90a8210e8752f2dfe6ddf1`.
No Chisel/firtool elaboration is repeated. The failed 20261107 full r1 and
its original script package remain preserved.

The new 19-file bundle differs from r1 in **only**
`freeze_rd1_wcg1_input.py`. The original Tcl/native runner, constraints,
proxy scripts, profiles and accepted functional-source manifest retain their
previous bytes. Bundle archive SHA:
`281d23783cbba22a27ff1e8908e27a6e25241dc3ff43c18ae7d8f2b8da0cf5fc`.
Outer dispatcher and admission-wrapper bodies/hashes are separately recorded
in JSON. The native binary remains DC O-2018.06-SP1, at most two cores,
original nice-10 invocation, unlimited stack and serial native phases.

The script now pins helper source, raw emitted file and canonical prepared
module separately. The accepted 342-byte module pin is `fbc839...`; the
381-byte raw-file pin is `aeb38a...`. See the
[repair and direct regressions](dc_rd1_wcg1_freeze_repair_20261108.md).
All 48 Python preparation tests pass, including 20 new freeze cases.

## Real input acceptance

- Reference wrapper is byte-identical to immutable RD1; candidate header and
  all non-table declared state match. All 121 functional-source checks pass.
- Retain 47 Route-A units, replace only the contextual wrapper and add the
  exact gate module: 49 Route-A units. Full-KV remains byte-identical.
- All 366,336 table data bits, both opaque 64-bit fields and 4,608 source gate
  instances remain. Page Manager is pinned to the old RD1 hash; PM1/RD2 off.
- R5 backing-exclusion checks, all 16 typed top-port families, all 12 real
  retained owners and all four raw Route-A array interiors pass.
- All five paired array-proxy boundaries pass. Only child interiors are
  proxied; parent controllers remain real. Arrays/external services remain
  nonzero and unestimated outside this mapped boundary.
- Fair-v1 static coverage passes with 1/49 compilation units, ordinary
  input/output counts 41/36 Full-KV and 259/125 Route-A, timed reset and zero
  static unconstrained ports.

New paired input archive SHA:
`59306981d8a7fbda704170b48cc69799b6c2424fcb545805032c93d845c4642e`.
Proxy manifest SHA:
`72d80385a0b6997b7facfa875e519da87b61b506f0184c5c85cd2c812fe33cbd`.
The archived input, target DB, proxy manifest and native driver rehash against
`input_sha256.txt`; source/composition reports and their pins are in JSON.

## Unchanged policies and acceptance boundary

Keep period 2.0 ns, setup/hold uncertainty .10/.02 ns, I/O .20 ns, transition
.05 ns and output load .005 pF. Synchronous reset stays timed; no false or
multicycle exceptions. Constraint Tcl SHA remains
`3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007`;
target library SHA remains
`5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.

Both full tops retain independent snapshots:

1. `primary_raw`: original ideal-clock mapping policy; historical RD1
   comparison requires the unchanged Full-KV primary area 23,091.432498.
2. `propagated_raw`: actual propagated clock arcs with equal .05-ns root
   transition on both complete tops, before any hold pass.
3. `propagated_hold_repaired`: identical `set_fix_hold` and
   `compile -only_hold_time` pass on both, charging all gates/buffers/resizing.

Each supplemental ratio uses its own measured Full-KV denominator, not the
historical ideal-clock area. Native binding must close 4,608 gates and CP/E/TE/Q,
characterization and four Route-A proxies before the formal pair. Final tiers
must retain all table flops, 48 driven entry_id bits, complete reports/DDC/HDL,
gate-enable setup/hold and actual positive gate-Q capture delays. Timing
failures remain measured outcomes, not silently waived tool failures.

Final acceptance still requires both native exit-0/side markers, all six
stage markers, postcheck, full RUN_PASS, result and dispatcher outer exit 0,
all input/library/script/proxy hashes and independent native report review.
Report tool/input closure, mapped area, timing and structural cleanliness
separately. No PPA, external-service zero cost, speedup or hardware net-benefit
claim follows from input freeze or launch. Await the user's completion notice;
do not poll indefinitely, restart, or retry a failed experiment automatically.
