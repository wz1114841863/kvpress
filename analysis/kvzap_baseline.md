# Qwen3-8B Full-KV versus KVzap baseline

## Frozen status

Phase 0 is frozen as of 2026-08-17. The authoritative run is
`kvzap-baseline-20260806T043908Z`, with configuration hash
`b1d3a4704b3cba56a1d31d47054c3e886bfff11bdfb8c0ca2ae89315433da1e6`.
Artifact hashes and exact summary values are recorded in
`analysis/baseline_freeze.json`.

Do not use `--overwrite` on `analysis/`. Reproduction or extension runs must use
a new directory under `analysis/experiments/`. Freezing means the recorded
configuration and results are the Phase 0 reference; it does not promote the
three built-in substring checks to an official accuracy benchmark.

## Goal

`tools/run_kvzap_baseline.py` runs the same small request set with:

1. `full_kv`;
2. `kvzap_prefill`;
3. `kvzap_prefill_decoding`.

It freezes the Qwen3-8B/MLP/threshold/window configuration and creates the
Phase 0 artifacts:

```text
analysis/baseline_config.yaml
analysis/baseline_results.csv
analysis/reproduction_notes.md
```

The built-in requests cover simple retrieval, summarization, and a longer
generation. They are functional checks, not substitutes for official
RULER/LongBench accuracy.

## Environment

Use the remote environment described in `analysis/kvzap_smoke_test.md`. The
frozen run used Transformers `5.0.0`; an exact reproduction must preserve that
version. The older `4.57.3` recommendation is suitable only for a separate
compatibility experiment, not a byte-for-byte reproduction. Confirm the
lightweight tests before loading Qwen3-8B:

```bash
.venv/bin/pytest -q \
  tests/presses/test_kvzap_press.py \
  tests/test_kvzap_baseline.py \
  tests/test_baseline_freeze.py
```

## First baseline run

Run all three variants:

```bash
.venv/bin/python tools/run_kvzap_baseline.py
```

Run only Full KV and prefill KVzap if a shorter first comparison is desired:

```bash
.venv/bin/python tools/run_kvzap_baseline.py \
  --variants full_kv kvzap_prefill
```

The script refuses to overwrite existing artifacts. Use a separate directory
for another experiment:

```bash
.venv/bin/python tools/run_kvzap_baseline.py \
  --output-dir analysis/experiments/qwen3_8b_baseline_02
```

Do not use `--overwrite` on the frozen `analysis/` artifacts. It remains
available for disposable experiment directories only.

## Custom request JSONL

Pass `--input-jsonl path/to/requests.jsonl`. Each nonempty line is one JSON
object:

```json
{"request_id":"sample-0","subset":"retrieval","context":"Long context...","question":"What is the code?","required_substrings":["ORCHID-7429"],"max_new_tokens":64}
```

Required fields:

- `request_id`;
- `context`;
- `question`.

Optional fields:

- `subset`, default `custom`;
- `required_substrings`, default empty/unscored;
- `max_new_tokens`, default 64.

Raw context and question are not written to the result CSV. The decoded answer
is saved so failures can be inspected.

## Confirmed options

| Option | Default | Meaning |
| --- | --- | --- |
| `--model-name` | `Qwen/Qwen3-8B` | Base model ID. |
| `--predictor-name` | `nvidia/KVzap-mlp-Qwen3-8B` | Official predictor ID. |
| `--threshold` | `-4` | Scores below this value are logically dropped. |
| `--window-size` | `128` | Protected recent window. |
| `--seed` | `42` | Reset before every request/variant. |
| `--variants` | all three | Selected baseline configurations. |
| `--input-jsonl` | built-in requests | Optional custom requests. |
| `--context-repetitions` | `12` | Built-in context length control. |
| `--max-new-tokens` | per-request value | Override every generation limit. |
| `--output-dir` | `analysis` | Artifact directory. |
| `--overwrite` | disabled | Explicitly replace existing baseline artifacts. |

## Result interpretation

`logical_removed_fraction` is the average fraction of logically masked KV
positions across layers. `logical_compression_factor` is calculated separately:

```text
logical_compression_factor = 1 / (1 - logical_removed_fraction)
```

The `kvzap_prefill_decoding` value is cumulative over both phases. Short
answers may end before many generated tokens leave the 128-token window; this
is expected and must not be interpreted as a decoding failure.

`elapsed_ms_diagnostic` is recorded only to catch gross regressions. The current
fake-key implementation keeps dense K/V tensors, so these timings do not prove
physical memory savings or KVzap speedup.

`generated_tokens_retokenized` is obtained by tokenizing the decoded answer. It
may differ by an EOS or other skipped special token from the internal generation
length. A future trace hook should capture exact generated token IDs.

## Success criteria

1. All requested variants complete for all requests.
2. Full KV reports removed fraction 0 and compression factor 1.
3. KVzap reports all 36 per-layer removed fractions.
4. The retrieval request contains `ORCHID-7429` in the answer.
5. Outputs contain no NaN/error and are nonempty.
6. Config, results, and notes share the same experiment ID/config hash.

This baseline has been reviewed and frozen. Trace work must now follow the
separate gates in `analysis/kvzap_trace.md`; a failed Trace implementation does
not invalidate the frozen baseline.

## PyTorch 2.10 compatibility note

PyTorch 2.10 exposes `torch.__version__` as a `TorchVersion` object rather than
an exact built-in `str`. PyYAML's safe dumper cannot serialize that object. The
baseline script explicitly converts runtime version metadata to built-in
strings, and `tests/test_kvzap_baseline.py` checks that the resulting metadata
can be serialized. This metadata fix does not affect model execution.
