# RTL2.3-C2 — R3 pending-member pack-read endpoint closure

**Status:** implemented and directed tested in one minimal integration harness.

## Scope

```text
explicit R3 member work
  -> R3 immutable ReadIssueDescriptor
  -> existing read-candidate adapter
  -> RTL2.3-C1 sole registry-allocation bridge
  -> existing R2 read ingress / R1 core-memory path
  -> registry-resolved typed read delivery
  -> R3 pack-read endpoint
  -> existing P3 functional backing
```

`RouteAR3PackReadPathHarness` composes existing R2, R1, registry, typed router,
and `RouteAM2P3Wrapper`. It introduces no parallel memory transport, top-level
mux, authority owner, source packet, S2/direct endpoint, publication, numeric
implementation, or physical storage/controller model.

The production top exposes the R3 work/issue boundary as inactive. C2 does not
activate it there: that would choose a live work producer and hot-versus-pack
P3 ingress composition rule outside this narrow closure. C2 is a component
integration witness, not a claim that top-level source service is complete.

## Frozen C2 transaction association

| Fact | C2 rule |
|---|---|
| Granularity | One retained member maps to exactly one `pack_read`. |
| Fragment count | `expected_fragment_count = 8`, eight logical 512-bit / 64-B fragments. |
| Member identity | `payload_ref` must equal immutable R3 admission-member ledger entry. |
| P3 slot mapping | `p3_index = member_ordinal * 8 + fragment_index`. |
| Response association | Class, target, identity, generation, count, ordinal, and status are checked before endpoint acceptance. |
| Reference versus handle | `p3_member_payload_ref` is immutable P3 association; `payload_handle_or_address` remains a parameterized opaque R1 reference. |
| Sidecar | Existing P3 sidecar binding remains separately required for `COMPLETE`; C2 adds no sidecar transport. |

`RouteAM2P3Wrapper` accepts `P3PackReadWork` only when it matches a live claimed
stage and immutable member ledger. It derives layer, stage generation, valid
count, group tag, member `payload_ref`, source kind, and fixed count from
checked work plus local state. `RouteAR3PackReadEndpoint` uses only the
registry-resolved allocation descriptor to create `P3PendingFragment`; response
data never creates or reconstructs a member association.

The single explicit work carrier is a conservative functional baseline, not a
permanent serial issue requirement or scheduler decision. C2 makes no claim
about four-live-read utilization, issue rate, response overlap, or a future
multi-member reorder buffer. Any multi-outstanding implementation requires its
own association/reorder closure.

## Fail-closed behavior

| Condition | Required C2 outcome |
|---|---|
| Work ref, stage generation, or ordinal mismatches R3 state | No acceptance, R1 request, or P3 deposit. |
| External stale identity | R1 consumes it as stale; no R2 source delivery or P3 mutation. |
| Typed endpoint class, target, identity, generation, count, ordinal, status, or terminal convention mismatches | Endpoint is not ready; no P3 deposit. |
| Matching R1 terminal fault | P3 fault control only; P3 becomes `FAULTED`, not `COMPLETE`. |
| Malformed matching R1 fragment sequence | R1 normalizes terminal fault; no payload deposit or P3 `COMPLETE`. |

P3 remains sole owner of backing and `COMPLETE`. Payload/descriptor durability,
publication, authority, source deliverability, four-GQA completion, R4, R6,
and Full-KV fallback are outside C2.

## Directed no-model verification

`RouteAR3PackReadPathSpec` has four independently runnable tests:

1. one immutable member emits one eight-fragment R1 read and reaches P3
   `COMPLETE` only after existing sidecar binding;
2. mismatched member work is refused, and stale external identity cannot mutate
   P3 before a valid transaction completes;
3. a matching terminal fault marks P3 `FAULTED` without payload deposit;
4. an out-of-order matching response is normalized fail-closed and cannot
   complete P3.

```text
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch 'Test / compile'
# PASS
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  "testOnly kvpress.routea.rtl2.RouteAR3PackReadPathSpec -- -z \"maps one immutable\""
# PASS, 1 test
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  "testOnly kvpress.routea.rtl2.RouteAR3PackReadPathSpec -- -z \"without P3 deposit\""
# PASS, 1 test
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  "testOnly kvpress.routea.rtl2.RouteAR3PackReadPathSpec -- -z \"fault control\""
# PASS, 1 test
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  "testOnly kvpress.routea.rtl2.RouteAR3PackReadPathSpec -- -z \"malformed fragment\""
# PASS, 1 test
```

Evidence labels: synthesizable functional-control/dataflow integration evidence;
no model/GPU; no cycle/timing/throughput claim; no PPA claim; no RTL
numeric-correctness claim; no new A4 DSE.

## Non-claims and next closure

C2 does not prove a physical P3 macro, port count, SRAM/HBM energy, controller
behavior, latency, throughput, deadlock freedom, numeric attention correctness,
or end-to-end Route-A correctness. It does not reopen pruning, admission, page
size, M2 organization, queue/scheduler semantics, P3 mapping, S2 count, GQA
legality, or atomic publication.

The safe next source-service closure is a separately named direct-pending or
packed-S2 endpoint path. Only after both are closed may source packets,
canonical `hot -> pending -> packed` composition, four-consumer commits, and
the R4 boundary activate.
