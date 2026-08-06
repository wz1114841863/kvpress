# KVzap baseline reproduction notes

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
