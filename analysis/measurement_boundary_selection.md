# MBR.0 — Candidate Measurement-Boundary Selection

**Status:** Candidate selection completed and **human MBR.0 review passed** on
2026-10-16.  The PASS incorporates the documented cost-evidence refinements
(deferred future-top integration cost, explicit SRP.3/SRP.4 evidence routes,
and the array-versus-control split).  It authorizes **MBR.1 fairness-baseline
planning only**. This remains a read-only planning record for the
`top_future_synthesis_boundary` SRP.5 blocker. It selects neither a new RTL
top nor an implementation, memory macro, black box, numeric kernel, clock,
synthesis flow, or PPA result.

## Preconditions and authority

MBR.0 starts from the clean planning head `5c7600c`, functional-closure
decision `cf9f055`, the SRP.0--SRP.5 manifest, and the recovered A4.14.1
provenance/preflight record. The precondition audit passes at this limited
scope:

- SRP.5 authorizes a separately reviewed planning activity but leaves future
  top selection blocked.
- The 30 SRP partition records remain complete and uniquely mapped; their
  common, incremental, external, and verification classifications are reused
  rather than redefined here.
- The recovered A4.14.1 report makes its conditional proxy ledger inspectable,
  but does not remove omitted-cost, physical, or net-benefit limits.
- `RouteAKVSubsystemTop` remains unsuitable as the candidate DUT: it is a
  composition-only skeleton with named inactive carrier ties and named outer
  functional-reference boundaries. The complete C3/C4 functional path is a
  test-scope witness, not this top made active.

The machine-readable, exactly-once source/partition inventory is
[`measurement_boundary_bom.json`](measurement_boundary_bom.json).

## Selected candidate: MBR-C0 control/protocol measurement cut

The candidate measurement DUT is named **`route_a_measurement_control_cut`**.
It is a future paired Route-A/Full-KV measurement boundary, not a source file
or an assertion that a realizable top already exists. Its purpose is to retain
the owner-local control and data-movement protocol whose differential cost is
paper-relevant, while making every non-DUT function an explicit contract or
evidence obligation.

```text
candidate Route-A measurement DUT
  R6 lifecycle / shared control       R3 M2/P3 and publication control
  R5 allocation / reclaim             R2/R1 transaction-control boundary
  S2 common control + packed ingress  typed delivery/context control
  direct-pending control              R4 structural packet/merge control
  logical storage-wrapper ports       external core_mem_if_v1 port

outside candidate DUT
  frontend, predictor, and Q/K/V generation
  source-attention partial PE
  R4 numeric kernel and partial-state realization
  HBM controller / PHY / CDC / physical HBM
  functional memories, functional sidecar/R4 providers, fixtures, observers,
  Python oracles, and replay scoreboards
```

M2/P3/R5/S2 logical control is inside this cut only to the extent stated in
the existing contracts. Their physical storage is represented by a future
logical-wrapper port, not by the current Chisel `Mem` as an implicit macro.
R1 control ends at `core_mem_if_v1`; this does not select an HBM protocol or
make the controller free. R4 structural acceptance/ordering is inside; its
numeric result/fault producer remains outside until the separate SRP.3 numeric
choice review. The outer source-partial provider similarly remains external:
MBR.0 neither includes a complete attention PE nor treats its Route-A-specific
activity as zero cost.

## Required non-tied functional contours

The candidate is credible only if a later implementation creates legal,
observable owner-to-owner paths for all contours below. It must not keep logic
alive by importing a test-only provider or by forcing an internal carrier.

1. Retained maturity through R3 M2/P3, R2/R1 write/control, R5 private
   descriptor durability, the sole publication event, and R6 authority.
2. Post-R6 packed demand through R5 descriptor/lease association, typed
   R2/R1 payload-plus-sidecar transport, and S2 `READY`.
3. Hot, pending, and packed source-service packet delivery through four
   consumer commits, R4 structural acceptance, the external numeric boundary,
   R6 terminal, retirement, and R5/R6 reclaim.
4. Reset/init, stale/fault exclusion, and backpressure across the same named
   interfaces; an external response may delay or fault but cannot manufacture
   publication, authority, a partial, or a terminal.

The integration bill must include, rather than optimize away, a future
measurement-top's interface adaptation, reset/init gating, legal protocol
fanout/muxing, delivery-context connectivity, and logical-wrapper adapters.
Their membership and common-versus-differential classification remain explicit
MBR review items; no unimplemented integration state is zero cost. The BOM
marks these five integration categories as `deferred_unestimated`; MBR.1 must
assign each one a paired Full-KV common or Route-A differential responsibility
before any comparative accounting.

## Evidence references and array-versus-control split

For every logical storage, numeric, and external-service row, the BOM now
carries `cost_evidence_plan_ref`. These references deliberately point to the
existing SRP.3 requirement register and SRP.4 differential-cost plan (plus the
R4 or recovered A4.14.1 record where applicable); they are a route to later
evidence, not a selection of a macro, CACTI configuration, numeric kernel, or
external service model.

`inside_logical_control_wrapper_boundary` never means that an entire Chisel
module becomes a memory black box. Its split is fixed for MBR purposes:

| Logical item | Candidate control retained in DUT | Future array-only treatment |
|---|---|---|
| M2 | protocol, mirrored update, publication, and wrapper peripheral | M2 storage array may receive a separately reviewed black-box/macro proxy. |
| P3 stage | fill, sidecar association, durable-write, and release control | transient staging array may receive a separately reviewed proxy. |
| R5 availability | allocator, generation, invalidation, reclaim, and peripheral control | availability-state array may receive a separately reviewed proxy. |
| S2 payload | fill association, `READY`, four-consumer, release, and peripheral control | payload SRAM array may receive a separately reviewed proxy. |
| S2 sidecar | immutable association, endpoint, completion, and peripheral control | sidecar storage array may receive a separately reviewed proxy. |

Thus no future DC flow may black-box `RouteAS2GqaSourceWrapper`,
`RouteAM2P3Wrapper`, or `RouteAPageManager` wholesale merely because it
contains logical storage. The array boundary and the retained control must be
made explicit by the later one-record-at-a-time wrapper decision and its frozen
semantic regression.

## Cost and Full-KV treatment at MBR.0

MBR.0 supplies the comparison classification, not the MBR.1 baseline design:

| Class | MBR.0 treatment | Required later comparison rule |
|---|---|---|
| Common R1/R2/R6/hot/S2 provision | In paired boundary on both sides. | Do not charge whole provision to Route-A; measure or model only a justified activity/control delta. |
| Route-A R3/M2/P3/R5/packed ingress/direct/R4 structural control | Candidate Route-A logic. | Include its required control and integration cost once. |
| Logical storage and external memory | Wrapper/external boundary, never omitted. | Use only a separately approved macro/proxy/service evidence route with the same Full-KV basis. |
| R4 numeric and source partial | External pending evidence/choice. | Account for Route-A differential merge/partial activity without importing a full attention PE. |
| Test-only functions | Excluded. | May validate a replacement, never populate a DUT or cost row. |

The A4 payload and metadata service coordinates remain non-additive. Thus this
record does not infer latency, throughput, or energy from the candidate cut.

## MBR.0 result and review disposition

The candidate resolves the *ambiguity* of what must be described.  The human
MBR.0 review has accepted the BOM, exclusions, no-tie-off obligations, and the
three non-behavioral refinements recorded above.  This authorizes MBR.1's
paired Full-KV fairness planning.  It **does not** resolve SRP.5's future-top
blocker, select a future top, or authorize an MBR.2 realization/cost-method
choice.

The completed human MBR review confirmed all of the following:

- each of the 30 partition records occurs exactly once in the BOM;
- every candidate logic member has an owner-to-owner activation contour and
  frozen regression reference;
- all current functional/test-only providers are outside the DUT;
- common and differential activity have a stated Full-KV comparison basis;
- every logical storage/numeric/external item has a nonzero future evidence
  route; and
- the future integration shell's mux/state/interconnect is not silently
  excluded.

Failure of any later challenge to an item returns to MBR.0 correction or an
independent scope review.  The recorded PASS authorizes only MBR.1
fairness-baseline planning; it does not authorize RTL, wrapper selection,
synthesis, or PPA.
