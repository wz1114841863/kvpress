# RTL2.3-C8 — four-consumer completion and R6 merge-request closure

**Status:** `implemented_directed_tested; verification_packet_integration_only`.

C8 closes the control-protocol segment after C7's owner-observation boundary:
an R4 `ConsumerPartialCommit` is routed to exactly one matching source owner;
that owner releases its exact generation-bearing `SourceInstance` only after
four distinct consumer commits; and R6 emits one `merge_req` only after every
present source in the immutable plan has released.

The machine-readable provenance record is
[`rtl2_3_c8_four_consumer_completion_manifest.json`](rtl2_3_c8_four_consumer_completion_manifest.json).

## Named commit routing and ownership

`route_a_source_commit_demultiplexer` is the sole C8 composition child between
the R4 merge boundary and the source owners.  It has no source state, plan,
payload, or release counter.  It accepts a commit only when:

```text
R4 header source_kind == source_instance.source_kind
                         in {hot, pending, packed}
```

and then copies exactly `transaction_identity`, `SourceInstance`, and
`consumer_id` to that one owner.  A kind disagreement or unsupported kind is
`ready`-low and cannot mutate any owner.  The respective existing owner-local
trackers retain the release obligation:

```text
four distinct matching consumer commits
  -> exactly one SourceRelease(identity, SourceInstance)
  -> R6 validates against its immutable plan
```

This preserves the frozen canonical packet order `hot -> pending -> packed`.
It neither selects that order as a scheduler policy nor claims arbitrary
reordering is bitwise equivalent.

## Full control sequence exercised

The C8 integration harness connects the real
`route_a_hot_source_path`, `route_a_direct_pending_endpoint_v1`,
`route_a_s2_gqa_source_wrapper`, source packet adapter, R4 boundary, named
commit demultiplexer, and R6 lifecycle adapter.  It deliberately supplies
owner activation/fill controls and structural source packets from its test
environment.  Those packets are exactly the C5 verification packets, not
hot/direct/S2 payload arithmetic, a numerical partial, or a production source
packet generator.

For each of the seven nonempty masks, the harness proves:

1. each present owner sees four exact matching R4 consumer commits;
2. its local release reaches R6 with the planned identity, kind, coordinate,
   and generation;
3. R6 does not issue `merge_req` after any strict subset of present releases;
4. R6 holds one matching `merge_req(identity, source_presence)` after the final
   release, and no second request appears after its handshake.

The separate directed case holds a one-source transaction after three commits,
then admits the fourth and observes the only R6 merge request.  A focused
router case proves a header-kind/sideband-instance disagreement cannot be
accepted or forwarded.

## C8 boundary

The C8 carrier behavior is sufficient to make the architectural
`consumer_partial_commit`, `source_release`, and `merge_request` protocol
observable in directed RTL integration.  No host-side RTL2 scoreboard-event
adapter has been added; C8 does not infer events from arbitrary internal state.
The historical schema and its active phase overlay remain unchanged.

C8 does not make top-level source opens, direct record terminals, S2 fills, or
verification packet ingress into a live production endpoint.  That replacement
of isolated C2/C3/C4 witnesses is precisely C9.  C8 also does not add an R4
result/fault producer, outward terminal, retirement, reclaim, numeric merge,
physical memory/controller behavior, cycle/timing/throughput, area, energy,
PPA, model/GPU, or A4 DSE claim.

## Reproduction

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  'Test / compile' \
  'testOnly kvpress.routea.rtl2.RouteAFourConsumerCompletionSpec' \
  'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec'
```
