# RTL2.4.1 — isolated R4 verification-stub provider

**Status:** `complete_isolated_test_scope; r4_r6_integration_and_scoreboard_pending`.

## Scope and ownership

RTL2.4.1 realizes only the finite verification provider frozen by RTL2.4.0:

```text
RouteAMergeBoundary accepted merge
  -> r4_active_merge_observation (read-only)
  -> testbench_route_a_r4_result_stub_provider
  -> R4ResultStub XOR R4NumericFault
```

`RouteAMergeBoundary` remains the sole consumer of R6 `merge_req`; it stores
the accepted identity and nonempty source-presence mask, then exposes them as
`Valid[MergeRequest]` while that merge remains active. The observation carries
no ready signal and cannot create, backpressure, reorder, or retire a merge.
It remains valid while R4 holds an unconsumed result/fault terminal and clears
only after that terminal has left R4.

`testbench_route_a_r4_result_stub_provider` is deliberately defined under
`src/test`, not instantiated in `RouteAKVSubsystemTop`, and owns no production
top-level port. The testbench remains the owner of explicit scenario input.
The provider has no R6, source packet, source-release, admission, authority,
publication, page, retirement, or reclaim interface.

## Frozen scenario and behavior

The test-only `R4StubScenario` fields are unchanged from RTL2.4.0:

| Field | Encoding / rule |
|---|---|
| `transaction_identity` | Exact `(request_id, incarnation)` match to active observation. |
| `disposition` | Two-bit code: `success=0`, `numeric_fault=1`; `2` and `3` are malformed. |
| `normalized_value` | Opaque 4,096-bit payload for success only; it must be zero for numeric fault. |

A scenario is accepted exactly when there is an active, nonempty observation,
its identity matches exactly, its encoding/value are legal, and neither a held
nor a completed scenario exists for that active identity. An accepted scenario
is copied into provider-held state. The provider exposes exactly one output:

- `success` produces only `R4ResultStub`, preserving the opaque value; or
- `numeric_fault` produces only `R4NumericFault`.

The selected output stays stable until R4 accepts it. After that acceptance,
the provider records the completed identity and refuses a duplicate while R4
continues to expose that same active incarnation. A changed or invalid active
observation releases that completed guard; exact incarnation matching prevents
an old request-ID incarnation from matching a reuse. Destructive reset clears
both held and completed provider state.

The provider rejects without mutation: no active merge, empty source presence,
stale/unknown/mismatched identity, malformed disposition, nonzero fault value,
or a duplicate. Its construction asserts that success and fault valid cannot
be high together. Environment-provided scenario stability while valid and
ready-low remains an assumption; provider-output stability is checked locally.

## Directed executable evidence

The no-model ChiselSim suite covers:

1. exact success and opaque-value preservation through result ready-low;
2. fault-only output and rejection of nonzero fault payload;
3. no-active, empty, stale, mismatched, malformed, and nonzero-fault
   fail-closed inputs; and
4. reset clearing plus request-ID reuse under a new incarnation.

`RouteAMergeBoundarySpec` additionally checks that its new observation is
absent before acceptance, retains the accepted identity/source mask while an
R4 terminal is held, and clears when the terminal leaves R4.

This is pure-software control evidence. It is not an R4 numeric
implementation, R4--R6 integration proof, terminal-scoreboard proof,
cycle/timing/throughput result, PPA claim, model/GPU result, or new A4 DSE.

## Deferred work

RTL2.4.2 must connect this provider with a real `RouteAMergeBoundary` and R6
lifecycle terminal path in one harness. RTL2.4.3 must then bind
`attention_terminal` to the versioned scoreboard-event schema and perform its
own completion review. Neither obligation is closed by this isolated provider.
