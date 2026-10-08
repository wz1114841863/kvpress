# RTL2.5.2 — fault / terminal cross-owner closure

**Status:** `complete_directed_fault_terminal_evidence; retirement_reclaim_pending`.

## Scope

RTL2.5.2 closes the existing R4-to-R6 numeric-fault terminal path in a
test-scope composition.  It reuses the real `route_a_merge_boundary` (R4),
the real `route_a_lifecycle_adapter` (R6), and the existing test-only result
scenario provider / scoreboard observer.  It adds no production-top module,
retry carrier, Full-KV carrier, source provider, numeric datapath, controller
schedule, or scoreboard schema event.

The covered path is fixed:

```text
one matching live R6 merge request
  -> one matching R4 numeric-fault carrier
  -> one matching R6 outward attention_terminal(status=numeric_fault)
  -> same-handshake testbench attention_terminal event
```

R4 retains the sole `merge_rsp_or_numeric_fault` terminal source.  R6 retains
the sole outward terminal owner.  The testbench adapter observes that named R6
carrier only; it does not originate a terminal.

## Directed closure

`RouteAFaultTerminalClosureSpec` establishes all of the following with the
fixed test-only anchor parameters:

| Situation | Required observation |
|---|---|
| Exact fault after a live, merge-ready identity | Exactly one outward `numeric_fault=1` terminal and exactly one same-handshake observation event. |
| Terminal/event ready-low | Both facts remain stable; no one-sided acceptance is possible. |
| Terminal accepted | The old live incarnation is closed; replaying its fault scenario is ready-low and yields no second terminal/event. |
| Wrong request ID or wrong incarnation | Fault scenario is ready-low; no terminal/event is generated. |
| Nonzero numeric-fault payload in the test stub | Scenario is ready-low; no terminal/event is generated. |

This is the required `one terminal outcome` closure for the covered R4/R6
fault boundary.  It does not create a retry path.  The composed harness has no
Full-KV selector, request, result, or terminal interface, so there is no
fallback carrier through which this fault can become a Full-KV substitution.
That interface-absence statement is deliberately narrow: it is not a proof of
the complete production dataflow or a performance claim.

## Preserved ordering and non-goals

The test does not accept metadata publication, an authority handoff, page
reuse, descriptor invalidation, allocator free, or retirement acknowledgement
as a consequence of a numeric fault.  Those effects remain under their named
R3/R5/R6 later closures.  In particular, a fault terminal is not evidence that
the R5 durable-invalidation-before-free sequence has run.

The evidence is deterministic no-model ChiselSim behavior.  It makes no claim
about R4 floating-point arithmetic, RTL equivalence, full end-to-end Route-A
correctness, formal deadlock freedom, cycle count, latency, throughput, area,
energy, PPA, model/GPU behavior, or a new A4 DSE.
