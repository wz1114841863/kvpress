# RTL2.0d — typed delivery-router endpoint descriptors

**Status:** endpoint_descriptor_contract_closed; router_behavior_pending.

This closure makes the deferred RTL2.2 split exact: an R2-preserved SourceDelivery
resolves through the separately owned delivery-context registry to one, and only
one, typed **read-fragment** or **write-terminal** endpoint. It neither
activates the router nor adds payload storage, an SRAM macro, a physical port,
a controller, a source scheduler, numeric hardware, or a second R1 path. The
machine-readable record is
[rtl2_0d_typed_delivery_router_manifest.json](rtl2_0d_typed_delivery_router_manifest.json).

## Sole-owner and resolution boundary

    R2 SourceDelivery (opaque ref unchanged)
        -> typed delivery router requests resolution
        -> registry validates live ref + identity + epoch + class
        -> one exact endpoint descriptor
        -> named endpoint accepts exact fragment or terminal
        -> registry releases ref only after final endpoint acceptance

route_a_delivery_context_registry remains the only owner of opaque-ref
allocation, reuse exclusion, and ref-to-descriptor association. The router does
not decode a ref, reconstruct a destination from response fields, allocate
request identity, create an authority transition, set S2 READY, make a source
deliverable, create an outward terminal, or choose a source plan. It forwards
R1 fragment identity, ordinal, last, status, and data unchanged to the
descriptor-selected endpoint.

Before endpoint observation, the registry must match delivery_context_ref,
transaction identity, reset epoch, candidate class, and immutable target
generation. Unknown, stale, duplicate, or mismatched deliveries are rejected
with no endpoint mutation. A ref remains live across accepted non-final read
fragments and is released only when the final read fragment or write terminal
is accepted by the exact target (or on destructive reset).

## Two non-interchangeable delivery forms

### Typed read fragment

The four frozen read classes resolve to p3_pending_read, s2_full_fill,
s2_packed_fill, or direct_pending_read. The logical TypedReadFragment contains
the validated common identity and target descriptor plus exact R1 fields:

    delivery_context_ref; transaction_identity; reset_epoch; candidate_class
    target_kind; target_identity_generation; fragment_index; last; status
    data[511:0]

On an OK response, data[511:0] is delivered unchanged to the named owner's
**replaceable functional payload/transport endpoint**, together with the typed
descriptor. This is a logical payload handoff, not a physical HBM address,
memory macro, port, or storage commitment. The owner may emit its existing
control-only P3PendingFragment, S2FillTerminal, or DirectPendingRecordTerminal
observation only after accepting that matching typed handoff. A fault response
creates the exact owner-local control fault observation but does not deposit
payload, make S2 READY, or make a direct source deliverable.

| Candidate class | Target kind and owner-local functional endpoint | Immutable descriptor fields |
|---|---|---|
| pack_read | p3_pending_read at route_a_m2_p3_wrapper.functional_p3_payload_endpoint | p3_layer, p3_stage_generation |
| s2_full | s2_full_fill at route_a_s2_gqa_source_wrapper.functional_s2_payload_endpoint | transaction_identity, page_ref, s2_slot, source_generation, requires_sidecar=false |
| s2_packed | s2_packed_fill at route_a_s2_gqa_source_wrapper.functional_s2_payload_endpoint | transaction_identity, page_ref, s2_slot, source_generation, requires_sidecar=true |
| direct_pending | direct_pending_read at route_a_direct_pending_endpoint_v1.functional_pending_transport_endpoint | transaction_identity, endpoint_generation, ordinal, explicit_empty |

These endpoint names are interface names only. In particular, neither they nor
data[511:0] choose an S2/P3 backing implementation or turn direct delivery into
a separately selected pending buffer.

### Typed write terminal

| Candidate class | Target kind and owner | Immutable descriptor fields | Exact terminal rule |
|---|---|---|---|
| pack_write | packed_write_terminal at route_a_m2_p3_wrapper | p3_layer, p3_stage_generation, transaction_group_tag | Emit P3PackedWriteTerminal only for the final R1 response; r1_payload_durable is true exactly when last && status==OK. |
| descriptor_maintenance | descriptor_maintenance_terminal at route_a_page_manager | kind, page_ref, transaction_group_tag | Emit DescriptorMaintenanceTerminal only for the final one-fragment R1 response; r1_descriptor_durable is true exactly when last && status==OK. |

Write terminals do not carry read data and are not read-rotation members. A
write fault is forwarded to its exact owner with the durable bit false; it does
not imply metadata visibility, packed authority, a retry, or a fallback. No
write terminal may be emitted on a non-final response.

## Required separation from existing control carriers

Existing P3PendingFragment, S2FillTerminal, and DirectPendingRecordTerminal are
control-only observations. They must not be relabelled as payload storage
interfaces. RTL2.2 therefore introduces a logical typed payload envelope before
an owner emits any corresponding control observation. P3SidecarBind,
M2GroupMemberResponse, R5 page allocation, metadata publication, authority
handoff, S2 READY, four-consumer completion, R4 packetization, and R6
lifecycle/retirement are outside this router's ownership and remain subject to
their existing contracts.

## Later behavioral obligations

RTL2.2 behavior must bind every router input and endpoint acceptance to these
descriptors and expose only architectural fragment_deliver / write_commit
events through the future RTL2 scoreboard schema. Negative tests must cover
stale ref/generation, wrong class, wrong endpoint, read-fault/no deposit,
non-final write response, and ready-low nonmutation. Fixed-seed legal stalls
may delay an accepted delivery only; they may not change descriptor, data,
ordinal, status, admission, mask, authority, terminal outcome, or ref reuse.

Validation:

    .venv/bin/python tools/validate_rtl2_typed_delivery_router_manifest.py --help
    .venv/bin/python -m pytest tests/test_rtl2_typed_delivery_router_manifest.py -q

This is a pure-software executable interface contract: no model/GPU,
cycle/timing/throughput, PPA, RTL-correctness, numeric-datapath, or new A4 DSE
claim is made.
