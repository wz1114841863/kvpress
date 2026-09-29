# Gate-A R3 — M2 and P3 logical-wrapper closure

## Status and boundary

**Status:** `complete_pure_software_m2_p3_wrapper_contract; pre_rtl_only`.

R3 selects the logical storage wrappers which an RTL implementation must see
for the A3 anchor.  It does not select an SRAM compiler, a physical M2 port
count, a 36-way macro replication, P3 banking, a page-manager placement, a
CACTI access time as a core cycle, HBM command mapping, a controller schedule,
throughput, timing, energy, PPA, or RTL implementation.

The selected boundary remains inside the R1 `core_clk` subsystem.  R1 owns the
core-memory transaction and terminal-status boundary; R2 owns eligibility and
core-side grant order; R3 owns only the M2/P3 stateful wrapper handshakes
required to provide R2's predicates.  All channels below are decoupled:
ready-low delays acceptance without changing FIFO order, ownership, a mask,
admission disposition, credit semantics, authority, or a terminal outcome.

## Evidence and retained meanings

| Input | R3 use | Explicit non-use |
|---|---|---|
| A4.12.0 / A4.12.2 M2 | Eight head-affine banks, two logical `head_control` replicas, one logical `span_owner` store, and semantic atomic RMW/publication membership. | Not a selected multiport SRAM, latency, service rate, or coherence protocol. |
| A4.10 `local32/shared256/staging512` | Existing logical queue/credit predicates supplied to R2/M2. | Not a physical FIFO depth, macro sizing, or 36-layer replication. |
| A4.13.1 P3 | Pending-HBM authority plus one 64-record, 32-KiB transient payload stage per logical layer. | Not a physical SRAM macro, port count, or access schedule. |
| A4.13.4 | One exact sidecar association per packed record and release only after required dependencies. | Not a sidecar latch/macro selection. |
| R1/R2 | 64-B fragments; payload-durable-only write commit; dependency scoreboard. | Not an HBM/controller implementation or a performance result. |

The only M2 realization candidate retained here is the already selected M2
replicated/duplicated control-storage **public-CACTI proxy**.  R3 does not turn
that proxy into a production macro.  P3 remains an unphysicalized Route-A
provision; its 36 logical slots total `36 * 64 * 512 B = 1,179,648 B` payload
capacity, not 36 selected SRAM instances.

## Selected M2 logical wrapper

The anchor has eight head-affine logical banks.  The bank for a grouped
operation equals its `kv_head` in `0..7`.  Its decoupled event boundary is:

```text
m2_op_req {
    operation_id, bank[2:0], object={head_control, span_owner},
    access={read, write, rmw}, opaque_address_ref, owner,
    transaction_group_tag?, group_member?
}
m2_op_rsp { operation_id, status={ok, fault} }

m2_publish_req { transaction_group_tag, p3_layer, p3_stage_generation }
m2_publish_ack { transaction_group_tag, status={published, fault} }
```

`opaque_address_ref` is not an M2 entry format, physical address, SRAM row, or
page descriptor.  Bank/object/access fields express the logical M2 service
contract; they select no macro port or request timing.  Ungrouped reads/writes
may complete with a normal `m2_op_rsp`.  A grouped publication has exactly two
frozen RMW members:

```text
head_control_rmw  -> object=head_control, access=rmw
span_owner_rmw    -> object=span_owner,  access=rmw
```

Both group members must be accepted and return `ok` before their state becomes
privately staged.  `head_control` replica update is one semantic operation:
the wrapper reports either a whole successful response or a fault.  It does
not expose a one-replica-visible state, select a replica-coherence protocol,
or equate two logical replicas with physical ports.

The pre-existing `metadata_control_local32`,
`metadata_control_shared256`, and `metadata_control_staging512` constraints
remain upstream logical credit/ownership predicates.  R3 carries their result
as eligibility; it neither reinterprets a transaction group as a resource unit
nor derives a new queue capacity from it.

## Selected P3 logical wrapper

P3 has exactly 36 logical layer-indexed slots for the anchor.  A slot has one
stream owner at a time and the following fixed payload envelope:

```text
layer                         : 0..35
valid_records                 : 1..64
payload bytes                 : valid_records * 512 B (at most 32,768 B)
payload fragment              : 512 bits / 64 B
fragments per retained record : 8
position sidecar binding      : one logical 8-B position per record
```

The 8-B sidecar binding is required before a stage is write-ready, but it is
not charged to the 32-KiB P3 payload capacity and R3 selects no sidecar storage
implementation.  `page_ref` is an opaque output-page association, not a
descriptor-table format or HBM address.

```text
p3_claim { layer, kv_head, owner, page_ref, valid_records }
  -> p3_claim_ack { layer, stage_generation }

p3_pending_read_req { layer, stage_generation, owner }
p3_pending_read_rsp { layer, stage_generation, fragment_index, last,
                      data[511:0], status }
p3_sidecar_bind { layer, stage_generation, record_ordinal, logical_position }

p3_packed_write_req { layer, stage_generation, owner }
p3_packed_write_terminal { layer, stage_generation, status,
                           r1_payload_durable }
```

There is one logical pending-to-stage read stream and one logical
stage-to-packed write stream for the selected one-packer anchor.  This is a
finite ownership interface, not a physical read/write port, arbitration
policy, or performance guarantee.  P3 state is:

```text
EMPTY -> RESERVED -> FILLING -> COMPLETE -> WRITE_ISSUED -> DURABLE
                                        \-> FAULTED
```

`RESERVED` is the R2 `p3_stage_ready/owned` predicate for a `pack_read`.
`COMPLETE` means every in-order 64-B payload fragment and every valid-record
sidecar binding is present; it is the R2 `p3_stage_complete/owned` predicate
for a pack write.  P3 has no authoritative-residency state in any of these
states.  Pending HBM remains authoritative until M2 publication; a durable
packed HBM write is still non-authoritative.

## Ownership, durability, publication, and release

The selected non-timing dependency is:

```text
R2 grants pending pack_read only with P3 RESERVED/owned
  -> P3 fills ordered fragments and binds each sidecar
  -> R2 grants pack_write only with P3 COMPLETE/owned and page allocation
  -> R1 successful write_commit
  -> P3 DURABLE and M2 records r1_payload_durable
  -> both M2 RMW members private/staged
  -> one `metadata_publish_commit` (m2_publish_req / m2_publish_ack) linearization boundary
  -> lifecycle pending -> packed authority transfer, metadata visible,
     P3 stage release
```

`metadata_publish_commit` is the sole architectural publication event.  The
R3 executable reference invokes the existing A2 lifecycle publication action
within that M2 event and binds R5 descriptor/stream visibility to the same
action.  If that action rejects, no M2 published
bit or P3 release occurs.  If `m2_commit_ready` is low, publication is delayed
without mutation.  Thus successful R1 commit is payload durable only, and the
single atomic metadata publication remains the unique pending-to-packed
authority transfer.

A P3 read or write fault fails its bound M2 group and makes publication
illegal.  An M2 member fault similarly makes the group non-publishable, but
does not discard an independently live P3/R1 stream; explicit fault cleanup
may release the stage only after that stream has reached a terminal state.
Neither case selects retry, timeout recovery, a Full-KV fallback, a mask
change, or a new admission path.

## Reset, stale generation, and limits

`destructive_reset` invalidates R3's local group, outstanding-op, transient
P3-owner, and stage-generation associations.  It does not erase HBM or make
P3 authoritative.  R3 accepts no new event until `r3_init_done`, which is
legal only after the R1 adapter has asserted `mem_init_done`.  R1 continues to
own suppression of pre-reset core-memory responses.  A stale P3 generation or
old M2 group cannot affect a newly claimed slot.

R3's fail-closed fault response is an upward terminal fault and nonpublication.
It is deliberately not a forward-progress or reset-recovery contract.

## Executable reference and required checks

`kvpress/route_a_m2_p3_reference.py` and
`tests/test_route_a_m2_p3_reference.py` execute only event-level wrapper
semantics.  Directed tests cover:

1. 36-slot/64-record/32-KiB envelope, exact sidecar binding, and P3
   non-authority;
2. M2 ready-low nonmutation and fixed grouped-RMW member/object shape;
3. one logical P3 fill/write stream with no physical-port inference;
4. R1 durability -> M2 private state -> one lifecycle publication -> P3
   release ordering;
5. M2/P3 fault nonpublication, explicit cleanup, destructive reset, and
   stale-generation rejection.

This is pure-software executable architecture-contract evidence.  It contains
no model/GPU run, cycle/timing/throughput claim, PPA claim, RTL correctness
claim, or new A4 DSE.
