# RTL3.9-C4-P1 — C3b event-provenance matrix

## Status

C4-P1 is complete as an **audit only**.  The machine-readable
[`rtl3_9_c4_p1_c3b_event_provenance_matrix.json`](rtl3_9_c4_p1_c3b_event_provenance_matrix.json)
enumerates all fourteen immutable RTL2 event records in schema order and maps
each to the C3b same-instance witness, its accepted-carrier status, exact
field provenance, and required next gate.

Every row is deliberately `capture_authorized=false`.  P1 adds no Chisel
observer, event FIFO/table, producer, default field, or scoreboard replay
trace.  It therefore cannot claim C4 functional closure.

## Findings

Three records have complete outward observations, but still require explicit
C4-P2 binding before they may be captured:

- `authority_transition`: the actual C0 R3-to-R6 acceptance is
  `r6_authority_transition_fire` with the exact transition bundle.  P2 must
  make its immutable-schema alias explicit and must not create an R6 page or
  ordinal table.
- `attention_terminal`: `c3_attention_terminal.fire` carries the exact fields
  and reuses the pre-existing RTL2.4.3 outward-observation binding.
- `retire_ack`: `c3b_retire_ack.fire` carries the exact fields and reuses the
  pre-existing RTL2.5.5 binding.

`page_free` has an exact R5 `allocator_release_out.fire` internally, but no
C3b harness observer.  `consumer_partial_commit`, `source_release`, and
`merge_request` likewise have internal owner fires but are not exported.
The matrix rejects shortcuts: `publication_commit` lacks the immutable
per-record metadata fields; S2 availability is not a handshake; external
functional-memory traffic is not the R2/R1 or router acceptance; and a
descriptor line or `reclaim_complete` cannot invent an invalidation/free
event.

## Validation

```bash
.venv/bin/python tools/validate_rtl3_9_c4_p1_c3b_event_provenance_matrix.py
.venv/bin/python -m pytest -q tests/test_rtl3_9_c4_p1_c3b_event_provenance_matrix.py
git diff --check
```

These are no-model audit checks.  No Chisel compilation is required or run.

## Boundary and next step

This matrix proves neither event occurrence nor replay correctness.  It makes
no current RTL-equivalence, functional-memory implementation, HBM/SRAM,
numeric/MAC/FP/exp, timing, throughput, area, energy, PPA, model/GPU, or
complete-inference claim.

C4-P2 must select a minimal subset, bind only the listed accepted handshakes,
and demonstrate that ready-low, stale/mismatch, fault, and reset produce no
invented event.  Any event with incomplete fields or no bound fire remains
uncapturable.
