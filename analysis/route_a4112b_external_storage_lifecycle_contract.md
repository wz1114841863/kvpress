# A4.11.2b external-storage lifecycle binding closure

## Purpose

A4.11.2b closes the only remaining A4.11 binding gap: lifecycle scalars are
observed on the A4.11.1 Qwen external-storage implementation, not on the
separate A40 policy-reference backend.  It is the final A4 software-to-model
binding gate; it is not a performance, hardware-queue, architecture, or RTL
experiment.

## Fixed implementation and guards

The run is fixed to Qwen3-8B, the frozen KVzap predictor and replay mask,
retrieval/summarization/reasoning, all 36 layers and 288 KV heads, window 128,
page 64, budget 512, and eight generated tokens.  Route-A is exactly
`RouteAQwenExternalColdStorageAttentionBackendSet` plus
`RouteAQwenMultiLayerExternalColdCache`.  A4.10 remains the fixed
record-granular HA8-wide contract with local 32, shared 256, and staging 512;
it is not retuned.

The run performs same-mask dense, external-storage trace-off, and
external-storage trace-on paths.  It requires exact equality of generated
token-ID SHA-256 for dense versus trace-on and trace-off versus trace-on;
complete replay consumption and all-layer/all-head coverage; and exact equality
of scalar final packed/pending/cold state between the two external paths.
There is no new Full-KV fallback, DROP, reordering, pruning rewrite, admission
rewrite, or policy-reference correctness oracle.

## Evidence classes and fixed conversion

The trace starts before the first external-storage prefill append.  It records
only scalar maturity, pending before/after service, packed page state, and
trace-end residual.  It does not invent ready-group, micro-op completion,
bank-port, RMW completion, credit, ownership publication, or physical commit
events.

Per-head pending watermarks are reported directly. A per-layer pending
watermark is the maximum, over that layer's append epochs, of the sum of the
post-maturity pending counters across all selected KV heads in that epoch; it
is not the largest individual-head watermark.

For the declared A4.10 input replay, frozen replay-mask retained tokens are
reconstructed from each observed maturity range, assigned to their logical
64-token span, and lowered deterministically into one
`(append event, layer, KV head, span)` binding group containing a declared
head-control RMW and span-owner RMW member.  Per-head FIFO predecessors are
fixed.  This conversion is not an observed A4.7.1 transaction, a software
commit event, or a hardware transaction.  The resulting A4.10 result remains
a declared model envelope only.
