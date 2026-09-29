# Gate-A R5 — packed-page manager, descriptor placement, and retirement closure

## Status and boundary

**Status:** `complete_pure_software_page_manager_descriptor_contract; pre_rtl_only`.

R5 closes where packed-page descriptor and allocator state reside, how they
are addressed, and how external logical retirement reaches physical reclaim.
It does not select an HBM controller, HBM address width, descriptor-cache
organization, on-chip macro, timing, throughput, energy, PPA, or RTL.

The closure preserves the existing authority rule: pending HBM is authoritative
until the single M2 atomic publication; a payload write commit and any
descriptor write before that boundary are not visibility or authority transfer.
R5 adds no pruning/admission path, page size, scheduler/DSE variant, data-plane
R2 arbitration class, Full-KV fallback, or retry policy.

## Selected storage ownership and finite footprint

| State | Selected owner/location | Finite anchor provision | Explicit boundary |
|---|---|---:|---|
| `StreamDescriptor` | On-chip page-manager active state, one per `(layer, kv_head)` | `36 * 8 = 288` entries, 96 logical bits/entry = 3,456 B | Logical bit inventory, not an SRAM macro, area, or power result. |
| Allocator availability state | On-chip page-manager active state | `146,880`-bit bitmap = 18,360 B plus 18-bit scan cursor | Generation is retained by the HBM descriptor record; in-flight-reference scoreboarding reuses existing R1/S2/direct/M2/P3 ownership facts rather than defining a new FIFO/macro. |
| Packed-page descriptor table | **Separate HBM metadata region** owned by the page manager | `146,880 * 128 b = 2,350,080 B` = 36,720 64-B lines (about 2.241 MiB) | Not included in the selected 5-GiB cold payload pool; its traffic/energy/controller impact remains Gate-B/unestimated. |
| P3 stage / M2 / merge / endpoint | Their already-selected owners | Unchanged | They are not hidden inside R5 storage. |

The 5-GiB pool continues to include only cold K/V payload, position sidecar,
and one 33,280-B migration reserve.  The R5 descriptor HBM region is separate
from it.  The 2.241-MiB number is a deterministic entry-count calculation, not
an HBM area, bandwidth, latency, energy, or performance claim.

## Selected 128-bit descriptor and deterministic map

The descriptor table index is the allocated `page_id[17:0]`; hence a payload
or sidecar handle is **derived**, rather than stored redundantly in the entry.
The table entry is little-endian and has the following selected layout:

```text
bits [  1: 0]  descriptor_state {FREE, ALLOCATED_UNPUBLISHED,
                                 LIVE_PACKED, RETIRE_PENDING}
bits [  7: 2]  owner_layer       (0..35)
bits [ 10: 8]  owner_kv_head     (0..7)
bits [ 17:11]  valid_count       (0..64)
bits [ 35:18]  next_page_id[17:0] (all ones means no next page)
bits [ 43:36]  next_generation[7:0] (ignored for no-next)
bits [ 51:44]  page_generation[7:0]
bits [127:52]  reserved, written and checked as zero
```

`PageRef = (page_id[17:0], generation[7:0])`.  The descriptor line location
is `entry_offset = page_id * 16 B`, `line_index = floor(page_id / 4)`, and
`lane = page_id mod 4`.  Given opaque, disjoint region bases supplied by the
external adapter:

```text
descriptor_line_handle = DESCRIPTOR_HBM_BASE + 64 B * line_index
payload_handle         = COLD_PAYLOAD_POOL_BASE + 33,280 B * page_id
sidecar_handle         = payload_handle + 32,768 B
migration_reserve      = COLD_PAYLOAD_POOL_BASE + 33,280 B * 146,880
```

The migration reserve has no allocatable page ID and no descriptor.  Physical
base/address width, HBM interleave, burst, and controller mapping remain
external parameters.  A descriptor must not be backfilled into A4.9.1's
59/50-bit metadata entries or silently charged to the 5-GiB data pool.

`StreamDescriptor` is a selected 96-bit logical on-chip active record:
owner layer/head, first and tail `PageRef`, `page_count[8:0]`,
`total_valid_tokens[14:0]`, and 11 reserved-zero bits.  It has no separate tail
valid-count field: for nonempty streams it derives from `total_valid_tokens
mod 64`, with zero remainder meaning 64.

## Descriptor-maintenance interface and publication dependency

R5 defines a separate page-manager maintenance client in the same `core_clk`
domain.  Every operation is one `desc_maint_write` FIFO-ordered maintenance
request through R2 and the **same R1 `core_mem_if_v1` write boundary** used by
payload paths.  It uses 64-B lines only because that is the already-selected
R1 core-facing fragment width.  It is not a native HBM request/burst, extra
HBM port, or a member of the frozen payload-read rotation.

```text
descriptor_op_req {
    op_id = {kind[1:0], subject_page_ref[25:0], target_page_ref[25:0]},
    kind = {new_page, tail_link, invalidate},
    descriptor_line_index[15:0], lane[1:0], data[511:0]
}
descriptor_op_rsp { op_id, status={ok, fault} }
```

At most two logical maintenance operations are live: one new-page descriptor
and, when an append has a prior tail, one prior-tail link update.  This is a
finite one-packer ownership bound, not two physical ports, a controller queue
depth, or a service rate.  Descriptor maintenance inherits R1 `(RID,
incarnation)`, ready/valid, exactly-one terminal, reset-epoch, and fault
rules.  It may be backpressured only by delaying its own
preparation/publication/retirement state; it cannot alter the R2 ordering of
`s2_fill -> direct_pending -> pack_read`, a mask, an admission decision, source
ownership, or a Full-KV decision.  External adapter arbitration between
descriptor maintenance and data traffic remains Gate-B.

For one page append the mandatory event order is:

```text
allocate PageRef / private stream ownership
  -> R1 packed payload write commit (payload durable only)
  -> descriptor new-page write and, if needed, prior-tail link write durable
  -> descriptor_prepared (still inaccessible to attention)
  -> R3 M2 private members staged
  -> one `metadata_publish_commit` action
  -> M2 visibility + lifecycle pending->packed authority + R5 descriptor and
     stream visibility as one event-level boundary
```

The physical descriptor bits may be materialized before publication, but the
page manager exposes a descriptor to packed traversal only after that M2
boundary.  Consequently a pre-published tail link cannot cause an attention
read of an unpublished page.  A descriptor fault makes its page manager
fail-closed and non-publishable; no retry, timeout recovery, fallback, or
semantic change is selected.

## Retirement, reclaim, reset, and generation reuse

The external runtime/session manager sends exactly one retirement request using
the selected finite `(request_id[2:0], incarnation[1:0])` identity after it
stops new logical work.  R5 returns the same identity only as `retire_ack`:

```text
runtime_retire_req(identity)
  -> admission/publication stop
  -> drain R1 requests, S2/direct/P3/M2/merge ownership and descriptor ops
  -> per page: no-live-reference quiescence
  -> durable descriptor invalidation (state FREE with next generation)
  -> allocator generation advance / bitmap free
  -> retire_ack(identity)
```

The exact per-page quiescence set remains the A3 one:
`no_live_page_reference`, `no_outstanding_old_page_response`,
`no_s2_old_page_association`, `no_direct_pending_old_page_association`, and
`no_metadata_old_page_reference`.  An 8-bit generation wrap additionally
requires this complete predicate before transition to zero.  No page ID can
become reusable before its descriptor invalidation is durable and its
generation advances.

`destructive_reset` invalidates local page-manager/stream/descriptor
visibility associations, stops requests, and requires R1 `mem_init_done`
before R5 init is acknowledged again.  It does not erase raw HBM bytes.  R1
continues to suppress pre-reset responses, and M2/lifecycle reset invalidates
old descriptor authority; R5 therefore does not make old raw descriptor bytes
reachable by a new session.

## Executable reference and evidence boundary

`kvpress/route_a_page_manager_reference.py`,
`kvpress/route_a_cross_closure_reference.py`, and their tests execute only descriptor packing,
address derivation, private-to-published visibility, fail-closed maintenance
faults, retirement drain, invalidation-before-generation-advance, and reset
init rules.  They use small finite tables for state-space tests and independently
check the anchor's 146,880-entry capacities.

This is pure-software executable architecture-contract evidence.  It is not a
model/GPU execution, controller/timing/bandwidth claim, PPA claim, RTL
correctness result, new A4 DSE, or accounting of descriptor HBM traffic/energy.
