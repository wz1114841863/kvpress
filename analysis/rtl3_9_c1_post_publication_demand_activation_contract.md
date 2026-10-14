# RTL3.9-C1 — post-publication packed-demand activation

**Status:** `complete_functional_post_publication_demand_activation`.

## Purpose and fixed boundary

C1 proves the first owner-correct activation step after C0's all-member R6
acceptance gate.  In one test-only composed witness, an actual R6-accepted
source-completion plan, R3's read-only post-R6 page-ready observation, the
matching R5-visible descriptor, and the S2 lease join at the existing packed
activation binder.  The existing packed-read association owner receives those
four facts and holds one exact registry-allocation request.

```text
R6 accepted packed-present source-completion plan
  + R3 post-R6 all-member page-ready observation
  + exact R5 descriptor grant
  + exact S2 fill lease
    -> existing binder authorization/demand
    -> existing packed-read association owner
    -> one held registry allocation request
```

The witness uses `RouteARTL265a2PackReadPublicationHarness`, extending the B3
functional instance without modifying `RouteAKVSubsystemTop`.  It therefore
checks the same R3/R5/R6 directions and existing binder/association owners,
but is not a claim that C2 transport has been activated in the production top.

## Ownership and provenance

- **R3** remains the only immutable member/ordinal ledger owner and emits the
  read-only post-R6 page-ready observation only after its real
  `authority_transition_out.fire` handshakes have been accepted by R6.
- **R6** remains only the lifecycle authority acceptor.  Its accepted
  `source_completion_plan_copy_out` is forked through the existing plan fork;
  C1 adds neither an ordinal table nor a second authority owner.
- **R5** alone returns the visible descriptor grant, and **S2** alone grants
  the fill lease.  The test harness composes their existing interfaces; it
  does not manufacture descriptor visibility or a lease.
- The existing packed activation binder verifies the C0 member/summary
  association before its descriptor query and demand.  The existing packed
  association owner alone forms the registry allocation request from exact
  demand, authorization, descriptor, and lease carriers.
- The top's pre-existing production direction remains composition-only:
  binder outputs connect to the association owner directly.  The C1 test
  witness does not make a top, testbench, or R6 a scheduler/authority owner.

## Directed evidence and fail-closed stop point

The directed no-model test drives the existing B3 publication sequence, feeds
one lifecycle-owned packed-present source plan, and observes exactly one
post-R6 page-ready fire, exactly one binder demand fire, and one active
association.  The held registry allocation is checked as an S2 packed-fill
target with the exact request identity, page, slot, and sidecar requirement.
With registry allocation acknowledgement held low, the request remains valid;
no subsequent carrier is injected or accepted.

C1 intentionally stops before the registry acknowledgement.  It does **not**
activate a typed R2/R1 read, functional-memory response, payload/sidecar
deposit, S2 `READY`, source service, consumer partial commit, outer R4
boundary, R6 terminal, retirement, or R5/R6 reclaim.  Those are C2--C4 work.
Thus C1 does not create a read scheduler, a memory/controller realization, or
a second allocation/authority path.

Before C0 completion, on malformed/duplicate member coverage, wrong plan or
descriptor/lease identity, ready-low, or reset, existing owners remain
fail-closed: no demand may form.  The C1 test proves the positive association
and held-allocation boundary only; C2 must add directed stale/mismatch, fault,
and reset read-delivery cases before any S2 `READY` claim.

## Validation

```bash
.venv/bin/python tools/validate_rtl3_9_c1_post_publication_demand_activation.py --help
.venv/bin/python tools/validate_rtl3_9_c1_post_publication_demand_activation.py
.venv/bin/pytest -q tests/test_rtl3_9_c1_post_publication_demand_activation.py
cd hardware/route_a/chisel
sbt -batch 'Test / compile'
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec -- -z "activates exactly one post-R6 packed demand"'
```

The static preflight and its Python test pass.  The selected Chisel/Verilator
witness passed on 2026-10-14 with one test, zero failures, and zero errors
(first build: 661.094 s).  This is functional control/dataflow evidence only.

## Evidence boundary

C1 establishes neither an HBM controller, SRAM macro, physical descriptor or
memory implementation, attention MAC, numeric/FP/exp pipeline, clock/CDC,
timing, bandwidth, throughput, area, energy, PPA, model/GPU result, complete
LLM inference engine, nor new DSE result.  It does not reopen KVzap pruning,
admission, 64-token pages, M2 organization, P3/S2 mapping, GQA legality,
queue/scheduler semantics, or the single atomic-publication boundary.
