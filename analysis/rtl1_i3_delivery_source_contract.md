# RTL1-I3 — delivery-context and source-instance contract

**Status:** `rtl1_i3_0_carrier_closure_complete; source_completion_behavior_pending`.

RTL1-I3 closes the transport association that was deliberately absent from the
owner-local RTL1 modules.  It may preserve post-decision source facts and bind
them to existing owners; it may not choose a source schedule, alter
DROP/RETAIN, page membership/publication, the two S2 slots, direct-pending
realization, R4's 128-bit numeric header, payload storage, HBM/controller
behavior, timing, throughput, or PPA.

## Delivery context

Every `SourceCandidate` now includes opaque `delivery_context_ref`, with the
existing positive parameter `sourceDeliveryOpaqueWidth`.  R2 copies the value
into its finite live-outstanding association and returns exactly that value in
the matched `SourceDelivery`; R2 neither decodes it nor gains any ownership of
S2, direct-pending, P3, page, payload, or source state.  A stale/unmatched R1
response still cannot create a delivery.

## Source-instance sideband

`SourceInstance` contains `{source_kind, instance_coordinate, generation}`.
The kind is the frozen semantic set `{hot=0,pending=1,packed=2}`;
`instance_coordinate` uses the selected logical entry-coordinate width, so it
can name a hot owner while also representing S2's finite slot or the direct
endpoint.  It is not an address, payload pointer, or physical mux encoding.

`R4SourceInstanceSideband` is separate from the frozen 128-bit R4 header and
carries `{transaction_identity, SourceInstance, consumer_id}`.  Later I3
behavior will require it to match the header source/consumer and return it
unchanged in `ConsumerPartialCommit`.  This carrier does not select numeric
arithmetic or claim arbitrary source reordering.

## Evidence boundary

This carrier step has a directed R2 preservation/stall test only.  It is
no-model, no-GPU, no-new-A4-DSE, no timing/throughput/PPA, and no end-to-end
RTL correctness evidence.
