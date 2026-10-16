# MBR.1-A — Measurement-Realization Candidate Proposal

**Status:** Candidate proposal only; **pending separate human approval** on
2026-10-16.  This is an MBR.1 supplement, not a re-execution of MBR.1 and not
an SRP.3 realization decision.  It proposes the smallest measurement-oriented
control composition and evidence split that could later be implemented after
approval.  It makes no Chisel change, macro/library/clock choice, DC/CACTI
run, synthesis/PPA result, controller implementation, or attention-accelerator
claim.

## Scope, authority, and retained blockers

The proposal starts from MBR.0 human PASS and MBR.1's pending-review paired
Full-KV plan.  The [candidate manifest](measurement_realization_candidate_manifest.json)
is an exact, machine-checkable proposal for two **future** measurement DUTs:

```text
route_a_control_measurement_dut_candidate_v0
full_kv_control_measurement_dut_candidate_v0
```

Neither is `RouteAKVSubsystemTop`, and neither exists as a source top.  MBR.1
still needs human review; SRP.5's future-top implementation/synthesis blocker
also remains open.  Accordingly, this proposal can be approved only as a
bounded *implementation-preparation plan*.  A later approval must separately
authorize any Chisel integration, physical wrapper mapping, DC invocation,
CACTI invocation, or evidence result.

The fixed Route-A semantics remain untouched: original mask, admission,
64-token pages, M2 organization, P3/S2 mapping, legal four-member GQA,
scheduler/queue behavior, and the sole atomic publication point.  Functional
providers, fixtures, observers, replay scoreboards, and Python oracles remain
outside both DUTs.

## Candidate DUT compositions and common interfaces

The Route-A candidate retains the named owner-local source classes already
listed in MBR.0, grouped only for an eventual integration plan.  The grouping
does not assert that these existing classes are already connected in one
synthesizable top.

| Candidate | Control groups to be live after a separately approved integration | Required common/external interfaces | Explicit exclusions |
|---|---|---|---|
| `route_a_control_measurement_dut_candidate_v0` | Common lifecycle/hot; R2/R1 transaction and typed delivery; R3 materialization/publication; M2/P3/R5 control; common S2 plus packed ingress/sidecar control; R4 structural packet/commit control; Route-A status/control delta. | `core_mem_if_v1`; reset/init/fault/stale contract; R6 authority/terminal/retire carriers; S2 fill/READY/four-consumer/release; legal GQA mapping; outer source-partial and R4 numeric result/fault ports. | HBM/controller/PHY/CDC, array interiors, full attention/source PE, R4 arithmetic/partial-state realization, functional environments and all test-only infrastructure. |
| `full_kv_control_measurement_dut_candidate_v0` | Only a port-level equivalent of common lifecycle/hot, R2/R1, and common S2 payload/GQA control; no R3/M2/P3/R5, packed ingress/sidecar, or cross-source merge. | The same `core_mem_if_v1`, reset/init/fault/stale semantics, S2 lifecycle, legal GQA cardinality, and outer source-partial boundary/profile. | Route-A-only control, position sidecar, cross-source R4 merge, HBM/controller/PHY/CDC, array interiors, source PE, and test-only infrastructure. |

The Full-KV row is deliberately a *contract-level counterpart*, not an
instruction to reuse a Route-A class with packed signals tied off.  Common
provision becomes comparable only if a later implementation proves the same
interface, reset, identity/backpressure, S2 lifecycle, and GQA configuration.

### No-tie-off / no-optimization gate

Before any control synthesis, each included group must have an owner-to-owner
activation proof: its input is driven only by the named owner or external
contract port; its accepted output is consumed by the next named owner or
external contract port; reset/fault paths are represented; and no
`StructuralTieOff`, forced carrier, testbench producer, or dangling output
keeps it present.  This proof must cover the Route-A maturity-to-authority,
post-R6-demand-to-S2-READY, source-service-to-terminal/reclaim, and
reset/stale/fault contours.  Full-KV must demonstrate its own active
common-source contour rather than obtain equivalence by dead-code removal.

Failure to meet any obligation blocks DC preparation; retaining an inactive
block merely to report its area is not an acceptable workaround.

## Array-only proxy boundary and DC + CACTI preparation

The proposed method keeps control/peripherals in the future DC control
candidate and models only the named array interior through a separately
approved CACTI/macro proxy.  It selects no port count, banking, technology,
frequency, or CACTI parameter in this phase.

| Logical storage | Array-only future proxy boundary | Control that remains in measurement DUT | Evidence before a future DC + CACTI run |
|---|---|---|---|
| M2 | M2 state array behind `m2_op_req/op_rsp` and publish acknowledgement. | Mirrored update, member result/publish protocol, wrapper peripheral, and atomicity checks. | Accepted M2/publish plus queue/staging action map; semantic replacement regression. |
| P3 stage | One transient payload-stage and immutable sidecar storage interior. | Fill, exact-fragment completion, sidecar association, durable-write, pack-read, and release control. | Accepted fill/write/read/release map and P3 stale/fault regression. |
| R5 availability | Availability/generation state array only. | Allocation, generation, descriptor visibility/invalidate, reclaim/free, and peripheral muxing. | Accepted R5 allocation/reclaim event taxonomy and reuse regression. |
| R5 descriptor region | External descriptor-service/proxy, not a local array assumption. | Descriptor-maintenance request/control and invalidation ordering. | Exactly-one descriptor-maintenance/visibility/invalidate transaction taxonomy plus declared external service profile. |
| S2 payload | Common two-slot payload array only. | Fill association, READY, four consumer commits, release, and common wrapper peripheral. | Same Full-KV/Route-A wrapper contract and access map before common cancellation. |
| S2 sidecar | Route-A sidecar storage only. | Immutable association, endpoint/completion, READY gate, and peripheral control. | Accepted sidecar fill/read/release events and packed association regression. |

The prospective DC result, if separately approved, would cover only live
control plus explicit non-array wrapper/peripheral logic under one future
common constraint set.  The prospective CACTI result, if separately approved,
would cover only the chosen array proxy under its explicitly recorded capacity,
port, access, and technology assumptions.  They are not added to A4 proxy
coordinates or each other until unit, basis, and double-counting review is
complete.

## R4 numeric route without a full attention PE

R4 receives a separate candidate evidence route, named
`r4_merge_numeric_evidence_candidate_v0`.  Its permitted scope is only the
canonical ordered partial merge boundary: four binary32 partial interfaces,
the 2,080-B logical group partial-state placement choice, normalization/fault
contract, and input/output action accounting.  Source partials remain supplied
at the named outer interface; Q/K/V generation, dot products, score creation,
and a complete attention MAC array are excluded.

Before any numeric implementation or cost proxy, this route must pass the
existing finite binary32/RNE conformance and fault cases for canonical
`hot -> pending -> packed` order.  It must then provide a source/subset/partial
state action inventory whose fields come from owner-carried accepted packets.
If a required field is absent, the numeric activity remains unresolved rather
than inferred.  A later numeric candidate may be compared only against this
contract and must separately state whether its partial state is register,
array, or spill evidence.

## Future-top shell and differential ledger entry

The future integration shell is a mixed common/differential deferred envelope,
not a Route-A-only row.  A later top BOM must place each of the following in
the relevant DC control scope and in a separate area versus dynamic-energy
ledger:

| Shell category | Conditional common portion | Route-A differential portion |
|---|---|---|
| Interface adaptation | Identical `core_mem_if_v1` and demonstrated common lifecycle/S2 interfaces. | Packed, descriptor, sidecar, direct-pending, and R4 structural adapters. |
| Reset/init gating | Equivalent R1/R2/S2 reset/init behavior. | R3/M2/P3/R5/packed-path state and their reset/stale gates. |
| Protocol fanout/muxing | Demonstrated common R1/R2/S2 paths only. | Source-class selection and packed/direct/sidecar routing. |
| Delivery-context connectivity | A Full-KV context only after explicit owner/type mapping. | Packed/direct source-class context and associated status paths. |
| Storage-wrapper adapters | Identical common S2 payload adapter only. | M2/P3/R5/sidecar wrapper adapters and peripherals. |

The candidate must carry these shell items as explicit top-level BOM entries;
they may not be folded into a black box or cancelled before structural
equivalence is demonstrated.  Their area/static-power and activity/energy
evidence remain separate, and external service still remains nonzero.

## Review decision requested

The requested decision is narrow: approve or reject this candidate preparation
plan as the scope for a later, separately authorized Chisel/measurement-top
proposal.  Approval would not approve an implementation, DC, CACTI, a macro,
a numeric design, or any PPA/cost conclusion.  Rejection or a missing
owner-to-owner/array/R4/integration proof returns to this proposal without
changing frozen Route-A semantics.
