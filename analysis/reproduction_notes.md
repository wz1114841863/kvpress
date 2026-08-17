# KVzap baseline reproduction notes

## Freeze record

- Status: **frozen** on 2026-08-17.
- Authoritative manifest: `analysis/baseline_freeze.json`.
- `analysis/baseline_config.yaml` SHA-256:
  `f6d8aaf2eed5f0ed2a7dc0c9433906c989c004063948b960398f3c2e7cf37e63`.
- `analysis/baseline_results.csv` SHA-256:
  `7f7798e9cf5b766465fd34e67e10575c631eb2adec5cf36eba869f2e516a1a07`.
- Do not overwrite these two artifacts. Put reruns under
  `analysis/experiments/<new_id>/`.
- Trace failures are tracked separately and do not alter this Phase 0 record.

- Experiment ID: `kvzap-baseline-20260806T043908Z`
- Config hash: `b1d3a4704b3cba56a1d31d47054c3e886bfff11bdfb8c0ca2ae89315433da1e6`
- Git commit: `efbaefeb315ee8c50a44923f9dbc7eb314d62f27`
- Model: `Qwen/Qwen3-8B`
- Predictor: `nvidia/KVzap-mlp-Qwen3-8B`
- Threshold/window: `-4.0` / `128`
- Decoding: greedy with Qwen thinking disabled.
- Runtime is diagnostic only; the current fake-key DMS path does not provide physical KV compression.
- `generated_tokens_retokenized` is computed by tokenizing the decoded answer and may exclude EOS/special tokens.

## Variant summary

- `full_kv`: requests=3, correct=3/3, mean logical removed fraction=0.0000
- `kvzap_prefill`: requests=3, correct=3/3, mean logical removed fraction=0.7151
- `kvzap_prefill_decoding`: requests=3, correct=3/3, mean logical removed fraction=0.7264

These built-in checks are smoke-level functional metrics, not official RULER/LongBench accuracy.
