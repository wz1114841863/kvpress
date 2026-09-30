# RTL1-I3 — delivery-context and source-instance contract

**Status:** `complete_rtl1_i3_delivery_source_and_r6_completion_composition`.

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
carries `{transaction_identity, SourceInstance, consumer_id}`. I3 behavior
requires it to match the header source/consumer and return it
unchanged in `ConsumerPartialCommit`.  This carrier does not select numeric
arithmetic or claim arbitrary source reordering.

## R6 source-completion plan

`SourceCompletionPlan` is an internal R6-facing, per-attention-identity
control carrier. It contains a nonempty three-bit `source_presence` mask and
one exact `SourceInstance` for each canonical kind in the frozen order
`hot -> pending -> packed`. The mask is a source-set declaration, not a source
scheduler, data mux, payload pointer, or a claim that arbitrary source order
is numerically equivalent.

R6 stores only the expected/released association for its existing finite
attention tracker. A release is accepted only when all of the following hold:

- the request identity names a live `AwaitMergeReady` tracker;
- the completion plan was accepted for that tracker;
- the corresponding mask bit is present and not previously released; and
- the full `{kind, coordinate, generation}` exactly matches the planned
  `SourceInstance`.

When and only when the released bitmap equals the planned nonempty presence
mask, R6 emits the already-frozen `merge_req`. This does not give R6 hot,
pending, packed, S2, direct-endpoint, page, or payload ownership; it is a
finite completion association. The prior external `R6MergeReady` carrier is
kept as a compatibility input only for an identity without an accepted plan;
the RTL1-I3 owner path uses the plan plus per-owner releases and cannot be
short-circuited by that older carrier.

## I3.2 implementation binding

The production top demultiplexes `ConsumerPartialCommit` by the returned
`SourceInstance.source_kind` to the sole owner: hot, direct-pending, or S2.
The owner accepts four distinct matching consumers before emitting its one
generation-bearing release. Those releases enter R6, which performs the exact
plan comparison above before creating `merge_req`; the existing R4 boundary
then maps an identity-matching numeric fault or replaceable result into R6's
one outward terminal path.

The production top deliberately leaves source-plan, hot-open, S2 fill, direct
record, and R4 packet ingress structurally inactive: their future packet and
payload adapters are not selected by I3. Test-only composition harnesses may
drive them as directed logical stimuli. This is not a claim of source-mux
realization, payload movement, numeric correctness, or an end-to-end top pass.

## Evidence boundary

## I3.1 implementation binding

R2 now retains `delivery_context_ref` in the same finite outstanding record
that already guards RID/incarnation response matching. A matched response
returns the exact stored value, including while its delivery peer holds
ready-low. R2 does not inspect the value.

The R4 boundary now performs an atomic ready/valid join of one header and one
matching `R4SourceInstanceSideband`. The 128-bit header remains unchanged; the
sideband must agree on identity, source kind and consumer ID, is latched with
the packet, and is returned unchanged with `ConsumerPartialCommit`. S2 accepts
only `{packed, slot, current-generation}` commits; direct accepts only
`{pending, endpoint=0, current-generation}` commits. The hot owner now has an
explicit control-only activation/current-instance/release state, with no hot
K/V storage or service implementation. Each owner still requires four distinct
matching consumers before a sole release.

Directed tests cover R2 preservation under ready-low, R4 sideband mismatch
rejection and round-trip, S2/direct current-generation filtering, and hot
current-generation four-commit release. I3.2 additionally checks every one of
the seven nonempty hot/pending/packed masks, stale-generation release
rejection, and a representative hot -> R4 -> R6 numeric-fault terminal path.
This is no-model, no-GPU, no-new-A4 DSE, no timing/throughput/PPA, no numeric
datapath evidence, and no end-to-end Route-A RTL correctness evidence.
