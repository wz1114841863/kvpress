# A4.13.3 — packed-KV HBM realization / source-buffer DSE contract

## Purpose

A4.13.3 asks one bounded question: after fixed 64-token packing and only
event-level-legal GQA reuse, how much of Route-A's logical reduction becomes a
smaller **declared** HBM page/transfer-beat/service-slot envelope?  It is a
replay of A4.13.1's exact scalar software source events, bound through the
accepted A4.13.2 report.  It does not execute a model, change a mask, modify
admission, or introduce a payload organization beyond A4.13.1 P3.

## Frozen inputs and fairness rule

The input is the accepted A4.13.2 report with SHA-256
`400df695bc2a41572e7a41376520621250403288658d9fc9b74b250bd9148099`, plus
the three A4.13.1 manifests whose hashes are recorded inside that report.
The recorder settings remain Qwen3-8B, all 36 layers, all 8 KV heads, GQA
group 4, hot window 128, page 64, admission budget 512, and the accepted
external-storage Route-A path.

For each `(layer, KV-head, cache position, phase)`, exactly four query-head
events with equal source/page state form a legal GQA group.  The same verified
groups are used for **both** sides:

```text
Full-KV + legal four-query-head GQA reuse
vs.
Route-A packed + legal four-query-head GQA reuse
```

This closes the fairness gap in A4.13.2, whose Full-KV baseline intentionally
had no fetch reuse.  The A4.13.2 no-reuse baselines are retained only as an
attribution reference; they are not the A4.13.3 headline comparison.

## Declared realization model

Both sides use 64-token, 32,768-B K+V page transfers.  Full-KV causal spans
are rounded to the same 64-token pages.  Route-A keeps hot/pending scalar
source words and fetches each observed packed page as a 32,768-B page.  A
packed-page position sidecar is conservatively carried as `64 * 8 = 512 B`
per packed page source fetch.  Full-KV has implicit causal positions and no
such sidecar in this accounting.

The only transfer granule is a **declared 256-B transfer beat**.  It is not an
HBM protocol transaction, burst length, controller configuration, bandwidth
measurement, or technology selection.  Counts of these beats are named
`declared_256B_transfer_beats` throughout the output.

The source interface is fixed as:

```text
HBM 32 KiB packed page
  -> 32 KiB source buffer
  -> four GQA query-head consumers
  -> four partial (max, exp_sum, weighted-V) states
  -> existing hot / pending / packed online-softmax merge
```

The partial-state interface is `4 * (128 + 2) * 4 = 2,080 B` if FP32.  It is
not a selected register file, SRAM macro, or physical merge transfer.

## Only two source-buffer sensitivities

| ID | Buffer interface | Declared normalized service envelope |
|---|---|---|
| S1 | one 32 KiB page buffer | A page fill and its consumer stream do not overlap. |
| S2 | two 32 KiB ping-pong buffers (64 KiB total) | Ideal steady-state fill/consume overlap; report `max(fill beats, consumer beats)` as a lower service-slot bound. |

One declared transfer beat and one declared consumer beat each take one
**normalized service slot**.  These are explicitly a scheduling/accounting
device, not cycles at a frequency.  S2 requires logically independent fill
and consume progress; it does not prove a physical SRAM port implementation.
The report calls out capacity, logical streams, and the non-overlapped versus
ideal-overlap envelopes rather than selecting an SRAM macro.

## Reported quantities and boundaries

For every workload and for `multi_token` and `decode` separately, report:

- Full-KV and Route-A legal-GQA page fetches, useful bytes, page-rounded bytes,
  256-B transfer-beat proxies, tail pages, and useful/transferred ratio;
- Route-A position-sidecar bytes/beats, P3 admission writes/movement, and
  existing partial-softmax merge interface terms;
- packed-page fetches, HBM bytes/beats, and service-slot envelopes per observed
  decode attention position; and
- the S1/S2 source-buffer capacities and their normalized service-slot
  envelopes.

The scalar trace has no physical HBM commands, page allocation, controller,
clock, bandwidth, address mapping, DMA, source-buffer ports, attention lane
timing, or energy.  Thus A4.13.3 can establish a trace-bound **modeled**
page/beat/service envelope only.  It makes no measured bandwidth, latency,
area, energy, PPA, speedup, or Route-A net-benefit claim.  Metadata traffic
continues to be outside this stage, and A4.10/A4.12 contracts remain frozen.

