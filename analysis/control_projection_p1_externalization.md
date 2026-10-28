# Control-projection P1: typed functional-boundary externalization

**Date:** 2026-10-28  
**Scope:** bounded paired control-projection implementation; not a memory,
numeric, clock, DC, CACTI, or PPA decision.

## Implemented source projection

`FullKVControlProjection` and `RouteAControlProjection` are explicit,
parameterized subclasses of the selected measurement DUTs. Neither constructs
`RouteAKVSubsystemTop`, and neither supplies a parameter default.

The Route-A projection retains the production R3/R6, M2/P3/R5/S2 parent,
R2/R1, RMW, publication, credit, READY, terminal, reclaim, reset, stale, and
fault paths. It changes only the three approved functional-reference boundaries
below.

| Former functional child | Projection treatment | Actual typed boundary | Cost treatment |
| --- | --- | --- | --- |
| `RouteAFunctionalSidecarDeliveryAdapter` | Not instantiated. | `functional_sidecar_work_out`, `functional_sidecar_payload_release_out`, `functional_sidecar_registry_allocate_in`, `functional_sidecar_registry_allocation_ack_out`, and `functional_sidecar_read_issue_in`. | Route-A external sidecar delivery/integration adapter remains `unestimated_not_zero`; no sidecar data/control is tied off. |
| `RouteAFunctionalPartialProviderBoundary` | Not instantiated. | Existing hot/pending/packed partial-offer and fragment ports connect directly to `RouteASourceServicePacketAdapter`. | Outer attention-partial provider remains nonzero/unestimated; the removed child was a stateless ready/valid pass-through, not a cost cancellation. |
| `RouteAFunctionalR4ReferenceBoundary` | Historical test alias remains, but projection uses `RouteAR4ExternalProtocolAdapter`. | Existing accepted-packet, merge-work, result, and numeric-fault ports remain live. | Association/transport control stays inside Route-A; R4 arithmetic and partial state remain external, Route-A differential, and `unestimated_not_zero`. |

The external sidecar work path is owner-produced by the packed association
owner, and its response returns only through the existing delivery-context
allocation and packed-sidecar issue joins. It is neither a test fixture nor a
new sidecar, source, or authority owner.

## Evidence

Remote EDA elaboration completed with the bounded paired 9-bit functional
profile only:

```text
testOnly kvpress.routea.structural.ControlProjectionElaborationSpec
Tests: succeeded 1, failed 0
PROJECTION_P1_ELAB_EXIT=0
```

Log: `/home/yaz80/wz_project/chisel_projects/kvpress/logs/projection_p1_elaboration_rerun_20261028.log`.
The test proves both projection constructors elaborate and that Route-A
CHIRRTL includes the external R4 protocol adapter while excluding all three
former functional-reference children. It does **not** select a final parameter
profile or generate a DC input HDL artifact.

## Next gate

The next independent batch is one explicit bounded
`RouteASkeletonParameters` control-projection profile. It must not reuse
`RouteAR6Encoding.testOnlyAnchor`, must record every width/capacity choice, and
must preserve the already non-cancellable S2/common and external-cost
dispositions.
