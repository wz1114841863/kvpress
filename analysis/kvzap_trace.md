# KVzap single-request trace

## What is captured

`tools/run_kvzap_trace.py` captures the following intermediate results for one
Qwen3-8B request:

- raw MLP predictor scores in explicit `[layer, KV head, token]` layout;
- `predicted_drop_mask`, obtained directly from `score < threshold` before
  sliding-window protection;
- `final_drop_mask`, containing only positions that have left the protected
  window and were actually added to `masked_key_indices`;
- per-step/per-layer/per-head decode admission and drop counts;
- request-level and layer/head-level logical-retention summaries.

It does not save attention matrices, K/V tensors, prompt text, or physical page
layouts. The results describe logical masking, not physical memory reduction or
wall-clock acceleration.

## Safety and equivalence check

The callback on `DMSPress` defaults to `None`. With tracing disabled, no score
tensor is copied. The exporter runs the same deterministic request twice using
the same loaded model and predictor:

1. tracing disabled;
2. tracing enabled.

It writes files only after verifying exact equality of the decoded answer,
per-layer compression ratios, and every final masked index. It also reconstructs
the final mask from trace events, compares that mask with `masked_key_indices`,
and verifies that the newest 128 tokens are not dropped.

Trace mode copies score and mask tensors to CPU and therefore must not be used
for performance measurement.

## Lightweight checks

These commands do not download or load Qwen3-8B:

```bash
python tools/run_kvzap_trace.py --help
pytest -q tests/test_kvzap_trace.py tests/presses/test_dms_trace.py tests/presses/test_kvzap_press.py
```

## Remote trace run

Use the same environment that passed the baseline experiment:

```bash
python tools/run_kvzap_trace.py \
  --max-new-tokens 384 \
  --output-dir traces/qwen3_8b_single_384
```

The destination must not already exist. Generated trace directories are ignored
by git because the compressed score tensor can still be several MiB or larger.
Transfer the selected trace directory separately, or force-add only a deliberately
small artifact after reviewing its size.

### Built-in request types

The default remains the original hardware-themed long-generation request. Use
`--preset` to capture genuinely different inputs:

```bash
python tools/run_kvzap_trace.py \
  --preset retrieval \
  --max-new-tokens 384 \
  --output-dir traces/retrieval_01

python tools/run_kvzap_trace.py \
  --preset summarization \
  --max-new-tokens 384 \
  --output-dir traces/summarization_01

python tools/run_kvzap_trace.py \
  --preset reasoning \
  --max-new-tokens 384 \
  --output-dir traces/reasoning_01
```

The retrieval answer may terminate well before 384 tokens; that is expected.
The three output directories must be generated successfully before they are
passed to the multi-request analyzer.

Each trace-off/trace-on pass uses an independent `DMSPress` runtime state while
sharing the already loaded predictor. This prevents a short-answer request from
leaking or losing the score buffer between equivalence passes. The DMS hook also
checks the actual dense KV length when identifying a newly created cache.
The trace exporter clears request-local attention masks before each pass and
enables a diagnostic bounds check. If a mask is invalid, it reports the pass,
layer, key shape, and index limits before launching CUDA advanced indexing.

### Custom request JSONL

Each JSONL row requires `request_id`, `context`, and `question`. `dataset` and
`subset` are optional and default to `custom`:

```json
{"request_id":"sample_01","context":"Long context...","question":"Question..."}
```

For a one-row file:

```bash
python tools/run_kvzap_trace.py \
  --input-jsonl requests.jsonl \
  --output-dir traces/sample_01
```

If the file has multiple rows, select exactly one request per trace directory:

```bash
python tools/run_kvzap_trace.py \
  --input-jsonl requests.jsonl \
  --request-id sample_01 \
  --output-dir traces/sample_01
```

The output directory contains:

```text
manifest.json
score_mask.npz
request_summary.csv
layer_head_summary.csv
decoding_events.csv
answer.json
```

`score_mask.npz` contains `scores`, `score_valid_mask`,
`predicted_drop_mask`, `final_drop_mask`, and `shape`. The pilot stores boolean
masks unpacked for simple inspection; `manifest.json` records this explicitly.
Later large benchmark traces should use sharding and bit packing as specified in
`TRACE_SCHEMA.md`.

## What to send back

First send the terminal output plus `manifest.json`, `request_summary.csv`, and
`layer_head_summary.csv`. For run-length, block occupancy, and head-similarity
analysis, also transfer `score_mask.npz`. The answer file is useful only when an
equivalence or quality issue needs inspection.

## Offline structural analysis

Analyze a trace without loading Qwen3:

```bash
python tools/analyze_kvzap_trace.py \
  traces/qwen3_8b_single_384 \
  --output-dir analysis/experiments/qwen3_8b_single_384_analysis
```

Multiple traces can be compared after the listed source directories have been
generated and each contains a complete trace:

```bash
python tools/analyze_kvzap_trace.py \
  traces/retrieval_01 \
  traces/summarization_01 \
  traces/reasoning_01 \
  --output-dir analysis/experiments/qwen3_8b_multi_request_analysis
```

Use `--no-plots` if only CSV/JSON artifacts are wanted. Plotting requires
`matplotlib`; all other analysis uses the project's NumPy dependency.

The analyzer validates the trace schema, tensor shapes, finite scores, sliding
window, and request-level KV counts before writing:

```text
analysis_manifest.json
request_summary.csv
layer_head_retention.csv
run_length_summary.csv
run_length_distribution.csv
block_occupancy.csv
head_similarity.csv
score_threshold_sensitivity.csv
decoding_growth.csv
figures/
```

Block estimates report both an exact-span value and a conservative padded value
for the final partial block. These are offline keep-any allocation estimates,
not measured GPU memory. `decoding_growth.csv` labels multi-token prompt chunks
separately from one-token generation so they are not mistaken for decode bursts.

Lightweight test:

```bash
pytest -q tests/test_analyze_kvzap_trace.py
```
