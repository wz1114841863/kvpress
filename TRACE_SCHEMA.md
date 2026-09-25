# TRACE_SCHEMA.md

## A4.1.5 external-storage profiler attribution

`kvzap-route-a4148-qwen-external-storage-profiler-1.0` records one separate
`torch.profiler` diagnostic capture for each of `full_kv_bypass`,
`same_mask_dense_replay`, and
`same_mask_route_a_external_storage_replay`. Context prefill/cache setup is
outside profiler scope. The operator summary is bounded to `top_operators` and
contains generic profiler CPU/device time and memory accounting; optional Chrome
traces are named only when `export_chrome_traces` is enabled. The Route-A record
contains only bounded ownership/page/ULP scalar guards. Profiler values must not
be pooled with A4.1.4 timing distributions or described as HBM traffic,
latency, throughput, energy, area, hardware, or RTL evidence.

## A4.1.6 phase-attributed external-storage profiler

`kvzap-route-a4149-qwen-external-storage-phase-profiler-1.0` is a separate
one-capture diagnostic for the replayed dense and external-storage Route-A
references. `route_a_phase::` profiler ranges label existing reference
operations: external cache append/materialization, maturity/admission/page
work, hot/pending/packed partial attention, online merge, same-mask dense
reference, FP32 guard, execution-dtype guard/diagnostic, and scalar summary.
The labels are nested and may be inclusive, so their times cannot be summed or
treated as latency data. They do not change mask replay, state ownership,
attention, or numerical-guard semantics.

## A4.1.6.1 paired phase-profiler coverage repair

`kvzap-route-a4150-qwen-external-storage-paired-phase-profiler-1.0` repairs
the A4149 reporting coverage: dense multi-token bridge operations receive
explicit `multi_token_*` ranges; same-name CPU/CUDA profiler views are coalesced
without doubling semantic invocation counts; and a phase-label coverage guard
requires labelled selected-head attention evaluations to equal the backend's
decode plus multi-token policy evaluations. Coalesced phase rows remain nested,
inclusive profiler diagnostics and cannot be summed or treated as timing data.

## A4.1.7.0 guard-elided execution semantic certification

`kvzap-route-a4151-guard-elided-execution-semantic-gate-1.0` is untimed. It
compares guarded Route-A external storage with an `execution_only` variant that
retains replay, Route-A state, external ownership, page and poison guards but
does not run per-query same-mask dense reference/FP32/dtype/ULP checks. It
stores only scalar paired full-model-logit relations and token digests, never
full logits. Passing certifies this fixed replay/request only; it is neither a
performance nor quality claim.

## A4.1.7.1 certified execution-mode whole-decode measurement

`kvzap-route-a4152-certified-execution-mode-whole-decode-measurement-1.0`
records repeated synchronized software measurements only after two separate
semantic prerequisites: a matching completed A4.1.7.0 Route-A certificate and
a fresh guard-on versus execution-only same-mask dense certificate. Raw rows
use `kvzap-route-a4152-certified-execution-mode-whole-decode-raw-repetition-1.0`.
They retain the A4.1 whole-decode timing/allocator fields plus only scalar
token/answer digests. Timed Route-A runs still require replay completion,
external ownership/native-cold exclusion and page coverage; they elide only
per-query numerical reference work. The three paths remain Full-KV bypass,
same-mask dense execution-only, and Route-A external-storage execution-only.
This is separate from guarded A4.1.4 timings and profiler captures; allocator
fields remain PyTorch observations rather than HBM traffic.

Execution-only artifacts additionally record actual same-mask numerical-guard
work counts. A requested `execution_only` mode is valid only when every
selected layer reports zero work; a mode flag alone is insufficient.

## A4.1.7.3 empty-source-elision semantic gate

`kvzap-route-a4154-empty-source-elision-semantic-gate-1.0` compares external
Route-A execution-only baseline with a candidate that skips only empty
hot/pending/packed partials. It records scalar paired logits/tokens, per-layer
skip counts and component-call counts. The named budget-512 gate requires an
empty pending skip and source accounting in which each merge evaluation has
exactly one partial or one skip per source; hot and packed attention must still
be observed. It is untimed semantic evidence only.

## A4.1.7.2 execution-only paired phase-profiler

`kvzap-route-a4153-execution-mode-paired-phase-profiler-1.0` is one diagnostic
capture each for certified same-mask dense execution-only and certified Route-A
external-storage execution-only. It inherits the matching A4151 certificate
and records a fresh dense certificate before profiling. The summary stores
coalesced CPU/CUDA profiler rows, scalar token digests, phase-label coverage,
and external ownership/page guards. Phase ranges are nested and may be
inclusive, so no phase value may be summed or treated as latency; all profiler
memory fields remain software diagnostics, not HBM traffic.

## A4 untimed semantic-gate scalar diagnostics

For an A4 native-storage gate using `execution_dtype_ulp_mode=record_only`,
the manifest may include `execution_dtype_ulp_breaches` below each paired
path. It contains only mode, limit, count, maxima and a bounded list of scalar
samples; it must never serialize K/V, attention, activation, or full-logit
tensors. `record_only` does not disable the FP32 same-mask guard. If
`execution_dtype_close_mode=quantization_aware_enforce`, that configured
cast-aware envelope remains a hard gate. These fields are semantic numerical
diagnostics, not timing, allocator, HBM-traffic, quality, or hardware metrics.

For a budget-512 native-storage page-state gate, the manifest must additionally
record the replay-source admission budget and `aggregate_page_coverage`. A
positive page witness identifies one layer/KV-head with at least one sealed
full page, multiple packed pages, and a nonempty packed tail; it is aggregate
coverage, not a requirement that every head retain cold K/V.

## A4.1.4 external-storage whole-decode measurement

`kvzap-route-a4147-external-storage-whole-decode-raw-repetition-1.0` records
one synchronized `question_forward_plus_greedy_decode` region per reset run.
The timed region begins only after that path's context prefill and cache setup;
its `memory_before` and `memory_after` are PyTorch allocator snapshots in
bytes. Path names are `full_kv_bypass`, `same_mask_dense_replay`, and
`same_mask_route_a_external_storage_replay`. The Route-A outcome may include
only bounded scalar ownership/page/ULP summaries, never adapter K/V, attention,
activation, or full logits tensors. Timing and allocator fields are measured
software observations, not HBM traffic, throughput, energy, area, or hardware
metrics.

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

The completed A2 evidence freeze is `analysis/route_a2_lifecycle_freeze.json`.
It preserves source SHA-256 values for each collector and replay artifact and
records the hard boundary between trace-derived lifecycle accounting and the
modeled byte/cycle quantities required by A3.

### Route-A3 modeled traffic/cycle DSE

`tools/simulate_kvzap_route_a3_traffic.py` consumes a validator-approved A2
lifecycle directory, matching page replay, the A2 freeze, and an A1 scheduler
manifest. It emits `a3_step_results.csv`, `a3_baseline_summary.csv`, and
`a3_manifest.json`. The step file is restricted to observed `phase=decode`
calls. It charges all prior context/prompt admission once before decode step 1
and matching decode admission at every later step.

The four `baseline` values are `full_kv`, `ideal_packed_kvzap`,
`packed_static_head`, and `packed_length_aware_head`. Full KV reads each L/H
cache length. Ideal packed reads the protected hot window plus logical cold
tokens and deliberately assumes zero admission, metadata, and scheduler cost.
The physical baselines read hot plus *allocated* cold slots, add declared page
metadata lookups and A2 admission bytes, and differ only by static affinity or
whole-head LPT cycles. `break_even_decode_step` means cumulative modeled bytes
first become lower than Full KV; it is not a measured event. The A1 manifest is
policy/cost provenance, not evidence that its simulated batches occurred in
the A2 request. All bytes/cycles and any derived latency interpretation remain
explicitly modeled.

`head_dispatch_cycles` and `scheduler_queue_bytes_per_head` are first-class
A3 sweep axes. They appear in both A3 CSV outputs so a selected-scheduler
comparison must use the same page, bandwidth, PE, and overhead point as its
static baseline. Values for Full, ideal, and static rows are intentionally
duplicated over these scheduler-only sensitivity points for a rectangular DSE.
The A3 CLI accepts ordered repeated `--lifecycle-dir` / `--page-replay-dir`
pairs to create one cross-workload suite; each pair must separately validate
against the A2 freeze and is recorded with individual hashes in the manifest.
It also provides the frozen `--workload-suite conservative_three` preset:
`retrieval_qasper`, `reasoning_2wikimqa`, and
`longhorizon_gov_report_row109`. Each CSV row has a `workload` field, so
cross-workload results cannot be accidentally aggregated only by request ID.

Route-A3 schema `kvzap-route-a3-traffic-cycle-dse-1.1` additionally supports
optional policy-sensitivity rows. `--oracle-min-decode-steps` emits
`packed_oracle_*`: an offline whole-request horizon gate that uses Full KV
when the completed observed horizon is below its threshold. It is an oracle
upper bound only and must never be described as an online policy. The
`--deferred-admission-decode-steps` rows (`packed_deferred_*`) read Full KV
for the first N observed decode calls; if call N+1 exists, they charge all
previously deferred declared admission bytes and start physical packed reads.
The `policy_kind`, `policy_threshold_decode_steps`, and
`policy_activation_decode_step` fields make these cases distinct from the four
fixed baselines. Deferred rows are a storage-policy model only: they do not
establish mask-equivalent generation or accuracy.
`--deferred-admission-decode-step-range START STOP` expands every inclusive
integer N in that range and merges it with explicit deferred points before the
resolved, sorted threshold list is written to the manifest. This is the
reproducible interface for boundary scans such as N=0..32; it does not add
oracle rows.

### Route-A3 edge microarchitecture DSE

`tools/simulate_kvzap_route_a3_edge.py` consumes the same validator-approved
A2 lifecycle/replay pairs but also requires a parameterized edge-target JSON,
such as `analysis/qwen3_8b_edge_target_v0.json`. The descriptor fixes model
dimensions, cache bytes, hot window, GQA grouping, and the candidate number of
layer-local attention stream engines. Its engine count is a head-group task
service-resource count, never a physical systolic-array MAC count.

The edge tool emits `a3_edge_step_results.csv`,
`a3_edge_baseline_summary.csv`, and `a3_edge_manifest.json`. For every
declared A2 admission event it rounds declared bytes to a configured memory
burst, combines the transfer cost with a configured pack throughput and
per-page setup cost, and LPT-schedules independent `(model call, layer, KV
head)` admissions on a configured number of shared admission engines. Context
admission is charged before decode step one. These are explicit cycle-model
assumptions, not DRAM/HBM measurements, and the tool does not model overlap or
prove a gate's generation equivalence. The manifest carries interfaces for the
separate policy-on generation validation and cross-model repeat required later.

The `kvzap-route-a3-edge-dse-1.1` manifest additionally records the Cartesian
scan axes `admission_engine_counts` and
`admission_pack_bytes_per_cycle_points`.  The resulting rows retain both
per-point values, so an admission-engine design-space result cannot be confused
with a measurement of an allocator, DRAM/HBM, latency, or throughput.

The same run emits `a3_edge_admission_constraints.csv`. For each active packed
length-aware policy and each workload/page/bandwidth point, it reports the
minimum *declared aggregate pack capacity* (`engine_count × per_engine_pack
bytes/cycle`) among scanned points whose modeled total cycles are non-negative
versus Full KV. Equal-capacity decompositions remain listed. An unactivated
deferred gate is explicitly `not_applicable_full_kv_fallback`; a missing point
is `no_nonnegative_point_in_scan`. Neither field is a calibrated hardware
requirement.

When `--admission-contract-dir` supplies one validated
`kvzap-route-a35-admission-shadow-1.3` directory per ordered workload, A3-edge
also emits `a3_edge_budgeted_admission_contract.csv`. The source must use
`per_layer_batch_v2`, contain a positive `admission_flush_token_budget`, obey
that budget in every task row, and drain its observed pending queue. For budget
`B`, layer count `L`, declared K+V bytes/token `K`, and a Full-KV attention
window of `T` modeled cycles, it records the *declared demand screen*
`B*K/T` (one per-layer engine) and `L*B*K/T` (one shared engine). It compares
the shared demand with the DSE point's declared `engine_count *
per_engine_pack_bytes_per_cycle`, plus the matching deferred packed
length-aware model sign. This is neither a measured service rate nor a proof that admission and
attention overlap; A3's original traffic/cycle ledger remains separate.

### Route-A3.5 admission shadow reference

`tools/run_kvzap_admission_shadow.py` runs normal Full-KV generation plus
silent and recorded read-only shadow passes. The shadow observes the already
updated dense `DynamicCache`, gathers only lifecycle-matured tokens retained by
the same fixed KVzap predictor, and appends them to separately allocated
per-layer/head packed K/V pages. It never supplies attention, changes the model
cache, or applies DMS. It writes lifecycle CSVs plus
`admission_shadow_tasks.csv`, `admission_shadow_final_state.csv`, and an A3.5
manifest. Host submission and CUDA-event times characterize only this reference
implementation; they are not end-to-end latency, allocator, HBM/DRAM, edge
hardware, or throughput measurements. `tools/validate_kvzap_admission_shadow.py`
checks answer/digest guards and lifecycle/task/final-count consistency without
loading a model.

Schema `kvzap-route-a35-admission-shadow-1.1` adds the A3.5b
`--submission-mode per_layer_batch` reference. It emits one timed batch envelope
per `(model_call, layer)` plus untimed constituent head rows. This reduces the
software submission granularity from one row per layer/head to one per layer,
but the implementation still performs each head's gather/page write separately;
it must not be described as a fused attention or gather kernel.

Schema kvzap-route-a35-admission-shadow-1.2 adds paired per_head_v2 and
per_layer_batch_v2 timing. Both record a common planning scope
(planning_host_us), a copy/page-submit scope (submit_host_us), and a CUDA stream
envelope (gpu_envelope_ms). Optional deferred-admission-decode-steps N queues
retained mature positions through the first N decode calls and flushes them at
call N+1 if it is observed. Dense Full KV remains the attention source.

For a repeat of a frozen LongBench A2 request, the runner accepts
expected-a2-lifecycle-dir together with the original input JSONL and request id.
It checks request content hash and frozen model/predictor/page parameters before
loading the model, then checks the normal Full-KV answer hash before recording
any A3.5 output.

Schema kvzap-route-a35-admission-shadow-1.3 adds budgeted oldest-first flush.
admission-flush-token-budget bounds physical packed writes per model-call/layer;
unserved retained positions remain in a FIFO pending queue. The companion
analyze_kvzap_admission_budget tool reports p50/p95/p99/max packed burst,
max pending depth, and whether the queue drained by the observed horizon.

Schema `kvzap-route-a35-admission-shadow-1.4` is opt-in through
`--record-hybrid-head-progress` and requires budgeted `per_layer_batch_v2`.
It additionally writes `admission_shadow_v2_head_progress.csv`: one untimed
row per `(model_call, layer, kv_head)` with decided/packed/pending counts,
actual packed-page state after the call, page allocations, and packed position
sum. The V2 layer-batch task remains the timing envelope; the progress CSV is
not a kernel timing record. The validator checks that every layer batch equals
the sum of its head-progress rows.

`tools/simulate_kvzap_route_a3_hybrid_activation.py` requires this 1.4 profile
because a batch aggregate cannot determine a head's dense-pending versus
packed-page read state. It models Full KV, hybrid dense-pending plus packed
cold KV, and wait-for-queue-drain policies under explicit index, metadata,
merge, bandwidth, and cycle assumptions. The state for decode call `c` is the
FIFO state after calls strictly before `c`; current-call admissions are charged
after its attention proxy. Its bytes/cycles are not HBM/DRAM, allocator,
latency, throughput, or policy-on generation measurements.

Schema `kvzap-route-a36-hybrid-activation-dse-1.1` records one Cartesian
hardware-sensitivity point in every step and summary row: effective pending
gather bytes/token, merge-state bytes/head, merge cycles/head, and per-layer
pending staging capacity. Effective pending gather bytes/token is at least the
declared K+V bytes/token; larger values are an explicit scatter/burst
amplification proxy. With bounded staging, the declared conservative
`layer_full_kv_fallback` reads all heads in any over-capacity layer from Full
KV for that call. These remain analytical sensitivity assumptions, not
calibrated hardware facts.

### Route-A3.7 memory-system and adaptive-gate DSE

`tools/simulate_kvzap_route_a37_memory_system.py` consumes the same validated
A2 lifecycle and schema-1.4 shadow inputs as A3.6, without rerunning the
model.  It replaces the A3.6 effective pending-gather-bytes/token sensitivity
axis with a declared contiguous per-head FIFO layout proxy: bank count, burst
bytes, per-bank bytes/cycle, either token-round-robin or head-affine bank
mapping, and a per-layer pending-staging capacity.  It writes layer, step, and
summary ledgers.  Schema `kvzap-route-a37-memory-system-dse-1.0` records the
bank/burst assumptions in every row and manifest.  Schema-1.4 does not retain
pending token positions, so this is a deterministic layout proxy, not a trace
of actual DRAM addresses, bank conflicts, HBM traffic, allocator behavior, or
latency.

`tools/simulate_kvzap_route_a37_adaptive_gate.py` consumes only a completed
A3.7 layer ledger.  For each `(decode call, layer)`, it compares the modeled
hybrid cost including current-call admission with the modeled Full-KV cost and
selects the lower declared byte or cycle objective, optionally requiring a
guard margin.  A staging overflow remains explicitly labeled Full-KV fallback.
Schema `kvzap-route-a37-adaptive-gate-dse-1.0` is an oracle-like same-call
cost gate: it is not an online predictor, hardware controller, sparse
attention execution, generation-equivalence result, or measured performance.

`tools/simulate_kvzap_route_a38_observable_gate.py` is the follow-on
screen.  It consumes a matching A3.7 memory-system ledger and cycle-objective
oracle-gate manifest, but its decision rule may use only features available
before attention: pending FIFO tokens, deterministic projected maximum bank
bursts, and the staging-overflow flag.  It sweeps declared token/burst
threshold pairs and reports agreement, false-hybrid/false-full counts, and
byte/cycle regret against the A3.7 oracle.  Schema
`kvzap-route-a38-observable-gate-dse-1.0` may optionally emit audit rows for
one threshold pair.  Costs are used only after selection to score the rule.
Threshold selection on the same workload is a heuristic sensitivity screen,
not a calibrated online controller, cross-workload generalization result, or
hardware measurement.

`tools/simulate_kvzap_route_a39_consistent_gate.py` corrects the preliminary
A3.7/A3.8 accounting ambiguity with explicit `continue_admission`: a Full-KV
selection changes only the current attention read path. Recorded
post-attention admission bytes are charged after either Full-KV or hybrid
attention, so the canonical schema-1.4 shadow state remains valid for the
following call. Its oracle and observable gate compare attention-only costs;
the common admission ledger is added afterward. Schema
`kvzap-route-a39-consistent-gate-dse-1.0` must not represent
`defer_admission`: that policy requires branch-dependent FIFO/page evolution,
and schema-1.4 count rows do not retain enough pending-position detail to
replay the original oldest-first order exactly.

`tools/summarize_kvzap_route_a39_cross_workload.py` takes completed A3.9
`continue_admission` directories for at least two named workloads and one
caller-fixed threshold pair. It writes per-workload results plus a common
hardware-point table whose minimum is taken across workloads. It refuses to
select a threshold itself or silently compare incompatible hardware sweeps.
The summary is still a modeled robustness screen, not cross-workload hardware
or controller validation.

Schema `kvzap-route-a35-admission-shadow-1.5` is an opt-in A3.10 collection
profile. With `--record-deferred-replay-positions`, it adds
`admission_shadow_v3_deferred_replay_positions.csv`, one row per retained
mature token decision containing `(model_call, layer, kv_head, position)`.
It is intentionally limited to selected workloads because it can be large.
Together with the validated head-progress counts it preserves the exact input
needed for branch-dependent oldest-first FIFO replay; it remains an
observational Full-KV shadow trace and not sparse-attention execution.

`tools/simulate_kvzap_route_a310_deferred_replay.py` consumes a frozen A2
lifecycle plus that schema-1.5 position stream. For each declared
`(deferred_decode_steps, admission_flush_token_budget)` point, it evolves a
separate append-only per-head cold-page list and FIFO of exact retained
positions. During the initial deferred horizon it records a Full-KV attention
fallback and performs no admission service; afterwards it appends current-call
decisions post-attention and serves a per-layer global oldest-first budget. It
emits a head-progress audit, a `deferred_replay_layer_state.csv` contract for a
later byte/cycle model, and a conservation-checked summary. These are
branch-dependent modeled state inputs, not sparse-attention execution, HBM
traffic, allocator measurement, latency, throughput, or policy-on generation
evidence.

`tools/simulate_kvzap_route_a311_deferred_memory_system.py` consumes the
A3.10 layer/head replay ledgers and applies the declared A3.7 bank, burst,
staging, scheduler, and admission byte/cycle assumptions. During the initial
deferred horizon it uses Full-KV attention and charges no service; after
activation it uses the exact replayed pre-call state. If staging forces a
Full-KV attention read after activation, current-call admission still remains
charged and advances the replayed state. Its outputs compare the resulting
candidate with Full KV at each caller-declared hardware point. They are modeled
byte/cycle estimates, not HBM traffic, allocator measurements, latency,
throughput, sparse-attention execution, or generation evidence.

`tools/summarize_kvzap_route_a312_cross_workload.py` consumes two or more
completed A3.11 directories. It rejects mismatched policy/hardware sweeps and
reports every common point's minimum and mean modeled savings across named
workloads. A point is marked positive only when every supplied workload has a
strictly positive modeled result. It performs no threshold selection or
controller calibration and remains a summary of modeled—not measured—results.

`tools/validate_kvzap_route_a313_short_horizon_guard.py` validates the
trace-known-horizon control for a completed A3.11 directory. For each supplied
guard horizon, it requires `horizon >= observed decode steps`, every decode
call to remain an initial Full-KV fallback, no staging fallback, and cumulative
candidate bytes/cycles exactly equal to Full KV. This deliberately establishes
a no-gain/no-loss safety control only; it is not an online output-length
predictor or a hardware measurement.

`tools/simulate_kvzap_route_a314_request_cap_gate.py` composes aligned A3.11
results using only the caller-visible `max_new_tokens` from each A2 lifecycle
manifest. Below a declared cap threshold it selects Full-KV/zero-admission;
otherwise it uses one fixed A3.11 deferred policy. It reports per-workload and
common nonnegative/positive modeled cycle regions. Since `max_new_tokens` is
an upper bound rather than a future-length guarantee, this is an observable
contract screen, not a general output-horizon predictor.

`tools/analyze_kvzap_route_a315_cap_mismatch.py` compares two separately
validated A2 lifecycle collections of the exact same request. The high-cap
collection must use a strictly larger caller `max_new_tokens`; all frozen
model, predictor, request-content, cache/page, threshold/window, and seed
fields must match. Schema `kvzap-route-a315-cap-mismatch-1.0` reports the two
caps, observed decode model-call counts, unused high-cap budget, and whether
the answer hashes match. A confirmation requires both a natural high-cap
early stop and the same answer hash. It is evidence that an upper-bound-only
request-cap gate is insufficient for that request; it is not a hardware
measurement or a general future-length predictor result.

`tools/freeze_kvzap_route_a315_lifecycle.py` validates one newly collected A2
lifecycle and writes a separate, hash-addressed
`kvzap-route-a2-lifecycle-freeze-1.0` file for A3.10/A3.11. It never edits the
existing A2 freeze. The new freeze contains only the three lifecycle artifacts
and the source collection configuration; it freezes provenance, not a new
hardware or accuracy claim.

`tools/simulate_kvzap_route_a316_continuation_contract_gate.py` composes
aligned A3.11 results using only an externally supplied lower bound on future
decode calls. Below a declared contract threshold it selects Full-KV with zero
admission; otherwise it selects one fixed A3.11 policy. Its separate audit
compares the declaration with observed trace length only after selection. Schema
`kvzap-route-a316-continuation-contract-gate-1.0` therefore distinguishes a
held contract from a contract breach; it does not infer a future horizon from
the trace, implement an online controller, or measure hardware behavior.

`tools/simulate_kvzap_route_a317_contract_policy_sweep.py` extends A3.16 over
an explicit Cartesian set of deferred-admission horizons and flush budgets.
It requires every supplied A3.11 input to contain each selected policy and the
same hardware points. Its cross summary separately records all-workload
nonnegative cycles and whether every *active* workload has strictly positive
modeled cycles; Full-KV-protected requests correctly contribute zero rather
than making a selective-policy point appear strictly positive.

`tools/summarize_kvzap_route_a318_contract_breach.py` compares two aligned
A3.17 outputs: an honest contract assignment and an explicit breach
counterfactual. It rejects changed source workload provenance and requires the
named workload's contract audit to change from held to violated. It reports
the modeled byte/cycle delta caused by the false declaration; observed horizon
remains audit-only and no result is a hardware measurement.

`tools/analyze_kvzap_route_a319_prefix_contract.py` derives an
observed-prefix continuation requirement from aligned A3.11 step ledgers. A
lower-bound contract of N permits an endpoint at any observed decode prefix at
or after N, so the tool selects the earliest N whose entire observed suffix of
cumulative modeled cycle savings is non-negative. It does not extrapolate past
the recorded trace or turn that trace-derived threshold into a general length
predictor or hardware measurement.

### Route-A3.20 no-contract speculative defer curve

`tools/analyze_kvzap_route_a320_speculative_defer_curve.py` consumes one or
more A3.11 directories that contain the same dense set of deferred-admission
points for one selected budget. Schema
`kvzap-route-a320-speculative-defer-curve-1.0` emits final-horizon rows and
per-`(defer, observed decode prefix)` cumulative byte/cycle rows. It verifies
the hardware grid and prefix-to-summary conservation, and records an exact
Full-KV zero-saving reference for unactivated policies. The observed horizon
is post-hoc analysis only: this is a no-contract, semantics-safe but
performance-speculative policy screen, not an online horizon predictor,
sparse-attention execution, or hardware measurement.

### Route-A4.0 policy-on packed-attention functional reference

`kvpress/route_a_attention.py` defines the no-model schema
`kvzap-route-a40-packed-attention-reference-1.0`. The Route-A fast path owns
one state instance per layer and keeps, for each KV head, a regular hot deque,
an oldest-position pending FIFO, and append-only packed cold pages. K/V input
is `[KV-head, token, head-dim]`; the caller supplies the already-decided
original boolean KVzap keep mask `[KV-head, token]` and contiguous positions.
At maturity, every position is partitioned by that mask into drop or pending;
global oldest-first service moves at most the declared budget into pages. A
token in the protected hot window is never pending or packed.

The reference attention path reads exactly `hot + pending + packed` records
and merges their independently stabilized partial softmax states. Its only
numerical comparison is against a dense attention concatenation over those
same retained records. `full_kv_bypass` is an explicit control path requiring
the caller's Full-KV records and performs no Route-A state construction or
admission; `route_a_fast_path` reads the three Route-A stores and has no dense
cold fallback. This schema is a unit-level functional guard only: it does not
yet define a transformer cache hook, generation result, timing, allocator,
HBM/DRAM counter, latency, throughput, energy, area, or RTL interface.

`tools/run_kvzap_route_a40_integration_gate.py` defines the separate,
non-overwriting `kvzap-route-a40-real-qwen-integration-gate-1.0` manifest. It
uses an attention post-hook on one declared Qwen3 layer and KV head, reads
post-RoPE cache K/V and the original score mask, and compares the Route-A
three-store output against dense concatenation over the exact same records for
every observed `q_len=1` decode query. A normal dense Full-KV run and this
read-only hook run must have identical answer hashes. It must record zero use
of DMS, fake keys, masked indices, cache mutation, or attention replacement.
It is an A4.0 integration prerequisite, not policy-on generation or A4.1
measurement; its reported differences are numerical-equivalence diagnostics,
not timing or memory measurements.

`tools/run_kvzap_route_a40_policy_gate.py` emits the new-directory-only
`kvzap-route-a40-policy-on-qwen-gate-1.0` manifest. Its `full_kv_bypass` pass
installs no backend and performs zero Route-A admission. Its selected
`route_a_fast_path` installs `RouteAPolicyAttentionBackend`: during a
single-layer/single-KV-head Qwen `q_len=1` decode call, the selected GQA query
group bypasses the original attention function and reads only hot, pending,
and packed cold K/V. The backend numerically guards that result against dense
attention over the exact same retained records. Other query groups remain
explicit dense attention in this minimum generation gate. An optional
`require_pending_nonempty` guard requires actual pending-staging reads. A
Full-KV/fast-path answer change is permitted; this is neither a Full-KV answer
equivalence nor an A4.1 timing/allocator/HBM result.

The same schema accepts `target_kv_head: "all"`. In this mode each KV-head
GQA group of the declared layer bypasses original attention on `q_len=1`, and
the manifest emits one numerical comparison row per `(policy decode call, KV
head)` plus `policy_coverage`. The standard all-head gate requires every
selected head to be compared and at least one pending-staging read. A selected
head with no retained mature cold token under the original mask legitimately
has no pending entry; the optional strict all-head-pending assertion may be
used only when that stronger coverage is desired. Other layers remain dense;
this is a layer-complete A4.0 semantic gate, not a full-model policy-on or
A4.1 measurement result.

For policy-on gates, the backend first compares online-merge and concatenated
same-mask results in FP32 under the declared `rtol`/`atol`; this is the
mandatory semantic guard. It then casts both to the model execution dtype and
records `max_abs_difference_fp32`, `max_abs_difference`,
`max_executed_dtype_ulps`, and `executed_dtype_ulp_limit` in each comparison
row. The post-cast ULP limit is an explicit diagnostic control (default 16,
configured as `max_executed_dtype_ulps` in the manifest), not a replacement
for the FP32 guard. It accounts for small low-precision differences that can
accumulate when a policy-on output feeds later substituted layers, while still
failing any FP32 mismatch or post-cast difference above the declared limit.

Schema `kvzap-route-a40-policy-on-qwen-gate-1.1` generalizes the gate from one
layer to an explicit `resolved_target_layers` set. Every selected layer has an
independent `RouteAPolicyAttentionBackend` state and every state consumes its
own original KVzap score stream; the set shares one frozen predictor instance
only. The manifest replaces the scalar policy-call field with
`policy_decode_call_count_by_layer`, adds `layer` to every comparison row, and
nests each layer's selected-head coverage in `policy_coverage.layers`. The
`target_layers: ["all"]` option denotes all model layers. This remains a
functional reference whose Python execution time is excluded from A4.1.

Schema `kvzap-route-a40-policy-on-qwen-gate-1.2` adds the declared
`max_executed_dtype_ulps` configuration field and the two guard values in
`observational_guards`. A successful run proves only that all per-head FP32
same-mask comparisons passed and each recorded post-cast difference was within
that declared diagnostic limit; it is not a timing or end-to-end answer
equivalence claim.

Schema `kvzap-route-a40-policy-on-qwen-gate-1.3` optionally adds an independent
online `same_mask_dense_kvzap` pass. It owns `DenseSameMaskAttentionState` per
selected layer: hot tokens remain regular, mature retained tokens append to a
dense cold list, and it has no pending FIFO, admission service, or packed
page. Both the dense control and Route-A score their masks online and emit a
per-layer `original_mask_sha256` plus `original_mask_decision_count`. The gate
fails unless those summaries match exactly. This establishes a paired logical
same-mask dense KVzap baseline for the declared request; it is not a Full-KV
equivalence, allocator, or performance measurement.

If those independent online passes drift, the requested fresh output directory
instead receives `kvzap-route-a40-online-mask-drift-diagnostic-1.0` with
`status: "failed"`. It stores bounded examples and per-layer counts for only
`(layer, kv_head, cache_position, score, keep)` events, plus answer digests and
mask summaries. It must never be interpreted as a successful same-mask
baseline or as an A4.1 measurement.

Schema `kvzap-route-a40-policy-on-qwen-gate-1.4` adds the explicit
`replay_dense_mask_for_route_a` control. In this three-pass paired control,
Pass 2 is the only online predictor source; Pass 3 consumes Pass-2
`(layer, kv_head, position) -> (score, keep)` events exactly once and does not
invoke its own predictor. The manifest records `pairing_mode:
"replayed_dense_mask"`, `route_a_mask_source: "replayed_dense_mask"`, and
`replay_mask_consumption_complete: true`. This proves an exact replayed-mask
storage/attention pairing only, not online mask stability or independent
Route-A predictor behavior.

The accepted instance
`analysis/experiments/route_a40_policy_on_qwen_all_layers_replayed_mask_01/`
is an A4.0 example of schema 1.4, not a new measurement schema: it has exact
per-layer mask digest/count equality and complete replay consumption for the
named request. Its 2,016 Route-A comparison rows, pending/page coverage, and
numerical fields remain functional diagnostics. They are not A4.1 runtime,
allocator, profiler, HBM, throughput, energy, or hardware measurements.

`kvzap-route-a41-harness-1.0` is the A4.1.0 no-model harness schema. Its
separate `a41_harness_started.json` and `a41_harness_manifest.json` records
make status explicit. A CUDA self-check, if run, writes
`kvzap-route-a41-raw-repetition-1.0` JSONL rows with synchronized host/CUDA
event milliseconds and before/after PyTorch allocator byte snapshots. A
`dry_run` writes no timing rows and proves only output/schema construction.
Neither record is a Qwen, KVzap, Route-A, allocator-under-model, HBM, or
performance result.

`kvzap-route-a41-replay-mask-source-1.0` is the separate, untimed source
artifact required before an A4.1 paired component run.  Its compressed NPZ
stores only `(layer, kv_head, cache_position, score, keep)` events from one
online dense-KVzap collection.  The manifest binds the NPZ SHA-256, event
count, request-content hash, frozen model/predictor revisions, threshold,
128-token window, page size, decoding configuration, and source answer digest.
It contains no K/V tensor or token text.  This source establishes the exact
mask stream to replay; it is neither a timing sample nor evidence that an
independent Route-A online predictor would make identical decisions.

`kvzap-route-a411-component-gate-1.0` is the one-layer/one-KV-head A4.1.1
component-measurement manifest.  Its raw JSONL uses
`kvzap-route-a41-raw-repetition-1.0` rows grouped by declared path and
component.  The paired paths are exactly `same_mask_dense_replay` and
`same_mask_route_a_replay`; the latter records named maturity/pending,
admission/page-table, hot, pending, packed, and merge regions.  The dense
path records dense maturity/cold append and same-mask dense attention.  An
optional `online_dense_predictor_control` records predictor score and threshold
formation separately and is explicitly unpaired.  Every component timer
synchronizes the device and resets allocator peaks, so these records support
micro-component attribution only and must not be aggregated as end-to-end
decode latency.  Allocator fields remain PyTorch allocator observations, not
HBM traffic, throughput, energy, area, or hardware evidence.

The accepted `route_a411_component_layer0_head0_budget1_02` instance uses the
matching `route_a41_replay_source_layer0_budget1_01` NPZ and has complete
replay consumption.  It is specifically a deliberately backlogged
`admission_budget=1` coverage point: selected layer 0/KV head 0 observed both
pending staging and a packed record.  Its component timing rows remain scoped
to the named Python reference callbacks and cannot be generalized to a
candidate admission point, full model, Full-KV comparison, or end-to-end
decode measurement.

The follow-on `route_a411_component_layer0_head0_budget1_03` and
`route_a411_component_layer0_head0_budget512_01` artifacts use that identical
source.  They make the pending coverage condition explicit: budget one has
nonempty pending staging, while budget 512 legally has none and retains its
head-0 cold entries in packed storage.  In schema 1.0, a component group's
`reported_repetitions` is its callback invocation count; its raw rows retain
`execution_order`, which identifies the 10 independent reset runs.  Do not
interpret callback rows as independent request repetitions.  A later summary
revision must report both callback and per-reset-run aggregate distributions.

Schema `kvzap-route-a41-summary-1.1` retains a named `callback_groups` view
and adds `reset_run_aggregate_groups`. The latter groups reported raw rows by
`(path, component, execution_order)`, sums synchronized callback wall/CUDA
durations within that reset run, counts callbacks per run, and uses the
run-local maximum for each allocator peak. It reports distributions over the
independent reset runs. These aggregate sums remain component attribution, not
end-to-end decode latency; allocator maxima remain PyTorch allocator
observations, not HBM traffic.

The component gate now records `packed_page_count`, `packed_full_page_count`,
and `packed_tail_tokens` in every Route-A comparison state. Coverage summaries
expose their maxima plus `ever_multi_page_packed` and
`ever_sealed_packed_page`. The explicit
`require_multi_page_packed` guard passes only when a selected head has at
least two packed pages and at least one full sealed page. It is a real-state
coverage guard for an append-only reference, not an allocator/page-fault/HBM
measurement.

The accepted head-6 `budget=512` multi-page artifact records four packed
pages and three full pages under the explicit guard; its independent
budget-one companion records nonempty pending staging. These are maxima over
the named decode comparisons, so a tail-token watermark and a page-count
watermark must not be combined as if they came from one instant. They close
A4.1.1 reference-state coverage only. A4.1.2 must use a distinct whole-decode
timing schema with exactly one timing region per reset run and no component
callback synchronization.

`kvzap-route-a412-whole-decode-gate-1.0` is the A4.1.2 replayed-mask
whole-decode schema. Each `kvzap-route-a412-whole-decode-raw-repetition-1.0`
row has exactly one `question_forward_plus_greedy_decode` timing region after
an untimed context prefill into a fresh cache. It records CUDA-event and host
time, PyTorch allocator snapshots, generated-token count, and digests of the
answer and generated token IDs. `full_kv_bypass` installs no Route-A backend;
`same_mask_dense_replay` and `same_mask_route_a_replay` consume the exact same
hashed replay source. The generic summary exposes one callback and one
reset-run aggregate per raw row. Context prefill is deliberately excluded, so
this is a decode-stage software observation, not full-request latency,
throughput, HBM traffic, energy, or hardware evidence.

The accepted `{0,18,35}` instance uses 39 raw rows: three paths with three
warm-ups and ten reported reset runs each. Its same-mask dense and Route-A
paths retain the model's native dense DynamicCache while adding reference
state, so allocator peak equality between those paths is not a physical-cache
comparison. The observed decode-region runtime is therefore a valid measured
Python-reference result but cannot establish Route-A speedup, HBM traffic, or
physical-memory savings. A separate profiler record must state its tool,
version, command, activities, and scope; it must not be pooled with timing
repetitions.

`kvzap-route-a412-profiler-diagnostic-1.1` is that separate A4.1.2.1 record.
It runs one fresh-cache, unprofiled warm-up per named path followed by exactly
one `torch.profiler` capture of `question_forward_plus_greedy_decode`, after
an untimed context prefill. It emits one Chrome trace and a normalized
top-operator table for each of `full_kv_bypass`, `same_mask_dense_replay`, and
`same_mask_route_a_replay`, along with answer/token-ID digests, replay guards,
and PyTorch allocator snapshots. Profiler execution changes the runtime, so
its operator totals are attribution diagnostics only: they must not be pooled
with A4.1.2 timing samples or presented as latency, throughput, HBM traffic,
energy, physical-memory, or hardware evidence.

Schema 1.1 uses `device_time_total_us` and `device_memory_usage_bytes` for
the normalized operator table, falling back to legacy `cuda_*` attributes only
when necessary. In this CUDA-only gate, device time denotes profiler-reported
CUDA device time. The old 1.0 table used legacy `cuda_time_*` attributes that
are empty under the accepted PyTorch 2.10 build; its raw Chrome traces remain
valid, but its zero-valued summary GPU-time columns are not usable for GPU
operator ranking.

`kvzap-route-a4122-cache-ownership-gate-1.0` is an untimed, single
`(layer, kv_head)` integration schema. It records the three policy paths and
records (but does not require) same-mask dense versus Route-A owned-cold
answer/token-ID relation. In
the owned-cold path, after original K/V is appended to Route-A hot/pending/
packed state, every mature selected-head K/V cell in the native DynamicCache
view is NaN-poisoned. Each later call verifies the old mature range remains
poisoned before selected Route-A attention executes. The manifest records
coverage and `native_cold_ownership`, including logical dense slot extent and
guard counts. `native_cold_slots_physically_freed` is required to be false:
poisoning is a no-silent-dense-read guard, not allocator, physical-memory, HBM,
or performance evidence.

Schema 1.1 fixes an over-strong 1.0 terminal assertion: the per-head FP32
same-mask numerical guard and finite selected Route-A decode output remain
required, while the first generated token-ID difference is stored as a bounded
diagnostic. Different legal reduction orders can change a later greedy token;
that drift alone neither proves a native-dense cold read nor invalidates the
ownership guard.

`kvzap-route-a4123-first-decode-logits-diagnostic-1.0` is an untimed replay
prefix diagnostic: it runs context prefill and exactly one multi-token question
forward, records only bounded final-position logits metadata (finite/NaN/Inf
counts, argmax, top-k, margin), and does not run greedy decode. It records the
question token count, policy-decode call count, and prefix replay consumption.
It must not assert full replay consumption. A nonfinite owned-cold route logit
with zero q_len=1 policy calls identifies that a multi-token native attention
fallback consumed NaN-poisoned selected cold K/V; it is a semantic integration
finding, not a timing or memory result.

`kvzap-route-a4124-multitoken-bridge-gate-1.0` repairs that scope for one
selected head: it appends each question token causally to Route-A state,
replaces selected-head outputs token by token, and gives native attention zero
placeholders for selected heads while it computes unselected heads. It requires
finite paired logits and equal first argmax, but remains an untimed replay
prefix and does not claim physical cache-slot removal.

`kvzap-route-a4124-multitoken-bridge-gate-1.1` additionally requires the
independent same-mask dense control to use the same causal multi-token bridge.
Version 1.0 delegated its q_len>1 selected heads to native Full-KV attention,
so a final-logit delta against Route-A conflated KVzap masking with numerical
reduction error. Version 1.1 records bounded per-question-token selected-head
attention summaries (`max_attn_output_abs_difference`, FP32 counterpart, and
executed-dtype ULP count) for both control and Route-A. It stores no full
attention, K/V, or hidden-state tensors. A final-logit comparison in this
schema is therefore a same-mask comparison; it still has no universal
elementwise-equality requirement because the packed online merge and dense
reference use legal different reduction orders.

The first schema-1.1 artifact,
`route_a4124_multitoken_bridge_layer0_head6_budget1_densebridge_01`, is a
narrow successful instance: the paired final logits were equal and Route-A's
largest selected-head discrepancy was one execution-dtype ULP. Its separate
Full-KV-to-same-mask-dense delta was `0.55078125`; that number is recorded as
mask-semantic behavior for this one prefix, not as a Route-A numerical error,
performance result, or quality result.

`kvzap-route-a4124-multitoken-bridge-gate-1.2` adds optional observed-state
guards for a selected-head Route-A bridge: `require_multi_page_packed`,
`require_full_packed_page`, and `require_tail_packed_page`. A requested guard
must be true for every selected head in the recorded coverage; a large
admission budget alone is not evidence. These guards complement, rather than
replace, the budget-one pending-staging artifact. They remain untimed prefix
semantics and do not establish allocator page allocation, HBM traffic, or
physical memory.

The first requested schema-1.2 multipage artifact,
`route_a4125_multitoken_bridge_layer0_head6_budget512_multipage_01`, observed
three packed pages for head 6 (two full and one 63-token tail) and passed all
requested guards with equal paired final logits. Its zero pending count is an
expected admission-policy state at budget 512, not missing coverage; pending
was established separately by the budget-one artifact. This remains a
single-head prefix semantic observation only.

`kvzap-route-a4124-multitoken-bridge-gate-1.3` permits
`target_kv_head=all` for simultaneous ownership substitution of every KV head
in one layer. It requires the dense control and Route-A coverage rows to name
exactly the resolved selected KV-head set and to contain one comparison per
question token for each head. Aggregate guards (`require_any_pending`,
`require_any_multi_page_packed`, `require_any_full_packed_page`, and
`require_any_tail_packed_page`) require at least one selected head to exercise
the named state. This is intentionally different from the existing
every-selected-head page flags: low-retention heads may correctly have no cold
page. All-head native K/V poisoning remains an observation guard, not physical
cache deallocation or a performance measurement.

The first all-head schema-1.3 artifacts passed ownership and per-attention
guards but reported a `0.44921875` paired final-logit delta, despite at most one
execution-dtype ULP at each selected attention output and an unchanged first
argmax. This is a diagnostic hold, not a failure proof or a multi-layer pass.
Moreover, schema 1.3 records an unrequested guard as true through the formula
`not requested or satisfied`; consumers must inspect its config request flags
and coverage rows. A later schema must record request and satisfaction as
separate fields; completed artifact contents remain immutable.

`kvzap-route-a4127-allhead-activation-diagnostic-1.0` is the follow-on
untimed locator for that all-head final-logit drift. It requires
`target_kv_head=all`, captures every decoder layer only during the question
forward, and serializes bounded scalar dense/Route-A activation relations per
layer and question-token offset. Each relation records shape, finite state,
max/mean absolute difference, relative L2 difference, and one maximum-location
descriptor; captured tensors are transient and must not be written. Its
`guard_requirements` records `requested` separately from `satisfied` (or null
when unrequested), replacing schema 1.3's vacuous-true encoding. Hooked output
is a semantic diagnostic, never a timing, allocator, HBM, physical-memory, or
hardware measurement.

The first A4127 budget-one artifact found its first nonzero activation relation
at selected layer 0 and a later-layer growth pattern, with all captured values
finite. That is a narrow localization result consistent with numerical
propagation after all-head replacement. It does not establish that the behavior
is independent of packed page state until the matching budget-512 artifact is
reviewed.

The matching A4127 budget-512 artifact exercised the requested multi-page,
full-page, and tail-page state and produced the same first-difference layer and
same 36-layer scalar relation table as budget one. For this replay prefix, that
controls the admission-layout variable: the recorded drift is downstream
numerical propagation rather than a pending-versus-packed storage effect.

`kvzap-route-a4128-allhead-continuation-diagnostic-1.0` is the next untimed
output-impact locator. It runs one all-head same-mask dense greedy reference,
then (1) a Route-A continuation forced with exactly those dense token IDs and
(2) an independent Route-A greedy continuation. The forced path records
bounded paired-logit summaries at every fixed token offset, while the
independent path records its first generated-token mismatch, if any. An
independent row after that mismatch no longer has the same generated input
prefix and therefore must not be read as a same-input numerical comparison.
The runner uses a fixed declared token count and requires complete replay
consumption for all three paths. It stores token IDs/digests and bounded top-k
metadata only, never a full logits tensor. This is an untimed same-mask
semantic diagnostic; it is not a quality, Full-KV-equivalence, allocator,
physical-memory, HBM, throughput, energy, area, hardware, or RTL result.
Requested pending/page-state guards apply only to the Route-A paths: the dense
same-mask control intentionally has no Route-A pending FIFO or packed-page
state and is not required to exercise either.

The first A4128 artifact,
`route_a4128_allheads_layer0_budget1_pending_continuation_02`, completed its
pending requirement and exhausted the shared 7,472-event replay source in all
three paths. Across its declared eight generated tokens, forced Route-A had
equal paired argmax at every offset and independent Route-A emitted the same
eight token IDs as dense. The largest per-offset logit maximum was `0.640625`,
whereas the smallest recorded dense top-1/top-2 margin was `21.5`. This is a
bounded greedy-decision observation for this layer-0, all-head, pending-state
request only; it does not quantify answer quality or establish behavior for
longer continuations, other layers, or page states.

The matching page-state artifact,
`route_a4128_allheads_layer0_budget512_multipage_continuation_01`, completed
the requested multi-page, full-page, and tail-page guards. Head 6 reached four
packed pages, three full pages, and a 63-token tail, with zero pending tokens.
It also exhausted the same replay source, had equal forced argmax at all eight
offsets, and had no independent greedy token mismatch. Its bounded per-step
logit relation table is exactly equal to the budget-one table; only the
per-attention FP32 maximum changed insignificantly (`5.2154e-08` to
`4.4703e-08`), while both remain one execution-dtype ULP. Thus, for this fixed
single-layer request and horizon, no greedy-token consequence is observed from
either pending or packed page layout. This does not establish multi-layer,
longer-continuation, quality, or performance behavior.

`kvzap-route-a4129-multilayer-continuation-diagnostic-1.0` is the next
untimed semantic expansion. Its initial scope is exactly layers `{0,18,35}`
with every KV head selected in each layer. It consumes a distinct immutable
multi-layer A4.1 replay source: each source event remains addressed by its
original `(layer, KV head, cache position)`. Its three paths are same-mask dense
greedy, Route-A forced with the dense IDs, and independent Route-A greedy.
Every selected layer must have complete replay consumption, all selected heads
must bridge each question token, and each Route-A layer must independently pass
native-cold ownership poisoning/read guards. State requirements are aggregate
across selected layer/head states, but coverage is serialized per layer and
head. The gate is strictly fixed-horizon and untimed; it is neither a quality,
Full-KV, allocator/HBM, throughput, nor hardware result.

`kvzap-route-a4130-alllayer-continuation-diagnostic-1.0` is the all-36-layer
counterpart. Its CLI accepts only `--target-layers all` (or its default all
scope) and rejects any partial layer selection. It reuses the same three-path
continuation contract as A4129, but requires an immutable replay source whose
resolved layer set is exactly every loaded decoder layer. In the frozen Qwen3-8B
scope and the current 8-token request, a complete source is expected to contain
36 independent layer streams; it must not be replaced with a three-layer
source. It remains an untimed semantic diagnostic, not a timing, memory,
quality, or hardware measurement.

If a Route-A execution-dtype ULP guard fails, the multi-layer runners write
`kvzap-route-a-executed-dtype-guard-failure-1.0` to the fresh output directory
before re-raising. It stores only the stage plus scalar layer/KV-head/query-head
/cache-position context, execution dtype, worst-component index, FP32 and
executed-dtype differences, ULP size, and configured limit. The FP32 same-mask
guard has already passed at that point. This diagnostic is for locating a
numerical tolerance breach; it neither loosens the guard nor serializes K/V,
attention, activation, or full-logits tensors.

The first A4130 budget-one attempt stopped in its forced common-token pass at
layer 8, KV head 3, query head 15, cache position 916, output component 20.
It recorded BF16 values `-1.6531e-08` and `-1.3504e-08`: their absolute cast
difference was `3.0268e-09`, but local BF16 ULP spacing was `1.1642e-10`, or
26 ULP. The vector's maximum paired FP32 difference was only `1.7136e-07`,
which passed the declared FP32 `rtol=1e-4` / `atol=1e-5` guard. This localizes
the stop to a near-zero execution-dtype ULP amplification during the question
bridge, not to a replay/mask or ownership-read failure. The gate did not finish,
so it establishes neither all-36 output equivalence nor a relaxed acceptance
policy; budget 512 remains blocked pending a bounded all-layer ULP-distribution
diagnostic.

`kvzap-route-a4131-alllayer-ulp-distribution-diagnostic-1.0` is that bounded
diagnostic. It accepts only the literal `--target-layers all`, reuses the
immutable all-layer replay source, and retains the hard FP32 same-mask
`rtol`/`atol` guard, replay-consumption checks, causal bridge checks, and
native-cold ownership checks. Its fixed `record_only` execution-dtype mode does
not turn a ULP breach into a pass: for every selected layer it records only the
breach count, maximum finite/infinite ULP status, maximum scalar FP32/cast
difference, and at most `--ulp-breach-sample-limit` scalar examples. It never
serializes K/V, attention, activation, or full-logit tensors. An A4131
manifest is diagnostic evidence of the distribution and not an all-36 semantic
acceptance, quality, memory, timing, or hardware result.

`kvzap-route-a4132-alllayer-scale-aware-continuation-gate-1.0` is the strict
follow-up. It fixes `--execution-dtype-ulp-mode record_only` so ULP remains a
reported locality diagnostic, but fixes
`--execution-dtype-close-mode scale_aware_enforce`.
For every selected output vector actually cast and injected into Qwen, it hard
executes `torch.testing.assert_close(route_cast, dense_cast, rtol, atol)` after
the existing FP32 same-mask guard. A failure writes the existing scalar-only
`kvzap-route-a-executed-dtype-guard-failure-1.0` artifact with
`guard_kind: scale_aware_executed_dtype_close`, tolerance ratio, allowed and
observed cast differences, plus location; it does not serialize tensors. A
completed A4132 run establishes only this fixed-source/fixed-horizon all-layer
scale-aware execution-dtype guard, not quality or a timing/memory/hardware
result.

The first A4132 run stopped at layer 1, KV head 7, query head 31, cache
position 915, component 77. Route-A and dense were adjacent BF16 values
(`0.0093994140625` and `0.00933837890625`), one local ULP apart
(`6.103515625e-05`), while their FP32 vector maximum was only
`1.1175870895385742e-07`. The direct post-cast FP32 tolerance was
`1.0907649993896484e-05` (ratio `5.59375`), so this is a rounding-boundary
counterexample to direct FP32-tolerance reuse, not a mask/replay/ownership
failure.

`kvzap-route-a4133-alllayer-quantization-aware-continuation-gate-1.0` keeps
the FP32 guard and ULP recording but hard-enforces, per component:
`atol + rtol * abs(dense_fp32) + local_ulp(route_cast) + local_ulp(dense_cast)`.
The two local spacings conservatively bound independently rounded execution
dtype values. Its scalar-only failure record includes observed/allowed error,
FP32 allowance, both local ULPs, and worst ratio. A pass is only a fixed-source
/fixed-horizon numerical gate, not quality, timing, allocator, HBM, or hardware
evidence.

The completed A4133 budget-one artifact
`route_a4133_all_layers_budget1_quantization_aware_continuation_01` matched the
immutable 268,992-event source hash. All 36 layers and 288 KV heads consumed
their 7,472-event streams, bridged 176 selected-head comparisons per layer, and
passed FP32 plus quantization-aware hard guards and native-cold ownership. The
forced and independent eight-token sequences matched same-mask dense. The
recorded seven >16-ULP events remain observations under this hard envelope.

`kvzap-route-a4134-alllayer-quantization-aware-page-state-gate-1.0` is the
fresh budget-512 counterpart. It fixes all layers, all heads, admission budget
512, ULP `record_only`, and quantization-aware hard casting. Before model
loading it requires three aggregate Route-A state flags: multi-page packed,
sealed full packed page, and nonempty tail page. It deliberately does not
require pending staging, which can legitimately drain at this admission budget.
It remains an untimed same-mask semantic gate.

`kvzap-route-a4135-storage-ownership-contract-gate-1.0` is an A4.1.3.0
no-model prerequisite for a future true cache adapter. For each selected KV
head it verifies that native logical cache length equals Route-A
`next_position`, native storage retains precisely the hot interval, and every
mature position is partitioned into Route-A pending/packed retained storage or
an intentional original-mask drop. It records releasable mature-cold logical
token counts only. `native_selected_cold_slots_physically_freed` remains false:
the contract neither mutates `DynamicCache` nor measures allocator/HBM/timing.
Its local `route_a4135_storage_contract_local_01` gate passed pending budget-1
and packed budget-512 synthetic cases, including multi-page/full-page/tail.

`kvzap-route-a4136-external-cold-storage-adapter-gate-1.0` is the A4.1.3.1
no-model follow-up. It keeps a bounded physical K/V tensor only for explicitly
selected KV-head hot tokens, stores logical cache length separately, and uses
Route-A pending/packed state as the sole selected mature-retained source. It
also proves that truncating stock `transformers.DynamicCache` changes that
cache's reported logical length, so the adapter must not masquerade as a
drop-in DynamicCache. The gate checks pending budget-1 and multi-page/full-
page/tail budget-512 cases plus same-mask attention equality. It is not model-
attached; `transformers_dynamic_cache_substitution` and
`native_selected_cold_slots_physically_freed` remain false. It provides no
allocator, HBM, runtime, throughput, energy, hardware, or RTL result.

`kvzap-route-a4137-qwen-external-cold-storage-gate-1.0` is A4.1.3.2, the
first model-attached Qwen gate for that adapter. It is limited to one replayed
layer/KV head. Qwen supplies normal logical cache positions, while the hook
appends newly created K/V into the external adapter and selected attention
reads mature retained K/V only through its hot/pending/packed state. Native
selected cold K/V remains NaN-poisoned to detect a fallback. The artifact
records complete replay consumption, selected coverage, adapter logical versus
physical-hot counts, and the recorded same-mask dense generation relation.
Ordinary multi-token prefill remains one Route-A admission epoch: it appends as
one chunk and services the global admission budget once. Only the causal
multi-token bridge appends token-by-token; doing that for prefill would
incorrectly over-drain pending staging and change policy semantics.
`transformers_dynamic_cache_substitution` and
`native_dense_cold_slots_physically_freed` must be false: this is a semantic
integration gate, not a physical storage, allocator, HBM, timing, throughput,
energy, hardware, or RTL measurement.

`kvzap-route-a4138-qwen-native-storage-replacement-gate-1.0` is A4.1.3.3, the
single-layer/head Qwen cache-interface prototype. At layer zero it persistently
stores dense K/V only for unselected heads; selected mature cold K/V is absent
from that cache and retained selected cold reads remain in Route-A external
pending/packed state. Qwen's current attention API still receives a transient
full-shaped K/V view: historical selected cells are unreadable and only newly
created selected K/V is present for the current Route-A append. The manifest
must separately report persistent cache storage and mark that transient view
as non-persistent. This is functional evidence only; it does not measure
allocated/reserved memory, HBM, timing, throughput, energy, hardware, or RTL.

`kvzap-route-a4139-qwen-native-storage-page-state-gate-1.0` is A4.1.3.4, the
budget-512 counterpart of A4138. It requires a separately collected layer-0
replay source with matching budget provenance, then requires the selected head
to exhibit a sealed full packed page, a second packed page, and a nonempty tail
page while the cache's persistent selected mature-cold tensor count remains
zero. Pending staging is intentionally not required at this admission budget.
It remains an untimed semantic representation gate; transient view allocation,
allocator/HBM traffic, runtime, throughput, energy, hardware, and RTL are all
out of scope.

`kvzap-route-a4140-qwen-allhead-native-storage-gate-1.0` is A4.1.3.5, the
layer-0 all-KV-head budget-one counterpart. It selects every layer-zero KV
head, requires all their Qwen GQA groups to be substituted, and records each
head even when its original mask yields zero retained mature cold tokens. The
persistent target cache has zero unselected heads and zero selected mature-cold
tensor tokens; Route-A external hot/pending/packed state is the only selected
K/V owner. It may require pending coverage in at least one retained head, not
every head. As with A4138/A4139, transient full-shaped views are non-persistent
and this is not allocator, HBM, timing, throughput, energy, hardware, or RTL
evidence.

`kvzap-route-a4141-qwen-allhead-native-storage-page-state-gate-1.0` is
A4.1.3.6, the all-head, budget-512 counterpart. It requires all layer-zero KV
heads to use the external Route-A ownership interface while persistent selected
native mature-cold tensors remain absent. Its aggregate page guard requires one
witness head (not every head) to simultaneously observe a sealed full page, a
second packed page, and a nonempty tail. This distinction is required because
an original-mask head may validly retain zero mature cold tokens. Per-head
coverage and the aggregate witness list are recorded. It is an untimed semantic
representation gate; transient views, allocator/HBM, runtime, throughput,
energy, hardware, and RTL remain out of scope.

`kvzap-route-a4142-qwen-multilayer-allhead-native-storage-gate-1.0` is
A4.1.3.7, the initial three-layer `{0,18,35}` all-KV-head, budget-one
counterpart. It requires each target layer to have an independent external
Route-A adapter and all its KV heads to be substituted while the custom cache
retains neither unselected nor selected mature-cold K/V at those target layers.
The matching three-layer replay source must have budget-one provenance, and
pending staging is required in at least one target-layer/head state. Non-target
layers retain native Qwen cache state. This is an untimed semantic interface
gate; transient views, allocator/HBM, runtime, throughput, energy, hardware,
and RTL remain out of scope.

`kvzap-route-a4143-qwen-multilayer-allhead-native-storage-page-state-gate-1.0`
is A4.1.3.8, the three-layer `{0,18,35}` all-KV-head, budget-512 counterpart.
It requires a separately collected three-layer/budget-512 replay source and
one target-layer/head witness with a sealed full page, multi-page packed state,
and a nonempty tail. The condition is aggregate because many original-mask
heads may validly retain too little, or no, mature cold K/V. Every target layer
must still substitute all KV heads and retain zero persistent selected
mature-cold tensors. This remains an untimed semantic interface gate; transient
views, allocator/HBM, runtime, throughput, energy, hardware, and RTL are out
of scope.

`kvzap-route-a4144-qwen-alllayer-allhead-native-storage-gate-1.0` is
A4.1.3.9, the all-model-layer/all-KV-head, budget-one counterpart. It requires
the literal `--target-layers all` and a completed all-layer/budget-one replay
source. Every model layer has an independent external Route-A adapter and must
substitute all its KV heads; each target-layer persistent cache summary must
have zero selected native mature-cold tensors and zero unselected heads.
Aggregate pending coverage is required. This is an untimed semantic interface
gate; transient views, allocator/HBM, runtime, throughput, energy, hardware,
and RTL are out of scope.

The first A4129 artifact,
`route_a4129_layers_0_18_35_budget1_pending_continuation_01`, completed with
the three-layer source hash `0ceb54ab^d6cea`. Each of layers 0, 18, and 35
consumed its own 7,472 events completely, bridged all eight KV heads across 22
question tokens, and independently passed native-cold poison/read ownership
guards. Aggregate pending coverage was observed. Across the declared
eight-token horizon, forced Route-A argmax and independent Route-A generated
IDs both matched same-mask dense. The largest final-logit maximum was `0.5`,
while the smallest recorded dense top-1/top-2 margin was `20.0`. This permits
the matching budget-512 page-state diagnostic, but remains a single-request,
fixed-horizon, three-layer semantic result only.

The matching A4129 budget-512 artifact,
`route_a4129_layers_0_18_35_budget512_multipage_continuation_01`, completed
aggregate multi-page/full-page/tail guards using the same 22,416-event source.
Multi-page states occurred in layers 0 and 18 (for example, layer-0 head 6 had
four pages, three full pages, and a 63-token tail; layer-18 head 3 had seven
pages, six full pages, and a 62-token tail). All replay, bridge, finite, and
per-layer ownership guards passed. The eight forced argmax values and the
independent greedy IDs again matched same-mask dense. Its largest final-logit
maximum was `0.75`, still below the smallest dense top-1/top-2 margin `20.0`.
The exact scalar logit-difference table is not identical to budget one, which
is expected for legal reduction layouts; no observed decision changed. This
closes the pending-versus-packed layout check for this fixed three-layer
horizon, not all-36-layer, quality, or performance behavior.

`kvzap-route-a4155-empty-source-elision-paired-measurement-1.0` is the A4.1.7.4
fixed-request repeated software-measurement schema. It requires a completed
matching A4154 semantic certificate, then executes adjacent fresh-reset pairs:
unelided all-layer/all-head Route-A external storage and the same path with
only empty hot/pending/packed source partials elided. Each raw row includes a
pair ID, execution order, synchronized wall/CUDA-event values, PyTorch
allocator snapshots, token digest, and scalar empty-source skip counts. The
summary contains callback/reset-run distributions and raw per-pair
candidate-minus-baseline deltas. It does not replace separate Full-KV and
same-mask-dense controls; timing/allocator values are not HBM, throughput,
energy, hardware, or RTL evidence.

`kvzap-route-a4156-empty-source-elision-phase-profiler-1.0` is the A4.1.7.5
profiler-only counterpart to A4155. It requires a completed matching A4155
manifest, performs one unprofiled warm-up plus one coalesced profiler capture
per unelided/elided Route-A variant, and requires each hot/pending/packed
source to account for every merge as either a partial attention call or an
empty-source skip. The profiler is separate from timing repetitions; nested
profiler ranges and memory values are not latency, HBM, throughput, energy,
hardware, or RTL evidence.

For its second-workload use, A4155 accepts
`--require-cross-workload-source-coverage`. The supplied A4154 certificate
must have required cross-workload coverage and must relay the current replay
event-file SHA-256, exact all-layer/KV-head coverage, and event count through
its A4151 provenance. The A4155 manifest records that relay explicitly. This
is provenance validation only, not a timing, memory, HBM, hardware, or RTL
claim.

### Route-A A4.8.1a causal readiness and root-cause propagation audit

`kvzap-route-a481a-readiness-root-cause-1.0` hash-binds the completed A4.8.0
report and every predecessor used there. It first reproduces each fixed A4.8.0
causal replay exactly, then adds observer-only readiness instrumentation. A
transaction is `ready` only when all fixed A4.7.0/A4.7.1 predecessors have
committed; a dependency-blocked transaction is not silently counted as a
service shortage.

The audit reports pre/post-service ready and dependency-blocked backlog, ready
age, per-head ready skew, trace-end residuals, extra no-arrival drain
opportunities, sustained ready-positive logical-opportunity runs, and
phase-separated rows. A shortage-root incident is a dependency-ready group
whose immediate blocker is modeled RMW, same-bank, or cross-bank shortage. Its
canonical lineage is propagated only through unresolved predecessors, so the
report gives downstream groups, lineage observations, and maximum dependency
depth per root. This is an attribution convention, not a complete causal graph
or hardware queueing proof; immediate blocker and root cause remain separate.

No service level, controller state, transaction mapping, FIFO order, commit
boundary, trace horizon, or scheduling decision changes. These logical
readiness/amplification quantities are not hardware capacity, service rate,
bank/port demand, cycle, timing, latency, traffic, bandwidth, throughput,
energy, area, architecture selection, or RTL evidence.

### Route-A A4.8.1b fixed abstract-service readiness/root-cause sweep

`kvzap-route-a481b-fixed-service-sweep-1.0` hash-binds the completed A4.8.1a
and A4.8.0 reports plus their full predecessor chain. It retains the recorded
direct-service and causal-controller baselines side by side, first checking
that A4.8.1a still exactly reproduces A4.8.0. It then replays the exact same
immutable transaction/order/commit/opportunity stream at global, predeclared
fixed per-bank/per-operation abstract quanta `{1,2,4,8,16}`. The sweep has no
future input, workload/anchor/horizon input, controller adaptation, borrowing,
or scheduler action.

For each quantum it reports ready/dependency-blocked backlog and age,
trace-end residual, bounded extra no-arrival drain, sustained ready-positive
run, immediate blocker, and the same declared shortage-root propagation
attribution as A4.8.1a. This permits controller-versus-sustained-service
sensitivity without treating a fixed quantum as a hardware service rate.
The resulting quantities are logical-model observations, not hardware queue,
bank/port, transaction, cycle, timing, latency, traffic, bandwidth,
throughput, energy, area, architecture-selection, or RTL evidence.

### Route-A A4.8.2a contract-simplification legality gate

`kvzap-route-a482a-contract-simplification-gate-1.0` hash-binds A4.8.1b,
A4.8.1a, A4.8.0, and their complete predecessor chain. It freezes the four
semantic record types and every A4.7.1 transaction/commit boundary, then
replays authoritative state after every unchanged commit. The only admitted
non-baseline work template expands one existing same-record RMW into one
logical read plus one logical write that remain invisible until that same
commit. It preserves record identity and adds no semantic record, but records
both the extra work and a same-record commit-exclusion obligation.

A versioned/shadow update is explicitly rejected: a latest-version selector is
additional semantic state not present in the frozen catalog or A4.7.1 sets.
Negative controls reject partial publication and ambiguous selector visibility.
This closes the A4.8.2a semantic variant catalog; A4.8.2b may assess only the
admitted baseline and read/write-expansion templates with full total-work,
footprint, readiness, drain, and root-amplification accounting.

The ledger is logical contract work, not hardware RMW/read/write accesses,
atomics, queues, banks/ports, cycles, timing, latency, traffic, bandwidth,
throughput, energy, area, architecture selection, or RTL evidence.

### Route-A A4.9.0 final eager-RMW envelope closure

`kvzap-route-a490-eager-rmw-envelope-1.0` hash-binds the completed A4.8.2b
eager-RMW closure and its full predecessor chain. It contains no new service
or semantic variant. It first reproduces A4.8.2b's eager modeled demand, then
retains A4.7.2.0 zero-slack per-context persistent metadata observations while
using A4.7.2.1 cross-context joint-safe references for its persistent-footprint
exit proof, along with per unchanged atomic-group commit/exclusion state,
existing object/bank fanout, and the already-recorded reasoning `q=4` drain
observation.

Its completion record names the count as `persistent_joint_safe_refs`; this is
the number of A4.7.2.1 cross-context references, never a count of A4.7.2.0
per-context observations.

It is the final envelope schema: no `A4.9.0.x` extension is authorized. A
finite observation in its covered traces is not a proof for arbitrary future
workloads, and none of its metadata bits, temporary state, fanout, abstract
quantum, or drain observations selects SRAM capacity, bank count, port count,
queue depth, RMW lane count, cycle/timing cost, architecture, or RTL.

### Route-A A4.9.1 declared-candidate metadata-engine replay

`kvzap-route-a491-candidate-metadata-engine-1.0` consumes the completed A4.9.0
closure and immutable A4.7.1 transaction trace. It declares a small fixed set
of bank/port/RMW-lane/queue/cycle candidates and replays their conservative
atomic-group reservations without changing FIFO, ownership, or commit order.
Its cycles are declared model units, not calibrated hardware latency.
It additionally records joint-safe raw modeled-object widths and the declared
64-bit padded candidate entries, with a no-field-overflow guard.

### Route-A A4.8.2b admitted-template fixed-service replay

`kvzap-route-a482b-contract-simplification-replay-1.0` hash-binds the closed
A4.8.2a report and the full A4.8.1b/A4.8.1a/A4.8.0 predecessor chain. It has
exactly two options: the eager RMW baseline and A4.8.2a's same-record
read/write expansion. It first requires eager modeled storage-object demands
and every fixed-quantum replay to reproduce A4.8.1b exactly. The alternate
maps an existing modeled storage-object RMW demand to read plus write demand on
that same object; neither may independently publish before the existing A4.7.1
commit boundary.

The schema records semantic-record work separately from modeled storage-object
demand, fixed semantic catalog/A4.7.2.1 footprint references, the explicitly
unselected commit-exclusion realization footprint, and per-option/quantum
ready backlog, age, residual, bounded no-arrival drain, and canonical root
lineage. These remain trace-derived/functional/model quantities, never
hardware accesses, queues, ports, cycles, latency, traffic, bandwidth,
throughput, energy, area, architecture selection, or RTL evidence.

`kvzap-route-a4162-cross-workload-three-path-measurement-1.0` is the A4.1.7.11
second-workload repeated measurement schema.  Every fresh reset run is one of
Full-KV bypass, same-mask dense replay, or A4154-certified empty-source-elided
Route-A external storage; order is randomized within each repetition.  It
requires the current A4151 execution certificate, current A4154 elision
certificate, and (when requested) their cross-workload source-coverage relay.
The dense and Route-A token digests are checked against their separate
certificates and their relation is recorded; Full-KV equality is not required.
CUDA/wall distributions and PyTorch allocator maxima remain software
observations, not HBM, throughput, energy, hardware, or RTL evidence.
Its raw repetitions use
`kvzap-route-a4162-cross-workload-three-path-raw-1.0`, validated by the shared
A4.1 raw-record contract before inclusion in any distribution.

`kvzap-route-a4163-cross-workload-three-path-profiler-1.0` is the A4.1.7.12
profiler-only counterpart. It consumes the completed A4162 measurement plus
the A4151/A4154 certificates, then takes one separate profile capture for
Full-KV bypass, same-mask dense replay, and empty-source-elided Route-A after
an unprofiled fresh-cache warm-up per path. Tagged Route-A source
partial-or-skip and merge accounting must cover every attention evaluation.
Profiler ranges are nested diagnostic views, never timing distributions or
HBM, throughput, energy, hardware, or RTL evidence.

`kvzap-route-a4164-component-accounting-report-1.0` is the A4.1.7.13
no-model report schema. It accepts only completed A4161/A4162/A4163 artifacts
with one exact replay event SHA-256 and validates their semantic/execution
guards before normalizing source partial/skip/merge call counts by the fixed
request's reported generated-token count. It does not add timings, aggregate
profiler range time, or claim hardware operations, traffic, or latency.

`kvzap-route-a4165-long-horizon-semantic-pipeline-1.0` is A4.1.7.14. It owns
a new output root and runs a fresh online-dense replay-source collection,
A4151 execution-only semantic certification, then A4154 empty-source-elision
semantic certification for one all-layer/all-head `max_new_tokens >= 32`
request. The final manifest binds all child paths, replay SHA, state/page
guards, and source partial/skip/merge accounting. It is untimed semantic/state
evidence only.

`kvzap-route-a4166-long-horizon-three-path-measurement-1.0` is A4.1.7.15. It
accepts a completed A4165 pipeline, requires its all-layer/budget-512 horizon
configuration, and runs the A4162 three-path runner under a child output
directory. Its parent manifest binds the A4165 replay SHA to the child
measurement. It is repeated Python-reference software measurement only.

`kvzap-route-a4167-long-horizon-three-path-profiler-1.0` is A4.1.7.16. It
accepts only a completed A4166 parent whose bound A4165 configuration is the
all-layer/all-head, budget-512, `max_new_tokens >= 32` semantic pipeline. It
runs the existing A4163 three-path profiler under a child directory with
offline cached model resolution, and requires the child to bind the same replay
event SHA-256 plus its token-digest, source partial-or-skip/merge, and
coalesced-phase guards. It is one separate profiler diagnostic per path, not a
timing distribution or any HBM, throughput, hardware, or RTL measurement.

`kvzap-route-a4168-cross-horizon-accounting-report-1.0` is A4.1.7.17. It is
an offline report over a completed 16-token A4164 component-accounting artifact
and a completed 32-token A4167 profiler parent. It revalidates each horizon's
own internal source/semantic/profiler chain, then reports generated-token
normalized hot/packed/pending partial-or-skip/merge accounting and page/tail
witnesses. The two freshly collected horizon sources are explicitly *not*
required to have equal SHA-256 values. It runs no model and does not aggregate
or compare profiler range times as latency.

`kvzap-route-a4200-observed-resource-contract-1.0` is A4.2.0. It accepts the
completed A4168 cross-horizon report and its bound A4167 parent, revalidates
the all-layer/all-head external-storage and native-cold-absence guards, and
records a software-observed contract for the explicit bypass control, three
ordered sources, one merge per evaluation, page/tail witnesses, and unresolved
hardware parameters. It is not an architecture-specification freeze: FIFO
depth, PTE width, allocator/seal policy, bank/burst/gather format, merge state
precision, PE scheduler, and switching/service timing remain explicitly
unresolved. It executes no model and derives no hardware sizing or timing.

`kvzap-route-a4201-contract-sensitivity-matrix-1.0` is A4.2.1. It accepts a
completed A4200 contract plus declared A3.6 hybrid and A3-edge DSE manifests.
It maps every explicitly unresolved A4200 parameter to an observed interface
requirement and, where available, an explicitly labeled modeled candidate
range. The 64-token observed page point must be represented by both DSE inputs.
No candidate range is selected as a hardware value; cross-engine merge versus
scheduler placement is retained as an explicit reconciliation item. It runs no
model and does not transform modeled bytes/cycles into measurement.

#### A4.2 status boundary (2026-09-09)

Completed A4200/A4201 artifacts establish an observed software interface and
a mapping to declared A3 model ranges only. They do not freeze an architecture
specification, select an engine count, FIFO depth, PTE width, bank/burst map,
merge precision, scheduler, admission overlap, or control timing. Any later
contract refinement must preserve this observed-versus-modeled separation and
bind a new result to the exact A4200/A4201 input hashes.

`kvzap-route-a422-scheduler-merge-placement-1.0` is A4.2.2. It consumes a
completed A4168 cross-horizon accounting report, A4200 observed resource
contract, and A4201 sensitivity matrix, recording all three input SHA-256
values. It compares two **modeled** organizations at the retained policy point
(`threshold=-4`, hot window `128`, page `64`, admission budget `512`):
co-located `(layer, KV head-group)` hot/pending/packed source service plus
online merge, and split-source service that exports `{partial max, partial
normalization state, partial value accumulator, valid/empty}` to an explicit
reduction interface. A4168 source partial/skip/merge conservation is a hard
gate. The split rows make state payload, one state transfer per non-empty
source, reduction dispatch, and an in-flight partial-state capacity *axis*
explicit. Because the inputs have no service timeline, that axis cannot infer
queue occupancy or FIFO depth. New interface-work axes are abstract modeled
units, not hardware cycles. The study executes no model and must not report
HBM traffic, latency, throughput, energy, area, frequency, hardware
acceleration, hardware sizing, or RTL readiness.

`kvzap-route-a423-scheduler-merge-service-sensitivity-1.0` is A4.2.3. It
consumes completed A4168 accounting and A422 placement reports, records their
SHA-256 values, and runs no model. A4168 does not contain a per-evaluation
source completion/reduction-arrival timeline. A423 therefore derives only the
inclusion-exclusion bounds for 1/2/3 active sources per merge from hot,
packed, and pending marginal counts; it does not recover queue occupancy. Its
co-located serial-service and split-source barrier-service rows sweep abstract
source, transfer, reduction-dispatch, merge-work, and per-logical-evaluation
state-capacity axes. Those values are modeled work labels, not cycles or
latency; the state capacity is not a FIFO depth or reducer count. No row may
claim measured scheduling behavior, HBM traffic, throughput, energy, area,
frequency, hardware acceleration, final placement, or RTL readiness.

`kvzap-route-a424-ordered-logical-event-gate-1.0` is A4.2.4. It runs an
explicitly enabled, untimed recorder alongside the accepted all-layer/all-head
policy-on external-cold Route-A path. Each logical attention invocation records
only its global invocation sequence, layer, KV/query head, cache position,
hot/pending/packed ordered partial-or-skip decision, scalar record-position
range, page/tail witness, and the one subsequent merge marker. The artifact
contains no Python/CUDA/hardware timestamp, source-completion event, or
reduction-arrival event. Trace-off, trace-on forced-token, and trace-on
independent runs must retain replay, ownership/native-cold, source-decision,
and token/logit guards. The gzip JSONL is a functional logical-order artifact,
not a timing trace, queue measurement, HBM traffic, throughput, energy, area,
hardware acceleration, or RTL result.

For cross-workload A4.1 collection, `collect_kvzap_route_a41_replay_source.py`
may record `replay_event_coverage`: selected-layer KV-head IDs, per-head event
and keep counts, retained-event count at/after the hot-window boundary, and
maximum cache position. `--require-all-kv-heads` rejects missing or unexpected
event-head IDs. This remains predictor-mask source provenance only; it does
not establish pending/packed state, physical capacity, timing, HBM traffic,
hardware, or RTL behavior.

The A4151 execution semantic gate accepts `--require-replay-event-coverage`.
When set, it stores and requires exact collector-recorded KV-head coverage for
every selected layer before guarded/execution-only comparison. This binds the
semantic result to the new source provenance; it does not alter the mask,
attention, state, timing, or claim boundaries.

For cross-workload A4154 use `--require-cross-workload-source-coverage`. It
requires both the current collector source and supplied A4151 certificate to
bind the same all-layer/KV-head event coverage and event count. This is source
provenance protection only; it does not establish elision performance.

`kvzap-route-a4157-empty-source-elision-reproducibility-gate-1.0` is the
A4.1.7.6 multi-batch extension of A4155. It retains raw fresh-reset pair rows
across batches, reports per-batch and aggregate signed-delta distributions
plus median absolute deviation, and records device-global nvidia-smi state
before/after each timed region without inspecting processes. Telemetry is
context only: it is not per-process attribution, HBM traffic, throughput,
energy, hardware, or RTL evidence.

`kvzap-route-a425-ordered-logical-schedule-1.0` is A4.2.5. It consumes a
completed A424 ordered-logical-event manifest plus completed A422/A423 modeled
placement inputs, records their SHA-256 values, and executes no model. A424
logical invocation sequence is validated as a contiguous submission order with
one ordered hot/pending/packed partial-or-skip decision and one subsequent
merge marker per event; timestamp-bearing events are rejected. A4.2.5 then
compares a co-located logical `(layer, KV head)` owner with a split-source
logical dependency that exports `{partial max, partial normalization state,
partial value accumulator, valid/empty}` to a local reduction dependency. Its
submission spacing, source work, transfer, dispatch, and merge work are
declared sensitivity axes in abstract work units. Resulting work positions or
dependency waits are not cycles, timestamps, latency, throughput, queue
occupancy, FIFO depth, reducer count, controller timing, HBM traffic, energy,
area, frequency, hardware sizing, final placement, acceleration, or RTL
evidence.

`kvzap-route-a426-exact-fanin-distribution-1.0` is A4.2.6. It consumes the
completed A424 timestamp-free gzip event stream and A423 marginal fan-in report
by SHA-256, validates A424's independent event summary, then counts exact
1/2/3-active-source combinations and per-`(layer, KV head)` fan-in rows for
the one fixed request. It checks these exact counts lie within A423's
inclusion-exclusion bounds. This is event-structure accounting only: it
records no source service/completion order, reduction arrival, timing, queue
occupancy, FIFO depth, engine utilization, cycles, latency, throughput, HBM
traffic, energy, area, frequency, hardware sizing, scheduler selection, or
RTL evidence.

`kvzap-route-a427-cross-workload-logical-stability-1.0` is A4.2.7. It first
collects a fresh second-workload online dense replay source, certifies A4151
execution semantics and A4154 empty-source elision semantics, then runs a
fresh all-layer/all-KV-head A424 ordered-event gate. Its final no-model report
hash-binds both accepted A424 manifests and gzip files, and compares only
source partial/skip fractions, exact active-source fan-in fractions, and
source-combination fractions under an identical non-horizon policy point. A
candidate records its declared child `max_new_tokens` separately from its
actual fresh-source `q_len=1` policy-decode-call count. A long-cap probe
selects the semantic child cap, and a separately collected source uses that
cap; its actual call count may differ because question forwarding can be
multi-token and generation can stop at EOS. A4151/A4154/A424 replay-complete
gates, rather than an equality assertion in A427, prove exact event
consumption. Comparisons are normalized by each event stream's count. It intentionally
selects no stability threshold. Event differences do not imply
source completion/arrival order, buffer or FIFO occupancy, backpressure,
cycles, latency, throughput, HBM traffic, energy, area, hardware sizing,
scheduler/placement selection, or RTL evidence.

`kvzap-route-a429-matched-interface-demand-1.0` is A4.2.9. It SHA-256 binds
completed A428 matched-horizon workload artifacts and the completed A422
interface definition, validates each A424 event artifact hash, then counts
one modeled split-source partial-state export per nonempty source and the
additional reduction inputs per merge. It reports per-workload and per-layer/
KV-head partial record and page/tail witness distributions. These are abstract
interface units, not bytes or cycles: no source completion/reduction arrival,
queue/FIFO occupancy, backpressure, latency, throughput, HBM, hardware, or
RTL result is claimed.

`kvzap-route-a4210-modeled-backpressure-envelope-1.0` is A4.2.10. It binds
A428, A429, and A425 SHA-256 inputs, rechecks matched-workload A424 event
hashes, and sweeps declared virtual source/reducer work and state-capacity
axes. Split-source exports, virtual in-flight states, blocked exports and wait
are model outputs; co-located cross-engine exports are explicitly zero. No
arrival/completion time, observed queue/FIFO occupancy, cycles, latency, HBM,
hardware, scheduler-selection, or RTL result is asserted.

Schema version `2.0` aggregates the active source partials of one logical
invocation into one fan-in merge task. Its capacity axis is abstract merge-task
capacity; it must not be compared as a physical FIFO depth with the preserved
v1 serial-per-partial study.

`kvzap-route-a428-matched-horizon-workload-stability-1.0` is A4.2.8. It
collects new summarization, retrieval, and reasoning replay sources at one
declared `max_new_tokens`, rejects unequal all-layer actual `q_len=1`
policy-decode-call counts, then requires A4151, A4154, and A424 for every
workload. The final report SHA-256-binds each fresh source and ordered-event
artifact and summarizes source partial/skip combinations, fan-in, partial
record-count distributions, and packed page/tail witnesses. It is functional
and timestamp-free logical-event evidence only: it does not measure quality,
runtime, source completion/reduction arrival, queue/FIFO occupancy,
backpressure, cycles, latency, HBM traffic, throughput, energy, area,
hardware, scheduler selection, or RTL readiness.

`kvzap-route-a4211-partitioned-backpressure-sensitivity-1.0` is A4.2.11. It
hash-binds A428/A429 inputs and sweeps declared merge placement, logical burst,
fan-in hierarchy, reducer parallelism and task-capacity contracts. Its virtual
backpressure outputs are not measured queue/FIFO occupancy, timing, cycles,
latency, HBM, hardware, or RTL evidence.

`kvzap-route-a4212-dispatch-epoch-evidence-1.0` is A4.2.12. It binds the
accepted A428 report and each A424 gzip event stream by SHA-256, then records a
separate gzip row per logical event with a reconstructed `forward_epoch`,
`layer_dispatch_epoch`, and `source_ready_epoch`. A forward epoch begins only
when the observed layer order resets; a layer dispatch epoch is one contiguous
`(layer, phase, cache_position)` region. The report verifies that the recorded
reference dispatch is serial, that same-KV-head query-head events see one
identical source snapshot, and that layer order never regresses within an
epoch. Same-layer source readiness is a dependency-preserving constructed
eligibility label; it is not a concurrent execution interval. Cross-layer
events remain ordered. No source completion/arrival timestamp, queue/FIFO
occupancy, cycle, latency, throughput, HBM, hardware, or RTL evidence is
recorded.

Its dispatch-epoch gzip uses fixed `mtime=0` and an empty gzip filename, so
the artifact SHA-256 is stable across hosts; this is a provenance property,
not a timing field or semantic change.

Schema version `2.0` of
`kvzap-route-a4211-partitioned-backpressure-sensitivity-2.0` optionally
SHA-256-binds A4.2.12 and adds `trace_dispatch_epoch` as an arrival contract.
It may place events from the same reconstructed layer epoch at one abstract
arrival label, while retaining distinct labels across layer epochs. The model's
backpressure and finish-work rows remain virtual-work outputs and must not be
interpreted as measured ready time, physical dispatch, FIFO occupancy, or a
hardware placement decision.

`kvzap-route-a4213-same-layer-group-contract-1.0` is A4.2.13. It binds A428
and A4212 by SHA-256 and revalidates that every same `(forward epoch, layer
dispatch epoch, KV head)` group has one immutable source/page snapshot across
its distinct query heads. It reports two logical accounting views: independent
per-query source/page-descriptor dispatch controls and one coalesced control
per active source per KV head-group. Each query head still owns one source
partial-softmax state and one online merge; neither state nor merge is reused.
Dispatch-control units are not bytes, operations, cycles, timing, queue/FIFO
occupancy, HBM traffic, throughput, energy, area, or hardware evidence.

`kvzap-route-a4214-core-contract-closure-1.0` is A4.2.14. It is a new-output,
no-model archive report that SHA-256 binds A4200, A4201, A428, A4211 schema v2,
A4212, and A4213. It requires their semantic, hash, workload-coverage, and
no-selection guards, then separates `Route-A Core Contract v1` from the fixed
Qwen3-8B/KVzap resource descriptor. A4211 arrival/placement rows and A4201
parameter ranges remain explicitly modeled and unresolved. The closure is
neither an architecture specification nor a FIFO/PTE/bank/burst/precision/PE/
scheduler/controller-timing freeze, hardware measurement, or RTL gate.

`kvzap-llama31-m0-provenance-1.0` is the no-model M0 entry gate for the cached
`NousResearch/Meta-Llama-3.1-8B-Instruct` snapshot. It records the fixed
snapshot revision; SHA-256/size records for `config.json`,
`tokenizer_config.json`, and the safetensors index; declared-shard existence;
the code-derived Linear KVzap predictor ID; the resolved predictor revision
and predictor-config SHA-256; and the JSON-level Llama/predictor dimension
compatibility check. It also records whether the official predictor repository
matches `KVzapPress`'s direct base-name derivation. A mismatch produces a
`blocked` report unless the invocation explicitly binds the reviewed,
default-off `predictor_repo_id_override` to that exact official predictor. It
rejects an existing output directory. It never imports a model runtime or
loads base/predictor weights, so it is observed provenance plus
code-derived compatibility only—not trace, semantic, accuracy, traffic,
timing, hardware, or RTL evidence.

`kvzap-llama31-m1-semantic-gate-1.0` is the next, untimed functional gate for
the M0-bound `NousResearch/Meta-Llama-3.1-8B-Instruct` snapshot.  It requires
a completed M0 manifest, its fixed base/predictor revisions, and the reviewed
default-off `predictor_repo_id_override` bound exactly to
`nvidia/KVzap-linear-Llama-3.1-8B-Instruct`.  It runs a Full-KV bypass, an
online same-mask dense control, and a Route-A hot/pending/packed control over
all 32 layers and all 8 KV heads.  Route-A consumes the dense control's online
original score-threshold decisions exactly once, then executes its FP32 and
executed-dtype same-mask numerical guards.  It deliberately does not claim
that a Route-A path can independently re-score identically after its own
attention substitution has changed later hidden states.  It records only hashes, bounded
scalar coverage/comparison summaries, and optional source-presence booleans;
it stores no K/V, attention matrices, activations, full logits, or token text.
`page_tokens` and `admission_budget` are explicit functional-reference inputs,
not selected hardware values.  This artifact is functional/trace-derived
evidence for one fixed request only, not model accuracy, a Meta-official
reproduction, traffic, timing, throughput, energy, area, hardware, or RTL
evidence.

`kvzap-llama31-m2-lifecycle-gate-1.0` binds completed M0 and M1 manifests, then
uses the M1 paired-mask contract at two declared functional-reference points.
At budget one, all-layer/all-KV-head Route-A state must observe hot, pending,
and packed service. At budget 512, it must observe hot/packed service and at
least one sealed packed page with multi-page state and a nonempty tail. Dense
attention is the sole online original-mask source; Route-A replays every event
exactly once, and both paths execute same-mask numerical guards. The output
contains hashes and bounded scalar lifecycle/page summaries only. It owns no
native model cache and establishes no external-cache ownership, allocator,
traffic, timing, throughput, energy, area, hardware, or RTL conclusion. The
two page/admission values are lifecycle probes, not hardware selections.

`kvzap-route-a-m3-portability-envelope-comparison-1.0` is a new-output,
no-model report that SHA-256 binds completed Qwen A4.2.14, Llama M0, M1, and
M2 artifacts. It rejects absent/incomplete inputs, missing required guards, or
broken M0-to-M1-to-M2 provenance hashes. Its portable-contract section records
only the two-anchor semantic compatibility checks; its Qwen and Llama sections
remain separate fixed-workload descriptors. In particular, Qwen source/fan-in/
page-tail distributions must not be merged with Llama's lifecycle scalar
summaries into a universal resource envelope. The report does not load a model,
estimate capacity, traffic, latency, throughput, energy, or area, select a
hardware parameter, authorize an architecture specification, or gate RTL.

`kvzap-route-a-m3-portability-envelope-comparison-1.1` is a fresh-output
archival clarification that also binds a completed `1.0` report. It replaces
the ambiguous descriptor field `kv_head_count` with both
`kv_heads_per_layer` and `total_layer_kv_head_state_count`. It additionally
records the prior/current raw Qwen source hashes and canonical hashes of the
Qwen semantic projection that M3.1 serializes or consumes; a mismatch in that
projection rejects the report. Equal projections do not imply byte identity of
the whole upstream reports. Version 1.1 adds no model run, workload sample,
capacity/traffic/timing estimate, hardware selection, architecture
specification, or RTL authorization.

`kvzap-llama31-m4-bounded-workload-envelope-1.0` is a new-output, no-model
aggregation of three completed `kvzap-llama31-m2-lifecycle-gate-1.0` manifests
for the fixed built-in retrieval, summarization, and reasoning requests. It
requires every input to bind the same M0/M1 manifests and matched functional
reference inputs, and rejects duplicate request content or missing M2 semantic
guards. It contains per-request bounded scalar descriptors and a coverage
summary; it must not turn their minima, maxima, or source/page observations
into a Llama distribution, universal resource envelope, capacity/traffic/
timing estimate, hardware parameter selection, architecture specification, or
RTL gate.

M4 input M2 manifests may declare `execution_dtype_ulp_mode=record_only` only
as an explicit bounded diagnostic after a strict enforce run reports a breach.
Such an M2 still requires executed same-mask numerical-guard work and exact
online-mask replay, and records per-layer breach counts, finite/infinite status,
bounded samples, and maximum observed ULP. A recorded breach is not a strict
numerical pass and must be kept distinct from an enforce-mode input. M4 requires
the same declared ULP mode, limit, and sample bound for all three workloads;
these are software numerical-diagnostic controls, not merge precision or a
hardware parameter.

`kvzap-llama31-m41-summarization-ulp-diagnostic-1.0` binds a completed M4
report and its three record-only M2 inputs. It validates the M4 hashes, M2
replay/guard boundaries, and each retained breach sample, then joins ULP count
to its scalar FP32 absolute difference, local route/dense values, ULP spacing,
reference point, and location. It may state whether a recorded FP32 maximum is
within the declared software `atol`; it cannot promote record-only evidence to
a strict ULP pass or select merge precision, capacity, traffic, timing,
hardware, architecture, or RTL parameters.

`kvzap-llama31-m5-matched-horizon-workload-descriptor-1.0` binds completed
Llama M0, M1, M4, and M4.1 artifacts by SHA-256, retaining M4.1's explicit
non-strict summarization 16-ULP context. It runs fresh fixed retrieval,
summarization, and reasoning requests at the M4-declared cap and rejects the
run unless all layers have one equal actual `q_len=1` policy-decode-call count.
For each request, Full-KV bypass is separate, online same-mask dense supplies
the original decisions, and Route-A consumes that decision stream once while
an enabled logical recorder stores ordered hot/pending/packed partial-or-skip
rows and one merge marker. The report records hashes plus event-normalized
source-combination/fan-in, partial record-count, and page/tail descriptors at
both workload and `(layer, KV head)` granularity. Events have no source-ready,
completion, Python, CUDA, or hardware timestamps. Thus this is bounded
functional/trace-derived descriptor alignment with Qwen A4.2.8 fields, not a
workload distribution, common hardware envelope, capacity, HBM traffic,
queue/FIFO, backpressure, timing, throughput, energy, area, architecture, or
RTL result. Its record-only setting does not alter M2's default enforce mode
or select a merge precision or any hardware parameter.

`kvzap-llama31-m51-fixed-horizon-workload-descriptor-1.1` is a fresh-output
correction after preserved M5 and M5.1.0 `started` records report unequal natural
policy-decode-call counts under the same pipeline cap. It SHA-256 binds M0,
M1, M4, M4.1, and that failed M5 record. It runs an explicit fixed non-EOS
continuation of eight tokens: Full-KV and dense select their fixed-length
greedy trajectories, while Route-A replays the dense token trajectory and the
same online-dense mask stream. Every workload must have exactly seven
`q_len=1` calls in all 32 layers, and dense/Route-A token IDs must match under
the declared forced trajectory. Existing per-attention FP32/executed-dtype
same-mask guards remain the numerical gate; whole-vocabulary logits after the
explicitly forced post-EOS trajectory are not a M5.1 gate. The report then uses the M5
timestamp-free event schema and its per-workload/per-`(layer, KV head)`
normalized source/fan-in/page-tail descriptors. This deliberately conditioned
continuation is not a natural output-length, accuracy, or serving result; it
has no source-ready/completion timestamp and cannot establish queue/FIFO,
backpressure, cycles, latency, HBM traffic, throughput, energy, area, hardware
parameters, architecture, or RTL conclusions. It preserves M4.1's record-only
ULP context and does not alter M2's default enforce guard.

`kvzap-route-a-m6-cross-model-fixed-horizon-envelope-1.2` is a fresh-output,
no-model comparison that SHA-256 binds the completed Qwen A4.2.14 core closure,
Qwen A4.2.8 matched-horizon descriptor report, and Llama M5.1 fixed-horizon
descriptor report. It additionally SHA-256 binds completed M3.2 and recreates
its canonical Qwen consumed projection: if the local and remote raw A4.2.14
JSON hashes differ, their projection must agree with M3.2 and the supplied raw
hash must be one of M3.2's two recorded hashes. Both are recorded in the
output. An unreconciled or unrecognized raw-hash difference is a hard failure. It
requires all six fixed workload rows to share the
declared eight-token continuation, seven all-layer `q_len=1` policy-decode
calls, hot window 128, and page reference 64. It retains each model/workload
row and reports only observed min/max coverage across normalized source
combination, active-source fan-in, source-active fraction, source-nonempty
conditional record-count, and packed-tail descriptor fields. It rejects absent
or inconsistent descriptor fields rather than silently treating them as zero;
only a combination absent from an otherwise valid fraction vector is explicitly
represented as an observed zero in that vector.

M6 must not pool absolute invocation/event counts, layer counts, or aggregate
KV-head state counts across models. Its observed min/max values are fixed-row
coverage summaries, not a workload distribution, capacity requirement, FIFO,
PTE width, bank/burst, merge precision, PE count, scheduler, controller timing,
traffic, latency, throughput, energy, area, hardware, architecture, or RTL
result. M6 preserves Llama M4.1's record-only ULP context and cannot turn it
into a strict numerical pass or a precision selection.

### Route-A frontend terminal-decision stream (SnapKV P0)

`route-a-frontend-decision-stream-1.0` is a compact, final-decision-only NPZ
for a pruning frontend that is being assessed for Route-A mapping.  Its rows
contain `frontend_name`, `request_id`, `decision_epoch`, `model_call_index`,
`layer`, `kv_head`, `original_position`, declared `sequence_length`, terminal
`keep`, and scalar `score`; it contains neither token text nor K/V tensors.
Every `(model_call_index, layer, kv_head, original_position)` identity occurs
once.  The declared sequence length makes a truncated tail a validation error
rather than silently redefining the request as shorter.

The first frontend is `snapkv_prefill_topk` at epoch `prefill_terminal`.
`tools/run_snapkv_route_a_p0_contract_gate.py` attaches only a post-attention
observer to a dense Qwen3-8B prefill; it never installs `SnapKVPress`'s native
cache-replacing hook.  It computes the same `ScorerPress.select_topk_indices`
set as native SnapKV, then serializes actions in canonical original-position
order.  The native score-ranked K/V gather order is recorded neither as a
Route-A identity order nor as a semantic equivalence claim.  The P0 validator
requires contiguous coverage of each declared sequence, the configured top-k
keep count, and retention of SnapKV's padded observation window.  Its two-pass
runner also requires the trace-on observer answer digest to equal a trace-off
dense control under the same seed.  A SnapKV P0 stream is one terminal prefill
epoch, so it has no online pending/maturity timeline and cannot by itself
establish a KVzap-like lifecycle.

P0 is functional evidence plus trace-derived frontend evidence when collected
on a model.  It is not same-mask decode equivalence, accuracy, physical cache
layout, allocator behavior, HBM traffic, timing, throughput, energy, area,
hardware sizing, architecture specification, or RTL evidence.  The planned
order is P1 then P3 then P2: P1 first performs offline packed-page opportunity
analysis from this canonical stream; P3 then consumes it in a same-mask
dense/Route-A functional comparison; P2 follows only after that mapping is
semantically accepted.

### SnapKV P1 static packed-page opportunity

`route-a-snapkv-p1-static-packed-opportunity-1.0` is a new-output, no-model
analysis of exactly one complete `route-a-snapkv-p0-contract-gate-1.0`
directory. `tools/analyze_snapkv_route_a_p1_packed_opportunity.py` validates
the P0 manifest/status, trace-off/on guard, registered terminal-stream filename
and SHA-256, then revalidates the terminal-decision contract. It accepts one
contiguous P0 prefill call with complete contiguous layer/KV-head/position
coverage and constructs an explicit final-drop array once.

For this mapping study only, the P0 SnapKV protected observation window is the
resident hot window; terminal keeps before it append independently to cold
pages in canonical original-position order, and terminal drops are absent.
The tool rejects a different resident-window value. Page sizes are explicit
static study axes. It writes one request row per page size and one layer-head
row per page size with slots, pages, tail waste, and declared metadata/K+V byte
accounting. Declared bytes are not allocator memory or HBM traffic
measurements; P1 has no model execution, native score-ranked gather order,
pending/maturity state, same-mask attention, scheduler, timing, or hardware
claim. The protected observation window is not a final Route-A or hardware
hot-window choice.

### SnapKV P3 same-mask prefill-tail semantic gate

`route-a-snapkv-p3-same-mask-semantic-gate-1.0` accepts only a completed P0
directory and P1 report. It recomputes the P0 manifest and terminal-stream
SHA-256 values, verifies P1's back-pointers and canonical mapping, and requires
the P1 `P=64` row. It converts each P0 terminal decision to the existing
Route-A `(layer, KV head, original position)` replay identity; native
score-ranked gather order remains unused.

P0 has no question or generated-token decision. Therefore P3 runs exactly the
P0 context prefill, leaves its multi-token output unchanged, and never invents
a later action. After appending the single terminal prefill epoch, it uses the
final real prefill query in every layer as a read-only probe against two
independent functional states:
same-mask dense cold lists and Route-A hot/pending/packed pages with
online-softmax merge. It records scalar numerical comparisons and requires
exact replay, all-layer/head coverage, matching mask digests, and an exact P1
`P=64` hot/cold/page/tail state cross-check. `page_tokens=64` and
`admission_budget=4096` fully materialize this fixed terminal state only; they
are not page/FIFO/PTE/bank/burst/merge-precision/PE/scheduler/controller
hardware selections.

The FP32 same-mask numerical guard is enforced. Its executed-dtype ULP field is
a bounded scalar `record_only` diagnostic because different reduction orders
can round differently; it is neither a strict ULP pass nor a merge-precision
selection.

P3's decisions are trace-derived and its comparison is functional. It is not
native SnapKV cache/decode validation, accuracy, allocator or physical-capacity
measurement, HBM traffic, true hardware latency/throughput/energy/area,
architecture specification, or RTL evidence.

### SnapKV P2 lifecycle/resource descriptor

`route-a-snapkv-p2-lifecycle-resource-descriptor-1.0` is a new-output,
no-model descriptor that consumes only completed SnapKV P0, P1, and P3
artifacts.  It recomputes and validates P0 manifest/stream, P1 report, and P3
manifest SHA-256 bindings; it also requires P3's exact terminal replay,
same-mask FP32 guard, canonical original-position mapping, and no-native-cache
replacement guards.  The descriptor contains individual field records with
`available` or `unavailable` status, an evidence classification, a value, and
an evidence explanation.

Available fields are limited to the one terminal per-identity action set,
canonical original-position mapping, protected-suffix-to-hot compatibility
mapping, static packed terminal state, and bounded prefill-tail same-mask
semantic probe.  One-shot prefill deliberately leaves online decision epochs,
maturity events, pending arrival/service/occupancy, generated-token decisions,
native cache replacement/decode behavior, source-ready/dispatch/completion
order, scheduler/backpressure, allocator/interface fields, and hardware
metrics unavailable.  An unavailable value is represented as `null`, never as
zero.  Thus a P3 terminal state with zero pending tokens cannot be reinterpreted
as evidence of zero pending behavior during decode.

P2 is provenance-backed trace-derived/functional field classification, not a
hardware model or measurement.  It selects no FIFO, PTE, bank/burst, merge
precision, PE, scheduler, controller timing, or other parameter, and cannot
authorize native SnapKV decode, scheduling/backpressure, traffic, cycles,
latency, throughput, energy, area, architecture specification, or RTL claims.

The completed fixed-request P2 output is
`analysis/experiments/snapkv_route_a_p2_lifecycle_resource_descriptor_qwen3_8b_01/`.
Its descriptor SHA-256 is
`29835a960c9a010421bf088ad3a869c476f5c67041b0127e4395df41a7c1aa29`, and it
binds P0 manifest/stream, P1 report, and P3 manifest SHA-256 values
`c4a2ef3150197cab46508445f03c622238d93cd650b2778e5981d3b9a0927599`,
`1cb4a7bba15e54486b85cf0377554b5384999e11703183550bdc6809b1e7a365`,
`f55f4a4ca9020dcbf02acce3c7f272dfafd5ecfd0bdfb2a79918015ddfd3010d`, and
`56cd9ca61d303be0154ec12c2934ee4b71c08332d8dc8d32c5e09ca27c73ff37`.
It records five available and eight unavailable fields for one 256,608-event
`prefill_terminal` stream; P3 executed zero generated-token forwards.  The
only positive eligibility is static canonical mapping and a bounded prefill
same-mask probe.  Decode/pending, native cache/decode, scheduler/backpressure,
and physical-resource/hardware contracts remain explicitly ineligible.

### Official trained-DMS M0 provenance and compatibility manifest

`route-a-dms-m0-official-provenance-1.0` is the entry gate for the separately
trained `nvidia/Qwen3-8B-DMS-8x` frontend.  It accepts only the pinned local
snapshot revision `da1535fc3bfb52fa340eca692a7e4e650f98838d`.  Static M0
parses the configuration and Safetensors index, checks the expected DMS
configuration fields and custom-code `auto_map`, parses the four required
checkpoint code files without importing them, and reads Safetensors headers
without materializing tensors.  It records snapshot/config/index/custom-code
hashes and shard metadata in a fresh manifest.

An explicit optional runtime probe may import the pinned local custom code and
perform either configuration loading or one short cache-enabled prefill; it
never downloads, generates tokens, creates Route-A decisions, compares
attention, or measures performance.  `blocked` means only that the exact
runtime/probe combination was incompatible; it is not a DMS or Route-A
negative result.  M0 selects no hardware parameter and establishes no quality,
lifecycle, traffic, latency, throughput, energy, area, architecture, or RTL
claim.

The first recorded instance is
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_01/`, whose
manifest SHA-256 is
`a8b6099eaa618249ff49ef73c43fb7a8df55d2aca2eb510f8c3cd922835b655e`.
Its static source guards accepted the pinned revision.  Its `model-prefill`
probe is `blocked` at model-code import with `ModuleNotFoundError` for
`flash_attn`; configuration custom code had imported, but
`model_weights_loaded=false` and `generation_calls=0`.  This preserves the
exact environment incompatibility as provenance and does not create a DMS
trace or upgrade any evidence classification.

A second isolated-environment probe is recorded separately, rather than
overwriting that blocked result.  The static manifest
`dms_route_a_m0_official_provenance_qwen3_8b_debug_env_static_01` completed
with SHA-256
`a77bee5d89f36889a548a5c9dcd77f7dac4a5a173362eccf1efc3243a945b861`.
Its companion `model-prefill` manifest
`dms_route_a_m0_official_provenance_qwen3_8b_debug_env_01` is blocked with
SHA-256
`91ac04a5d90b11090fc14cce9a325023fe35999f869d312e677c541738336f8e`:
the available FlashAttention `2.8.3` environment has Transformers `4.52.4`,
whose `configuration_utils` lacks `layer_type_validation` required before the
checkpoint configuration can import.  It likewise executed no checkpoint
custom code, loaded no weights, and made no generation, trace, performance, or
hardware claim.

A third M0 runtime probe preserves the result after the unified KVPress
`.venv` gained a separately hash-verified FlashAttention wheel.  The artifact
is `dms_route_a_m0_official_provenance_qwen3_8b_venv_flash_attn_01`, with
manifest SHA-256
`d39a15f0aadbdfefc07665361d8fca8dbd449b179c6095c0ab53129565cfc125`.
It records that configuration custom code imported, while the model remains
unloaded and generation calls remain zero; under Transformers `5.0.0` it is
blocked by missing `Qwen3Config.pad_token_id`.  The separately confirmed
FlashAttention import/minimal CUDA call establishes only dependency
functionality.  It does not make this blocked manifest a DMS trace, hardware
measurement, or an eligibility upgrade for M1.

The next isolated `debug_env` probe upgrades only that environment's
Transformers to the version named by the official DMS README, `4.57.3`, while
preserving PyTorch `2.5.1+cu121`; FlashAttention remains `2.8.3`. M0 now
requires an explicit local `--tokenizer-root` for `model-prefill`, because the
DMS README names the separate base `Qwen/Qwen3-8B` tokenizer and the DMS
snapshot contains no tokenizer files. The fresh static artifact
`dms_route_a_m0_official_provenance_qwen3_8b_debug_env_tf457_tokenizer_contract_static_01`
completed with manifest SHA-256
`35f65e8e72b2342bc4e1caa76157792e6932cbe93c07501798aca9ac384633a7`.
The separate prefill artifact
`dms_route_a_m0_official_provenance_qwen3_8b_debug_env_tf457_base_tokenizer_prefill_01`
completed with manifest SHA-256
`0fda714d8f67b9c646c82788113b4e037c9e3b70ef12121b6133cb103dc7687d`.
It hash-records the supplied base-tokenizer files, loads official DMS weights,
and completes one cache-enabled `[1, 7]` prefill with finite `[1, 7, 151936]`
logits and zero generation calls. This is bounded functional runtime
compatibility only: it is neither a DMS semantic/mask/lifecycle result nor
trace-derived, modeled, or measured hardware evidence.

### Official trained-DMS M1 native semantic manifest

`route-a-dms-m1-native-semantic-gate-1.0` binds a completed official DMS-M0
manifest, its exact local DMS snapshot, and the explicit base-tokenizer root.
It runs the official model twice on one fixed input: first without observation,
then with a wrapper around inherited `DMSCache.update` that only copies binary
decision summaries and per-layer/KV-head native cache lengths before and after
each update. It accepts only if generated token IDs, per-forward last-logit
digests, and final 36-by-8 native-cache-length digest match exactly between
the two runs. It records no K/V tensors, attention matrices, token text, or
performance data.

The first completed M1 artifact is
`analysis/experiments/dms_route_a_m1_native_semantic_qwen3_8b_retrieval_02/`,
manifest SHA-256
`5c3e72957711c6d801667a2da0ca08720ce9e1238393b42137c1c9874a0aaa55`.
For its one 625-token input plus four fixed decode forwards, all 36 layers and
8 KV heads emitted 180 observed cache-update events. It observed 126,919
binary decision-one bits and native cache length below the 629-token logical
history in 269/288 layer-head states (final lengths range 513--629). This is
trace-derived native-DMS state plus functional observer equivalence. DMS's
delayed eviction and cache-slot reuse are not relabeled as Route-A
hot/pending/packed cold storage, so this does not yet establish a Route-A
adapter, physical capacity, traffic, timing, hardware, or RTL claim.

### Official trained-DMS M2 delayed-eviction adapter-contract manifest

`route-a-dms-m2-delayed-eviction-adapter-contract-1.0` is a bounded follow-on
to completed M0 and M1, not a Route-A attention implementation. It runs the
same official DMS request once without observation and once with the existing
read-only cache-update observer extended to make an in-memory copy of the
official binary decision bits. The two native executions must retain exactly
identical generated-token, per-forward last-logit, and final native-cache
length digests. M2 then writes a compressed NPZ containing only flattened
binary decision bits and event layer/call/q-length/kind delimiters—never token
IDs/text, K/V, attention, logits, allocator data, or timing.

An independent pure-Python controller consumes that stream per layer and
KV-head. Its explicit contract is: a decision labels the preceding arrival;
when that arrival subsequently becomes the configured ring's eviction
candidate, its abstract native slot is reused, otherwise the native logical
cache length grows. The manifest accepts only if the controller agrees with
the official native before/after cache lengths at every observed event and with
the final 36-by-8 matrix. Its `dms_cache_ring_window_size` is recorded
separately from the model `dms_window_size`, because official model creation
passes the cache a value one larger than the decision window.

The binary decisions and native-state comparison are trace-derived software
evidence for the fixed request. The standalone controller is functional,
explicitly scoped modeled contract evidence. Abstract slots do not indicate
K/V movement, a hot/pending/packed-cold mapping, allocator capacity, external
storage, or an interface suitable for Route-A. M2 is not a trained-DMS quality
result and makes no HBM/DRAM, latency, throughput, energy, area, hardware,
architecture, or RTL claim.

M1 supplies a completed native-observer prerequisite and identical-request
provenance; M2 records, but does not require, equality of its newly observed
event-summary hash with M1's summary-only hash. M1 did not preserve raw bits,
and cross-run/device summary equality is not the M2 semantic gate. M2 instead
requires its own trace-off/on equivalence and exact per-event native-length
agreement by the controller.

The first completed M2 artifact is
`analysis/experiments/dms_route_a_m2_adapter_contract_qwen3_8b_retrieval_01/`,
manifest SHA-256
`52b1445bf591948c12b8af131e3c92be4be3a9c9f73f35804b5ff77d0cfc842e`.
On the M1-bound 625-token retrieval request plus four fixed decode forwards,
M2 captured 180 events and 127,047 decision-one bits. Its independent
controller exactly matched every native before/after length vector and the
final 36-by-8 matrix; 269/288 final layer-head lengths were below logical
history, and abstract slot reuse was observed in 677 layer-head event states.
The M2 and M1 summary hashes differed across runs and are retained as a
reported comparison, not treated as a controller failure. These are still
fixed-request native-state/control-contract results, not physical capacity or
hardware evidence.

### Official trained-DMS M3 active-native-slot topology manifest

`route-a-dms-m3-active-native-slot-topology-1.0` is the next bounded adapter
precondition after M2. It binds completed M0/M1/M2 manifests and M2's hashed
decision stream, then repeats one fixed official DMS request with trace-off/on
equivalence. The observer copies only official binary decisions, native cache
lengths, `recent_info` ring metadata, and `recent_info_position`; it never
reads or writes K/V, token IDs/text, attention outputs, allocator state, or
timing.

An independent controller assigns each arrival a logical serial and replays
the delayed decision, ring candidate, and native slot reuse. It must agree at
every event with official lengths, full per-head `recent_info`, and ring cursor.
It exports final logical-source serials by active native slot. This establishes
only a control/topology representation for native DMS resident slots. It does
not say that physical slot order is chronological, that attention is
order-invariant in a numerical implementation, or that the topology is already
a Route-A hot/pending/packed-cold mapping. A later functional attention study
remains separately gated.

The accepted M3 artifact is
`analysis/experiments/dms_route_a_m3_active_topology_qwen3_8b_retrieval_04/`,
manifest SHA-256
`f56816bb7998083de49ff24385f4bb5793d4445a98783c2063f328c2b3bf74a7`.
For the fixed 629-token horizon it observed 180 events and accepted every
native length, ring-metadata, and cursor comparison. Its final active native
slots map to unique logical source arrivals in every layer/KV head. Crucially,
269/288 layer-heads have nonmonotonic logical-source order when read in native
physical-slot order (3,140 adjacent descents total). The controller required
the official software cache's prefill chunk rule—confirmed-eviction slots are
written before newly allocated slots within a chunk—to reproduce that state.
This identifies a necessary adapter metadata/order-preservation condition, not
a physical page-size or hardware-selection result.

### Official trained-DMS M4 active-resident attention manifest

`route-a-dms-m4-active-resident-attention-gate-1.0` is the functional gate
after accepted M3 topology. It binds M0--M3 and the hashed M3 control/topology
artifacts, then repeats one fixed official DMS request twice. The second pass
wraps the official cache update and `flash_attn_with_kvcache` only to observe
their unchanged inputs and return value. It gathers active native K/V in the
official logical-slot/block-table order and performs an in-memory one-source
FP32 online-softmax replay for every `q_len=1` decode call. K/V, queries,
attention outputs, token IDs, and text are never serialized.

Acceptance requires exact trace-off/on generated-token, per-forward logit, and
final native-cache digests; fresh native ring/controller agreement; complete
all-layer decode coverage; and declared FP32 numerical tolerance. M4 does not
replace official attention, create packed cold storage, establish source
splitting/merge placement, or prove order-invariance. Native observations are
trace-derived software state and the replay is bounded functional evidence;
neither is capacity, HBM/DRAM traffic, latency, throughput, energy, area,
quality, hardware, architecture, or RTL evidence.

The first accepted artifact is
`analysis/experiments/dms_route_a_m4_active_resident_attention_qwen3_8b_retrieval_01/`,
whose manifest SHA-256 is
`6e4dc1eda065f440800ee29c03f65ad59502cf95c84f2408dce7ce8e6485b028`.
It observes 144 decode calls (36 layers times four fixed decode forwards), all
within the declared FP32 `atol=rtol=0.03`; the recorded maximum absolute
difference is `0.0629558563` and the mean of per-call mean absolute differences
is `0.0003103976`. This tolerance result is a numerical functional guard, not
a statement that the maximum difference is a universal numerical bound. The
fresh 180-event topology replay also again matches native length/ring metadata,
with active resident lengths 513--629 and 269 nonmonotonic layer/KV-head slot
orders. It validates only the fixed-request native-resident source reference.

### Cross-frontend residency descriptor study (planned)

The post-M4 commonality phase is specified in
`analysis/cross_frontend_commonality_study_plan.md` and archived in
`analysis/cross_frontend_residency_evidence_archive_20260915.md`. Its v1
descriptor separates semantic identity/visibility/epoch/order fields from the
`persistent_packed`, `one_shot_packed`, and `dynamic_resident_slot` realization
extensions. Every descriptor value must explicitly distinguish `observed`,
`derived`, `modeled`, `unknown`, and `not_applicable`; unknown is never zero.

This study does not make DMS slots a packed-cold source, infer unobserved
SnapKV decode behavior, pool Qwen/Llama resource values, define a hardware
interface, select a parameter, or authorize RTL.

### Cross-frontend C0 evidence index

`cross-frontend-c0-evidence-index-1.0` is the no-model C0 entry gate for the
Commonality Study. It reads only the four completed JSON artifacts explicitly
named and SHA-256-bound by the 2026-09-15 archive: Qwen A4.2.14 core closure,
Qwen/Llama M6 coverage, SnapKV P2, and DMS M4. It requires each expected
schema/status/hash and stated semantic/claim-boundary guards. It rejects
SnapKV generated-token/decode state if changed from unavailable/null and
rejects DMS if native-source/no-attention-replacement guards drift.

C0 opens no trace/tensor payload, model, runtime, cache, or allocator state.
It writes only a new provenance index and establishes no descriptor field,
resource envelope, hardware interface/parameter, architecture specification,
or RTL claim.

The first accepted C0 output is
`analysis/experiments/cross_frontend_c0_evidence_index_01/cross_frontend_c0_evidence_index_report.json`,
with SHA-256
`8a7636c2cce353ae1ba6099abb19861694d8789a6b23c8063825aeb88a750cc4`.
All four completed artifacts are hash-bound to the archive; C0 records that no
raw trace/tensor payload, model/runtime, or hardware parameter was opened or
selected. It advances only the provenance index prerequisite for C1.

### Cross-frontend C1 semantic descriptor

`cross-frontend-c1-semantic-descriptor-1.0` is a no-model contract artifact,
not a raw trace schema or cache format. It hash-binds C0 and its four completed
source manifests, then defines `CrossFrontendResidencyDescriptor v1` at
`(model, layer, kv_head, epoch)` grain. Its typed core fields are
`model_topology`, `identity`, `epoch`, `decision`, `visibility`,
`position_provenance`, `traversal_order`, and `attention_binding`. Each value
uses exactly one of `observed`, `derived`, `modeled`, `unknown`, or
`not_applicable`; `unknown` and `not_applicable` require a literal reason and
are never encoded as zero.

`persistent_packed`, `one_shot_packed`, and `dynamic_resident_slot` are
realization extensions, not core schema fields. C1 preserves SnapKV generated
decode as unknown and preserves DMS arrival serial, unknown literal position,
and required native traversal order as distinct facts. It does not open raw
payloads or create a shared hardware/resource interface.

C1 normally consumes each literal C0-bound path. An explicit cross-host staging
path is permitted only when its SHA-256 exactly matches C0; both origin and
staging path are recorded. This is provenance transport only and never
authorizes replacing an existing artifact.

The accepted C1 artifact is
`analysis/experiments/cross_frontend_c1_semantic_descriptor_01/cross_frontend_c1_semantic_descriptor_report.json`
with SHA-256 `7b37e8f0945018f6b387085ea129f10758962dd987b4d8437cb243c7a45677a7`.
It records only typed availability over C0-bound evidence and selects no
hardware interface or parameter.

The hash-preserving remote replica is
`analysis/experiments/cross_frontend_c1_semantic_descriptor_remote_replica_01/cross_frontend_c1_semantic_descriptor_report.json`
(SHA-256 `58a1dda80511f4f580853b0aaa32c8aa82b77133db472b315ad2adb5f839f1d0`).
It is a cross-host provenance replica, not a second frontend measurement.

### Cross-frontend C2 realization adapters

`cross-frontend-c2-realization-adapters-1.0` is a no-model semantic-projection
artifact. It hash-binds C1 plus the four source manifests and emits exactly one
projection per realization extension: KVzap `persistent_packed`, SnapKV
`one_shot_packed`, and official DMS `dynamic_resident_slot`. Every projection
must preserve C1's eight core-field statuses, source provenance, and required
traversal order. An `unknown` or `not_applicable` core field must have a reason
and a null value; otherwise the gate rejects it as fabricated.

The accepted C2 artifact is
`analysis/experiments/cross_frontend_c2_realization_adapters_01/cross_frontend_c2_realization_adapters_report.json`
with SHA-256 `7e14af14250b0143b37a9462bea152ce67b44cd9d227e37ae88e31ea24f43acb`.
It is mapping/classification evidence only and defines neither allocator,
physical-capacity, traffic, timing, hardware interface, nor RTL evidence.

The matching remote replica is
`analysis/experiments/cross_frontend_c2_realization_adapters_remote_replica_01/cross_frontend_c2_realization_adapters_report.json`
(SHA-256 `3dd5e120438db7406f02482ba74b50afaf9c8048d5c43cc9228234919e70b568`).
It is a cross-host provenance replica only.

### Cross-frontend C3 commonality matrix

`cross-frontend-c3-commonality-matrix-1.0` is a no-model classification over a
completed C2 report. It records per-frontend typed field status, admits an
invariant candidate only when all of its prerequisite fields are observed in
all three projections, and emits separate frontend-specific and unresolved
lists. A candidate may state only an abstraction (such as preserving a required
frontend order); it never creates a common physical order or cache format.

The accepted C3 artifact is
`analysis/experiments/cross_frontend_c3_commonality_matrix_01/cross_frontend_c3_commonality_matrix_report.json`
with SHA-256 `6d9e16d618dc9d779db60d6a408b87c3257e3aa2e33394e4c4e425032607fea0`.
It retains DMS literal position and SnapKV generated decode/lifecycle as
unresolved and establishes no resource, hardware interface, or RTL evidence.

The matching remote replica is
`analysis/experiments/cross_frontend_c3_commonality_matrix_remote_replica_01/cross_frontend_c3_commonality_matrix_report.json`
(SHA-256 `74fc3eb42a3231904bc6762221c4ea41590c48813aa27b1267107560d8834a0f`).
It is cross-host provenance reproduction only.

### Cross-frontend C4 attention primitive study

`cross-frontend-c4-attention-primitive-study-1.0` is a no-model revalidation
of previously accepted functional comparator evidence. It binds completed C2
and C3 reports plus the KVzap core, SnapKV P2, and DMS M4 manifests. It records
one declared source-cardinality/order/comparator report per frontend; it does
not rerun attention. C4 requires a single source to remain sufficient for the
bounded SnapKV and DMS evidence, retains DMS native order, and permits optional
KVzap multi-source composition only for KVzap.

The accepted C4 artifact is
`analysis/experiments/cross_frontend_c4_attention_primitive_study_01/cross_frontend_c4_attention_primitive_study_report.json`
with SHA-256 `558f5a9c9c4c09c6ad9d4f4d4a562182be8e2841b10362f7b4cce6e0a158c715`.
It establishes no new attention execution, measurement, resource, hardware,
or RTL evidence.

The matching remote replica is
`analysis/experiments/cross_frontend_c4_attention_primitive_study_remote_replica_01/cross_frontend_c4_attention_primitive_study_report.json`
(SHA-256 `6808293d0e49e34c84db9e59058407049ec788d4ac3289661204b381a6310087`).
It is cross-host provenance reproduction only.

### Cross-frontend C5 hardware-direction decision

`cross-frontend-c5-hardware-direction-decision-1.0` is a no-model archival
decision memo over the hash-bound C0--C4 chain. It decides only the research
primary path and records the pre-RTL checklist; it cannot select a hardware
parameter, freeze an architecture specification, or authorize RTL. Its decision
rule keeps Route-A persistent-packed primary when C3/C4 establish only a
frontend-bound semantic traversal abstraction and retain frontend-specific
lifecycle/order/comparator differences.

The accepted C5 artifact is
`analysis/experiments/cross_frontend_c5_hardware_direction_decision_01/cross_frontend_c5_hardware_direction_decision_report.json`
with SHA-256 `f7f3aec661602e5ec8febb7a43418c16cdf3dfc27e84a808a084b737d3c06fff`.
It selects Route-A as research direction only; resource parameters, architecture
specification, and RTL remain unselected/unfrozen/unauthorized.

The matching remote `zsy_1` provenance replica is
`analysis/experiments/cross_frontend_c5_hardware_direction_decision_remote_replica_01/cross_frontend_c5_hardware_direction_decision_report.json`
with SHA-256 `1e45e60713ce6256df33c5efb06b5db93f1ecf6a630b9de7fb916b9d730868b3`.
It reproduces the complete remote C0--C4 evidence chain and does not add a
functional, modeled-resource, measured-hardware, or RTL claim.

### Route-A A4.3.0 resource-contract / workload-envelope / fallback gate

`kvzap-route-a43-resource-contract-envelope-fallback-1.0` is a no-model,
new-output-only pre-specification gate. It SHA-256 binds C5, A4200, A4201,
A4211, A4214, M6, A317, and A318. Its output separates the five unresolved
resource-contract parameters, six distinct fixed-horizon Qwen/Llama
model/workload descriptor rows, and the Full-KV zero-admission fallback
contract including the A318 breach boundary. It rejects pooled rows, parameter
selection, input drift, or a bypass that enters Route-A admission/cold state.
When a local and remote A4214 serialization differ, the supplied A4214 must
bind the supplied A4211 hash and must be one of M6's explicitly reconciled raw
hashes; this records provenance variants without treating different bytes as
identical.

The result is a provenance-bound functional/trace-derived and modeled-input
ledger only. It does not establish occupancy, FIFO depth, PTE encoding,
allocator behavior, bank/burst utilization, service timing, HBM traffic,
hardware latency/throughput, energy, area, architecture specification, or RTL.

### Route-A A4.3.1 policy-on pending-staging snapshot envelope

`kvzap-route-a431-policy-pending-staging-envelope-1.0` is a new-output-only,
no-model aggregation of exactly three accepted Qwen all-layer/all-KV-head
policy-on manifests: retrieval, summarization, and reasoning. Each must use
the paired online same-mask dense/replayed-mask Route-A control, budget one,
and a nonempty pending witness. It reports per-workload and per-layer/KV-head
pending-token comparison-snapshot maxima plus a three-workload observed range.

The values are functional/trace-derived attention-comparison snapshots. They
are not FIFO occupancy at arrival/completion, finite FIFO depth, overflow
observation, service rate, target capacity, or hardware performance evidence.
The policy-on backend retains its contiguous logical cache-position contract;
if a gate rejects a non-contiguous call, its failure-only diagnostic reports
only count, first/last positions, and the first scalar mismatch, never token
text or a full position vector. This diagnostic is not an accepted trace,
workload result, or hardware observation.
The A4.3.1 source manifests must additionally declare
`require_single_visible_cuda_device=true` and record `cuda_environment` with
exactly one visible CUDA device. This protects the Python semantic hook from
unsupported multi-device automatic dispatch. It is an execution-environment
guard, not a hardware performance or architecture result.
They use `kvzap-route-a40-policy-on-qwen-gate-1.5`, retain
`max_executed_dtype_ulps=16` in `record_only` mode with a 32-sample scalar
bound, and hard-enforce `quantization_aware_enforce` in addition to the FP32
same-mask guard. Both dense and Route-A sections serialize bounded per-layer
ULP-breach summaries. A recorded ULP breach is neither a strict ULP pass nor
permission to choose a wider merge datapath; failure of either hard close
guard rejects the source manifest.

### Route-A A4.3.2 policy-on lifecycle-transition trace

When `record_lifecycle_transitions=true`, schema
`kvzap-route-a40-policy-on-qwen-gate-1.6` includes
`a432_logical_lifecycle_transitions.jsonl.gz`, hash-bound from the manifest.
Each `kvzap-route-a432-logical-lifecycle-transitions-1.0` row is one scalar
Route-A state append with layer-local logical position range, phase, and
per-KV-head pre-maturity, post-maturity, and post-reference-service state.
The recorder verifies conservation of mature-kept, pending, admitted, and
packed tokens, and records no K/V, token text, timestamps, source-ready/
completion order, queue arrival, or hardware service interval. Trace-on must
match trace-off Route-A answer and original-mask decisions; this is functional
trace integrity, not FIFO sizing or hardware evidence.

### Route-A A4.3.3 conditional admission/staging envelope

`kvzap-route-a433-conditional-admission-staging-envelope-1.0` consumes exactly
three hash-checked A4.3.2 transition sources and first reproduces their
aggregate budget-one pending state per layer append. It then replays scalar
head-token arrivals under declared service quanta and conditional aggregate
pending thresholds. `Q` is an untimed count after each logical append, and
`C` is a comparison threshold; neither is a hardware rate, FIFO depth, SRAM
capacity, overflow observation, page-sealing result, or resource selection.

### Route-A A4.3.4 prefill micro-event lifecycle trace

Schema `kvzap-route-a40-policy-on-qwen-gate-1.7` records a default-off,
trace-on-only `prefill_maturity_chunk_tokens` value in its lifecycle descriptor.
Positive values split only the Route-A reference state's contiguous prefill
append into ordered micro-events under the same replayed original mask. The
trace must match the batch Route-A answer and mask decisions. This is a
functional granularity counterfactual, not a controller clock, service rate,
FIFO observation, page/bank/burst measurement, or hardware selection.

### Route-A A4.3.5 micro-event quantum sweep

`kvzap-route-a435-microevent-quantum-sweep-1.0` compares hash-bound chunk-64
functional sources at declared admission budgets 1, 8, and 32. It requires
per-workload batch Route-A answers to match across the sweep. Q is a reference
action count, not a hardware rate; pending/page state is not FIFO, HBM, or
physical-page evidence.

### Route-A A4.3.6 conditioned Llama micro-event quantum sweep

`kvzap-route-a436-llama31-microevent-gate-1.0` binds the completed Llama M0,
M1, and M5.1 fixed-continuation prerequisites, including M5.1's explicit
record-only ULP context. It records a full-KV bypass, online dense mask source,
trace-off Route-A replay, and trace-on chunk-64 Route-A replay for one Llama
workload at each Q in `{1,8,32}`. The trace-on path must consume the dense
mask stream and forced fixed token trajectory exactly once, preserve the
trace-off token digest, and contain scalar, layer-contiguous, timestamp-free
lifecycle events. `kvzap-route-a436-llama31-microevent-quantum-sweep-1.0`
accepts exactly the nine such sources, preserves workload rows separately, and
rejects cross-Q conditioned token-trajectory divergence. The fixed continuation
is not natural-generation evidence; record-only ULP context is not a strict
pass. Q and logical pending/page state do not define a hardware rate, FIFO,
physical page, HBM traffic, timing, capacity, or architecture parameter.

### Route-A A4.3.7 cross-anchor micro-event Q-sensitivity envelope

`kvzap-route-a437-cross-anchor-microevent-envelope-1.0` SHA-256 binds only a
completed Qwen A4.3.5 report and completed conditioned-Llama A4.3.6 report.
It requires each input to retain its three workload rows, Q=`{1,8,32}`, and
chunk-64 contract, and retains Llama's fixed continuation plus record-only ULP
context. It emits a direction matrix and Q=1-to-8/32 deltas *within each
model/workload row only*. It creates no cross-model average, min/max envelope,
common capacity/traffic range, or hardware parameter. These scalar logical
state summaries remain neither FIFO, physical-page, HBM, timing, nor hardware
evidence.

### Route-A A4.4.0 Full-KV-to-Route-A activation and benefit-bypass contract

`kvzap-route-a440-deferred-activation-contract-1.0` is a functional gate
conditioned on the completed Llama M0/M1/M5.1 provenance and M5.1's declared
eight-token non-EOS continuation.  For each of retrieval, summarization, and
reasoning it records two distinct deferred-policy branches: an
end-before-activation branch (`D=8`) that remains native Full KV through end,
and an activation branch (`D=1`) that transitions
`full_kv_bypass -> route_a_active` at an explicit q_len=1 commit boundary.

Before commit, the predictor decision journal is permitted but Route-A logical
hot/pending/packed records, admissions, logical pages, and logical page-table
entries must not exist.  At commit, the report records only scalar prefix
length, mature-kept/drop partition, hot/pending/packed split, one configured
reference admission action, and logical page/tail counts.  The native cache is
retained by the functional reference.  Post-commit lifecycle JSONL contains
only timestamp-free Route-A state transitions; it is hash-bound from the
report.  No row is allocator activity, DMA/HBM traffic, a burst observation,
physical capacity, FIFO occupancy/depth, service rate, PTE width, page/bank
mapping, merge precision/PE, scheduler/controller timing, latency, throughput,
energy, area, architecture specification, or RTL evidence.  The two model
anchors remain separate; this Llama gate creates no common hardware envelope.

### Route-A A4.4.1 Qwen activation and benefit-bypass contract

`kvzap-route-a441-qwen-deferred-activation-contract-1.0` is the independently
conditioned Qwen counterpart to A4.4.0.  It hash-binds the frozen Qwen Gate-A
manifest/mask and the completed A4.3.5 Qwen report, requires exactly one
visible CUDA device, and runs retrieval, summarization, and reasoning under a
declared fixed eight-token non-EOS continuation.  `D=8` must remain pure native
Full KV through end; `D=1` must commit exactly once from Full-KV history to
logical Route-A state.  It retains Qwen's existing quantization-aware hard
executed-dtype close envelope plus record-only ULP diagnostics.

Its report and post-commit traces retain only scalar lifecycle state and
logical page metadata.  They are functional/trace-derived evidence, not
natural-output, quality, allocator, physical-capacity, HBM, DMA, burst,
FIFO/service, timing, throughput, energy, area, hardware-parameter, or RTL
evidence.  Qwen and Llama A4.4 rows must remain separate until a later
no-model cross-anchor contract report verifies shared *semantics* without
numeric pooling.

### Route-A A4.4.2 no-model cross-anchor activation-contract closeout

`kvzap-route-a442-cross-anchor-activation-contract-1.0` accepts only a
completed Qwen A4.4.1 report and completed Llama A4.4.0 report.  It SHA-256
binds each report and every referenced post-commit gzip trace, verifies the
three workloads independently for pure `D=8` Full-KV bypass, `D=1` one-commit
activation, absent pre-commit Route-A logical state, retained native cache,
positive post-commit same-mask guard work, and timestamp-free one-token decode
trace rows.  It retains six separate anchor/workload rows and a boolean
semantic-invariant matrix only.

It has no cross-anchor mean, min/max, normalization, common capacity/traffic
envelope, or parameter derivation.  The logical activation totals remain
per-anchor reference accounting, not FIFO/PTE/page/bank/burst/merge/scheduler
resources, physical capacity, allocator/HBM/DMA observations, timing,
throughput, energy, area, architecture specification, or RTL evidence.

### Route-A A4.5.0 logical capacity-protection boundary replay

`kvzap-route-a450-capacity-protection-boundary-replay-1.0` consumes only
hash-validated A4.4.1/A4.4.0 reports and their post-commit logical traces. It
sweeps declared positive integer pending high-watermarks over the maximum
per-selected-layer aggregate pending state. At the activation boundary or a
later pre-append logical boundary, a crossing moves the *counterfactual*
request mode one-way from `route_a_active` to `protected_full_kv`: later
Route-A logical admissions and drops are disabled, re-entry is disallowed, and
the retained native Full-KV cache is the fallback authority.

The high-watermarks are sensitivity labels only; they are not observed FIFO
depths, capacities, overflows, service rates, physical resource sizes, or
hardware selections. The scalar replay cannot prove a real controller avoids
within-append transients, performs a native attention switch, or preserves
model outputs. It records no transfer, HBM/DMA traffic, allocation, timing,
latency, throughput, energy, area, architecture specification, or RTL result.

### Route-A A4.5.1 model-on layer-local capacity-protection semantic gate

`kvzap-route-a451-capacity-protection-semantic-gate-1.0` hash-binds one
completed anchor-specific A4.4 activation report and the completed A4.5.0
replay before model load. For each fixed continuation workload it uses the
declared `C=1024` logical pending witness to exercise a one-way, **layer-local**
`route_a_active -> protected_full_kv` transition. After hydration from retained
native Full-KV history, a layer whose aggregate pending tokens across KV heads
reaches `C` freezes its Route-A state, clears the current captured mask, and
uses native attention for current and later calls. The report retains scalar
transition state, frozen logical position, native-call count, and whether
other layers remain Route-A active; journals must remain contiguous.

This is an executable attention-hook primitive, not A4.5.0's request-global
controller replay. It proves neither controller look-ahead/synchronization nor
prevention of a within-append transient. `C=1024` is a logical probe, not FIFO
depth/capacity, overflow observation, service rate, or hardware choice. Forced
Full-KV tokens establish bounded functional inputs only. No field is
natural-generation/quality, allocator/reclamation, physical capacity, HBM/DMA
traffic, burst, timing, latency, throughput, energy, area, architecture-spec,
or RTL evidence. Qwen and Llama reports remain separate and cannot be pooled.
The runner declares its cached model/predictor artifact requirement before
importing Transformers/huggingface_hub: it may not issue an incidental Hub
metadata request. A missing local artifact is a blocked provenance/runtime
condition, not a reason to substitute a model, revision, or network result.

### Route-A A4.5.2 request-global controller reconciliation

`kvzap-route-a452-global-protection-controller-reconciliation-1.0` is a
no-model, hash-bound reconciliation of completed A4.4 activation reports,
the A4.5.0 `C=1024` request-global counterfactual, and completed A4.5.1
layer-local functional reports. For every anchor/workload row, it requires the
actual A4.5.1 protected-layer set to equal the A4.4 per-layer aggregate-pending
set at or above `C=1024`, including activation-boundary native fallback and
frozen-state guards.

It then declares a non-retroactive controller contract: the first triggering
layer-complete activation observation latches request-global protection, but
layers already completed in that activation epoch cannot be rerouted; the first
all-layer request-global effect boundary is the following decode epoch. This
is neither a model-on global-controller implementation nor a measured delay,
barrier, broadcast, cycle, or timing result. `C=1024` remains a logical probe,
not a FIFO capacity/service parameter. The report contains no physical
capacity, traffic, burst, performance, energy, area, architecture, or RTL
claim, and preserves Qwen/Llama rows without numeric pooling.

### Route-A A4.5.3 model-on next-epoch request-global protection semantic gate

`kvzap-route-a453-global-next-epoch-protection-gate-1.0` is a model-on,
anchor-specific functional report. It hash-binds the completed A4.5.2
reconciliation report and its completed A4.5.1 inputs before model loading.
For each fixed-continuation workload, `controller` records the ordered
post-hydration/pre-append activation observations, first threshold latch, and
the only permitted request-global effect position: the next `q_len=1` decode
epoch after every layer completed the activation epoch. Per-layer rows retain
the local A4.5.1 event (if any), the global next-epoch event, native fallback
call counts, and frozen Route-A logical state positions.

The first threshold observation is a latch, not permission to rewrite layers
already completed in the activation epoch. A local crossing may take its
existing current-epoch layer-local fallback; all layers take request-global
native Full-KV fallback only at the committed next epoch. Reports reject an
early/non-uniform action, re-entry, source-set inconsistency, input mutation, or
Route-A state mutation after freezing. `C=1024` is a logical sensitivity probe,
not a FIFO occupancy/capacity, service rate, overflow, or hardware parameter.
This schema records no controller delay/broadcast timing, physical allocation,
HBM/DMA traffic, bursts, latency, throughput, energy, area, architecture
specification, or RTL evidence. Qwen and Llama rows remain separate.

### Route-A A4.5.4 protected Route-A shadow-state disposition semantic gate

`kvzap-route-a454-protected-shadow-state-reclamation-gate-1.0` is a model-on,
anchor-specific functional report hash-bound to a completed A4.5.3 report and
its A4.5.2/A4.5.1 source chain. At the existing next-decode-epoch request-global
fallback boundary, each layer records `logical_inventory_before_tombstone`:
per-KV-head and total hot/pending/packed token counts plus logical packed-page
counts. It then marks Route-A shadow state non-authoritative and replaces it
with an access-failing tombstone; native Full-KV remains the sole authority.

Every later bounded continuation call must use native attention without a
Route-A shadow read, append, admission, drop, re-entry, or native-cache
mutation. The report rejects an inventory/head-total mismatch, a changed global
boundary or local trigger set, absent tombstone, or non-identical forced
Full-KV token input. `route_a_shadow_logically_marked_reclaimable=true` means
only that the functional reference no longer permits Route-A shadow access. It
is explicitly not a Python allocator/free observation, allocated bytes,
physical-page release, HBM/DMA traffic, burst, FIFO capacity/service/overflow,
controller timing, latency, throughput, energy, area, architecture
specification, or RTL evidence. Qwen and Llama remain separate.

### Route-A A4.6.0 Route-A-active long-horizon steady-state gate

`kvzap-route-a460-route-a-active-steady-state-gate-1.0` hash-binds completed
A4.4.2 activation-contract evidence and records a model-on, fixed 64-token
continuation after a `D=1` Full-KV-to-Route-A commit. The active branch must
remain `route_a_active`; its Full-KV run exists only to provide fixed token
inputs and must not become a fallback or backing path. Per workload it stores
the timestamp-free post-commit lifecycle trace and an untimed final-32-decode
append-opportunity analysis of sustained non-decreasing pending-growth witnesses.

The trace's hot/pending/packed/page fields and tail witness are functional
logical state, not an observed queue, arrival/service rate, FIFO occupancy,
capacity, overflow, physical allocation, bytes, HBM/DMA traffic, burst, timing,
latency, throughput, energy, area, architecture specification, or RTL evidence.
The finite horizon cannot prove indefinite stability or select hardware
parameters. Qwen and Llama rows remain separate.

### Route-A A4.6.1 activation-burst logical envelope

`kvzap-route-a461-activation-burst-logical-envelope-1.0` is a no-model,
hash-bound analysis of completed A4.4.2 and anchor-specific A4.6.0 reports.
For every retained anchor/workload row it records two deliberately separate
timestamp-free logical sources: the all-layer/all-KV-head activation-commit
inventory (`matured_*`, pending, admitted, hot, packed, and logical pages) and
the subsequent `q_len=1` append-event inventory (`matured_*`, admission,
pending, and packed state). It verifies report/trace SHA-256 bindings,
complete layer/head coverage, and per-event pending/packed conservation before
emitting integer distribution summaries.

These are trace-derived/functional logical workload inputs for a later resource
model, not observed physical bursts or a service timeline. They do not state
FIFO occupancy/capacity, service rate, overflow, allocation/capacity, bytes,
HBM/DMA traffic, page/PTE/bank requirements, timing, latency, throughput,
energy, area, architecture specification, or RTL. Qwen and Llama rows cannot
be pooled, range-reduced, or used to select hardware parameters.

### Route-A A4.6.2 multi-horizon logical service envelope

`kvzap-route-a462-activation-logical-service-envelope-1.0` is a no-model,
hash-bound sensitivity model over completed A4.4.2, Qwen/Llama A4.6.0, and
A4.6.1 inputs. For each anchor/workload separately it initializes every
`(layer, KV-head)` backlog from activation-commit pending state and replays only
the post-commit `matured_kept_tokens` arrival sequence. Recorded A4.6.1
admission actions are explicitly not reused as a service-rate input. It finds
the minimum logical quantum that drains each bounded prefix at horizons
`{1,2,4,8,16,32,62}` append opportunities, and records per-head maximum/final
backlog, service grant, drain opportunity, reaccumulation, and per-layer
fairness spreads.

Independent per-stream quantum is an optimistic no-competition bound. The
second policy shares one quantum within each layer and assigns individual
logical tokens round-robin among nonempty KV heads; it is a declared contention
sensitivity, not a hardware scheduler. A quantum is only an abstract
tokens-per-logical-append-opportunity variable. It is not cycles, service rate,
FIFO capacity/depth, bandwidth, physical burst/traffic, HBM/DMA activity, or a
page/bank/PTE/merge/PE resource selection. The bounded model is an input to
later physicalization-cost and attention/admission-contention DSE; Qwen/Llama
rows remain separate and no hardware parameter or RTL result follows.

### Route-A A4.6.3.0 physicalization mapping contract

`kvzap-route-a4630-physicalization-mapping-contract-1.0` hash-binds the
completed A4.4.2/A4.6.0/A4.6.1/A4.6.2 chain and replays each A4.6.2 per-head
candidate to check its granted/final-pending state. It records physicalization
work only under named assumptions: `eager_copy_on_logical_service` maps one
logical service token to one abstract source-read and packed-write token unit;
`sealed_page_copy_with_unsealed_tail_reference` maps payload work only for
newly sealed candidate pages and retains an explicit unsealed-tail reference.
For page-token sensitivity `{16,64,128}`, each variant records page allocation,
seal, tail, PTE, position-metadata, and post-service dual-source merge-state
records per head.

No lifecycle transition is automatically a transfer. These are modeled
token-unit/record inventories, not measured KV reads/writes, bytes,
transactions, HBM/DMA traffic, bandwidth, timing, or hardware resource use.
Neither mapping nor page sensitivity point is selected. A later A4.6.3.1 may
place this explicit inventory beside continuous attention work in a separate
abstract contention model; this mapping report does not do so.

### Route-A A4.6.3.1 aggregate attention/admission contention envelope

`kvzap-route-a4631-aggregate-attention-admission-contention-1.0` consumes all
A4.6.3.0 mapping variants and the hash-bound A4.6.1 source traversal inventory.
It keeps attention traversal/merge work separate from admission physicalization
work, under named abstract cost profiles, and compares admission-isolated,
attention-first, and reserved-admission-share aggregate requirements. These are
bounded-horizon abstract work units, not temporal arbitration, traffic, cycles,
bandwidth, FIFO, or hardware-resource results. No mapping/page/cost/share is
selected and A4.6.2 per-head deadline/fairness is inherited rather than
recomputed under a temporal fabric.

### Route-A A4.6.3.2 temporal abstract contention replay

`kvzap-route-a4632-temporal-abstract-contention-replay-1.0` hash-binds the
complete A4.6.1 activation/append source and A4.6.3.0 mapping report. It keeps
the Qwen and Llama anchor/workload rows separate and, for every retained
layer-shared mapping point at horizons `{8,16,32,62}`, stores epoch records with
`A_t_attn_source_traversal_token_units`, `A_t_new_mature_kept_logical_tokens`,
`B_t_before_arrivals_logical_tokens`, `B_t_after_arrivals_logical_tokens`,
`G_t_logical_admission_grant`, and `B_t_plus_1_after_grant_logical_tokens`.
The final field records the explicit logical recurrence
`B[t+1]=max(0,B[t]+A_new[t]-G[t])`.

Each policy result provides `B_max`, `B_max_h`, per-head final backlog and
terminal drain/censoring, deadline misses, per-layer fairness, hard-reservation
idle capacity, work-conserving attention borrowing, and grant-mapped payload,
position, PTE, page-seal, merge, and tail-reference inventories. Mapping work
uses only the named eager-copy or sealed-page-copy-with-tail-reference
assumption. A dual-source merge record is emitted once per head after all grants
in an append opportunity, never once per individual token grant. It is emitted
as separate attention-side work, including when `G_t` is zero, rather than as
admission-occupied work. It is a timestamp-free modeled inventory, never measured KV
traffic, bytes, HBM/DMA work, cycles, bandwidth, latency, throughput, energy,
area, FIFO capacity, or hardware scheduler behavior. No policy, mapping, page
size, reservation, or resource parameter is selected.

### Route-A A4.6.4 causal elastic-admission contract

`kvzap-route-a464-causal-elastic-admission-contract-1.0` hash-binds the valid
A4.6.1/A4.6.3.0/A4.6.3.2 chain and emits three same-level policy replays:
minimum-only work-conserving, `causal_counter_hysteresis_v1`, and a
clairvoyant same-level offline reference.  Each epoch records the normal
`A_t`, `B_t`, `G_t` recurrence plus per-layer observable controller inputs:
`B_layer`, `B_max_h`, `Age_max`, current mature-kept arrival, selected level,
actual grant, and transition.

The causal policy receives neither later arrivals, evaluation horizon, anchor
or workload identity, nor A4.6.2's trace-derived optimal quantum.  It uses the
fixed global logical ladder `{16,64,256}` and declared counter hysteresis;
prefix-causality is a required test.  Per-head age/backlog/deadline/fairness,
level occupancy, transitions, mapped admission work, and separate dual-source
merge work are modeled logical/token-unit/record evidence only.  They are not
hardware service rates, cycles, traffic, bytes, HBM/DMA activity, bandwidth,
FIFO depth, timing, latency, throughput, energy, area, or hardware selection.
Within a layer, round-robin grants cannot exceed each head's current pending
cohort; over-service is an invalid replay.

### Route-A A4.6.5 observer-only causal capacity envelope

`kvzap-route-a465-causal-capacity-envelope-1.0` hash-binds A4.6.1, A4.6.3.0,
and the completed A4.6.4 causal report.  For each horizon it verifies that an
independent replay reproduces A4.6.4 backlog/grant/drain state, then records
head-local and layer-shared cap observers over pending immediately after arrival
and before grant.  Each cap point contains first breach, breach count, peak
excess, consecutive duration, and affected streams; it cannot alter controller
inputs/state, grants, admission, DROP, fallback, backing, or protection.

Per-layer service-shortage records include `Age_max`, high-level saturation with
residual post-grant backlog, saturation duration, positive-debt run, and peak
debt.  The logical cap grids and these pressure descriptors are not FIFO depth,
physical capacity, buffer organization, bytes, HBM/DMA traffic, cycles,
bandwidth, timing, latency, throughput, energy, area, scheduler selection, or
hardware parameters.

### Route-A A4.6.6 equal-budget pending-organization contract

`kvzap-route-a466-pending-organization-contract-1.0` hash-binds the complete
A4.6.1/A4.6.3.0/A4.6.4/A4.6.5 chain.  It independently reproduces the fixed
A4.6.4 causal replay and validates the resulting `B_max`, terminal state, drain,
and per-head tails against both A4.6.4 and A4.6.5 before any organization
observer runs.  The input at each opportunity is only the same post-arrival,
pre-grant pending vector already produced by that replay.

For an identical per-layer logical budget `C`, it compares equal-quota
head-local capacity, one layer-shared pool, and hierarchical `N_head*q +
C_overflow = C` ownership.  The hierarchical private-quota fraction sweep is
global, and all sampled `C` values use one globally pre-registered grid that
preserves integral quarter-quota splits across observed head counts.  It reports equal-budget
breach/excess/duration and private-reservation stranding, plus zero-breach
`Cmin` and named bounded-breach logical sensitivity frontiers.

These rows neither allocate storage nor assign individual overflow entries.
They cannot alter an A4.6.4 grant, controller state, arrival, per-head order,
admission, DROP/fallback/backing state, or lifecycle.  `C`, quota, overflow,
stranding, and `Cmin` are logical observer quantities only: not FIFO depth,
physical capacity, descriptor/PTE format, allocator behavior, ports, banking,
bytes, HBM/DMA traffic, cycles, bandwidth, timing, latency, throughput, energy,
area, protection policy, hardware selection, architecture specification, or RTL
evidence.

### Route-A A4.6.7.0 immutable pending-ownership semantic reference

`kvzap-route-a4670-pending-ownership-reference-1.0` hash-binds the complete
A4.6.1/A4.6.3.0/A4.6.4/A4.6.5/A4.6.6 chain.  It derives per-head grants from
the already validated A4.6.4 state trajectory rather than re-running a
scheduler, then verifies aggregate and per-head pending state against all three
predecessors at every horizon.

Each pending entry has immutable `(birth_opportunity, within_head_sequence,
source_at_enqueue)` identity.  Head-local assigns private source, layer-shared
assigns shared source, and hierarchical assigns private until its declared
per-head quota then shared overflow.  Source residence cannot change.  Every
dequeue compares private/shared fronts and must consume the canonical oldest
entry for that head; any source-age inversion, altered grant, or migration is
an invalid run.  q=0 and a per-row large-quota semantic endpoint must recover
the layer-shared and head-local traces respectively.

The report records a separate activation enqueue/residency summary and append-
opportunity enqueue/dequeue/release, active span/source, oldest-source
comparison, and cross-source-switch summaries.  It retains a hash-bound
per-head semantic summary after every individual head has been validated in
memory; activation must never be silently omitted from concurrency inventory.
It has no finite capacity, allocator, spill, compaction, descriptor format,
PTE, physical port/bank, byte, HBM/DMA, cycle, timing, throughput, energy,
area, protection, hardware selection, architecture specification, or RTL
meaning.  A4.6.6 `Cmin` values are context only, never allocated state.

### Route-A A4.6.7.1 unweighted organization-management exposure versus capacity recovery

`kvzap-route-a4671-pending-organization-tax-recovery-contract-1.0` hash-binds
the completed A4.6.6 organization frontier and repaired A4.6.7.0 ownership
reference, while retaining their A4.6.1/A4.6.3.0/A4.6.4/A4.6.5 provenance
hashes.  It reuses the already fixed causal grants and exact per-head FIFO
reference; it cannot reschedule admission or invoke finite-capacity behavior.

Each `organization_tax_capacity_rows` item contains: (1) the named
organization's A4.6.6 `Cmin` recovery relative to head-local in logical tokens
per layer and logical token-layers; (2) separate logical source-affiliation
creation/release, cross-source selection, concurrency, and unit-conservation
inventories; and (3) unweighted exposure ratios that use a named logical event
count as denominator.  `horizon_completion_state` is `drained` only when the
fixed causal backlog is zero; otherwise it is `prefix_censored_pending_remains`.

Logical source-affiliation segments are candidate bookkeeping records only, not
physical descriptors or PTEs.  Creation/release/comparison/switch/span fields
are not descriptor width, metadata bytes, accesses, ports, banks, bank
conflicts, HBM/DMA traffic, cycles, timing, latency, throughput, energy, area,
FIFO depth, physical capacity, or hardware cost.  The ratios assign no equal
cost weight to heterogeneous primitives and select no organization or hardware
parameter.  This schema contains no allocator, spill, migration, compaction,
DROP, fallback, Full-KV backing, protection policy, physical mapping,
architecture specification, or RTL result.

### Route-A A4.6.8.0 birth-ordered span representation sufficiency

`kvzap-route-a4680-pending-representation-sufficiency-1.0` hash-binds A4.6.1,
A4.6.4, A4.6.7.0, and the authoritative A4.6.7.1 report.  It derives the fixed
per-head grant trajectory from A4.6.4 and replays the immutable A4.6.7.0 source
assignment with `birth_ordered_source_span_v1`: private/shared source queues of
`(source, birth_opportunity, within_head_sequence_start, count)` spans.

For every ownership variant and horizon, `representation_sufficiency_gate`
records successful reconstruction of current pending state, exact birth/order,
unique oldest entry, source ownership, and fixed dequeue chunks at activation,
append, and dequeue checkpoints.  The span creation/release inventory must
match A4.6.7.0 and A4.6.7.1.  A source-total-only negative control is explicitly
rejected because it cannot order older shared work ahead of newer private work.

The representation is a logical semantic candidate, not a physical descriptor
or PTE.  Per-token reference units, span counts, and logical entries/span are
not metadata bytes, payload movement, accesses, ports, banks, traffic,
HBM/DMA, cycles, timing, latency, throughput, energy, area, physical capacity,
hardware selection, architecture specification, or RTL evidence.  No finite
allocator, migration, spill, compaction, DROP, fallback, Full-KV backing,
protection action, or banking/port model is present.

### Route-A A4.6.8.1 representation-aware access contract

`kvzap-route-a4681-representation-access-contract-1.0` hash-binds the A4.6.1,
A4.6.4, A4.6.7.0, A4.6.7.1, and A4.6.8.0 reports.  The latter is a mandatory
representation-sufficiency gate.  The schema replays the same fixed grants and
source assignment with `birth_ordered_source_span_v1`, checking after
activation, every append, and every dequeue that pending membership, exact
birth order, unique oldest entry, source ownership, and source/count dequeue
chunks reconstruct A4.6.7.0 canonical FIFO exactly.

For every ownership variant and horizon, `hardware_agnostic_access_pressure`
separates activation, steady-state append, and steady-state dequeue primitive
counts.  Declared lifecycle primitives are `span_create`, `tail_extension`,
`span_partial_dequeue`, and `span_release`; declared metadata primitives include
source-head observation, two-source oldest comparison, remaining/head update,
and ownership link/unlink.  Tail extension is legal only for same-source,
same-birth, sequence-contiguous work and is explicitly rejected across a birth
boundary.  `payload_reference_create/release` records association lifetime only,
not payload movement.  The schema also reports per-layer/opportunity primitive
and cross-source-selection peaks, active-span/source concurrency, and release
patterns.

All operations are hardware-agnostic logical primitives.  They are not
physical accesses, descriptor/PTE widths, payload reads/writes/copies, bytes,
HBM/DMA traffic, bandwidth, ports, banks, conflicts, cycles, timing, latency,
throughput, energy, area, capacity, hardware selection, architecture
specification, or RTL evidence.  No allocator, finite capacity, migration,
spill, compaction, DROP, fallback, Full-KV backing, protection, scheduler, or
physical storage mapping is modeled.

### Route-A A4.6.8.2.1 metadata-organization sensitivity report

`kvzap-route-a46821-metadata-organization-sensitivity-1.0` consumes and
hash-validates finalized `kvzap-route-a4682-access-epoch-trace-record-1.0`; it
does not create a lifecycle trace. `sensitivity_rows` retain anchor/workload/
horizon/organization plus `metadata_bucket_mapping`,
`abstract_bucket_count_per_layer`, and
`abstract_service_units_per_bucket_per_logical_checkpoint`.

`span_identity_striped_v1` and `head_source_affine_v1` are replaceable logical
projections, not physical bank mappings. Classes are source-head read, source
compare, mutable-head update, release update, and creation/ownership link.
Payload-reference events are counted but excluded. Each phase/all-phase summary
reports nonzero demand, same-epoch shortfall, class shares, class-isolated
shortfall, and leave-one-out relief; shortfall cannot alter FIFO/grants.

No field is a physical access, descriptor/PTE width, payload movement, bytes,
HBM/DMA traffic, port, bank, conflict, cycle, timing, latency, throughput,
energy, area, physical capacity, hardware parameter, architecture spec, or RTL.

### Route-A A4.6.8.2.2.0 strict metadata-recordization report

`kvzap-route-a468220-metadata-recordization-1.0` hash-binds the finalized
A4.6.8.2.0 event report/trace and A4.6.8.2.1 report. Its
`a468220_record_access_trace.jsonl.gz` uses
`kvzap-route-a468220-record-access-record-1.0` and records a logical record
type/identity, access kind, primitive sequence, and conservative/strict merged
operation count. The only strict merge sequence is adjacent partial-dequeue plus
remaining-update on an identical span record and ordered context.

`record_operation_curves` and per-context phase curves distinguish the
conservative primitive-granularity upper curve from the strict same-record
curve. Payload-reference events are counted separately and excluded. Logical
record identities have no descriptor fields, physical layout, width, address,
bytes, payload movement, HBM/DMA traffic, bank, port, cycle, timing, latency,
throughput, energy, area, capacity, or RTL meaning.

### Route-A A4.6.8.2.2.1 record-aware organization sensitivity report

`kvzap-route-a468221-record-organization-sensitivity-1.0` hash-binds the
A4.6.8.2.1 report and finalized A4.6.8.2.2.0 report/record trace.
`sensitivity_rows` retain the fixed context and add `record_curve`,
`record_bucket_mapping`, abstract bucket count, and abstract issue units.

Each row separates control, span, ownership, and same-record RMW demand;
reports P95/P99/max, non-propagating shortfall, RMW serialization sensitivity,
per-head skew, contiguous logical-checkpoint hot runs, and phase/checkpoint/
head bucket fanout. Mapping and issue units are abstract sensitivity labels,
not physical banking/port/timing parameters. No row denotes physical accesses,
bytes, payload traffic, HBM/DMA, cycles, latency, throughput, energy, area,
capacity, or an architecture/RTL choice.

### Route-A A4.6.8.2.0 access-epoch trace and span-lifetime closure

`kvzap-route-a4682-access-epoch-trace-1.0` hash-binds A4.6.1, A4.6.4,
A4.6.7.0, A4.6.7.1, A4.6.8.0, and the completed A4.6.8.1 access-contract
report.  `a4682_access_epoch_trace.jsonl.gz` uses
`kvzap-route-a4682-access-epoch-trace-record-1.0`; every record contains only
the prior logical primitive and its phase, opportunity, layer, KV head, source,
and span identity.  It does not contain token text, K/V payload, physical
addresses, widths, or bytes.

The logical checkpoint convention is activation=0, append(t)=2t-1, and
dequeue(t)=2t.  `span_lifetime` separates completed from right-censored spans,
and reports lifetime checkpoint/opportunity distance plus active-span residence
checkpoint distributions, including per-source breakdown.  A right-censored
span remains active at the fixed horizon and is observationally ended at the
final dequeue checkpoint.  `phase_separated_active_span_occupancy` reports
global/per-layer peaks and exact-max contiguous plateau duration.

These are ordered functional replay indices and logical occupancy statistics,
not hardware time, cache residency time, physical accesses, descriptor/PTE
widths, payload movement, bytes, HBM/DMA traffic, ports, banks, cycles, timing,
latency, throughput, energy, area, capacity, hardware selection, architecture
specification, or RTL evidence.  No allocator, finite capacity, migration,
spill, compaction, DROP, fallback, Full-KV backing, protection, scheduler, or
physical metadata mapping is present.

### Route-A A4.7.0 metadata-access concurrency contract

`kvzap-route-a470-metadata-access-concurrency-1.0` consumes and hash-validates
the finalized A4.6.8.2.2.0 record trace plus the A4.6.8.2.2.1 observer report.
It does not emit a new lifecycle trace or alter its fixed event order. For each
anchor/workload/horizon/organization, record curve, abstract mapping, bucket
count, and phase, `dependency_rows` reports weighted logical total record work,
longest-path critical work, and `1 - critical_path_work / total_record_work`.

The only preregistered direct dependency labels are `same-record`,
`same-head-control`, `span-lifecycle`, and `ownership-order`.  The report also
contains their counts, checkpoint distributions (P50/P95/P99/max), contiguous
dependency-bearing logical-checkpoint runs, per-head skew, and logical
cross-bucket fanout.  Activation, steady-state append, and steady-state dequeue
are phase-induced analyses: edges from another phase are not silently carried
into a phase result.

Critical-path and parallel-work values are logical graph accounting, not an
instruction schedule, measured runtime, hardware parallelism, bank/port
requirement, cycles, timing, latency, throughput, traffic, bytes, capacity,
energy, area, architecture specification, or RTL evidence.  No record
reordering, merge, FIFO/source/grant change, scheduler, protection, or payload
movement is modeled.

The corrected `_02` result uses schema
`kvzap-route-a470-metadata-access-concurrency-1.1`.  In addition to weighted
critical work, it records deterministic maximum-work path node count, edge
count, and edge-type composition.  Ties prefer more nodes and then the earlier
predecessor, so a path length is reproducible without becoming a schedule.
Per-checkpoint critical-work/total-work fractions and their complements include
`min`, `P1`, `P5`, `P50`, `P95`, `P99`, and `max`; this prevents high parallel
percentiles from hiding a small set of bad checkpoints.  The former `_01`
schema lacks these contract-completion fields and is not the authority for
chain-length or low-tail-ratio conclusions.

### Route-A A4.7.1 semantic metadata-transaction contract

`kvzap-route-a471-metadata-transaction-contract-1.0` consumes and hash-binds
the finalized A4.6.8.2.2.0 record trace and A4.7.0 `_02` report.
`a471_metadata_transaction_trace.jsonl.gz` uses
`kvzap-route-a471-metadata-transaction-record-1.0`. Each row maps fixed
dependency-record nodes to one declared semantic transaction group, carrying
`read_set`, `write_set`, `rmw_set`, `release_set`, deduplicated
`touched_records`, and exactly one commit/linearization boundary.

`admission_create`, `dequeue_nonterminal`, and `dequeue_terminal` are the only
observed group types. `tail_extension_reserved_zero_observed` remains a defined
contract type with observed count zero; no synthetic tail event may be added.
Phase summaries and A4.7.0 critical-path expansion rows report dependency
nodes, transaction groups, and touched-record instances separately. Negative
controls expose an unowned pending span after split admission and a stale
owner/frontier after split terminal release.

Semantic atomicity only prevents observation of a partial logical state. It is
not an SRAM atomic, physical transaction, access, port/bank request, cycle,
byte, HBM/DMA movement, timing, latency, throughput, energy, area, capacity,
architecture specification, or RTL evidence.

### Route-A A4.7.2.0 metadata-storage sufficiency report

`kvzap-route-a4720-metadata-storage-sufficiency-1.0` hash-binds A4.6.8.2.0,
A4.6.8.2.2.0, A4.7.0 `_02`, and A4.7.1 report/transaction-trace inputs. It is
the final semantic storage closure: the fixed four semantic records map to
declared modeled storage objects while A4.7.1 read/write/RMW/release sets and
commit boundaries remain unchanged.

`width_sufficiency_rows` explicitly records scope (`per_head`, `per_layer`, or
`global`), trace-distinct versus reuse-after-terminal-commit namespace policy,
reserved invalid encoding, generation bits, slack, field widths, semantic
record widths, modeled storage-object widths, right-censored live descriptors,
and overflow guards. `layout_mapping_rows` separately preserves semantic record
count and reports only modeled storage-object fanout for full separation,
span/ownership co-location, control co-location, and both co-locations.

A semantic record, modeled storage object, and physical entry are distinct:
co-location maps multiple semantic records to one modeled object; it neither
deletes semantic state nor selects a physical entry or allocator. Metadata bits
are modeled field accounting only. A4.7.2.0 contains no bank mapping, service
capability, scheduler, contention, access, SRAM/HBM transaction, cycle,
latency, throughput, energy, area, architecture specification, or RTL claim.

### Route-A A4.7.2.1 metadata physicalization sensitivity report

`kvzap-route-a4721-metadata-physical-dse-1.1` hash-binds A4.7.0 `_02`,
A4.7.1, and A4.7.2.0. It replays the immutable A4.7.1 transaction trace and
maps only A4.7.2.0-sufficient semantic layouts to modeled storage-object
operations. The report separates static field/footprint profiles after a
declared monotonic width-slack filter, per-logical-checkpoint modeled R/W/RMW
demand under predeclared bank-count/mapping sensitivities, object/bank commit
fanout, and independent-class versus unified-total abstract service shortfall.

Each transaction retains its A4.7.1 order and commit boundary. Co-location may
lower records only inside one existing transaction to one modeled object
operation; it never merges transactions or makes a hardware atomic operation.
A4.7.0 intrinsic dependency remains predecessor evidence and is not attributed
to modeled bank contention.

Bank labels, modeled object-operation demand, logical-checkpoint service quanta,
shortfall, and fanout are sensitivity values only. They are not physical bank or
port choices, hardware accesses, SRAM/HBM transactions, cycles, timing,
bandwidth, latency, throughput, energy, area, architecture specification, or RTL
evidence.

Schema `1.1`, preserved in `_02`, additionally
reports a conservative cross-context joint-safe modeled footprint: maximum field
widths and maximum modeled object counts are combined before bit accounting,
rather than treating a per-context maximum as a fixed-candidate bound. It also
records per-bank, per-phase maximum consecutive saturated
*logical-checkpoint* runs for each abstract service interpretation. Checkpoint
adjacency is numerical only and is not a cycle or timing duration. These
additions do not select physical entries, banks, ports, or service rates.

The corrected schema `1.2`, used only for a fresh `_03` output, fixes the
saturation-run axis: A4.7.1 append and dequeue raw logical checkpoints are
interleaved, so runs are computed over the contiguous phase-local opportunity
ordinal obtained by sorting raw checkpoints within that phase. The raw
checkpoint remains provenance only; the ordinal is not a cycle, latency, or
time quantity.

### Route-A A4.8.0 commit-aware transaction-backlog replay

`kvzap-route-a480-commit-aware-backlog-1.0` hash-binds the corrected A4.7.2.1
`_03` report, A4.7.2.0, A4.7.1 transaction trace, and the A4.6.8.2.2.0 record
trace required to reconstruct exactly the four preregistered A4.7.0 dependency
edge types. It additionally retains the already-fixed A4.7.1 per-head FIFO
transaction predecessor; that serialization guard is not a new A4.7.0 edge
type. It retains every A4.7.1 transaction group, FIFO-derived order,
and one commit/linearization boundary. A `direct_unconstrained_commit`
functional baseline must drain all dependency-ready groups in their recorded
logical opportunities.

The only bounded sensitivity policy is `causal_elastic_v1`. It selects from
fixed abstract levels `minimum/medium/high={1,2,4}` using only present logical
backlog, maximum per-head backlog, maximum pending age, and its own previous
state. It receives no future arrival, evaluation horizon, anchor, or workload
identity. A no-arrival post-trace drain continuation is explicitly bounded and
reported solely to distinguish `drained` from `prefix_censored_backlog_remains`;
its bound is not controller input.

For each uncommitted group after an opportunity, exactly one first blocker is
reported with fixed precedence: intrinsic transaction dependency, modeled RMW
service shortage, modeled cross-bank atomic-commit waiting, or modeled
same-bank service shortage. `logical_opportunity_epoch_delay` is an ordinal
difference between trace/replay opportunities, never latency. Level occupancy,
longest high-level logical-opportunity run, escalation/de-escalation counts,
and residual high-level backlog are modeled observations only. No field is a
physical bank/port, access/atomic/transaction, cycle, timing, traffic,
bandwidth, performance, capacity, energy, area, architecture selection, or RTL
claim.
