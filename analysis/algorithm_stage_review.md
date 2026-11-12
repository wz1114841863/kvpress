# 算法与系统探索阶段：研究脉络及紧凑报告整编评估

更新：2026-11-12；整理起点 `research/kvzap-latest / c9cc40d`。
本次任务是恢复研究过程的可读性，范围覆盖官方算法复现至 A4.14.1 的前 RTL 探索，
包括跨模型/前端支线。这里的“算法阶段”也包含功能软件参考和系统模型；后来的
RTL、DC、RD1/WCG1 及持续执行补齐不并入这条历史主线。

本页是**已有探索的综合整理和报告编排评估**，不是六份最终报告已经完成的声明。
R1 已收敛为[算法复现、稀疏结构与路线筛选](algorithm_reports/01_reproduction_and_route_selection.md)
一份正文，关键数据表、原始来源和必要保留决定均在其中。
R2 已整理为[Packing、调度与摊销](algorithm_reports/02_packing_scheduling_and_amortization.md)，
直接提取原始容量、调度、预算、短输出与前缀结果。
R3 已整理为[功能参考与执行观察](algorithm_reports/03_functional_reference_and_execution_observations.md)，
涵盖三源语义、cold ownership、数值边界、软件测量和逻辑事件。
R4 已整理为[跨模型与前端边界](algorithm_reports/04_cross_model_and_frontend_boundaries.md)，
涵盖Llama、SnapKV、官方DMS与C0—C5，保留各自数值/生命周期边界；尚待整理R5—R6两份。
后续每个专题以一份正文为目标，直接引用已有数据，不默认配套数据包、资料清单或归档方案。
没有重跑实验、改变旧结论或清理原文件。已阅读纵向计划、阶段归档、主要合同、
冻结结果及选定原始 JSON；未逐一重新验收所有运行。下文区分可直接引用的结果与
仍需提取数据的部分，不能将旧计划中的验收要求当成实际通过。

## 一、整条研究主线

```text
官方 predictor 能否复现？
  → 原 mask 的稀疏结构有什么特点？
  → 用 block 换规则性，还是保留原 mask 做 packing？
  → packing 能否保留容量价值，调度能否抵消负载不均？
  → admission 的一次性代价何时能由重复读取摊销？
  → hot/pending/packed 和 merge 能否实际保持同 mask 的 attention 语义？
  → 这种语义在哪些模型、哪些前端上成立？
  → activation、pending 容量、归属、metadata 服务能否形成有界方案？
  → 把已明确的 metadata 和 payload 成本加回后，还剩多少条件性余量？
  → 进入架构规格，等待实现级成本和时序检验
```

研究并不是只验证了“删除率很高”。它逐步把一个压缩机会拆成容量、调度、摊销、
数值语义、生命周期、资源管理和成本几个问题。后一个阶段往往是在补前一个阶段
暴露出的假设。整编时应保留这条因果关系，删去正文中的重复启动/检查过程。

## 二、建议最终保留六份专题报告

六份是这次评估提出的编辑目标，名称为工作名；不需要为每个小实验再新建正文。
页数是排版预算，图表和必要解释优先于严格限页。现有文档仍保留，先完成内容提炼。

| 报告 | 研究主题及阶段 | 正文目标 | 核心回答 |
|---|---|---|---|
| R1 算法复现、稀疏结构与路线筛选 | baseline、trace Gate A/B、v1/v2、Route-B | 6—8 页 | 原算法提供什么机会，为什么当时选 Route-A？ |
| R2 Packed-page、调度与 admission 摊销 | A0—A3.20 | 8—10 页 | 什么条件下 packing 值得做，什么条件下会亏？ |
| R3 功能软件参考与实际执行观察 | A4.0、A4.1、A4.2 | 6—8 页 | 物理分区能否保持给定 mask 的数值语义，软件执行暴露什么开销？ |
| R4 跨模型与跨前端的适用边界 | Llama M0—M6、SnapKV P0—P3、DMS M0—M4、C0—C5 | 4—6 页 | 哪些抽象可迁移，哪些机制是 Route-A 专用？ |
| R5 激活、pending 与 metadata 资源探索 | A4.3—A4.10，含 A4.6.8/A4.7/A4.8/A4.9 各细分 | 10—12 页 | 如何从生命周期走到容量、归属、原子事务和有限服务模型？ |
| R6 前 RTL 成本账本与架构入口判断 | A4.11—A4.14.1 | 6—8 页 | 哪些成本已纳入，剩余收益依赖哪些未完成假设？ |

合计约 40—52 页，采用“一份报告、多个研究问题”的形式。另保留一张来源索引，
不再为 provenance、副本和重跑过程各写一篇供日常阅读的总结。每项数值仍附模型、
workload、比较对象和证据类型；完整 hash/退出状态等只在底层可追溯资料保存。

## 三、各报告应当整理出的研究内容

### R1：算法复现、稀疏结构与路线筛选

**目的。** 先确认官方 predictor 能运行，再判断原始 token/head 级稀疏是否适合规则
存储；对“直接 block 化更容易做硬件”这一备选作出有证据的判断。

**计划与尝试。** 固定 Qwen3-8B、官方 MLP、threshold −4、window128；完成三个
内置请求的 Full-KV、prefill pruning、prefill+decode pruning 对照。随后从单请求
Gate A、三类请求 Gate B，推进到 18 条 v1 和 45 条 task/length-balanced v2。
分析删除率、layer/head 轮廓、token mask 重叠、fragmentation 和 block/page 布局；
筛查 B=4 的 margin-aware coalescing，并执行 9 请求×4 变体的小样本生成筛查。

**关键结果。** baseline 9 个组合内置检查通过。v2 token 加权删除率 66.23%，逻辑
压缩 2.96×；layer/head retention 跨请求 Pearson 均值约 0.972/0.980，但 keep-mask
Jaccard 约 0.205、扣除 marginal-rate 后约 0.069。B=4,m=+0.25 删除率约 53.22%，
逻辑压缩约 2.14×；仅在被测 timeline-page 模型下得到约 5—8% 容量/read proxy 优势，
没有改善样本的 per-layer/head page-count P95 或最大值。36 次生成的 mask gate 通过，
使用的是筛查指标，不能写成正式 LongBench 准确率已闭合。

**分析与承接。** 宏观保留比例稳定不等于可以共享 token mask。规则 block 有压缩
损失；原 mask 的 arbitrary-token packing 当时保留了更大的容量机会，因此 Route-A
成为主线。这一选择基于当时的布局模型，不包含后来实际控制逻辑的完整成本；它不是
“已证明结构化路线永远不值得做”。R1 应保留这项选择的依据和条件。

**核心来源。** [baseline](baseline_freeze.json)、[v1](longbench_core_v1_freeze.json)、
[v2](longbench_balanced_v2_freeze.json)、[Route-B](b4_route_b_screening_freeze.json)。
R1 正文已提取关键数据表、范围与分组结果，并列出未来分布图的数据来源；当前不要求生成图片。

### R2：Packed-page、调度与 admission 摊销

**目的。** 将逻辑稀疏转换为可检验的容量、调度和 byte/cycle 假设；确认一次 packing
之后是否有足够多的 decode reads 偿还 admission。

**计划与尝试。** A0 比较 page16/32/64/128、hot/cold、尾页和 metadata；A1 比较
static head、whole-head LPT、dynamic page，并显式加入 dispatch/merge 成本。
A2 用不改变 dense 生成的 read-only lifecycle 记录 maturity、admission、page 和
实际 decode horizon。A3 从初始 traffic 模型推进到有预算的 admission、pending
读取、bank/burst/staging、branch-consistent deferred admission；再依次检验 observable
gate、请求 cap、自然 early-stop、continuation contract、违约和前缀曲线。

**关键结果。** 已有归档给出的 P64 slot 容量压缩约 2.9147×，加入显式 metadata
约 2.9133×；这仍是静态容量模型。whole-head 调度在部分候选点能回收不均衡，
dynamic-page 的额外 merge/dispatch 可抵消利用率收益。高请求 cap 不能排除自然早停，
17-call Qasper 是具体反例。三条长摘要在指定共同模型点、defer0 的最终 modeled
cycle saving 为 40.9644%/42.0195%/46.5624%；同点观察到的共同安全前缀为 22 calls。
defer16 的启动亏损分别约 −10.5890%/−2.8957%/−1.8343%，于 calls38/31/25 恢复。
假 continuation 的反例可造成约 −10.9942% 的 modeled saving。

**分析与承接。** 能回本是带未来 horizon 和服务假设的条件性结果。trusted continuation
不是 max_new_tokens，也不是事后知道输出长度的 oracle。没有可信下界时，Full-KV
bypass 是严格安全对照，deferred admission 属于可亏损的投机策略。长摘要结果不能
给出真实请求总体的亏损概率。由此进入 R3：模型中的分区和 merge 必须实际执行。

**核心来源。** [A0—A3 阶段归档](route_a_stage_archive_20260902.md)、
[交接中的证据目录](route_a_a0_a3_a4_handoff_20260902.md)、
[A2 冻结](route_a2_lifecycle_freeze.json)、[纵向计划的 A0—A3 章节](route_a_research_plan.md)。
这里的数值引用既有验收/归档；最终 R2 应直接抽取对应 CSV 的容量尾部、policy 曲线
和 sensitivity 表，不把不同模型点拼成一组结果。

### R3：功能软件参考与实际执行观察

**目的。** 实际用 hot、pending、packed 三类源执行 attention，验证 mask、position、
append order 与 online softmax merge，并观察参考实现的开销组成。

**计划与尝试。** 从无模型数值 harness、单层单头、单层全头、早中晚多层推进至全
36 层/8 KV heads；分别覆盖小 budget 的非空 pending 与大 budget 的多页 packed。
比较 Full-KV、same-mask dense KVzap、Route-A，并执行组件计时、重复软件测量、
allocator/profiler 和 horizon16/32 accounting。A4.2 从 profiler marginals 进一步
收集有序逻辑 source/merge 事件、确切 fan-in、三 workload 对齐及 GQA 共享边界。

**关键结果。** 早期全层 replayed-mask gate 每侧有 2,016 次比较，包含实际 pending
和 packed 读取；同 mask FP32 最大差约 1.526e−5。独立在线分支出现 5/268,992 个
threshold 决策翻转，因此后续严格配对使用 dense-source mask replay。外部 cold
ownership 路径避免了用原生 dense cold 暗中完成被选 attention。Python 参考存在
慢于 dense 的结果；h32 accounting 观察到约 34.53% 的三源决策被空源省略、平均
约 1.964 个实际 partial source/merge。源调用次数不是实际硬件访问次数。

**分析与承接。** 给定 mask 的分区数值等价和在线 predictor 决策始终一致是两个
问题。软件 profiling 暴露 hot/packed/merge 开销，不能用 Python 慢直接断定硬件慢。
GQA 可共享某些 source/descriptor dispatch 信息，Q 相关 partial/merge 状态仍须独立。
聚合调用量不能替代执行时序，于是需要后续资源和依赖模型。

**核心来源。** [A4.0 与 A4.1 进度归档](route_a_a0_a3_a4_handoff_20260902.md)、
[A4 讨论简报](route_a_a4_discussion_brief_20260909.md)、
[A4.1 测量计划](route_a41_measurement_plan.md)、[纵向计划 A4.2](route_a_research_plan.md)。
R3正文已提取指定retrieval/summarization配置的软件计时与分位数、测量范围、allocator
和source调用结构，直接引用原结果；不将同步组件时间加成end-to-end时间，也不声称
重新验收全部profiler或完成更多workload性能评测。

### R4：跨模型与跨前端的适用边界

**目的。** 检验 Route-A 是哪些语义下的后端，避免把 Qwen 的一个实例直接称为
通用稀疏 KV 加速器。

**计划与尝试。** Llama M0—M6 检验 predictor/同 mask attention/lifecycle 的可迁移性，
扩展三类 workload 并修正 horizon 对齐。SnapKV 检验 terminal prefill 后的 packed
映射。官方训练 DMS 检验 delayed eviction、native slot reuse 和 active-resident
attention。C0—C5 对已有证据作字段与 primitive 分析，不是又跑了六轮模型实验。

**关键结果。** Qwen/Llama 提供两个有限 anchor 的 Route-A 语义证据，但不能合并
成同一容量分布。SnapKV 有一次性 prefill terminal packed 映射和 bounded semantic
probe，生成期 decode 未观察。DMS 有 144-call 的一源 active-resident replay；
accepted request 的 288 个最终 layer/head 状态中，269 个按 native slot 遍历读取
arrival serial 时非单调，说明不能用 arrival-order 替换它要求的 native 顺序。
C5 保留 Route-A 主线，共同部分仅为 frontend-bound 有序 variable-length source
traversal 的语义抽象，未得到共同 cache、scheduler 或硬件资源合同。

**分析与承接。** “语义可迁移”“共享接口抽象”“同一硬件经济可行”必须分别回答。
此支线最值得留下的成果是适用边界与未观察项，不是环境兼容过程或副本校验。

**核心来源。** [跨前端证据归档](cross_frontend_residency_evidence_archive_20260915.md)、
[C0—C5 完成记录](cross_frontend_commonality_study_plan.md)。R4正文已提取M6六行fan-in、
SnapKV布局和DMS重放结果，以比较矩阵收口适用范围；不同模型、fixed continuation
与自然输出不合并统计，严格ULP未通过和未知字段继续保留。

### R5：激活、pending 与 metadata 资源探索

这部分细分最多，建议按下面六个研究问题合并，而非逐个 A4.x 写正文。
“已有进展”是现有记录的综合，最终报告需从对应结果提取关键曲线和比较数值。

| 研究问题 | 当时的计划/比较 | 已有进展及应保留的分析 | 如何推进下一步 |
|---|---|---|---|
| pending 压力是否只是观察粒度导致？A4.3 | attention 时刻 snapshot → append 前后 lifecycle → Q/C scalar replay → prefill chunk64、Q1/8/32，Qwen/Llama 分列 | 增加 service opportunity 会改变 pending/page 状态；snapshot、逻辑 quantum 都不是物理 FIFO 和服务率。不能将三 workload 的无越界点当容量保证 | 需要明确何时启用 Route-A，如何退出 |
| activation 与保护能否保持功能？A4.4—4.5 | end-before-activation、一次 FULL_KV→ACTIVE；layer-local 触发、next-epoch request-global fallback、shadow tombstone | 明确当前 epoch 与下一 epoch 的作用边界；保留 native Full-KV 的参考路径支撑 fallback，shadow 不可再访问仅证明逻辑失效，不是零成本物理回收 | 回到正常 active 路径，分析持续 pending 增长 |
| 服务不足还是容量组织问题？A4.6.0—4.6.7 | bounded64-token active 路径；burst/多 horizon；future-aware 对照与因果16/64/256级 service；等预算 private/shared/hierarchical | 区分 activation burst、持续到达、grant、容量闲置；pooling 可研究偏斜吸收，同时必须保留每 head oldest/FIFO。组织比较不能改原 grant；管理事件数量不等于成本 | 对共享/分层管理提出可验证的记录表示 |
| 什么状态和原子边界真的必要？A4.6.8—4.7.2 | birth-ordered span、四类逻辑 record、access epoch；依赖图；admission/dequeue/release transaction；namespace/reuse/width/layout | 用 span/记录表达归属，保留 source/birth/FIFO；只允许限定同 record 合并。原子 commit 阻止中间态被观察。跨 context 固定 provision 不能用某个 context 的峰值代替 | 在固定语义上测映射争用和 backlog |
| backlog 是何种服务/依赖导致？A4.8 | direct/causal/fixed service；ready 与 dependency backlog、shortage-root 传播；eager RMW 对照同 record read+write | 不能把传播后的依赖等待全部叫 intrinsic。RMW 拆解增加 R/W 工作并保留 commit-exclusion 义务，不是免费消除 RMW；其实际收益应按完整对照提取 | 收口语义变体，进入具体候选执行模型 |
| 候选 metadata engine 能否有限排空？A4.9—4.10 | joint-safe footprint、temporary commit 状态；whole-bank/record-granular；有限 local/shared/staging、lossless credit | A4.9.0 在覆盖 trace 中得到有限状态/fanout 与 reasoning 有界 drain；后续采用 HA8-wide、record-granular、local32/shared256/staging512 模型点，仍是声明服务模型 | 需要把同一实际 lifecycle 对齐到 metadata/payload 成本 |

**必须保留的研究判断。** service budget 是每次能做多少工作，不能等同全局 pending
容量；逻辑 observer 的 cap 不代表真实存储已实现；共享节省的容量与引入的归属/
选择/原子成本必须同账。这个阶段的价值是逐步暴露并约束实现义务，不能将大量
reference-model PASS 数量作为经济可行性的证据。

**核心来源。** [纵向计划 A4.3—A4.10](route_a_research_plan.md)，以及来源索引列出的
对应报告目录。已直接抽查 A4.7.2.1、A4.8.2b、A4.9.0/4.9.1 JSON；其中 A4.9.1
声明的 53,696 bit aligned metadata 是该 candidate model 的 accounting，不能套用到
后来 RTL compact 表。最终 R5 仍需提取 pooling 容量恢复、管理工作、backlog/drain
及 granularity/credit 对照的核心表格；本轮不补造缺失数值或把历史计划当实验结果。

### R6：前 RTL 成本账本与架构入口判断

**目的。** 把功能 lifecycle、metadata 和 packed payload 放到明确的成本边界中，
决定能否进入架构规格；不是预先证明完整芯片获益。

**计划与尝试。** A4.11 对三个固定 workload 完成 trace-off 语义、软件测量与
prefill-armed external-storage lifecycle；A4.12 将 metadata 接口映射至 macro
候选，A4.13 对 packed payload、合法 GQA reuse、HBM/source buffer/P3 计账；
A4.14 将 M2 replay 对齐同 workload，再做包含遗漏项的最终差分预算。

**关键结果。** M1 unified1RW 被拒，M2 replicated/duplicated control 成为完整
public-CACTI proxy 候选，M3 register 未计价。Full-KV/Route-A 都给予相同合法 GQA
reuse，旧 no-reuse 对照不再作 headline。最终 retrieval/summarization/reasoning 的
HBM-byte 比约 0.327/0.313/0.233（含 P3 admission）；动态能量的 differential
omitted-cost budget 约 27.646/40.498/167.442 mJ/request。对应 metadata replay
无损 drain。P3 1,179,648 B 是 staging envelope，尚非已落地 SRAM 价格。

**分析与承接。** 正预算的含义是“Route-A 未估计动态成本减 Full-KV 未估计动态
成本必须小于这笔余量”，不是遗漏项为零；这也不是面积或周期预算。metadata 与
payload 的服务坐标没有统一成可相加的总延迟。结果只支持进入 architecture spec。
后来硬件实现的大面积/时序问题不推翻原结构观测，但说明条件性机会尚未完成兑现。

**核心来源。** [A4.11 语义合同](route_a4110_semantic_contract.md)、
[A4.14.1 最终合同](route_a4141_accounted_net_benefit_ledger_contract.md)、
[最终结果目录](experiments/route_a4141_accounted_net_benefit_ledger_01/)、
[纵向计划完成记录](route_a_research_plan.md)。正式报告应采用最终 fair-GQA ledger 的
workload 行，保留 common/fixed/activity/unestimated 成本表，而不是罗列各次运行。

## 四、把资料减下来：保留内容的判断标准

**进入六份正文：** 每个问题的动机、对照和变量、固定条件、关键结果及分布、
解释、被推翻的假设和通向下一阶段的理由。数值结果与结论边界一起保存。

**保留为底层证据但不占阅读主线：** 核心配置、选定实验的结果表/图、必要 trace、
代码版本与可复现入口、原始 manifest/freeze；原始 hash 可以留在其既有位置。
这些不是每天要读的内容，后续也不能只留报告而丢掉唯一的数据依据。

**后续可评估合并或清理：** 相同结果的多份交接/启动说明、被最终结果完整取代的
进度快照、纯环境报错和重试记录、可重建的临时输出。目录名后缀 `_01/_02`、
`remote_replica` 或 `failed` 本身不能决定可删性；先核对有无独有结果和依赖。

**科学负结果留在正文。** Route-B 压缩损失、短输出亏损、在线 mask 翻转、Python
参考较慢、M1 不满足服务等，都是改变研究判断的信息。因工具/环境报错而没有得到
有效实验的运行通常只需留在可追溯记录中，两者不能混为“失败记录”一起删除。

清理前应满足：关键结论已被专题报告接住；关键结果文件已选定并可定位；旧文件
没有独有的结果/条件；必要原始制品已有明确保存位置。**本次未生成删除清单，
也未授权或执行删除。** 后续清理应按专题逐批做，不能只依赖文件名批量清空。

## 五、这一批整理已完成与尚待完成的部分

已完成：形成六个主题的归并方案和上述探索内容；将纵向计划的阶段入口映射到
[来源索引 CSV](algorithm_stage_source_index.csv)，使细阶段不会在压缩叙事时消失。
索引记录原文标题/行号和应归报告；它不是实验通过清单、去重结果或删除依据。

尚待完成：将R5—R6两个专题的关键原始表/曲线提炼成自足报告，特别是
R5 的组织/服务对照。旧论文范围和硬件实现问题另留在项目总览中，避免反复塞入
算法阶段正文。建议整编顺序 R1→R2→R3→R4→R5→R6，完成一份就用它承接对应旧
阅读入口，不再新增同主题的每日总结；各份完成后再评估相应中间材料的可清理性。
