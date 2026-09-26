# A4.11.2 trace-on control-event mapping contract

## Scope

A4.11.2 validates that the policy-on Route-A reference can expose an honest,
scalar lifecycle view suitable as an input mapping to the fixed A4.10 declared
queue/staging/credit contract.  It follows completed A4.11.0 trace-off
semantics and A4.11.1 trace-off software observations.  It is not a timing,
allocator, hardware-service, or performance experiment.

## Trace start and path scope

The Route-A trace must be armed before its `generate()` prefill call, hence
before any hot-window maturity can create pending retained state.  Its first
event in every selected layer must be `prefill` at position zero; retained
pending state must be observed after prefill maturity.  A4.11.2 uses the
existing lifecycle-transition recorder at actual model-call append granularity
(`--prefill-maturity-chunk-tokens 0`), rather than constructing artificial
micro-events.

The command still runs Full-KV bypass, same-mask dense, trace-off Route-A, and
trace-on Route-A so tracing itself is compared against the paired control.
Only trace-on Route-A has detailed lifecycle events.  Full-KV is a bypass
boundary check; same-mask dense remains a mask/token semantic comparator and
has no synthetic queue trace.

## Software-to-model mapping

| A4.10 modeled field | Software source | Status |
| --- | --- | --- |
| arrival | `matured_kept_tokens` | direct scalar observation; retained tokens, not an atomic-group timestamp |
| queue/staging watermark | pending counters before/after logical admission | direct software scalar; not bank FIFO/shared hardware staging occupancy |
| ready group | none | no direct software correspondent |
| micro-op done | none | no direct software correspondent |
| single commit / ownership publish | none | no direct software correspondent |
| bank ports, RMW lane, cross-bank coordination | none | no direct software correspondent |

Missing correspondents are reported explicitly.  The validator must not infer
or manufacture them from reference execution order.

## Fixed contract and required guards

Keep A4.9.2 record-granular execution, HA8-wide/HA8-base catalog, local 32,
shared 256/layer, staging 512/layer, page 64, budget 512, all layers and all
KV heads.  Use replayed dense masks and `record_only` plus
`quantization_aware_enforce`; FP32 same-mask and executed-dtype close remain
hard guards.  Require trace-on Route-A answer/mask equality with trace-off
Route-A, no DMS/fake-key/native-cache mutation, and replayed-mask equality.
Same-mask dense versus Route-A generated-answer equality is recorded per
workload, not required: same-mask dense is a mask and numerical comparator,
not a second Route-A lifecycle implementation.

The result may state only that the observed scalar lifecycle can or cannot be
mapped to the listed declared-model inputs.  It cannot calibrate cycles,
FIFO depth, credit latency, throughput, HBM traffic, energy, area, hardware,
architecture, or RTL.
