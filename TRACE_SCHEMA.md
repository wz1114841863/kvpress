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
