# RTL2.3-C3 — direct-pending endpoint closure

Status: closed as a pure functional RTL integration harness.

## Frozen functional boundary

One admitted pending record is 512 B and is transported as exactly eight ordered 64-B R1 read fragments. `direct_source_last` marks the last record of a direct source and is distinct from `record_last_fragment`, which is true only for fragment seven of that record.

The C3 path is `DirectPendingReadWork -> R2/R1 -> registry -> typed router -> RouteADirectPendingReadEndpoint -> RouteADirectPendingEndpointV1`. The endpoint accepts a fragment only when the delivery target, request identity, current direct-endpoint identity, and endpoint generation agree. Successful payload fragments are transient transport observations; they are neither S2 state nor authoritative residency.

The existing direct-pending endpoint owns source deliverability and the frozen four-consumer GQA completion/release rule. C3 emits a record terminal only after its eighth successful fragment, or after a matching R1 terminal fault. It does not emit an R4 source packet, invoke merge, create a pending buffer, reuse S2, or activate a top-level producer.

## Fail-closed rules

| Condition | Required C3 result |
| --- | --- |
| stale external response identity | consumed by R1; no direct payload, terminal, READY, ownership, or release mutation |
| target, current identity, or endpoint-generation mismatch | no direct payload or terminal handoff |
| malformed matching fragment | R1 normalizes it to terminal fault; no payload handoff |
| matching R1 terminal fault | direct fault terminal only; no payload handoff or GQA release |
| successful record fragments 0 through 6 | transient payload only; no direct record terminal |

`valid_count` is checked as a legal 1..64-byte R1 request field, while C3 freezes the semantic expected response count for a pending record at eight fragments. This is a functional transaction contract, not a physical HBM request, port, timing, throughput, storage-macro, numeric, or PPA claim.

## Evidence and verification

The directed Chisel harness covers one complete eight-fragment record and four-consumer release, stale identity, endpoint-generation mismatch, matching terminal fault, and malformed matching response. It contains no model or GPU invocation and no top-level behavioral activation.

Commands run after this closure:

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'testOnly kvpress.routea.rtl2.RouteADirectPendingReadPathSpec'
```

The next isolated endpoint closure is C4, packed authoritative read to S2. Source-packet/R4 composition remains outside C3.
