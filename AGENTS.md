# AGENTS.md

## 1. 项目目标

本仓库用于研究 NVIDIA 论文 **KVzap: Fast, Adaptive, and Faithful KV Cache Pruning** 的算法行为与硬件友好实现。

当前阶段的首要目标不是训练新的 KVzap predictor，也不是立即实现 RTL，而是把冻结的
KVzap 原始 mask 转化为可证伪的 Route-A 物理系统假设：

1. 复核官方实现与论文结果的一致性；
2. 导出可复用的 score / mask / KV-size trace；
3. 系统分析 KVzap 稀疏模式；
4. 验证一次 packing/admission 是否能被后续 decode KV-read 减少快速摊销；
5. 验证 variable-length head/page workload 是否造成可恢复的调度损失；
6. 用显式 byte/cycle 模型验证物理容量能否转化为净 traffic 与性能收益；
7. 仅在这些门槛通过后，冻结架构规格并进入 RTL。

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
5. `traces/qwen3_8b_single_384/` 是单个 hardware 请求的补充 Trace 参考，不属于
   Phase 0 baseline，也不能替代多请求 Trace 验证。

### 1.2 LongBench predictor-only pilot 冻结状态（2026-08-18）

首轮真实样本结构 pilot `longbench_core_v1` 已冻结，权威记录为
`analysis/longbench_core_v1_freeze.json`：

- 18/18 请求完成并通过 `kvzap-predictor-trace-1.1` 离线校验；
- retrieval、summarization、reasoning 各 6 条，并各覆盖
  `[1024,4096)`、`[4096,8192)`、`[8192,16384)` 三个 tokenizer 长度桶；
- request-mean logical removed fraction 为 `66.26%`，范围为 `63.86%..67.00%`，
  request-mean logical compression 为 `2.97x`；
- layer/head retention profile 跨请求稳定，但原始 token mask 仍呈现较低 keep-mask
  Jaccard 与明显 block fragmentation；
- 该 pilot 的子任务组成不均衡：qasper 占 retrieval 的 5/6，qmsum 未入选。

冻结规则：不得覆盖 v1 的 JSONL、manifest、pilot run 或 analysis 目录。后续验证使用
`longbench_balanced_v2`，将每个 category/length bucket 扩展到 5 条，并记录每个 task
在各桶的 available/selected 数量。v1 和 v2 均为 predictor-only 结构证据，不能用于
准确率、decode 生命周期、物理显存或速度结论。

### 1.3 LongBench task-balanced v2 冻结状态（2026-08-22）

`longbench_balanced_v2` 的权威冻结记录为
`analysis/longbench_balanced_v2_freeze.json`：

- 45/45 predictor-only requests 完成，并逐条通过 `kvzap-predictor-trace-1.1` 离线校验；
- retrieval、summarization、reasoning 各 15 条；每个 category/length bucket 各 5 条；
- token-weighted logical removed fraction 为 `66.23%`，request mean 为 `66.47%`，
  logical compression 为 `2.96x`；
- 跨请求 layer / layer-head retention Pearson 均值分别为 `0.972` / `0.980`；
- 原始 keep-mask Jaccard 均值 `0.205`，扣除 marginal-rate 后 excess `0.069`，不能把
  稳定的 layer/head 宏观轮廓误解为可直接共享的 token mask。

冻结规则：不得覆盖 v2 preparation manifest、pilot run、trace 或
`analysis/experiments/longbench_balanced_v2_analysis/`。原始 JSONL 被 gitignore；其
SHA-256 由 preparation manifest 和 freeze record 保存，未同步到本地时不得伪称已重算。
该冻结同样仅是 predictor-only 结构证据。

### 1.4 B=4 Route-B 筛查冻结状态（2026-08-22）

`analysis/b4_route_b_screening_freeze.json` 是 B=4 margin-aware block
coalescing 的权威边界。它冻结了 45 条 v2 trace 的离线结构筛查、实际 DMS mask gate、
9 条分层 screening generation，以及 page-layout 成本模型。

- B=4,m=+0.25 在 9 条 screening 的 36/36 次运行中通过 mask gate；所用 QA F1 和
  whitespace-token ROUGE-L 仅为筛查指标，不是官方 LongBench accuracy；
- 原始 KVzap 在 arbitrary-token packed 下明显更优；B=4,m=+0.25 只在无法 token
  compaction 的 timeline-page 假设下有约 5--8% 容量/read proxy 优势；
- 该候选没有改善 sample 中 per-layer/head page-count 的 P95 或最大值。

结论：Route B 是受限备选，不扩大 B=4,m=+0.25 的 45 条 accuracy screen。byte/read
数值为显式假设下的代理，不是物理显存、HBM 流量或速度测量。

### 1.5 Route-A 研究计划（当前，2026-08-22）

权威交接和实验合同为 `KVZAP_ARCHITECTURE_PATH.md` 与
`analysis/route_a_research_plan.md`。Route A 保留原始 KVzap mask，并实现：

```text
predict at creation -> hot window (128) -> compact at maturity
-> append-only per-layer/head packed cold pages -> load-aware attention scheduling
```

当前先在冻结 v2 predictor-only trace 上做静态 page feasibility、容量尾部、批量调度和
byte/cycle DSE；这些都不加载模型。现有 trace **不能**证明 admission break-even 或
end-to-end 性能：两者需要安全的 read-only decode-lifecycle trace 或独立测量。

Route A 的 go/no-go 问题为：

1. packing/admission 是否在有用的未来 decode horizon 内回本；
2. 静态 head mapping 是否存在显著可恢复的 utilization 损失；
3. metadata、admission、scheduler 与 merge 开销后，net traffic 和 modeled latency
   是否仍显著优于 Full KV。

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

### Q2. Packing 是否保留原始 mask 的物理容量价值？

- `P ∈ {16,32,64,128}` 的 append-only packed pages 是否接近逻辑压缩？
- tail-page fragmentation、page-table metadata 和 page count 的 P50/P95/P99 是多少？
- 任意-token packed 下界与 timeline-position page 的差距有多大？
- compaction 是否需要辅助原始 position metadata？未检查代码前不得假设。

### Q3. 负载不均衡是否严重，调度是否值得？

- static head ownership 的 makespan、PE utilization 与 idle cycles 是多少？
- length-aware whole-head scheduling 能回收多少损失，是否已经足够？
- page/chunk dynamic scheduling 的额外 queue/merge 开销是否值得？
- batch `{1,2,4,8}` 的离线组合工作负载中，tail latency 和 request fairness 如何变化？

### Q4. Physical compression 能否成为净 traffic 与性能收益？

必须分开报告 Full KV、ideal packed KVzap、packed+static、packed+selected scheduler：

- hot/cold KV read/write bytes；
- page metadata、allocator、queue 和 partial-softmax merge bytes/cycles；
- attention compute cycles 与 bandwidth roofline；
- admission break-even future decode steps；
- modeled decode latency、tokens/s 和敏感性分析。

## 6. 两条后续路线

### 路线 A：固定 predictor，设计稀疏 KV 后端（主线）

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

### 路线 B：结构化稀疏软硬件协同（冻结备选）

不训练 predictor，只改变 score-to-mask 过程，使稀疏更适合硬件：

- block size `B ∈ {4, 8, 16, 32}`；
- page-aligned keep/drop；
- head group size `G ∈ {1, 2, 4, 8}`；
- block score：max / percentile / k-of-B；
- score margin-aware merging；
- effective length bucketing；
- layer/head selective protection。

必须重新运行精度评测，不允许只根据 trace 推断精度。除非 Route-A 的静态与系统模型
失败或 Route-B 出现明确的系统 Pareto 优势，否则不继续扩大该分支。

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

### Phase 3：Route-A static packed-page feasibility（当前）

只用冻结 trace，模拟 per-layer/head append-only packed cold page lists，输出 capacity、
tail waste、metadata、page count、per-head tail 和 Full-KV/ideal-packed 基线。不能把
静态最终 mask 伪称为 decoding admission trace。

### Phase 4：Route-A scheduler 与 traffic/cycle DSE

在明确的 page/PE/bandwidth/throughput 假设下，比较 static head、length-aware head 和
dynamic page/chunk scheduling。离线合成的多 request workload 必须标为 simulated batch。

### Phase 5：安全 decode-lifecycle trace 与 break-even

只有 static DSE 给出可行 Pareto 区域后，才采集不改变输出的 generated-token scores 和
maturity events，验证 admissions、page seals、promotion traffic、cold growth 与 break-even。

### Phase 6：架构规格、校准与 RTL 决策

只有 packed capacity、admission horizon、scheduler gain 和 net modeled traffic/latency 同时
通过预先记录的 go/no-go 门槛，才冻结 `analysis/architecture_spec.md` 并进入 RTL。

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
2. **已完成**：用相同 987-token hardware 输入对照
   `traces/qwen3_8b_single_384/score_mask.npz`；predictor-only acceptance gate A
   于 2026-08-17 通过，冻结证据见 `analysis/predictor_trace_gate_a.json`；
3. **已完成并冻结**：retrieval、summarization、reasoning 三个内置请求均通过
   predictor-only Gate B；证据、哈希和结论边界见
   `analysis/predictor_trace_gate_b_freeze.json`；
4. **已完成**：扩展并验证 `tools/analyze_kvzap_trace.py` 对
   `kvzap-predictor-trace-1.1` 的 run-length、block occupancy、head similarity、
   load imbalance 和 score-margin 离线分析；
5. **已完成并冻结**：18 条 `longbench_core_v1` predictor-only pilot；证据、哈希、
   统计结论和采样限制见 `analysis/longbench_core_v1_freeze.json`；
6. **已完成并冻结**：45 条 `longbench_balanced_v2`，并完成 category/task/length-bucket
   分组统计和 marginal-rate-adjusted head Jaccard；
7. **已完成并冻结**：B=4/m=0 与 B=4/m=+0.25 的离线结构、实际 DMS mask gate、9 条
   分层 screening 和 Phase-3 page-layout 筛查；权威记录为
   `analysis/b4_route_b_screening_freeze.json`；
8. **已完成 A0--A3（条件性可行性）**：静态 packed-page replay、scheduler、read-only
   lifecycle、branch-consistent admission/memory DSE、短输出反例、continuation-contract
   policy、breach sensitivity、observed-prefix sufficiency，以及长输出 A3.20 dense curve
   均已完成。交接入口为 `analysis/route_a_a0_a3_a4_handoff_20260902.md`，阶段归档为
   `analysis/route_a_stage_archive_20260902.md`；两者均不是 architecture-spec 或硬件测量冻结。
9. **A3.20 状态**：短输出亏损机制已有 A3.15 反例与 A3.20 activation-dip/recovery
   曲线支持；除非目标是估计真实请求分布的风险比例，不再以寻找更多亏损长度为主线。
   Full-KV bypass 是严格性能安全对照，deferred admission 只能标为语义安全的投机策略。
10. **当前主线 A4**：先实现 policy-on、语义校验的 packed-cold + pending-staging
    attention reference（A4.0），再采集 allocator/profiler/runtime 的实际软件测量（A4.1），
    最后收束 FIFO/page/bank/merge/scheduler/bypass 资源合同（A4.2）。contract 是可选软件
    控制面接口，而不是隐含长度预测器。
11. **RTL gate**：仅当 A4 同时验证语义、实测趋势、Full-KV fallback/control 以及跨模型/
    workload 的稳定资源合同后，才冻结 architecture spec 并考虑 RTL。
12. 任何会改变 mask 的结构化策略都必须回到独立精度评测，不能由 trace 直接推断准确率。
