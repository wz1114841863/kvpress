# KVzap single-request trace

## Current status: predictor-only gate A passed

Phase 1 is not frozen, but predictor-only acceptance gate A passed on 2026-08-17.
The matched hardware run may now authorize a small Gate B collection for
retrieval, summarization, and reasoning. Stateful DMS/attention tracing remains
paused and is not revived by this decision.

The frozen machine-readable record is
`analysis/predictor_trace_gate_a.json`. Its experiment ID is
`kvzap-predictor-trace-20260817T080939Z`, the implementation commit is
`f97ccd8b60a388ae791607da6da28ff8d8616059`, and the config hash is
`6a645914544d8f7a03319c1d836eeb2d7f4d5f178dcf0196b371e9af7e13a1a4`.
The frozen predictor revision is
`bd5c5917846617da4311539859c137a262a6348b`.

One artifact remains useful as a bounded reference:

- `traces/qwen3_8b_single_384/` completed one hardware-themed request with the
  original two-pass exporter and recorded trace-on/off equivalence. It may be
  used only as the matched hardware reference for the next exporter.

Local reference checksums are:

- `manifest.json`:
  `b528402ab9be70ea51be41e27dc452e41d68895290c4e9bc42d255d6562667f2`;
- `score_mask.npz`:
  `5b84c600f3eacdaf073405ea73c61c94080f8fa4aaa11f750cbcd1a8565ad1c3`;
- `request_summary.csv`:
  `687e5a3c9108796698cc89d31447251695bfa3e3c3c843269934bd60c30ef9e4`.

Because `traces/` is ignored by Git, these hashes must be checked after the
reference directory is transferred to another machine.

The following artifacts/runs are invalid for scientific conclusions:

- `retrieval_prefill_01` and `retrieval_prefill_02` from the rolled-back
  prefill callback exporter;
- the reported `3.28%` retrieval removal result from that exporter;
- failed hardware prefill runs that produced zero events or only layers 30--35;
- any directory missing the complete schema or a passed provenance/equivalence
  gate.

## Failure audit

The failed attempts coupled tracing to mutable runtime state in `DMSPress` and
the attention patch. Observed failures included:

1. missing or stale `scores_buffer` state between prefill and decoding;
2. invalid/corrupted `masked_key_indices` and CUDA out-of-bounds indexing;
3. the existing KVPress `search_hyperplane` fake-key method failing for some
   query geometries;
4. recorder drop counts disagreeing with DMS cumulative counts;
5. trace-on and trace-off generation producing different token sequences;
6. a nominally prefill-only exporter recording no layer events, then on another
   input recording only layers 30--35;
7. an anomalous retrieval score distribution/removal rate that cannot be
   trusted because the same exporter failed the matched hardware control.

These failures do not show that the official KVzap predictor is ineffective.
They show that the attempted observer was entangled with `cache_position`,
`scores_buffer`, `masked_key_indices`, in-place fake-key masking, hook order, and
two-pass model state. The frozen Phase 0 baseline remains valid within its
documented smoke-test scope.

## Predictor-only observational trace

The first gate-A implementation is `tools/export_kvzap_predictor_trace.py`, with
this data flow:

```text
one normal context prefill
  -> observe each attention layer input hidden state
  -> invoke the official per-layer KVzap MLP immediately
  -> copy only score [1, KV-head, token] to CPU
  -> reconstruct predicted_drop = score < threshold offline
  -> reconstruct the prefill final mask by protecting the newest 128 tokens
```

It must not use `DMSPress.forward_hook`, mutate `scores_buffer` or
`masked_key_indices`, call the fake-key attention path, generate answer tokens,
or run the same model object twice. It must record that the final mask is an
offline reconstruction of the documented prefill rule, not an observed decode
mask.

The matched hardware Gate A command was:

```bash
python tools/export_kvzap_predictor_trace.py \
  --reference-trace traces/qwen3_8b_single_384 \
  --output-dir traces/hardware_predictor_gate_a_01 \
  2>&1 | tee hardware_predictor_gate_a_01.log
```

It reported exact score equality, shape `[36, 8, 987]`, and reconstructed
prefill logical removal `74.34003152088259%`. Independent inspection confirmed
all scores finite, all score-valid flags true, exact `score < -4` masks, exact
128-token window protection, and 288 complete layer/head summary rows.

### Acceptance gate A: matched hardware reference

Before collecting any new task type, compare against
`traces/qwen3_8b_single_384/score_mask.npz` using the identical 987-token
hardware context:

1. exactly 36 layers and 8 KV heads are present;
2. score layout is exactly `[36, 8, 987]`;
3. per-element scores match the reference within a documented BF16 tolerance;
4. `score < -4` produces the same predicted mask;
5. offline window protection produces approximately `74.34003152088259%`
   prefill logical removal, matching the recorded prefill event;
6. mismatches must preserve diagnostics and fail the gate rather than silently
   writing a valid manifest.

### Acceptance gate B: new task traces

Only after gate A passes may retrieval, summarization, and reasoning inputs be
collected. Each request runs in a fresh process and must record model,
checkpoint revision, threshold, window, seed, input hash, token count, tensor
shape, dtype, and source git commit. These traces may support score distribution,
margin, run-length, block occupancy, head similarity, and load-imbalance
analysis only.

Gate B is implemented by the same exporter using schema
`kvzap-predictor-trace-1.1`. Before model loading, every Gate B run verifies the
exact Gate A artifact hashes and metadata. It accepts one built-in preset or one
selected JSONL request per process, and records the resolved model and predictor
revisions. Start with retrieval only:

```bash
python tools/export_kvzap_predictor_trace.py \
  --preset retrieval \
  --gate-a-evidence traces/hardware_predictor_gate_a_01 \
  --output-dir traces/retrieval_predictor_gate_b_01 \
  2>&1 | tee retrieval_predictor_gate_b_01.log
```

Do not launch the other presets until this first Gate B directory has been
returned and checked. A custom JSONL row requires `request_id`, `context`, and
`question`; `dataset` and `subset` are optional. A multi-row file additionally
requires `--request-id` so that each process still handles exactly one request.

### Deferred work

Generation accuracy remains a separate baseline/benchmark path. Actual DMS
prefill-mask equivalence, decoding maturity/admission events, physical KV
compaction, and speed measurement are deferred until predictor-only traces are
stable. None may be inferred from the observational score trace.

## Historical exporter: what is captured

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

## Historical exporter: safety and equivalence check

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

## Historical two-pass trace command (reference only)

The following command produced the bounded hardware reference. It is retained
for provenance, not recommended for collecting new requests:

```bash
python tools/run_kvzap_trace.py \
  --max-new-tokens 384 \
  --output-dir traces/qwen3_8b_single_384
```

The destination must not already exist. Generated trace directories are ignored
by git because the compressed score tensor can still be several MiB or larger.
Transfer the selected trace directory separately, or force-add only a deliberately
small artifact after reviewing its size.

### Historical stateful built-in request types (do not use)

These commands document the previous interface. Do not run them as new evidence
because they exercise the rolled-back stateful DMS/attention trace path:

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
