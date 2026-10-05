# RTL2.3-C9 — authorized top endpoint composition

**Status:** implemented and no-model directed/structural verification passed.

## Purpose

C9 replaces the three isolated C2/C3/C4 read-endpoint router attachments with
one composed-top path:

```text
R2/R1 response
  -> delivery-context registry
  -> typed delivery router
  -> C9 descriptor-only read-endpoint demultiplexer
  -> { R3/P3 pack-read | direct-pending | packed/S2 }
```

The registry allocation remains the only association authority.  The C9
demultiplexer accepts only the stored candidate class plus target kind; it
does not infer an endpoint from R1 response fields, create an identity,
select a source plan, or schedule a source.

## Explicit verification ingress

`route_a_kv_subsystem_top` now exposes named `verification_*` ingress carriers
for the already-defined C2/C3/C4 work and owner-open prerequisites.  They are
test-environment carriers, not deployed producer interfaces and not a second
owner.  They exist so the composed hierarchy can exercise the existing
functional endpoint contracts before a later authorized producer realization.

The top only combines a lifecycle-owned S2/direct open with its corresponding
verification ingress under an explicit one-producer exclusion.  Simultaneous
offers assert/fail closed; C9 deliberately does not introduce a priority
policy, arbitration rule, queue depth, source schedule, or service rate.

The pre-existing hot P3 ingress and C2 P3 pack-read ingress similarly meet at
`route_a_exclusive_p3_pending_ingress`.  It forwards exactly one input and
asserts on simultaneous offers.  This preserves the absence of any newly
chosen P3 service ordering.

## Endpoint binding

| Frozen endpoint | C9 binding | Preserved fail-closed condition |
|---|---|---|
| C2 `P3PendingRead` | demux -> `route_a_r3_pack_read_endpoint` -> exclusive P3 ingress -> R3 | class/kind, identity, generation, member ordinal, fragment count/index, terminal status |
| C3 `DirectPendingRead` | demux -> `route_a_direct_pending_read_endpoint` -> direct terminal owner | owner active identity/generation and exact eight-fragment terminal contract |
| C4 `S2PackedFill` | demux -> `route_a_packed_s2_read_endpoint` -> S2 payload/terminal owner | slot/page/identity/generation, sidecar prerequisite, 1..512 fragments and terminal status |

The direct payload fragment egress is intentionally an explicit verification
transport output.  It is not source storage, a numeric partial, or an R4
input.  S2 sidecar ingress remains a distinct existing interface and is not
constructed or transformed by C9.

## Top-level logical carrier bound

Because the composed top now contains C4's fixed 64-record packed-page
endpoint, `coreMemoryFragmentCountWidth` must represent the one-past full-page
count `512` (minimum 10 bits) and `coreMemoryFragmentIndexWidth` must represent
`0..511` (minimum 9 bits). This is a logical interface/elaboration bound from
the frozen 64-token page contract. It is not an SRAM port count, HBM command
format, controller width, timing choice, or physical realization claim.

Any test-only top harness must either use these bounds or intentionally avoid
instantiating the composed C4 path; it must explicitly tie the named C9
verification ingress inactive when testing unrelated control behavior.

## Non-goals and retained boundaries

This closes only control/dataflow attachment.  C9 does **not** activate:

- opaque C5/C7 verification packet offers as numeric source partials;
- a source scheduler, cross-member issue policy, multi-outstanding policy, or
  response-reordering policy;
- R4 arithmetic, result/fault terminal producer, FP format, online merge, or
  numeric correctness;
- physical HBM/SRAM controller behavior, queue physicalization, timing,
  throughput, area, energy, or PPA claims.

All stale, mismatched, generation-invalid, malformed, and fault endpoint
checks remain in the pre-existing C2/C3/C4 functional endpoint modules.  C9
only makes their common descriptor-selected composition explicit.

## Required evidence

The companion manifest hashes the shared router, top, endpoint-harness tests,
and living navigation edits, and records the exact no-model Chisel command.
The relevant tests retain C2/C3/C4 positive plus stale/mismatch/fault
fail-closed coverage through the new common demultiplexer; the structural top
test elaborates all C9 child modules and top verification ports.
