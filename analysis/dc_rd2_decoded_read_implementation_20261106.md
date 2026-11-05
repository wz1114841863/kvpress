# RD2 isolated decoded-read candidate — 2026-11-06

## Scope and selected realization

RD2 progresses independently while the frozen RD1 complete paired DC runs.
The production `RouteAM2P3Wrapper` and all frozen remote inputs remain
unchanged.  `RouteARecordReadDecode` is a new, currently unused-by-production
combinational helper.  It builds one ordinal decoder shared across banks,
selects each bank's word using `Mux1H`, then selects the bank using `Mux1H`.
Each caller retains its own port.  It has no valid, ready, fire, state,
arbitration or latency input/behavior.

The initial experiment targets the remaining read implementation, not a new
concurrency restriction.  It keeps the RD1 M/S/O shared member reader on both
sides.  Four additional independent raw reads are:

| reader | output width | baseline | candidate |
|---|---:|---|---|
| M pending suffix | 80 | nested indexed suffix read | decoded suffix read |
| C payload and pending suffix | 144 | two indexed tables | concatenated word with common decode |
| F payload reference | 64 | indexed member payload | field-specific decoded payload |
| B member | 79 | indexed member record | decoded member record |

Both screen inputs include the same 36 x 64 member/suffix table image.
Storage is an identical combinational input image and excluded from area on
both sides.  Every raw read remains observable continuously, including
consumer-valid-low cycles; C/F/B are never assumed mutually exclusive.  The
common RD1 M/S/O outputs retain the previous valid-gating and M-position-zero
convention.  No generated production state or port changes.

## Equivalence boundary and integration gate

The current experiment compares in-range layer/ordinal values.  It does not
claim equivalence for out-of-range layers, where the baseline dynamic Vec read
has implementation-dependent behavior.  That behavior and fail-closed ready
semantics must be explicitly checked before any production integration.

The helper and test-only `RouteARD2RemainingReads` function are exercised by a
differential miter sharing actual register images.  Geometry is checked at
4 x 8 and 36 x 64.  Tests cover every address on every raw reader with valid
low, all validity masks, same-bank different-ordinal concurrency, different
banks, pre-edge same-address read/write and held reads across cycles.  Random
records include independent 15-bit position, 64-bit payload and 80-bit suffix
values.  Exact output values are also checked against a software scoreboard.

The first local build was interrupted after the default C++ optimizer consumed
most available RAM/swap (r1 outer exit 143).  A second attempt did not produce
a terminal marker; the local kernel recorded an OOM kill of `cc1plus` and its
tmux scope disappeared.  Neither attempt supplies a full-geometry test pass.
The test now explicitly splits Verilator C++ outputs/functions and limits
build parallelism to two jobs.  This changes only simulator compilation, not
RTL, stimulus or synthesis effort.  Small-geometry address widths also match
their actual Vec sizes to eliminate avoidable elaboration warnings.

The synthesis harness changes only nested indexing versus decoded reading.
Candidate selection/masks, reconciliation, write network, lifecycle and all
production owners are outside this experiment.  Any area benefit must be
incremental relative to the RD1-enabled baseline, not re-credited RD1 savings.

## Small-synthesis procedure

`RouteARD2ReadNetworkEmitter` emits immutable SV pairs.
`run_rd2_read_network_screen.sh` consumes a fresh prepared root containing
copied inputs, source snapshots and scripts.  It verifies fair-v1 numerical
constraints, the target-library and constraint hashes, records every input
hash, then runs each side in its own DC process with unlimited stack.

Both tops use the identical fair-v1 2.0-ns constraint procedure and medium-effort
mapping.  Zero registers, complete reports/DDC/mapped HDL, native side PASS
and an error-free log are required.  A final postcheck rehashes the inputs and
checks exact non-empty scalar summaries.  Setup/hold/delay, fanout, area and
lint must be evaluated independently; any negative result is retained.

This isolated screen does not establish storage cost, complete Route-A area,
timing closure, PPA, external-service cost or hardware net benefit.  Integration
requires a later explicit decision, functional tests and generated-input
closure after RD1 acceptance.

## Current validation handoff

Source compilation passes with Java 21 and Chisel 7.15.0.  Bash syntax, runner
help, both embedded Python blocks, Tcl structural completeness and
`git diff --check` pass.  The production wrapper is byte-identical to HEAD's
pre-RD2 version.  No full-suite functional PASS is claimed yet.

The active final-source local run is in tmux
`kvzap-rd2-local:rd2-test`, with log
`/tmp/kvzap_rd2_local_20261106_r4.log`.  It runs the 4 x 8 and 36 x 64
`RouteARD2ReadDecodeSpec` tests, followed only on test success by the paired
emitter targeting `/tmp/kvzap_rd2_read_inputs_20261106_r4`.  Required terminal
marker is `KVZAP_RD2_LOCAL_TEST_EMIT_EXIT=0`, plus the two-test pass and
`RD2_SCREEN_INPUT_EMIT_PASS`.

R3 was a simulator-build trial with the split-output settings; it was
interrupted before acceptance to correct C's observed fields from the full
79-bit member to its actually consumed 64-bit payload.  R4 tests and emits
the final 144-bit C payload+suffix path.  R1--R3 logs remain diagnostic only.

At the current snapshot the final-source full-geometry simulator C++ build is
still active; the large remaining compiler process uses about 6 GiB while
host memory remains available.  No native simulation/assertion failure is
reported, but absence of an error is not a test pass.  The immutable remote
RD1 process remains independently active.

After the user reports local completion, verify the full test and emitter
markers, compare both generated port headers and hashes, then freeze a new
isolated remote RD2 screen root.  No RD2 remote DC is active yet.  Do not
start DC on partial emission or treat the current state as functional or
mapped acceptance.
