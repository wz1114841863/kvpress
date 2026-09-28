# Route-A architecture specification — pre-RTL interface boundary

## 1. Status and scope

**Status:** review draft, 2026-09-28.  A4.14.1 conditionally authorizes this
architecture specification; it does not authorize RTL, Chisel, PDK/PPA,
physical SRAM macros, a native HBM controller, or measured performance claims.

This specification preserves the original per-layer/per-KV-head KVzap mask.
It does not train or modify the predictor, restructure the mask, prune before
attention, or revise A4.8--A4.11 admission, queue, execution, scheduler,
FIFO, ownership, credit, or atomic-commit semantics.

**Frozen** denotes a semantic/accounting contract already bound by A4 evidence.
**Parameter** denotes a value an implementation must state and validate before
use.  **Unestimated** denotes a module that carries no area, energy, cycle,
bandwidth, latency, or PPA conclusion in this document.

The Gate-A0 local provenance declaration for this document is
`analysis/architecture_gate_a0_provenance_freeze.md`.  It records the accepted
input identities, the functional reference source-order lock, and any pending
byte-level report verification without promoting a missing artifact to a pass.

## 2. Provenance and evidence boundary

The report hashes below are accepted input identities, not hashes of this
Markdown file.  Ignored experiment directories are not all present locally;
implementation review must re-hash the reports and their materialized inputs
before accepting them.

| Interface evidence | Accepted artifact SHA-256 | Retained contract |
|---|---|---|
| Exact-token external lifecycle and maturity | A4.11.2b `57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3` | [A4.11.2b](route_a4112b_external_storage_lifecycle_contract.md) |
| HA8-wide queue/credit contract | A4.10 `_04` `97f9cec11c8ffff95ce8405d303f35ddf76ea2c4078512f0d98d38e6ec0ec9e4` | [A4.12.0](route_a4120_metadata_interface_inventory_contract.md) |
| Metadata inventory, macro envelope, service replay | A4.12.0 `e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534`; A4.12.1 `d5f0f436251cb607b884e3102788caf2e775e398542686ad9ca88b58a96e3f7d`; A4.12.2 `e2578b08b852036b500ed9ce8dbba8ea9c55ec45b75a6eea02a3893473feb415` | [A4.12.1](route_a4121_metadata_macro_envelope_contract.md), [A4.12.2](route_a4122_metadata_cycle_energy_contract.md) |
| P3 payload organization | A4.13.1 `ba6ec8291d213317e953dd0ac3a050524cf10a327705c6390fe652531a98950c` | [A4.13.1](route_a4131_payload_organization_contract.md) |
| Fair payload realization and source/merge actions | A4.13.3 `fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1`; A4.13.4 `2390958f801c63b7a54e725106b9e75bd36de8950b733ab9bac9d4ac2ee94597` | [A4.13.3](route_a4133_packed_kv_hbm_realization_contract.md), [A4.13.4](route_a4134_page_source_reuse_interface_contract.md) |
| Target payload-service proxy | A4.13.5 `8a3c07255d8e6382807701b437935c89207b60065df5d671dacad0b8cfb7a502` | [A4.13.5](route_a4135_target_payload_service_cost_contract.md), `hardware/route_a/payload/a4135_target_profiles.json` |
| Workload-aligned M2 binding | A4.14.0 `3d3cc52eade09c20ed305159d78b7bc43673db0072a4d1b9bc211bd061ae8034` | [A4.14.0](route_a4140_workload_aligned_metadata_cost_contract.md) |
| Accounted-ledger disposition | A4.14.1 `0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb` | [A4.14.1](route_a4141_accounted_net_benefit_ledger_contract.md) |

Software lifecycle quantities are direct observations; token/span lowering is
deterministic conversion; service coordinates are declared models; CACTI is a
public proxy.  None is a physical ready event, port count, clock, controller
command, or layout result.

## 3. Common infrastructure and Route-A increment

| Class | Module/function | Boundary |
|---|---|---|
| Common GQA infrastructure | **S2**, two 32-KiB ping-pong source-page buffers and four-consumer GQA fanout | Needed by fair Full-KV and Route-A paths.  Fixed proxy provision is reported once; path-specific accesses remain per path. |
| Common front end | Transformer Q/K/V and fixed KVzap predictor | Outside incremental subsystem scope. |
| Route-A increment | M2, admission/packing, the A4.13.1 P3 mapping (pending-HBM backing plus `p3_payload_stage_page`), packed-page manager, position sidecar, packed cold list, multi-source merge control | Required by compacted cold-data lifecycle. |
| Route-A fixed public proxy | **M2** replicated/duplicated control storage | Complete A4 public-CACTI proxy candidate, not a selected production macro/port design. |
| Route-A unphysicalized provision | `p3_payload_stage_page` physical realization, sidecar/page management, and merge state | Interface/capacity only; no physical macro, area, or dynamic energy. |

S2 is never a Route-A-only incremental cost.  Sidecar, page management, M2,
P3, and merge costs must be evaluated as Route-A incremental costs.

## 4. Top-level microarchitecture boundary

The graph below is an **architectural dependency graph**.  It defines data
ownership and control dependencies, not a wire protocol, port count, clocked
pipeline, controller schedule, or latency.

```text
                                Route-A increment
  mask / maturity  ---------->  Admission + M2 control  ---+--- metadata publication
                                    |                       |
  mature K/V from hot source  ------+                       v
                                    +--> pending-HBM backing
                                           |             |
                                  packing read           +-- attention read
                                           v                         |
                                   P3 payload-stage page       pending delivery realization
                                           |                    (Gate-A choice: direct or S2)
                                           v                         |
                                    Page manager                  +--+
                                           |                          |
                              packed-page write / commit             |
                                           v                          v
                                    packed cold HBM ----------> S2 payload slots
                                                                      |
 Common infrastructure:                                               v
 Full-KV causal pages also use S2                         common source mux / GQA fanout
 hot local source ----------------------------------------------->    |
 pending delivery ------------------------------------------------>    +--> four GQA consumers
 packed S2 source ------------------------------------------------>    |
                                                               partial states
                                                                    |
                                                      Route-A multi-source merge control
                                                                    |
                                                               attention output
```

M2 may authorize and publish the metadata state required by a payload action,
but the graph does not assert a physical M2-to-HBM control path.  S2 payload
slots and the four-head GQA fanout are distinct common-infrastructure modules:
S2 is a page-source buffer, while the mux/fanout accepts hot, pending, and
packed sources.  The packed sidecar, packed-page manager, P3, M2, and
multi-source merge control are Route-A incremental.  `pending_delivery_realization`
is a Gate-A blocking choice; no existing A4 evidence selects
direct delivery, reuse of S2, or a separate pending buffer.  Every graph edge
becomes a concrete interface only after the corresponding Gate-A parameter and
dependency contract are frozen.

## 5. Frozen lifecycle

```text
predict/mask at creation -> hot window (128) -> maturity
  -> DROP, or admitted pending append -> sealed packed cold pages
  -> hot / pending / packed source traversal -> online merge
```

The anchor is Qwen3-8B with all 36 layers, all 8 KV heads, the original replay
mask, page size 64, admission budget 512, and eight generated tokens.  This
coverage is not a portability claim.  The trace observes scalar maturity,
pending state, packed-page state, and residual only; it establishes ordering,
not a clocked hardware schedule.

## 6. Packed page and position sidecar

Every packed cold page belongs to one `(layer, kv_head)` append-only stream.

| Property | Status | Interface meaning |
|---|---|---|
| `page_tokens = 64` | frozen | At most 64 compact append-ordered retained entries/page. |
| K+V = 512 B/retained token | frozen for Qwen anchor | 32,768-B payload page. |
| position sidecar = 8 B/entry | frozen logical interface | Separate 512-B sidecar on a full packed page. |
| `valid_count` | frozen semantic field | `0 <= valid_count <= 64`; only tail page is partial. |
| ownership | frozen | One page has one layer/KV-head stream owner. |

The sidecar maps compact rank to logical position.  It is neither a selected
physical PTE/address/latch representation nor free storage; replacement needs
separate semantic and cost validation.

`payload_page_id`, `next_page_id` or page-list index, payload address/handle,
generation/valid tag, bank/address mapping, and physical address widths are
required **parameters**.  `tail_page_id`, `page_count`, `valid_count`, and
`total_valid_tokens` remain semantic descriptor state, not a prescribed header
layout.  These payload fields are outside the A4.9.1 59/50 raw and 64/64
padded metadata accounting and must not be backfilled into those widths.

### Normative logical descriptors

The following is a logical state schema.  It establishes required state, not
bit widths, a SRAM layout, a linked-list implementation, or an allocator ABI.
Every field marked `PARAMETER` requires a frozen implementation value at Gate
A.

```text
PackedPageDescriptor {
    owner_layer, owner_kv_head,       // semantic owner; field widths PARAMETER
    payload_page_id, payload_handle,  // PARAMETER
    position_sidecar_handle,          // PARAMETER; separate from payload capacity
    next_ref,                         // PARAMETER: next-page ID or page-list reference
    valid_count,                      // frozen semantic range: 0..64
    generation_or_validity_tag,       // PARAMETER
    valid                             // frozen semantic state
}

StreamDescriptor {
    owner_layer, owner_kv_head,       // semantic owner; field widths PARAMETER
    first_page_ref, tail_page_ref,    // PARAMETER reference encoding
    page_count, total_valid_tokens    // frozen semantic counters
}
```

An allocated packed page has exactly one stream owner.  A stale reference must
not designate a reallocated live page; an implementation may enforce this with
a generation, a validity discipline, or another Gate-A-frozen equivalent.

## 7. Admission, P3, and page manager

The semantic admission input is:

```text
layer, kv_head, logical_position, keep/drop, K, V,
tail-page state, and applicable logical credit/ownership state
```

Its output is either `DROP` or an append record containing compact payload
rank, sidecar entry, updated tail state, and metadata transaction-group
members.  It may not reorder records, change a mask, or make partial group
state externally visible.

The A4.13.1 **P3 mapping** must distinguish three different concepts:

| Concept | Architectural authority |
|---|---|
| Pending logical state | M2/lifecycle semantic state: pending membership, credit, ownership, and append order. |
| Pending payload backing | The P3 mapping retains P1's lossless **pending HBM backing**.  It is the authoritative pending K/V payload source until packed-page publication. |
| `p3_payload_stage_page` capacity | One 64-token payload staging page per layer.  It is a transient, non-authoritative copy used to form packed HBM-page writes; it may not create a second logical residency. |

Thus a retained token that matures is written to pending HBM backing, may be
read into its layer's `p3_payload_stage_page` for admission, and is written to
packed HBM before its packed page may be published.  This is the existing P3 declared
mapping, not a newly measured transaction schedule.  The page manager must
preserve the corresponding ownership and publication dependency.

For the 36-layer anchor the frozen `p3_payload_stage_page` capacity envelope is:

```text
36 * 64 * 512 B = 1,179,648 B
```

This is not 36 chosen SRAM macros or a physical 1,179,648-B macro.  Staging
macro organization, access schedule, physical location, and energy remain
unestimated.  The page manager semantically owns free-page allocation,
per-stream list/tail updates, append page creation, and release; allocator
timing, queue topology, reclamation, address translation, and physical page
count remain parameters.

## 8. M2 metadata/control interface

M2 logically uses two 1RW `head_control` replicas and one 1RW `span_owner`
store per head-affine bank.  A head read selects a free replica; head
write/RMW updates both replicas atomically in the declared model; span access
uses its separate proxy.

The frozen requirement is eight head-affine banks with at most two read-class,
two write-class, and two commit-coupled RMW issues per **abstract service
opportunity**.  It is not a 2R2W SRAM, physical RMW-lane count, latency, or
throughput promise.  Every A4.12 macro was a 1RW public 0.032-um CACTI proxy.

The frozen A4.10 resource names `local32/shared256/staging512` are called
`metadata_control_local32`, `metadata_control_shared256`, and
`metadata_control_staging512` in this specification to distinguish them from
the P3 payload stage.  They mean local capacity 32/bank, shared capacity
256/layer, and metadata/control staging capacity 512/layer under the lossless
logical queue/credit contract.  They are not 36-layer physical replication;
simultaneous physical layer concurrency, FIFO depths, topology, and access
timing are not established.

## 9. S2 source buffer, memory transport, GQA multicast, and merge

Each of the two logical S2 slots has 32,768-B **payload** storage.  For a
Route-A packed page it additionally requires 512-B position-sidecar storage,
plus slot identity, generation/validity, and consumer-completion state.  The
512-B sidecar is not included in the 32-KiB payload-buffer capacity.  The
payload buffer remains common Full-KV/Route-A infrastructure; Route-A sidecar
and its management are incremental and unestimated.

### Abstract memory transport contract

The following is an architectural interface requirement, not a selected
AXI/HBM protocol, native transaction format, controller, address width, or
outstanding-request limit:

```text
page_read_req {
    request_id, source_kind, payload_handle_or_address, valid_count,
    expected_generation_or_validity, destination_endpoint
}
page_read_rsp {
    request_id, destination_endpoint, observed_generation_or_validity,
    beat_index, payload_or_sidecar_data, last, status
}
page_write_req { request_id, destination_payload_handle_or_address, valid_count }
page_write_data { request_id, beat_index, payload_or_sidecar_data, last }
page_write_commit { request_id, resulting_page_reference, status }
```

`destination_endpoint` is either an S2 slot or a direct-source endpoint.  A
packed-page read targets S2.  `pending_delivery_realization` is the Gate-A
choice that assigns a pending-HBM read to an S2 slot or a direct-source
endpoint; no other pending payload path is implied.  For an S2-targeted read,
`READY` is legal only after a matching successful response has delivered all
required payload beats and, for packed Route-A, the sidecar.  For a direct
pending delivery, Gate A must define the corresponding source-mux deliverable
event without treating it as an S2 `READY` event.  For a write, packed-page
metadata publication is legal only after a matching successful
`page_write_commit` and the frozen metadata transaction-group requirements.
`request_id`, endpoint encoding, handle/address encoding, generation encoding,
maximum outstanding operations, response ordering, and transport backpressure
are Gate-A parameters.  `status` reserves a fault boundary; retry, timeout,
ECC, error recovery, and fallback policy are not selected here and may not
change the mask or admission semantics.

### Request lifetime and stale-response contract

An accepted `request_id` becomes live and remains live until exactly one
terminal outcome: a successful terminal read response, a terminal fault status,
or (for a write) one `page_write_commit`.  Every response beat must belong to
exactly one live request.  A live `request_id` may not be reallocated.  A slot
targeted by a live read request cannot be reassigned.  The slot's fill
association is the live request identity together with its expected
generation/validity; a late or stale response that does not match that
association cannot make a reused slot `READY`.  A write commit uniquely
terminates its matching live write request.  Gate A must additionally freeze
whether terminal ID reuse relies on a transport no-late-response guarantee or
on an explicit request epoch carried by every response.

These are request-lifetime invariants, not a selection of request-ID width,
response ordering, transport retry, or controller microarchitecture.

### Abstract S2 slot state contract

```text
EMPTY -> FILL_REQUESTED -> FILLING -> READY -> CONSUMING
     -> WAIT_GQA_COMPLETIONS --release_event--> EMPTY
```

`FILL_REQUESTED` means a read request has been accepted by the abstract
transport; `FILLING` has not yet received its complete matching response.
`READY` carries a complete source and initialized consumer-completion state.
`WAIT_GQA_COMPLETIONS` holds ownership until all consumer partial updates have
committed.  `release_event` is an architectural event, not a persistent slot
state; it occurs only when the release predicate holds and returns the slot to
`EMPTY`.  With `READY(A)` and `FILLING(B)`, A may be consumed.  If A is
complete and B is not `READY`, the next packed attention source stalls; it may
not assume infinite bandwidth, drop work, substitute Full-KV, or change the
mask.  These are semantic consequences, not selected cycle counts, SRAM ports,
or HBM latency.

Full-KV follows the same `FILL -> READY -> four-consumer -> partial update ->
release_event` lifecycle for causal pages but has no position sidecar or cross-source
merge.  A 256-B internal beat is frozen accounting only: 128 payload beats and
two sidecar beats/page; it is not an HBM transaction or burst.

Hot, pending, and packed sources feed the same GQA fanout.  Every source path
must emit one `source_deliverable_event` before fanout consumer tracking is
initialized.  For an S2 source, that event is `READY`; for a direct pending
source, it is the Gate-A-defined direct-delivery completion.  At that event,
the Qwen anchor initializes `consumer_pending[3:0] = 4'b1111` for the exact
four verified query-head members.  Consumer `i` clears its bit only when that
consumer's partial-state update is committed; reading the source payload alone
is not completion.  `release_event` is legal only when `consumer_pending == 0`
and all four dependent updates have committed.  A generalized design must
parameterize the group cardinality; it must not silently reuse the four-bit
anchor state for a different GQA mapping.

Each group has four logical `(max, exp_sum, weighted-V)` partial states,
totaling `4 * (128 + 2) * 4 = 2,080 B` for the A4.13.4 FP32 interface.  This
is pipeline-local state, not a chosen RF/SRAM/spill or merge implementation.
Spilling it requires explicit reads, writes, capacity, and ordering costs.

For two source partials `A = (m_a, l_a, o_a)` and `B = (m_b, l_b, o_b)`, the
functional online-softmax merge contract is:

```text
m = max(m_a, m_b)
l = exp(m_a - m) * l_a + exp(m_b - m) * l_b
o = exp(m_a - m) * o_a + exp(m_b - m) * o_b
attention_output = o / l
```

This equation defines the mathematical reference, not an adder pipeline or
numeric format.  The current accepted functional reference iterates the
canonical source order `hot -> pending -> packed`; Gate A must hash-bind that
source-code reference and may not substitute another order without separate
finite-precision validation.  No implementation may claim that arbitrary
source reordering is bitwise equivalent under finite-precision arithmetic.

An absent source produces the identity partial
`(m, l, o) = (-infinity, 0, 0)`; an implementation may bypass that merge only
if it is mathematically equivalent to this identity.  Normalization is legal
only when `l > 0`.  Invoking the merge with an entirely empty logical source
set is an interface-reference assertion failure, not a zero-output fallback.

Two buffers hide a next fill only when `T_consume(current) >= T_fill(next)`;
warm-up and drain remain.  This symbolic condition neither provides a common
clock with M2 nor demonstrates a physical SRAM port implementation.

## 10. Atomicity, ordering, and backpressure

1. Each frozen metadata transaction group has one external publication/
   linearization boundary.  Internal record micro-ops may interleave, but no
   partial member state is visible before all group members and predecessors.
2. Preserve per-head FIFO predecessors, ownership/oldest release, dependency
   release, and lossless credit.  Backpressure may hold work, never drop,
   reorder, substitute Full-KV, or alter admission.
3. M2 replica writes/RMW are atomic at the semantic interface; this does not
   choose a coherence protocol or memory primitive.
4. A source page remains owned through all four GQA completions and partial
   updates; release cannot race a consumer or merge dependency.
5. Payload and metadata publication need an explicit dependency edge in any
   implementation.  This document does not choose its handshake, cycle,
   scoreboarding, or HBM-completion realization.
6. A packed-cold payload read may not start before its associated metadata
   publication is visible.  This condition does not constrain direct hot or
   pending-source delivery.
7. A successful `page_write_commit` establishes packed payload durability or
   availability only.  It does not itself transfer authoritative residency.
   The pending-to-packed authoritative handoff occurs only at the associated
   atomic metadata publication/linearization boundary; pending remains the
   authoritative source during the intervening interval.

The HA8-wide model has `commit_slots = 0`: groups with completed frozen members
and predecessors may publish in one declared service coordinate.  This is not
a global commit controller or physical contention claim.

## 11. Assertion and conservation contract

The interface reference model and any later RTL verification environment shall
be able to express the following invariants.  They are semantic assertions,
not claims that an existing A4 trace observed hardware signals.

```text
no_partial_group_visible
valid_count <= 64
packed_page_owner_is_unique
release_event -> all_gqa_consumers_partial_updates_committed
packed_cold_read -> associated_metadata_is_published
no_stale_page_reference_reaches_a_reused_live_page
accepted_request_id -> exactly_one_terminal_outcome
live_request_id -> not_reallocated
response_beat -> exactly_one_live_request_id
live_read_targeting_s2_slot -> slot_not_reassigned
stale_response -> cannot_make_reused_s2_slot_ready
page_write_commit -> uniquely_terminates_matching_live_write
backpressure_never_changes_mask_or_admission_disposition
retained_token_has_exactly_one_authoritative_residency(hot, pending, packed)
merge_normalization -> exp_sum_l > 0
```

The final conservation assertion excludes explicitly transient P3 staging and
S2 source-buffer copies: they may mirror an authoritative payload but cannot
become an independent logical residency.  DROP tokens have no pending or
packed authoritative residency after their maturity disposition.

## 12. Parameters, unestimated costs, and timing boundary

| Category | Treatment |
|---|---|
| Frozen | Original mask; window 128; page 64; Qwen-anchor 512-B K+V/token; 32-KiB page; 8-B sidecar; four legal GQA consumers; canonical functional source order `hot -> pending -> packed`; 256-B beat; two S2 buffers; eight banks; HA8-wide abstract capability; frozen A4.10 `local32/shared256/staging512`, named here `metadata_control_local32/shared256/staging512`; M2; FIFO/ownership/dependency/credit; one atomic commit boundary. |
| Parameters | Model/layer count; non-anchor bytes/token; page population; page-ID/pointer/handle/address/tag/generation/bank/offset widths; macro/port organization; allocator capacity/mapping; `pending_delivery_realization`; request-ID, epoch/reuse, and outstanding-operation bounds; HBM command/address mapping; fault policy; common clock, arbitration, and overlap schedule. |
| Unestimated | `p3_payload_stage_page` physical realization/dynamic energy; M2 queue/staging dynamic accesses; sidecar/page manager; partial-state storage/spill; merge arithmetic; controller/interconnect; clock/wire/leakage; HBM physical area/energy. |

The A4.14.1 ledger keeps payload and metadata service coordinates separate.
They must not be added into latency, cycles, throughput, or tokens/s until a
shared clock, dependency graph, arbitration, and overlap schedule are defined.
M2 dynamic energy is control-entry-only; it is not total M2 dynamic energy.

The accounted differential omitted-cost budgets for retrieval, summarization,
and reasoning are respectively 27.646, 40.498, and 167.442 mJ/request.
Subsequent Route-A realization must satisfy:

```text
Route-A unestimated dynamic cost - Full-KV unestimated dynamic cost
    < corresponding omitted-cost budget
```

This is an engineering constraint, not a claim of zero omitted cost.  The 2x
HBM rule remains an engineering margin, not a performance guarantee.

## 13. Verification plan and separate RTL gates

Before implementation work: re-hash accepted reports/materialized inputs; run
the existing no-model A4.11.2b--A4.14.1 contract tests and preflights; and
review this document for source split, parameter fields, omitted costs, and
non-additive service coordinates.  A missing ignored artifact is a provenance
gap, not a pass and not authorization to overwrite a frozen artifact.

### Gate A — RTL-entry architecture freeze

Gate A is separate and not passed.  It authorizes RTL work only after review
freezes the following executable architecture contract:

1. the top-level module graph, ownership boundaries, abstract S2 state machine,
   memory request/response and lifetime contract, pending-delivery realization,
   and metadata/payload dependency edges;
2. finite parameter values or allowed ranges for request IDs, epoch/reuse,
   outstanding work, `pending_delivery_realization`, macro/controller
   assumptions, fault behavior, common-clock/arbitration/overlap, and
   backpressure; and
3. a candidate macro/controller/port/replication assumption sufficient to
   define interfaces, without claiming final physical PPA;
4. an RTL-visible implementation page/address/allocator schema derived from
   those frozen parameter choices, including widths, validity/generation
   semantics, and reclamation;
5. an executable interface reference plus the assertion/conservation contract
   above, directed tests, and randomized tests for maturity, tail sealing,
   atomic publication, FIFO/ownership, credits, four-head release, and
   multi-source merge; and
6. a native or explicit controller/interconnect interface with common clock,
   request/response dependencies, arbitration, and overlap.

### Gate B — post-RTL implementation validation

Gate B follows RTL and implementation work.  It requires macro mapping,
synthesis and timing results, area and power validation, realized controller
and service behavior, and accounting for every previously unestimated
differential cost against the A4.14.1 omitted-cost budget.  Gate B is the
first point at which implementation evidence may support a PPA or service
claim; it is not a prerequisite artificially assumed by Gate A.

Until Gate A is accepted, this remains a pre-RTL interface boundary only.  It
does not authorize A4.14 variants or changes to frozen Route-A semantics.
