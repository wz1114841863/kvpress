# KVzap 项目总览与管理入口

更新：2026-11-12；本轮清理基于 `research/kvzap-latest / 42048b2`。
本页与R1—R6构成研究阅读入口：先看本页，再按问题进入六份报告，即可理解从
算法复现、系统探索到硬件检验的推进过程。原始JSON/CSV、trace、源码、schema
与冻结记录用于技术复核；旧计划、启动记录和交接不再是理解算法阶段的必读材料。
本轮整理没有重跑模型、模拟或DC。硬件阶段已完成初步梳理并提出四份报告的
归并范围；软件—硬件职责调整仍是待讨论候选，没有改变现有RTL或研究协议。

## 我们研究什么，目前做到了哪里

问题是：KVzap选择少留一些KV后，能否通过存储组织、一次packing和后续重复
读取，把逻辑稀疏变成值得实现的容量、访问和能量节省？这首先是稀疏KV存储与
执行管理问题；它本身不等于加速Transformer算术，也不是训练新的predictor。

**已经得到指定范围的算法结构、软件功能和条件性系统模型证据；硬件原型的
部分功能已验证，但完整持续执行、统一时序和系统净收益仍未闭合。**

## 六份报告：每一步为什么做，结果怎样推动下一步

| 报告与范围 | 本阶段要解决的问题 | 主要结论与下一步 |
|---|---|---|
| [R1 算法复现、稀疏结构与路线筛选](algorithm_reports/01_reproduction_and_route_selection.md)：baseline、trace、v1/v2、Route-B | 算法能否运行，稀疏位置是否规则，为什么选择packing？ | 45条v2 trace逻辑压缩约2.96×；比例轮廓稳定但位置不规则。原mask packing保留更多容量机会，实际硬件成本尚未比较完整 |
| [R2 Packing、调度与摊销](algorithm_reports/02_packing_scheduling_and_amortization.md)：A0—A3.20 | 整理存储是否回本，调度是否值得？ | P64容量模型接近逻辑压缩；调度的merge/dispatch可吃掉收益。长请求有正向模型区域，短输出、错误continuation和启动前缀有亏损反例 |
| [R3 功能参考与执行观察](algorithm_reports/03_functional_reference_and_execution_observations.md)：A4.0—A4.2 | hot/pending/packed能否真正参与attention，代价在哪里？ | 给定mask和数值标准下可执行；Python参考仍较慢。分源并行带来额外partial传输，逻辑事件不能直接给出物理服务时序 |
| [R4 跨模型与前端边界](algorithm_reports/04_cross_model_and_frontend_boundaries.md)：Llama、SnapKV、DMS、C0—C5 | 哪些语义可迁移，哪些机制专用？ | 两个模型提供有界KVzap语义证据；其他前端暴露不同生命周期。共同身份/作用域/遍历/比较依据尚不构成共用cache或低成本硬件 |
| [R5 Pending与metadata资源探索](algorithm_reports/05_pending_and_metadata_resource_exploration.md)：A4.3—A4.10 | 待整理KV如何保存、归属、排队和原子更新？ | 共享与span有逻辑价值；RMW拆分是负结果。内部交错改善模型排空但未消除溢出，有限shared/staging及生产者持有责任须计入 |
| [R6 前RTL成本账本与架构入口判断](algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md)：A4.11—A4.14.1 | 已计成本后还剩多少机会，为什么允许进入架构？ | 三固定workload通过公平HBM的2×工程余量门槛并有正动态能量遗漏预算；允许写架构规格，未证明完整硬件净收益 |

六份报告分别给出实验目的、计划、结果、分析和直接数据来源。它们不是六组
独立样本：v1包含于v2，后续大量研究复用同一批固定请求或事件，敏感性组合数
也不等于独立请求数。Qwen、Llama、自然生成与固定continuation不合并统计。

整条因果链是：**逻辑压缩机会 → 保持mask的物理整理 → 回本条件 → 功能与执行
观察 → 适用边界 → 有限资源合同 → 条件性成本账本 → 接受实际硬件检验。**
后一个阶段在补前一个阶段未解决的问题，不能把前面的正号直接传递到最后。

## 方案的共同词汇与历史选择

Route-A的目标生命周期为：

```text
creation时预测 → 最近128条hot保护 → maturity
  → drop，或成为仍须可读的pending保留项
  → 按预算admission并追加到每layer/head的packed pages
  → 后续decode重复读取 → 最终退休/回收
```

一个KV记录属于某个layer、KV head及token位置。Qwen目标的K+V按BF16/head_dim128
为512 B，page64为32 KiB；这些是本次参数，不是算法的通用常数。打包与读取
依赖membership、position、页身份、归属和生命周期管理，不能只按payload估成本。
软件参考与RTL是不同实现；软件能重复处理状态，不代表RTL已支持全部持续行为。

Route-B改变score-to-mask以换规则性。B4,+0.25约2.14×逻辑压缩同样有价值，
但原mask在arbitrary-token packed布局下容量更好，B4生成筛查也未建立质量等价。
因此当时保留Route-B备选，优先研究Route-A；并未完成同质量、同技术的A/B完整
硬件比较。若packing/管理过贵，仍有理由重新比较，不能把历史选择当成最终胜负。

## 从前RTL账本到硬件：哪些问题真正暴露了出来

A4.14.1的正向判断有明确前提：Qwen3-8B、原mask、hot128/page64/budget512、
三个固定workload、共同合法GQA复用，以及public-CACTI和声明HBM服务参数。
它已计部分metadata宏、payload访问、admission搬运和source buffers；P3本地
stage、完整控制、partial/merge数值处理、外围、leakage及统一时序仍未全部计价。
正的动态能量遗漏预算不是面积预算，也不能支付时序违例。

后来的RTL把状态owner、publication、authority、握手和错误处理变成具体电路，
暴露出compact表及访问网络、跨owner ready链、页管理和生命周期问题。这说明
原始条件性假设需要实现检验；也不能反过来抹掉已观察的压缩、功能或模型事实。

| 硬件检验部分 | 最后已验收的范围/快照 | 仍未建立 |
|---|---|---|
| 功能 | first-use路径有测试；显式v2小规模场景覆盖一次packing后同页读两次、错误路径及retire排空 | 默认v1的重复读取、同session多组admission、完整32K并发和数值链 |
| 控制面积 | RD1＋WCG1：Route-A 2,990,737.01、Full-KV 23,091.43，同库cell-area units，约129.52× | 完整系统面积、PPA或净硬件收益 |
| 时序 | 原2 ns下Route-A primary setup WNS −0.469940 ns；primary hold无违例，补充hold-pass后setup/hold仍未闭合 | 完整顶层setup/hold/clock-gating及物理时钟树闭合 |
| 优化处置 | metadata bridge、compact membership、RD1/WCG1有各自证据；RD2负结果未集成，PM1有小面积收益但顶层setup退化后未纳入最终基线 | 局部收益能无限叠加，或当前寄存器实现是算法必然面积下界 |

上述DC快照不含后加的持久页v2功能；129.52×是控制投影比，不能推断最终系统
面积比一定更大或更小。具体实现证据按需查
[RD1＋WCG1结果](dc_rd1_wcg1_full_paired_result_20261109.md)、
[持久页结果](route_a_persistent_page_read_r2_result_20261109.md)。

目前集中存在四类未闭合问题：同session多组admission与journal/pending释放，
compact/P3/M2/R5等必要存储及端口，原2 ns下跨owner控制链和setup/hold，以及
完整差分成本。注册窗口关闭等候选合同仍需生产者承诺、在途操作排空和实现验证，
不能将参考模型通过当成生产RTL已实现。未来研究方向尚未决定。

## 硬件阶段：研究过程与四份报告的归并范围

本轮只梳理已有架构、RTL、存储边界和映射结果。以下H1—H4是拟整理的正文，
尚未新建报告，不增加阶段评估、来源清单或配套附件。

硬件探索的推进过程可以串成五步：

1. **从系统模型到架构。** Gate-A及RTL-entry把A4的条件性机会转成硬件R1—R6
   owner、publication、memory/source、generation与retire接口。明确唯一写入和
   发布职责有助于验证，但物理存储、共同服务时钟与完整数值实现当时仍未落实。
   原mask/位置与正确可见性属于语义；36层实例、通用wrapper兼容和具体握手
   行为则有各自的设计来源，不能统称为算法必然要求。
2. **从控制骨架到有界数据流。** RTL1完成局部控制与跨owner协作，RTL2激活
   admission、publication、读取、四消费者和回收，RTL3引入功能memory及
   partial/R4环境，C4-D闭合packed首次使用。它们积累了真实功能证据，但环境
   提供的memory/数值服务并未因此成为自主硬件attention实现。
3. **从功能模型到测量边界。** SRP、MBR、MR-1/2区分生产父控制、数组内部、
   外部服务与验证环境，并建立Full-KV对照。DC计入真实父控制，数组内部采用
   代理；因此面积比回答控制实现问题，P3/M2/R5宏、外围和外部服务仍需另计。
4. **从面积热点到具体优化。** metadata bridge去重复状态、compact membership、
   RD1共享读取、WCG1共享字门控依次取得完整顶层面积收益。相同primary口径下，
   控制面积比约为291×→171×→157×→147×→130×。PM1完整顶层仅省约0.90%且
   setup退化，RD2隔离面积反增约0.30%，均未纳入最终RD1＋WCG1基线。面积
   收益不等于时序闭合，隔离结果也不能直接加成顶层收益。
5. **从首次使用回到持续执行。** v2已在小规模15项native测试中验证同页两次
   读取及错误/retire场景；同session多组admission和journal释放仍未实现闭合。
   旧合同允许迟到registration/lookup，令历史不能仅因一次服务结束就丢弃；
   这些兼容要求需要与论文执行范围一起重新审视，不能直接扩大为免费历史存储。

| 拟报告 | 覆盖范围 | 要讲清楚的结论 |
|---|---|---|
| H1 架构设计与软硬件职责边界 | A4进入架构、Gate-A、RTL-entry、硬件R1—R6分工与有限anchor | 为什么选择这些模块和接口；哪些是算法语义，哪些是架构、兼容或实现选择 |
| H2 RTL实现与持续执行范围 | RTL1—RTL3/C4-D、外部功能环境、Stage-A探针、持久页v2及多组/journal讨论 | 从骨架到哪些真实功能路径；首次使用、重复读取和持续服务分别证明到哪里 |
| H3 存储实现、测量边界与完整成本 | SRP/MBR/MR-1/2、compact/P3/M2/R5/S2、存储映射与增量账本 | 哪些控制已映射、哪些数组/服务未计；容量、端口、生命周期及外围为何限制物理实现 |
| H4 面积／时序优化与设计复盘 | 原始DC、bridge、compact/entry_id、RD1、PM1、RD2、ST1、WCG1及顶层STA | 每项修改针对什么、局部与完整结果如何、保留哪些负结果，以及瓶颈为何仍在 |

每份按目的、方案、结果、分析写成一篇，直接引用已有数据。原始数据和技术
定义保留在原位置；启动重试、工具报错和哈希过程不进入探索主线。entry_id
修复只作为正确验收的必要背景，不计作独立面积优化；ST1/RD2等研究负结果保留。
H3承接算法R6之后的真实实现成本，避免重复抄写前RTL的proxy账本。

主要依据：[架构规格](architecture_spec.md)、[RTL1](rtl1_phase_contract.md)、
[RTL2/3推进](rtl2_phase_contract.md)、[首次使用闭合](rtl3_9_c4_d_functional_completion_review.md)、
[MR-2](mr2_completion_review.md)、[完整增量账本](route_a_incremental_storage_cost_ledger_p0_20261106.md)、
[最新完整DC结果](dc_rd1_wcg1_full_paired_result_20261109.md)、
[持续页读取结果](route_a_persistent_page_read_r2_result_20261109.md)。

## 软件—硬件协同：值得评估的职责调整

已有实现的困难提示：不应默认所有全局状态、长期历史与系统管理都必须由这块
硬件自主完成。算法可以规定保留集合、位置/顺序和生命周期；runtime或设备端
软件组织任务和内存，硬件执行有界、吞吐敏感的数据工作。以下只是候选分工：

最新映射中M2/P3 wrapper仍占顶层约67.46%，两张compact表保留366,336个数据位。
热点同时涉及必要状态、寄存器/读取网络的实现方式，以及全局管理职责放在哪里；
它不证明算法必须付出当前电路的成本，也不证明搬到软件就能免费消除这些工作。

| 层次 | 候选职责 | 仍需回答的问题 |
|---|---|---|
| 算法／执行抽象 | 保留集合、maturity、生效范围、读取顺序与正确性比较依据 | 原KVzap是输入；本研究贡献应落实为可执行抽象与实现机制，跨算法范围仍需验证 |
| 软件系统／runtime | 路径选择、粗粒度head/page/group任务组织、HBM分配与全局目录、长期记录和回收计划 | 软件维护量、命令粒度、控制流量与延迟；不能把未来decode长度当已知，也不能假设CPU逐fragment往返免费 |
| 硬件执行与局部控制 | pack/gather/DMA、活动buffer、端口仲裁/credit、GQA供数、在途完成与错误处理 | 维持数据/位置对应、可见性顺序和安全回收；软件计划不能替代真实传输完成 |
| Attention计算单元 | 根据声明接口消费数据并产生partial/result，可评估复用既有单元 | 当前partial/R4环境尚不等于自主数值实现，供数、合并、服务竞争及差分成本须计入 |

例如软件可以把全局目录编译为一批页任务，硬件执行搬运后返回完成，再由软件
决定后续读取与回收；不要求硬件永久保存全部软件历史。但数据完成前不得发布、
在途服务结束前不得复用、保留位置不得错配等约束仍要落实到双方协议中。
这属于重新选择执行边界，不能当作保持全部旧wrapper行为的局部等价优化。
是否优于当前方案，要比较软件开销、控制流量、HBM/计算重叠、硬件状态及完整
差分成本；当前证据尚未给出这套协同方案的面积或端到端收益。

## 哪些早期设想没有变成已证明的结论

正式RULER/LongBench准确率、与KVzip oracle的全面误删比较、长上下文下的
predictor质量保证、threshold/window/score量化的完整质量权衡，不在六份报告
已建立的结论内。结构阈值扫描不能代替这些质量实验。FastKVzip等新增算法的
硬件适配也尚未验收；C0—C5只分析已有前端证据，没有完成统一后端。

最初关于吞吐、内存和RTL的目标，应理解为待检验目标。软件计时、模型cycles、
HBM字节、动态能量proxy、DC cell area与物理PPA分别属于不同证据，不能互相
替代。当前研究的瓶颈是功能范围、存储与服务合同、实现成本和时序能否同时成立。

## 仓库与数据怎么找

| 位置 | 内容及用途 |
|---|---|
| [kvpress/](../kvpress/) | 软件推理与前端；[KVzap predictor](../kvpress/presses/kvzap_press.py)、[DMS包装](../kvpress/presses/dms_press.py)、[attention patch](../kvpress/attention_patch.py)是关键入口，实际数据流见R1 |
| [evaluation/](../evaluation/)、[kvzap/](../kvzap/) | benchmark、算法相关工具和训练代码；代码存在不等于本研究运行过或训练过 |
| [analysis/algorithm_reports/](algorithm_reports/) | 六份研究正文；从本页直接进入，不需先读中间评估/索引 |
| [analysis/experiments/](experiments/) | 原始结果、配置、输入副本、manifest、日志和失败运行；目录数不等于有效实验数 |
| [traces/](../traces/)、[pilot_inputs/](../pilot_inputs/) | score/mask、生命周期和请求输入，很多被Git忽略 |
| [tools/](../tools/)、[tests/](../tests/) | 采集、分析、模型与对应检查；从各报告的数据链接和实现入口查找 |
| [hardware/route_a/chisel/](../hardware/route_a/chisel/) | Chisel源码与功能测试；可从[顶层](../hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala)进入 |
| [hardware/route_a/dc/](../hardware/route_a/dc/)、[mem/](../hardware/route_a/mem/)、[payload/](../hardware/route_a/payload/) | 综合/STA、存储proxy与payload配置；工具存在不是结果通过 |
| [TRACE_SCHEMA](../TRACE_SCHEMA.md)、[架构规格](architecture_spec.md) | 按需核查字段、版本及实现合同，不承担算法研究过程的补充叙述 |

理解研究过程读七份文件；核验数值、重绘分布或复现时，再进入各报告直链的
JSON/CSV、trace、配置和源码。均值不能重建完整分布，提交文档也不等于备份
Git忽略的数据。首批已清理13份旧文件，本轮继续清理22份已归并的说明、计划、
合同及恢复记录，实验数据保留。旧AGENTS和已删除说明可在Git版本`42048b2`
中查看；旧记录中的路径按当时版本解释，不要求当前目录保留重复说明。真正供C0
工具读取的跨前端归档仍保留，研究阅读只需总览与六份报告。AGENTS只保留开发
约束，不再承担项目历史或例行哈希检查。

本轮资料状态有两个明确限制：R1的原v2请求JSONL本地仍缺；R5的A4.9.2/A4.10
汇总已在已有`algorithm`项目中找到并与接受链核验，但本地仍缺副本，具体位置
和结果见R5§9。其他传递依赖并未全部重新验收。因此七份文件已串起研究解释，
不表示全部实验已可从本地离线重建。后续更新优先修改这七份文件中的对应内容，
不再为同一研究阶段默认增加数据包、清单或新的总览副本。
