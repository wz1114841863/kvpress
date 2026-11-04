# RD1 bank-local member read sharing — 2026-11-04

## Scope and implementation

User-authorized implementation of the selected candidate in
`dc_compact_membership_read_sharing_plan_20261104.md`. RD1 shares only the
member-record lookup for M/S/O within each bank. The 36 x 64 x 79 register
table, 80-bit suffix table, C/F/B lookups, global consumer selectors and all
existing state updates remain intact. No registers, latency, ready/fire
arbitration or forwarding are added. Three different banks retain concurrent
service. Inactive source bits may differ, as allowed by the read-sharing plan;
valid-cycle fields and existing handshake equations are preserved.

`RouteAMemberRecordReadSharing.scala` is an inline combinational helper:
each bank merges the ordinal of its sole valid M/S/O request, reads one
record, and supplies the existing consumer bank selections. Assertions check
at most one request per bank and valid layer bounds. The wrapper also asserts
the reviewed observationActive -> EMPTY invariant. The two reconstructed
entry_id outputs and synthesis driver-preservation policy are unchanged.

## Local verification

- Java 21 `Test / compile`: PASS.
- `RouteARD1ReadSharingSpec`: 1/1 PASS, outer
  `KVZAP_RD1_MITER_EXIT=0`, log `/tmp/kvzap_rd1_miter_20261104_r1.log`.
  One shared register image feeds independent original reads and the actual
  production helper. It checks all 6,912 consumer/address choices, 512 random
  distinct-bank concurrent cases with held requests and independent writes,
  all eight valid subsets, and same-address pre-edge/post-edge visibility.
  This is a directed/random local equivalence miter, not formal reachable-state
  equivalence of the complete wrapper.
- `RouteARD1ReadNetworkEmitter`: PASS, two immutable SV inputs generated in
  `/tmp/kvzap_rd1_screen_inputs_20261104_r1`. No extra production module is
  introduced by the helper.
- Existing `RouteARTL39AMaterializationSpec` and `RouteAR3R5PublicationSpec`
  are running in local tmux `kvzap-rd1-local:rd1-emit-focus`, log
  `/tmp/kvzap_rd1_emit_focus_20261104_r1.log`. Acceptance is pending their
  final test summary and `KVZAP_RD1_EMIT_FOCUS_EXIT`.

## Isolated synthesis screen

The test-only emitter creates original/shared combinational readers at the
actual 36 x 64 x 79 geometry. Identical data inputs replace storage on BOTH
sides. Both expose valid-gated M/S/O payload_ref, S/O logical_position and
valid bits; M logical_position is a constant zero on both sides because M
does not consume it. Legal requests require layers < 36 and no same-bank
overlap. Shared reads use the production helper; original reads use three
independent dynamic lookups. Verification assertions are excluded from both
synthesis inputs. The synthetic inputs do not encode full-wrapper phase or
priority correlations, and inactive outputs are masked equally on both sides.

`run_rd1_read_network_screen.sh` refuses an existing manifest/output directory,
verifies the frozen library/constraint hashes and all fair-v1 numbers, and
records input/script/source hashes. `screen_rd1_read_network.tcl` runs each
side with the same mapping command and saves DDC, mapped HDL, native QoR,
hierarchy area, timing, constraints and design checks. All scripts are copied
into an isolated screen root. They never overwrite the active full-DC scripts,
input archive, proxy tree or run directory.

Screening is launched from implementation commit `e5d3107` in remote tmux
`kvzap-control-refine:p12-rd1-screen`. Run ID:
`rd1_read_network_screen_20261104_r1`. The root is
`/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/rd1_read_network_screen_20261104_r1/`;
the total log is `dc_shell.log` within it. Completion requires both
`KVZAP_RD1_SCREEN_SIDE_PASS` markers, `KVZAP_RD1_READ_NETWORK_SCREEN_PASS`,
outer `KVZAP_RD1_READ_SCREEN_EXIT=0`, and complete native artifacts.

Initial acceptance is **input closure only**, not a synthesis result:

- `KVZAP_RD1_SCREEN_INPUT_PASS`; all 13 remotely recorded input/script/source
  hashes match the local prepared bundle.
- Manifest SHA-256:
  `961866b818e5af2bd4285285cc509964114bfb9ee194655095b5b63b95f09f67`.
- Original SV SHA-256:
  `200872b0f1735b18f0b33163d0779ca41b5820f19e4324c07a8b5a756935791f`.
- Shared SV SHA-256:
  `94c86e0726bc3413faa586f59504a6e41054aa62d5e60e19a0876e8a051ef17b`.
- The launcher verified the library and constraint Tcl against the frozen
  fair-v1 profile, including all seven numerical timing/load values.
- Initial native log shows the original reader completing Presto compilation.
  Both the screen process and pre-existing driver-repair dc_shell are active;
  no completion, area or timing result is accepted yet.

After notifying the user, leave the remote experiment running and await their
completion notification. Inspect native reports, hashes, both exits and the
outer marker before concluding. It may establish a bounded combinational
read-network area/delay change only. It
cannot establish whole-wrapper savings, complete setup closure, storage cost,
clock-load reduction, PPA, external-service cost or system net benefit. RD1
does not reduce the 366,336 bits stored by the two compact tables. The full
57-test regression and generated-source/proxy gates remain future integration
checks; no new complete paired DC is authorized or launched.

The existing driver-repair run
`dc_feasibility_fair_m2p3_entryid_repair_20261104_r1` was inspected read-only:
its dc_shell process remains active in `kvzap-control-refine:p11-entryid-dc`.
Its files and process are untouched.
