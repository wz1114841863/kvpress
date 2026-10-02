# RTL2.0e — R3/R5 descriptor-durability prerequisite

**Status:** descriptor_durability_interface_owner_closed; behavioral_delivery_pending.

This closure resolves the R3/R5 prerequisite missing from the RTL2.0 inventory.
It defines one R5-produced aggregate result for one allocated, private append
and binds it to the existing R3 metadata-publication gate. It does not activate
a Chisel carrier, descriptor write, R1 request, R3 publication, physical
descriptor storage, controller, timing, throughput, PPA, or new A4 DSE.

The machine-readable record is
[rtl2_0e_r3_r5_durability_prerequisite_manifest.json](rtl2_0e_r3_r5_durability_prerequisite_manifest.json).

## Exact result and sole owners

R5 alone owns descriptor-operation aggregation and emits exactly one
DescriptorDurabilityPrerequisite result per live append association:

    { layer, kv_head, page_ref=(page_id,generation), transaction_group_tag,
      required_descriptor_operation_mask, durable_descriptor_operation_mask,
      descriptor_prepared, status={OK,FAULT} }

The two logical mask bits are fixed semantic names, not a physical descriptor
format or port decision:

    bit 0 = new_page     (required for every append)
    bit 1 = tail_link    (required exactly when R5 allocation reported requires_tail_link)

For status=OK, descriptor_prepared is true and durable mask equals required
mask. For status=FAULT, descriptor_prepared is false; R5 may report already
durable operations in the durable mask, but it must never later turn that same
association into a successful prerequisite without explicit cleanup/reset. No
result represents descriptor visibility, packed authority, metadata publication,
a page free, or an R1 terminal.

R3 alone consumes the result as a prerequisite for the matching
(layer, P3 stage generation, transaction group tag, page_ref) publication
association. R3 must match layer, kv_head, page ref including generation, group
tag, and the current private stage association before accepting it. It may
record a successful prerequisite only for status=OK, descriptor_prepared=true,
and an exact required/durable mask match. A fault result makes that matching
R3 group non-publishable; it cannot retry, fall back, alter admission, or
create a second terminal path.

## Required ordering

    R5 allocation -> private descriptor maintenance terminals
      -> one R5 aggregate durability result
      -> R3 accepts exact successful prerequisite
      -> existing R3 M2/P3 prerequisites
      -> one existing metadata_publish_commit
      -> nested R3-to-R5 visibility apply/ack and R3-to-R6 observation

The result can be delayed by ready-low only. While held valid, its entire
identity, masks, prepared bit, and status are immutable; neither R5 private
state nor R3 prerequisite state may be advanced by valid alone. Individual
DescriptorMaintenanceTerminal facts remain local to R5. The typed router never
sends them directly to R3, and R3 must not reconstruct descriptor durability
from page allocation, write commit, a payload terminal, or visibility ack.

The pre-existing metadata_publish_commit remains the sole linearization point:
successful descriptor durability is necessary but not sufficient for visibility
or pending-to-packed authority transfer. R3 may not emit
metadata_publish_visibility_apply until it has the exact accepted R5 success
result plus the frozen P3 payload-durable, M2-member, membership, and lifecycle
conditions. R5 may not independently expose the descriptor after producing
the success result.

## Fault, reset, and scope exclusions

A mismatched, stale-generation, duplicate, unexpected-mask, or already released
result is rejected with no R3 or R5 publication/authority mutation. Destructive
reset invalidates both private R5 association and R3 prerequisite association;
an old result cannot match a new page generation or group. R5 descriptor
invalidation/reclaim uses its separately frozen path and is not this append
prerequisite.

This closure leaves P3 payload movement, descriptor-maintenance candidate
production, R1 request/terminal routing, M2 member behavior, sidecar, source
delivery, R4, R6, functional descriptor backing, physical HBM layout, and
all performance questions deferred. In particular, the logical masks do not
select an R5 queue depth, port count, macro, or descriptor line layout.

## Validation

    .venv/bin/python tools/validate_rtl2_r3_r5_durability_prerequisite_manifest.py --help
    .venv/bin/python -m pytest tests/test_rtl2_r3_r5_durability_prerequisite_manifest.py -q

This is a pure-software executable interface contract: no model/GPU,
cycle/timing/throughput, PPA, RTL-correctness, numeric-datapath, or new A4 DSE
claim is made.
