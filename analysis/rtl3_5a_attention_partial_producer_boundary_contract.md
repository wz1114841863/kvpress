# RTL3.5-A — query/position/RoPE and attention-partial-producer boundary

**Status:** `complete_interface_owner_freeze_pre_functional_partial_provider`.

RTL3.5-A closes the second RTL3.0 stop-for-review item: the query/position/RoPE
association that must exist before any Route-A source can produce an attention
partial.  It freezes an interface and ownership boundary only.  It introduces
no Chisel module, payload store, attention MAC, RoPE arithmetic, exp/FP
implementation, timing model, or production-top activation.

```text
common frontend attention-context provider (outside Route-A)
  -> exact query association / already-RoPE-applied Q / query position
source owners (hot | direct-pending | S2)
  -> exact K/V payload access / per-record logical positions / source instance
route_a_functional_attention_partial_provider (replaceable PE/reference boundary)
  -> existing SourceServicePartialOffer + SourceServiceValueFragment
route_a_merge_boundary -> R4 functional merge provider -> R6
```

The machine-readable companion is
[`rtl3_5a_attention_partial_producer_boundary_manifest.json`](rtl3_5a_attention_partial_producer_boundary_manifest.json).

## Sole owners and boundary direction

| Resource or fact | Sole owner / producer | Consumer | Non-negotiable rule |
|---|---|---|---|
| Q projection, query RoPE application, query vector availability | `common_frontend_attention_context_provider` (environment endpoint) | partial producer | Outside Route-A.  The partial producer receives an already-RoPE-applied query; it does not own Q projection, RoPE tables, or rotation arithmetic. |
| Query position and Qwen GQA association | same frontend provider | partial producer | Immutable per `(transaction_identity, layer, kv_head, consumer_id)` work item. |
| K/V payload, source-local position sequence, source identity/generation | exact selected hot, direct-pending, or S2 owner | partial producer | A storage owner exports no `(m,l,o)` and no R4 header/fragment merely by owning K/V. |
| Partial computation and packet production | `route_a_functional_attention_partial_provider` | existing source packet adapter / R4 boundary | The only RTL3.5 producer of a present `SourceServicePartialOffer` and its eight value fragments.  It is a replaceable functional PE/reference boundary, not a selected hardware PE. |
| Packet acceptance, consumer commit, source release, merge/result terminal | existing source packet adapter, R4, source owners, and R6 | unchanged | The partial producer cannot release a source, change authority, manufacture an R4 result, or create an outward terminal. |

`common_frontend_attention_context_provider` is a new named environment
endpoint, not a child of `route_a_kv_subsystem_top`.  It may not be silently
replaced by a testbench default after the future provider is activated.

## Frozen association record

One future `AttentionPartialWork` is accepted only when all fields below match
exactly.  The record is a logical/functional interface; opaque payload handles
and position iteration do not select wires, ports, SRAMs, DMA, or a physical
data layout.

| Field | Producer | Rule |
|---|---|---|
| `transaction_identity = (request_id, incarnation)` | R6-accepted source plan and frontend | Exact reusable identity; request ID alone is illegal. |
| `layer`, `kv_head`, `consumer_id` | source plan / frontend | Qwen anchor values are `0..35`, `0..7`, and `0..3`; generalized widths remain parameters. |
| `query_head` | frontend | Qwen anchor mapping is exactly `query_head = 4 * kv_head + consumer_id`; a non-anchor design must provide an explicit mapping parameter rather than reuse this formula. |
| `query_position` | frontend | One immutable logical decode/query position, associated with the exact query vector. |
| `query_payload_handle` | frontend | Opaque handle to the already-RoPE-applied query vector; it is not a new Route-A payload residency or a selected transport width. |
| `rope_semantics_profile` | frontend | `qwen3_rope_applied_at_q_and_k_creation_v1` for the anchor.  It states semantic placement only, not a RoPE-table/arithmetic realization. |
| `attention_semantics_profile` | frontend | `qwen3_gqa_scaled_causal_attention_v1`; scale/mask semantics are supplied by the common frontend contract, not invented by a storage owner. |
| `source_instance = (kind, coordinate, generation)` | selected source owner | Exact current hot/direct/S2 instance, matching the already accepted source plan and eventual R4 sideband. |
| `source_payload_handle` | selected source owner | Opaque access to the exact K/V records.  K has already received the same frozen RoPE semantic at its own logical position; the partial producer must not rotate K again. |
| `source_logical_positions` | selected source owner | Exact ordered per-record positions, including the packed sidecar mapping; count/order must match the supplied K/V record sequence. |

The source-position sequence is a semantic input to causal visibility and
association validation.  It does not authorize a new sidecar transport,
position cache, or positional encoding store.  Under the anchor profile each
selected key position must be causally visible to `query_position`; the
provider rejects an impossible/mismatched association before acceptance rather
than repairing it, substituting Full-KV, or altering a mask/admission result.

## Packet and failure rules

For each accepted source work item and each `consumer_id`, the partial provider
may emit exactly one present frozen R4 packet through the existing
`SourceServicePartialOffer` plus eight ordered
`SourceServiceValueFragment`s.  The packet retains the exact transaction
identity and source instance, uses the already frozen source ordinal and
consumer ID, and remains subject to R4's canonical `hot -> pending -> packed`
merge order.  The provider cannot re-order sources or claim that different
finite-precision orders are bitwise equivalent.

An excluded source has no provider work item and no data-bearing packet; the
already frozen R4 functional provider alone supplies its absent identity from
the accepted R6 source-presence mask.  A selected source with missing query,
identity, layer/KV-head/GQA mapping, position sequence, RoPE profile, source
generation, or causal-visibility association is **not accepted**.  It emits no
partial, no consumer commit, no source release, no result, and no authority
transition.  This is a fail-closed interface violation under the environment
assumption of well-formed immutable work; it is not reclassified as an R4
`numeric_fault` and creates no retry/fallback policy.

Once a work item is accepted, ready-low may delay only the existing packet
offers/fragments.  It may not change the query association, source positions,
source generation, source selection, GQA consumer mapping, mask, admission,
or packet content.  Existing R4/R6 exactly-once terminal and four-consumer
release rules remain unchanged.

## Explicit scope boundary

This freeze makes `route_a_functional_attention_partial_provider` the sole
future attention-partial owner in RTL3.  Its initial realization may be a
functional PE/reference model.  Before replacing it with numerical RTL, a
separate realization gate must select and verify any Q/K/V representation,
attention-MAC array, RoPE arithmetic/tables, scale/mask implementation, exp
unit, precision, buffering, pipeline, clocking, service rate, or PPA model.

RTL3.5-A does not activate the provider, remove the existing testbench source
packet ingress, bind a production top, implement source payload reads, choose
a source schedule, change S2/direct/hot ownership, alter R3 publication or R5
reclaim, change pruning/admission/atomic commit, or make a model/GPU,
throughput, timing, area, energy, or PPA claim.  RTL3.5-B may implement only a
separately reviewed functional provider that consumes this exact boundary.

## No-model validation

```bash
.venv/bin/python tools/validate_rtl3_5a_attention_partial_producer_boundary.py
.venv/bin/python -m pytest -q tests/test_rtl3_5a_attention_partial_producer_boundary_manifest.py
```

The checks validate provenance hashes and the frozen owner/association rules.
They do not run a model, GPU, numerical attention, or Chisel simulation.
