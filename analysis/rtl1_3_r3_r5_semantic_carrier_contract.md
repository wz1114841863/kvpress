# RTL1.3.0 — R3/R5 publication semantic-carrier closure

## Status and boundary

**Status:** `complete_nonphysical_internal_carrier_closure; RTL1.3_behavior_pending`.

This record freezes the module-local, control-only carriers required to turn
the already-closed R3/R5 publication dependency into synthesizable control
RTL.  It refines neither a top-level Route-A port nor the one R1 external
memory path.  In particular, it does not select an HBM command, descriptor
cache, SRAM macro, P3 payload store, M2 port count, queue depth, controller
schedule, cycle, throughput, energy, or PPA result.

The existing cross-owner publication triplet remains unchanged:

```text
lifecycle metadata_publish_req
  -> R3 metadata_publish_visibility_apply
  -> R5 metadata_publish_visibility_ack
  -> R3 m2_publish_ack
```

The new carriers are local R3/R5 implementation-test boundaries.  The top
shell ties them inactive until their owning integration paths are implemented.
They therefore cannot create a second memory, publication, descriptor, or
authority path.

## R3 P3 and M2 carrier association

One P3 claim carries `(layer, kv_head, owner, page_ref, valid_records,
transaction_group_tag)`.  `transaction_group_tag` is an association label for
the already-selected M2 publication group; it is not an M2 address or a new
lifecycle decision.  For a claimed `(layer, stage_generation)` the R3-local
events are:

```text
p3_claim
  -> p3_pending_fragment { fragment_index, last, status }
  -> p3_sidecar_bind { record_ordinal }
  -> p3_packed_write_terminal { status, r1_payload_durable }
  -> two m2_group_member_rsp { member=head_control_rmw|span_owner_rmw,
                               status }
  -> existing m2_publish_req
```

`p3_pending_fragment` deliberately has no stored payload data field.  RTL1.3
checks fragment ordinal/completion and sidecar association only; P3 payload
storage/macro realization remains deferred.  A fragment is 64 B by the fixed
R1 carrier, and a claim requires exactly `valid_records * 8` in-order
fragments and `valid_records` in-order sidecars before it is COMPLETE.

`p3_packed_write_terminal.r1_payload_durable` is the explicit R1 terminal
association.  It is the payload-durable fact only: neither it nor either
successful M2 member may expose the page or transfer authority.

The two M2 member identifiers are frozen semantic identities, not an M2 port
encoding:

```text
0 = head_control_rmw
1 = span_owner_rmw
```

Each is accepted once for the matching durable P3 claim and group tag.  A
fault makes that group non-publishable.  The R3 wrapper may not accept the
existing publication request until the matching P3 claim is durable and both
members are privately staged/OK.  Ready-low rejects without mutation.

## R5 allocation and descriptor-durability association

R5 has two module-local control carriers:

```text
page_allocation_req { layer, kv_head, valid_records, transaction_group_tag }
page_allocation_rsp { page_ref, requires_tail_link, transaction_group_tag }

descriptor_maintenance_terminal {
    kind={new_page,tail_link,invalidate}, page_ref, transaction_group_tag,
    status, r1_descriptor_durable
}
```

The allocation response is a private `PageRef` produced from the selected
18-bit page-ID / 8-bit generation space.  RTL1.3 uses a caller-supplied small
allocator-entry bound only for control-state elaboration and directed tests;
the selected 146,880-entry anchor is preserved as the intended integration
binding.  This is not a physical bitmap/macro decision.

For each active `(layer, kv_head)` append, R5 requires one durable `new_page`
descriptor operation and, only when an already-visible tail exists, one
durable `tail_link` operation.  `invalidate` is rejected in RTL1.3: retirement
and physical reuse remain R6/R5-later work.  Descriptor data/line writes stay
on the already frozen R2 `desc_maint_write` / R1 path; this terminal carrier
does not bypass that path or model its data payload.

R5 accepts `metadata_publish_visibility_apply` only for a matching private,
descriptor-prepared allocation.  Its acknowledgement is the nested R5 part
of the sole R3 publication boundary, never an independent descriptor-visible
event.  A ready-low or fault acknowledgement does not mutate stream/page
visibility.

## Frozen dependency and implementation limits

The only successful RTL1.3 order is:

```text
R5 private allocation
  + P3 COMPLETE
  + R1 payload-durable terminal
  + durable required descriptor operation(s)
  + two private M2 OK members
  -> one existing R3 publication request
  -> R5 visibility acknowledgement
  -> R3 published acknowledgement and P3 release
```

This carrier closure does not choose a retry, timeout, Full-KV fallback,
mask/admission change, a different scheduler, or a different atomic commit.
Reset invalidates only local carrier associations; both R3 and R5 may accept
new local events only after their `mem_init_done` input from R1's reset-epoch
boundary.

## Evidence label

This is RTL-entry interface/control planning only.  It is not model/GPU
evidence, a timing/throughput claim, PPA claim, RTL correctness result, or a
new A4 DSE.
