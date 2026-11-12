# KVzap 项目总览与管理入口

更新：2026-11-12；本轮清理基于 `research/kvzap-latest / ced72e0`。
本页与R1—R6构成研究阅读入口：先看本页，再按问题进入六份报告，即可理解从
算法复现、系统探索到硬件检验的推进过程。原始JSON/CSV、trace、源码、schema
与冻结记录用于技术复核；旧计划、启动记录和交接不再是理解算法阶段的必读材料。
本轮整理没有重跑模型、模拟或DC，没有决定新研究路线。

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
Git忽略的数据。本轮已清理13份内容已归并且无冻结/工具输入依赖的旧算法说明、
合同及整编中间文件，没有删除实验数据。仍被冻结原文引用、按原文哈希登记或
作为工具输入的资料继续保留；研究阅读仍只需总览与六份报告。

本轮资料状态有两个明确限制：R1的原v2请求JSONL本地仍缺；R5的A4.9.2/A4.10
汇总已在已有`algorithm`项目中找到并与接受链核验，但本地仍缺副本，具体位置
和结果见R5§9。其他传递依赖并未全部重新验收。因此七份文件已串起研究解释，
不表示全部实验已可从本地离线重建。后续更新优先修改这七份文件中的对应内容，
不再为同一研究阶段默认增加数据包、清单或新的总览副本。
