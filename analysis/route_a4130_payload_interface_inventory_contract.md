# A4.13.0 — Route-A payload interface inventory

## Purpose

A4.13 begins physicalization of the Route-A **KV payload** path.  This first
step freezes the software-visible payload word/page/lifecycle interface before
selecting a memory tier, physical page address, SRAM/HBM organization, DMA
engine, attention datapath, clock, area, or energy model.

It is deliberately an inventory, not a payload PPA or performance study.
The accepted A4.11.2b external-storage lifecycle is the authority for the
software path.  A4.12.0 remains the authority for the separate metadata/control
logical resource contract.  Neither contract is retuned here.

## Fixed inputs

The builder requires the exact accepted A4.11.2b binding report
(`57da81a6...dcdc3a3`) and the exact accepted A4.12.0 interface report
(`e5a7ad30...be3534`).  It also validates the tracked Qwen3-8B target descriptor:

```text
36 layers, 8 KV heads, head dimension 128
two-byte cache scalar (bfloat16 reference cache)
K+V = 512 B per (layer, KV head, token)
window = 128, packed page = 64 tokens, admission budget = 512
```

The report records immutable copies and hashes of these authority artifacts,
plus the two software-reference implementation files that establish separate K
and V pages and an eight-byte logical-position sidecar.

## Deterministic dimensional derivation

For the fixed software reference layout only:

```text
K word = 128 * 16 bits = 256 B
V word = 128 * 16 bits = 256 B
K+V token word = 512 B
64-token K+V page = 32,768 B
64 logical positions * 64 bits = 512 B sidecar
```

The position sidecar mirrors the existing software reference.  It is not a
selected physical position encoding, page-table entry, address, or handle.

## Frozen lifecycle interface

```text
creation / predictor decision
  -> hot window (128)
  -> maturity produces logical pending candidates
  -> admission retains original-mask members
  -> append to separate per-(layer, KV-head) packed K/V pages
  -> seal each 64-token packed page
  -> attention consumes hot + pending + packed-cold logical sources
  -> source partials have one semantics-preserving online-softmax merge
```

This interface preserves the accepted A4.11 exact-token and final-state
guards.  It does not turn a software lifecycle transition into a physical
transfer, ready event, port operation, commit cycle, or attention-engine
schedule.

## Explicitly unresolved A4.13 parameters

- physical page count, page-ID/handle/address width, bank mapping, and
  page-table encoding;
- pending-KV placement/capacity, allocation ownership, and movement/DMA;
- SRAM versus HBM/DRAM tiering, burst layout, read/write ports, and bandwidth;
- packed page allocation granularity and layer sharing policy;
- query/K/V datapath, source traversal order, partial-softmax state placement,
  arithmetic precision, and merge implementation;
- cycle, throughput, area, energy, physical traffic, and realized serving
  benefit.

Those choices belong to subsequent bounded A4.13 studies.  A poor result may
not reopen A4.8--A4.12 semantics, pruning, admission, queue, or execution
granularity contracts.
