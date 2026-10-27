# MR-2-P3 — P3 staging array-only boundary

**Status:** `parent_access_adapter_functionally_verified`; independent of MR-1B.

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
| accepted legal `p3_pending_fragment_in.fire` | tagged payload-write request `{layer, fragment, data}` followed by exact write ack | exact identity/generation/ordinal/status and fragment order; `stageFragmentNext`/`COMPLETE` cannot advance on request fire alone |
| accepted legal `p3_sidecar_bind_in.fire` | tagged sidecar-write request `{layer, record ordinal, position}` followed by exact write ack | immutable member/payload-ref/logical-position and ordinal order; `stageSidecarNext`/`COMPLETE` cannot advance on request fire alone |
| R3 packed-write read state | tagged payload-read request `{layer, fragment}` followed by held tagged response `{layer, fragment, data}` | immutable write identity, expected count, response-identity comparison, durable terminal |

No direct-pending work, source-plan field, R6 authority, atomic publication,
M2 organization, page size, scheduler, or admission rule changes in this
batch. The boundary has one bounded logical payload-write acknowledgement lane,
one bounded sidecar-write acknowledgement lane, and one bounded tagged payload
read/response lane. These functional parent/child contracts select neither a
physical port count, banking, macro, latency, clock, nor controller. A future
wrapper may map them only after its own approved realization review.

## Required regression

The regression must show that exact materialized member payload/sidecar data
still drives the same packed-write sequence, and that stale, mismatched, fault,
and malformed P3 paths remain fail-closed. Structural guard coverage must also
show that the R3 wrapper contains no direct P3 `Mem`; only the named array
boundary owns the functional reference arrays.

No physical-storage, controller, timing, throughput, energy, area, PPA,
numeric, or model/GPU conclusion follows.

## Verification record

### Parent access successor (2026-10-27)

Successors `c3ec15d`, `cb078fc`, `38248b8`, `742f21e`, and `0023e76` replace
the former direct whole-array parent view with `p3_stage_access_v1` typed
payload/sidecar write acknowledgements and a held, identity-tagged payload
read response. `RouteAM2P3Wrapper` advances fill/sidecar ordering only on the
matching child acknowledgement; it emits each packed-write data beat only
after the matching payload-read response. Claim, generation, admission and
binding ledger, materialization, packed-write ordering, durability,
publication, authority and release remain in the parent.

Remote EDA evidence at successor `0023e76` is:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/logs/
  p3_parent_adapter_isolated_rerun_0023e76.log

RouteAP3StageArrayBoundarySpec                    1/1
RouteAR3R5PublicationSpec                         6/6
EXIT_CODE=0
```

The sixth R3/R5 case is a narrow simulator-facing parent probe: it proves the
P3 request -> tagged read response -> exact packed-write data sequence while
leaving the production candidate/delivery carriers below the probe. This is
required because the remote ChiselSim DPI bridge cannot generate C++ accessors
for an unrelated, existing B2c deep `direct_pending_association` field when
the full R3 wrapper is the simulation root. It is a test-harness limitation,
not a production tie-off, carrier change, or P3 semantic exception.

The historical direct-root `RouteARTL39AMaterializationSpec` is therefore not
used as current remote P3-wrapper evidence; its root DPI failure must not be
counted as a P3 functional failure or as a passing regression. The narrow
probe and P3-child test above are the current directed evidence for this
adapter sub-batch.

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
