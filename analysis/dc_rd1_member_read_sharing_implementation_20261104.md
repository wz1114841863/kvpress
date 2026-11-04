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
- Existing `RouteARTL39AMaterializationSpec` and `RouteAR3R5PublicationSpec`:
  9/9 PASS, 2/2 suites complete, outer `KVZAP_RD1_EMIT_FOCUS_EXIT=0`.
  The tests cover materialized work/sidecar hold and release, fault handling,
  packed-write sequencing, publication ordering, non-contiguous members,
  descriptor failure and tail-link behavior. Log:
  `/tmp/kvzap_rd1_emit_focus_20261104_r1.log`.

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

Input closure:

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
- The source commit recorded in the run is `e5d3107`.

## Completed screen result

The tmux pane exited with status 0. Both side PASS markers, total
`KVZAP_RD1_READ_NETWORK_SCREEN_PASS` and outer
`KVZAP_RD1_READ_SCREEN_EXIT=0` are present. Both sides emitted DDC, mapped
HDL, QoR, area, timing, constraints and design-check reports. There are no
remaining screen processes.

| metric | original independent reads | RD1 shared reads | change |
| --- | ---: | ---: | ---: |
| combinational / cell area | 342,379.460369 | 126,874.772938 | -215,504.687431 (-62.943%) |
| combinational cells | 412,372 | 165,779 | -246,593 (-59.799%) |
| nets | 594,427 | 347,834 | -246,593 (-41.484%) |
| buffer/inverter cells | 60,976 | 30,535 | -30,441 (-49.923%) |
| buffer/inverter area | 30,727.200494 | 15,359.904245 | -15,367.296249 (-50.012%) |
| sequential cells / area | 0 / 0 | 0 / 0 | unchanged, as intended |
| macros / black boxes | 0 / 0 | 0 / 0 | unchanged |
| worst reported logic levels | 20 | 21 | +1 |
| worst max-path arrival | 0.578519 ns | 0.634739 ns | +0.056220 ns (+9.718%) |
| precise worst setup slack | +1.121480 ns | +1.065261 ns | -0.056219 ns |
| TNS / violating paths | 0 / 0 | 0 / 0 | unchanged |

Thus RD1 is a clear area win for this isolated read network. It trades one
extra request/ordinal selection level for a small delay increase. Both sides
still meet the identical fair-v1 2.0-ns screen constraint with positive slack,
no setup/hold violations, no design-rule violations and no unconstrained
endpoint diagnostic. QoR prints WNS as 0.00 because neither side has negative
slack; the precision timing reports provide the positive values above.

Structural warnings are unchanged: 34 on each side, comprising the unused
clock/reset of this deliberately combinational harness, direct valid pass-through
and the intentionally constant-zero unused M position output. They do not show
a lint improvement or regression in production RTL. Native result identities:

- original area/QoR/timing report SHA-256:
  `3ce1cc980e17c0e7912160ed9ac979cd7ecacdde7c3c38e86844954ffa477c30`,
  `cf775f09c7ac7b2e4c78d423da2afa16d94406fdfd49f8de2bb42edafa0c52c6`,
  `1b052a215662f696ed303a8b49eab0f65598d880ecc8db16fbaf65e2b2aadcae`;
- shared area/QoR/timing report SHA-256:
  `a81a0ed71d208c69ef38a5dacc9715c7cc1442ae7be183b1cd5eb0707291ac74`,
  `a6b22d6e12b063088d6c280b49865ba933a1443bb7d73617436df962c27cb995`,
  `9eddfe359b805d48219ab71bd523a2d24b101edc327489b5d6cda9d9fb223722`;
- original/shared mapped HDL SHA-256:
  `9fd7f6be1cb4b7f9f33d4bb5481aaf5d92d8dfe68d6b7f97b1701cd3b39ce32a`,
  `c6f65c48dfd8bca3b7074e16d81e6827c09f03bee1e7d1f31821d582214ee58c`.

This establishes a bounded combinational read-network area/delay result only.
It cannot establish the realized whole-wrapper saving because production
context may merge or overlap other cones. It also excludes storage and clock
load: RD1 does not reduce the 366,336 stored bits, and the screen has no
sequential cells. It does not establish complete Route-A timing closure, PPA,
external-service cost or system net benefit. The full 57-test regression and
generated-source/proxy gates remain future integration checks; no new complete
paired DC was launched.

The existing driver-repair run
`dc_feasibility_fair_m2p3_entryid_repair_20261104_r1` was inspected read-only:
its dc_shell process remains active in `kvzap-control-refine:p11-entryid-dc` at
result inspection time.
Its files and process are untouched.
