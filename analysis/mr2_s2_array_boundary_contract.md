# MR-2-S2 — S2 payload/sidecar array-only boundary

**Status:** `implemented_directed_tested`; independent of MR-1B.

## Scope and closed precondition

The precondition audit finds exactly one S2 control owner:
`RouteAS2GqaSourceWrapper`. It owns slot reservation/generation, fill-open
validation, payload and sidecar ordering, READY, owner-local read
authorization, four-consumer completion, release, reset/init, and drain.
Its previous in-wrapper reference arrays were the only S2 payload/sidecar
`Mem` declarations.

MR-2-S2 moves only those two byte-array interiors into
`route_a_s2_payload_sidecar_array_boundary`. The child has no ready/valid
protocol and cannot create a source instance, fill, READY, GQA commit, release,
authority transition, or lifecycle fact.

## Exact logical access boundary

| Existing accepted S2 event | Array-only access | Control retained in S2 wrapper |
| --- | --- | --- |
| `s2_payload_fragment_in.fire` | payload write at `{slot, fragment}` | exact identity/generation, FILLING, fill-open, ordinal and `last` validation |
| `s2_sidecar_fragment_in.fire` | sidecar write at `{slot, record ordinal}` | exact identity/generation, FILLING, sidecar-required and ordinal validation |
| `s2_payload_read_req_in.fire` | payload read at `{slot, fragment}` | READY, identity/generation, range and response-hold ownership |
| `s2_sidecar_read_req_in.fire` | sidecar read at `{slot, record ordinal}` | READY, identity/generation, sidecar-required/range and response-hold ownership |

The logical capacity stays fixed at two slots, each with 512 64-B payload
fragments and 64 8-B padded sidecar records. This is not an SRAM macro,
banking, port, latency, controller, clock, energy, area, throughput, or PPA
selection.

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

All commands below were run against the implementation in this batch on
2026-10-19.

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
