# RTL3.0 — replacement-owner manifest and stop-for-review map

**Status:** `implemented_planning_stop_for_review`.

RTL3.0 is a no-model, no-RTL planning closure.  It records how the remaining
RTL2 verification conveniences may be replaced by named functional boundaries;
it does not activate one, change an existing owner, or authorize RTL3.1
behavior.  The machine-readable authority is
[`rtl3_0_replacement_owner_manifest.json`](rtl3_0_replacement_owner_manifest.json).

## Frozen interpretation

The following invariants remain unchanged:

- R3/M2 is the sole metadata-publication and pending-to-packed authority
  boundary; R5 remains the packed-page/descriptor owner.
- R2/R1 retain typed delivery, request, response, FIFO, credit, and terminal
  ownership.  An external functional memory environment is not a second
  payload, metadata, or residency authority.
- Hot, direct-pending, and S2 owners provide payload, position/sideband,
  identity, and generation facts.  They do **not** produce attention
  `(m, l, o)` merely by owning K/V storage.
- R4's observable binary32 packet, canonical `hot -> pending -> packed`
  order, normalization guard, and numeric-fault rule remain frozen.  RTL3.0
  selects neither an exp implementation nor internal precision, storage,
  pipeline, service rate, or latency.

## Replacement map

| Current convenience | Planned replacement boundary | RTL3.0 result |
|---|---|---|
| Manually driven external R1 responses / page contents | `testbench_route_a_functional_memory_environment` at the existing `core_mem_if_v1` external interface | Planned for RTL3.1; non-authoritative functional environment only. |
| Verification packed-S2 service/work and sidecar ingress | A future packed-read association from accepted R6 request, R5 page fact, R3 publication fact, and owner-local S2 slot/generation | **Stop for review.** No current owner may construct this cross-owner association without an explicit replacement contract. |
| Structural hot/direct/packed packet offers and value fragments | `route_a_functional_attention_partial_provider` between source payload/sideband owners and the frozen packet/R4 boundary | **Stop for review.** Query association plus position/RoPE semantics are not yet represented by an authorized interface. |
| R4 result stub / numeric-fault stimulus | `route_a_functional_r4_merge_provider` at the already frozen R4 boundary | Planned for RTL3.3--RTL3.4; oracle-consistent functional model only. |

## Required stop-for-review resolution

Neither stop may be bypassed by a testbench default or a temporary top-level
producer.

1. **Packed-read association:** specify the sole future association owner and
   the accepted fields that join R6 request identity, R5 `PageRef` and
   generation, R3 publication/authority observation, S2 slot/generation, and
   R2 delivery context.  The solution may not select or alter a scheduler.
2. **Partial-producer inputs:** specify the common-front-end query association
   and position/RoPE sideband contract before a provider can calculate an
   `(m, l, o)` partial.  The solution may not turn a hot/direct/S2 storage
   owner into a MAC owner.  If attention MAC remains outside RTL scope, the
   provider must be an explicitly replaceable functional PE/reference boundary.

The stop conditions do not invalidate RTL2.6.  They prevent RTL3 from silently
expanding the subsystem scope while replacing its verification conveniences.

## Evidence boundary

This is a pure-software planning and provenance record.  It makes no claim
about production-top integration, a real HBM controller, SRAM/HBM macros,
numeric RTL correctness, final FP/exp implementation, timing, throughput,
area, energy, PPA, model/GPU execution, or a new A4 DSE.
