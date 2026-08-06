# KVzap repository inventory

## 1. Scope and evidence

This inventory records the repository state inspected on 2026-08-06 at commit
`8bb3315aa552d2d0b33f38ef0835e68cfa49a11a` (`research/kvzap-latest`). The
working tree already contained user changes and untracked research documents;
they were treated as input and were not modified.

Evidence used:

- repository instructions: `AGENTS.md`, `RESEARCH_CONTEXT.md`,
  `TRACE_SCHEMA.md`, and `CODEX_FIRST_TASK.md`;
- repository documentation: `README.md`, `kvzap/README.md`, and
  `evaluation/README.md`;
- implementation and tests cited below;
- local paper `papers/KVzap.pdf` (arXiv:2601.07891v1, 20 pages).

No model or dataset was downloaded, no benchmark or training job was run, and
no implementation file was changed. Therefore model/checkpoint availability is
reported from the paper, README, and checkpoint-name construction in code, not
from a successful local load.

## 2. Top-level layout

| Path | Role in this study |
| --- | --- |
| `kvpress/` | Core library, pipeline, attention patch, and press implementations. |
| `kvpress/presses/` | KV compression/scoring methods, including KVzap and DMS. |
| `kvzap/` | KVzap-specific README, training/data collection, and AIME25 evaluation. |
| `evaluation/` | Generic benchmark CLI, registries, configs, launch scripts, metrics, and dataset adapters. |
| `evaluation/benchmarks/` | AIME25, InfiniteBench, LongBench, LongBench-v2, LooGLE, Math500, needle-in-a-haystack, RULER, and ZeroScrolls. |
| `tests/` | Unit/integration tests for presses, head-wise masking, attention patching, decoding, and pipeline behavior. |
| `notebooks/` | Demos and speed/memory experiments; not the primary reproducible CLI. |
| `papers/` | Local KVzap paper (`KVzap.pdf`). |
| `analysis/` | Research inventory and future analysis artifacts (created for this task). |

The project package is `kvpress` version `0.5.4` (`pyproject.toml`). The primary
runtime dependencies are PyTorch, Transformers, Datasets, Pandas, Accelerate,
and Python Fire. Evaluation dependencies are optional.

## 3. Entry points and key symbols

### 3.1 User-facing inference

| File / symbol | Function |
| --- | --- |
| `kvpress/pipeline.py:24` — `KVPressTextGenerationPipeline` | Main user-facing inference pipeline, registered as `kv-press-text-generation`. |
| `kvpress/pipeline.py:172` — `_forward` | Prefills the context under the press hook, then greedily decodes one or more questions. |
| `kvpress/pipeline.py:263` — `generate_answer` | Performs question forward pass and token-by-token greedy decoding. |
| `kvpress/presses/base_press.py:164` — `BasePress.__call__` | Registers a post-forward hook on every supported self-attention layer. |
| `kvpress/__init__.py:50-51` | Globally patches Transformers attention functions at import time. |

The context prefill call is `self.model.model(...)` at
`kvpress/pipeline.py:215-220`; the question and generated-token calls are at
`kvpress/pipeline.py:289-309`.

### 3.2 Benchmark/evaluation

| File / symbol | Function |
| --- | --- |
| `evaluation/evaluate.py:37` — `EvaluationConfig` | Defines generic evaluation configuration and CLI-overridable fields. |
| `evaluation/evaluate.py:188` — `EvaluationRunner` | Creates output directories, press, model/pipeline, dataset, inference, predictions, and metrics. |
| `evaluation/evaluate.py:528` — `CliEntryPoint` | Python Fire entry point; YAML defaults are overridden by CLI arguments. |
| `evaluation/evaluate_registry.py:50` | Dataset-to-Hugging-Face-ID registry. |
| `evaluation/evaluate_registry.py:78` | Press registry, including `kvzap_linear` and `kvzap_mlp`. |
| `kvzap/evaluate_aime.py:34` — `evaluate` | KVzap-specific AIME25 entry using `model.generate`, sampling, and decoding-time DMS. |

The generic evaluator groups rows by identical context and performs one prefill
per context group (`evaluation/evaluate.py:428-455`). Consequently, a future
trace “request” must be defined explicitly: for the generic evaluator the
natural unit is a context group/prefill, not necessarily one CSV row/question.

### 3.3 KVzap predictor and checkpoint loading

| File / symbol | Function |
| --- | --- |
| `kvpress/presses/kvzap_press.py:14` — `KVzapConfig` | Stores input/output/hidden dimensions and number of layer modules. |
| `kvpress/presses/kvzap_press.py:25` — `KVzapModel` | Holds one Linear or two-layer GELU MLP predictor per transformer layer. |
| `kvpress/presses/kvzap_press.py:64` — `KVzapPress.post_init_from_model` | Constructs the Hugging Face predictor ID and calls `KVzapModel.from_pretrained`. |
| `kvpress/presses/kvzap_press.py:70` — `KVzapPress.score` | Selects the predictor for `module.layer_idx` and maps hidden states to per-KV-head scores. |

The constructed ID is:

```text
nvidia/KVzap-{linear|mlp}-{model.config.name_or_path basename}
```

The code does not accept an explicit local checkpoint path through
`KVzapPress`; it derives the ID from the base model name. A differently named or
local base model may therefore construct a nonexistent predictor ID.

### 3.4 Threshold, window, indices, and logical eviction

| File / symbol | Function |
| --- | --- |
| `kvpress/presses/dms_press.py:15` — `DMSPress` | Wraps `KVzapPress`, owns threshold/window/decoding state and the score buffer. |
| `kvpress/presses/dms_press.py:88-96` | Computes scores for newly created KV entries and initializes/appends the per-layer score buffer. |
| `kvpress/presses/dms_press.py:98-106` | Removes matured scores from the window and applies `scores_to_evict < threshold`. |
| `kvpress/presses/dms_press.py:109-120` | Converts buffer-relative token positions to cache-absolute indices and accumulates them in `module.masked_key_indices`. |
| `kvpress/attention_patch.py:43` — `attention_patch` | On later attention calls, replaces indexed keys with fake keys whose attention contribution is numerically zero. |

`DMSPress` does **not** call `gather`, shorten `cache.layers[*].keys/values`, or
allocate a compact KV layout. Physical `gather` exists in the generic fixed
ratio `ScorerPress.compress` (`kvpress/presses/scorer_press.py:92-100`), but
KVzap's documented path wraps the scorer with `DMSPress` and bypasses that
method. Thus the current KVzap result is a logical removed fraction represented
by head-wise indices; it is not physical cache compression or measured memory
saving.

## 4. Actual KVzap data flow and pruning timing

```text
attention-layer input hidden states [B,T,Dh]
        |
        | normal attention computes and appends K/V first
        v
post-forward DMS hook
        |
        +-- per-layer KVzap Linear/MLP -> scores [B,Hkv,Tnew]
        +-- append scores to scores_buffer[layer]
        +-- protect newest W=128 scores in buffer
        +-- for scores that just matured: score < threshold
        +-- accumulate (batch, kv_head, absolute_token) indices
        v
future attention invocation
        |
        +-- attention patch overwrites indexed keys with fake keys
        +-- dense K/V tensor and sequence dimension remain allocated
```

Pruning is after attention:

1. `BasePress.__call__` registers `register_forward_hook`, not a pre-hook.
2. `DMSPress.forward_hook` reads K/V already appended to `past_key_values`.
3. During prefill, the attention patch clears old indices when query length
   equals key length; the DMS hook then installs indices for subsequent calls.
4. During decoding, a new score is produced only after that token has
   participated in its creation-time attention. Once a score leaves the
   128-token buffer, its threshold decision affects future attention calls.

This matches the paper's experimental statement that all compression was
applied after attention. The paper's suggestion that pruning could occur before
attention is explicitly future work and is not the current code path.

## 5. Tensor shapes and index semantics

Symbols: `B` batch size, `L` transformer layers, `Tnew` tokens processed by the
current attention call, `Tcache` dense cache length, `W=128`, `Dh` model hidden
size, `Hkv` KV heads, `Hq` query heads, and `D` head dimension.

| Object | Shape / representation | Source and notes |
| --- | --- | --- |
| Layer input hidden states | `[B, Tnew, Dh]` | `BasePress`/`ScorerPress` docstrings; passed to KVzap. |
| Keys and values | each `[B, Hkv, Tcache, D]` | `extract_keys_and_values`; DMS passes only the newest `Tnew` slice to the scorer. |
| Linear predictor | `Dh -> Hkv` per layer | `KVzapModel.layers[layer_idx]`. |
| MLP predictor | `Dh -> hidden_dim -> Hkv` per layer | GELU between projections. Paper uses `hidden_dim=Dh/8`. |
| Raw score for one layer/call | `[B, Hkv, Tnew]` | Predictor output `[B,Tnew,Hkv]` transposed at `kvzap_press.py:81`. |
| Score buffer for one layer | `[B, Hkv, <=W]` after eviction processing | During prefill it is first `[B,Hkv,T]`; after matured entries are processed, only the newest `W` remain. During decoding new scores append, then the prefix beyond `W` is processed. |
| Matured scores | `[B, Hkv, n_to_evict]` | `n_to_evict = buffer_length - W`. These are compared with the threshold. |
| New masked indices | three 1-D integer tensors `[Nnew]` | Output of `torch.where`: batch, KV head, and buffer-relative token; token positions are shifted to dense-cache absolute positions. |
| Accumulated masked indices | three 1-D tensors `[Nmasked]` per attention module | Stored in `module.masked_key_indices`; this is the current final logical drop set. |
| Dense query in attention patch | `[B, Hq, Tq, D]` | Reshaped into KV-head groups to construct one fake key per `(B,Hkv)`. |
| Dense K/V after masking | still `[B, Hkv, Tcache, D]` | Indexed keys are overwritten; values and tensor length are not compacted. |

There is no repository-native stacked `[L,H,T]` score or mask tensor today.
A trace exporter must construct it explicitly (or store per-layer ragged records
with shapes and offsets) and must not rely on an implicit reshape.

### Sliding-window semantics

- Default `sliding_window_size` is 128.
- The buffer stores the newest score positions. Only the prefix that has left
  the window is thresholded.
- Code uses `score < threshold` for drop; therefore equality is kept, equivalent
  to the paper pseudocode's `score >= threshold` keep rule.
- Prefill with `T <= 128` creates no masked indices.
- During decoding, score buffering is active only when `DMSPress.decoding=True`.
  The generic registry creates KVzap DMS presses with the default `False`; the
  KVzap AIME script explicitly sets it to `True`.

## 6. Officially documented commands (not executed)

These commands are copied from repository documentation or scripts. They are
not inferred CLI options.

### Installation

```bash
uv sync
uv sync --extra eval --extra flash-attn
```

### Direct KVzap pipeline usage

The official `kvzap/README.md` example uses:

```python
from transformers import pipeline
from kvpress import KVzapPress, DMSPress

model = "Qwen/Qwen3-8B"
pipe = pipeline("kv-press-text-generation", model=model, device_map="auto", dtype="auto")
press = DMSPress(KVzapPress(model_type="mlp"), threshold=-4)
```

It sets `press.decoding=False` for prefill-only use or `True` for combined
prefill and decoding.

### Generic evaluation CLI

Run from `evaluation/`:

```bash
python evaluate.py
python evaluate.py --config_file <your_config.yaml>
python evaluate.py --dataset loogle --data_dir shortdep_qa --model meta-llama/Meta-Llama-3.1-8B-Instruct --press_name expected_attention --compression_ratio 0.5
```

The repository's four-GPU `evaluation/leaderboard.sh` gives the confirmed KVzap
form (one command shown, without recommending the long sweep):

```bash
python evaluate.py --dataset ruler --data_dir 4096 --model Qwen/Qwen3-8B --press_name kvzap_mlp --threshold -4 --output_dir ./results_lb --device cuda:0
```

The script comments specify thresholds `-3,-4,-5,-6` for Qwen3-8B and
`-6,-7,-8,-9` for Llama-3.1-8B-Instruct. The paper evaluates
`{-6,-5,-4,-3}` for Qwen3-8B/Qwen3-32B and `{-9,-8,-7,-6}` for Llama.

### AIME25

From `kvzap/`:

```bash
python evaluate_aime.py <model_type> --threshold <threshold> --model_name <base_model_name>
```

`<model_type>` is documented as `mlp`, `linear`, or `no_press`. This path uses
sampling (`temperature=0.6`, `top_p=0.95`, `top_k=20`) and defaults to up to
32k generated tokens, so it is a long benchmark and was not run here.

## 7. Models, predictors, and benchmarks

### Models and predictors confirmed by the paper

The paper reports experiments and trained Linear/MLP predictors for:

- `Qwen/Qwen3-8B`;
- `meta-llama/Meta-Llama-3.1-8B-Instruct`;
- `Qwen/Qwen3-32B`.

All three have `Hkv=8` in the paper. Hidden sizes are 4096, 4096, and 5120,
respectively. The paper reports the best configurations as Qwen3-8B MLP at
`tau=-4`, Llama-3.1-8B Linear at `tau=-7`, and Qwen3-32B MLP at `tau=-4`.

Code-derived expected checkpoint IDs include, for each base-model basename,
`nvidia/KVzap-linear-<basename>` and `nvidia/KVzap-mlp-<basename>`. Their remote
existence was not verified because this task prohibited downloads. No predictor
checkpoint is stored in this checkout.

`BasePress.SUPPORTED_MODELS` lists tested architecture classes for Llama,
Mistral, Phi3, Qwen2, Qwen3, and Gemma3, but this does **not** imply that a
matching pretrained KVzap predictor exists. KVzap support is limited by the
derived checkpoint ID unless a new predictor is trained.

### Benchmarks

Generic registry entries:

- LooGLE, RULER, ZeroScrolls, InfiniteBench;
- LongBench, LongBench-E, LongBench-v2;
- needle-in-a-haystack;
- AIME25 and Math500.

The KVzap paper reports RULER (`n=6500`), LongBench (`n=4750`), and AIME25
(`n=30`, four rollouts). RULER/LongBench use greedy decoding with reasoning
disabled; AIME25 uses Qwen reasoning and sampling.

## 8. Result formats and locations

### Generic evaluator

The default root is `evaluation/results` when invoked from `evaluation/`
(`output_dir: ./results`). A unique configuration directory encodes dataset,
subset, model, press, threshold/ratio, and selected options. It contains:

- `predictions.csv`: all dataset columns except raw `context`, plus
  `predicted_answer` and, for the grouped non-`DecodingPress` path, the reported
  `compression_ratio`;
- `metrics.json`: benchmark scorer output;
- `config.yaml`: resolved evaluation configuration plus the press
  representation.

Existing results are not overwritten: a numeric child directory is selected if
the configuration directory exists. If both predictions and metrics already
exist at the selected path, the run is skipped.

### AIME25-specific evaluator

The path is:

```text
kvzap/results/aime25__<model>__kvzap_<type>__<threshold>/<uuid>/
```

It saves `predictions.csv` and `metrics.json`, but no resolved config file.

### Compression terminology

`DMSPress.compression_ratio` is the average over layers of
`Nmasked / (B * Hkv * Tcache)`. It is a **removed fraction**, not a compression
factor. The paper's Table 2 also labels the parenthesized “compression ratio” as
removed fraction, while separately reporting factors such as `3.5x`. Future
trace/results must store both definitions from `TRACE_SCHEMA.md`:

```text
removed_fraction = 1 - kept / total
compression_factor = total / kept
```

## 9. Paper/code agreement and conflicts

### Confirmed agreement

- Predictor input is the attention-layer input hidden state; output is one score
  per KV head and token.
- Predictor is per-layer Linear or two-layer MLP.
- Fixed thresholding is input-adaptive; low scores are dropped.
- The newest 128 tokens are protected.
- Current experimental pruning timing is after attention.
- Decoding requires a score buffer to defer decisions until tokens leave the
  sliding window.

### Material conflict / implementation caveat

Paper Algorithm 1 returns indexed `keys[indices], values[indices]`, suggesting a
physically shortened representation. The checked-out DMS path instead stores
head-wise indices and overwrites keys inside dense attention. Its own
`attention_patch.py` docstring states that this does not reduce peak memory and
slightly increases runtime. Therefore the repository's reported KVzap
compression ratio is currently logical compression. It must not be cited as
physical GPU-memory reduction or wall-clock speedup.

### Other caveats

- The paper explicitly says wall-clock speedup and GPU memory saving were not
  explored and that variable-length PagedAttention engineering is non-trivial.
- The paper notes possible train/test distribution shift because training
  prompts are at most 1,250 tokens.
- The first transformer layer has poorer predictor correlation in the paper.
- `DMSPress.threshold` defaults to `None`; direct use without setting it will
  fail at comparison time. The generic evaluator asserts it is set.
- `masked_key_indices` grows by concatenation during decoding. Long reasoning
  outputs may incur metadata and concatenation overhead even though the score
  buffer itself remains bounded by 128 positions.
- The attention patch mutates dense keys in place. A trace hook must observe
  score/mask decisions in `DMSPress`, not attempt to reconstruct the original
  decision later from already modified K/V.
- The generic evaluator only records a single average removed fraction per
  context group; it does not preserve request/layer/head distributions.
- `evaluation/leaderboard.sh` is a multi-GPU sweep and is not suitable as the
  first small validation run.

## 10. Candidate trace hook points

Ranked by fidelity and invasiveness:

1. **Decision hook in `DMSPress.forward_hook` immediately after score creation
   and thresholding.** It has `layer_idx`, raw `[B,Hkv,Tnew]` scores,
   `scores_to_evict`, the exact threshold decision, window maturity, dense cache
   length, absolute indices, and prefill/decoding phase. This is the canonical
   hook for semantic score/mask traces.
2. **Request lifecycle in `EvaluationRunner._run_inference`.** It knows dataset
   row/context identity and can enable the recorder for exactly one context
   group, finalize it, and then leave tracing disabled for all remaining
   requests.
3. **Pipeline generation loop for decoding-size summaries.** Before/after each
   question or generated-token forward call, it can record step and dense cache
   lengths. For KVzap, logical per-head lengths should instead be derived from
   cumulative mask indices; dense `cache.get_seq_length()` alone is not a
   compressed size.
4. **Attention patch only as an optional assertion point.** It can verify that
   the installed absolute indices are consumed on a future attention call, but
   it is too late and too performance-sensitive to be the primary exporter.

Do not hook the full attention matrix; KVzap does not require it and the trace
schema prohibits it for large experiments.

## 11. Minimal trace patch plan (proposal only)

No part of this plan is implemented in the current task.

### 11.1 Proposed files

| File | Proposed minimal change |
| --- | --- |
| `kvpress/presses/dms_press.py` | Add an optional, non-serialized trace callback/sink field defaulting to `None`; emit detached score/decision records only when it is present. Do not change threshold, window, index shift, or mask installation. |
| `evaluation/evaluate.py` | Add explicitly documented proposed options such as `trace_dir` and `trace_request_limit` (default disabled/zero); establish/finalize request IDs around context groups and attach the sink only for selected requests. These are new options, not current CLI. |
| `kvpress/trace.py` (new) | Small recorder/writer implementing schema version checks, per-request/per-layer buffering, CPU transfer, NPZ score/mask shards, and JSON manifest. Keep file I/O out of the attention hook. |
| `tests/presses/test_dms_trace.py` (new) | Deterministic mock-scorer tests for disabled equivalence, enabled equivalence, shapes, exact threshold equality, absolute indices, and window protection. |
| `tests/test_trace_writer.py` (new) | Round-trip/shard tests, explicit layout metadata, bit packing, and one-request limiting without a model download. |
| `evaluation/README.md` and/or `analysis/reproduction_notes.md` | Document new flags, request-unit semantics, output schema, and a one-request command only after the CLI exists and `--help` confirms it. |

If an even smaller first patch is required, omit decoding-step Parquet and
request summaries initially: export one NPZ plus a manifest from a single
pipeline request, then add evaluation integration after semantic equivalence is
proven.

### 11.2 Default behavior guarantee

- All trace fields default to disabled (`None`/zero).
- The disabled branch performs no tensor clone, device transfer, mask
  materialization, synchronization, or file I/O.
- The existing score tensor is passed unchanged to the threshold comparison.
- When enabled, the recorder receives `scores.detach()` and copies to CPU after
  the decision; it never returns a tensor or value used by pruning.
- Final mask records are derived from the exact boolean comparison/indices
  already used by DMS, not from a second independently implemented threshold.
- Writes occur after the model call or via a bounded queue, never by modifying
  K/V or attention outputs.

### 11.3 Export exactly one request

- Define a generic-evaluator request as one unique context group/prefill and
  record the associated row IDs/questions in metadata.
- `trace_request_limit=1` arms the sink for the first selected context group,
  finalizes it after its question generation, then detaches the sink before the
  next group.
- A stable `request_id` should be derived from dataset/subset plus original row
  index or a collision-resistant hash; raw text is not saved by default.
- For a minimal direct smoke test, call the pipeline once with one context and
  one question; do not use a fractional dataset sample as a substitute for an
  exact one-request limit.
- Resume behavior should treat an already complete request shard as finished
  and must not overwrite it.

### 11.4 Verification

Fast, download-free unit tests:

1. With tracing disabled, compare output tensors, `scores_buffer`,
   `masked_key_indices`, and compression ratio against the unmodified path.
2. With tracing enabled, run the same seeded inputs and compare logits/output
   token IDs plus all pruning state exactly (not approximately).
3. Assert score `[B,Hkv,Tnew]`, matured mask shape, and three index tensors agree.
4. Assert tokens in the most recent 128 positions never appear in the final
   drop set; test `T<128`, `T=128`, and `T>128`.
5. Assert `score == threshold` is kept and only `score < threshold` is dropped.
6. Verify prefill absolute shift `0` and decoding shifts across multiple calls.
7. Round-trip bit-packed masks and NPZ offsets/shapes; merged shard statistics
   must equal an unsharded run.
8. Verify removed fraction and compression factor separately.

One small real-model validation, only after user approval and using already
available model/checkpoint assets:

- run one short request twice with fixed seed/config, trace off then on;
- compare generated token IDs, logits for the checked steps, per-layer final
  indices, and reported removed fraction;
- verify the manifest records commit, config hash, model, predictor ID/type,
  threshold, window, dtype, seed, pruning timing, and explicit tensor layout.

Do not start RULER/LongBench/AIME sweeps until this equivalence check passes.

### 11.5 Expected trace size

For raw per-request scores stored densely, the uncompressed size is:

```text
score_bytes = L * Hkv * T * bytes_per_score
mask_bytes_bitpacked = ceil(L * Hkv * T / 8)
```

For the paper's `Hkv=8`, a 4k-token request and `L=32..64` is approximately:

- FP16/BF16 scores: 2–4 MiB;
- FP32 scores: 4–8 MiB;
- one bit-packed mask: 0.125–0.25 MiB;
- both predicted and final masks: 0.25–0.5 MiB;
- manifest and layer/head summaries: normally well below 1 MiB.

Thus a minimal one-request 4k trace using FP16/BF16 scores, two bit-packed
masks, and metadata should be roughly 2.5–5 MiB before NPZ compression. At 128k
tokens the same dense score trace grows linearly to roughly 64–128 MiB for
`L=32..64`, so large runs require sharding and possibly recorded score
quantization. Storing three int64 indices for every dropped KV position can be
much larger than a bit mask (up to 24 bytes per dropped entry) and should not be
the primary on-disk mask format.

## 12. Open questions before implementation

1. Should “request” mean context group (matching the pipeline cache reuse) or
   individual dataset row/question? The manifest must state this explicitly.
2. Is the first trace target prefill-only generic evaluation, decoding-enabled
   AIME, or both? Prefill-only is the smallest semantic patch.
3. Should raw scores be stored in model dtype, normalized to FP16, or quantized?
   Threshold reproduction requires a recorded dtype/mapping and error bound.
4. Do we need both `predicted_mask` (all scores versus threshold) and
   `final_mask` (only matured/window-eligible drops)? For window analysis, both
   are valuable and must be clearly distinguished.
5. `module.masked_key_indices` represents cumulative logical drops in dense
   coordinates. A future physical backend will need a separate compact-index or
   page-table trace; it cannot infer physical allocation from this tensor alone.
6. The current AIME evaluator does not save a resolved config/seed and the
   generic evaluator does not expose a KVzap decoding flag. Reproducibility
   fields must be added before claiming Phase 0/1 completion.

## 13. Go/no-go conclusion for the next task

The repository is ready for a **minimal semantic trace hook** around
`DMSPress.forward_hook`, but not for structured pruning or a hardware model.
First capture the exact score-to-logical-mask behavior and prove trace-on/off
equivalence. Physical compression, page occupancy, HBM traffic, and speedup
cannot be measured from the present fake-key implementation and must remain
separate modeled quantities until a real compact backend exists.
