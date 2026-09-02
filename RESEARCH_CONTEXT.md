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

## 2. 当前研究定位（Route A 为主线）

不建议把论文定位成“为 KVzap 的小 MLP 设计加速器”。Linear/MLP 计算结构常规，创新性有限。

更有价值的研究问题是：

> 如何把 KVzap 的逻辑剪枝转化为真实的物理 KV 容量、HBM 流量和 decoding 性能收益？

自 2026-08-22 起，Route A 是主线：保留原始 token/head 级 mask，通过 hot/cold
lifecycle、per-head packed pages 与 load-aware attention scheduling 获取收益。Route B
（直接把 mask 结构化）已完成有界筛查，冻结于
`analysis/b4_route_b_screening_freeze.json`，仅作为无法进行任意 token compaction 时的
备选，不再是默认研究方向。

## 3. 两条路线

### 路线 A：预测驱动的稀疏 KV 生命周期（主线）

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

Route A 必须依次验证三件事：

1. **Packing 回本**：一次 hot-to-cold admission 的读/写/metadata 成本，能否被后续
   减少的 KV read 在足够短的输出步数内摊销；
2. **调度价值**：variable-length per-head page workload 是否造成静态 head mapping 的
   显著 PE 空闲，以及 length-aware/page-level scheduling 是否能在计入开销后回收该损失；
3. **系统收益**：物理 packed capacity 是否在 metadata、admission、scheduler、merge
   成本后仍转化为净 HBM traffic 和 modeled decode-latency 收益。

### 当前阶段交接（2026-09-02）

A0--A3 的证据索引、结论边界和 A4 入口见
`analysis/route_a_a0_a3_a4_handoff_20260902.md`。当前仅为条件性可行性：Route A
可以进入 policy-on functional reference 与实际软件测量研究，但不具有 RTL、真实 HBM、
wall-clock 或通用加速结论。无可信 continuation 信息时，Full-KV bypass 是严格性能安全
路径；deferred admission 仅为语义安全的投机策略。continuation contract 是可选上游控制
面接口，不是默认假设存在的长度预测器。

三项的详细可复现实验合同见 `analysis/route_a_research_plan.md`。现有
predictor-only prefill trace 只能先支持静态 packing 和 scheduler DSE；admission
break-even 与实测 end-to-end 仍需要后续安全的 decode-lifecycle trace 或独立测量。

### 路线 B：无训练的结构化稀疏（冻结的备选）

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

已知边界：B=4,m=+0.25 在 timeline-page 假设下可带来约 5--8% 容量/read proxy
改善，但无法降低 page-count 尾部，且紧凑存储潜力显著低于原始 mask。不得将该结论
扩大为真实 HBM 或速度结论。

## 4. 关键风险

1. 原始 mask 可能缺少 block locality，但 packed per-head storage 是否足够低碎片仍待验证；
2. 逻辑删除率高，但 packing/admission 一次性流量可能无法在短输出中回本；
3. layer/head 保留长度差异是否会造成可恢复的调度损失，尚未由 scheduler 模型验证；
4. predictor、metadata、queue 与 partial-softmax merge 可能吞噬理论带宽收益；
5. predictor-only prefill trace 不能代替 decode lifecycle、实际 allocator 或 wall-clock 测量；
6. 与已有 sparse KV/PagedAttention 工作重叠，必须突出 KVzap 的静态 score、一次 admission、
   sealed cold-page 生命周期与定量 break-even；
7. prefill-before-attention pruning 会改变算法语义，不能直接采用。

## 5. 论文叙事的候选方向

较弱：

> A hardware accelerator for KVzap.

较强：

> Prediction-guided structured KV admission for adaptive KV cache pruning.

候选贡献：

1. 系统刻画 KVzap score/mask 的 layer、head、request 与后续 decode lifecycle 行为；
2. 提出保留原始 token/head pruning 语义的 hot/cold packed admission 与 page sealing；
3. 提出针对 variable-length KV page workload 的最小必要调度机制；
4. 以 break-even、traffic/cycle 模型和必要的测量，验证逻辑压缩何时能够转化为物理容量、
   HBM 流量和 decoding 性能收益。
