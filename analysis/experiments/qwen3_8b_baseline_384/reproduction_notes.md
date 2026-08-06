# KVzap baseline reproduction notes

- Experiment ID: `kvzap-baseline-20260806T050324Z`
- Config hash: `1b8474aa6a7540064486904a8848e6d6d0ab364c31d4a337b09850be7c2ae287`
- Git commit: `0decd7452ac92808ca99d38d4023a166278c900e`
- Model: `Qwen/Qwen3-8B`
- Predictor: `nvidia/KVzap-mlp-Qwen3-8B`
- Threshold/window: `-4.0` / `128`
- Decoding: greedy with Qwen thinking disabled.
- Runtime is diagnostic only; the current fake-key DMS path does not provide physical KV compression.
- `generated_tokens_retokenized` is computed by tokenizing the decoded answer and may exclude EOS/special tokens.

## Variant summary

- `full_kv`: requests=3, correct=3/3, mean logical removed fraction=0.0000
- `kvzap_prefill`: requests=3, correct=3/3, mean logical removed fraction=0.7151
- `kvzap_prefill_decoding`: requests=3, correct=3/3, mean logical removed fraction=0.7263

These built-in checks are smoke-level functional metrics, not official RULER/LongBench accuracy.
