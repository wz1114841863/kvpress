# RTL3.8.4 — dynamic R4 functional-reference protocol activation

**Status:** `complete_i7_i8_dynamic_protocol_activation_external_oracle_bound`.

RTL3.8.4 removes the exercised functional top's local inactive
`r4_result_stub` / `r4_numeric_fault` tie-offs.  It installs the named
`route_a_functional_r4_reference_boundary` between the existing structural
R4 acceptance owner and the already frozen, external
`route_a_functional_r4_merge_provider` role from RTL3.4-B.

```text
structurally accepted R4 packet
  -> functional_r4_accepted_packet_out
  -> external pure-software RTL3.4-B oracle environment

R6 active merge observation + exact received source mask
  -> functional_r4_merge_work_out
  -> one matching success XOR numeric-fault response
  -> existing RouteAMergeBoundary
  -> existing R6 outward terminal path
```

`route_a_merge_boundary` remains the sole R4 packet acceptance owner.  R6
remains the sole group-level outward-terminal owner.  The new child owns only
the reference-environment association protocol; it performs no merge
arithmetic and cannot create a terminal without a previously issued, matching
merge-work item.

## Frozen protocol

| Event | Owner | Boundary rule |
|---|---|---|
| accepted partial packet | existing `route_a_merge_boundary` | Forward only after structural R4 acceptance; key it by exact RID/incarnation, source instance, and consumer. |
| packet receipt | `route_a_functional_r4_reference_boundary` | For one live identity, record exactly one canonical source bit per consumer after the outer environment accepts the packet. |
| functional merge work | boundary | Emit only when `packet_mask[consumer] == source_presence`, with nonempty source presence and the exact active R6 identity/consumer. |
| functional success/fault | outer `route_a_functional_r4_merge_provider` environment | Accept only after work has fired, only for the active exact identity/consumer, and only one of success or fault. |
| R4/R6 terminal | existing `route_a_merge_boundary` then R6 | Unchanged; the boundary cannot bypass, duplicate, or create an outward terminal. |

Canonical source-bit positions remain `hot=0`, `pending=1`, `packed=2`.
They are association bits, not a numeric source reorder, port choice, queue,
or scheduling policy.

## Fail-closed rules

- A packet with a stale/new identity while another identity is live, an invalid
  source/consumer, header-sideband disagreement, or duplicate source bit is
  ready-low and cannot change receipt state.
- Missing selected source packets prevent `functional_r4_merge_work_out`;
  they never yield a zero result, absent substitution, retry, Full-KV
  fallback, or terminal.
- A stale/mismatched result or numeric fault is ready-low.  Simultaneous
  success and fault are both rejected.
- Receipt state is reset with destructive reset, after consumer-3 success, or
  after a fault.  A fault does not retain an old identity for later reuse.
- The boundary preserves a work/result/fault carrier while its downstream
  ready is low.  The external reference environment is responsible for
  keeping its valid response payload stable until accepted.

## Environment/DUT split

The external functional provider is an environment, not synthesizable Route-A
hardware.  It must consume only packet/work events emitted by this boundary,
use the already frozen RTL3.3/RTL3.4-B oracle, and return a matching terminal.
The DUT guarantees that it cannot observe a work item until the complete
selected accepted-packet set has been delivered and cannot mutate R4/R6 from a
response that does not match that issued work.

There is deliberately no Python-to-Chisel production bridge in this change.
The Python provider remains separately executable pure-software evidence; the
Chisel boundary establishes its dynamic event and terminal protocol only.

## Historical provenance

The original `source_sha256` snapshot belongs to immutable closure commit
`a65f2d46ad973e85fbaeab911a65721f17abf5db`.  Its validator replays that
snapshot through `git show`, as recorded in
[`rtl3_8_4_dynamic_r4_functional_reference_historical_provenance.json`](rtl3_8_4_dynamic_r4_functional_reference_historical_provenance.json),
rather than rejecting valid descendant changes to shared source and the live
phase ledger.  The replay is historical evidence only, not C0--C3 or physical
realization evidence.

## What this closes, and what remains open

Closed here:

- I7/I8 no longer rely on local top-level R4 terminal tie-offs on the
  production-shaped functional path;
- a dynamic, packet/work-gated R4 reference environment interface is present;
- packet receipt, work issue, response association, stale/mismatch,
  simultaneous-terminal, ready-low, and reset behavior are directed-tested.

Still open:

- a live functional source payload/position lease producer for every source
  subset (RTL3.8.3 deliberately left R3/direct work inactive);
- a same-simulation Python/Chisel oracle co-simulation bridge, if later needed
  as verification infrastructure;
- RTL3.8.5 all-subset/full-path success and fault coverage; and
- any synthesizable FP/exp/MAC/RoPE implementation, physical memory,
  controller/macro/CDC, clock/latency/throughput, area/energy/PPA/DC, or full
  LLM inference claim.

## Directed no-model checks

```bash
cd hardware/route_a/chisel && sbt -batch \
  'testOnly kvpress.routea.rtl3.RouteAFunctionalR4ReferenceBoundarySpec' \
  'testOnly kvpress.routea.structural.RouteAKVSubsystemTopSpec' \
  'testOnly kvpress.routea.integration.RouteAInitDrainIntegrationSpec'
.venv/bin/python -m pytest -q \
  tests/test_route_a_merge_numeric_reference.py \
  tests/test_rtl3_3_r4_functional_profile.py \
  tests/test_rtl3_4b_functional_r4_provider.py \
  tests/test_rtl3_4b_functional_r4_provider_manifest.py
.venv/bin/python tools/validate_rtl3_8_4_dynamic_r4_functional_reference.py
```

This is directed structural/protocol evidence plus the pre-existing
pure-software oracle evidence only: no model/GPU, no timing/throughput, no
numeric RTL correctness, no PPA, and no new A4 DSE.
