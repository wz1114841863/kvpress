# RTL1.2.0 — R2 semantic-carrier realization closure

**Status:** `complete_rtl1_2_carrier_refinement; no_r2_behavior_or_physical_queue_selection`.

## Purpose and boundary

This closure maps the already frozen Gate-A R2 semantic candidate and routed
response records onto the existing RTL0.2 logical ports
`source_candidate_to_r2` and `source_delivery_out`. It adds no top-level
logical port, architecture candidate, DSE, controller protocol, HBM timing,
physical FIFO depth selection, PPA claim, or change to pruning, admission,
mask, FIFO, ownership, credit, grant order, descriptor semantics, or atomic
publication.

The source port was intentionally opaque in RTL1.0. Its refinement is required
before R2 can create the already-selected R1 request or route a matching R1
response without inventing a side channel.

## Existing-port refinements

`source_candidate_to_r2` remains one ready/valid logical candidate port. Its
record carries:

```text
candidate_class, arrival_ordinal, candidate_id,
eligibility_snapshot,
r1_request { identity, request_kind, destination, address_ref,
             expected_fragment_count, fragment_index, last, data[511:0] }
```

`eligibility_snapshot` has the fixed R2 semantic bit meanings below. The
source supplies current facts; R2 alone evaluates the class-specific required
set and never treats an asserted bit as an authority transfer, publication,
or credit return.

| Bit | Meaning |
|---:|---|
| 0..3 | FIFO predecessor, ownership, logical source credit, destination ready |
| 4 | packed S2 metadata publication visible |
| 5 | pending payload authoritative |
| 6 | P3 stage ready/owned for pack read |
| 7..9 | page allocated, P3 complete, P3 owned for pack write |

The six candidate encodings are `s2_full`, `s2_packed`, `direct_pending`,
`pack_read`, `pack_write`, and `desc_maint_write`. Read rotation treats the
first two as the one frozen `s2_fill` class. All candidate and predicate
encodings are required Chisel elaboration parameters with no deployment
default.

R2 accepts a candidate snapshot only when every required predicate is already
true and an internal logical candidate slot is available. An ineligible source
keeps/re-presents its candidate after the relevant owner changes the supplied
fact; R2 does not latch a false predicate and later synthesize an unobserved
state update. This is backpressure only: it cannot drop, alter, reclassify, or
overtake a frozen FIFO predecessor.

`source_delivery_out` remains the existing ready/valid response-routing port.
It carries the matched `candidate_id`, `candidate_class`, destination, and the
complete R1 response `{identity, fragment_index, last, status, data}`. A
consumer receives no unmatched/stale response. The later S2/direct/R3/R5 owner
phases bind that existing logical delivery to their local state; RTL1.2 does
not implement those consumers.

## Finite implementation parameters

`r2CandidateSlotsPerClass` is a required Chisel elaboration parameter. It is
an implementation-local elastic-storage bound, not an A4 queue result, an
RTL-entry anchor parameter, selected physical FIFO depth, SRAM macro, service
rate, timing assumption, or PPA claim. Unit tests may choose a small local
value solely to exercise ordering/backpressure. A deployment integration must
name and separately validate a value.

R2 tracks one transport reservation per live R1 identity. This reservation is
created only on `core_mem_req.fire` and released only on the matched terminal
R1 response. It is distinct from source/M2/R3/R5 semantic credits: R2 checks
those as input predicates but does not return them, publish metadata, or move
authority.

## Deterministic selection

Read classes remain exactly:

```text
s2_fill -> direct_pending -> pack_read -> s2_fill
```

For any read class, the smallest `(arrival_ordinal, candidate_id)` eligible
candidate wins. The cursor advances only on accepted R1 request fire.

`pack_write` and `desc_maint_write` remain outside that rotation. Both use the
sole R1 write boundary; if both eligible write heads contend, R2 selects the
smallest `(arrival_ordinal, candidate_id)` without advancing the read cursor.
This is a lossless finite conflict resolver for the already-single write
boundary, not a new read class, scheduler, controller arbitration, or
throughput policy. Descriptor candidates are constrained to one expected
64-B fragment (`expected_fragment_count=1`, data fragment index zero, and
`last=1`); their durable terminal remains descriptor-only.

## RTL1.2 verification binding

RTL1.2 shall bind the existing R2 records as follows:

- `a_ready_low_nonmutation`: a stalled selected R1 request holds selected
  candidate, outgoing payload, cursor, transport reservation, and candidate
  storage state; R2 also backpressures new candidate acceptance in that case.
- `a_fifo_credit_losslessness`: grant requires the frozen class predicate,
  preserves within-class minimum ordinal/id, creates one reservation at fire,
  and releases it only at the matching terminal response.
- `p_credit_return`: remains an assumption-guarded, bounded protocol-progress
  test under eventual matching terminal delivery; it is not a latency claim.

Directed ChiselSim tests shall cover every source-specific guard, read rotation,
within-class order, R1 ready-low, response delivery backpressure, write/descriptor
separation, descriptor single-fragment validation, terminal success/fault
credit release, and fixed-seed legal interleavings. Python references remain
the semantic oracle inventory; no event adapter, model/GPU workload, numerical
datapath, controller, timing, or PPA evidence is added.
