# RTL1.4.0 — S2/direct-pending semantic-carrier closure

## Status and boundary

**Status:** `complete_nonphysical_s2_direct_control_carrier_closure; rtl1_4_control_complete_at_module_scope`.

This record freezes only the module-local control carriers needed for the
already-selected two-slot common S2/GQA wrapper and the Gate-A1
`direct_pending_endpoint_v1`. It does not modify a top-level Route-A port,
create a source-mux owner, connect R4 numeric merge, or implement R6 terminal
or retirement behavior. The top ties these local carriers inactive until the
owner integrations exist.

No carrier here selects an S2 SRAM macro/bank/port, a direct-pending buffer,
an HBM command, a burst, a controller schedule, a multicast network, a merge
numeric format, timing, throughput, energy, or PPA result.

## S2 control carrier

`s2_service_req` remains the existing lifecycle-to-S2 allocation request. A
matching local fill sequence is:

```text
s2_service_req { identity, page_ref, s2_slot }
  -> s2_fill_open { identity, page_ref, slot, source_generation,
                    expected_fragment_count, requires_sidecar }
  -> ordered s2_fill_terminal { identity, slot, source_generation,
                                fragment_index, last, status }
  -> optional s2_sidecar_complete { identity, slot, source_generation }
  -> S2 READY
```

The two fixed S2 slots remain common Full-KV/packed source infrastructure.
`requires_sidecar` is true only for the Route-A packed source path. A slot
cannot become READY until the matching successful final fragment has arrived
and, when required, the matching sidecar-complete event has arrived. The
carrier tracks fragment ordinals and completion only; it does not store the
32-KiB payload or 512-B sidecar.

Each accepted service request increments that slot's local source generation.
A fill terminal with an old identity, slot generation, or page association is
not accepted and cannot alter a reused slot. A fault is fail-closed and never
produces READY or release. This is the module-local refinement of the existing
R1 stale-response boundary, not a second R1 response path.

## Direct-pending control carrier

The existing `pending_source_open` stays the sole endpoint-open boundary. Its
matching local terminal carrier is:

```text
direct_pending_record_terminal {
    identity, endpoint_generation, ordinal, last, status, explicit_empty
}
```

It denotes that the matching metadata-valid pending record (or explicit empty
identity) and its payload traversal are deliverable. It intentionally carries
no stored K/V data: direct pending remains an endpoint transport association,
not a pending page, S2 allocation, or persistent pending buffer. For a
non-empty source, ordinal starts at zero and increases by one. `last` closes
the source only after the matching ordinal. `explicit_empty` is legal only as
ordinal zero with `last`; it does not infer emptiness from an absent response.

Every endpoint open increments a local endpoint generation. A stale old
terminal is not accepted and cannot change the active endpoint, release state,
or an S2 slot. Direct pending may never allocate an S2 slot. Pending HBM stays
authoritative until the already-frozen R3 publication action.

## Four-consumer completion and release

Both source owners receive the same local control carrier:

```text
gqa_consumer_commit {
    identity, source_is_direct, source_slot, source_generation, consumer_id
}
source_release {
    identity, source_is_direct, source_slot, source_generation
}
```

`source_slot` is meaningful only for S2; direct uses its one finite endpoint
instance. `source_generation` distinguishes a reused slot/endpoint from a
stale response or commit. A source initializes four consumer bits exactly once
when it becomes deliverable. A matching consumer can clear its own bit once.
Release is legal only after a successful source terminal and all four consumer
bits have cleared; ready-low may delay release but may not mutate the
identity/generation/bitmap. The selected four-consumer rule is logical GQA
completion, not physical multicast, consumer pipeline, or latency evidence.

The global matrix owner for `a_gqa_release` remains
`route_a_s2_gqa_source_wrapper`. The direct endpoint implements the same local
safety rule but does not reassign any frozen owner or preempt R6's exactly-one
terminal behavior.

## Deliberately deferred integration

The existing top-shell `source_partial_to_merge` and
`consumer_partial_commit` ports remain structurally present but inactive in
RTL1.4. A future R4/R6 integration must explicitly bind canonical
`hot -> pending -> packed` source ordering and map the R4 commit to the local
generation-bearing carrier. RTL1.4 does not silently make the top a new
stateful source mux or infer that source reordering is numerically equivalent.

## Evidence label

This is a no-model RTL-entry control-interface closure. It makes no model/GPU,
timing/throughput, controller/HBM, numeric-datapath, PPA, end-to-end RTL
correctness, or new A4-DSE claim.

## RTL1.4 implementation binding

`RouteAS2GqaSourceWrapper` implements only two-slot identity/generation,
fill/sidecar completion, READY, four-bit GQA completion, and release control.
`RouteADirectPendingEndpointV1` implements only one direct endpoint's
identity/generation, FIFO ordinal/close/fault, four-bit completion, and
release control. Neither module stores source payload/sidecar bytes or
connects to R4/R6.

`RouteAS2DirectPendingSpec` is the directed no-model module-level check. It
covers packed sidecar-before-READY, all-four-commit release, ready-low release
stability, reused-S2 stale terminal rejection, direct FIFO ordinal, direct
stale terminal rejection, and direct fault nonrelease. `a_gqa_release` is
bound at its frozen S2 owner; direct endpoint checks the corresponding local
safety condition without changing matrix ownership.
