# RTL2.4.0 — R4 verification-stub terminal contract

**Status:** `contract_frozen; behavioral provider and integration pending`.

## Purpose and boundary

RTL2.4 begins only after RTL2.3 has passed
`control_protocol_complete`. Its first closure freezes the finite,
verification-only association that may terminate one already-active R4 merge:

```text
R6 nonempty merge_req accepted by R4 boundary
  -> read-only active-merge observation
  -> explicit verification scenario
  -> exactly one success XOR numeric_fault offer
  -> existing R4 terminal response
  -> R6 only outward attention terminal
```

This contract does not add an arithmetic implementation. The scenario value is
opaque verification data; it is not calculated from R4 packets, K/V payloads,
source order, partial softmax state, or any floating-point operation.

## Frozen ownership and planned interfaces

| Fact / carrier | Owner | Consumer | Rule |
|---|---|---|---|
| accepted nonempty `merge_req` | `route_a_merge_boundary` | internal active-merge state | R4 remains the sole consumer of the R6 request. |
| `r4_active_merge_observation` | `route_a_merge_boundary` | verification-only stub provider | Read-only `Valid[MergeRequest]`; it asserts only while the boundary has one active accepted merge. It cannot backpressure or create a merge. |
| `R4StubScenario` | verification environment | verification-only stub provider | Explicit identity plus disposition and opaque value; neither R4 nor the provider derives it. |
| `r4_result_stub` / `r4_numeric_fault` | verification-only stub provider | `route_a_merge_boundary` | Exactly one mutually-exclusive terminal fact for the observed identity. |
| `merge_rsp_or_numeric_fault` | `route_a_merge_boundary` | R6 lifecycle adapter | The pre-existing sole R6-facing terminal path. |

`R4StubScenario` is frozen as a verification-harness bundle, not a production
top-level port:

```text
transaction_identity : RID + incarnation
disposition          : success | numeric_fault
normalized_value     : opaque 4096-bit value; meaningful only for success
```

RTL2.4.1 may introduce the provider and the boundary's read-only observation
port exactly as stated above. It may not add a second R6 terminal, an alternate
merge consumer, a result-dependent source release, or a top-level source
schedule.

## Acceptance and fail-closed rules

The provider may accept a scenario only if all of the following hold:

1. `r4_active_merge_observation.valid` is high;
2. the observed `source_presence` is nonempty;
3. scenario identity exactly matches the observed active merge identity;
4. no scenario/result/fault fact is already held for that merge; and
5. disposition is one of the two frozen encodings.

For `numeric_fault`, the scenario's opaque value must be zero. For `success`,
the provider copies the opaque 4096-bit value exactly and makes no numerical
claim about it. The provider holds one selected output stable until the R4
boundary accepts it. It never asserts success and fault together.

Empty, stale, reset-era, mismatched, duplicate, malformed-disposition, or
simultaneous terminal scenarios are ready-low and cannot mutate R4 or R6.
The existing boundary remains responsible for rejecting simultaneous
`r4_result_stub` and `r4_numeric_fault` inputs and for mapping a fault to zero
terminal value. R6 remains responsible for exactly-one outward terminal
consumption.

## Reset, progress, and non-goals

Destructive reset clears the boundary's active merge; any previously held or
later-arriving scenario then fails closed. A bounded progress test may assume
that the verification environment eventually supplies exactly one matching
scenario for an active merge and that R6 eventually accepts its terminal. This
is an environment fairness assumption, not a latency, throughput, or
deadlock-freedom claim.

RTL2.4.0 does not authorize:

- source partial arithmetic, `exp`, binary32 computation, precision choice,
  online merge, or numeric correctness;
- a production source-packet producer, scheduler, or endpoint ingress change;
- retry, Full-KV fallback/substitution, authority transition, publication,
  page operation, retirement, or reclaim behavior;
- HBM/SRAM/controller selection, cycles, timing, throughput, area, energy, or
  PPA claims.

## Planned evidence sequence

RTL2.4.1 will add the provider plus isolated success/fault/stall/stale/reset
tests. RTL2.4.2 will bind it with real R6 and `RouteAMergeBoundary` in a
cross-owner harness. RTL2.4.3 will activate the `attention_terminal`
scoreboard binding and run a separate completion review. The current closure
is contract/provenance only and makes no RTL behavior claim.
