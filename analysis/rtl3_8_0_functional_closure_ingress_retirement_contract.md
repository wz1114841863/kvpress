# RTL3.8.0 — functional-closure ingress retirement contract

**Status:** `complete_planning_ingress_retirement_freeze_pre_rtl3_8_activation`.

RTL3.8.0 converts Review-03's remaining testbench ingress findings into one
machine-readable retirement map.  It is planning/provenance only: no Chisel
module, top-level connection, scheduler, authority transition, admission
decision, page format, atomic-publication boundary, memory realization, or
numeric implementation is changed.

The target is a Route-A **functional subsystem closure**, not complete LLM
inference and not physical/numeric/PPA closure.  An allowed external
environment may interact only through a named boundary below; it may not write
an interior Route-A carrier.

## Inherited non-negotiable rules

- R3/M2 remains the sole metadata-publication and pending-to-packed authority
  boundary.  R5 remains the sole page/descriptor owner.
- R2/R1 remains the sole typed delivery/request/response/FIFO/credit owner.
  A functional memory environment is non-authoritative.
- Hot, direct-pending, and S2 own K/V, logical-position sideband, source
  identity, and generation; none produces `(m,l,o)` merely by storage
  ownership.
- The partial-provider boundary of RTL3.5-A remains the sole partial producer;
  its source order is `hot -> pending -> packed` and its query/position/RoPE
  facts are supplied only by the named common frontend boundary.
- R4/R6 retains exact success XOR numeric-fault and group terminal ownership.
  No replacement environment may create a terminal, source release, reclaim,
  or Full-KV fallback.

## Retirement map

The labels *retire* and *isolate* are intentional.  *Retire* means a future
functional-closure elaboration must not expose or consume the carrier as an
interior testbench ingress.  *Isolate* means an existing structural-top port
may remain for older tests, but it must be absent from the future functional
closure path and its synthesis target.

| ID | Current test-only/interior boundary | Future sole producer or allowed environment | Frozen consumer | Disposition | Required condition before retirement |
|---|---|---|---|---|---|
| I0 | `c2Demand` (`PackedSourceDemand`) | `route_a_packed_read_activation_binder`, derived only from an accepted R6 packed-source plan | `RouteAPackedReadAssociationOwner` | retire | Binder requires exact identity, selected packed source, and no live conflicting association. |
| I1 | `c2Publication` (`PublicationReadAuthorization`) and `verificationAssociation` publication coupling | same activation binder, from R3's already accepted publication/authority observation | association owner / S2 service path | retire | Publication is visible and authoritative before authorization; binder cannot create a second publication or authority transition. |
| I2 | `c2Descriptor` (`DescriptorLocationGrant`) | same activation binder, by observing the existing R5 readable descriptor fact | association owner | retire | Exact `PageRef`, generation, payload handle, sidecar handle/count, and valid-record count match the published page. |
| I3 | `c2Lease` (`S2FillLease`) | same activation binder, receiving an owner-local lease from S2 allocation state | association owner | retire | Slot/generation is live, unique, and may not be inferred from page ID or a test default. |
| I4 | `RouteARTL36cSidecarFixtureTransport` plus `verification_s2_sidecar_fragment_in` / `verification_s2_sidecar_complete_in` | `route_a_functional_sidecar_delivery_adapter`, fed only by an accepted association descriptor and functional R1/R2 sidecar response boundary | S2 sidecar ingress | retire | Exact sidecar handle/count, identity, page, generation, and accepted filling lease match; payload traffic may not infer sidecar completion. |
| I5 | top `verification_p3_pack_read_work_in`, `verification_s2_service_req_in`, and `verification_packed_s2_read_work_in` | existing R3/R5/R6 facts through the activation binder and existing typed-delivery path | existing R2/R1/S2 owners | isolate then retire from functional top | No new scheduler/arbitration policy; binder may only materialize an already selected work fact. |
| I6 | top `verification_direct_pending_open_in` and `verification_direct_pending_read_work_in` | existing R6 direct-pending plan plus direct-pending owner-local state | existing direct endpoint / R2-R1 typed path | isolate | Deferred to the source-service coverage closure; it must not be conflated with packed C2 activation. |
| I7 | static RTL3.6-B packet and terminal fixture, `packedOffer`, `packedFragment`, `resultStub`, and `numericFault` harness ingress | named dynamic functional partial-provider and functional R4 reference environments, each at the frozen RTL3.5-A / RTL3.4-B boundary | source-packet adapter and merge boundary | retire | Dynamic accepted query/source lease and accepted R4 packet/work are the only inputs; static packet/result replay is prohibited. |
| I8 | structural top `r4_result_stub` / `r4_numeric_fault` tie-offs and source offer/value-fragment tie-offs | future replaceable partial/R4 boundary instances or explicit synthesis blackboxes | existing source-packet adapter / merge boundary | isolate | A functional-closure top cannot contain the tie-off on an exercised source path. A later control-only synthesis target may retain declared blackboxes, not fixture carriers. |

`route_a_packed_read_activation_binder` and
`route_a_functional_sidecar_delivery_adapter` are **contract names**, not yet
implemented Chisel modules.  They name responsibility only and select no
physical memory, request kind, port count, bank, clock, or service schedule.

## Allowed outer environments

Only the following outer boundaries may remain outside a future functional
closure instance.

| Boundary | May provide | Must not provide |
|---|---|---|
| `common_frontend_attention_context_provider` | Accepted lifecycle/query association, already-RoPE-applied query handle, query position, and frozen GQA association | Source choice, metadata authority, delivery context, source release, R4 result, retirement, or reclaim. |
| `route_a_functional_memory_environment` at `core_mem_if_v1` | Init acknowledgement and response/terminal behavior for accepted R1 requests, including legal stall/fault behavior | Admission, descriptor selection, page generation, sidecar inference, source schedule, or residency authority. |
| `route_a_functional_attention_partial_provider` | Dynamic partial packets after exact accepted query/source leases | Source selection, source release, authority change, R4 result, or outward terminal. |
| `route_a_functional_r4_merge_provider` | Dynamic success XOR numeric-fault only from accepted R4 packets and accepted R6 merge work | Packet acceptance, source selection, consumer commit, group terminal ownership, retirement, or reclaim. |

These are functional interface roles only.  They do not authorize a live
Python/Chisel production bridge, an attention-MAC/RoPE/FP implementation, a
HBM controller, an SRAM macro, or a PPA claim.

## Ordered activation plan

1. **RTL3.8.1 — packed activation binding.** Implement and test I0--I3 as one
   exact association producer.  It observes accepted R6/R3/R5/S2 facts and
   produces no scheduler decision, descriptor mutation, or authority event.
2. **RTL3.8.2 — functional sidecar delivery.** Replace I4 using only the
   accepted descriptor/lease and existing typed R1/R2 response path.  S2 may
   become READY only after both payload and sidecar completion.
3. **RTL3.8.3 — source payload/partial boundary activation.** Isolate I5/I6
   from the functional top and bind dynamic hot/direct/S2 payload-sideband
   observations to the frozen frontend/partial-provider boundary.  This is not
   a numeric PE implementation.
4. **RTL3.8.4 — dynamic R4 functional reference activation.** Replace I7/I8
   with dynamic, accepted-packet/work-driven functional reference behavior.
   It remains non-synthesizable/reference-only until a separate numeric gate.
5. **RTL3.8.5 — full-path closure coverage.** Exercise all legal nonempty
   source subsets, four GQA completions, success/fault, legal stall,
   stale/mismatch, and reset in one production-shaped instance.  Then create
   an aggregate current provenance manifest without rewriting historical
   RTL3.7 manifests.

No later step may begin solely because an earlier interface elaborates.  Its
contract must pass directed positive/negative no-model checks first.

## Functional-closure exit rule

RTL3.8 may request final RTL3 review only when every I0--I8 item is either
retired from the exercised functional path or explicitly retained as one of
the four allowed outer environments, and the Review-03 seven-point rubric is
covered by a current aggregate evidence record.  The future disposition is
still only:

```text
pass_for_control_plane_synthesis_entry
!= physical-memory/numeric/PPA completion
!= complete LLM inference
```

## Evidence boundary

This is a pure-software contract/provenance freeze.  It makes no model/GPU,
numeric RTL correctness, controller/macro, cycle/timing/throughput/deadlock,
area/energy/PPA, DC, or new A4-DSE claim.  It does not reopen pruning,
admission, page size, M2 organization, queue/scheduler semantics, P3 mapping,
S2 count, GQA legality, atomic commit, or Route-A/Route-B choice.

## Validation

```bash
.venv/bin/python tools/validate_rtl3_8_0_functional_closure_ingress_retirement.py
.venv/bin/python -m pytest -q tests/test_rtl3_8_0_functional_closure_ingress_retirement.py
```
