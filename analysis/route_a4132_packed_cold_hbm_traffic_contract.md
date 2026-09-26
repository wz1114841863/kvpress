# A4.13.2 — packed-cold attention HBM traffic accounting contract

## Purpose

A4.13.2 turns A4.13.1's exact external-storage source/page trace into a
bounded **HBM-resident packed-KV accounting** comparison.  It does not seek to
place all KV payload in SRAM.  Packed cold KV remains HBM-resident; the only
on-chip interface assumed for GQA reuse is a streaming source/page buffer.

This stage fixes Qwen3-8B, 36 layers, 8 KV heads, GQA group size 4, 512 B K+V
per token, and 64-token packed pages.  It consumes the exact A4.13.1 report
and its three trace manifests.  No model execution, mask/admission change,
queue change, or payload-organization expansion occurs.

## Three accounting baselines, not new architecture variants

1. **Full-KV HBM baseline**: each observed query-head evaluation traverses its
   full causal K/V length (`cache_position + 1`) from HBM with no GQA fetch
   reuse.
2. **Packed no-reuse**: the existing hot/pending/packed source counts are read
   separately for every query-head evaluation.  Hot/pending are counted at
   useful K/V-word bytes; each packed source traversal fetches every observed
   packed page as a full 64-token payload page.
3. **Packed legal GQA reuse**: only events with exactly four query heads of one
   KV head, identical source lengths and identical packed page state are
   deduplicated.  One HBM source fetch serves four query-head consumers through
   a local streaming buffer.  No arithmetic divide-by-four is accepted without
   this event-level proof.

All figures are declared traffic accounting under this explicit mapping, not
measured HBM transactions/bandwidth.

## Transfer and reuse interface

```text
HBM packed page fetch (32,768 B)
  -> one page/source buffer
  -> four GQA query-head consumers
  -> four partial attention accumulators
  -> existing online-softmax merge
```

The minimum packed page buffer interface is 32,768 B.  Four partial tuples use
`4 * (128 + 2) * 4 = 2,080 B` if represented as FP32.  These are interface
sizes only: no SRAM macro, port count, dataflow schedule, frequency, area, or
energy is selected.

For reporting an explicit transaction proxy, the model also uses a fixed
256-B **accounting sector** (the existing K or V word size).  Sector counts are
not asserted to be native HBM transaction counts.  Packed-page request count,
average bytes/request, and useful/page-rounded ratio remain reported directly.

## Capacity and non-payload terms

Final Full-KV resident payload is derived from the trace's final causal length.
Route-A resident payload is final hot K/V plus final packed page-slot capacity;
the final pending residual is required to be zero.  Logical position sidecar
capacity is reported separately.  Metadata and merge are retained as separate
interface terms: this stage does not invent metadata traffic or physical merge
transfers.

The A4.13.1 P3 admission/staging mapping is carried forward only as the small
staging/HBM-backed reference. P2 remains an upper SRAM-cost reference in its
source report; no P4/P5 is introduced.
