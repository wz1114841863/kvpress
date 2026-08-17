# AGENTS.md

## 1. 项目目标

本仓库用于研究 NVIDIA 论文 **KVzap: Fast, Adaptive, and Faithful KV Cache Pruning** 的算法行为与硬件友好实现。

当前阶段的首要目标不是训练新的 KVzap predictor，也不是立即实现完整加速器，而是：

1. 复核官方实现与论文结果的一致性；
2. 导出可复用的 score / mask / KV-size trace；
3. 系统分析 KVzap 稀疏模式；
4. 判断后续更适合：
   - 路线 A：保留原始稀疏模式，设计高效稀疏 KV 后端；
   - 路线 B：在不重新训练 predictor 的前提下，把原始稀疏转化为硬件友好的 block/page/head-group 结构；
5. 只有在上述分析完成后，才开始实现硬件模型、调度器或 RTL。

### 1.1 当前冻结状态（2026-08-17）

Phase 0 baseline 已冻结。后续工作必须以以下记录为权威边界：

- 冻结实验：`kvzap-baseline-20260806T043908Z`；
- 配置哈希：`b1d3a4704b3cba56a1d31d47054c3e886bfff11bdfb8c0ca2ae89315433da1e6`；
- 运行环境：Qwen3-8B、官方 MLP predictor revision
  `bd5c5917846617da4311539859c137a262a6348b`、threshold `-4`、window `128`、seed `42`、
  greedy decoding、thinking disabled、A100-SXM-64GB、PyTorch `2.10.0+cu128`、Transformers `5.0.0`；
- 核心制品：`analysis/baseline_config.yaml`、`analysis/baseline_results.csv`；
- 冻结清单与 SHA-256：`analysis/baseline_freeze.json`；
- 9 个运行组合全部完成，三个内置功能检查在 Full KV、KVzap prefill、KVzap
  prefill+decoding 下均通过；
- KVzap prefill logical removed fraction 为 `69.54%..74.34%`
  （`3.28x..3.90x` logical compression）；
- KVzap prefill+decoding logical removed fraction 为 `70.36%..74.91%`
  （`3.37x..3.99x` logical compression）。

冻结结论只证明：在这三个内置请求、指定模型/checkpoint/环境下，官方 predictor 与
KVPress 路径能够运行，功能检查通过，并产生上述逻辑裁剪率。它不证明官方
RULER/LongBench 精度、任意请求上的 faithful generation、物理显存节省或 wall-clock
加速。`elapsed_ms_diagnostic` 不得用于性能结论。

冻结规则：

1. 不覆盖或手工编辑 `analysis/baseline_config.yaml` 和 `analysis/baseline_results.csv`；
2. 新 baseline 必须写入 `analysis/experiments/<new_id>/`，不得复用冻结 experiment ID；
3. Trace、结构化 mask 或后端修改失败，不得反向否定已经冻结的 Phase 0 事实；
4. 任何高于“内置功能检查”的准确率结论都必须单独运行正式 benchmark；
5. `results/qwen3_8b_single_384/` 是单个 hardware 请求的补充 Trace 参考，不属于
   Phase 0 baseline，也不能替代多请求 Trace 验证。

## 2. 研究边界

### 当前应做

- 使用官方 pretrained KVzap predictor；
- 复现实验和采集 trace；
- 分析 layer/head/token/request 级行为；
- 实现不需要训练的 score-to-mask 后处理；
- 建立 logical compression、physical compression、HBM traffic、load imbalance 的分析模型；
- 保证所有实验可复现。

### 当前不做

- 不训练或微调新的 KVzap predictor；
- 不修改基础 LLM 权重；
- 不先做 prefill-before-attention pruning；
- 不先实现完整 NPU；
- 不把 predictor 的普通 Linear/MLP 加速本身作为主要创新；
- 不在没有实验依据时假设 KVzap mask 具有 block locality 或 head similarity。

## 3. 论文与代码的来源约定

- 论文 PDF 应放在以下任一位置：
  - `papers/KVzap.pdf`
- 代码仓库以当前本地 checkout 为准。
- 官方 checkpoint、模型配置和 benchmark 配置优先级高于本文件中的示例。
- 若论文、代码和 README 不一致：
  1. 记录冲突；
  2. 以实际代码路径和运行结果为准；
  3. 不静默修正；
  4. 在实验日志中明确说明。

## 4. 首次进入仓库时的必做动作

开始修改前，先完成仓库勘察，并生成 `analysis/repo_inventory.md`：

1. 列出顶层目录；
2. 找到推理入口、benchmark 入口、KVzap 实现、predictor 加载代码；
3. 找到 threshold、sliding window、compression timing 的实现位置；
4. 找到 score、mask、KV indices 的张量形状；
5. 找到官方推荐的运行命令；
6. 找到结果保存格式；
7. 确认支持的模型、predictor 类型和数据集；
8. 确认代码是否在 attention 前或 attention 后执行 pruning；
9. 确认 decoding 中如何维护 128-token sliding window；
10. 不要在未确认命令前编造 CLI 参数。

## 5. 当前研究问题

所有新增代码和实验应服务于下列问题之一。

### Q1. Predictor 是否稳定可靠？

- 不同 layer/head 的 score 分布是否一致？
- 阈值附近的 score margin 是否足够大？
- 长上下文下是否出现 score distribution shift？
- 可获得 KVzip+ oracle 时，false negative 主要出现在哪些 layer/head？

### Q2. 原始稀疏模式是否具有硬件可利用结构？

- 连续删除区间是否足够长？
- block occupancy 是否集中在 0 或 1？
- 不同 KV head 的 mask 是否相似？
- 不同 layer 的 mask 是否相似？
- 每个 head 的有效长度差异有多大？

### Q3. 输入自适应是否造成容量和负载尾部风险？

- 每个 request 的 compression ratio 分布是什么？
- P50/P90/P95/P99 物理 KV 容量是多少？
- decoding 过程中 KV 增长是否平稳？
- admission 是否存在 burst？

### Q4. 不重新训练时，能否获得更规则的稀疏？

优先评估：

- token block pruning；
- page-aligned pruning；
- head-group shared mask；
- head-length bucketing；
- margin-aware block coalescing；
- fixed-point / INT8 score quantization；
- layer/head protection policy。

## 6. 两条后续路线

### 路线 A：固定 predictor，设计稀疏 KV 后端

保持原始 score/mask 语义，重点研究：

- Hot Cache：最近 `w=128` token 规则存储；
- Cold Cache：离开窗口后长期存储；
- `predict at creation, compact at maturity`；
- page sealing；
- append-only sealed cold pages；
- per-head variable-length page table；
- page-granular sparse attention scheduling；
- online softmax reduction；
- physical memory、metadata、HBM traffic 与 load balance。

此路线的主要风险是与已有 sparse KV / PagedAttention 工作重叠，因此必须突出 KVzap 的静态 score、一次预测、一次 admission、后续重复访问的生命周期特性。

### 路线 B：结构化稀疏软硬件协同

不训练 predictor，只改变 score-to-mask 过程，使稀疏更适合硬件：

- block size `B ∈ {4, 8, 16, 32}`；
- page-aligned keep/drop；
- head group size `G ∈ {1, 2, 4, 8}`；
- block score：max / percentile / k-of-B；
- score margin-aware merging；
- effective length bucketing；
- layer/head selective protection。

必须重新运行精度评测，不允许只根据 trace 推断精度。

## 7. 实验阶段与门槛

### Phase 0：Baseline 冻结（已完成）

输出：

- `analysis/baseline_config.yaml`
- `analysis/baseline_results.csv`
- `analysis/reproduction_notes.md`

要求：

- Full KV 与官方 KVzap 均可运行；
- 记录模型、checkpoint、threshold、window、数据集、解码参数、seed；
- 记录 per-sample accuracy、compression、generation length；
- 区分 removed fraction 与 compression factor。

冻结记录见 `analysis/baseline_freeze.json`。除非发现冻结制品校验和不匹配或原始结果
解析错误，否则当前工作从 Phase 1 继续，不重复覆盖 Phase 0。

### Phase 1：Trace 采集

输出：

- request-level summary；
- layer/head retention；
- raw score 或可恢复的压缩 score；
- final keep/drop mask；
- decoding step 级 KV size；
- trace schema 见 `TRACE_SCHEMA.md`。

要求：

- trace 默认关闭；
- 开启 trace 时不改变算法结果；
- 大规模实验禁止保存完整 attention matrix；
- 支持分片、压缩和断点续跑。

### Phase 2：原始稀疏分析

至少生成：

1. layer-head retention heatmap；
2. per-request compression CDF；
3. zero/one run-length distribution；
4. block occupancy 与 internal fragmentation；
5. head-head Jaccard similarity；
6. head load imbalance；
7. decoding KV size over time；
8. score margin distribution。

### Phase 3：结构化策略筛选

先用 trace 离线估算：

- logical occupancy；
- physical occupancy；
- metadata bytes；
- page count；
- average burst length；
- head load imbalance。

只将 Pareto 较优的少量策略送入完整精度评测。

### Phase 4：重新评测精度

必须报告：

- accuracy；
- logical compression；
- physical compression；
- per-subtask degradation；
- failure samples；
- 与原始 KVzap 的差异。

### Phase 5：硬件/系统模型

只有在以下条件满足时进入：

- 结构化策略保留了足够精度和物理压缩；或
- 原始 mask 明确不适合结构化，因此路线 A 的 token/page compaction 必要性成立。

## 8. Trace 与数据处理原则

- Tensor 维度必须在代码和文件中显式记录；
- 不允许依赖隐式 reshape；
- 所有 trace 必须包含版本号；
- 所有结果必须包含 git commit、配置 hash、模型、数据集和 seed；
- 对大 tensor 优先使用 `npz`、`parquet`、`safetensors` 或分片二进制；
- CSV 仅保存汇总，不保存完整 score tensor；
- 文本 token 可能包含隐私或大体积内容，默认只保存 token id 与位置；
- 需要文本时只对明确选定的小样本保存。

## 9. 代码修改规则

- 先以最小侵入方式增加 instrumentation；
- 不重写官方 pruning path；
- 不改变默认行为；
- 新功能通过显式 flag 开启；
- 每个新 flag 必须在 README 或 `analysis/` 文档中说明；
- 核心张量处理函数需有 shape assertion；
- 新增离线分析脚本优先放在 `tools/` 或 `analysis/`；
- 不把大型 trace、checkpoint、benchmark 输出提交到 git；
- 增加 `.gitignore` 规则；
- 所有脚本支持 `--help`；
- 长任务支持 resume 或分片。

## 10. 测试要求

至少增加以下测试：

1. trace 开关关闭时，输出与原始代码逐项一致；
2. trace 开关打开时，模型输出和 mask 不变；
3. score shape、mask shape、KV index shape 一致；
4. sliding window 中 token 永远保留；
5. compression ratio 计算正确；
6. removed fraction 与 compression factor 转换正确；
7. block/page/head-group 后处理在 `B=1, G=1` 时退化为原始 KVzap；
8. 结构化 mask 不包含越界索引；
9. 分片 trace 合并后统计与单次运行一致。

## 11. 结果与图表规范

每张图必须包含：

- 模型；
- 数据集；
- threshold；
- predictor 类型；
- sliding window；
- prompt/output 长度范围；
- 样本数；
- git commit 或实验 ID。

不要只给平均值。优先报告：

- distribution；
- CDF；
- P50/P90/P95/P99；
- per-layer/per-head heatmap；
- per-subtask 结果；
- Pareto frontier。

## 12. 事实与结论边界

允许的结论必须由实验支持。

### 可以说

- “在已评测的官方 predictor 和模型上……”
- “trace 显示……”
- “该结构化策略在这些 benchmark 上……”
- “硬件模型估计……”

### 不可以说

- “适用于任意 LLM”；
- “无需训练即可迁移到其他模型”；
- “3.5× 逻辑压缩等于 3.5× 加速”；
- “物理显存下降与 token 删除比例相同”；
- “prefill 可以直接提前剪枝”，除非重新验证；
- “已有 wall-clock speedup”，除非真实测量。

## 13. Codex 的工作方式

每次任务遵循：

1. 先阅读本文件、论文、README 和相关源码；
2. 先给出拟修改文件、数据流、风险和验证方式；
3. 优先实现最小可验证改动；
4. 运行最小测试；
5. 再运行小规模真实样本；
6. 最后更新文档和实验记录；
7. 不执行未经用户确认的长时间 benchmark；
8. 不删除已有结果或 checkpoint；
9. 不假设训练环境可用。

## 14. 建议的目录结构

```text
papers/
  KVzap.pdf
analysis/
  repo_inventory.md
  baseline_config.yaml
  baseline_results.csv
  reproduction_notes.md
  experiments/
  figures/
  notebooks/
tools/
  export_kvzap_trace.py
  analyze_retention.py
  analyze_run_length.py
  analyze_block_occupancy.py
  analyze_head_similarity.py
  analyze_decoding_growth.py
  evaluate_structured_mask.py
traces/
  .gitkeep
results/
  .gitkeep
```

不要强制重构现有仓库；若已有目录约定，优先复用。

## 15. 当前执行顺序

按顺序执行：

1. **已完成并冻结**：仓库勘察、代码路径定位和 Phase 0 baseline；
2. **当前任务**：远程验证与 DMS/attention 状态解耦的
   `tools/export_kvzap_predictor_trace.py`；本地实现完成不等于 gate A 已通过；
3. 用相同 987-token hardware 输入对照
   `results/qwen3_8b_single_384/score_mask.npz`，通过 `analysis/kvzap_trace.md`
   的 acceptance gate A；
4. gate A 通过后，才导出少量 retrieval、summarization、reasoning
   predictor traces；
5. 完成 run-length、block occupancy、head similarity 和 score-margin 分析；
6. 只有 predictor-only 结果稳定后，才单独设计 actual DMS mask 与 decode 生命周期验证；
7. 基于可信 trace 决定是否推进 block/page/head-group 结构化策略；
8. 任何结构化策略都必须回到独立精度评测，不能由 trace 直接推断准确率。
