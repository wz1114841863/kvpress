# RTL2.3-C4 — packed-authoritative page read to S2 closure

Status: closed as a pure functional RTL integration harness.

## Functional boundary

`RouteAPackedS2ReadProducer` captures one immutable packed-page work item,
then holds its fill-open association until the target logical S2 slot accepts
the same transaction identity and page reference. It cannot issue the R1 read
until that happens. It then uses the existing C1 allocation bridge, R2, R1,
registry, and typed delivery router. `RouteAPackedS2ReadEndpoint` is the sole
resolved read-response consumer for this harness.

`valid_records` is frozen before issue and preserves tail pages. Payload count
is exactly `valid_records * 8` logical 64-B fragments. Thus a full 64-record
packed page is exactly 512 fragments and 32 KiB of payload; a tail page has its
smaller valid-record count. The endpoint explicitly widens the nine-bit final
fragment index before comparing one-past index 512, so a valid final full-page
fragment cannot wrap to zero.

For every successful R1 response, the endpoint serializes the payload handoff
before the matching S2 terminal handoff. This matches the existing S2 owner's
payload-before-terminal validation. Position sidecars stay on the existing,
separate S2 sidecar ingress: `expected_sidecar_records = valid_records`, and
S2 cannot become `READY` until all payload/terminal facts and the matching
sidecar completion have arrived.

## Ownership and non-claims

The packed-page manager remains owner of packed-page validity and metadata
publication; S2 remains owner of slot state, functional backing, READY, and
four-consumer release. C4 owns neither page allocation, publication, source
packet emission, R4, numeric merge, authority, a top-level source schedule,
sidecar-content production, an HBM controller, or an S2 macro/port choice.
Payload and S2 are transient and never authoritative residency.

The production top remains intentionally inactive for this work carrier. C4 is
an integration witness, not a production source-service or end-to-end Route-A
claim.

## Fail-closed rules

| Condition | Required result |
| --- | --- |
| stale external identity | consumed by R1; no S2 payload/terminal mutation |
| S2 identity, page, slot state, or generation mismatch | no response acceptance or S2 mutation |
| mismatched producer generation | fill-open is held; no R1 request issues |
| matching R1 terminal fault | S2 becomes `FAULTED`; no payload or release |
| malformed matching response | R1 normalizes fault; no payload deposit or READY |
| incomplete or mismatched sidecar | S2 remains non-READY |

## Directed no-model verification

`RouteAPackedS2ReadPathSpec` covers:

1. a full 64-record page: 512 payload fragments, 64 sidecars, READY, functional
   payload reads, and four-consumer release;
2. a one-record tail page after a stale external response;
3. generation, page-reference, and S2-slot mismatch before issue;
4. matching terminal fault; and
5. malformed matching fragment normalization.

```bash
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'testOnly kvpress.routea.rtl2.RouteAPackedS2ReadPathSpec'
```

Evidence labels: synthesizable functional control/dataflow RTL and directed
Chisel simulation; no model/GPU; no timing, throughput, physical-memory,
controller, numeric-correctness, PPA, or new-A4-DSE claim.

The next closure is source packet/R4 composition, not a new packed-page DSE or
S2 realization selection.
