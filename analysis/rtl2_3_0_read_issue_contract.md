# RTL2.3.0 — read-issue descriptor contract

**Status:** implemented and directed tested.  This is the first RTL2.3
interface-only closure.  It freezes the immutable facts a later named source
owner must provide before its read candidate can be accepted by the existing
R2-to-R1 path.  It does not activate a candidate, R1 request, R2 grant,
response delivery, P3/S2/direct payload mutation, source deliverability, GQA,
R4, retirement, or an architectural scoreboard event.

The machine-readable companion is
[`rtl2_3_0_read_issue_manifest.json`](rtl2_3_0_read_issue_manifest.json).

## Exact logical descriptor

`ReadIssueDescriptor` is an immutable Chisel bundle and a `Decoupled` channel
factory only.  It has no production endpoint binding in this closure.  Its
fields are intentionally a direct logical refinement of the frozen
`page_read_req` contract:

```text
delivery_context_ref, candidate_class, transaction_identity,
source_kind, payload_handle_or_address, valid_count,
expected_generation_or_validity, destination_endpoint,
expected_fragment_count, target_descriptor
```

`payload_handle_or_address` remains an opaque core-side reference.  It does
not select an HBM address encoding, a physical memory map, a controller,
bursting, port count, or a sidecar transport sequence.  `valid_count` is the
frozen 0..64 semantic count; an owner-local default or reconstruction from a
response is forbidden.  The existing `DeliveryTargetDescriptor` retains the
P3/S2/direct association.  In particular, `requires_sidecar` plus the frozen
`PageRef` preserve the packed-sidecar obligation without choosing the sidecar
handle calculation or physical realization.

The descriptor also carries the existing `delivery_context_ref` and
`candidate_class`.  Therefore a future producer cannot create a read issue
whose context, class, identity, endpoint generation, or expected fragment
count are inferred after R2 acceptance.

## Owner and provenance boundary

This closure makes the source of each fact explicit; it does not add a
scheduler or a top-level adapter.

| Future read class | Read-issue fact owner | Endpoint owner | Source-kind fact | Handle/generation provenance |
|---|---|---|---|---|
| `pack_read` | R3 `route_a_m2_p3_wrapper` | R3 functional P3 endpoint | `pending` | R3's live pending/group association |
| `direct_pending` | R3 `route_a_m2_p3_wrapper` | `route_a_direct_pending_endpoint_v1` | `pending` | R3's live pending association and endpoint generation |
| `s2_packed` | R5 `route_a_page_manager` | `route_a_s2_gqa_source_wrapper` | `packed` | R5 published `PageRef`/descriptor; sidecar requirement is retained |
| `s2_full` | existing common Full-KV source owner | `route_a_s2_gqa_source_wrapper` | outside Route-A incremental payload path | existing Full-KV contract, unchanged |

R3 and R5 supply source facts; neither may choose R2 priority, credit,
within-class oldest selection, read rotation, request identity allocation, or
R1 acceptance.  R2 remains the sole owner of those controls.  S2 and direct
remain destination/source-service owners and may not reconstruct a handle,
`valid_count`, or generation from a response.  The top remains composition
only and does not construct this descriptor.

No core-memory read is legal for `source_kind=hot`: hot is supplied by the
common hot path, not R1.  This is a future producer legality rule, not a
runtime scheduler policy.

## Relation to existing R1 and scoreboard contracts

When a later behavioral slice is authorized, the producer must form the
existing `SourceCandidate.r1_request` and its immutable allocation from this
same descriptor before R2 exposure.  R1 sees a logical read only after the
existing R2 acceptance rule.  RTL2.3.0 does not alter the frozen R2 rotation
`s2_fill -> direct_pending -> pack_read`, and it does not use an R1 response
to fill any descriptor field.

No new scoreboard event is emitted here.  The existing versioned RTL2 schema
reserves `request_accept` for actual R1 acceptance and `fragment_deliver` for
actual typed response delivery; both remain owned by their existing named
owners.  A future adapter may expose a diagnostic `read_issue` observation
only as a non-architectural planning record, never as a substitute for either
event or as evidence of R1 acceptance.

## Directed evidence and limits

The interface-only harness drives a packed read descriptor through a direct
Chisel bundle mirror and checks every category of frozen fact, including the
opaque handle, `valid_count=64`, generation, expected fragment count, PageRef,
and sidecar requirement.  It introduces no state or production owner.

Run from `hardware/route_a/chisel`:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'testOnly kvpress.routea.rtl2.RouteAReadIssueDescriptorSpec'
```

Passing evidence is synthesizable interface/elaboration evidence only: no
model/GPU, cycle, latency, throughput, PPA, physical-memory, RTL
numeric-correctness, deadlock-freedom, or new A4 DSE claim.

Recorded result: JSON parse and `git diff --check` preflight passed; `Test /
compile` passed; `RouteAReadIssueDescriptorSpec` passed 1/1; and the affected
RTL2.2 registry/allocation-bridge/router plus structural-top regression passed
10/10.  These results validate bundle elaboration and non-regression only;
they do not activate a production read path.
