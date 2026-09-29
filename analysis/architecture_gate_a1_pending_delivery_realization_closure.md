# Gate-A1 — pending-delivery realization closure

## Decision status and evidence boundary

**Status:** architecture closure for the pre-RTL Route-A interface; not a
performance DSE, RTL implementation, macro selection, or HBM-controller claim.

A4.13.1 freezes P3 as lossless pending-HBM backing plus a transient
`p3_payload_stage_page`; A4.13.4 freezes **logical** direct pending-source
delivery to the shared GQA fanout.  Neither artifact selects a physical direct
endpoint, an S2 reuse policy, a separate pending buffer, a transport command,
or an issue schedule.  The selection below is therefore a new, reviewable
architecture decision.  It is not described as an A4 measurement or inferred
through tokens/s, latency, energy, or GPU-workload comparison.

## Candidate closure analysis

| Candidate | Frozen-semantic fit | New persistent resource or representation | Interface consequence | Gate-A1 result |
|---|---|---|---|---|
| Reuse S2 for pending HBM | Possible only with new pending fill/ownership semantics | Reuses a common page buffer for a source that A4.13.4 accounts as record delivery; needs a pending page/segment formation rule and S2 allocation/release policy | Makes an existing packed/Full-KV page contract carry an unbound pending representation | rejected |
| Direct pending endpoint | Matches the A4.13.4 logical direct source action and P1/P3 pending-HBM traversal | No new pending payload residency; endpoint has transient transport state only | Adds one finite pending-source stream endpoint and its request/response/credit contract | **selected** |
| Separate pending buffer | Can be semantically correct only with a further copy/ownership discipline | Introduces a new persistent pending payload provision, macro/capacity and dynamic-access boundary | Requires allocator, fill, release, fault, and cost contracts absent from P3 | rejected |

This is a feasibility and interface-simplicity comparison, not a ranking of
throughput or energy.  S2 reuse and a separate buffer are not declared
incorrect in general; they are excluded because each adds an unbound source
organization or resource contract at this gate.

## Selected finite realization

`pending_delivery_realization = direct_pending_endpoint_v1` is frozen for the
Qwen anchor.  The endpoint reads the P3 pending-HBM authoritative payload and
delivers its frozen FIFO-ordered pending source sequence directly to the
common source mux/GQA fanout.  It does not allocate an S2 slot, materialize a
pending page, or create a persistent pending payload copy.

The direct endpoint is record-granular at its semantic boundary.  A record is
the existing `(layer, kv_head, logical_position, K, V)` pending member; for the
anchor, K+V has the existing 512-B logical payload size.  This does **not**
make 512 B an HBM transaction, burst, or physical port width.  The endpoint
must preserve the existing FIFO order and the canonical source order
`hot -> pending -> packed`; its transport may not reorder a pending record.

The pending source is a bounded, metadata-described sequence rather than an
S2 `READY` page.  Its control interface is:

```text
pending_source_open {
    request_id, layer, kv_head, ordered_pending_descriptor_ref,
    expected_generation_or_validity, destination=direct_pending_endpoint
}
pending_record_rsp {
    request_id, ordinal, logical_position, K, V, last, status
}
pending_source_close { request_id, status }
```

`ordinal` is strictly increasing from zero for a successful source and is
coupled to the frozen FIFO descriptor snapshot.  The endpoint may emit a
record to the common mux only after its matching metadata ownership/validity
check and its K/V payload are both available.  `last` plus a successful
`pending_source_close` establishes source completion.  Request-ID lifetime,
generation matching, stale response rejection, fault status, and backpressure
follow the common transport rules in `architecture_spec.md`; widths and
outstanding bounds remain Gate-A parameters.

For each direct pending source, consumer tracking is initialized once at
`direct_pending_source_deliverable`: the successful open and first
metadata/payload-deliverable record (or an explicitly represented empty source
identity).  Its four GQA consumer bits may clear only after that consumer has
committed all partial updates through the successful terminal record.  The
endpoint cannot return its control credit, expose a packed authoritative
residency, or release dependent state before all four consumers and their
pending-source partial updates complete.  This preserves the existing
multi-source online-merge contract without asserting a physical pipeline or
numeric format.

## Required consequences

1. Pending HBM remains the sole authoritative pending payload residency until
   the already-frozen atomic metadata publication transfers authority to
   packed HBM.  Direct transport and P3/S2 copies are transient mirrors only.
2. S2 remains common Full-KV/packed-page infrastructure.  It is not reserved,
   charged, or redefined for pending delivery.
3. The pending endpoint introduces no new area, dynamic-energy, latency,
   controller, wire, clock, or overlap result.  Those terms remain within the
   A4.14.1 omitted-cost budget and later Gate-A/B implementation accounting.
4. The selected endpoint must appear in the executable interface reference
   with directed checks for FIFO ordinal order, stale responses, terminal
   closure, four-consumer completion, backpressure, and the atomic
   pending-to-packed handoff.

No A4.14.x variant or workload comparison is authorized by this closure.
