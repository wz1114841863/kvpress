# Route-A next structure opportunities — 2026-11-06

## Evidence and scope

This documentation-only review extends the compact-wrapper read-port audit,
mapped hotspot attribution and Page Manager P0 using current source.  It
starts no implementation or experiment.  RD1's isolated read-network saving
is measured; whole-top RD1 benefit still requires native integrated acceptance.
PM1's saved-DDC result closes its bottom-up screening role.

Accepted entry-id compact hierarchy areas are 2,638,229.5377 for M2/P3
(72.8% of the top), 407,451.2386 for Page Manager (11.2%), 175,682.9790 for
M2 production control (4.85%) and 85,833.0491 for the metadata bridge (2.37%).
These are predecessor areas, not post-RD1 attribution.

The mapped compact-table audit retains 366,336 sequential cells, approximately
1,292,433 area, or 35.7% of the accepted top.  RD1 preserves all of them.
The top noncombinational area is 1,982,097.150886, about 54.7% of total area.
Selector changes cannot remove this state cost.

## Candidates and their actual structures

Source anchors below refer to `RouteAIncrementalSkeletons.scala` unless noted.

### RD2 — remaining wrapper record readers

RD1 helper `RouteAMemberRecordReadSharing.scala` shares only M/S/O member
reads per bank.  Three member validation readers C/F/B and two 80-bit pending
suffix readers M/C remain independent (around lines 2739, 2801--2802, 2850,
2908--2910).  F consumes 64 bits and B consumes 79 bits.

Compare nested mux lowering with field-specific, explicit bank/ordinal decode
and balanced one-hot selection.  Share decode across fields of the same port,
retaining every simultaneously legal independent read.  Use a 36 x 64 harness
including RD1 and all remaining readers to measure incremental benefit.
C/F/B ready depends on stored data even with valid low; fire/ready must not
decide port reuse.  One-hot decode may increase gates or fanout, so no saving
is established before matched mapping.

### SEL1 — materializer mask and selection

Around lines 2727--2739, 36 64-bit candidate masks include a variable
shift/subtract prefix mask, followed by lowest-layer and lowest-ordinal
selection.  Screen equivalent prefix generation and balanced selection;
compare shared prefix decode with per-bit range compares.  Preserve priority,
valid-cycle data, ready-low behavior and pre-edge reads.  No extra register or
cycle is proposed.  This also targets a measured timing surface: P0 traced
stageValidRecords through this logic into ready paths.  Measure separately
from RD2 to avoid attributing the same cone saving twice.

### WR1 — table write decode and register enable network

Around lines 2696--2710, an admission writes the selected member, optionally
its pending suffix, and presence masks.  Audit mapped D-input hold muxes and
write-enable fanout.  Test explicit shared bank/ordinal decode across fields
and both records while preserving the optional-binding enable and concurrent
unrelated reads.  DC may already share enables; source repetition is not
evidence of waste.  This retains all state and clock-pin count and proposes
no clock gating.

### RC1 — ordinal-indexed reconciliation

Around lines 3424--3460, lookup compares 64 full bindings, reduces the hits
and priority-encodes the result.  Admission stores each accepted binding at
its validated ordinal; equality also compares that ordinal.

Use the ordinal to read one journal record, then retain full equality and
present/transition checks.  Check the full ordinal range before truncating
to six bits.  Preserve transition > same-cycle admission > stored journal >
unseen precedence.  Keep persistent records and full withdrawal payloads.
Tests must cover malformed/stale/late registration, same-cycle events and
backpressure.  This is a small independent candidate; DC may already factor
ordinal comparisons, and the indexed alternative adds a wide mux.  Do not
claim a 64-fold area reduction or any state reduction.

### MC1 — M2 production-control searches and updates

Around lines 1930--1995, 2034--2041 and 2252--2280, M2 retains 614 slot
occupied/generation records and visible keys, performs a 614-way first-free
selection and a 614-way handoff match, then selects and updates the slot.

Perform mapped-cone P0 attribution before choosing an implementation.  Initial
candidates are shared field decode, balanced match reduction and exact-priority
free selection.  A reverse layer index requires a stronger proof: handoff
has no slot field, and visible records can outlive prepared-group state.
Prove concurrent-live and generation/reuse behavior before replacing the
search.  Do not infer 36 visible slots from 36 layers or shrink capacity.
The entire owner's 4.85% top share bounds scope, not expected savings.

### PM2 — indexed stream events and redundant coordinates

Around lines 4097, 4151--4165, 4193--4208 and 4380--4385, stream index is
`Cat(layer, head)`, yet buildLayer/buildHead are stored in each stream slot.
Payload durability compares layer/head/page/generation/tag across 288 slots.

Derive coordinates from the slot and screen indexed event lookup with all
remaining identity checks.  Prove invalid-slot/range/truncation behavior for
every supported r5StreamSlots setting.  The mapped P0 retains 2,592 coordinate
cells with about 8,128.5 area: their removal alone is about 0.22% of top.
Additional comparator savings are unmeasured, so this is secondary to wrapper
work.  Preserve append, publication and reclaim ordering.

### EQ1 — conditional equal-address reuse

Production top connects M directly to C (`RouteAMeasurementDut.scala`, lines
314--316); generic wrapper tests independently drive C.  S/B also have an
ingress association, while F/B may use different ordinals.

Do not remove validation or assume equality for arbitrary inputs.  Generic
equal-index reuse needs address/shape predicates independent of ready/fire,
full fallback and invalid/stale tests.  The fallback may retain all original
hardware and add overhead; DC may already share production logic.  Rank below
RD2 until a mapped duplicate cone is demonstrated.

### STORE — larger storage realization study

The 366,336 table bits are live.  Payload reference and pending location handle
have different owners and no general equality proof.  Further large field
compaction is not established.

A larger state-cost change may require banked memory, latch or macro study,
including real storage/peripheral costs, every port's legal concurrency and
read timing.  Synchronous memory can change current combinational-read
semantics and needs explicit interface review.  This is separately scoped;
no free proxy, state deletion, capacity reduction or implicit added latency is
authorized by this inventory.

## Recommended order and acceptance

1. Target RD2's remaining read network; screen SEL1 independently.
2. Use RC1 as a bounded independent equivalence/small-synthesis experiment;
   perform MC1 mapped P0 attribution before M2 implementation.
3. Audit WR1 D-input/enable costs.  PM2 is a secondary small candidate;
   STORE is the separately scoped direction for a larger state-cost change.
4. Keep candidates separately switchable and measured.  Accept RD1's complete
   native result before choosing the cumulative integration successor.

Every implementation needs focused equivalence, matched small synthesis and
functional/input closure before separately authorized full paired DC.  The
current inventory reports opportunities, not predicted savings.  Area, timing
and cleanliness remain distinct; no PPA or system/hardware benefit follows.
