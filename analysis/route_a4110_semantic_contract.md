# A4.11.0 trace-off three-path semantic matrix

## Scope

This gate binds the completed A4.10 `_04` declared queue/control contract to
three independent, trace-off Qwen policy-on semantic manifests: retrieval,
summarization, and reasoning.  It does not load a model itself.  Each input
must come from the existing `run_kvzap_route_a40_policy_gate.py` three-pass
runner with Full-KV bypass, replayed same-mask dense KVzap, and Route-A packed
hot/pending/cold paths.

The matrix requires all layers and all KV heads, exact dense-to-Route-A mask
replay, per-head numerical comparisons, a pending-staging witness, and the
existing no-DMS/no-fake-key/no-native-cache-mutation guards.  Full-KV output
equality is recorded but intentionally not required.

The policy manifests must use `--execution-dtype-ulp-mode record_only` and
`--execution-dtype-close-mode quantization_aware_enforce`.  FP32 same-mask
`rtol/atol` remains mandatory and the executed-dtype close check remains hard;
only scalar ULP exceedances are retained as bounded diagnostics.  This matches
the subsequent A4.1.4 measurement contract and prevents the generic runner's
strict 16-ULP default from rejecting a semantically valid quantized execution.

## Fixed boundary

The input A4.10 report must retain record-granular execution, HA8-wide plus
HA8-base catalog, local `32`, shared `256/layer`, staging `512/layer`, and the
64-bit reference word.  A4.11.0 does not consume those values as runtime FIFO
dimensions and does not change them.

`--record-lifecycle-transitions` and prefill micro-events are rejected here.
They belong to a later, separately versioned trace-on control-event validation.
Timing, allocator, profiler, HBM, queue latency, and hardware claims are also
outside this gate.

## Required sequence

For each named preset, first create a fresh trace-off semantic manifest with
the existing runner using `--target-layers all --target-kv-head all`,
`--with-same-mask-dense-baseline`,
`--replay-dense-mask-for-route-a`, and `--require-pending-nonempty`.  Use one
fixed semantic configuration across all three runs, including
`--execution-dtype-ulp-mode record_only` and
`--execution-dtype-close-mode quantization_aware_enforce`.  Then validate
them:

```bash
.venv/bin/python tools/validate_kvzap_route_a4110_semantic_matrix.py \
  --a410-report analysis/experiments/route_a410_queue_staging_credit_contract_04/a410_queue_staging_credit_contract_report.json \
  --retrieval-manifest analysis/experiments/<new-retrieval>/a40_policy_on_qwen_manifest.json \
  --summarization-manifest analysis/experiments/<new-summarization>/a40_policy_on_qwen_manifest.json \
  --reasoning-manifest analysis/experiments/<new-reasoning>/a40_policy_on_qwen_manifest.json \
  --preflight-only \
  --output-dir analysis/experiments/<new-a4110-matrix>
```

Only after this gate passes may trace-off measurement and trace-on control
event work be run in distinct fresh directories.
