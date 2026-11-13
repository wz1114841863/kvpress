# MR-2-S2 — S2 payload/sidecar array-only boundary

**Status:** `route_a_and_full_kv_parent_access_adapters_functionally_verified`;
independent of MR-1B.  Both contours now have a payload-only typed logical
array access path.  This remains implementation evidence, not a paired
access-map or common-cost cancellation decision: Route-A retains its distinct
sidecar path and the two parent shells have not yet been dispositioned as
equivalent.

## Scope and closed precondition

The precondition audit finds exactly one S2 control owner:
`RouteAS2GqaSourceWrapper`. It owns slot reservation/generation, fill-open
validation, payload and sidecar ordering, READY, owner-local read
authorization, four-consumer completion, release, reset/init, and drain.
Its previous in-wrapper reference arrays were the only S2 payload/sidecar
`Mem` declarations.

MR-2-S2 moves only those two byte-array interiors into
`route_a_s2_payload_sidecar_array_boundary`. The child exposes bounded typed
payload/sidecar write request/acknowledgements and read request/responses.  It
has no transaction identity, source generation, READY, GQA, release,
authority-transition, lifecycle, allocator, or selection state.  The parent
captures only already accepted, fully validated coordinates; its matching ack
or response is required before parent order advances or an outward response is
offered.

## Exact logical access boundary

| Existing accepted S2 event | Array-only access | Control retained in S2 wrapper |
| --- | --- | --- |
| `s2_payload_fragment_in.fire` | parent captures tagged payload write; child `payload_write_req.fire` writes `{slot, fragment}`; matching `payload_write_ack.fire` advances payload order | exact identity/generation, FILLING, fill-open, ordinal and `last` validation |
| `s2_sidecar_fragment_in.fire` | parent captures tagged sidecar write; child `sidecar_write_req.fire` writes `{slot, record ordinal}`; matching `sidecar_write_ack.fire` advances sidecar order | exact identity/generation, FILLING, sidecar-required and ordinal validation |
| `s2_payload_read_req_in.fire` | parent captures approved read; child `payload_read_req.fire` / matching `payload_read_rsp.fire` supplies `{slot, fragment}` data | READY, identity/generation, range and external response-hold ownership |
| `s2_sidecar_read_req_in.fire` | parent captures approved read; child `sidecar_read_req.fire` / matching `sidecar_read_rsp.fire` supplies `{slot, record ordinal}` data | READY, identity/generation, sidecar-required/range and external response-hold ownership |

The logical capacity stays fixed at two slots, each with 512 64-B payload
fragments and 64 8-B padded sidecar records. This is not an SRAM macro,
banking, port, latency, controller, clock, energy, area, throughput, or PPA
selection.

## Full-KV payload-only paired successor (2026-10-28)

`FullKVS2GqaSourceWrapper` now owns a real parent-to-child payload path through
`full_kv_s2_payload_array_boundary`.  The child accepts only `{slot, fragment,
data}` writes and `{slot, fragment}` reads, returning typed acknowledgements
and data.  It contains no transaction identity, source generation, READY,
terminal, four-consumer, release, fault, or source-selection state.  The
baseline parent keeps those facts and admits an outward read only for a READY
slot with exact identity, generation, and fragment range.  Its write order
advances only after a matching child acknowledgement; its read response is
held by the parent under downstream backpressure.

This is deliberately payload-only.  Full-KV does not acquire Route-A packed
sidecar, packed-page, or Route-A direct-source control merely to make an
interface look similar.  The common payload classification remains pending
the separate paired access-map and shell-equivalence disposition.

| Remote directed successor | Result |
| --- | --- |
| `FullKVMeasurementDutSpec` | `5/5` passed: async write-ack/READY, read data and response hold, stale identity, fault without READY/release, reset and lifecycle drain |
| `DualMeasurementDutStructuralSpec` | `3/3` passed |
| remote log / marker | `fullkv_s2_directed_rerun.log`, `FULLKV_S2_RERUN_EXIT=0` |

The first remote run exposed a test-only fixed-cycle assumption about child
write-ack timing.  The rerun waits for the actual parent-owned READY fact; it
does not weaken the wrapper protocol or use a test tie-off.  These results are
functional/structural only and neither select physical ports, macros, timing,
DC, CACTI, nor PPA.

## Required regression

Existing S2 coverage must continue to prove payload and sidecar storage are
readable only after READY, read responses remain stable under backpressure,
stale/reuse traffic fails closed, and release occurs only after four matching
GQA commits. The structural guard must prove that
`RouteAS2GqaSourceWrapper` owns no direct S2 payload/sidecar `Mem` and that
the named child is the sole logical-array owner.

No direct-pending association, R6 plan schema, R3/R5 publication, admission,
page size, scheduler, numeric, external memory, physical-storage, or PPA
conclusion changes in this batch.

## Executed verification record

The historical direct-boundary results below remain valid.  The typed parent
adapter successor was run remotely on 2026-10-27.

| Check | Command / result |
| --- | --- |
| array-boundary structural guards | `.venv/bin/python -m pytest -q tests/test_mr2_p3_array_boundary.py tests/test_mr2_s2_array_boundary.py` — `4 passed` |
| Chisel compilation | `cd hardware/route_a/chisel && env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'` — passed |
| S2 direct behavior | `testOnly kvpress.routea.s2.RouteAS2DirectPendingSpec` — `3/3` passed |
| packed S2 behavior | `testOnly kvpress.routea.rtl2.RouteAPackedS2ReadPathSpec` — `6/6` passed |
| reset epoch regression | `testOnly kvpress.routea.integration.RouteAResetEpochIntegrationSpec` — `4/4` passed after the composition-only legacy top's unused fork and test ingress were explicitly drained |
| W0/MR-1A Route-A non-regression | `testOnly kvpress.routea.RouteAMeasurementDutR3Spec` — `3/3` passed |
| W0/MR-1A Full-KV non-regression | `testOnly kvpress.routea.FullKVMeasurementDutSpec` — `5/5` passed |
| dual-DUT structural guard | standalone rerun of `testOnly kvpress.routea.DualMeasurementDutStructuralSpec` — `2/2` passed; the preceding combined invocation had a Verilator temporary dependency-file build failure, not a Chisel assertion or test failure |

The final standalone structural command ended with
`MR2_S2_STRUCTURAL_EXIT=0`. This is functional/structural regression evidence
only; it does not select a physical wrapper or establish synthesis/PPA
eligibility.

### Parent-access adapter successor (2026-10-27)

| Check | Result |
| --- | --- |
| local no-model guard | `.venv/bin/python -m pytest -q tests/test_mr2_s2_array_boundary.py` — `2 passed`; `git diff --check` passed |
| Route-A S2 directed | remote `RouteAS2DirectPendingSpec` `3/3` plus `RouteAPackedS2ReadPathSpec` `6/6`; `s2_adapter_directed_rerun.log`, `S2_ADAPTER_RERUN_EXIT=0` |
| selected cross-stage non-regression | Route-A measurement `4/4`, Full-KV measurement `5/5`, dual-DUT structural `3/3`, and four-consumer `3/3`. The first combined execution exposed only a fixed-cycle S2 terminal-ready test assumption; `RouteAFourConsumerCompletionSpec` was rerun after it waited for the required child write ack, `S2_FOURCONSUMER_RERUN_EXIT=0` |

The Full-KV five-test result is a non-regression control only.  It does not
provide a Full-KV payload access adapter, an access-map equivalence proof, or
a common-cost cancellation.  No macro, physical port count, latency, clock,
controller, DC, CACTI, or PPA conclusion follows.

The immutable `measurement_dut_cut_freeze_20261025.json` remains anchored to
`fc06fdbc` and is deliberately not rewritten.  Its live-source SHA guard now
reports the prior P3 successor drift in `RouteAIncrementalSkeletons.scala` and
this S2 successor drift in `RouteACommonSkeletons.scala`; that expected
historical-manifest mismatch is not a semantic regression.  A new source/port
freeze is deferred until the approved Full-KV S2 pairing and P3 full-root DPI
harness recovery are both complete.
