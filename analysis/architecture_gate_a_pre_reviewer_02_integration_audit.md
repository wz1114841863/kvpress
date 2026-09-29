# Gate-A pre-Reviewer-02 — R1–R6 cross-closure integration audit

## Scope and result

**Status:** `complete_pure_software_cross_closure_audit; ready_for_reviewer_02=true`.

This audit applies the user-provided Reviewer-02 preflight checklist to the
already selected R1–R6 contracts. It adds no architecture candidate, model/GPU
run, timing/throughput/PPA DSE, RTL, or change to frozen Route-A semantics.
It checks only whether individually closed contracts compose into one finite
interface boundary.

Three integration ambiguities were found and closed by this audit:

1. R5 HBM descriptor maintenance now has one explicit path:
   `R5 desc_maint_write -> R2 maintenance FIFO -> R1 core_mem_if_v1 -> external adapter`.
   It is exactly one 64-B R1 write fragment, but remains outside the frozen
   payload-read rotation.
2. `metadata_publish_commit` is named as the one architectural publication
   event. Compatibility method spellings in pure-software references delegate
   to that same event; they are not alternate publication mechanisms.
3. R4 `numeric_fault` has an executable R6 consumer: after all four GQA
   updates commit, it creates the one outward attention terminal fault, without
   retry, fallback, mask/admission change, or early source release.

The cross-closure reference executes the shared publication nesting directly:
R3 owns the accepted outer commit, while R5 descriptor visibility and the A2
lifecycle authority action occur inside that one event. The test rejects the
interpretation that descriptor durability alone could create packed visibility.

## Cross-closure matrix

| Required integration property | Owner / single definition | Audit result |
|---|---|---|
| Request acceptance and ready-low nonmutation | R1 accepts only at ready; R2 advances read rotation only on R1 acceptance, with separate FIFO descriptor maintenance | PASS |
| Two S2 destinations retain identity/generation ownership | A2/A3 S2 contract; R2 carries a concrete destination rather than collapsing the `s2_fill` class into one slot | PASS |
| Every HBM-resident object has one path | Pending and packed payload/sidecar use R1; R5 descriptor lines use R2 then the same R1 write boundary | PASS |
| P3 payload and position-sidecar accounting remain separate | R3 preserves 32-KiB payload envelope and separate 8-B/record binding | PASS |
| Authority has one linearization point | `metadata_publish_commit`: R1 payload durable + P3 complete + staged M2 + durable descriptor prerequisite; only then pending -> packed and descriptor visibility | PASS |
| Packed-read eligibility | R2 requires metadata published; descriptor durability or payload durability alone is insufficient | PASS |
| Fault behavior | R1/R3/R5 fail closed; R4 fault terminates outward in R6; no retry, Full-KV fallback, mask, or admission mutation | PASS |
| Credit/ownership losslessness | R2 eligibility carries frozen FIFO/ownership/credit predicates; stalled paths delay only | PASS |
| Page retirement and reuse | R5 requires full quiescence, durable invalidation, then generation advance/bitmap free; R6 global drain includes R1/R2/R3/R4/R5/S2/direct | PASS |
| Reset stale-state exclusion | R1 suppresses pre-reset replies before init; R3/R5/R6 reset only local reachability and require init; raw HBM bytes do not become reachable | PASS |
| Numeric conformance oracle | R4 has one binary32 packet/order/reference contract; canonical absent identity is legal and is not normalized | PASS |
| Generic top-level port boundary | R6 carries post-decision disposition only; score/threshold/predictor are excluded. Qwen widths/window are anchor-profile bindings. | PASS |

## Explicitly retained implementation choices

The following remain legitimate later RTL/Gate-B choices, not unresolved
architecture decisions: FSM encoding, pipeline registers, exp implementation,
internal precision beyond the R4 boundary, SRAM compiler/banking/floorplan,
HBM burst/channel mapping, physical controller timing, common overlap schedule,
and PPA. The following are no longer left to an RTL implementer: descriptor
memory path, publication linearization, ready-low state behavior, descriptor
invalidation-before-free, numeric-fault consumer, reset stale-state exclusion,
and retirement drain membership.

## Executable evidence boundary

The focused no-model regression is:

```text
.venv/bin/python -m pytest -q \
  tests/test_route_a_architecture_reference.py \
  tests/test_route_a_core_memory_reference.py \
  tests/test_route_a_arbitration_reference.py \
  tests/test_route_a_m2_p3_reference.py \
  tests/test_route_a_page_manager_reference.py \
  tests/test_route_a_merge_numeric_reference.py \
  tests/test_route_a_lifecycle_adapter_reference.py \
  tests/test_route_a_cross_closure_reference.py
```

It is pure-software architecture-contract evidence only. It makes no
model/GPU, timing, throughput, controller, PPA, RTL-correctness, or new-A4-DSE
claim. Hash binding and exact result are in
`analysis/architecture_gate_a_pre_reviewer_02_provenance_freeze.md`.
