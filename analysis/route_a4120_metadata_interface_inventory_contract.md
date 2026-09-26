# A4.12.0 — metadata/control interface inventory contract

## Purpose

A4.12.0 freezes the provenance and logical interface entering metadata macro
and cycle-cost work. It does not select an SRAM macro, port count, physical
queue allocation, cycle latency, energy, area, architecture specification, or
RTL.

## Frozen inputs

The builder accepts a relocated mirror only when its bytes equal the accepted
A4.9.1 `_02`, A4.10 `_04`, A4.11.2b binding `_02`, C5, and C5 remote-replica
reports. A different rerun, even with a similar configuration, is rejected.

| Interface input | Authority | Required interpretation |
|---|---|---|
| HA8-wide, eight banks, head-affine, abstract 2/2/2 capability | A4.9.1 `_02` | Declared service candidate, not physical SRAM ports or an implementation. |
| local32/shared256/staging512 | A4.10 `_04` | Logical lossless queue/credit guarantee, not per-layer SRAM replication. |
| 59/50 raw, 64/64 padded metadata entries | A4.9.1 `_02` | Joint-safe modeled entry accounting, not a final physical pointer-bearing entry. |
| retained token to 64-token span/group conversion | A4.11.2b binding `_02` | Deterministic binding conversion; not observed hardware ready/commit/RMW activity. |
| external-storage prefill-armed maturity/pending/packed lifecycle | A4.11.2b binding `_02` | Direct scalar software observation only. |
| Route-A persistent-packed primary direction and pre-RTL boundary | C5 plus remote replica | Direction/provenance only; selects no hardware parameter. |

## Service and capacity boundaries

The frozen requirement is eight head-affine banks supporting at most two
read-class issues, two write-class issues, and two commit-coupled RMW issues
per **abstract service opportunity**. These quantities must not be rewritten as
a 2R2W SRAM, two macro ports, two physical RMW lanes, or calibrated throughput.

`local32/shared256/staging512` are logical contracts. A4.12.1 may assess only
M1 (banked SRAM plus pipelined RMW), M2 (replicated/duplicated control storage),
and M3 (small register hot state plus SRAM backing), without changing the
guarantee or assuming one statically copied macro per layer.

The A4.9.1 `head_control` and `span_owner` fields are metadata-semantic
accounting. Payload page ID, offset, bank, and address/handle widths are not
inside the frozen 59/50-bit values. They remain A4.13 parameters.

## Non-backtracking rule

An unfavorable A4.12 result may enter the partial metadata ledger, but cannot
reopen A4.8--A4.11 semantics, record-granular execution, queue/credit
parameters, scheduler, pruning, or admission. An unfavorable A4.13 payload
result likewise belongs in A4.14's complete net-benefit decision.
