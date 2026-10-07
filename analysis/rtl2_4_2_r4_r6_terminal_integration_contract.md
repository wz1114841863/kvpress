# RTL2.4.2 — R4--R6 verification terminal-chain integration

**Status:** `complete_test_only_cross_owner_harness; attention_terminal_scoreboard_pending`.

## Scope and fixed chain

RTL2.4.2 binds the terminal association which RTL2.4.1 intentionally left
isolated:

```text
explicit verification R6MergeReady
  -> RouteALifecycleAdapter.merge_req
  -> RouteAMergeBoundary accepted active merge
  -> testbench_route_a_r4_result_stub_provider
  -> R4ResultStub XOR R4NumericFault
  -> RouteAMergeBoundary.merge_rsp_or_numeric_fault
  -> RouteALifecycleAdapter.merge_terminal_in
  -> RouteALifecycleAdapter.attention_terminal_rsp
```

Every arrow above is an existing owner-local or already-frozen cross-owner
carrier. The harness merely composes the real R6 lifecycle adapter, real R4
boundary, and test-scope provider. It does not instantiate the provider in
`RouteAKVSubsystemTop`, add an R6 terminal bypass, or introduce another
terminal consumer.

The harness's `merge_ready` input is explicitly a test stimulus for an
already-completed canonical source set. It invokes the pre-existing R6
`merge_ready -> merge_req` transition and does not produce packets, choose
hot/pending/packed sources, construct a source plan, release a source, or
schedule an endpoint.

## Cross-owner requirements exercised

| Requirement | Harness observation |
|---|---|
| R6 owns merge request and only R4 consumes it | An R6-attention tracker accepts the explicit nonempty `R6MergeReady`; its real `merge_req` is bulk-connected to the R4 boundary. |
| R4 owns active association | Provider observes only `r4_active_merge_observation`, which comes from the accepted R4 request. |
| One result/fault association | Test-scope provider remains success-XOR-fault and connects only to R4's existing two input slots. |
| R4 owns R6-facing terminal mapping | The only R4 output is `merge_rsp_or_numeric_fault`; a fault still maps to the existing zero-value numeric-fault response. |
| R6 owns outward terminal | Only `attention_terminal_rsp` leaves the harness; it carries identity and status after R6 accepts the R4 terminal. |

The terminal response does not expose or validate the opaque 4,096-bit success
value. Numeric semantics remain outside this closure.

## Directed executable coverage

The no-model ChiselSim harness covers:

1. a matching success scenario reaching the unique R6 outward success terminal
   while `attention_terminal_rsp` is held stable under ready-low;
2. a stale scenario being rejected with no outward terminal, followed by one
   matching numeric-fault scenario reaching the unique R6 outward fault
   terminal; and
3. destructive reset after provider acceptance clearing the in-flight chain so
   no outward terminal is produced.

The provider remains under `src/test`; only its test-scope visibility is shared
with this second test harness. This lets the same frozen behavior be composed
without duplicating a competing provider implementation. Earlier RTL2.4.1
provenance remains a historical byte snapshot of its then-reviewed test file.

## Deferred work and evidence boundary

RTL2.4.3 must bind this real `attention_terminal_rsp` to the versioned
scoreboard event schema and close event/oracle traceability. A later completion
review must still assess the complete R4 terminal slice.

RTL2.4.2 makes no claim about R4 partial arithmetic, `exp`, precision, online
merge, source-packet production, source schedule, page/authority behavior,
physical memory/controller selection, cycle latency, throughput, deadlock
freedom, area, energy, PPA, model/GPU execution, numerical correctness, or a
new A4 DSE.
