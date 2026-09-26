# A4.12.3 — metadata-side partial benefit ledger

## Purpose

A4.12.3 closes the metadata/control cost side without pretending to evaluate
the unphysicalized KV payload path.  It joins only these frozen artifacts:

```text
A4.11.2b external-storage lifecycle
  -> matured kept/dropped cold-token accounting
  -> logical capacity and future-traversal potential

A4.12.1 macro envelope + A4.12.2 service replay
  -> metadata proxy area, service feasibility, and partial SRAM dynamic energy
```

## Benefit classification

For each A4.11.2b workload, `matured_dropped_tokens` is a direct software
observation at the point a token becomes cold.  It is reported as:

- logical cold-KV capacity removal potential; and
- one-unit-per-future-cold-source-traversal attention-work reduction potential.

The latter has no observed future traversal count in A4.11.2b.  It is not
HBM traffic, actual attention operations, runtime, energy, or realized
savings.

## Non-pairing rule

The A4.11.2b Qwen external-storage requests and the A4.12.2 multi-context
metadata traces are not one-to-one aligned.  A4.12.3 therefore reports cost
and benefit ledgers side by side, never divides benefit by area/energy or
claims a net benefit.  A4.13 must physicalize payload storage/movement and
packed attention before A4.14 can construct a full Route-A ledger.

## Candidate disposition

M1 is retained as a rejected physical mapping because it does not drain every
frozen context.  M2 is a complete SRAM-proxy candidate.  M3 is service-feasible
but has intentionally incomplete register area/energy, so it remains a range
endpoint rather than a selected winner.
