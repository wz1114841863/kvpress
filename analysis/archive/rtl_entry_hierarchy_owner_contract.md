# Gate-RTL0.1 — RTL hierarchy and unique-owner closure

## Status and boundary

**Status:** `complete_non_implementational_hierarchy_owner_closure; gate_rtl0_ports_pending`.

This is the first Gate-RTL0 planning closure.  It freezes only a reviewable
Route-A DUT hierarchy, the unique owner of each mutable architectural resource,
and the permitted cross-owner handoffs.  It creates no SystemVerilog, no
synthesizable module skeleton, no FSM, no numeric datapath, no clock period,
no physical port/macro/controller selection, no PPA/timing/throughput claim,
and no new A4 DSE.  It does not alter pruning, admission, FIFO, scheduler,
GQA, direct-pending, or one-atomic-commit semantics.

The machine-readable companion is
`analysis/rtl_entry_interface_manifest.json`, currently in
`hierarchy_owner_frozen_ports_pending` state.  It is intentionally a
hierarchy/owner manifest in this step: the complete per-signal interface
records and their Markdown consistency comparison are Gate-RTL0.2 work.

## Frozen hierarchy

```text
environment endpoints (not DUT children)
  frontend_post_decision_adapter
  external_memory_adapter
  runtime_session_manager
                 |
                 v
route_a_kv_subsystem_top                 integration shell; no duplicate state
  |- route_a_lifecycle_adapter           Route-A lifecycle/terminal/retirement
  |- route_a_hot_source_path             common hot residency
  |- route_a_s2_gqa_source_wrapper       common S2 generation/GQA release
  |- route_a_direct_pending_endpoint_v1  Route-A pending delivery
  |- route_a_core_side_arbiter           common R2 dependency/grant order
  |- route_a_core_mem_if_v1              common R1 external-memory boundary
  |- route_a_m2_p3_wrapper               Route-A M2/P3 state
  |- route_a_page_manager                Route-A descriptor/allocator/reclaim
  `- route_a_merge_boundary              Route-A replaceable R4 packet boundary
```

`route_a_kv_subsystem_top` composes children only.  It must not mirror a child
owner's mutable state, decide a child-local terminal action, or introduce a
second memory, publication, descriptor, source-release, or retirement path.
The listed module names are interface-manifest identities, not an RTL file
layout, language choice, pipeline partition, or selected implementation.

## Unique-owner matrix

| Resource / decision | Sole owner | Required handoff / prohibition |
|---|---|---|
| Top-level composition | `route_a_kv_subsystem_top` | Composition only; no duplicate protocol state. |
| Hot/pending/packed authority, dispatch membership, exactly-one attention terminal association | `route_a_lifecycle_adapter` | Only immutable maturity disposition and the one `metadata_publish_commit` may change authority; R4 reports `numeric_fault`, but R6 consumes it. |
| Hot-source residency | `route_a_hot_source_path` | Lifecycle supplies arrival/maturity intent; no other owner mutates hot residency. |
| S2 identity/generation/READY plus four-consumer release | `route_a_s2_gqa_source_wrapper` | A stale response cannot change a reused slot; no source releases before all four committed updates. |
| Direct pending-delivery association | `route_a_direct_pending_endpoint_v1` | Direct path only; it cannot alter S2 ownership, lifecycle authority, or terminal outcome. |
| FIFO/dependency/credit predicates and grant cursor | `route_a_core_side_arbiter` | R2 alone advances a grant on R1 acceptance; ready-low is nonmutating. |
| R1 transaction identity, fragments, terminal status, local reset epoch | `route_a_core_mem_if_v1` | Every payload, sidecar, and descriptor HBM-resident object uses this sole DUT-to-memory path. |
| M2 private group and P3 stage/generation/sidecar state | `route_a_m2_p3_wrapper` | R1 commit is payload-durable only; R3 cannot publish descriptor visibility, transfer lifecycle authority, or release P3 independently. |
| R4 observable partial/result packet state and `numeric_fault` production | `route_a_merge_boundary` | Replaceable stub boundary only; cannot release a source, mutate authority, or emit outward terminal status itself. |
| Stream descriptor, allocator availability, page generation, descriptor preparation/visibility, per-page reclaim | `route_a_page_manager` | Descriptor visibility is only within `metadata_publish_commit`; page reuse follows durable invalidation and quiescence. |
| Retirement acceptance and one global drain acknowledgement | `route_a_lifecycle_adapter` | R6 owns the complete global predicate; R5 performs per-page reclaim only after it holds. |

The environment endpoints are not Route-A owners: the frontend supplies only
post-decision events, the external adapter owns native controller/CDC behavior,
and the runtime session manager requests logical retirement.  Their assumptions
and DUT guarantees are deferred to the Gate-RTL0 assertion matrix; this step
does not assign external behavior to the DUT.

## Required cross-owner boundaries

1. R2 is the sole immediate producer of accepted R1 requests.  R5 descriptor
   maintenance uses its own R2 FIFO client but reaches external memory through
   the same `route_a_core_mem_if_v1` path as payload/sidecar.
2. R1 successful packed write commit makes payload durable only.  R3 owns the
   prerequisite state, R5 owns descriptor visibility, and the lifecycle
   adapter owns authority; all three change only in the one R3-outer
   `metadata_publish_commit` event.
3. `route_a_s2_gqa_source_wrapper` and
   `route_a_direct_pending_endpoint_v1` own independent transport state.  A
   stale pending response may not mutate S2 state; neither transport owner
   becomes authoritative residency.
4. `route_a_merge_boundary` receives only committed source partials in the
   frozen `hot -> pending -> packed` order.  It exposes a result or
   `numeric_fault` to the lifecycle adapter after GQA completion; it has no
   Full-KV fallback or retry authority.
5. Retirement is accepted by the lifecycle adapter, which gathers R1/R2/R3/R5
   /S2/direct/merge drain acknowledgements.  R5's descriptor invalidation and
   generation advance remain per-page operations after that global predicate.

## Gate-RTL0.1 checks and next boundary

`tools/validate_rtl_entry_interface_manifest.py` validates the JSON module
inventory, external-versus-DUT split, direct-child hierarchy, required unique
owners, declared connections, and the required later signal-record field
schema.  It runs only standard-library JSON validation and supports `--help`.
The accompanying tests deliberately inject a duplicate owner and an invalid
module inventory.

Gate-RTL0.2 must populate the per-signal records for the frozen hierarchy and
provide the promised Markdown-to-manifest consistency check.  It may not
rename/reassign these owners to solve a later port/FSM convenience issue.  The
subsequent assertion/assumption matrix will bind the listed ownership rules to
properties, directed tests, random scenarios, environment assumptions, and
coverage bins.
