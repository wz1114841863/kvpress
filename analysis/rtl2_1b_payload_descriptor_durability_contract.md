# RTL2.1b — payload durability and descriptor prerequisite

**Status:** implementation in progress; structural/top elaboration passed.

RTL2.1b activates the minimum functional path that RTL2.1a deliberately left
inert:

```text
hot-owner payload/position egress
  -> R3 replaceable P3 functional backing
  -> R3 pack-write candidate
  -> sole R2 ingress / sole R1 boundary
  -> R3 payload-durable fact
  -> R5 private descriptor maintenance
  -> R5 aggregate DescriptorDurabilityPrerequisite
  -> R3 private publication prerequisite
```

The top remains composition-only. It constructs none of the payload,
sidecar, candidate, endpoint key, page association, descriptor result, or
authority facts.

## Functional-storage boundary

R3 retains exactly the frozen logical P3 capacity using a flat, replaceable
reference backing: `36 * 64 * 8` 64-B payload fragments and `36 * 64` logical
8-B position-sidecar entries. Its flat indexing is solely a functional model
of the already-frozen layer-local envelope; it is not a selected SRAM macro,
port count, controller schedule, physical address mapping, timing, throughput,
area, energy, or PPA claim.

The hot owner is still the only payload provenance owner. Its new top-level
egress is accepted only after the immutable R6/R3 admission association is
complete, in canonical record ordinal and fragment order, with every
`payload_ref` and logical position checked against that association. P3 is a
transient non-authoritative copy; pending remains authoritative.

## Durable-write and descriptor ordering

R3 alone creates the pack-write request/data candidate from a complete stage.
It uses the one existing R2 candidate ingress and the one existing R1 external
memory boundary. Its R1 opaque address handle is the R5-owned logical payload
offset association `page_id * 33,280 B`, not a physical HBM address or base
mapping. A successful R1 terminal emits `P3PayloadDurable` only; it does not
publish metadata or transfer authority.

Only the matching R5 active append accepts that fact. R5 then emits its private
new-page descriptor operation and, only when the allocation reported a prior
tail, its private tail-link operation. The functional descriptor image preserves
the frozen four 128-bit lanes per 64-B descriptor line, but is replaceable
reference backing rather than a descriptor-HBM implementation.

R5 emits exactly one held `DescriptorDurabilityPrerequisite` carrying the
fixed mask: `01` for new-page only or `11` for new-page plus tail-link. R3
accepts it only on an exact `(layer, kv_head, PageRef including generation,
group tag)` match and exact required/durable masks. Fault makes the stage
non-publishable. Successful receipt records a private prerequisite; it does
not invoke `metadata_publish_commit`. RTL2.1c remains the only gate that may
activate the existing atomic publication/authority path.

## Explicitly excluded

No pruning, admission, page size, M2 organization, queue/scheduler policy,
P3 physical mapping, S2/direct delivery, read router, M2 private member
production, metadata publication, packed authority transition, numeric R4,
HBM controller, timing, throughput, energy, or PPA behavior is introduced.

## Verification state

`RouteAKVSubsystemTopSpec` elaborates the new ownership/composition graph.
The legacy R3/R5 simulation suite is being updated for the new required
descriptor prerequisite; it is not recorded as passing until that update and
the new actual R2/R1 end-to-end directed harness complete. This document makes
no RTL-correctness or performance claim from structural elaboration alone.
