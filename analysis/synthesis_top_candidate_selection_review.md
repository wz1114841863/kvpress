# Synthesis-top candidate selection review

**Review date:** 2026-10-25
**Source-cut anchor:** `analysis/measurement_dut_cut_freeze_20261025.json` at
`fc06fdbc763325e55638f6cc164cf251b424a2f2`
**Disposition:** `conditional_paired_control_top_candidates_selected`

## Decision

The selected future synthesis-top candidates are **projections** of the two
frozen measurement DUTs, not the present Chisel modules compiled unchanged:

| Candidate ID | Projection source | Selection result |
| --- | --- | --- |
| `route_a_synthesis_control_top_candidate_v1` | `RouteAMeasurementDut` | Selected as the Route-A control candidate, conditional on externalizing named functional references, replacing only array interiors with wrappers, and retaining all listed parent control. |
| `full_kv_synthesis_control_top_candidate_v1` | `FullKVMeasurementDut` | Selected as the Full-KV control candidate, conditional on resolving the current hot/S2/lifecycle structural mismatch before any common-cost cancellation or DC comparison. |

`RouteAKVSubsystemTop` is expressly **not** a candidate: it is the historical
composition-only skeleton with inactive carrier ties. The functional witness
and the two measurement DUTs do not make that skeleton an eligible synthesis
top.

This selection chooses no memory macro, wrapper implementation, physical port
count, latency, library, clock, frequency, controller, numeric implementation,
DC run, CACTI run, or PPA result.

## Candidate membership

### Route-A control candidate

The candidate retains the current Route-A parent control projected from
`RouteAMeasurementDut`:

- R6 lifecycle/status and the legal hot, packed, terminal, retirement and
  reclaim owner chains;
- R3 admission/materialization/publication; M2 production control/metadata
  bridge; P3 staging protocol; R5 allocation/reclaim control; and all
  parent-owned array boundary peripherals;
- R2/R1, delivery-context, typed routing, read/write ingress, endpoint and
  packed/direct transport control;
- S2 fill/READY/four-consumer/release control plus packed sidecar/ingress
  control; and
- R4 structural packet/commit/merge control only.

The following current measurement-DUT classes are **not copied as functional
implementation** into the candidate: `RouteAFunctionalSidecarDeliveryAdapter`,
`RouteAFunctionalPartialProviderBoundary`, and
`RouteAFunctionalR4ReferenceBoundary`. Their named ports remain external
contracts until a separate approved sidecar/partial/numeric realization choice.
Likewise, P3 pending backing, R5 descriptor service and `core_mem_if_v1`
remain explicit external services.

M2/P3/R5/S2 parent controls remain candidate RTL. Only their already isolated
logical array interiors may be replaced by future wrappers. No candidate may
black-box `RouteAM2P3Wrapper`, `RouteAM2ProductionControlOwner`,
`RouteAPageManager`, or `RouteAS2GqaSourceWrapper` wholesale.

Direct-pending membership is limited to the frozen MR-1B single-record
`valid_count = 1` contour. The candidate has no multi-record claim.

### Full-KV control candidate

The candidate retains the baseline-local `FullKVReadProducer`,
`FullKVDeliveryContextBridge`, `FullKVS2ReadEndpoint`,
`FullKVS2GqaSourceWrapper`, `FullKVTerminalRetireAdapter`, and
`FullKVStatusCollector`, together with the actual shared
`RouteACoreSideArbiter`, `RouteACoreMemIfV1`,
`RouteADeliveryContextRegistry`, and `RouteATypedDeliveryRouter`.

Its functional outer contracts remain `full_kv_read_work_in`, the matching
`core_mem_if_v1` service, `source_ready_out`, the four-consumer commit boundary,
and terminal/retire interfaces. It contains no R3/M2/P3/R5, packed sidecar,
direct-pending, R4 cross-source merge, or Route-A publication/authority
control. The previously uninitialized Route-A-only direct-cancel sideband is
explicitly inactive and cannot become a baseline source owner.

## Paired-common decision table

| Provision | Actual source observation | Candidate accounting rule before DC |
| --- | --- | --- |
| R2/R1, delivery context and typed routing | Both DUTs instantiate the same arbiter, R1, registry and router classes and expose `core_mem_if_v1`. | Candidate-common, but pair only under an identical chosen interface/reset/configuration. |
| S2 payload/GQA | Both have read-to-READY and four-consumer/release responsibilities, but use different Full-KV and Route-A S2 classes. | `paired_common_pending_equivalence`; no structural or cost cancellation yet. |
| Lifecycle/status | Both enforce init/stale/fault/terminal/retire behavior, but Full-KV uses baseline-local terminal/status classes while Route-A uses R6 lifecycle/status control. | `paired_common_pending_equivalence`; document a same-contract wrapper mapping or retain a non-cancelled difference. |
| Hot residency | `RouteAHotSourcePath` exists only in the current Route-A DUT. | **Pre-DC fairness condition:** either realize a legal Full-KV counterpart or obtain an explicit approved common/differential allocation. It must not disappear from the comparison. |
| R3/M2/P3/R5, packed/direct/sidecar, R4 structural control | Route-A only. | Route-A incremental; retain in candidate and keep all unresolved cost rows nonzero. |

Thus the candidates define a fair comparison *target*, not a declaration that
the currently different Chisel module hierarchies already cancel in a netlist.

## Required future top interfaces

Both candidates must retain the named `core_mem_if_v1` reset/init/fault/stale
contract. Route-A additionally retains lifecycle, source-plan, pending
descriptor/binding, hot/pending functional backing, partial provider, R4
result/fault, direct-pending transport, terminal and retire ports at the
appropriate named boundary. Full-KV retains baseline read work, source-ready,
four-consumer commit, terminal and retire ports. A later integration top may
adapt these ports, but must account for the adaptation rather than tie them
off or infer owner facts.

The five MBR.1 shell categories are mandatory in the future top BOM:
interface adaptation, reset/init gating, protocol fanout/muxing,
delivery-context connectivity, and logical-storage-wrapper adapters. Their
current classification remains mixed common/differential and
`deferred_unestimated`.

## Pre-DC closure conditions

Before either candidate may become an actual DC input, all of the following
must be approved and evidenced:

1. **Common-equivalence resolution.** Resolve the hot and non-identical
   S2/lifecycle/status treatment. A common label alone is insufficient.
2. **Array-only wrapper contracts.** Define semantic wrapper ports,
   clock/reset ownership, accepted access/response behavior, and replacement
   regression for M2, P3 stage, R5 availability, common S2 payload and S2
   sidecar. Descriptor and pending backing remain external-service decisions.
3. **External/reference replacement boundaries.** Specify how the functional
   sidecar, partial-provider and R4-reference classes are excluded/replaced at
   top level, and retain nonzero external/numeric cost responsibility.
4. **Integration-shell implementation plan.** Name the actual future top
   source, filelist, reset/clock ownership and the five deferred shell
   categories without silently optimizing any active contour away.
5. **Successor source freeze and regressions.** Any source or wrapper change
   requires a successor hash inventory plus the relevant owner, reset/stale,
   publication, READY, terminal and reclaim regressions.

Failure of any condition stops DC preparation for the affected candidate; it
does not justify synthesizing a smaller tied-off contour or charging absent
logic as zero.

## Next authorized activity

This review authorizes only the next realization-preparation subtask:
**array-only wrapper-interface planning and common-equivalence disposition**.
It does not authorize Chisel changes, physical macro selection, DC/CACTI, or PPA.
The paired candidates remain conditional until that subtask is reviewed.
