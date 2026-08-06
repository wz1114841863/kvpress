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

