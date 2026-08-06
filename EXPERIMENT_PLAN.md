# EXPERIMENT_PLAN.md

## A. Baseline

- [ ] Full KV Cache 可运行
- [ ] 官方 KVzap 可运行
- [ ] 结果与论文/官方日志数量级一致
- [ ] 固定模型、predictor、threshold、window、seed、decoding 参数
- [ ] 保存 per-sample accuracy、compression、generation length
- [ ] 区分 removed fraction 和 compression factor

## B. Trace instrumentation

- [ ] score tensor shape 已确认
- [ ] mask tensor shape 已确认
- [ ] KV indices / compressed layout shape 已确认
- [ ] trace 默认关闭
- [ ] trace 开启不改变输出
- [ ] request-level summary
- [ ] layer-head retention
- [ ] raw score 或压缩 score
- [ ] final mask
- [ ] decoding step KV size
- [ ] git commit、config hash、dataset、seed

## C. Predictor behavior

- [ ] per-layer/per-head score mean/std
- [ ] score margin around threshold
- [ ] long-context distribution shift
- [ ] 可行时计算 oracle agreement
- [ ] false negative by layer/head
- [ ] Linear vs MLP comparison
- [ ] score quantization sensitivity

## D. Sparsity structure

- [ ] layer-head retention heatmap
- [ ] per-request compression CDF
- [ ] zero-run length
- [ ] one-run length
- [ ] autocorrelation at lag 1/2/4/8/16/32
- [ ] block occupancy B=4/8/16/32/64
- [ ] internal fragmentation
- [ ] head-head Jaccard
- [ ] layer-layer Jaccard
- [ ] head load imbalance CV/max-to-mean

## E. Adaptive capacity

- [ ] P50/P90/P95/P99 KV capacity
- [ ] threshold-compression curve
- [ ] threshold-accuracy curve
- [ ] compression by dataset/subtask
- [ ] compression by prompt length
- [ ] compression by output length
- [ ] decoding KV growth over time
- [ ] admission burst statistics

## F. Sliding window

- [ ] w=0/32/64/128/256/512
- [ ] accuracy
- [ ] compression
- [ ] Hot Cache bytes
- [ ] sealing frequency
- [ ] task sensitivity

## G. Failure analysis

- [ ] Full KV correct / KVzap wrong samples
- [ ] layer/head abnormal pruning
- [ ] first-layer protection
- [ ] first-k-layer protection
- [ ] last-k-layer protection
- [ ] sensitive-head protection
- [ ] larger window
- [ ] special token protection

## H. Structured sparsity candidates

- [ ] block max
- [ ] block percentile
- [ ] k-of-B
- [ ] page-aligned pruning
- [ ] head-group max mask
- [ ] head-length bucketing
- [ ] margin-aware coalescing
- [ ] B=1,G=1 recovers original behavior

## I. Mandatory reporting

- [ ] Accuracy
- [ ] Logical KV bytes
- [ ] Physical KV bytes
- [ ] Metadata bytes
- [ ] Page count
- [ ] Internal fragmentation
- [ ] Estimated HBM transactions
- [ ] Average burst length
- [ ] PE/load imbalance
- [ ] Per-subtask degradation
- [ ] Failure cases
- [ ] Pareto frontier

