# RESEARCH_CONTEXT.md

## 1. 背景

KVzap 使用每层的轻量 Linear/MLP predictor，从输入 hidden state 预测每个 KV head 的重要性分数，并通过固定阈值删除低分 KV。最近 128 个 token 使用 sliding window 强制保留。论文报告在若干模型和长上下文/推理任务上获得约 2–4× KV Cache 压缩，精度损失较小。

论文同时明确指出：

- 真实 wall-clock speedup 与 GPU memory saving 未在该工作中完成；
- per-head 非均匀长度需要支持 variable-length block 的 PagedAttention；
- kernel 与内存管理优化并不简单；
- predictor 训练不是 training-free，官方仅提供有限模型的 checkpoint；
- 训练 prompt 较短，长上下文可能存在分布偏移。

因此本项目不把“训练新 predictor”作为前提，而把官方 predictor 作为固定工作负载。

## 2. 当前研究定位

不建议把论文定位成“为 KVzap 的小 MLP 设计加速器”。Linear/MLP 计算结构常规，创新性有限。

更有价值的研究问题是：

> 如何把 KVzap 的逻辑剪枝转化为真实的物理 KV 容量、HBM 流量和 decoding 性能收益？

以及：

> 如何在不重新训练 predictor 的前提下，将 token-head 级不规则稀疏转化为硬件友好的结构化稀疏？

## 3. 两条路线

### 路线 A：预测驱动的稀疏 KV 生命周期

核心概念：

- KV 生成时即可得到静态重要性分数；
- 最近 128 token 先进入规则 Hot Cache；
- 页面离开滑动窗口时成熟；
- 成熟页面根据 score/mask 一次性 admission/compaction；
- Cold Cache 页面 sealed 后不再修改；
- 后续 query 重复访问压缩后的长期缓存。

关键词：

- predict once, admit once, access many times；
- predict at creation, compact at maturity；
- hot/cold KV；
- page sealing；
- append-only cold cache；
- page-granular sparse attention。

### 路线 B：无训练的结构化稀疏

使用官方 score，但将原始 token-head mask 转为：

- block mask；
- page-aligned mask；
- head-group shared mask；
- length bucket；
- margin-aware mask；
- selective layer/head protection。

目标不是最大删除率，而是联合优化：

- accuracy；
- physical KV bytes；
- metadata；
- memory burst efficiency；
- PE load balance；
- scheduling complexity。

## 4. 关键风险

1. 原始 mask 可能接近随机，缺少 block locality；
2. 逻辑删除率高，但物理页面碎片大；
3. head 间保留长度差异造成负载不均；
4. predictor 权重访问可能引入额外流量；
5. 结构化策略可能导致精度明显下降；
6. 与已有 sparse KV、PagedAttention、KV compression 工作重叠；
7. prefill-before-attention pruning 会改变算法语义，不能直接采用。

## 5. 论文叙事的候选方向

较弱：

> A hardware accelerator for KVzap.

较强：

> Prediction-guided structured KV admission for adaptive KV cache pruning.

候选贡献：

1. 系统刻画 KVzap score/mask 的 layer、head、time 和 request 行为；
2. 提出无需训练的 score-to-structure 转换；
3. 提出基于 KV 生命周期的 hot/cold admission 与 page sealing；
4. 证明逻辑压缩可以转化为物理容量、HBM 流量和 decoding 性能收益。

