# RTL3 completion cross-owner review 03

**Status:** `reviewed_no_pass_remaining_functional_source_replacement`.

This no-model review audits the current `RTL3.7-A/B/C` witness and the
production composition top against the intended RTL3 functional-realization
goal.  It is an evidence/provenance review; it changes no architecture rule,
owner, scheduler, admission decision, atomic publication point, or physical
realization choice.

## What the bounded witness now proves

The following testbench-only facts are closed in the current bounded retained
packed-source witness:

1. A successful R3 eight-fragment write is the object read through the C2 R1
   path (`RTL3.7-A`).
2. Each endpoint terminal reaches S2; only the final terminal releases the
   association, and that release precedes matching R6 retirement (`RTL3.7-B`).
3. C2 R1 initialization/drain and R2 payload/descriptor drain facts join their
   corresponding publication-wrapper facts before the unchanged R6 collector;
   the directed witness covers legal request backpressure, stale reset response
   suppression, and inherited packed-endpoint fail-closed fault behavior
   (`RTL3.7-C`).

These are valid bounded functional-transaction facts.  They do **not** turn a
testbench carrier into a production owner.

## Review result: RTL3 cannot PASS yet

The audit finds the following remaining blockers.

| ID | Current concrete boundary | Why it blocks RTL3 functional closure | Required future closure |
|---|---|---|---|
| R03-1 | `c2Demand`, `c2Publication`, `c2Descriptor`, and `c2Lease` are test-harness inputs to `RouteAPackedReadAssociationOwner`. | The association owner validates the facts, but no functional owner produces them from accepted R6/R3/R5/S2 state. | Name and bind the sole functional grant/association producer without changing the frozen scheduler. |
| R03-2 | `RouteARTL36cSidecarFixtureTransport` supplies sidecar completion from a static test fixture. | S2 READY still depends on test fixture transport rather than a functional sidecar source associated with the packed read. | Replace the fixture with a named functional sidecar response/binding path; preserve exact handle, count, identity, page, and generation checks. |
| R03-3 | The production top ties off all source-packet offers/value fragments. | Hot, direct-pending, and packed/S2 owners are not connected through the frozen query/position boundary to a functional partial producer. | Bind source-owner payload/sideband plus the external common-front-end query/position facts to the unique replaceable partial-provider boundary. |
| R03-4 | The production top ties off `r4_result_stub` and `r4_numeric_fault`; the same-instance witness instead replays static fixture packets and static terminal bytes. | The functional R4 oracle has not consumed dynamically produced partials in the composed instance. | Feed the accepted dynamic partial path to the functional R4 model and return exactly one matching success-or-fault terminal through existing R6 ownership. |
| R03-5 | The production top retains explicit `verification_*` ingress and several inert source/read/maintenance carriers. | The top remains a structural/control composition, not a functional source-to-terminal integration. | Remove or isolate each verification ingress from the functional closure path; any remaining external interface must name an allowed environment owner. |
| R03-6 | RTL3.7-A/B manifests hash the shared harness and living navigation files at their historical commits; their validators intentionally fail on the newer C snapshot. | This is a provenance/replay usability gap, not evidence of a transaction-semantic regression. | At the next review, make historical revision binding explicit or provide a current aggregate replay manifest; do not rewrite the historical manifests. |
| R03-7 | The current full same-instance positive path is packed-only and bounded. Reset/fault/stall evidence is component or packed-path scoped. | It does not yet demonstrate functional source coverage for hot, pending, all legal source subsets, or an end-to-end dynamic fault path. | Add directed functional-closure coverage after R03-1--R03-4 are closed; do not treat fixture substitution as coverage. |

Therefore `rtl3_functional_realization_complete = false`.  This is not a
physical/PPA failure: no HBM controller, SRAM macro, FP/exp pipeline, timing,
throughput, area, energy, or model/GPU claim is being evaluated here.

## RTL3 functional-closure rubric

RTL3 may PASS only when all of the following are true.

1. One same-instance retained transaction reaches
   `hot -> pending -> packed -> packed read -> S2 -> source service -> partial
   producer -> R4 -> R6 terminal -> retire -> durable reclaim -> retire_ack`
   without a testbench injection into an interior carrier.
2. Every cross-owner fact has one named producer and one frozen consumer;
   authority remains `hot/pending/packed == 1`, and only R3 publication moves
   pending authority to packed authority.
3. The allowed external environments are explicit: common frontend supplies
   query/position facts, and functional memory supplies only accepted R1
   transaction responses. Neither may create metadata authority, source
   schedule, delivery context, or R6 terminal outcome.
4. Hot, direct-pending, and packed/S2 provide K/V-plus-sideband only; the
   unique partial-provider boundary produces `(m,l,o)`, and R4 consumes those
   dynamic accepted partials in frozen `hot -> pending -> packed` order.
5. R4 returns exactly one matching success **or** numeric fault to R6; R6
   remains the group terminal and retirement owner.
6. Directed functional tests cover all nonempty legal source subsets, four
   GQA consumer completions/release, legal backpressure, stale/mismatch,
   reset epoch, and a dynamic fault path.  They must end in the prescribed
   success or exactly-one fault/reclaim outcome without Full-KV substitution.
7. A current aggregate provenance manifest hash-binds source, test, contract,
   and event-oracle evidence. Historical manifests remain immutable snapshots.

This rubric establishes only a functional Route-A subsystem boundary. It does
not require, choose, or imply a physical implementation.

## Does RTL3 mean complete LLM inference?

No. Even a future RTL3 PASS would mean that this **KV-cache Route-A
subsystem** can complete its declared functional transaction against explicit
frontend and memory environments. It would not implement or execute the full
decoder: tokenizer/sampling, embeddings, Q/K/V and output projections,
attention MAC array, RoPE hardware, MLP/MoE, residual/norm, full model
weights, predictor execution, or a host/runtime integration are outside this
closure.  Nor would it establish accuracy, token/s, HBM behavior, timing, or
PPA.

Full inference requires a later system integration that supplies those missing
LLM components and validates generated tokens against a model-level reference.
That is a different gate from RTL3 and is not authorized by this review.

## Disposition

The next planning action is a narrowly scoped **RTL3 functional-source
replacement plan** for R03-1 through R03-4, followed by dynamic full-path
coverage for R03-7.  R03-6 should be resolved as provenance hygiene alongside
that future review.  This review does not authorize physical/numeric
realization, profiling, optimization, synthesis, timing, PPA, or Gate-B.

## Validation

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265eSameInstanceWitnessSpec -- -z "retains event order"'
cd ../../..
.venv/bin/python tools/validate_rtl3_7c_drain_fault_stall_reset_scoreboard.py
.venv/bin/python tools/validate_rtl3_completion_cross_owner_review_03.py
.venv/bin/python -m pytest -q tests/test_rtl3_completion_cross_owner_review_03.py
```
