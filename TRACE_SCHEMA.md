# TRACE_SCHEMA.md

## 1. 目标

Trace 用于离线分析 KVzap 的 predictor score、最终 mask、物理布局和 decoding 时间演化。Trace 必须可分片、可压缩、可复现，并且开启后不能改变模型输出。

## 2. 建议文件组织

```text
traces/<experiment_id>/
  manifest.json
  request_summary.parquet
  layer_head_summary.parquet
  score/
    shard_00000.npz
  mask/
    shard_00000.npz
  decoding/
    shard_00000.parquet
```

若仓库已有格式，优先复用。

## 3. manifest.json

建议字段：

```json
{
  "schema_version": "1.0",
  "git_commit": "<commit>",
  "config_hash": "<hash>",
  "model": "<model>",
  "predictor": "linear|mlp",
  "predictor_checkpoint": "<path-or-id>",
  "dataset": "<dataset>",
  "subset": "<subset>",
  "threshold": -4.0,
  "sliding_window": 128,
  "dtype": "bfloat16",
  "seed": 0,
  "pruning_timing": "after_attention",
  "tensor_layout": "L,H,T",
  "created_at": "<iso8601>"
}
```

## 4. request_summary.parquet

每个 request 一行：

- `request_id`
- `dataset`
- `subset`
- `prompt_tokens`
- `generated_tokens`
- `correct`
- `metric_value`
- `threshold`
- `window`
- `logical_kept_kv`
- `logical_total_kv`
- `removed_fraction`
- `compression_factor`
- `runtime_ms`（若有）
- `seed`

定义：

```text
removed_fraction = 1 - logical_kept_kv / logical_total_kv
compression_factor = logical_total_kv / logical_kept_kv
```

## 5. layer_head_summary.parquet

每个 `(request, layer, kv_head)` 一行：

- `request_id`
- `layer`
- `kv_head`
- `sequence_tokens`
- `kept_tokens`
- `removed_tokens`
- `retention_ratio`
- `score_mean`
- `score_std`
- `score_min`
- `score_max`
- `margin_abs_mean`
- `near_threshold_fraction`
- `zero_run_mean`
- `zero_run_p90`
- `one_run_mean`
- `one_run_p90`

## 6. score shard

建议保存：

- `request_ids`: `[N]`
- `offsets`: `[N+1]`
- `scores`: 扁平数组
- `shapes`: `[N,3]`，每项为 `(L,H,T)`

允许量化存储，但必须记录：

- scale；
- zero point；
- 原始 dtype；
- 量化误差；
- threshold 的映射方式。

## 7. mask shard

优先 bit-pack：

- `request_ids`
- `offsets`
- `mask_bits`
- `shapes`
- `bit_order`

同时保存 sliding-window 强制保留前后的 mask 时，应明确区分：

- `predicted_mask`
- `final_mask`

## 8. decoding trace

每个 `(request, step, layer, kv_head)` 一行或按需聚合：

- `request_id`
- `step`
- `layer`
- `kv_head`
- `hot_tokens`
- `cold_tokens`
- `newly_admitted_tokens`
- `newly_dropped_tokens`
- `active_pages`
- `sealed_pages`
- `allocated_bytes`
- `metadata_bytes`

若体积过大，允许只保存 request/step 或 layer/step 汇总，但需在 manifest 中说明聚合方式。

## 9. 兼容性要求

- 新 schema 版本不得覆盖旧 trace；
- 分析脚本必须检查 schema version；
- shape、dtype、layout 必须显式保存；
- trace 合并后结果必须与未分片运行一致；
- 不保存完整 attention matrix，除非是明确指定的小样本。

## 10. Predictor-only observational profile (`kvzap-predictor-trace-1.1`)

当前稳定的 predictor-only exporter 使用一个更窄的 profile：

- `score_mask.npz` 包含 `scores`、`score_valid_mask`、
  `predicted_drop_mask`、`reconstructed_final_drop_mask`、
  `context_token_ids` 和显式 `shape`；
- final mask 是 `score < threshold` 加 prefill 末尾 128-token 保护的离线重建；
- `gate_a_evidence.json` 必须与 manifest 内嵌证据完全一致且所有检查通过；
- 不生成答案，不使用 DMS、fake-key attention 或 `masked_key_indices`；
- 不包含 `decoding_events.csv`，因此 decoding growth/admission 指标明确不可用；
- `request_summary.csv` 的 token 字段为 `context_tokens_scored` 和
  `question_tokens_not_scored`，question 不属于 score/mask 的 token 轴。

该 profile 可用于 score、margin、retention、run-length、block occupancy 和
layer/head imbalance 分析，不能用于答案精度、decode 生命周期、物理显存或速度结论。

## 11. Multi-request pilot manifest

真实样本 pilot 不把多个请求塞入同一模型进程。`tools/run_kvzap_predictor_pilot.py`
为每个 JSONL request 启动一个新的 predictor-only exporter，并在 output root 保存：

```text
pilot_run_manifest.json
logs/<stable-request-name>.log
requests/<stable-request-name>/<predictor-trace-files>
```

`pilot_run_manifest.json` 必须记录输入 JSONL/manifest/exporter 的 SHA-256、Gate A
路径、threshold、window、seed、shard 配置、每个 request 的 source metadata、状态、
日志和 trace 目录。Resume 只能跳过通过完整离线校验的请求；不完整目录禁止覆盖。

## 12. Balanced pilot preparation 与分组分析

`kvzap-real-pilot-1.1` preparation manifest 在 v1.0 provenance 基础上增加：

- `selection_policy=rotating-balanced-round-robin-v2`；
- 每个 category/length bucket 的 `available_by_task` 与 `selected_by_task`；
- `tasks_without_candidates` 与 `available_tasks_not_selected`，禁止静默掩盖 task coverage 缺口；
- 默认目标为每个 category/length bucket 5 条，共 45 条。

离线分析传入 `--pilot-manifest` 后必须生成 `request_group_summary.csv`，至少包含：

- `all`、`category`、`task`、`length_bucket` 分组；
- request count 和 token 范围；
- request-mean、weighted、P50、P90、min/max logical removed fraction；
- weighted/mean logical compression；
- layer/head load CV、head keep Jaccard、score-margin 汇总。

`head_similarity.csv` 同时保存实际 Jaccard、在 observed marginal keep/drop rates 下
independent mask 的期望 Jaccard，以及 `actual - expected` excess。该 excess 只用于区分
边际保留率导致的表观重叠与额外 token-position sharing，仍不能推出共享 mask 的精度。

## 13. Frozen-pilot structured policy evaluation

`tools/evaluate_kvzap_structured_masks.py` consumes only validated
`kvzap-predictor-trace-1.1` traces and writes a separate, never-overwritten
evaluation directory. `head_length_bucketing.csv` rounds per-layer/head cold
capacity to a token quantum and does not change a mask. In contrast,
`structured_policy_request.csv` applies margin-aware B=4/8 coalescing only to
the mature cold region and reports both `newly_dropped_fraction` and
`recovered_keep_fraction`.

The protected trailing window must remain unchanged. Positive coalescing
margins may add drops and are candidates for later accuracy evaluation only.
`structured_policy_summary.csv` reports both weighted and request-mean padded
physical-compression estimates; neither is measured memory or speed.

## 14. Phase-3 physical-layout estimate

`tools/evaluate_kvzap_physical_layout.py` consumes the same validated
predictor-only traces without loading a model. It reports two named, mutually
non-interchangeable storage estimates for each policy and page size:

- `packed`: a per-layer/head arbitrary-token compaction lower bound, followed
  by page rounding;
- `timeline`: original token-position pages, allocated whenever a page has one
  or more kept mature tokens.

The output also records page metadata and one-query all-active-KV read-byte
proxies under explicit byte assumptions. These are analytical estimates, not
allocator measurements, physical HBM traces, bandwidth, latency, or speed.

## 15. Route-A packed-page and lifecycle evidence

The active Route-A contract is `analysis/route_a_research_plan.md`. It keeps
the original KVzap final mask and distinguishes two evidence tiers.

### Static packed-page replay

Frozen predictor-only prefill traces can support a model-free replay into
append-only, per-`(layer, kv_head)` packed cold-page lists. Every result must
record page size, cache dtype/bytes per K+V token, page metadata format/bytes,
and whether it is a packed lower bound or a timeline-position layout. Required
outputs include logical kept tokens, allocated slots, tail waste, page count,
metadata bytes, and per-head P50/P95/P99/max page counts.

Static replay may not claim an admission rate, packing break-even, real HBM
traffic, allocator memory, latency, or throughput.

`tools/simulate_kvzap_packed_pages.py` implements the Route-A0 profile as
`kvzap-route-a0-static-packed-page-replay-1.0`. It accepts only validated
predictor-only traces and writes a new directory containing
`request_packed_page_replay.csv`, `layer_head_packed_page_replay.csv`,
`packed_page_replay_summary.csv`, and `replay_manifest.json`. The manifest
records source `manifest.json`/`score_mask.npz` hashes, cache dtype and byte
assumptions, page metadata bytes, and git commit.

For a final mask `[L,H,T]`, `hot_slots` are valid trailing-window positions;
each mature kept stream independently allocates
`ceil(cold_logical_kept_slots / page_tokens) * page_tokens` cold slots.
`tail_waste_slots` is the difference from mature kept slots and
`fragmentation_fraction` divides it by cold allocated slots. Byte fields are
storage accounting assumptions, not HBM traffic measurements. This profile is
always a static final-mask replay, never a decode-admission replay.

### Route-A1 scheduler DSE

`tools/simulate_kvzap_route_a1_scheduler.py` consumes only a completed A0
directory, not a model or raw trace. It forms deterministic sequential
combinations of independent request trace IDs and labels every combination as a
simulated serving batch. The final short batch is retained with its explicit
actual size unless `--drop-incomplete-batch` is selected.

The output directory contains `scheduler_layer_results.csv`,
`scheduler_batch_results.csv`, `scheduler_summary.csv`, and
`scheduler_manifest.json`. The manifest must hash the A0 replay inputs and
record all cost constants, PE count, page size, policy, source order, and batch
construction. Policies are `static_head`, `length_aware_head`, and
`dynamic_page`; the latter records per-task dispatch and serial partial-softmax
merge cost separately. `useful_cycles`, overhead cycles, utilization,
makespan, queue depth, and fairness fields are modeled quantities only. They
are not actual scheduling traces, HBM measurements, latency, throughput, or
decode-lifecycle evidence.

### Read-only decode-lifecycle trace (Route-A2 collector)

Only after static packing and scheduling DSE selects plausible parameters may a
new collector record generated-token maturity. It must prove output/mask
equivalence with tracing disabled and must not mutate `DMSPress`,
`scores_buffer`, `masked_key_indices`, or fake-key attention state.

The lifecycle trace must make these fields explicit per request/step/layer/head
or under a documented aggregation:

- `hot_tokens_before`, `matured_tokens`, `cold_admitted_tokens`, `cold_dropped_tokens`;
- `cold_page_allocations`, `cold_page_seals`, `tail_valid_count`;
- `hot_to_cold_read_bytes`, `cold_write_bytes`, `metadata_update_bytes`;
- `cold_logical_tokens`, `cold_allocated_slots`, `cold_page_count`.

These trace-derived events are still not HBM counter measurements. They are the
inputs to a separately parameterized break-even and cycle model.

`tools/run_kvzap_decode_lifecycle_trace.py` implements the Route-A2 collector.
It runs normal dense-KV generation without `DMSPress`, observes attention inputs
through read-only forward hooks, and applies the fixed official predictor only
for lifecycle accounting. It must never write `scores_buffer`,
`masked_key_indices`, fake keys, or the model cache. It uses three same-seed
passes: normal/no observer, observer/no serialization, and observer/serialized.
The answer hash must match across all passes and the two observer lifecycle
digests must match before it writes anything.

Its output includes `lifecycle_events.csv` (one model-call/layer/KV-head row),
`lifecycle_final_state.csv`, and `lifecycle_manifest.json`. Event fields cover
hot tokens before maturity, matured tokens, admitted/dropped tokens, page
allocations/seals, tail validity, and declared hot-to-cold/cold-write/metadata
byte accounting. The manifest also records phase-wise request calls/query
tokens and aggregate L/H work, observed `q_len=1` decode-call count, the
generated-token-id count implied by the fixed KVPress greedy loop, and a
separately labelled decoded-answer re-tokenization count. These bytes are
based on manifest assumptions and must not be called HBM traffic or allocator
measurements.

`tools/replay_kvzap_decode_lifecycle_pages.py` is a second, model-free stage:
it validates one lifecycle directory, then replays its already-recorded cold
admissions for one or more page sizes. It outputs replay event/final/summary
CSVs plus a source-hash manifest. Its page-size sweeps are static
capacity/accounting comparisons only; they do not re-run generation, measure
admission, or establish HBM, allocator, latency, throughput, or break-even
results.

When a prior A2 sample ends too early for a meaningful decode horizon,
`tools/screen_kvzap_a2_output_horizon.py` may first screen an explicitly named,
small candidate set sequentially. It runs ordinary dense-KV greedy generation
without predictor, observer, DMS, or pruning and stores only answer hashes plus
decoded-text re-tokenization lengths. This length is a selection proxy, not an
accuracy metric or lifecycle measure; only a subsequent three-pass A2 collector
run establishes the authoritative decode-call horizon.
