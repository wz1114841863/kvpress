# Qwen3-8B KVzap smoke test

## Purpose

`tools/run_kvzap_smoke.py` verifies the official
`nvidia/KVzap-mlp-Qwen3-8B` predictor and runs a bounded KVzap test with
`Qwen/Qwen3-8B`. It does not run a benchmark and does not measure physical KV
memory reduction. The reported `compression_ratio` is the average logical
removed fraction across layers.

The predictor is downloaded explicitly before the base model is loaded. The
current KVzap implementation still loads the predictor into the press on the
first model call, so “base model loaded” and “KVzap predictor used
successfully” are reported separately.

## Recommended remote environment

- Linux with an NVIDIA CUDA GPU;
- Python 3.10 or 3.11;
- at least 24 GiB GPU memory for the simplest single-GPU BF16 smoke test, or
  multiple GPUs usable through `device_map="auto"`;
- at least 25 GiB free disk space for the base model, predictor, and download
  cache;
- PyTorch built for the server's CUDA/driver combination;
- Transformers 4.57.3, matching the official predictor metadata;
- no FlashAttention installation is required for this first smoke test.

The official predictor is `nvidia/KVzap-mlp-Qwen3-8B`. Its configuration is 36
layer modules with `4096 -> 512 -> 8` MLPs. The download is approximately
339 MiB in the Hugging Face cache. The much larger `Qwen/Qwen3-8B` base model is
also downloaded automatically if it is not already cached.

Recommended setup:

```bash
uv venv --python 3.11
uv sync --extra eval
uv pip install transformers==4.57.3
```

Confirm the server sees the intended environment before loading the model:

```bash
.venv/bin/python -c "import torch, transformers; \
print('torch:', torch.__version__); \
print('transformers:', transformers.__version__); \
print('cuda:', torch.cuda.is_available()); \
print('gpu:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

If `cuda` is false, fix the remote PyTorch/CUDA installation before running the
8B smoke test. Do not fall back to CPU unless a very slow run is acceptable.

The included compatibility change makes `KVzapConfig` default-constructible as
required by Transformers serialization, while `KVzapModel` still rejects a
config missing the three required model dimensions. It does not change KVzap
scores or pruning behavior.

## Commands

Show all confirmed options without loading a model:

```bash
.venv/bin/python tools/run_kvzap_smoke.py --help
```

First run the lightweight configuration round-trip test; it does not download
or load Qwen3-8B:

```bash
.venv/bin/pytest -q tests/presses/test_kvzap_press.py
```

Optionally download the predictor separately. The smoke script performs the
same download automatically:

```bash
.venv/bin/hf download nvidia/KVzap-mlp-Qwen3-8B
```

Recommended first run (prefill only):

```bash
.venv/bin/python tools/run_kvzap_smoke.py --mode prefill
```

After prefill succeeds, exercise score-buffer maturity during generation:

```bash
.venv/bin/python tools/run_kvzap_smoke.py \
  --mode prefill-decoding \
  --max-new-tokens 256
```

Run both phases with separate `DMSPress` instances:

```bash
.venv/bin/python tools/run_kvzap_smoke.py --mode both
```

Do not begin with a 2,000-token generation. First confirm model/predictor load,
nonzero per-layer logical removal, and sensible output with the bounded commands
above.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--model-name` | `Qwen/Qwen3-8B` | Base-model Hugging Face ID. |
| `--predictor-name` | `nvidia/KVzap-mlp-Qwen3-8B` | Predictor downloaded and validated before inference. Must match the ID derived by `KVzapPress`. |
| `--threshold` | `-4` | Scores strictly below this value are logically dropped. |
| `--window-size` | `128` | Newest tokens protected from pruning. |
| `--mode` | `prefill` | `prefill`, `prefill-decoding`, or `both`. |
| `--max-new-tokens` | `256` | Generation cap for prefill+decoding mode. |
| `--prefill-max-new-tokens` | `64` | Answer generation cap for the prefill-only test. |
| `--context-repetitions` | `12` | Ensures the sample prefill context is longer than the window. |
| `--enable-thinking` / `--no-enable-thinking` | enabled | Qwen3 thinking setting for prefill+decoding mode. |

## Success criteria

1. Predictor config validation passes.
2. Base model loads in a compatible environment.
3. The first KVzap call reports
   `nvidia/KVzap-mlp-Qwen3-8B` as its loaded predictor.
4. All 36 layers report a logical removed fraction.
5. The prefill context exceeds 128 tokens.
6. Generated output is nonempty and reasonable for the prompt.

This smoke test is not yet the Full-KV-versus-KVzap equivalence experiment and
does not export score or mask traces.
