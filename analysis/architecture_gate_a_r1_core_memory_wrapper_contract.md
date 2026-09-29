# Gate-A R1 — core memory-wrapper / clock / reset closure

## Status and boundary

**Status:** `complete_pure_software_core_mem_if_v1_contract; pre_rtl_only`.

R1 closes the core-side memory transaction, reset, and clock-domain boundary
for the selected `rtl_entry_qwen3_8b_32k_s1_v1` anchor.  It is an
architecture realization contract, not an HBM controller, PHY, CDC
implementation, timing model, service-rate result, PPA result, or RTL
implementation.

The KV subsystem has one synchronous `core_clk` domain for lifecycle/M2/P3/S2,
page manager, direct-pending endpoint, merge control, and `core_mem_if_v1`.
The HBM controller and any clock crossing are outside the subsystem.  The
external memory adapter is responsible for translating this core-side contract
to its native controller/clock behavior without weakening the rules below.

## Selected `core_mem_if_v1` boundary

Every core-side fragment is exactly 512 bits / 64 B.  This is the selected
core-facing interface width, not an HBM channel width, burst width, or the
frozen 256-B accounting beat.

```text
transaction_identity = (request_id[2:0], incarnation[1:0])

core_read_req {
  transaction_identity, read_kind, destination, address_ref,
  expected_fragment_count
}
core_read_rsp {
  transaction_identity, fragment_index, last, status, data[511:0]
}

core_write_req {
  transaction_identity, address_ref, expected_fragment_count
}
core_write_data {
  transaction_identity, fragment_index, last, data[511:0]
}
core_write_commit { transaction_identity, status }
```

`address_ref` is an opaque core-side handle.  It is not an HBM command address,
page-table format, controller burst, or physical channel selection.  R1 admits
the anchor read kinds `s2_fill`, `direct_pending`, and `pack_read`; writes are
the single packer packed-page write path.  It provides at most four live reads
and one live write.  The A3 sixth global identity is a local source-group
association bound; it is not an additional core-memory request slot.

Each channel is decoupled by ready/valid semantics.  Ready-low only delays
acceptance and may not drop, duplicate, reorder a same-transaction fragment,
change a mask/admission disposition, or substitute Full-KV.

## Identity, ordering, fault, and durability

A read/write request becomes live only when its request channel accepts it.  A
live request ID cannot acquire another incarnation.  A terminal request may
later reuse its request ID only with a different incarnation under the A3
quiescence discipline; this R1 reference conservatively rejects reuse of an
identical `(request_id, incarnation)` within one adapter epoch.

Successful read responses for one live identity have fragment indexes
`0..expected_fragment_count-1` in order, exact 64-B data, and `last=1` only on
the final fragment.  Responses for different identities may return in any
relative order.  A terminal fault is `last=1` and has no data; no later
response may affect that terminal identity.  A stale response is rejected.

Successful write data is similarly ordered and exact-width.  A successful
`core_write_commit` is legal only after all expected write data fragments have
been accepted.  It establishes **payload durable only**.  It cannot make a
packed page authoritative, visible, or readable: the existing atomic metadata
publication dependency remains the only pending-to-packed authority transfer.
Fault commits are terminal and fail closed.

## Destructive reset and external adapter obligation

`destructive_reset` clears local/transient subsystem ownership, live
transactions, and local validity associations.  It does not claim to erase
HBM bits.  Pre-reset payload is inaccessible after reset because session,
descriptor, and generation ownership is invalidated by the later lifecycle
contracts.

After reset, `core_mem_if_v1` accepts no traffic until the external adapter
raises `mem_init_done`.  The adapter must drain or suppress every pre-reset
response/commit before asserting that handshake.  The pure-software reference
models this obligation with an adapter epoch solely for verification; adapter
epoch is not a new core-side data wire.  A pre-reset response is rejected even
if its numeric `(request_id, incarnation)` would otherwise collide with a new
post-reset request.

Reset does not select retry, timeout, recovery, HBM initialization, physical
CDC, controller reset sequence, or forward-progress policy.  Those remain
external integration/Gate-B concerns unless a later Gate-A wrapper contract
requires additional interface signals.

## Executable reference and evidence boundary

`kvpress/route_a_core_memory_reference.py` and
`tests/test_route_a_core_memory_reference.py` execute only event-level
acceptance, fragment ordering, fault, backpressure, reset, epoch, and
payload-durable-only checks.  They do not contain model/GPU execution, HBM
commands, cycles, latency, bandwidth, controller arbitration, PPA, or RTL.

R1 is a prerequisite for R2 arbitration/dependency closure.  Every selected
HBM-resident object reaches the external adapter through this one core-facing
boundary: pending payload, packed payload/sidecar, and the R5 descriptor
region.  A descriptor maintenance line is exactly one 64-B R1 write fragment;
its durable write completion is not metadata publication.  R1 does not select
R2 eligibility policy, M2/P3 wrappers, descriptor placement, numeric merge
format, or top-level lifecycle adapter ports.
