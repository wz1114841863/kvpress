# WCG1 wrapper model-repair retry — accepted directed functional result

## Disposition

`wcg1_wrapper_model_fix_844e586_20261106_r2` completes successfully:
**baseline 4/4, WCG1 candidate 4/4, total 8/8**, with zero failures, errors,
skips or aborted suites. Independent read-only inspection accepts the
directed real-wrapper functional validation and input/tool provenance.
It does not accept universal equivalence, production integration, real-wrapper
mapped area, 2-ns setup/hold, structural cleanliness, PPA or net hardware benefit.

The prior r1 candidate simulator-build failure remains immutable historical
evidence. This new r2 result demonstrates that the repaired simulation model
builds and executes all four candidate cases. The RD1+PM1 run is not accessed,
modified, restarted or included in this result; no new simulator/DC/STA job
is launched by the audit.

## Completion and independent provenance checks

Source/launch authority:
[`dc_wcg1_wrapper_retry_launch_20261106.md`](dc_wcg1_wrapper_retry_launch_20261106.md)
and its JSON; model repair:
[`dc_wcg1_wrapper_model_repair_20261106.md`](dc_wcg1_wrapper_model_repair_20261106.md).
The independent receipt is
[`dc_wcg1_wrapper_retry_result_20261106.json`](dc_wcg1_wrapper_retry_result_20261106.json).

| Gate | Observed result |
|---|---|
| Input gate | `KVZAP_WCG1_WRAPPER_INPUT_PASS` |
| Required minimal preflight | `WCG1_WRAPPER_GATE_PREFLIGHT_PASS checks=6156 native_modes=0` |
| Native test completion | `All tests passed.`; 8 succeeded, 0 failed/canceled/ignored/pending; 2 suites, 0 aborted |
| Postcheck | `KVZAP_WCG1_WRAPPER_POSTCHECK_PASS tests=8` |
| Run marker | `KVZAP_WCG1_WRAPPER_FUNCTIONAL_RUN_PASS` |
| Outer marker | `KVZAP_WCG1_WRAPPER_VALIDATION_OUTER_EXIT=0` |
| Persisted status | `exit_status` contains `0` |
| Matching r2 processes | None at audit |
| Named tmux | `kvzap-wcg1-wrapper-r2:functional` exists as an idle `sh` pane; completion follows reports/markers, not pane disappearance |

Native test execution reports 1 h 9 min 38 s. Both suite XMLs contain exactly
four testcase elements and zero failure/error/skipped nodes; their independently
computed hashes match `result.json`. The input and preflight result receipts
are byte-identical to the launch snapshot. All 122 frozen project files and
four auxiliary sources rehash against the launch freeze; the preflight's
five source and six output-log hashes also match. The persisted result's
source map and preflight object equal the independently inspected files.
The archive and exact versioned runner rehash as follows:

| Artifact | SHA-256 |
|---|---|
| Input archive | `6565f23ec51c5c499a56c7eeb5559828935c7953ec08b51b42e5874a4a4fb965` |
| Versioned runner | `32090f6850a085f6cdf85045f35f02d229ca78c974ed972f234d5a49fb83746f` |
| Input manifest | `b6257a4ecc534e85979bbc7dd88c6ccf339611d1f72797d8a1e3dc0b9b95f83e` |
| Gate preflight receipt | `25199b6446467021f36b857fc282923c54dbf2c44080c750e85bef03864e36fd` |
| Native functional result | `ddac376cfe45c7b82ced346b591aff24851d62f34fd21e37c3d891508bbbe8bf` |
| Baseline suite XML | `5dbc4fd94660aa5db486a926cb826821a9487a1e53ed811fd303912360040155` |
| Candidate suite XML | `3e258f54436c9d9ef26d8a1c1d5b69ca8c90c69c82f158c5f78bec8c64798f89` |

## What the eight tests cover

Both suites execute the same four case descriptions:

1. Exact A0-bound work and sidecar materialization, retaining reservation
   until the full record completes.
2. Matching-fault reservation release without producing another member work.
3. Exact automatic packed-write sequence and matching-terminal acceptance.
4. Unbound joins, absent-authority stalls, duplicate exclusion, independent
   banks using ordinal 63, and destructive reset behavior in that case.

`RouteAWCG1WrapperSpec` enables the candidate and same-parameter reference
miter in the complete wrapper observation harness. Input and downstream-ready
leaves are shared; output valid/ready is compared continuously and payload is
compared when its channel is live. All 36×64 member/suffix words remain in
the candidate, with 79/80-bit data geometry and the full-width pending handle.
The baseline suite retains its original narrower test transport profile;
candidate/reference comparison is parameter-matched within each candidate
case. This is not an area comparison across those test profiles.

The audit also checks the actual four candidate build directories, not only
Scala source or XML:

- Each has a nonempty 12,020,696-byte simulation executable and a completed
  native compilation log, without `%Error` or COMBDLY.
- Each emitted inline gate matches the repaired frozen helper body, including
  blocking low-phase enable capture and the unchanged SYNTHESIS native binding.
  Emitted gate-file SHA-256 is
  `aeb38a91977e96c1ea8a7b686d712c39bcd902a4489aedfcb0bb4810b2c1fc28`.
- Each Verilator source list contains that inline gate and the generated
  harness assertion layer; the build has `--assert` enabled.
- Each harness assertion layer retains 72 occurrences of the full-wrapper
  differential assertion message, SHA-256
  `484efb73205d3c032f4a1c33a19a159b043d23ea92481ff2279aa48a4051bdd7`.
  These are emitted assertion-message sites, not 72 additional tests or a
  quantified coverage metric. Assertions retain ordinary reset qualification.

The remote minimal preflight remains 6,156 checkpoints / 1,634 edge checks,
with expected differences for bare-AND and merged-enable negative controls.
`native_modes=0` correctly means remote preflight uses Verilator only. The
two earlier local native-cell comparisons, each 368 checks, are separate
model-repair evidence, not a new full-wrapper native-cell timing result.

## Warnings and remaining gates

The aggregate log contains **four** nonfatal `circt.VerbatimBlackBoxAnno`
unprocessed-annotation warnings, one per candidate elaboration, as well as
Scala deprecation/feature/type-test warnings. The emitted gate's presence,
source-list inclusion, native executable and successful stimulus are checked;
there is no evidence that the annotation warning prevented this simulation.
Do not suppress it or describe this result as warning-free. A separately
frozen synthesis input must still prove inline-file/native-cell closure.

This is a positive functional milestone: the earlier COMBDLY build blocker
is passed, and the gated candidate preserves the tested outputs/handshakes
against the reference. Four directed candidate cases are not a proof for
every legal generic-wrapper trace; no broad regression or formal closure is
silently substituted by the eight-test count.

Next is the already planned **real-wrapper isolated HDL/native-binding
closure and matched mapping/propagated-clock STA**, including actual parent
enable setup/hold, reset/reuse/raw-read coverage and charged hold repair at
unchanged 2 ns. It is not launched by this inspection. The earlier accepted
one-bank 16.5262% area reduction remains a separate screen, not a new full
wrapper or full Route-A result. The accepted RD1 overall ratio is unchanged
at 146.747×; do not add PM1/WCG1 local savings to it arithmetically.

Production tops remain default-off for WCG1. RD2 stays excluded. Preserve
the independent RD1+PM1 input and wait for its separately reported completion.
All local source/receipt consistency and documentation checks, followed by
`git diff --check`, are required before the separate result-document commit.
