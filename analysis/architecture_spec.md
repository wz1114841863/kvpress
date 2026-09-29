# Route-A architecture specification — pre-RTL interface boundary

## 1. Status and scope

**Status:** architecture-contract freeze, Reviewer-02 passed, 2026-09-29.
A4.14.1 conditionally authorized this architecture specification and
Reviewer-02 closed the R1--R6 cross-contract review. This permits only a
separately reviewed RTL-entry design/verification plan; it does not authorize
RTL implementation, Chisel, PDK/PPA, physical SRAM macros, a native HBM
controller, or measured performance claims.

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

Gate-A1 closes `pending_delivery_realization` as
`direct_pending_endpoint_v1`; its architecture-choice rationale and finite
interface are recorded in
`analysis/architecture_gate_a1_pending_delivery_realization_closure.md`.
This closure is not retroactive evidence that A4 selected a physical endpoint.
Its revision-specific byte bindings are frozen in
`analysis/architecture_gate_a1_provenance_freeze.md`.

Gate-A2 makes the selected ownership, request, S2, and publication assertions
executable in the pure-software reference described by
`analysis/architecture_gate_a2_executable_contract.md`.  It is a
scoreboard/golden-reference seed, not RTL or timing evidence.
Its revision-specific byte bindings are frozen in
`analysis/architecture_gate_a2_provenance_freeze.md`.

Gate-A3 completes finite RTL-boundary parameter closure in
`analysis/architecture_gate_a3_plan.md`.  Its selected
`rtl_entry_qwen3_8b_32k_s1_v1` profile is an engineering anchor
instantiation, not an architecture definition; the profile validator and
provenance freeze remain pure-software evidence.  A3 does not pass Gate A and
cannot convert deployment-profile assumptions into performance, PPA, or
portability claims.

Reviewer 01 established semantic/finite-anchor readiness; Reviewer 02 then
completed the R1–R6 cross-closure review in
`analysis/architecture_gate_a_reviewer_02.md`. Gate A therefore passes only as
an architecture-contract freeze: it permits definition of a separately scoped
RTL interface/assertion gate, not RTL implementation evidence, PPA, controller
selection, or a new A4 DSE. The reviewed state is byte-bound by
`analysis/architecture_gate_a_reviewer_02_provenance_freeze.md`.

For current navigation, read this document together with `analysis/README.md`.
The individual A0--A3, R1--R6, and reviewer records remain retained historical
closure/provenance evidence rather than parallel living specifications.

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
| Generic lifecycle boundary | R6 lifecycle adapter: post-decision arrival, maturity disposition, attention request, and session retire | The backend has no score/threshold/predictor input. Finite Qwen-anchor adapter fields are not a portability claim. |
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
                                   P3 payload-stage page       direct pending endpoint
                                           |                    (Gate-A1 architecture closure)
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
multi-source merge control are Route-A incremental.  Gate-A1 selects the
direct pending endpoint because it preserves A4.13.4's logical direct-source
action without adding a pending page/buffer contract; this is an architecture
choice, not an A4 physical realization result.  Every graph edge becomes a
concrete interface only after the corresponding Gate-A parameter and
dependency contract are frozen.

R6 freezes the generic frontend adapter and binds this dependency graph to the
R1--R5 wrappers. Its finite Qwen-anchor port fields, common/incremental owner
split, reset/init prerequisites, and runtime-retirement drain acknowledgements
are in `analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md`; the
revision-specific binding is
`analysis/architecture_gate_a_r6_provenance_freeze.md`. The resulting graph is
still pre-RTL: it does not select a controller, FSM encoding, service rate,
physical port, or overlap schedule.

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

R5 freezes the Qwen-anchor page reference as
`PageRef = (page_id[17:0], generation[7:0])`, a 128-bit packed-page descriptor
in a separate HBM metadata region, and a 96-bit on-chip active
`StreamDescriptor`.  The descriptor table index is `page_id`, so its payload
and sidecar handles derive from the disjoint cold-payload base plus
`page_id * 33,280 B`; the sidecar is at payload offset `32,768 B`.  The
descriptor region is exactly 2,350,080 B for 146,880 entries and is not inside
the 5-GiB cold-payload pool.  Base-address width/mapping and physical HBM
implementation remain external parameters.

These fields are outside the A4.9.1 59/50 raw and 64/64 padded metadata
accounting and must not be backfilled into those widths.

### Normative logical descriptors

The following is the R5 anchor schema.  It fixes logical bit fields and
ownership, not an SRAM macro, HBM controller map, physical layout, or ABI.

```text
PackedPageDescriptor {
    state[1:0], owner_layer[5:0], owner_kv_head[2:0],
    valid_count[6:0], next_page_id[17:0], next_generation[7:0],
    page_generation[7:0], reserved_zero[75:0]
}

StreamDescriptor {
    owner_layer[5:0], owner_kv_head[2:0],
    first_page_ref[25:0], tail_page_ref[25:0],
    page_count[8:0], total_valid_tokens[14:0], reserved_zero[10:0]
}
```

An allocated packed page has exactly one stream owner.  `next_page_id=all
ones` means no successor.  A stale reference must not designate a reallocated
live page: the selected R5 rule is the 8-bit PageRef generation plus A3's
complete quiescence predicate before wrap.  The full placement, descriptor-line
map, retirement, reset, and maintenance interface are in
`analysis/architecture_gate_a_r5_page_manager_descriptor_contract.md`; the
revision-specific R5 binding is
`analysis/architecture_gate_a_r5_provenance_freeze.md`.

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
timing, descriptor-maintenance service, physical HBM address mapping, and
macro organization remain unestimated.

### Gate-A R3 P3 logical-stage wrapper

R3 binds the per-layer P3 stage to a finite event-level wrapper: exactly 36
logical layer-indexed slots, each with one owner, `valid_records` in `1..64`,
at most 32,768 B payload, and eight ordered 64-B fragments per retained
512-B K+V record.  A sidecar binding supplies one logical 8-B position for
each valid record before the stage becomes write-ready; it is not included in
P3's 32-KiB payload capacity and R3 selects no sidecar latch or macro.

P3 accepts one logical pending-to-stage fill stream and one logical
stage-to-packed write stream for the one-packer anchor.  Those streams are
decoupled ownership interfaces, not physical SRAM ports, an arbitration
schedule, or service guarantee.  `RESERVED` grants the existing R2
`p3_stage_ready/owned` predicate for a pending pack read; `COMPLETE` requires
all ordered payload fragments and sidecar bindings and grants the existing R2
`p3_stage_complete/owned` predicate for a pack write.  P3 is transient in all
states and is never an authoritative residency.

After a successful R1 write commit, P3 becomes `DURABLE` only with the R1
payload-durable indication.  It remains non-authoritative until the one M2
atomic publication.  Publication then makes metadata visible, invokes the
existing lifecycle pending-to-packed handoff, and releases the P3 stage as one
event-level linearization boundary.  The exact interface/reset/fault contract
is in `analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md`; it leaves
P3 macro organization, physical ports, dynamic energy, and timing unestimated.
The revision-specific R3 binding is
`analysis/architecture_gate_a_r3_provenance_freeze.md`.

### Gate-A R5 page-manager and descriptor wrapper

R5 selects 288 96-bit on-chip active stream descriptors, an 18,360-B
on-chip page-availability bitmap, and a separate 2,350,080-B HBM metadata
region containing 146,880 128-bit packed-page descriptors.  This descriptor
region is excluded from the 5-GiB cold payload pool; the fixed accounting is a
storage-interface capacity only, not an HBM area/energy/performance result.
Each descriptor line is four 16-B entries in one 64-B core-facing maintenance
line.  The selected table-index/handle derivation, entry layout, and
maintenance interface are in
`analysis/architecture_gate_a_r5_page_manager_descriptor_contract.md`.

R5 permits at most two logical descriptor maintenance operations for one
packer append: the new page entry and, if present, the old tail's next-link.
Each is an exactly-one 64-B `desc_maint_write` through R2 and the same R1
`core_mem_if_v1` write boundary; this separate maintenance FIFO cannot advance
the frozen payload-read rotation. They are private until the sole
`metadata_publish_commit`, at which one
event-level action makes the M2 state, page-manager descriptor/stream state,
and pending-to-packed authority transition visible.  Maintenance backpressure
can delay publication or retirement only; it cannot form a new R2 data-plane
arbiter class, change the fixed grant order, or alter a mask/admission result.

The runtime requests retirement using the finite A3 `(request_id,
incarnation)` identity.  R5 stops new work, drains all preexisting ownership,
requires A3 page quiescence, durably invalidates each descriptor, then advances
generation/frees the allocator bit before returning the matching `retire_ack`.
Destructive reset invalidates local reachability but does not erase HBM bytes;
R1 response suppression and a new R5 init handshake remain mandatory.

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

### Gate-A R3 M2 logical wrapper

R3 gives the selected M2 semantic storage a decoupled logical interface:
`m2_op_req/op_rsp` carry an operation identity, the eight-bank head-affine
bank identity, `head_control` or `span_owner` object identity, `read/write/rmw`
kind, opaque address reference, owner, and (where applicable) transaction
group/member tag.  A group has exactly the frozen private members
`head_control_rmw` and `span_owner_rmw`; both must return `ok` before the group
is staged.  The M2 `m2_publish_req/ack` is accepted only after that state and
the matching P3/R1 payload-durable dependency, and is the same single atomic
publication boundary described above.

M2 ready-low delays `op_req` or publication without state mutation.  A member
fault makes the group non-publishable; it cannot cause Full-KV fallback, a
retry policy, a mask/admission change, or a partial group visibility.  The
logical atomic `head_control` replica update does not select a coherence
protocol, macro port count, SRAM layout, service rate, or CACTI-derived cycle.
R3's destructive reset invalidates local M2/P3 ownership and accepts no new
traffic until R1's `mem_init_done` has enabled the R3 init handshake; it does
not erase HBM or relax R1 stale-response suppression.

## 9. S2 source buffer, memory transport, GQA multicast, and merge

Each of the two logical S2 slots has 32,768-B **payload** storage.  For a
Route-A packed page it additionally requires 512-B position-sidecar storage,
plus slot identity, generation/validity, and consumer-completion state.  The
512-B sidecar is not included in the 32-KiB payload-buffer capacity.  The
payload buffer remains common Full-KV/Route-A infrastructure; Route-A sidecar
and its management are incremental and unestimated.

### Core-side memory transport contract

Gate-A R1 selects `core_mem_if_v1` as the synchronous core-side boundary.  It
places lifecycle/M2/P3/S2/page-manager/direct-pending/merge control and this
interface in one `core_clk` domain.  The HBM controller, PHY, and any CDC are
outside the KV subsystem and must be adapted without weakening this contract.
The selected 512-bit/64-B fragment is core-facing only; it is not an HBM bus
or burst width and is not the frozen 256-B accounting beat.

The following is an architectural core-side requirement, not a selected
AXI/HBM protocol, native transaction format, controller command/address, or
timing/service-rate assumption:

```text
page_read_req {
    request_id, incarnation, source_kind, payload_handle_or_address,
    valid_count, expected_generation_or_validity, destination_endpoint,
    expected_fragment_count
}
page_read_rsp {
    request_id, incarnation, destination_endpoint,
    observed_generation_or_validity, fragment_index,
    payload_or_sidecar_data[511:0], last, status
}
page_write_req {
    request_id, incarnation, destination_payload_handle_or_address,
    valid_count, expected_fragment_count
}
page_write_data {
    request_id, incarnation, fragment_index, payload_or_sidecar_data[511:0], last
}
page_write_commit { request_id, incarnation, resulting_page_reference, status }
```

For one accepted `(request_id, incarnation)`, successful fragments are ordered
from zero through the declared terminal count; different live identities may
return in any relative order.  A terminal fault carries no valid payload and
cannot be followed by a successful response for that identity.  The selected
anchor permits four live reads and one live write at this boundary; its sixth
global A3 identity is a local source-group association, not another memory
request slot.  `payload_handle_or_address` is an opaque core-side reference,
not an HBM physical address or page-table format.

R1 defines destructive local reset: after reset, the subsystem accepts no
core-memory traffic until the external adapter acknowledges `mem_init_done`.
That adapter must drain or suppress pre-reset responses/commits; the
software-only R1 reference models the obligation with an adapter epoch that is
not a core-side data wire.  Reset invalidates local/session/descriptor
ownership; it does not claim to erase HBM data.

The complete R1 contract and executable reference binding are in
`analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md`, with the
revision-specific snapshot in `analysis/architecture_gate_a_r1_provenance_freeze.md`.
R1 does not select a controller implementation, HBM timing, a physical clock
crossing, retry/timeout policy, or sustained issue rate.

### Core-side eligibility and issue contract

Gate-A R2 selects an event-level dependency scoreboard before the R1 request
channels. Every candidate first satisfies frozen FIFO predecessor,
ownership, dependency, and credit predicates.  It additionally satisfies its
source-specific predicate: packed S2 fill requires metadata publication;
direct-pending and pack reads require pending authority; pack read also
requires P3-stage readiness/ownership; and the one pack write requires page
allocation plus complete, owned P3 data.  A successful R1 write commit makes
the related metadata group eligible only as **payload durable**; the existing
M2 atomic publication is still the authority handoff.

Eligible payload-read classes rotate deterministically as
`s2_fill -> direct_pending -> pack_read`; the oldest eligible candidate within
one class wins.  The cursor advances only after R1 accepts a request.  This is
weak fairness among continuously eligible classes at accepted grant
opportunities, not a latency, progress, bandwidth, or external-HBM-scheduler
claim. Descriptor maintenance is a separate FIFO-ordered one-fragment write
channel through the same R1 boundary, not a descriptor-read class or a second
HBM port. R2 cannot reorder a frozen FIFO predecessor, alter a mask/admission
disposition, drop work, or substitute Full-KV.  Its complete contract and
reference are in `analysis/architecture_gate_a_r2_arbitration_dependency_contract.md`,
with the revision-specific snapshot in
`analysis/architecture_gate_a_r2_provenance_freeze.md`.

`destination_endpoint` is either an S2 slot or the Gate-A1 direct pending
endpoint.  A packed-page read targets S2; a pending-HBM read targets only the
direct pending endpoint defined by the Gate-A1 closure.  S2 reuse and a
separate pending buffer are outside this specification.  For an S2-targeted read,
`READY` is legal only after a matching successful response has delivered all
required payload beats and, for packed Route-A, the sidecar.  A direct pending
delivery uses `direct_pending_source_deliverable`, not an S2 `READY` event, as
defined by the Gate-A1 closure.  For a write, packed-page
metadata publication is legal only after a matching successful
`page_write_commit` and the frozen metadata transaction-group requirements.
The anchor freezes request-ID/epoch bounds, four read/one write core-memory
limits, response ordering per identity, and R1/R2 backpressure behavior.
Endpoint, handle/address, and generation encodings remain selected-profile
fields; their concrete controller mapping is not an HBM implementation claim.
`status` reserves a fault boundary; retry, timeout, ECC, error recovery, and
fallback policy are not selected here and may not change the mask or admission
semantics.

### Request lifetime and stale-response contract

An accepted `(request_id, incarnation)` becomes live and remains live until
exactly one terminal outcome: a successful terminal read response, a terminal
fault status, or (for a write) one `page_write_commit`.  Every response beat
must belong to exactly one live identity.  A live `request_id` may not acquire
another incarnation; terminal reuse requires a new incarnation and the A3
wrap-quiescence predicate.  A slot targeted by a live read request cannot be
reassigned.  The slot's fill association is the live identity together with
its expected generation/validity; a late or stale response that does not match
that association cannot make a reused slot `READY`.  A write commit uniquely
terminates its matching live write request.  Gate-A3 selects explicit epoch
carriage, rather than a transport no-late-response assumption, for the anchor
profile.

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
initialized.  For an S2 source, that event is `READY`; for pending it is the
Gate-A1 `direct_pending_source_deliverable` event.  At that event,
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

### Gate-A R4 finite numeric merge wrapper

R4 selects the Qwen-anchor observable partial format as binary32 `m`, binary32
`l`, and 128 binary32 `o` lanes for each of the four query-head consumers.
Each present partial carries a 128-bit little-endian header and eight ordered
64-B value fragments; an absent source is a header-only encoding of
`(-infinity, +0, +0[128])`.  The header fixes source ordinal
`hot=0/pending=1/packed=2`, four-consumer ID, one active merge instance, and
reserved-zero bits.  These are logical core-side fields, not an HBM transaction
or a port, timing, macro, traffic, or energy selection.

The finite numeric reference rounds observable results to binary32
round-to-nearest, ties to even.  Present nonfinite input, output nonfinite,
binary32 overflow, or `l <= 0` is terminal `numeric_fault`, with no normalized
output, retry, Full-KV substitution, or mask/admission change. R6 consumes it
after all four GQA partial updates as the exactly-one outward attention fault.
Exponent-scale
underflow to `+0` remains an ordinary term.  `m` must match A2 bitwise and
`l`/`o` must meet the declared `abs(delta) <= 1e-5 + 1e-4 * abs(A2)` relation.
The exp implementation and internal precision remain unselected.  The complete
contract and executable reference are in
`analysis/architecture_gate_a_r4_numeric_merge_contract.md`; the
revision-specific binding is
`analysis/architecture_gate_a_r4_provenance_freeze.md`.

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
5. R3 selects an event-level payload/metadata handshake:
   `R1 payload durable -> P3 DURABLE + M2 private group staged + R5 descriptor
   durable -> one metadata_publish_commit -> lifecycle authority transfer + P3
   release + descriptor/stream visibility`.
   It does not select a cycle, controller completion implementation,
   scoreboarding microarchitecture, or overlap schedule.
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

The Gate-A2 interface reference model and any later RTL verification environment
shall be able to express the following invariants.  They are semantic
assertions, not claims that an existing A4 trace observed hardware signals.

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

Gate-A2 additionally executes the canonical mathematical source-partial merge,
the hot/maturity/DROP authority path, and lossless semantic stalls.  Its strict
non-reuse request-ID profile is the baseline; its optional epoch-reuse profile
is only a stale-response refinement and does not select request width or an
outstanding-operation bound.

## 12. Parameters, unestimated costs, and timing boundary

| Category | Treatment |
|---|---|
| Frozen | Original mask; window 128; page 64; Qwen-anchor 512-B K+V/token; 32-KiB page; 8-B sidecar; four legal GQA consumers; canonical functional source order `hot -> pending -> packed`; 256-B beat; two S2 buffers; eight banks; HA8-wide abstract capability; frozen A4.10 `local32/shared256/staging512`, named here `metadata_control_local32/shared256/staging512`; M2; FIFO/ownership/dependency/credit; one atomic commit boundary; Gate-A1 `direct_pending_endpoint_v1`; R3 fail-closed M2/P3 fault/nonpublication and reset-init boundary; R4 binary32 partial/result packet contract and numeric-fault disposition; R5 18-bit page ID/8-bit generation, 128-bit descriptor, separate descriptor HBM region, and retirement/reclaim order; R6 score-free generic lifecycle port set, reset/init prerequisites, and retirement-drain dependency. |
| Parameters | Model/layer count; non-anchor bytes/token; page population; macro/port organization; non-anchor allocator capacity/mapping; descriptor/payload HBM base-address and controller mapping; request-ID, epoch/reuse, and outstanding-operation bounds; HBM error-detail/ECC realization; common clock, arbitration, and overlap schedule. |
| Unestimated | `p3_payload_stage_page` physical realization/dynamic energy; M2 queue/staging dynamic accesses; direct-pending endpoint transport/control; R4 exp/internal-precision implementation, partial-state storage/spill, and merge dynamic energy; R5 descriptor maintenance traffic/dynamic energy and on-chip macro cost; sidecar/page manager physical implementation; controller/interconnect; clock/wire/leakage; HBM physical area/energy. |

### A3 selected RTL-entry anchor

Gate-A3 materializes one finite engineering anchor at
`analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json`.  It uses a
32,768-token, one-concurrent-sequence Qwen3-8B Route-A instantiation; one
pending endpoint; one pack engine; one active KV-head group; `4` live reads
(`2` S2 fills, `1` direct-pending, `1` pack read); one live write; and a
512-bit/64-B core fragment.  The entry profile's field schema names an
abstract retention-KV semantic interface, but its declared evidence scope is
only this Route-A Qwen3-8B anchor, not cross-algorithm portability.

Its 5-GiB cold-KV HBM pool is a shared pending/packed address pool with
distinct authority tags, rather than two separately provisioned 5-GiB
regions.  It is sized with a keep-all cold-record guard, one packed-page
migration reserve before atomic publication, 18-bit page IDs, and finite
request/page generation quiescence.  `MAX_PENDING_RESIDENT_RECORDS` is the
HBM-resident authority bound; the one live pending transaction is a separate
endpoint bound.  This only closes finite address/resource interfaces.  It
does not model HBM allocation timing, claim capacity sufficiency outside this
anchor, or alter M2/P3/S2/FIFO/atomic-publication semantics.

The 5-GiB pool includes only cold K/V payload, the 8-B/token position sidecar,
and one 64-token payload-plus-sidecar migration reserve.  It excludes page
descriptor/allocator metadata, M2 control metadata, `p3_payload_stage_page`,
direct-endpoint transient fragments, partial merge state, ECC/alignment, and
HBM-controller overhead.  The page manager owns the excluded descriptor/allocator
state in the R5-selected separate HBM descriptor region plus on-chip active
state.  The
listed exclusions must not be silently charged to the pool or treated as
covered capacity; R5 descriptor traffic/dynamic energy and on-chip macro cost
remain unestimated.

The selected 512-bit/64-B fragment is solely a core-facing internal interface
choice.  It is not an HBM channel width, burst width, or reinterpretation of
the frozen 256-B accounting beat.  Any mapping between this interface and a
later HBM controller belongs to the Gate-A memory-wrapper contract and Gate-B
implementation evidence.

Logical session retirement is requested by the external runtime/session
manager.  The KV subsystem then drains live work, checks quiescence, reclaims
physical pages, and advances validity/generation.  A page-generation wrap
requires no old live page reference, response, S2 association, direct-endpoint
association, or metadata reference.

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

### Gate A _ architecture-contract freeze

Reviewer 02 passed the cross-closure review of the following executable
architecture contracts. This freezes the interface boundary and permits only a
separately approved RTL interface/assertion gate; it does not itself establish
RTL correctness or select a physical implementation:

1. the R6 top-level module graph/generic lifecycle adapter, abstract S2 state
   machine, R1/R2 memory lifetime contract, Gate-A1 direct-pending endpoint,
   R3 M2/P3 wrapper, and metadata/payload dependency edges;
2. finite parameter values or allowed ranges for request IDs, epoch/reuse,
   outstanding work, macro/controller
   assumptions, fault behavior, common-clock/arbitration/overlap, and
   backpressure; and
3. a candidate macro/controller/port/replication assumption sufficient to
   define interfaces, without claiming final physical PPA;
4. the R4-selected numeric packet/comparison/fault contract and the
   R5-selected page/address/allocator schema, including descriptor-region
   ownership, widths, validity/generation semantics, and reclamation;
5. an executable interface reference plus the assertion/conservation contract
   above, directed tests, and randomized tests for maturity, tail sealing,
   atomic publication, FIFO/ownership, credits, four-head release, and
   multi-source merge; and
6. a native or explicit controller/interconnect interface with common clock,
   request/response dependencies, arbitration, and overlap.

### Gate B _ post-RTL implementation validation

Gate B follows RTL and implementation work.  It requires macro mapping,
synthesis and timing results, area and power validation, realized controller
and service behavior, and accounting for every previously unestimated
differential cost against the A4.14.1 omitted-cost budget.  Gate B is the
first point at which implementation evidence may support a PPA or service
claim; it is not a prerequisite artificially assumed by Gate A.

This remains a pre-RTL interface boundary. It does not authorize A4.14 variants
or changes to frozen Route-A semantics.
