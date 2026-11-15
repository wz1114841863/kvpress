# Predictor-driven Sparse KV Cache：算法抽象与系统需求定义

日期：2026-11-13。研究主线：System-Hardware Co-design Architecture Exploration（此前称Phase II）。
本主线内 **Phase 1 = Algorithm Abstraction & System Requirements**，
**Phase 2 = Software Reference & GPU Baseline**；历史Phase I指R1—R6/H1—H4，不能与新Phase 1混用。
**当前状态：Phase 1三个调查/设计任务已形成结果，提交审阅；逻辑接口未冻结，Phase 2未启动。**
本轮只读核查源码/官方接口及本地、远程既有制品，在CPU上提取真实集合示例；§8记录结果、缺失与验收。
没有实现统一Adapter/调度器，也未运行模型、GPU Benchmark、RTL、仿真或综合。
下文“首版”指拟在Phase 2实现的软件范围，不表示当前已有实现；逻辑接口、二进制接口和微架构均未冻结。

本文逐项使用以下三种状态；同一主题的证据和建议分开标记：

| 状态 | 含义与证据边界 |
|---|---|
| **Verified** | 原论文、当前代码/官方接口可直接核查，或已有指定范围的实验/模型结果。正文注明来源；论文提出/报告的内容不等于本项目复现，代码能力、模型估计与实验通过不互相替代 |
| **Proposed** | 本阶段提出的抽象、职责、首版范围或验证要求；文档写成不等于功能已经实现 |
| **Unknown** | 当前尚无足够证据的问题，包括未选定的实现、未验证的适配和未测收益；不按零成本处理 |

**Verified（历史证据）：** [项目总览](../project_overview_20261111.md)、算法R1—R6及硬件H1—H4
继续保存Phase I结果。约2.96×是指定Qwen3-8B/45条predictor-only trace的逻辑压缩；
129.52×是旧RD1＋WCG1控制投影的cell-area比。二者均不能作为本阶段系统收益。
旧RTL部分路径已有功能证据，完整持续执行、数值连接、存储成本和时序仍有缺口。

## 1. Research Scope

### 1.1 研究目标与适用范围

**Proposed：** 暂定方向为 **Software-Hardware Co-design for Predictor-driven Sparse KV Cache Management**。
研究预测驱动算法如何向系统提供明确的保留集合，软件如何组织存储与任务，以及有界的数据搬运硬件
能否在复用既有Attention和内存基础设施时，改善稀疏KV管理的时间、资源或能量成本。

**Proposed：** 先以KVzap和FastKVzip为两个具体前端。可适用的算法类别应满足：能够在声明的
生效边界给出准确的attention-visible集合，集合内记录具有明确身份，K/V数据存在且可以被稳定读取。
选择可以是阈值、预算或其他策略；旧记录能否再次被淘汰由各算法profile声明。
共同抽象不要求creation-time决策、统一hot window或append-only生命周期。

**Proposed：** 首个实现切片为：单请求、合法prefill后选择、逐KV head变长数据、源目标分离的
一次packing、现有Attention多次读取及安全释放。软件参考还必须能表达后续decode新增记录和
FastKVzip旧记录撤销；这不要求首版RTL同时实现全部动态能力。BF16/head_dim128可作为
首个具体实例，不成为抽象常数。保留零项的单流如何处理由consumer适配明确规定。

**Proposed：** 本阶段不训练predictor，不为兼容后端而修改selection policy，不设计完整LLM
推理/生产级serving系统、HBM controller/PHY或新的Attention算术单元，不重建旧R1—R6。
不迁移或重写Phase I冻结结果；旧Route-A保留为历史架构和成本参照。

### 1.2 职责和部署假设

| 层次 | 状态 | 本阶段职责 |
|---|---|---|
| Algorithm / selection frontend | Proposed | 保留原算法的score计算、保护范围、选择域、阈值/tie行为和生效边界；输出最终集合 |
| Software runtime / scheduler | Proposed | 维护集合版本、backing与布局、分配、packing策略、任务批次、read plan及回收；后续区分host与设备端软件 |
| Sparse KV movement engine | Proposed | 执行有限任务中的索引/读取、数据整理和写出，保存必要的局部在途状态，返回明确完成/失败 |
| Existing Attention / memory infrastructure | Proposed | 复用其计算与内存服务；适配、共享带宽、可见性和同步成本仍计入 |

**Proposed：** 主要架构研究假设为引擎与Attention能够访问同一HBM地址域，软件提交粗粒度任务；
这是一种拟评估的集成条件。外置设备可以另作部署情形，但需计入额外互连与数据复制。

**Unknown：** 具体平台、地址可达性、GPU缓存一致性、写入可见性fence、内存仲裁和共享带宽尚未选定。
现有GPU不能因规格提出了引擎就被认为能够直接调用它。CPU还是设备端软件产生高频任务、提交开销多大，
也未测量。Python参考只回答语义和工作量，不能代表高效runtime的延迟。

### 1.3 研究问题与收益口径

| 状态 | 需要回答的问题 |
|---|---|
| Proposed | 同一选择能否被准确表达、搬运和消费，并覆盖新增/撤销与在途读取？ |
| Proposed | 何种源布局、保留密度、批量和head偏斜下，packing及后续读取值得执行？ |
| Proposed | 专用引擎相对合理GPU实现改善了哪些工作：packing延迟、SM占用、能量或共享资源竞争？ |
| Unknown | 完整管理与集成成本计入后，净收益区域、面积代价及跨算法泛化范围有多大？ |

**Proposed：** Full-KV用于系统基线和算法质量对照；GPU Sparse KV与Proposed尽量使用相同
选择、调度策略和输出布局来分离搬运硬件贡献。算法质量与同集合实现正确性分别验证。
GPU实测、引擎仿真/综合、内存模型与系统延迟估计分别报告。旧控制比不是新架构的公平性能基线。

### 1.4 两阶段的工作边界

| 阶段 | 状态 | 要完成的工作 | 此阶段不承担的工作 |
|---|---|---|---|
| Phase 1：Algorithm Abstraction & System Requirements | 设计已提交审阅；接口仍Proposed、未冻结 | 三项设计调查：算法接口、Consumer与布局、系统职责与执行合同；结果见§8 | 不启动统一Adapter/调度参考实现、GPU Benchmark或RTL；不要求先测出收益 |
| Phase 2：Software Reference & GPU Baseline | Proposed；当前未启动 | 基于Phase 1确认的逻辑接口实现Adapter/参考，接入Consumer，测合理GPU基线及瓶颈 | 不重新发明算法决策或默认改职责；发现接口矛盾时明确回修Phase 1，不静默改变算法 |
| Phase 3：Hardware Architecture | Proposed；本次不展开 | 由Phase 2的瓶颈、成本预算和部署限制选择硬件功能 | 不能现在就确定prefix-sum、lane/bank数、页大小或完整Compaction Engine微架构 |

**Proposed：** Phase 1的设计验收与Phase 2的运行验收分开；接口建议被接受后仍是Proposed设计，
只有实际运行结果才补充Verified证据。任务、交接、验收清单及仍需确认的问题集中在§7。

## 2. Algorithm Characteristics

### 2.0 原论文、代码与历史实验的证据分工

本轮直接核对原论文相关章节、源码和已有结果，以下不只依据研究摘要。

| 来源与状态 | 可据此确认的内容 | 不得据此推出的内容 |
|---|---|---|
| Verified（原论文）：[KVzap本地v1](../../papers/KVzap.pdf)，§2.3、Algorithm 1及§3实验设置 | 以hidden state预测逐head重要性、阈值与recent window；论文所报实验在attention后压缩 | 论文伪代码中的索引操作不证明本仓库fake-key路径减少了dense tensor；约2.96×来自本项目trace而非论文 |
| Verified（原论文）：[FastKVzip v3](https://arxiv.org/html/2601.17668v3)，§3.1、Appendix A.5 | Gate与retention policy分工、chunked prefill、decode hidden buffering和周期性预算裁剪 | 精确比较符号、ties及旧KEEP撤销次数需看当前源码/实验，不能全部归于论文 |
| Verified（代码）：§2.1所列当前实现 | 真实比较、保护、cache重建和决策调用时点 | 代码存在不证明新Adapter、数值标准或性能通过 |
| Verified（历史制品）：[F1原JSON](../../../FastKVzip/research/experiments/fastkvzip_f1_gate_equivalence_20261103_r1/artifacts/f1_gate_report.json)、[F3原JSON](../../../FastKVzip/research/experiments/fastkvzip_f3_policy_comparison_20261103_r1/comparison.json)；F2原报告保留于[阶段文档归档](../../../FastKVzip/research/archive/step_documents_20261113.tar.gz) | 指定环境/输入下的Gate组织负结果、生命周期和离线选择对照；归档按原路径只读查看，未解包覆盖 | Synthetic trace不变成真实请求质量/性能分布，原预算4096与归一化预算1229不混算 |
| Verified（历史记录）：[F4 profile](../../../FastKVzip/research/experiments/fastkvzip_f4_global_threshold_candidate_20261103_r1/profile.json)、[初步校准](../../../FastKVzip/research/experiments/fastkvzip_f4v0_calibration_scores_20261103_r1/preliminary_calibration.json)、[收尾汇总](../../../FastKVzip/research/experiments/fastkvzip_f4v0_calibration_scores_20261103_r1/summary_finalized.json) | 80条已处理，28 eligible/52 short，存在初步校准；profile仍为候选，原64条目标未达到 | 不属于正式阈值冻结、盲验证质量或官方FastKVzip等价支持，本轮不读取盲验证 |

**Verified（历史研究，按各报告范围）：** R1—R6/H1—H4的含义仍分别保留，本文没有改写它们：

| 报告 | 本阶段直接继承的限制/经验 |
|---|---|
| [R1](../algorithm_reports/01_reproduction_and_route_selection.md) / [R2](../algorithm_reports/02_packing_scheduling_and_amortization.md) | 原mask机会不等于物理收益；短输出、dispatch/merge、启动与未来长度影响回本 |
| [R3](../algorithm_reports/03_functional_reference_and_execution_observations.md) / [R4](../algorithm_reports/04_cross_model_and_frontend_boundaries.md) | 同mask/数值配对与独立在线生成不同；跨前端共同字段不证明共用低成本cache |
| [R5](../algorithm_reports/05_pending_and_metadata_resource_exploration.md) / [R6](../algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md) | 容量、服务量与在途责任分开；前RTL公平账本是含遗漏项的条件性机会 |
| [H1](../hardware_reports/01_architecture_and_software_hardware_boundaries.md) / [H2](../hardware_reports/02_rtl_implementation_and_sustained_execution_scope.md) | 必要语义不唯一决定模块；首次使用和小规模两读不等于完整持续/数值链 |
| [H3](../hardware_reports/03_storage_measurement_boundary_and_complete_cost.md) / [H4](../hardware_reports/04_area_timing_optimization_and_design_review.md) | 信息、接口与物理存储代价分开；局部面积改善不能替代顶层时序或完整系统成本 |

### 2.1 当前可核查的选择机制

下表均为 **Verified（代码；实验范围另列）**，不表示已验证任意请求的质量或性能。

| 属性 | KVzap当前研究路径 | FastKVzip chunked prefill路径 | FastKVzip fixed-budget decode路径 |
|---|---|---|---|
| Score | 模型专用MLP/linear处理该层输入hidden，产生per-token/per-KV-head score | Chunk forward中计算Gate score | 积累hidden，在compression epoch计算Gate score |
| 选择域 | 离开保护窗口的最旧新成熟记录 | 本轮刚成熟的cohort，在所读pair配置下跨layer/head选择 | 当前完整retained score pool，跨layer/head选择 |
| Selection Epoch | 原生每层forward hook决策事件；研究重放profile为被消费的保存gate事件/当前append边界 | Chunk完成后的prune事件 | 全局compression epoch；中间新增受保护KV不必触发新global selection |
| 比较与tie | `score < threshold`为DROP，等号KEEP | pair阈值路径为`score > threshold` | 排序确定自适应threshold，再用`score >= threshold` |
| 保护 | 最近window；Qwen主线128是实验配置 | 系统prompt sink及recent window；所读F2-P配置window4096 | first tokens与recent window在score中置1；所读F2-D为first4/window128 |
| 旧mature KEEP | 当前路径不重新选择 | 已测cohort路径不重新选择 | 后续epoch可以再次淘汰 |
| 决定生效 | 原生DMSPress在attention后hook更新；Route-A policy研究后端在数值attention前append/mature，必须另标profile，见下文 | Chunk forward完成后prune | 整个model forward完成后`compress_post`，新集合供后续调用 |
| 数据保存 | 原fake-key路径仍保留dense K/V；external-cold是另行验证的软件参考 | Boolean gather实际重建保留K/V及逐head长度 | Boolean gather实际重建当前retained K/V及逐head长度 |
| K/V Record Identity（现有） | 原生以batch/head/cache index定位；研究参考有_Record.position，但未实现本统一ID接口 | 生产cache用每head保留行及flatten offset，trace另跟踪logical identity | 同样没有本统一持久ID；gather改变rank，trace旁路跟踪原logical position |
| Original Position来源 | 原cache_position及保存mask event；本例研究路径要求连续位置 | 原模型position/RoPE与F2旁路logical-position数组 | 模型逻辑seen/position与F2 before/after/attention_visible数组；不能由压缩rank反推 |

**Verified（源码位置）：** KVzap见[打分](../../kvpress/presses/kvzap_press.py)、
[forward hook注册](../../kvpress/presses/base_press.py)、[窗口与裁剪](../../kvpress/presses/dms_press.py)
及[fake-key路径](../../kvpress/attention_patch.py)。FastKVzip为本机相邻仓库：
[prefill调度](../../../FastKVzip/prefill/model/wrapper.py)、
[pair threshold](../../../FastKVzip/prefill/attention/score.py)、
[prefill cache](../../../FastKVzip/prefill/attention/kvcache.py)、
[decode选择](../../../FastKVzip/math/method/compression/fastkvzip.py)、
[decode调用时点](../../../FastKVzip/math/method/modeling.py)。相邻仓库链接不是kvpress checkout自带文件。

**Verified（代码）：** Decode的`budget_total = budget × layers × KV_heads`是目标，`>=`比较
在边界有并列score时可能多留记录，不能改写成精确top-k。Prefill与decode比较符号不同；
后端消费实际mask/count，不重新根据ratio或budget猜测集合。

**Verified（本轮源码核查）：** 原生[BasePress](../../kvpress/presses/base_press.py#L203)注册forward hook，
但[Route-A policy后端](../../kvpress/route_a_policy_backend.py#L323)在pre-hook捕获/重放keep决策，
其[attention入口](../../kvpress/route_a_policy_backend.py#L652)先`_append_state`，再计算所选head的数值输出。
两者的mask来源与生效边界不能混为一谈；本轮真实KVzap示例见§8，明确其来自哪条路径。
这项修正只纠正本文的归属说明，不修改算法、旧实验或它们的验收标准。

### 2.2 已有证据、负结果与不能升级的结论

| 状态 | 证据与适用范围 | 对新阶段的约束 |
|---|---|---|
| Verified（结构观察） | [R1](../algorithm_reports/01_reproduction_and_route_selection.md)：指定45条Qwen trace中逐head位置不规则，逻辑压缩约2.96× | 可作为不规则输入实例；不能当真实容量或速度 |
| Verified（有界软件实验） | [R3](../algorithm_reports/03_functional_reference_and_execution_observations.md)：同mask三源与external-cold功能；独立在线mask存在少量分歧，部分严格ULP检查失败，Python参考较慢 | 原mask配对、数值标准和性能实现分开；不强求独立生成永远一致 |
| Verified（有界生命周期实验） | [FastKVzip F2汇总](../../../FastKVzip/docs/official_behavior_and_compatibility.md)：synthetic Qwen输入的prefill/decode路径；decode两个完整epoch分别观察35,654/36,529次旧mature KEEP→EVICT | 共同描述必须覆盖集合撤销；不是所有输入的更新频率或硬件需求界 |
| Verified（负实验） | [FastKVzip F1汇总](../../../FastKVzip/docs/official_behavior_and_compatibility.md)：指定BF16 Gate/合成hidden下改变计算批量，12/12 ratio-mode出现mask翻转 | 移动任务批处理不授权重组Gate计算后声称同mask；先消费canonical选择 |
| Verified（离线比较） | [FastKVzip F3汇总](../../../FastKVzip/docs/official_behavior_and_compatibility.md)：单一synthetic score trace中fixed-threshold不撤销旧mature KEEP | 只是替代策略的生命周期证据，不是官方decode等价 |
| Proposed | [F4系列](../../../FastKVzip/docs/threshold_policy_and_validation.md)注册fixed-global-threshold候选，已有初步校准，但记录仍为`CANDIDATE_ONLY_UNVALIDATED` | 作为改变selection policy的设计候选保留，不能称官方decode等价 |
| Unknown | 上述F4候选的质量与可部署参数；初步校准不能替代长程容量和盲验证，本轮未读取blind validation或复验远程制品 | 不把候选注册或校准升级为算法质量或支持能力PASS |

**Proposed：** KVzap的“成熟KEEP单调”与FastKVzip prefill的类似观察作为profile属性描述。
完整visible set仍会因hot项成熟被删而变化，不能由“cold append-only”推出整个集合只增不减。
FastKVzip官方decode保留原有可替换集合，不能为了复用旧Route-A而自动切换threshold策略。

**Unknown：** 两算法在新consumer、不同计算组织和真实workload上的数值/质量、更新频率分布、
最坏live集合及统一低成本实现均未建立。R4对SnapKV/DMS的共同性证据可辅助定义身份/顺序，
不扩大本阶段已支持的算法范围。

## 3. Unified Sparse KV Abstraction

### 3.1 描述什么：集合语义、数据绑定与执行任务分开

**Proposed：** `SparseKVStateDescriptor`首先是软件参考中的逻辑对象，不是硬件包。
它描述特定流和生效区间内的准确可见集合。算法前端必须将算法特定的score、threshold、ranking、
tie行为和保护规则转换成canonical retention set；系统后端只消费实际selected records，
不得重新计算、近似选择，或按目标budget再次截断。

> **Proposed — interface rule:** Algorithm frontend is responsible for converting algorithm-specific
> scores, thresholds, ranking and protection rules into a canonical retention set. The system backend
> consumes the actual selected records and must not recompute or approximate the selection decision.

**Proposed：** Score不属于该接口的输入，不要求跨算法统一其数值含义。前端profile标识只用于说明
选择来源与语义，后端不根据它执行score-to-mask。算法诊断/质量研究可另行保留score，不能用诊断数据
替代已确定的集合；预算与ratio也不能代替实际mask/count。表示转换和集合核对不等于重新选择。

**Proposed：** 四个对象分开，责任方如下。Runtime通过共同的scope、record identity和版本将算法状态
与backing关联；算法对象既不包含物理HBM地址，也不包含`backing_view`引用、tensor指针或布局版本。
调度器再组合逻辑集合与数据绑定，生成任务和read plan。一个批次可携带多个流，不要求逐token命令。

| 对象 | 状态 | 回答的问题 | 责任方 |
|---|---|---|---|
| `SparseKVStateDescriptor` | Proposed | 哪些KV必须保留，何时对Attention生效？ | Algorithm frontend |
| `KVBackingView` | Proposed | 这些KV实际在哪里、什么布局、何时可读？ | Runtime / Memory Manager |
| `PackingTask` | Proposed | 如何将选中记录组织到目标布局？ | Software Scheduler |
| `AttentionReadPlan` | Proposed | 本次Attention读取哪一选择版本及哪些物理来源？ | Software Scheduler |

| 字段组 | 状态 | 最小含义 |
|---|---|---|
| `scope` | Proposed | Request/sequence实例、模型及算法profile引用、layer、KV head；不同请求实例不混淆 |
| `snapshot_version` | Proposed | 该scope内的不可变快照版本；不与物理layout版本或任务身份混用 |
| `selection_epoch` | Proposed | 前端产生/定稿选择的算法决策批次；FastKVzip可为跨layer/head的global compression epoch，KVzap可为该层hook决策事件；不要求数值等于snapshot_version |
| `decision_available_at` | Proposed | 选择决定何时已知；不能倒用于已完成的attention调用 |
| `effective_epoch` | Proposed | 新集合从哪个算法执行边界生效，以及作用的后续attention调用/query范围；多流可共享全局epoch，不是快照编号或DMA完成时间 |
| `update_kind` | Proposed | `APPEND`或`REPLACE`，描述与supersedes集合的关系；两者都携带完整snapshot，详见§3.3 |
| `record_ids` / `selected` | Proposed | 声明域内记录身份和完整可见mask，包含受保护项；也可用等价索引列表表达 |
| `original_positions` | Proposed | 与身份对应的原位置；与压缩后rank、内存地址分开。位置编码由profile说明 |
| `supersedes` | Proposed | 同一scope的前一snapshot_version；初始快照为空。不是物理数据销毁命令 |
| `traversal_order` | Proposed | 首版候选为保持原始相对顺序；如改变原实现遍历顺序，单独验证数值 |
| `semantic_requirements` | Proposed | 前端/模型声明的因果、位置、保护与必须保持的遍历约束引用；不包含选定Consumer、kernel参数或物理布局 |

**Proposed：** `KVBackingView`声明record到K/V源区域的映射、布局版本、shape/stride、dtype、
head_dim、K是否已经应用RoPE、位置来源、数据就绪依赖及存活承诺。规则布局优先用base/stride或
segment表达，确有需要时才用逐记录地址。描述字段是语义义务，不要求每层重复存一张宽表。

**Proposed：** `record_ids`明确声明域，`selected`与之逐项对应且长度相等，
`selected_count = sum(selected)`。索引列表表示必须无重复、指向同一声明域并保持约定顺序；
完整snapshot覆盖整个scope的可见集合，不能只给当前packing batch而省略其他仍合法的记录。

**Proposed：** 四种时间/版本明确分开：selection epoch标识算法决策，snapshot version标识适配器输出的
状态对象，effective epoch约束后续Attention，supersedes指向同scope的前一snapshot version。
例如两次compression之间新增受保护KV，可以产生新snapshot，而最近一次selection epoch不变。
实际Reader仍按具体调用确定完整集合，不能只在compression时更新一次snapshot并漏掉随后新增KV。

**Proposed（字段归属建议）：** 以上为最终推荐的逻辑字段草案，仍待Phase 1 Task 1确认；没有C/RTL ABI。

| 字段/事实 | 归属与责任方 | 不进入哪里 |
|---|---|---|
| Scope、完整selected set、record identity、original position、四种时间/版本及必要语义约束 | 算法接口；由前端Adapter输出，identity命名与Runtime对齐 | 不要求硬件保存全部长期snapshot |
| Record到K/V位置、content/representation与layout版本、shape/stride/dtype、RoPE provenance、ready依赖及存活期 | 系统数据管理；Runtime / Memory Manager的KVBackingView | 不回写到SparseKVStateDescriptor |
| 选定Consumer、Q/GQA绑定、数值标准、读取哪些区域/长度及准备方式 | Scheduler的AttentionReadPlan及其Consumer配置 | 不成为原算法的selection输入 |
| Batch、源/目标范围、mask/index引用、输出顺序/容量、依赖和完成身份 | Scheduler生成PackingTask，GPU或候选引擎执行 | 不携带重新执行score/ranking的义务 |

**Proposed（KVBackingView适配起点）：** KVzap当前规则源可用`[B,Hkv,T,D]`的tensor、stride与
显式identity映射定位；FastKVzip flatten源可用`cu_len_k[h] + local_rank`定位每head现存行。
这只是地址计算起点，local_rank不是原位置。两者的tensor指针/offset都只在Runtime侧保存。
FastKVzip布尔gather时，Adapter须对旁路identity/position映射施加同一原mask；不能从压缩后rank推回位置。
**Unknown：** 这些绑定在新Adapter中的完整性、数据就绪/存活和更新逻辑，须到Phase 2验证。

### 3.2 必须维持的解释规则

以下均为 **Proposed（新参考模型的正确性要求）**；必要性可由
[R4共同字段](../algorithm_reports/04_cross_model_and_frontend_boundaries.md)与
[H1语义/实现区分](../hardware_reports/01_architecture_and_software_hardware_boundaries.md)解释，尚无新实现PASS。

1. **身份稳定。** `record_id`采用§3.4的scope＋创建序号建议，不使用position、compact offset或地址直接冒充身份。
   同一record的K、V、position必须一起对应；迁移不生成新逻辑记录。
2. **集合完整。** 声明域与快照组合能够确定该调用需要的全部记录。未列入当前packing batch不表示DROP。
   `selected=false`、数据未就绪和未决策是不同事实；未决策但受保护项仍可visible。
3. **无隐式复活。** 选择必须有合法backing；已删除且没有保存的数据不能仅凭新mask重新产生。
   FastKVzip retained pool的历史删除不会由完整snapshot自动恢复。
4. **选择与布局分离。** Packing不能改变集合、原位置或规定顺序；算法epoch与layout版本分别管理。
   Snapshot版本也独立于两者。实际selected count从集合得到，不能从预算推测。
5. **生效边界明确。** 同一快照若不能正确描述多query的不同可见范围，就拆为多个区间或携带consumer可执行的mask；
   不把terminal prefill集合倒用于此前所有query。
6. **数据有效。** 被选择记录的数据必须已就绪，或有显式依赖；搬运及合法旧reader排空前不能覆盖源。
7. **表示等价另验。** Bitmap/index/segment间转换、重排和batching均验证集合与顺序，不能借机重算score改变mask。

### 3.3 完整Snapshot的更新规则与最小例子

**Proposed：** 第一版只传完整集合、`snapshot_version`、`selection_epoch`、`supersedes`、`effective_epoch`及上述语义字段。
不定义delta传输、独立的任意DELETE事件或多版本并发提交协议。每scope按supersedes链串行提交，
最多一个当前版本和一个待生效版本；未解决的前驱不能被后继越过。初始快照用`REPLACE`且supersedes为空。
不同scope可并行组织任务，不要求全系统只有一个版本。

| 更新类型 | 状态 | 完整集合语义 | 不隐含的物理操作 |
|---|---|---|---|
| `APPEND` | Proposed | 在相同scope的稳定record identity下，`S_prev ⊆ S_next`，可以增加记录但不得撤销旧selected；相同集合也满足此条件 | 不等于只传新增项，也不保证目标内存可以原地追加 |
| `REPLACE` | Proposed | `S_next`整体取代`S_prev`的逻辑可见集合，可包含新增、撤销或两者；由完整快照表达 | 不要求立即删除所有旧物理KV，也不要求所有新集合成员重新搬运 |

**Proposed：** 已启动旧reader可以在固定旧read plan下排空，不接受新的旧版本reader；
旧引用只因排空而短暂存活，不构成任意多版本并发提交。首版可保守等待旧reader结束后再完成下一轮
布局切换，软件参考先验证串行路径，不以支持多版本并行为前提。

**Proposed：** Scheduler可以按稳定身份计算交集`S_prev ∩ S_next`、新增`S_next − S_prev`和
撤销`S_prev − S_next`。这些集合差只用于布局与数据复用决策，不是后端重新选择。
首版允许out-of-place完整复制作为正确性基线；后续可研究复用交集backing、增量搬运新增项或按需
重整理。复用还要求K/V内容未改变、位置及编码关联一致、backing仍可读且版本匹配；相同record_id
本身不授权覆盖、复用失效地址或跳过必要布局转换。
**Unknown：** Consumer能否有效消费复用后的多个segment/含洞page、相关生命周期代价和净收益；
交集大不自动意味着少搬运，仍可能受目标布局约束。

**Proposed（说明性合成例子，不是实验）：** 省略共同scope，按原位置排列。

| 场景 | 前一快照可见记录 | 后一快照可见记录 | 系统要表达什么 |
|---|---|---|---|
| 无旧项撤销的更新 | `{0,3}` | `{0,3,6}` | `APPEND`仍传完整集合，不只传6 |
| KVzap式，window2 | 成熟保留`{0,3}`＋hot`{4,5}` | 成熟保留`{0,3}`＋hot`{5,6}`，4成熟DROP | 完整集合有撤销，因此用`REPLACE`；成熟cold仍可append-only |
| Mutable selection | 旧成熟`{a,b,c}`＋保护集合 | 新成熟`{a,c,d}`＋新保护集合 | `REPLACE`；交集a/c可研究复用，b从新plan移除，旧reader结束后才允许回收其无其他引用的backing |

**Unknown：** 最经济的snapshot编码、字段位宽、分片粒度、epoch提交方式和跨流协调尚未选定。
先保证Python对象能表达两例及真实前端，再决定哪些字段进入设备任务。

### 3.4 Record ID、Original Position、Compact Rank和Physical Address

以下均为 **Proposed（Phase 1 Task 1的身份规则建议）**，不是声称原生cache已有这些字段：

| 概念 | 推荐逻辑规则 | 何时改变 |
|---|---|---|
| Record ID | 完整身份为`(sequence_instance, layer, kv_head, record_serial)`；scope可提取前三项。serial在本序列创建KV时由Adapter分配/观察并保持，不复用 | 搬运不改变；另一次请求/执行轨迹使用新sequence_instance |
| Original Position | 该KV在模型原始序列中的位置，显式绑定到Record ID；位置编码的position_ids另按模型profile说明 | 搬运不改变；不能由compact rank反推 |
| Compact Rank | 某个layout version内该head的存储排列序号 | 筛选、重排或追加时可改变 |
| Physical Address | KVBackingView中的buffer/区域加字节offset；不固定为某种HBM地址编码 | 复制、分配或区域复用时可改变 |

**Proposed（合成示例）：** 同一scope的`r17`可具有original position1024，先在layout A的rank0/address A，
后在layout B的rank5/address B；ID和position不变。另一请求的position1024使用另一sequence_instance。
在当前普通线性序列中serial可以恰与position数值相等，但仅是Adapter的一种显式映射，接口不依赖等式。
首版不支持beam分支、回滚、共享prefix和原位置重算覆盖；出现这些操作时不能静默沿用旧ID。

**Proposed：** Runtime另维护K/V内容与representation版本。相同ID不证明地址仍live、数据未被覆盖，
也不证明不同dtype/RoPE表示可直接复用。记录内容若重新计算而变化，需要明确新执行实例/记录或版本规则，
不属于首版隐式行为。

**Verified（代码/历史trace）：** 当前FastKVzip生产cache没有本统一Record ID接口，研究
[prefill tracer](../../../FastKVzip/research/prefill_trace.py)与
[decode tracer](../../../FastKVzip/research/decode_trace.py)另行重建logical position。
**Unknown：** 首版Adapter能否完整旁路维护上述身份映射、对齐所有gather/append，尚未运行验证。

### 3.5 两个原算法的映射及独立derived policy

**Proposed（基于§2源码时点的映射示例；不是新执行结果）：**

| 输入路径 | Snapshot与更新 | 时间/版本映射 | 必须保留的原行为 |
|---|---|---|---|
| 原生KVzap/DMSPress，prefill后 | 全部mature KEEP与protected集合形成v0，`REPLACE/supersedes=null` | selection epoch=该层已完成hook事件；effective epoch=其后合法Attention调用；不能影响刚完成的attention | 原threshold、保护窗口、等号KEEP及原mask |
| KVzap Route-A policy研究profile | 保存的creation keep决策加当前hot规则形成完整集合；独立标明原mask重放来源 | pre-hook重放决策，append/maturity在当前policy数值attention前；不能套用原生post-hook的Effective Epoch | 只证明指定研究路径；不宣称两种调用时点是未经验证的原生等价实现 |
| KVzap，后续新增/成熟 | v1仍含完整集合；无旧selected撤销才用APPEND，成熟DROP导致完整集合减少时用REPLACE | supersedes=v0；新snapshot与新layout分开；不能仅输出本轮admission batch | Mature cold单调不等于全部visible set单调 |
| 原FastKVzip chunked prefill | Chunk完成后对本轮新成熟cohort选择，再输出完整现存selected＋保护集合 | selection epoch=该chunk后的prune；effective epoch=下一合法消费；v按scope编号 | 原global pair阈值和严格`>`；不把新集合倒用于过去prefill query |
| 原FastKVzip fixed-budget decode | Compression后v1完整替换v0，通常为REPLACE；两次compression间新增保护KV也更新snapshot | selection epoch=全局compression e；effective epoch=其后调用，执行compression的forward仍用旧集合；supersedes=v0 | 对当前retained pool选择、`>=`及实际ties；不能按nominal budget截断 |

**Proposed：** 首版统一表达层支持完整Snapshot、APPEND和REPLACE，初始任务切片用prefill后选择；
Phase 2软件参考还实现串行decode新增/替换的有界序列。支持“原FastKVzip映射”首先指原集合可被表达，
不代表新consumer或系统已验证支持完整官方生成流程。

**Proposed（独立算法profile）：** FastKVzip-derived fixed-global-threshold使用官方Gate但更换retention
policy；旧mature KEEP不撤销，以容量增长换取不同生命周期。它与官方fixed-budget使用不同profile身份，
记录独立mask/质量结果，不能作为后者的无害替换或为了后端兼容而默认启用。其完整visible snapshot
仍可能因保护项成熟DROP而REPLACE，不将“derived append-only cold”误写成全集合APPEND。
**Unknown：** F4初步校准之外的容量增长、任务质量与部署阈值；这些不阻止研究原始FastKVzip的REPLACE接口。

## 4. Attention Consumer Interface

### 4.1 调查依据与版本范围

**Verified（接口/代码）：** 本节查阅2026-11-13可访问的官方资料及本地FastKVzip源码。
FlashAttention以固定[v2.7.3 Python接口](https://github.com/Dao-AILab/flash-attention/blob/v2.7.3/flash_attn/flash_attn_interface.py)
及[C++检查](https://github.com/Dao-AILab/flash-attention/blob/v2.7.3/csrc/flash_attn/flash_api.cpp)为可复核版本；
这是FastKVzip README的推荐版本，非所有历史运行版本。
FlashInfer以[官方KV布局文档](https://docs.flashinfer.ai/tutorials/kv_layout.html)及
[Attention API](https://docs.flashinfer.ai/api/attention.html#flashinfer.decode.BatchDecodeWithPagedKVCacheWrapper)
为调查依据，所查文档标示0.7.4；网页可能随版本变化，实际实现前须选定版本。

**Verified（静态安装文件）：** 本地FastKVzip环境的
[`METADATA`](../../../FastKVzip/.venv/lib/python3.12/site-packages/flash_attn-2.8.3.post2.dist-info/METADATA)
记录2.8.3.post2，其Python接口也注明上述paged入口的256倍数要求。
安装文件版本不证明远程实验实际导入版本；不把README推荐版本当作历史运行环境。

**Unknown：** 本轮没有导入/运行这些库；代码接口存在不证明当前机器可运行、新布局已兼容或性能已建立。

### 4.2 真实输入布局与逐head稀疏的适配

下表为 **Verified（指定接口和源码）**；“需要适配”是接口形状的分析，不是新增运行结果。

| Consumer | 数据和控制入口 | 对本项目的含义 |
|---|---|---|
| FlashAttention `flash_attn_varlen_func` | Q为`[total_q,Hq,D]`，普通K/V为`[total_k,Hkv,D]`；`cu_seqlens_q/k`描述每条sequence的边界，另传max长度、causal等 | 同一sequence内的多个KV heads共享sequence边界；逐head独立长度需要适配 |
| FlashAttention `flash_attn_with_kvcache` | 普通cache为`[B_cache,S_cache,Hkv,D]`；`cache_seqlens`描述每sequence长度；可接受新K/V、位置相关参数及`block_table` | 标准入口不直接提供每个原始KV head独立长度数组；原位置不可由compact长度冒充 |
| 上述FA的paged入口 | 以`block_table`寻页，paged K/V为`[num_blocks,page_block_size,Hkv,D]`；v2.7.3要求page block size为256的倍数 | 旧Route-A P64不能假定逐页直接接入此版本；需选其他page几何、segment或明确转换 |
| FlashInfer ragged KV | NHD为`[sum(lengths),Hkv,D]`，`kv_indptr`按request划分；Q有自己的`qo_indptr` | Request变长不自动等于同request逐head独立变长 |
| FlashInfer paged KV | K/V可分开为`[pages,P,Hkv,D]`或HND；也可合并增加K/V维；以`paged_kv_indptr/indices/last_page_len`描述每request的页 | Page内部多个heads共享该request的页序列；需要选择适配方式，不能只凭“支持page”宣称可用 |
| FastKVzip当前prefill/flatten decode | 各KV head作为pseudo-sequence；K/V为`[sum_h Lh,1,D]`，Q为`[sum_h Qh,G,D]`，G为该KV head的query group；逐head累计长度传入FA varlen | 已有具体的GQA与逐head变长适配代码，可作为首个consumer候选 |

**Verified（本地代码）：** FastKVzip prefill的
[`EvictCache.prepare`及`_sample_cache`](../../../FastKVzip/prefill/attention/kvcache.py)
与[`llama_qwen_attn_forward`](../../../FastKVzip/prefill/attention/attn.py)，以及decode的
[`EvictCache.prepare`](../../../FastKVzip/math/method/kvcache.py)和
[`QwenLlamaAttention_forward`](../../../FastKVzip/math/method/modeling.py)负责reshape、逐head长度和FA调用。
两条路径的cache类同名但实现不同；所读adapter的长度元数据按KV head建立，不能由reshape中的bsz变量
推断已支持任意batch。首版限定batch1，batch-general适配属于Unknown。

**Verified（代码）：** Prefill的`update_flatten_view`在追加时复制旧segment并插入新行，
见[CUDA实现](../../../FastKVzip/csrc/csrc/cuda_api.cu)；decode flatten路径也有cache更新/重建工作。
因此只比较一次prune的gather会遗漏持续追加成本。该代码观察没有给出运行耗时或真实HBM事务量。

**Verified（官方API）：** FA的`cu_seqlens_q/k`为int32、长度`Nseq+1`，GQA要求Hq能被Hkv整除。
FlashInfer ragged wrapper通过`plan(qo_indptr, kv_indptr, num_qo_heads, num_kv_heads, head_dim_qk, ...)`
后`run(q, k, v, ...)`；paged decode wrapper通过
`plan(indptr, indices, last_page_len, num_qo_heads, num_kv_heads, head_dim, page_size, ...)`
后`run(q, paged_kv_cache, ...)`。其页指针/索引按所查文档为int32；这些是接口摘要，不是已执行的调用。

**Verified（官方布局）：** 标准`last_page_len`只描述末页尾部，前面的页按满页解释，不能表示任意
页内失效洞。**Proposed：** Mutable集合需要重整理，或使用consumer明确支持并验证的mask/索引适配，
不能仅修改有效数量就认为旧页已表达新集合。

### 4.3 Causal、位置及多来源消费

| 状态 | 要求或已知边界 |
|---|---|
| Verified（官方接口） | FA v2.7.3 causal mask在Q/K长度不等时按右下对齐，其判断基于输入sequence索引；sliding window也基于索引。它没有因此获知任意原始token间距 |
| Verified（代码） | FastKVzip所读模型路径先应用RoPE，再更新cache；已旋转K不能在新布局下按compact rank重新旋转并称等价 |
| Proposed | 首个compute probe用单query decode；所选KV的原position不晚于query，满足该profile选择/因果范围，K已正确RoPE；保留GQA与稳定原始顺序，独立核对同集合dense参考 |
| Unknown | 多token question/chunk、sliding window、相对位置bias及混合位置要求下，压缩索引的causal/window mask是否等价；需逐profile验证，必要时custom mask或拆分调用 |
| Proposed | 软件read plan显式列出protected/new与packed来源。首版可将其组织为一个consumer可接受的输入；为此新增的拼接/复制计费 |
| Unknown | 现有consumer能否直接消费这些来源而避免每步重建大tensor；若拆成多次attention，正确合并结果由谁完成、代价多少 |

**Proposed：** 输出候选同时保留“每head连续segment”和“每head页链”，不先冻结Page Formation。
首选调查FastKVzip现有varlen适配，再评估FlashInfer或FA paged变体；不同时实现全部consumer。
复用Attention不等于适配、mask、GQA重排和必要合并没有成本。

**Unknown：** 新consumer适配的数值标准与性能。Phase I各前端不同的ULP/FP32标准不能直接合并为
统一硬件精度；新路径须预先声明比较容差，保留失败，不能因最终argmax相同便宣告所有数值检查通过。

### 4.4 Attention Consumer Capability

**Proposed：** 以下表格面向系统选型：左列是需要的能力，中列只登记现有证据，右列明确新架构仍待验证
的部分。官方API或旧adapter有代码不等于新backend已经运行通过；`REPLACE`尤其是系统交接责任，
不是声称Attention库存在同名原生操作。

| Consumer能力 | 已具备的证据及状态 | 新架构需要验证的内容及状态 |
|---|---|---|
| Per-head variable length | Verified（代码）：FastKVzip batch1的head-as-sequence适配、逐head累计长度和FA varlen调用 | Unknown：新输入/布局下独立运行与数值对应、空head处理及适配开销；任意batch支持未建立 |
| GQA | Verified（代码/API）：每条pseudo-sequence一个KV head、G个query heads；FA有对应GQA接口 | Unknown：不同head长度下的query归属、输出还原、正确性和实际复用/性能 |
| Original position preservation | Verified（代码）：FastKVzip先按模型原位置RoPE后保存K；本文§4.3列出索引/位置区别 | Unknown：新布局中K/V/身份/position的完整对应，多query、window/bias以及是否需传输position sidecar |
| Multiple segments | Verified（接口边界）：ragged的多条sequence不能直接当作同一query的多个来源；本项目尚无共同多segment合同 | Unknown：是否拼接复制、映射成pages或分次计算/合并，正确性及准备/合并成本 |
| Paged KV | Verified（官方API）：FA/FlashInfer有paged入口和各自页表/几何约束，见§4.2 | Unknown：逐head稀疏适配、page大小、尾页/失效洞、GQA及实际服务效率 |
| Decode append | Verified（代码）：FastKVzip有更新与长度维护，所读flatten追加会复制旧segment | Unknown：能否避免重复复制历史数据，并保持长度、位置、read plan和数值正确 |
| `REPLACE` | Proposed：完整snapshot替换及completion/read-plan交接，见§3.3/§5 | Unknown：交集复用、旧/新backing与Attention的安全交接、失效记录排除和实际更新成本 |

**Proposed：** Head-contiguous优先复用现有varlen适配，Segment-based必须先解决同一query跨segment
消费，Page-based必须满足所选consumer的页几何与逐head映射。三者按上述能力及实测/模型中的
追加、重整理、适配和生命周期成本选择；本表不提前宣布某一布局胜出。

### 4.5 Phase 1 Task 2的首选建议及适配边界

**Proposed（明确的首选，尚未运行验收）：** 使用`flash_attn_varlen_func`，复用FastKVzip的
head-as-sequence方法；首选布局为Head-contiguous：每层K/V按KV head顺序紧凑排列，每head内部保持
所选记录的原始相对顺序。首个实例为batch1、Qwen3-8B、BF16、单query full-context decode，K在写入源时
已按模型原position完成RoPE；不要求重新执行裁剪前的prefill attention。

| 接口项 | 状态 | 首版建议 |
|---|---|---|
| Q与GQA | Proposed | Hkv条pseudo-sequence，每条一个KV head、G个query heads；Q为`[Hkv*Lq,G,D]`，首轮Lq=1；query-head按原模型group对应并还原输出 |
| K/V | Proposed | `[sum_h Lh,1,D]`；两者使用同一record顺序、有效长度与位置绑定；不是将每条KV复制G份 |
| 长度metadata | Proposed | 逐head int32 `cu_seqlens_q/k`及max lengths，与真实行数对应；准备/host scalar同步成本在Phase 2记录 |
| hot/new与cold | Proposed | Scheduler先按准确snapshot形成每head的一条完整输入；不同backing的数据显式gather/拼接到目标，计入复制，不能把多个独立sequence当成一个softmax |
| 位置与因果 | Proposed | 所选position不晚于query并满足前端scope；已旋转K不重新RoPE，压缩长度不冒充逻辑position；多query/window/bias扩展另验 |
| 空head | Proposed | 抽象允许零selected，首版adapter显式检测并报告；Consumer若未验证零长度则拒绝该执行profile，不凭空保留KV或静默改mask |

**Verified（代码＋历史执行）：** FastKVzip已有该类具体adapter，F2原生trace-off/on实验实际覆盖了
相应路径并记录prepare metadata检查。**Unknown：** 本统一descriptor/backing/read plan生成的新输入
与独立same-set dense reference的数值对应和性能；既有F2不能替代新adapter验收。

**Proposed（必要适配工作，Phase 2才实现）：** 原选择旁路输出→绑定稳定identity/position→生成每head
长度和排列→准备已RoPE的K/V及相应Q/GQA→调用varlen→还原query-head输出；原输入/mask独立构造dense
reference。记录每次tensor分配、gather/concat、重建和scratch，不因复用现有kernel而省略准备费用。

**Verified（所查接口/代码）：** 当前普通varlen路径的cumulative lengths界定紧密排列的head segment；
所查本地2.8.3.post2接口没有独立`seqused_k`参数来自动跳过任意预留空洞。
因此“每head预留容量、只追加新行且保持同一紧凑输出”不能直接假定成立。
**Proposed：** Phase 2的Persistent Incremental方案必须记录维持紧凑边界的重建；或明确作为
`with_kvcache`按pseudo-sequence预留容量/长度、paged等Consumer/布局变体独立比较。
后者不能与相同输出格式的微kernel对照混算，padding、准备和同步仍计费。

**Proposed：** Phase 1 Task 2结束时应交付此首选的shape/stride/dtype、长度/GQA/位置说明、准备步骤及限制，
同时保留Segment/Page备选的适配清单。它是设计选型，不是断言所有能力已经运行通过或布局全局最优。

### 4.6 Attention Consumer Specification：提交审阅版本

**Proposed（设计结果，不是运行PASS）：** 首版采用FastKVzip已有组织方式调用
`flash_attn_varlen_func`。此表将§4.5的首选落实为一个具体Consumer profile：

| 参数 | 首版规格 | 依据/证据边界 |
|---|---|---|
| 工作范围 | Batch1，逐layer，Qwen3-8B，BF16，D=128，单query decode/full-context | 模型/code已有该维度；新路径执行属Unknown |
| Q输入 | `[8,4,128]`，连续元素stride `(512,128,1)` | 8个KV-head pseudo-sequence，每个GQA group4个query heads |
| K/V输入 | 各为`[sum(Lh),1,128]`，连续元素stride `(128,128,1)` | Head-contiguous目标；源可以不连续，准备复制需显式列出 |
| Head长度 | `Lh>0`；CUDA int32 `cu_seqlens_k=[0,L0,L0+L1,...]`，shape `[9]` | 现有EvictCache.prepare的组织；零head暂不纳入首版执行profile |
| Query长度 | CUDA int32 `cu_seqlens_q=arange(9)`，`max_seqlen_q=1`；`max_seqlen_k=max(Lh)` | Max scalar准备/同步费用以后记录，不假定免费 |
| 算术参数 | dropout0、causal=True、full window、scale=`1/sqrt(128)`；不启用ALiBi/softcap | 原模型full-context单query范围；滑动窗口/位置bias另验 |
| 输出 | `[8,4,128]`还原原32个query heads；`query_head=4*kv_head+consumer` | 保持GQA绑定，不将KV复制四份 |
| Position | Original position在Runtime identity映射中；K已经原位置RoPE，按相同值搬运 | 首版kernel不需要新增8 B/record位置输入；不等于系统可以丢掉位置 |

**Verified（源码依据）：** [prefill准备](../../../FastKVzip/prefill/attention/kvcache.py#L204)、
[decode准备](../../../FastKVzip/math/method/kvcache.py#L166)、
[原始位置RoPE与调用](../../../FastKVzip/math/method/modeling.py#L45)、
[varlen及输出还原](../../../FastKVzip/math/method/modeling.py#L119)，以及
[本地2.8.3.post2接口](../../../FastKVzip/.venv/lib/python3.12/site-packages/flash_attn/flash_attn_interface.py#L1370)。
上述stride是拟形成连续目标时的形状计算，不声称所有现存源tensor已有相同stride。

**Proposed（固定准备次序）：** 绑定本次真实完整snapshot与query→定位每head全部合法cold/protected/new
记录→按规定顺序gather/concat成连续K/V→建立identity/rank对应与实际Lh→准备Q/GQA及长度→等待ready→
调用varlen→还原输出→Reader完成。多个独立源不能通过多个sequence条目变成一个联合softmax。
Prefill后选择只影响其合法生效边界之后的消费，首版不重新计算全部历史prefill attention。

**Proposed（Phase 2预先声明的比较规则）：** 搬运前后K/V、ID、position必须与原selected records独立
索引得到的结果精确一致。Attention固定同一Q/原selected K/V，使用固定参考算法：关闭TF32，
FP32内部计算且先缩放Q的dense结果记为`R32`，`O_ref=R32.to(BF16)`；执行dtype PyTorch baseline
`O_pt`采用下述官方`attention_ref(upcast=False, reorder_ops=True)`算法（缩放K、相同mask/GQA），
不能故意换成误差更大的baseline。Dropout0、无bias/window，softmax及输出cast遵循该参考算法。
R32另保留作FP32诊断；BF16误差门槛比较的是三个BF16输出提升到FP32后的值：

```text
E_fa = maxabs(O_FA - O_ref)
E_pt = maxabs(O_pt - O_ref)
require finite outputs AND E_fa <= 2 * E_pt
```

**Verified（规则来源）：** [FlashAttention v2.8.3官方测试](https://github.com/Dao-AILab/flash-attention/blob/v2.8.3/tests/test_flash_attn.py)
的`attention_ref`和测试断言提供上述算法及相对误差依据；其upcast参考最终也返回原dtype。
**Proposed：** 本profile逐测试例使用该门槛，并另报逐head、
max/mean absolute error和ULP诊断；`E_pt=0`时不静默加floor。FP32参考构造不能从候选状态导出全部数据。
这不是历史16-ULP合同的改写，也不是应用质量保证。**Unknown：** 新路径能否通过；失败时保留原失败，
不能事后放宽门槛而仍称同一次验证通过。

## 5. System Requirements

### 5.1 软件必须维护的最小状态

下表均为 **Proposed**；这是功能责任清单，不要求每项各建一个模块或逐token大目录。

| 状态 | 最小用途与存活期 |
|---|---|
| Selection state | 每scope的当前/至多一个待生效完整snapshot、版本、supersedes与effective_epoch；串行提交，旧reader仅保留固定旧plan排空 |
| Backing/layout state | 源与目标区域、版本、每head长度/offset或page列表、尾部有效数、位置绑定、数据就绪依赖 |
| Allocation state | 目标容量与scratch预留、所有权和待回收区域；不假设原tensor一删mask就释放 |
| Packing state | 未提交/在途/完成/失败task及依赖；有限队列满时工作留在谁处 |
| Attention read plan | 为具体调用选定准确集合和可读backing、consumer布局及准备成本；发布后对该reader保持稳定 |
| Reader/completion state | 尚在使用的旧plan、搬运读和attention读完成事件；用于安全回收 |

**Proposed：** 软件可用事件、版本化对象或等价方式跟踪责任，具体机制后续选择。
尚未packed的合法记录继续保存在源backing；不要求完整硬件Pending FIFO。
新协议关闭已排空任务/epoch，不继承旧wrapper的无限late lookup。已关闭与从未存在分开处理，
也不能由“当前组未包含该记录”推断其非法。

**Verified（历史依据）：** [H2](../hardware_reports/02_rtl_implementation_and_sustained_execution_scope.md)
区分长期页、临时S2服务、组工作区及journal寿命；admission budget限制单次服务量，不能代表总pending。
[H3](../hardware_reports/03_storage_measurement_boundary_and_complete_cost.md)区分信息、接口和物理表示成本。

**Proposed（对新系统的职责判断）：** 下列正确性责任仍要落实，旧实现形式不自动继承。
旧形式的事实依据为[H1](../hardware_reports/01_architecture_and_software_hardware_boundaries.md)至H3，
新形式尚未实现或证明更经济。

| 必须承担的责任 | 旧Route-A形式 | 本阶段允许重新选择的实现 |
|---|---|---|
| 保留且未整理的记录仍可读 | Hot/pending/packed及direct pending endpoint | 源tensor/segment与软件read plan，不要求三个物理模块 |
| 选择与物理布局对应 | R3逐成员关联、M2/P3及R5联动 | 软件编译的任务与版本化布局，不默认两张36×64 compact表或opaque64字段 |
| 新数据就绪后才切换读取 | 固定metadata publication与跨owner交接 | Task completion＋内存可见性＋软件read-plan发布 |
| 页/区域回收不影响合法读取 | 硬件R5分配、generation与reclaim | 软件分配/回收加局部在途保护，不要求完整硬件Page Manager |
| 不把旧引用误认成新对象 | 精确journal与旧接口的late lookup历史 | 明确对象存活区间、版本匹配和关闭边界，不保存无限任务历史 |
| Attention按正确集合计算 | 分源partial/R4协议与外部数值服务 | 先复用已选consumer；必要的适配/合并仍须实现和计价 |

### 5.2 Task与完成交接

**Proposed：** 软件生成batch-level `PackingTask`，最少包含：任务身份、源layout版本、selection
snapshot或mask/index引用、K/V源布局、目标区域/容量、各流边界、目标布局与顺序、源就绪依赖。
算法descriptor与backing的关联在scheduler侧完成，物理源/目标不回写到算法对象。
软件可以一次提交多个layer/head任务；不要求每token host往返。首版out-of-place，不支持原地覆盖、
任意取消或自动重试；后续确有收益再扩展。

**Proposed：** 任务身份绑定不可变的snapshot_version、selection_epoch、effective_epoch及源/目标layout版本；mask/index自身在任务结束前
也保持稳定。迟到或不匹配completion不能发布已经复用的目标或新版本，不预先规定ID位宽或永久历史表。

**Proposed：** Completion最少报告task身份、写完成/失败、各流实际输出数、写入范围及visibility依赖。
`WRITE_COMPLETE`与Consumer可见性分开：只有所需K/V及侧信息已完成写入、且目标对Consumer可见，
才满足用于发布的成功条件（§5.7）。仅接受写请求或发完最后一个beat不足以发布read plan。
具体硬件done与系统fence如何组合属于Unknown。

**Proposed：** 首个参考交接顺序如下。可用软件屏障实现，无须复制旧跨owner事务网络：

```text
绑定准确snapshot，等待源就绪并固定源存活期
  → 预留独立目标，提交task
  → 搬运完成，目标写入满足可见性要求
  → 核对完成身份、count、范围及输出语义
  → 在算法允许的边界发布新read plan
  → 等待旧reader和搬运读均结束
  → 释放不再被引用的旧区域和任务状态
```

**Proposed：** 故障不发布半成品，保留可恢复的合法源；缺失所选数据显式报错。
有限队列满则延迟接收并由生产者保持任务，不能静默丢弃。未支持的consumer/profile显式拒绝，
不通过Full-KV fallback伪装成同集合执行。

### 5.3 算法epoch与异步搬运的关系

**Proposed：** Packing完成时间不能推迟算法要求的删除。FastKVzip新epoch生效后，新Attention
必须读取新集合：可从旧backing精确筛选，也可等待新packed输出就绪；这两种方式的成本分别记录。
此前合法启动的旧epoch reader按既定边界排空。旧源的回收同时受gather与旧reader约束。

**Proposed（合成检查例子）：** E0集合为`{a,b,c}`，E1为`{a,c,d}`。E1 packing等待期间，
若E1 reader仍直接读取完整E0，就错误保留b且遗漏d。新布局未就绪时应精确绑定a/c/d的源或等待，
不能以“物理整理尚未完成”为理由继续使用旧mask。若d源未就绪，则reader有显式依赖。

**Unknown：** 多流global selection与逐layer消费怎样同步、可重叠多少工作，以及软件目录/事件的
代价。这里的正确性要求不预设所有layer必须同拍提交，也不允许软件提前使用未来决策。

### 5.4 策略、账本与首轮验证

**Verified（离线模型）：** [R2](../algorithm_reports/02_packing_scheduling_and_amortization.md)
已给出短输出亏损、高cap仍早停、延迟启动仍有负前缀等反例；max_new_tokens不是最低剩余长度。

**Proposed：** 在线策略只用当前/历史状态及明确外部承诺。Trace未来可用于事后账本和oracle诊断，
不能作为在线策略输入。每个策略分支演化自己的布局、任务和已付成本。记录至少包括：

- Task数量、批量、等待时间、每流selected数、源读/目标写、索引/位置/目录及追加重建工作。
- 每次Attention读取的准确集合、字节、适配工作，以及初始化、warm-up、drain和真实依赖。
- 峰值容量`old backing + new backing + scratch + metadata`，包括搬运期间的副本。
- 启动与持续成本、逐前缀回本、短输出/少保留/偏斜等亏损场景；并行阶段按依赖和资源竞争计算完成时间。

**Proposed：** 逻辑payload bytes、按声明粒度估算的事务和实测HBM计数分别记录；Python账本不能
称为真实HBM流量。引擎吞吐上界、仿真完成时间、GPU实测和系统估计也使用各自的证据标签。

**Proposed：** 软件参考的首轮检查直接服务于下一步实现，不另建复杂验证体系：

| 检查对象 | 需要观察的结果；均为未来验证，尚未执行 |
|---|---|
| 集合与数据 | 从原输入和原mask独立构造参考；K/V/position不漏、不重、不串head，不只从候选状态导出对照 |
| 输入边界 | 零/全保留、不同head长度、尾部、保护项成熟及实际count与名义预算不一致 |
| Snapshot更新 | APPEND仍是完整快照且不得撤销旧selected；REPLACE表达撤销但不强制全量物理删除/搬运；版本/supersedes串行，生效前后reader使用准确集合，不复活已删除数据 |
| 连续任务 | 无reset多批周转；completion延迟、队列背压时不提前发布，不覆盖在途源 |
| Consumer | 先验证单query、GQA及位置处理，再扩展多query；按预先声明的数值标准比较 |
| 资源/失败 | 峰值副本与scratch可解释；目标不足、缺源、失败任务显式停止或报告，不静默放宽选择 |

**Proposed：** Phase 1的目标是语义、接口调查与需求定义，当前设计已提交审阅（§8），尚未冻结。达到§7交接条件后，
Phase 2才实现上述小规模参考和GPU对照，不要求先验收RTL。若Consumer必须大规模重建或无法保持
因果语义，应明确回修布局/接口；若测得瓶颈不在搬运，则调整硬件假设，不默默扩大模块范围。

### 5.5 Phase 1 Task 3的职责与首版执行合同

以下均为 **Proposed（职责建议，待Phase 1确认）**，不是已接入GPU的专用硬件系统：

| 角色 | 首版职责 | 保留在边界外的工作 |
|---|---|---|
| CPU / Host | 选择request/profile、粗粒度packing策略、资源预算、分配/回收策略与实验配置 | 不默认每step把全部layer/head mask/count取回CPU再逐token往返 |
| GPU Device Runtime | 在设备侧衔接原算法最终选择，维护tensor紧邻identity/位置/长度映射，准备mask/index、backing、batch task/read plan，提交GPU操作与事件依赖 | 不改变原score计算组织或selection；Phase 2可先做直观参考，再分离计时区的高频实现 |
| 候选专用引擎 | 执行有限batch中的索引、gather/整理/写出，局部buffer/credit与准确完成/错误 | 不承担全局selection、完整Page Manager、无限late-query journal或请求级生命周期 |
| HBM / Memory Infrastructure | 接受声明范围内的读写、顺序与完成/visibility服务，仲裁共享带宽 | 地址可达性、一致性、PHY与外部引擎接入尚未实证；不是免费额外端口/带宽 |
| Existing Attention Engine | 等待ReadPlan就绪，按query/GQA/因果配置读取并报告Reader结束 | 不替Scheduler选择KV或维护全局目录；输入准备与数值边界不自动解决 |

**Proposed：** 一次`Batch-level PackingTask`可包含多个layer/head的有限工作，明确各子流的snapshot、
源/目标和count。首版按批串行，目标预分配，out-of-place；不要求跨批重叠、任意取消、原地覆盖、
复杂journal或多组并发生命周期。多个任务依次无reset周转属于Phase 2正确性范围，不等于多组并发。

**Proposed：** 首版软件以`source-ready → submitted → writes-complete → consumer-visible → plan-published
→ old-readers-drained → reclaimable`描述执行阶段；这些名称不规定硬件FSM。Phase 2使用真实GPU
stream/event建立依赖，先采用保守串行次序；task失败或缺少visibility时不发布目标。
已发生的REPLACE必须在新reader前按准确集合处理或等待，不能用旧plan继续计算新epoch。

**Proposed：** `AttentionReadPlan`最少绑定query调用/原position范围、snapshot version、selection/effective
epoch、consumer配置、K/V backing/layout版本、逐head长度/遍历与ready依赖；Reader结束后交还引用。
它回答“本次读什么与从哪里读”，不参与重新选择。部分旧源仍由新plan复用时，只回收没有任何reader、
gather或新plan引用的区域。

**Unknown（部署）：** 主要候选是专用引擎与GPU/Attention共享HBM地址域；尚无选定平台证明可达性、
GPU cache可见性、DMA fence和仲裁。Phase 2 GPU内核可验证软件次序，不能因此宣称未来引擎completion
已实现硬件—GPU可见性。Phase 1必须登记该假设及若不成立时的复制/互连代价，不能默认平台支持。

### 5.6 Minimal PackingTask与AttentionReadPlan：Phase 1设计结果

**Proposed（提交审阅的逻辑接口v0，非可执行调度器/硬件ABI）：** 一个batch包含有限个stream工作，
每个stream必须与一个完整snapshot精确关联；首版全batch完成后统一发布，不做部分成功发布或跨批并发。

| PackingTask字段 | 必须表达的事实 | 产生/保持者 |
|---|---|---|
| `task_id` | sequence实例＋本实例单调batch序号；在途及未消费完成结果期间不复用 | Scheduler；执行者回传原值 |
| `snapshot_refs[]` | scope、snapshot_version、selection/effective epoch的不可变引用；对应原selected集合 | Algorithm Adapter提供集合，Scheduler绑定 |
| `source_views[]` | KVBackingView对象/内容/布局版本、K/V区域和record定位方式；包括mask/index数据自身的存活 | Runtime / Memory Manager |
| `source_ready[]` | 数据生产完成与执行所需可读性的依赖，不是“已分配buffer” | Producer / Runtime提供，执行前满足 |
| `selection_views[]` | 完整snapshot选中记录的等价有序bitmap/index视图；逐stream边界与实际count | Device Runtime生成，不重新排序score或截budget |
| `destination` | 独占、预留的K/V目标区域、容量、目标layout版本；首版与所有源范围分离 | Runtime分配，Scheduler编译 |
| `output_contract` | Head-contiguous、原始相对顺序、dtype/head_dim、逐head预期输出count及必要身份/位置关联 | Scheduler；Consumer规格约束 |
| `completion_ref` | 回传队列/事件槽的逻辑引用；能够唯一匹配此task，保持至Runtime接收 | Runtime/执行者，不规定门铃或总线 |

**Proposed：** `KVBackingView`的最小绑定是`(view_id, content_version, layout_version, scope/record_map,
K/V buffer+offset/stride/shape/dtype, RoPE_provenance, ready_dependencies, lifetime_owner)`。
这些字段都在Runtime侧。ID相同但内容、编码或存活版本不一致时，不能复用旧字节。
首版不设计统一物理地址位宽、页表或逐token硬件目录。

| AttentionReadPlan字段 | 需要的约束 | 责任方 |
|---|---|---|
| `plan_id / query_binding` | sequence、layer、调用号、query原position与GQA query→KV head映射 | Scheduler由模型调用绑定 |
| `snapshot_refs[]` | 本次调用使用的准确选择版本/生效边界，不能读入已撤销记录 | Scheduler |
| `consumer_profile` | §4.5首选的形状、dtype、scale、causal/window/position约束和输出还原规则 | Consumer Adapter配置 |
| `read_views[] / lengths` | 精确K/V backing/layout版本、各head长度和累计长度、顺序；首版每head形成一条连续序列 | Runtime绑定、Device Runtime准备 |
| `ready_dependencies` | 完整目标或精确源输入达到consumer-visible；准备gather/concat也在依赖内 | Runtime；Attention等待 |
| `reader_completion_ref` | 这次消费何时真正结束，用于释放plan及backing引用；launch/accept不等于完成 | Attention执行侧回报，Runtime回收 |

**Proposed：** 第一版允许计划生成时尚未ready，但禁止执行或发布为可消费plan；所有长度/位置映射必须
与引用snapshot对应。Hot/new与cold来自不同区域时，计划列出准备复制，直到一条合法连续输入形成才调用
首选Consumer。不能仅增加多个`cu_seqlens`条目替代同query的多源合并。

### 5.7 Completion、Visibility与回收的最小执行合同

**Proposed：** 执行者回传`Completion(task_id, snapshot/layout refs, WRITE_COMPLETE|FAILED,
actual_counts, written_ranges, visibility_dependency)`。`WRITE_COMPLETE`要求本任务全部目标写实际完成，
不是只发出请求；它与GPU能否看到这些字节仍是两个事实。用于发布的成功条件为：

```text
Publishable = matched_completion
           AND status == WRITE_COMPLETE
           AND counts/ranges == output_contract
           AND visibility_dependency_satisfied
           AND snapshot_is_next_for_its_effective_boundary

Reclaimable(source_region) = no_inflight_gather_read
                         AND no_old_reader
                         AND no_published_or_pending_plan_reference
```

**Proposed：** 首版顺序为：固定snapshot/源及mask-index存活→等源ready→预留独立目标→提交整批→
匹配写完成→满足Consumer可见性→发布新plan，阻止新发起的旧版本reader→已有旧reader与gather排空→
只回收无引用区域。可先停止新旧reader并等待排空后再切换，保守串行实现不要求硬件支持并发版本。

**Proposed：** 失败、错误count、错版本/迟到completion、目标不足或visibility未知均不发布；缺少合法
源时显式失败或等待依赖，不退回不同集合的Full-KV。有限入口满则producer保持未接收task。
REPLACE只影响新plan的集合；旧reader继续其合法旧plan，交集backing仍被引用时不能整体释放。

**Unknown：** 未来硬件的visibility token由何种平台fence/cache协议实现。Phase 2可用GPU stream/event
验证GPU域内次序，不能因此把设备外引擎—GPU的一致性标为Verified。该合同也不证明当前已有任务队列、
生命周期状态机或故障恢复实现。

**Verified（软件API依据）：** [PyTorch v2.7.0 Stream/Event源码](https://github.com/pytorch/pytorch/blob/v2.7.0/torch/cuda/streams.py)
定义record、wait、query/synchronize等接口；wait约束随后提交的工作，不等于CPU已经等待完成。
**Proposed：** Phase 2据此实现GPU域内ready/drain依赖；该API证据不覆盖候选引擎的共享地址或cache协议。

## 6. Initial Hardware Hypothesis

### 6.1 候选能力及需要证明的作用

**Proposed：** 主要候选为 **Sparse KV Compaction Accelerator**，在已声明的共享内存条件下
执行软件编译的有限搬运任务。下表是可选择的能力，不要求全部集成，也未选定prefix-sum、lane数、
page大小、buffer容量、端口或频率。

| 候选能力 | 状态 | 要检验的收益假设与代价 |
|---|---|---|
| Mask/index processing | Proposed | 若bitmap为原生输入，减少GPU端扫描/索引生成；若前端已有indices，比较直接索引入口，避免重复compaction |
| Parallel gather | Proposed | 对逐head离散记录保持足够在途读与有效带宽；代价包括地址生成、顺序恢复、buffer和互连 |
| Stable compaction | Proposed | 按规定顺序排出K/V及必要位置；prefix-sum、分块计数或其他网络由输入与代价决定 |
| Segment/page formation | Proposed | 直接产生选定consumer需要的布局；只有page确有价值时才增加页形成逻辑 |
| Burst-oriented write | Proposed | 合并连续目标写、处理尾部并与下一批重叠；评估burst利用率和额外padding，不假设源随机读也自动连续 |
| Local task/buffer control | Proposed | 有限队列、buffer credit、传输完成和错误处理；软件全局管理仍需要硬件准确报告在途事实 |

**Proposed：** 全局Page Manager、长期pending/journal、全局selection、复杂metadata事务、请求级调度
以及专用Attention partial/merge优先由软件或既有设施承担。确有必要的局部仲裁、边界检查、保持状态和
在途完成仍由引擎负责；其成本不能随职责迁移被删除。

### 6.2 尚未验证的关键假设

| 问题 | 状态 | 后续需要的证据 |
|---|---|---|
| Gather是否是主要瓶颈 | Unknown | 合理GPU基线的分项测量；区分selection、索引、payload移动、cache追加及提交同步 |
| 输入不规则性如何落到事务 | Unknown | 基于真实K/V布局、记录大小、run-length、stride及head偏斜的请求/事务统计；不把token不连续直接当作每个标量随机读取 |
| 专用硬件是否优于GPU | Unknown | 相同选择与输出语义，匹配或明确归一化的存储条件；GPU实测与引擎模型/综合分别报告 |
| 搬运能否与Attention重叠 | Unknown | 软件依赖、源/目标生命周期、共享HBM争用与consumer时间模型；不能把两个峰值带宽独立相加 |
| 节省SM能否改善系统 | Unknown | Packing占用和实际并发工作/调度证据；单独少用SM不自动等于更快decode |
| 动态能量和面积是否值得 | Unknown | 真实buffer/端口/外围、索引/目录访问、搬运及同步活动，区分共同设施与增量；不同工艺proxy不直接相加 |

### 6.3 进入架构/RTL前的研究判断

**Proposed：** 首先完成“canonical选择 → 软件task → GPU packing/consumer”的可执行切片，
定位瓶颈并量化专用引擎可改善的空间。可在consumer允许时增加不做持久packing的稀疏读取诊断对照，
检验一次性搬运是否必要。旧Python Route-A用于语义参照，其性能不作为强GPU基线。

**Proposed：** 后续硬件功能应说明改善了哪个被测瓶颈、代价和适用条件；若GPU路径已经接近可用
带宽且卸载/能量价值不足，或consumer转换吃掉收益，应缩减/改变候选而非继续堆叠RTL。
首个RTL至少覆盖多个任务连续周转、真实数据对应和完成交接，避免再次只证明一次首次使用。

**Unknown：** 本阶段没有新的软件原型PASS、GPU吞吐、完整引擎面积/时序、动态能量或端到端收益。
这份定义确立了后续检验的对象，不构成硬件实现或性能承诺。

## 7. Phase 1 / Phase 2研究规划、交接与验收

### 7.1 Phase 1的三个任务：设计与需求定义

以下保留任务要求，设计内容均为 **Proposed**；实际调查/设计交付及当前验收见§8。
所有结果继续更新本文，不另建重复报告。

| 任务 | 输入与具体工作 | 必须交付的设计结果 | 本任务的验收界限 |
|---|---|---|---|
| Task 1：Algorithm Abstraction Interface | 阅读原论文/当前policy与真实mask结构；逐字段核对§3，讨论importance estimation与retention policy的差异、完整snapshot作用域和四类身份 | 推荐逻辑字段及归属；KVzap/原FastKVzip映射；derived policy独立说明；初始/APPEND/REPLACE与选择/生效示例；首版identity分配/映射规则 | 能用不改变选择的同一逻辑接口解释两个原算法。仅完成字段表不算完成，scope、时间及ID歧义必须有明确建议/限制；无须实现Adapter |
| Task 2：Attention Consumer Interface Investigation | 核查EvictCache、FA varlen/kvcache/paged和FlashInfer ragged/paged实际shape/调用；比较三种布局及位置、GQA、因果和追加 | 至少一个首选Consumer和布局（§4.5），输入/输出形状、必要数据准备、可能复制点、数值比较方案、已实现/API可表达/新适配未验的能力表 | 首选有源码依据，能给出从backing到Consumer的具体步骤；不能仅列API名。新适配运行与Benchmark留到Phase 2 |
| Task 3：System Responsibility and Execution Contract | 明确Host/Device Runtime/引擎/既有服务的职责；梳理串行batch与源/目标/Reader生命周期 | §5的职责、任务字段、Completion/visibility、read-plan发布/回收次序；首版支持/排除项；共享HBM及平台Unknown | 每个交接事实有责任方，故障/未就绪不能被当成功；平台未落定可保留Unknown，但不得暗中假设免费可见性或搬运 |

**Proposed：** Task 1与Task 2可并行调查；Task 3根据两者形成合同，然后回查字段/Consumer是否自洽。
阶段内允许小型逻辑示例和手工接口走查，不启动完整软件原型、模型、GPU Benchmark或RTL。

### 7.2 Phase 1验收清单与当前状态

下列为 **Proposed（阶段验收标准）**；当前设计检查结果集中在§8.6。
未勾选表示尚未作为整个阶段审阅确认，不表示本轮未执行调查。

- [ ] **统一表达：** 明确最终selected set是唯一选择输入；KVzap与原FastKVzip有完整scope映射，
  所需protected/new均在可见集合内；derived policy有独立身份和质量边界。
- [ ] **集合更新：** APPEND/REPLACE均为完整Snapshot；snapshot/selection/effective epoch与supersedes
  分开，明确何时可发布；不引入独立DELETE或多版本并发提交。
- [ ] **身份规则：** Record ID/Original Position/Compact Rank/Physical Address及内容/布局版本的责任
  明确，已有源能如何提供/旁路维护identity和position有具体方案，不从rank臆造原位置。
- [ ] **消费布局：** 首选Consumer、Head-contiguous输入、GQA/长度/位置/causal范围和数据准备步骤明确；
  跨segment、paged、append重建及空head限制可解释，待Phase 2验证内容列明。
- [ ] **执行合同：** CPU/Device/引擎职责、batch task、源pin、Completion与visibility、read-plan切换及旧源
  最后使用点明确；单请求、prefill后、out-of-place、串行批范围和排除项一致。
- [ ] **后续验证可执行：** 给出Phase 2的小规模输入来源和获取计划、运行平台选择、同集合数值标准及测量范围。
  缺K/V/Q或logical-position provenance等问题显式列为前置缺口，不以文件/文档检查代替实验。

**Proposed：** Phase 1通过后，能回答“两个算法如何表达、如何更新、Consumer接受什么、谁负责什么、
首版支持什么、还有哪些假设未验”。这形成后续采用的逻辑接口v0及实验约束；仍不冻结硬件ABI或微架构，
也不把接口设计、历史F2执行覆盖和新Adapter通过混同。

**Unknown（当前尚需验证）：** §3身份旁路维护、selection/effective映射和§4.6比较标准的新运行结果，
以及首批完整K/V/Q与运行环境的可用性仍须Phase 2检查。规则/映射与比较方法的设计已经交付，不等于运行验收。
共享HBM硬件集成可在Phase 1结束时仍为Unknown，只要其对后续结论的限制与成本责任明确。

### 7.3 Phase 1 → Phase 2的交接

**Proposed：** 交接对象是本文中已确认范围的逻辑设计及输入/验证约束，最少包括：

1. 前端profile、完整snapshot字段/身份/版本/生效规则，两个原算法的映射；score不进入后端选择。
2. KVBackingView、PackingTask、AttentionReadPlan各自字段、版本关联、batch和完成/回收合同。
3. 首选Consumer、布局、shape/dtype/长度/GQA/RoPE/causal范围，必要的准备复制与不支持项。
4. 小规模输入计划、独立same-set dense reference构造方式、拷贝应保持的精确数据对应和Attention数值标准。
5. Phase 2任务/测量范围、部署假设、会阻断执行的Unknown与允许作为模型假设保留的Unknown。

**Verified（输入范围）：** R1的predictor-only trace可以提供score/mask结构，但本身不等于完整K/V/Q
执行样本。F2原生trace有既有覆盖，也不意味着所有远程制品和本地环境均已可用。
**Proposed：** Phase 1只做源格式/位置和可用性调查，不下载权重或生成样本；Phase 2再按确认计划获取
少量完整数据。合成边界用例与真实算法输出分别标记，不能用合成输入冒充真实Adapter已验。

**Proposed：** 若Phase 2发现字段缺失、Consumer不兼容或数值合同不成立，回到本文明确修订范围/版本，
再继续受影响路径。只更换数据布局不授权更换原mask、阈值、保护规则或Gate计算组织。

### 7.4 Phase 2的三个任务：Software Reference & GPU Baseline

以下均为 **Proposed（后续实现/实验计划，本次不启动）**。Phase 2落实Phase 1接口，不再以设计文档
替代可运行参考，也不以GPU必须缓慢作为研究目标。

| 任务 | 要实现的内容 | 必要验证与输出 |
|---|---|---|
| Task 1：Algorithm Adapter and Software Reference | 将原KVzap与原FastKVzip canonical选择接为统一Descriptor；实现完整Snapshot、APPEND/REPLACE、KVBackingView、PackingTask、AttentionReadPlan与串行生命周期 | 原选择完全对应，K/V/ID/position精确关联；覆盖新增、成熟删除、旧mature撤销、重复任务、迟到completion、缺源/目标不足及Reader排空；报告实际通过/失败，不只输出结构示例 |
| Task 2：Attention Consumer Adapter | 按§4.5接入首选varlen＋Head-contiguous；从新backing/read plan生成合法输入，保留GQA与原位置RoPE | Per-head变长、GQA/输出还原、单query因果、自身新K/V、prefill后多次读取及APPEND/REPLACE后的准确新集合；独立same-set dense比较；记录tensor重建、复制和显存峰值 |
| Task 3：GPU Packing Baseline and Bottleneck Analysis | 实现Boolean mask＋gather、index-based gather＋compact、persistent layout＋incremental update；Consumer允许时增加无持久packing的sparse access诊断 | 同选择/数据/输出及Attention语义的公平测量；分项时间、真实可获得计数、峰值、启动/追加/REPLACE/复用/同步和亏损反例；判断硬件改善空间是否足够 |

**Proposed：** Task 1先用小规模确定性记录和实际canonical mask走通，再接Task 2；Task 3只测已通过
相应数值/生命周期检查的配置。真实前端输出可只读截获/replay，是否运行完整模型取决于后续实验范围，
不默认先跑大模型/完整serving。旧research共享计算可复用，不能因复用旧类而继承全部Route-A接口。

**Proposed（数值与身份）：** 搬运结果的K/V值、ID及position应与原mask索引得到的参考精确对应；
Attention在固定同一Q/K/V/选择下按预先选定FP32及执行dtype标准检查。不得从候选状态导出全部参考，
也不以token/argmax相同替代数值检查。独立自由生成的mask漂移和任务质量另行研究，不能混入搬运正确性。

### 7.5 GPU基线的公平性、测量和回本

| 路径 | 状态 | 公平实现约束 |
|---|---|---|
| Boolean mask＋gather | Proposed | 使用原最终mask；布尔选择通常已包含索引/整理与拷贝，融合的费用如实记录，不再重复计一次“compaction” |
| Index-based gather＋compact | Proposed | 从同一mask构造等价有序index并计构造成本；若输入本来有index，另外给出相应边界，不能只让该路径免费获得indices |
| Persistent layout＋incremental update | Proposed | 保持相同准确集合；测APPEND与REPLACE，计交集复用需要的边界迁移/历史复制。首选紧凑格式不支持零复制时明确记重建；更换Consumer/容量布局则单列变体 |
| 无持久packing的sparse access | Proposed（条件性） | 仅在Consumer真正可表达同集合时执行；需要每次gather或merge则计费，若接口不支持，记录限制，不静默改变Attention集合 |

**Proposed：** 三条主要路径先用同一输入、保留集合、输出布局和Consumer。布局/Consumer变体的
微kernel比较与包含适配的完整执行比较分开；原算法原生GPU路径作为实际参照，旧慢Python参考不能
代表合理GPU基线。Full-KV属于不同可见集合的系统基线，不能用它替代所有同集合归因对照。

**Proposed（需实际记录的测量）：**

| 范围 | 测量和解释 |
|---|---|
| Mask/index、gather、compaction | 分别标明输入已知条件、融合kernel边界与可分计时；不能从源码行数推时间 |
| Tensor rebuild/copy、decode append、REPLACE | 记录被重复复制的历史量、分配/迁移、交集复用与选择生效等待；不能只测首次prefill packing |
| Attention及输入准备 | 单独与合并区间都报告；计cu-length/max-length准备、reshape/concat、GQA还原及必要mask/merge |
| 提交与同步 | GPU段用适当CUDA events，Host段用host clock；说明stream、warm-up、reset、计时范围/重复次数和同步点；不把Profiler开销混入正常重复计时 |
| HBM统计 | 区分逻辑读写bytes、声明事务估计与可获得的真实计数器；不可获得的counter明确Unknown，不用payload bytes冒充HBM transactions |
| 显存和资源 | 报old＋new＋scratch＋metadata峰值、allocated/reserved及初始化基点；能获得时报告SM活动/占用，不能仅从卸载假设推资源收益 |
| 动态能量 | 如有合适设备计量，说明范围/分辨率/空闲基线；不可获得则保留Unknown，proxy不冒充实测，也不能直接得出新硬件能量优势 |

**Proposed：** 代表性范围至少覆盖：合法prefill后一次整理、不同head长度/保留密度、短/长复用、
decode新增与一次旧mature撤销，含少量实际前端输出；合成边界补充零/全保留、尾部及强偏斜。
运行前选定小规模点和重复数，不将每个组合当作独立真实请求，也不自行扩成大规模采集。

**Proposed：** 回本针对相同观察范围，比较“准备/packing＋更新＋提交同步＋后续消费”与可行的
不持久packing/重建读取路径，分别报告容量、时间、资源和能量；另与Full-KV报告系统观察。
串行首版可按同单位累计成本，存在重叠时按真实依赖/竞争解释完成时间，不直接相加嵌套区间。
报告逐前缀回本和失败窗口；在线策略不能使用已知未来输出长度，max_new_tokens仍只是上限。

### 7.6 Phase 2验收清单及交给Phase 3的结果

以下均为 **Proposed（后续验收标准）**，当前全部未执行：

- [ ] **生命周期正确：** Task 1真实选择不变，完整snapshot/身份/backing关联正确；连续串行批、
  APPEND/REPLACE、新增KV和旧Reader回收实际验证，无提前发布/释放或静默fallback。
- [ ] **消费正确：** Task 2首选Consumer实际运行，per-head变长/GQA/位置/RoPE/causal/单query及
  prefill后重复读满足同集合数值标准，复制、tensor重建和峰值可解释；未支持扩展不冒称通过。
- [ ] **基线可比：** 三条主要GPU方案有实际可比结果，布局变体单列；条件性sparse-access的
  可用性或阻断原因明确。不能将待实现路径标为完成，也不通过隐藏重建让某路径占优。
- [ ] **瓶颈可定位：** 分项与完整范围测量一致，selection/index、搬运、历史重建、Attention准备、
  append、同步各有归因；计数器/能量不可获得时明确缺口，不伪造硬件统计。
- [ ] **回本与硬件空间可判断：** 给出有效区域及亏损例、主瓶颈、专用硬件可改善的工作量/时间或资源上界，
  以及其必须承担的带宽、buffer/在途、命令、适配和同步义务；不要求此时已有引擎面积/PPA。

**Proposed：** Phase 2最终应回答：参考是否正确、GPU能否执行相同组织与计算、主要开销在哪里、
packing何时回本、专用硬件可能改善什么及需要支付哪些成本。结果可以是“GPU已足够高效，硬件机会不足”，
这仍是有效研究结果。若某核心适配失败，记录失败并回修Phase 1，不能宣布通过后继续硬件实现。

**Proposed：** 交给Phase 3的是实测瓶颈、适用输入范围、硬件所需服务/状态及允许成本预算/敏感性，
不是GPU时间自动换算的RTL性能。硬件的吞吐、面积、时序、外围与能量仍需后续独立实现/评价。

### 7.7 关键Unknown与是否具备开始条件

| 当前Unknown | 应在哪里解决/约束 |
|---|---|
| 新身份/位置旁路维护、selection/effective映射能否正确运行 | Phase 1 Task 1已给规则与真实输出映射；Phase 2 Task 1验证自动Adapter |
| 首选varlen新输入能否通过§4.6比较规则，及零head/multi-query/window扩展 | Phase 1 Task 2已给首版范围与比较方法；Phase 2 Task 2实际验证，扩展单独接受 |
| hot/new与cold同Consumer消费是否反复重建历史、REPLACE交集是否值得复用 | Phase 1列出准备步骤/复制点；Phase 2 Task 2/3测量，不承诺零复制 |
| GPU运行平台、数据可用性、环境兼容性、Device/Host高频控制成本 | Phase 1调查并给最小输入/运行方案；Phase 2检查环境并测量，当前不安装依赖 |
| 引擎共享HBM地址、GPU cache可见性、fence与争用 | Phase 1 Task 3显式约束；平台支持与真实集成后续验证。GPU内实验通过不消除此Unknown |
| 主瓶颈与回本、硬件性能/能耗/资源收益和完整成本 | Phase 2提供实测依据/预算，Phase 3及后续再验证硬件；Phase I模型/DC不替代 |

**Proposed（阶段边界）：** 以上为后续采用的计划。当前Phase 1调查/设计已执行，具体结果与缺失见§8；
先审阅接口/身份、首选Consumer及执行合同，再依据确认范围进入Phase 2。设计交付不等于接口已冻结，
也不证明运行环境、硬件集成或收益已经成立。本轮未启动Phase 2实验或Phase 3开发。

## 8. Phase 1正式设计结果与验收报告（提交审阅）

日期：2026-11-13。本节执行§7的三个调查/设计任务，给出真实输出示例、设计结果和证据分级。
§7保留后续任务与验收要求，当前完成情况以本节为准。**本次没有实现统一Adapter、调度器或Consumer
适配，没有运行模型、GPU Benchmark、RTL、仿真或综合。** 对既有NPZ/JSON的CPU读取与集合核对属于
本次证据调查，不是新算法实验。新逻辑字段及执行合同仍为Proposed，供审阅后作为Phase 2依据。

### 8.1 Task 1：真实输出、集合变化与Descriptor映射

**Verified（来源/解析）：** 下列位置均为zero-based，区间`[a,b)`左闭右开。所列集合公式是完整集合，
不是省略号预览；A由完整保存gate字段与hot规则精确投影，B/C/D与直接保存的完整集合数组核对相等。
新统一scope、snapshot版本和Record ID命名属于
**Proposed映射**，不是旧制品原生字段。对这些线性trace，Adapter可将已保存的logical/cache position
显式映射为稳定record_serial；该数值映射不改变§3.4的四类概念区分。

**A．KVzap当前研究profile：真实gate输出上的确定性投影。**

本地来源为
[replay_mask_events.npz](../experiments/route_a4146_replay_source_all_layers_budget512_01/replay_mask_events.npz)、
[来源manifest](../experiments/route_a4146_replay_source_all_layers_budget512_01/a41_replay_mask_source_manifest.json)，
及引用同一replay source的
[既有配对结果](../experiments/route_a4146_qwen_all_layers_allheads_budget512_quantization_aware_pages_01/a4146_qwen_alllayer_allhead_quantization_aware_native_storage_page_state_manifest.json)。
Request为`builtin_retrieval_trace`，268,992条事件＝36层×8 heads×934位置；每流位置唯一且连续0…933。
CPU核对layer0/head0的934条保存事件`keep == (saved_score >= -4)`，不重新预测或更改threshold。

取layer0/head0，q927与q928的共同成熟KEEP集合完整为：

```text
C = {0,73,76,147,150,221,224,295,298,369,372,
     443,446,460,531,534,605,608,679,682,753,756}
S927 = C union [800,928)   # 150 records
S928 = C union [801,929)   # 150 records
removed = {800}; added = {928}; intersection_count = 149
```

**Verified（既有真实决策＋确定性集合投影）：** 此处用NPZ实际keep与研究参考的hot128规则得到
append/maturity后的完整集合。Position800保存score为−5.0625、keep=false，离开hot后被删；928为
−5.46875、keep=false，但仍受保护。C未撤销，完整集合需要REPLACE。
该源保存字段为`layer/kv_head/cache_position/keep/score`，没有直接保存逐调用完整visible mask；
因此这不是直接捕获的原生DMSPress当前attention集合。

**Proposed（真实输出的接口实例）：** scope绑定此来源执行/layer0/head0，令v0对应S927、v1对应S928，
`supersedes=v0, update_kind=REPLACE`。Selection引用所消费的原gate事件，Effective Boundary采用
`kvzap_research_replayed_same_mask`的append-before-current-policy-attention边界（q928），
不能改标为原生post-hook“下一forward”。原生`kvzap_native_post_hook`按§2/§3.5另行描述。
**Unknown/缺失：** 本例没有K/V/Q、真实字节地址或原生DMSPress逐调用完整visible数组；不能由它验证
新KVBackingView、Consumer数值，也不能推断两种profile在当前调用时点完全等价。

**B．原FastKVzip Prefill：直接读取保存的selected positions。**

**Verified（远程原始制品，只读）：**

```text
algorithm_new:/home/myserver/san/zsy/zsy_2/Cache/FastKVzip_F2/results/
  fastkvzip_f2p_prefill_lifecycle_20261103_r4/summary.json
  fastkvzip_f2p_prefill_lifecycle_20261103_r4/trace_arrays.npz
keys: epoch_0_layer_1_head_5_after, epoch_1_layer_1_head_5_after
```

取layer1/head5，保存数组为int32逻辑位置：

| 原记录 | 完整selected set | Count |
|---|---|---:|
| Epoch0 after | `[0,28) ∪ {7118} ∪ [11904,16000)` | 4125 |
| Epoch1 after | `[0,28) ∪ {7118,12824} ∪ [15932,20028)` | 4126 |

**Verified：** 交集98，旧集合撤销4027，新增4028即`[16000,20028)`。旧成熟KEEP7118仍在，
12824从旧window进入成熟KEEP；完整集合因保护项成熟删除而REPLACE。原配置sink28/window4096，
新成熟cohort分别`[28,11904)`及`[11904,15932)`，pair threshold严格`>`。
[wrapper源码](../../../FastKVzip/prefill/model/wrapper.py#L196)先完成chunk forward再prune，
epoch1 after不能用于刚完成的chunk attention。

**Proposed（接口实例）：** scope为该run/layer1/head5；`snapshot_version=p1, supersedes=p0,
selection_epoch=prefill_prune_1, update_kind=REPLACE`，完整selected记录取第二行，original position按
保存数组绑定，effective epoch为prune1之后首次合法消费。此实例不把整个prefill重算为裁剪后集合。

**C．原FastKVzip Decode：直接证实旧mature KEEP撤销与生效边界。**

**Verified（远程原始制品，只读）：**

```text
algorithm_new:/home/myserver/san/zsy/zsy_2/Cache/FastKVzip_F2/results/
  fastkvzip_f2d_decode_lifecycle_20261103_r1/summary.json
  fastkvzip_f2d_decode_lifecycle_20261103_r1/trace_arrays.npz
keys: epoch_1_layer_2_head_2_after, epoch_2_layer_2_head_2_after,
      epoch_2_layer_2_head_2_before, epoch_2_layer_2_head_2_attention_visible
```

| Layer2/head2保存记录 | 完整集合 | Count |
|---|---|---:|
| Epoch1 after | `[0,4097)` | 4097 |
| Epoch2 before / attention_visible | `[0,4225)` | 4225 |
| Epoch2 after | `[0,4225) \ {1878}` | 4224 |

**Verified：** 相比epoch1 after，epoch2 after交集4096、撤销1878、新增`[4097,4225)`共128。
1878已经成熟。`attention_visible == before`且仍含1878；summary记录该compression forward的
`step_index=128, logical_seen=4225`。结合[post-forward压缩源码](../../../FastKVzip/math/method/modeling.py#L196)，
新集合用于其后调用。原global budget4096是平均目标，本例某head保留4224不违反全局预算语义。

**Proposed（完整Snapshot实例，字段值由真实输出映射，不是已实现Adapter）：**

```text
scope = (fastkvzip_f2d_decode_lifecycle_20261103_r1, layer2, head2)
snapshot_version = d2
selection_epoch = decode_compression_2
decision_available_at = after_model_forward(step_index=128)
effective_epoch = first_attention_after(decode_compression_2)
supersedes = d1
update_kind = REPLACE
encoding = ordered_selected_records
selected_records = {(RecordID(scope, p), original_position=p)
                    for p in ([0,4225) minus {1878})}  # complete, count4224
```

此处`encoding/selected_records`是§3的有序selected-ID列表表示，等价于完整domain＋mask；
不只传删除1878的delta，不包含任何物理地址。Original position和serial在本例有显式对应，仍分别存义。

**D．FastKVzip-derived fixed threshold：真实APPEND实例与反例。**

**Verified（已保存离线策略输出，不是官方native decode）：**

```text
algorithm_new:/home/myserver/san/zsy/zsy_2/Cache/FastKVzip_F3/results/
  fastkvzip_f3_policy_comparison_20261103_r1/policy_masks.npz
keys: fixed_global_threshold_epoch_1  # bool [36,8,4097]
      fixed_global_threshold_epoch_2  # bool [36,8,4225]
```

取layer13/head2，完整集合`E1=[0,4097)\X`、`E2=[0,4225)\X`，X完整为58项：

```text
X = {13,43,91,135,164,184,224,227,240,268,287,288,291,302,
     377,390,417,435,442,443,444,523,532,541,546,600,612,
     751,755,782,822,862,866,920,984,1061,1062,1065,1083,
     1128,1227,1343,1362,1368,1403,1429,1459,1465,1516,
     1547,1987,2230,2513,2558,2575,2582,2680,3916}
```

**Verified：** E1/E2实际count4039/4167，撤销0，交集4039，新增恰`[4097,4225)`128条。
本次直接读取保存mask，没有重算selection。**Proposed映射：** 两个完整snapshot为t1/t2，
`supersedes=t1, update_kind=APPEND`；selection epoch指向这份离线replay的epoch，不能伪装成
曾经实际执行的候选模型forward。Effective Boundary只是该策略拟遵循的后续消费边界，属Proposed。

**Verified（同一制品的反例）：** Layer0/head0的完整集合605→620，旧window撤销113、新增128，
所以仍需REPLACE；其mature cold则473→488且旧KEEP撤销0。阈值为F3 synthetic参考
0.031696561723947525，归一化average budget1229，与官方budget4096不是同一配置。
**Unknown：** F4真实请求候选的质量/部署支持；不能把以上离线APPEND映射称为原FastKVzip等价。

**访问与缺失边界：** F2/F3上述NPZ无本地独立副本，本轮经现有`algorithm_new`配置只读访问，未同步、
写入或新启动实验。远程路径不是本机文件链接。现有本地JSON及维护入口见§2。
这些集合足以给出真实membership/position接口实例；没有因此验证新Adapter、数据字节或Consumer执行。

### 8.2 Task 1结论：统一接口的支持范围

**Proposed（正式设计建议）：** 采用§3字段及四对象分工，以scope内稳定Record ID表达完整canonical
selected set，附snapshot/selection/effective epoch与supersedes；所有更新均传完整Snapshot。
APPEND只表示旧selected包含于新集合，REPLACE表示完整逻辑替换。算法保留score/policy/tie职责，
Runtime绑定backing，Scheduler生成任务与ReadPlan，硬件只执行有界搬运。

**Verified（本轮证据调查）：** A—D的真实保存输出可被这种完整集合表示表达，包含protected项首次成熟
删除、旧mature KEEP撤销及真实whole-set APPEND。**Unknown：** 自动Adapter、K/V关联与多次执行的
正确性尚需Phase 2；本轮没有以四个例子宣称所有合法输入已获得形式证明。

### 8.3 Task 2与Task 3交付定位

| 设计交付 | 本文正式结果 | 当前状态与依据 |
|---|---|---|
| Attention Consumer Specification | §4.6的varlen、batch1、8 pseudo-sequences、GQA4、BF16/D128、Head-contiguous、单query full-context；§4.5/4.6给准备及比较方法 | Proposed设计；§4原API/实际代码/历史执行证据支持调查结论，新路径运行Unknown |
| System Responsibility Matrix | §5.5分别列CPU/Host、GPU Device Runtime、Sparse KV Hardware、Memory Infrastructure、Attention Engine | Proposed职责；旧方案必要性/成本依据为H1—H4，不继承旧M2/R5/R6组织 |
| Minimal Execution Contract | §5.6的KVBackingView/PackingTask/AttentionReadPlan及§5.7的WRITE_COMPLETE、visibility、publication、Reader drain与reclaimable条件 | Proposed逻辑合同；不声称已经有队列/引擎或跨设备fence实现 |

### 8.4 First-version Scope

| 项目 | 提交审阅的首版范围（Proposed） | 仍需Phase 2或后续验证 |
|---|---|---|
| 算法语义 | KVzap两个明确profile、原FastKVzip prefill/decode的完整Snapshot＋APPEND/REPLACE；derived单列 | 不改变原mask；真实自动Adapter待验，不把新policy当原算法 |
| 执行切片 | 单请求，合法prefill后packing，source/destination分离，batch级、按批串行，completion后发布、旧reader排空后回收 | 软件参考还覆盖decode新增/一次REPLACE；不要求多组并发 |
| Consumer | §4.6首选；所有合法selected position不晚于query；hot/new/cold明确材料化为连续输入 | 多query、window/ALiBi、零head、任意batch、分源零复制不在首版执行范围 |
| 身份与存储 | 新命名只在Adapter/Runtime；记录原position、内容/表示及layout版本 | 未验证物理地址/真实K/V数据绑定；不固定硬件地址/ID位宽 |
| 排除项 | 原地覆盖、任意取消、自动重试、永久journal、共享prefix/beam/回滚、多版本并发提交、完整serving | 排除不允许静默改算法；不支持输入显式报告 |
| 部署 | 评估共享HBM域的候选引擎，GPU内reference可先独立实现 | 实际引擎接入/一致性/仲裁Unknown，不阻止提交设计，但限制硬件收益主张 |

**Proposed（后续输入/运行安排，不在本轮执行）：** Phase 2优先在已有FastKVzip兼容环境中先跑
小规模Consumer probe；历史A100/Transformers4.51.3/FA2.8.3.post2仅为候选运行起点，当前可用性与
两个仓库环境能否共用仍Unknown。本文的membership示例不含完整Q/K/V执行样本；先检查既有完整制品，
不足时再按后续授权捕获一个短请求的原始Q/K/V、最终集合、位置及调用边界，不以重算score或拼接不同
执行轨迹充当真实同集合输入。所有GPU/模型执行仍留在Phase 2。

### 8.5 Verified / Proposed / Unknown Evidence Ledger

以下是本轮实际结论的账本，不新建哈希清单或重复证据包。

| 内容 | 状态 | 直接依据/仍缺什么 |
|---|---|---|
| Importance/retention/protection、selection scope和调用时点 | Verified（论文＋源码） | §2论文、原DMSPress/研究backend区分、FastKVzip wrapper/policy/modeling；论文不替代当前实现细节 |
| KVzap A的150→150完整集合及800删除/928保护 | Verified（保存决策上的确定性投影） | §8.1A本地NPZ/manifest；不是直接捕获原生visible mask，缺本例K/V/Q |
| 官方FastKVzip prefill/decode B/C的完整集合与生效反例 | Verified（原始trace数组，本轮只读核对） | §8.1B/C远程NPZ/summary及精确key；本地副本缺失，未重跑 |
| Derived D的APPEND及完整集合REPLACE反例 | Verified（已保存离线策略输出） | §8.1D的policy_masks；不是原生模型运行或F4质量验收 |
| Record ID/epoch对象、字段归属和完整Snapshot逻辑接口 | Proposed（基于真实输出的设计映射） | §3/§8.1；原文件无统一Record ID，自动转换待实现 |
| Varlen/Paged/Ragged/GQA API与现有FastKVzip布局/复制 | Verified（API＋当前代码，历史运行另列） | §4.1—4.4与源码；不意味着新consumer已通过 |
| 首选Consumer、五方职责、最小任务/ReadPlan/交接与首版范围 | Proposed（设计结果） | §4.6、§5.5—5.7、§8.4；软件/硬件实现均未执行 |
| 新Adapter数值、K/V字节、tensor复制/峰值、提交开销、回本 | Unknown | Phase 2对象；没有GPU测试或新性能结论 |
| 引擎地址可达性、cache可见性、fence、共享带宽/完整成本 | Unknown | 未选定并验证平台；GPU事件不能替代真实跨设备协议 |

### 8.6 Phase 1 Acceptance Report

**结论：三个调查/设计任务已形成交付，提交审阅；逻辑接口尚未冻结，Phase 2保持未启动。**
此处验收是设计与来源范围的检查，不是将Proposed升级为已实现功能。当前不自动标记整个阶段用户验收PASS。

| Phase 1验收问题 | 本轮结果 | 限制 |
|---|---|---|
| 两原算法可否由统一接口表达 | 设计检查满足：§3及§8.1真实集合例 | 非所有输入的形式证明，自动Adapter仍Unknown |
| APPEND/REPLACE与生效是否明确 | 设计检查满足：完整Snapshot；A—D揭示whole-set与mature cold差别，C直接核对before/visible/after | Native DMSPress与研究profile不同；derived Effective Boundary为设计映射 |
| 身份、位置、rank、地址是否分开 | §3.4和真实记录映射规则已交付 | 新ID属于Proposed，不从旧artifact臆造原生ID；无K/V地址的例子不作字节验证 |
| Consumer与输入格式是否明确 | §4.6已给具体形状、stride、GQA、位置、准备/比较标准和限制 | 未运行新输入，不承诺零复制append或数值PASS |
| 职责、执行/回收与首版是否明确 | §5.5—5.7/§8.4已给五方矩阵、字段及发布/回收条件 | 实际平台visibility和运行实现Unknown |
| 数据/部署缺口是否如实列明 | 本地/远程来源、缺少副本与K/V/Q，以及Phase 2/硬件Unknown已列明 | 后续获取数据或运行实验需另按阶段开展，本轮未同步或启动 |

**停止点：** 等待审阅上述设计与证据范围；不自动进入Phase 2，不创建完整软件调度器或RTL。
