# Gate-A2 — executable transaction/reference harness

## Scope

Gate-A2 turns the pre-RTL architecture assertions into a pure-software
transaction reference.  The implementation is
`kvpress/route_a_architecture_reference.py`; its directed tests are
`tests/test_route_a_architecture_reference.py`.  Neither imports a model,
executes Qwen forward, reads a trace, instantiates a clock, or estimates
latency, bandwidth, area, or energy.

The reference is a future RTL-scoreboard/golden-reference seed, not RTL.
It models only abstract event ordering, ownership, mathematical source-partial
semantics, and terminal outcomes.

## Covered executable invariants

| Architecture assertion | Harness rule |
|---|---|
| `no_partial_group_visible` | Metadata members stage privately; publication rejects an incomplete group. |
| `page_write_commit` is not residency transfer | Packed payload becomes durable at write commit, while authority remains pending until metadata atomic publication. |
| `release_event -> all_gqa_consumers_partial_updates_committed` | An S2 slot cannot release before all four consumer commits. |
| Canonical multi-source merge | `hot -> pending -> packed` is explicit; absent sources use `(-inf, 0, 0)` and an entirely empty logical source set fails. |
| Normalization | The mathematical reference rejects normalization when `l <= 0`; it makes no finite-precision or source-reordering equivalence claim. |
| Exactly one terminal request outcome | A live request transitions once to success or fault; the strict profile never reallocates IDs. |
| Stale response safety | A response for a terminal, mismatched-generation, or non-owner request is rejected without changing a reused S2 slot. |
| One authoritative residency | Each retained live token is exactly `hot`, `pending`, or `packed`; P3, S2, and direct transport are transient and never authoritative. |
| Maturity disposition | Hot tokens either DROP with no pending/packed authority or admit exactly once to pending before any packed handoff. |
| Gate-A1 direct pending endpoint | Ordered pending records stay pending-authoritative, require FIFO ordinals, and cannot close before all four consumers commit. |
| Semantic backpressure | Request acceptance, response delivery, consumer completion, metadata publication, credit availability/release can stall only by leaving state unchanged. |
| Logical credit losslessness | An optional finite logical admission-credit count delays admission and returns credit only with atomic pending-to-packed publication; it is not a physical FIFO depth. |
| Optional finite ID reuse | `epoch_reuse` permits a terminal ID's later incarnation only with a different explicit epoch; delayed old-incarnation responses are stale. |

## Deliberate non-models

The harness does not choose request widths, physical beat/burst format,
controller policy, port count, timing, numeric datapath format, exp unit,
partial-softmax implementation, macro organization, or overlap.  The merge is
only the architecture's mathematical functional reference.  There is no model
or GPU execution, cycle/timing/throughput claim, PPA claim, RTL correctness
claim, or new A4 DSE.  The strict non-reuse request-ID profile remains the
safe baseline; `epoch_reuse` is an executable refinement only, leaving width
and outstanding-operation bounds for Gate-A3.
