# A4.13.1 — bounded pending + packed payload organization envelope

## Purpose

A4.13.1 records scalar source traversal from the existing external-storage
reference, then compares exactly three lossless payload organization mappings.
It does not retune A4.10, change pruning/admission/commit semantics, add a
queue/scheduler/granularity variant, or select an implementation.

The workload is fixed to Qwen3-8B, retrieval/summarization/reasoning, all 36
layers/all 8 KV heads, original replay mask, window 128, page 64, budget 512,
and eight generated tokens. Dense, trace-off, and trace-on external paths must
retain exact token equality; trace-on must also equal accepted A4.11.2b.

## Direct observations

The prefill-armed recorder records one existing software-reference Route-A
attention evaluation per selected query head. It stores only hot/pending/packed
logical record counts and the existing merge marker. Together with lifecycle
events this provides scalar pending watermark, admission, packed page state,
source traversal, and source-combination observations. It is not a physical
cache read, HBM transaction, port, timing, or bandwidth trace.

## Fixed reference dimensions

The accepted A4.13.0 layout fixes 512 B K+V per retained token and 64 tokens
per page: 32,768 B payload/page. The 8-B logical position sidecar remains
separate and is not a physical PTE/address choice.

## Exactly three declared organization mappings

| ID | Mapping | Declared interpretation |
|---|---|---|
| P1 | independent pending HBM backing -> packed HBM | Isolated per-(layer, KV-head) pending maxima are provisioned. Each retained token is written to pending HBM, read for admission, then written to packed HBM. |
| P2 | layer-local pending SRAM -> packed HBM | Every layer has a shared pending SRAM provisioned to its observed layer-total peak. Retained payload moves locally around admission, then writes once to packed HBM. |
| P3 | one 64-token SRAM staging page + pending HBM -> packed HBM | P1's lossless pending HBM backing remains. One staging page per layer chunks each admission epoch into `ceil(admitted/64)` fills without reordering or dropping. |

P1/P3 map pending and packed logical source traversal to HBM reads. P2 maps
pending traversal to declared local SRAM and packed traversal to HBM. These are
declared mappings only; no macro, address width, HBM burst, port, clock, DMA,
arbitration, cycle, area, or energy is inferred.

## Packing and merge accounting

Final packed 64-token page payload capacity versus final logical K/V payload
forms a page-capacity amplification; it is neither a write-traffic count nor a
macro capacity result. The existing partial tuple is `(max, exp_sum,
weighted_v)`: 130 scalar elements for head dimension 128. Each nonempty source
beyond the first contributes one merge interaction; 520 B/tuple if materialized
as FP32 is interface accounting only, not measured transfer or computation.

## Exit boundary

A4.13.1 may identify whether reasoning has a larger pending, movement,
page-amplification, cold-traversal, or merge envelope. It cannot claim HBM
traffic, runtime, energy, area, selected architecture, or Route-A net benefit.
