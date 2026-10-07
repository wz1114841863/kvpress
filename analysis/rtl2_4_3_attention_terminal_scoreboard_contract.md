# RTL2.4.3 — attention-terminal scoreboard and Python-oracle binding

**Status:** `complete_testbench_event_oracle_binding; rtl2_4_completion_review_pending`.

## Fixed event meaning

RTL2.4.3 activates exactly one event record from the existing versioned RTL2
vocabulary:

```text
R4-origin r4_to_r6_terminal
  -> R6 accepts the named terminal
  -> R6 outward attention_terminal_rsp
  -> same-handshake testbench attention_terminal event
  -> Python R6 lifecycle reference
```

The schema's architectural origin remains `route_a_merge_boundary` and
`r4_to_r6_terminal`. The testbench observation point is deliberately the
named R6 outward terminal because it is the sole externally visible terminal
after R6 accepts that R4-origin fact. The binding compares only
`(request_id, incarnation, terminal_status)`; it neither treats the R6 output
as a new architectural origin nor infers an event from arbitrary state.

The active phase overlay now marks only this event as
`bound_and_emittable_in_rtl2_4_3_test_harness`. The historical RTL2 v1.0 event
schema and RTL1-V schema remain byte-unchanged historical records.
The RTL2.4.2 terminal-chain manifest remains its historical source snapshot;
the separate RTL2.4.3 binding below hashes the current extended harness rather
than rewriting that earlier freeze.

## Chisel carrier adapter

`testbench_route_a_attention_terminal_scoreboard_adapter` is test-scope only.
It pass-throughs the real R6 `attention_terminal_rsp` and emits one event only
when that terminal is accepted. Both output carrier and event have identical
identity/status and are accepted in the same handshake. A scoreboard-event
ready-low interval therefore delays the terminal legally in this harness; it
does not manufacture an event, create a second terminal, or make a latency
claim. The frozen one-bit status domain has exactly `success=0` and
`numeric_fault=1` encodings.

The R4--R6 harness from RTL2.4.2 now observes this adapter on real success and
fault terminal paths. Stale scenario and destructive-reset paths still create
no terminal and hence no event.

## Python-oracle adapter

`RouteARTL2AttentionTerminalScoreboardAdapter` validates the binding JSON,
requires exactly the three frozen event fields, then calls the existing
`RouteALifecycleAdapterReference`:

- `success=0` calls `terminal_attention(..., success=True)`;
- `numeric_fault=1` calls `merge_numeric_fault(...)`;
- duplicate, stale, reset-era, malformed-field, or unknown-status events fail
  closed.

Session, accepted attention, and all-GQA-complete facts are explicit
testbench mirror setup before terminal observation. They are not additional
RTL2 events and cannot be reconstructed from internal Chisel state. The
adapter has no R4 value/numeric payload, source scheduling, retry, or Full-KV
fallback interface.

## Evidence boundary

The binding is a no-model Chisel/Python executable event contract. It does not
prove R4 arithmetic or numeric correctness, RTL equivalence, full Route-A
end-to-end behavior, deadlock freedom, timing, throughput, PPA, or a new A4
DSE. RTL2.4 still requires its separate completion review.
