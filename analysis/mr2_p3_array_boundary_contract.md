# MR-2-P3 — P3 staging array-only boundary

**Status:** `implemented_directed_tested`; independent of MR-1B.

## Scope

MR-2-P3 separates the existing functional P3 payload-stage and position-sidecar
array interior from `RouteAM2P3Wrapper` into
`route_a_p3_stage_array_boundary`. The boundary retains the current fixed
logical envelope only: 36 stage layers, each with 512 64-B payload fragments
and 64 8-B sidecar records.

This is not a macro, SRAM port, banking, latency, controller, clock, or PPA
choice. Its named accesses are the current accepted functional transactions;
a future physical-wrapper mapping remains separately pending.

## Preserved ownership

`RouteAM2P3Wrapper` remains the sole owner of P3 control and all semantic
decisions: claim/generation, admission-member and pending-binding ledger,
fragment and sidecar ordering, fault exclusion, materializer reservation,
packed-write sequencing, payload durability, M2 publication, R6 authority
observation, and release. The new child holds bytes only. It does not create
an R2 request, authority transition, source selection, payload binding,
publication, endpoint, or source packet.

The exact logical access mapping is:

| Existing accepted event | Array-only access | Retained R3 control gate |
| --- | --- | --- |
| `p3_pending_fragment_in.fire` | one payload write at `{layer, fragment}` | exact identity/generation/ordinal/status and fragment order |
| `p3_sidecar_bind_in.fire` | one sidecar write at `{layer, record ordinal}` | immutable member/payload-ref/logical-position and ordinal order |
| accepted packed-write data state | one payload read at `{layer, fragment}` | existing immutable write identity, expected count, durable terminal |

No direct-pending work, source-plan field, R6 authority, atomic publication,
M2 organization, page size, scheduler, or admission rule changes in this
batch. The boundary does not decide whether a later P3 macro has one or more
physical ports; a future wrapper may map these logical accesses after its own
approved realization review.

## Required regression

The regression must show that exact materialized member payload/sidecar data
still drives the same packed-write sequence, and that stale, mismatched, fault,
and malformed P3 paths remain fail-closed. Structural guard coverage must also
show that the R3 wrapper contains no direct P3 `Mem`; only the named array
boundary owns the functional reference arrays.

No physical-storage, controller, timing, throughput, energy, area, PPA,
numeric, or model/GPU conclusion follows.

## Verification record

The following commands passed from the current live worktree on 2026-10-19:

```text
.venv/bin/python -m pytest -q tests/test_mr2_p3_array_boundary.py
# 2 passed

cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
# passed

env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.rtl3.RouteARTL39AMaterializationSpec' \
  'testOnly kvpress.routea.rtl2.RouteAR3PackReadPathSpec'
# 3/3 and 4/4 passed

env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.RouteAMeasurementDutR3Spec' \
  'testOnly kvpress.routea.FullKVMeasurementDutSpec' \
  'testOnly kvpress.routea.DualMeasurementDutStructuralSpec'
# 3/3, 5/5, and 2/2 passed
```

`RouteAR3PackReadPathSpec` needed one harness-only repair: it now explicitly
holds the later RTL3.9-A materializer outputs backpressured, because the
legacy test injects its own checked pack-read work and has no materializer
consumer. This neither changes the production wrapper nor consumes or
manufactures a production owner event.
