# RTL3.9-A1 — R3 materialization and P3-ingress exclusion contract

**Status:** `complete_pre_activation_materialization_and_ingress_contract`.

RTL3.9-A1 turns the three Review-04 preconditions for RTL3.9-A into one
implementation contract, without yet activating a producer in the functional
top. It closes only the boundary between R3's immutable admitted-member facts
and the pre-existing C2 `P3PackReadWork` carrier:

```text
R3 immutable member + A0 pending binding
  -> R3-owned functional-baseline materializer
  -> P3PackReadWork / P3SidecarBind
  -> existing R2 -> R1 -> typed endpoint -> P3 ingress
```

It does not change the fixed **one retained member = one 8 x 64-B pack-read**
granularity, immutable member ordinal, R2 FIFO/eligibility/credit/arbitration
semantics, A0 binding, P3 completion/publication/authority, or any
physical-memory, timing, numeric, or PPA decision.

## Owner, field provenance, and conservative baseline

`route_a_m2_p3_wrapper` is the sole architecture owner of materializing a
work item from its stored immutable R3 membership ledger plus the A0
`PendingPayloadReadBinding`. The top is composition only and must not rebuild
a member association, synthesize an opaque pending handle, or create a second
work producer.

| `P3PackReadWork` field | Required provenance |
|---|---|
| `layer`, `stage_generation`, group tag, valid count | live R3 P3 stage |
| `member_ordinal`, `payload_ref`, logical position | immutable R3 member ledger |
| `transaction_identity`, `payload_handle_or_address`, `source_generation`, `destination_endpoint` | exact A0 binding recorded beside that ordinal |
| class/source/fragment count | frozen `pack_read` / pending / eight-fragment C2 semantics |
| `arrival_ordinal`, `candidate_id` | R3-local monotonically increasing materialization sequence, advanced exactly once when the work handshake is accepted |
| `eligibility_snapshot` | existing six named R2 predicates, offered only when all required logical predicates are true |

The R3-local sequence is a producer submission key already consumed by R2; it
is **not** an R2 winner decision, global queue index, new arbitration rule,
physical FIFO depth, service rate, or permanent member-scheduling policy.

The initial RTL3.9-A realization is deliberately a **one active member work
item per live P3 stage** baseline. It scans immutable member ordinals in
ascending order and holds a valid work item stable until accepted. This avoids
silently introducing response-reordering policy; it is not an architecture
requirement that prevents future multiple R1 reads. Any concurrency/reorder
change requires a separate R2/R3 association closure.

## Sidecar and ingress lease

For an accepted work item, R3 is also the sole producer of the matching
`P3SidecarBind`. Its layer, stage generation, ordinal, payload reference, and
logical position are copied only from the same immutable member association.
It is ready/valid stable under backpressure. A work item cannot become a P3
complete record from payload fragments alone: the matching sidecar handshake
remains required.

The materializer exports a logical **P3 pack-fill reservation** from accepted
work through matching payload terminal and sidecar acceptance. While the
reservation is active, pre-existing frontend hot-P3 payload and sidecar
ingresses must both remain invalid. This is an explicit functional environment
assumption, not a priority rule or a new hot/pack service schedule. The
existing `RouteAExclusiveP3PendingIngress` remains fail-closed: a simultaneous
hot and pack payload offer is an assertion failure, never a priority selection.
RTL3.9-A adds equivalent fail-closed exclusion for the sidecar pair.

## Fail-closed rules

- No work is produced without a present exact A0 binding, live matching R3
  stage, and immutable member ordinal below `group_valid_records`.
- A changed identity, payload handle, source generation, endpoint, member
  payload reference, stage generation, or sidecar coordinate invalidates the
  candidate; no R1 issue, P3 deposit, completion, publication, or authority
  transition may result.
- A fault terminal closes the active baseline work only as faulted; it does not
  advance to a new member or make the P3 group COMPLETE.
- Reset clears transient active/reservation/sequence state with existing P3
  transient state; old-generation work/sidecar/terminal input cannot match a
  new stage.
- Backpressure may delay legal work, sidecar, or response; it cannot alter an
  immutable association, reorder a baseline ordinal, duplicate work, or cause
  a Full-KV fallback.

## Explicit non-claims

RTL3.9-A1 neither activates the top-level work path nor makes `p3_packed_write`
live. Therefore it does not establish payload durability, descriptor
durability, `metadata_publish_commit`, pending-to-packed authority handoff,
direct-pending or S2 functional-source replacement, R4 numeric computation,
physical HBM/SRAM/controller realization, frequency, throughput, deadlock
freedom, area, energy, PPA, DC, model/GPU behavior, or complete LLM inference.

## No-model validation

```bash
.venv/bin/python tools/validate_rtl3_9_a1_r3_materialization_ingress_exclusion.py --help
.venv/bin/python tools/validate_rtl3_9_a1_r3_materialization_ingress_exclusion.py
.venv/bin/pytest -q tests/test_rtl3_9_a1_r3_materialization_ingress_exclusion.py
```

The A1 manifest hash-binds this contract, its machine-readable disposition, and
the no-model validator/test. RTL3.9-A may begin only from this contract and
must provide new directed Chisel coverage before claiming functional activation.
