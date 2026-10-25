# MR-2 completion review — logical storage boundaries

**Review date:** 2026-10-25
**Disposition:** `functional_measurement_boundary_passed`
**Authority:** MR-2 only; this is not a synthesis, macro, controller, DC,
CACTI, timing, area, energy, throughput, or PPA decision.

## Decision

MR-2 is complete at its approved functional measurement-boundary scope. The
four approved logical storage interiors are isolated behind production Chisel
parents, while the state machines, accepted-event qualification, identity and
generation checks, atomicity, lifecycle, reset, and external-service contracts
remain in the parent DUT logic. No MR-2 child creates an R3 publication, R6
authority/terminal action, R2 request/arbitration action, source selection, or
external-memory service action.

This review does not treat a logical `Mem`/`RegInit` split as a selected memory
implementation. Every physical wrapper, macro, port count, latency, access
model, queue/staging activity model, and cost value remains unselected or
`unestimated_not_zero` under the SRP/MBR records.

## Boundary completion matrix

| Interior isolated by MR-2 | Parent-retained production control | Functional evidence | Completion result |
| --- | --- | --- | --- |
| P3 stage payload and sidecar arrays: 36 logical stages with 512 64-B payload fragments and 64 8-B sidecar records per stage | `RouteAM2P3Wrapper`: claim/generation, immutable binding ledger, fragment/sidecar ordering, materializer reservation, packed-write durability, M2 publication, R6 observation and release | `mr2_p3_array_boundary_contract.md`: local structural `2/2`; materialization `3/3`; pack-read `4/4`; Full-KV/Route-A/dual-DUT checks | PASS: byte interiors only; no P3 control or external backing is hidden in the child. |
| S2 payload and sidecar arrays: two logical slots, each with 512 64-B payload fragments and 64 8-B sidecar records | `RouteAS2GqaSourceWrapper`: fill validation/order, READY, read authorization/response hold, four-consumer completion, release, reset/init and drain | `mr2_s2_array_boundary_contract.md`: local structural `4/4`; S2 direct `3/3`; packed read `6/6`; reset `4/4`; W0/MR-1A and dual-DUT checks | PASS: the common S2 control remains paired Full-KV/Route-A infrastructure. |
| M2 head/span entry arrays: 288 keys × two mirrored 128-bit head entries plus 614 128-bit span entries | `RouteAM2ProductionControlOwner`: immutable operand/prepare association, RMW decision, private prepare/abort, slots/generation, credit, typed fault, publication resolution and post-R6 handoff | `mr2_m2_array_boundary_contract.md`: local guards `8` passed; remote directed `11/11`; selected cross-stage `40/40` | PASS: publication visibility and handoff release remain parent-owned; fixture-only `RouteAM2EntryStorage` remains non-production evidence. |
| R5 availability/generation vectors | `RouteAPageManager`: allocation choice, PageRef/generation validation, descriptor visibility, durable invalidate-before-free, reclaim, drain/reset/init and descriptor-service behavior | `mr2_r5_availability_array_boundary_contract.md`: local structural `2/2`; R5 directed `21/21`; latest selected cross-stage `40/40` | PASS: descriptor image remains an external descriptor-service proxy, not an R5 local array proxy. |

The P3/S2 record counts above are their preserved stage-local directed evidence.
The latest selected 40-test cross-stage run additionally exercised the
current-source packed/hot/direct-pending, S2 four-consumer, M2, Full-KV and
dual-DUT contours. It is not a substitute for a physical memory test.

## Cross-boundary findings

1. **Array-only rule holds.** M2, P3, R5 and S2 array children receive only
   already-qualified parent accesses or observations. They do not add
   ready/valid admission paths that can backpressure R3 publication or R6
   authority.
2. **Control is retained and counted.** M2 grouped prepare/abort, credit,
   stale-safe reuse and publication gating; P3 materialization/durability;
   R5 descriptor/reclaim; and S2 READY/four-consumer/release all remain
   candidate DUT control. None may be removed with a future array proxy.
3. **Common versus differential treatment remains intact.** S2 common
   payload/GQA control remains a paired Full-KV/Route-A provision. M2, P3 and
   R5 are Route-A incremental, with unmeasured control/storage activity kept
   in the BOM rather than treated as zero cost.
4. **Existing functional limits are preserved.** Direct-pending remains the
   approved single-record contour; outer memory, descriptor service,
   functional partial provider and R4 numeric boundaries remain explicit
   external/reference scopes. MR-2 does not promote any of them to physical
   hardware evidence.

## Remaining work and prohibited inferences

MR-2 leaves the following open:

- selection and conformance of a future M2/P3/R5/S2 physical wrapper, including
  clock/reset ownership, port behavior, latency and macro/proxy evidence;
- external P3 payload backing and R5 descriptor-service/controller evidence;
- R4 numeric realization/cost evidence and outer-memory activity evidence;
- future integration-shell mux/state/interconnect cost;
- multi-record direct-pending coverage.

Accordingly, this review does **not** authorize synthesis, DC/CACTI, PPA, a
memory-macro choice, a controller, a complete attention engine, or any
performance conclusion. It also does not reopen pruning, admission, page size,
M2 organization, P3/S2 mapping, GQA legality, scheduler, R3 atomic
publication, R6 sole authority, or R2 ordering.

## Authorized successor boundary

The next bounded task is the **dual-DUT measurement-cut freeze**: record the
actual Full-KV and Route-A source lists, active owner chains, external ports,
reset/init obligations, common-versus-incremental accounting, and the
single-record direct-pending limit. It must not select a synthesis top or a
physical wrapper. A separate approval remains required before
realization-choice planning or any DC invocation.
