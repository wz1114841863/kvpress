# PM1 registered selector screen successor — 2026-11-04

## Purpose and failure-layer correction

This is the bounded successor to failed isolated run
`pm1_selector_screen_20261104_r1`. That run passed input closure, analyze,
elaborate, link and fair-v1 constraint application, then the DC 2018 native
process segfaulted while mapping the original 36,720-primary-input flat
selector. It produced no mapped side and never attempted the PM1 candidate.

The successor changes only the measurement harness:

- both sides retain the exact immutable combinational selector SV from r1;
- both sides add the same 36,720-bit registered state source;
- both sides add the same 17-bit registered result boundary;
- the measured selector path is therefore Q -> selector -> D, matching the
  structural class of the Page Manager path rather than primary input ->
  primary output;
- original and banked sides run in independent `dc_shell` processes, so one
  native-process failure cannot erase the other side's evidence.

The state shifts one serial input solely to keep every bit controllable with a
narrow top interface. It is not Page Manager allocation/reclaim update logic
and its identical sequential area must not be counted as PM1 savings. The only
allowed differential is the selector realization.

## Local validation

- Java 21 `Test / compile`: PASS after correcting one missing local `Cat`
  import; no synthesis input existed at that failed compile attempt.
- `RouteAPM1RegisteredSelectorSpec`: 1/1 PASS. At a 73-entry, 8-entry-bank
  geometry, original and banked sides use independent but identical shift
  state/result registers and match cycle-by-cycle across 1,344 zero, one,
  boundary-pattern and random shifts. Outer marker
  `KVZAP_PM1_REGISTERED_MITER_EXIT=0`; log
  `/tmp/kvzap_pm1_registered_miter_20261104_r1.log`, SHA-256
  `0a0876e2901436d067c2e743a045c60fbcf7a0245cb3aac971a70f82a72f76ad`.
- Direct full-width Chisel emission of registers plus selector caused firtool
  itself to exit 139 before producing a file. The accepted preparation path
  therefore regenerates the already accepted combinational SV and appends one
  small explicit SystemVerilog wrapper using
  `wrap_pm1_registered_selector.py`; it does not modify the child selector
  body.
- Both resulting full-width inputs pass Verilator lint. Original log SHA-256
  `b9f36af162e99b8cbf8c8481d9863c04a97cb3a74fcecf7512a5c78bb20bd633`;
  banked log SHA-256
  `ef9c7d47ff7d067e6fb3c50a05b0273307142b8e36cd661c7808b1e1b79867b4`.

Input identities:

- immutable original child SV remains
  `8019d8c27b3920ec97448fcdf381b12a4e2655522a9f81d46fd194208ab023db`;
- immutable banked child SV remains
  `1603cdecda927ba02bead96ced5939eb2b356f4ea4acccabd6f5b794ffda7fac`;
- wrapped original input SHA-256 is
  `74d5c9370540aa91eae4c234c66de7b16161d2040111dbdd8ead9ec2756dd8b8`;
- wrapped banked input SHA-256 is
  `12f0e1394244bbba327b299e1b0c5779f95023a4721c63b6a350fe4437a7ddf9`.

## Screen acceptance

The runner verifies the same immutable `dc_feasibility_fair_v1` profile,
seven numerical constraints, target-library hash, constraint-Tcl hash and all
input/source/script hashes. Each side must have exactly 36,737 registers both
before and after mapping: 36,720 matched state bits plus 17 matched result
bits. Each independent side must emit its own PASS and outer exit zero. Total
acceptance additionally requires the combined PASS/outer-zero markers and
native DDC, mapped HDL, design checks, QoR, hierarchy area, precise timing and
constraint reports for both sides.

## Completed remote screen disposition

The successor was launched from commit
`9e6632ba3082e01728e098ff7133ad9cd20b461b` in remote tmux
`kvzap-control-refine:p14-pm1-reg-r2`:

- run ID: `pm1_registered_selector_screen_20261104_r2`;
- root:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/pm1_registered_selector_screen_20261104_r2/`;
- total log: `dc_shell.log` in that root, with independent
  `original_dc_shell.log` and `banked_dc_shell.log`;
- manifest SHA-256:
  `64d147117826fe2c2571aca2d1d19a317231f012d5ce5816f51e9b8b427da4b9`;
- frozen target-library SHA-256:
  `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.

Input closure passed, but the paired screen did **not** complete normally:

- original analyzed, elaborated, linked, applied fair-v1 constraints and
  passed the exact 36,737-register precompile gate, then native DC again
  segfaulted in Pass-1 mapping while processing child
  `pm1_original_selector`; side outer exit is 139 and no original mapped
  artifact/report exists;
- because the runner uses independent processes, banked continued and emitted
  side PASS, side outer exit zero, DDC, mapped HDL and all native reports;
- combined markers are `KVZAP_PM1_REGISTERED_SELECTOR_SCREEN_FAIL` and
  `KVZAP_PM1_REGISTERED_SELECTOR_SCREEN_OUTER_EXIT=1`;
- the tmux window and run processes are gone.

Thus r2 confirms that adding matched Q/D boundaries does not avoid the DC 2018
mapping crash for the original flat child. It also confirms the banked child
is independently mappable. The run is not a matched PM1 comparison and cannot
establish an area or timing improvement.

The banked-only native result is retained as partial diagnostic evidence:

- 36,737 sequential cells / 98,999.710669 sequential area, matching the
  harness contract;
- 96,132 combinational cells / 66,640.727301 combinational area;
- selector-child area 64,849.6793;
- precise worst setup slack +0.000505 ns, zero setup TNS/violating paths;
- 28 hold violations, hold WNS about -0.01 ns and hold TNS -0.14 ns, all
  reported at artificial shift-state endpoints rather than selector result
  registers.

Banked artifact identities include DDC SHA-256
`f3dc759e6d80a3807626434366ddc7308e396f24bd26819ff1e25a9a5792f739`,
mapped-HDL SHA-256
`195cc6230d3f3eb1003b0eac04daf657cb15bd5835779289269e267b1f62d347`,
and area/QoR/timing report SHA-256 values
`0c2ed31dfd47d7c40c7bd35a302c0c3dee79639e70081b15e68ff5b138cf5412`,
`2ad7f3f70b2135c14e8359c0136f79a86b7f2adcf688df7744294e0118beace7`,
and `604c4c8720cf9eda4632b45a20921f1ff9fcad1b50f105479474d6c7b9201e19`.
Do not restart or relabel this failed paired run.

## Boundaries

This screen can establish only the differential area and Q-to-D delay of the
isolated exact selector under fair-v1 library/constraint assumptions. It does
not establish production Page Manager integration, complete Route-A area or
timing closure, clock-load improvement, lint closure, PPA, external-service
cost, system acceleration or hardware net benefit. It changes no pruning,
admission, R3 publication, R6 authority, R2 arbitration or R5 proxy contract.
