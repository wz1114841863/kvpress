# H1：架构设计与软硬件职责边界

整理日期：2026-11-12。本文承接[算法R6](../algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md)，
整理从A4系统模型、Gate-A架构合同到Gate-RTL0实现入口的探索，并用后续实现结果
解释当时选择的影响。只整理已有证据，没有修改RTL或重跑实验，也没有确定新的软硬件分工。
下文的“硬件R1—R6”是六类架构职责，与算法阶段六份报告的编号不同。

**当时的路线是：先把稀疏KV的正确性和资源归属讲清楚，再逐步实现控制逻辑。
这建立了可验证的功能边界，却没有同时证明这些职责全部放进当前硬件划分后仍然经济、
满足时序或支持持续decode。算法要求与这套具体划分需要分开理解。**

## 1. 目的：为什么需要从算法模型走到架构设计

前期已经看到原始KVzap mask的压缩机会，也验证了hot/pending/packed软件路径。
但逻辑上“不再保留某条KV”，与物理上少占空间、少读HBM之间，还隔着存储和执行系统：
谁保存尚未packing的保留项，谁搬运数据，什么时候可以读取新页，什么时候才能回收旧副本？

A4.14.1把三个固定workload的metadata、payload和部分服务成本对应起来，在公平GQA
对照下通过HBM流量的2×工程余量门槛，并留下正的差分动态能量遗漏预算。因此当时允许
**开始编写架构规格**。它没有证明完整控制、P3本地stage、数值merge、外围和时序已经可行，
也没有证明最终芯片净收益。架构阶段的任务，正是把这些尚未实现的工作转成明确职责与接口。

| 推进步骤 | 当时要回答的问题与方案 | 得到的结果及边界 |
|---|---|---|
| A4→架构规格 | 把模型中的队列、存储、搬运和commit对应到实际系统对象 | 分清共同设施与Route-A增量；依赖图仍不代表物理端口或时钟流水线 |
| Gate-A1 | Pending还没打包时，attention从哪里读？比较复用S2、直接endpoint和独立pending buffer | 选择direct pending endpoint，避免另加pending页组织/驻留副本；未证明吞吐或能量最优 |
| Gate-A2 | 归属、发布、背压和merge规则能否写成可执行参考？ | 形成纯软件参考与断言，作为后续RTL检查依据；不是硬件验证 |
| Gate-A3 | 抽象身份、页和在途请求如何落到有限范围？ | 固定Qwen3-8B/32K/单sequence等anchor及有限命名空间；不是容量压力或持续执行验收 |
| 硬件R1—R6与Gate-A复审 | 谁能改变哪些状态，模块之间何时交接？ | 架构合同通过交叉检查，可定义独立RTL入口 |
| Gate-RTL0 | 哪些层次、端口、断言和参考模型指导第一版RTL？ | 允许分阶段control-first骨架；数值微架构、宏、HBM/CDC、频率与物理实现继续留待后续 |

这里每一步的“完成”含义不同：接口定义完整，不等于电路已经正确；电路功能通过，
也不等于面积、服务能力和时序已经合适。

### Gate-A2 与最终复核实际检查了什么

Gate-A2使用当时的纯软件事务参考及定向测试检查：不完整metadata组不能
发布，payload写完成不立即转移authority，四个GQA消费者提交前不能释放，stale或
错代响应不能改变当前对象，ready-low只能延迟而不能改变状态。数学merge按
`hot→pending→packed`处理；全空source和非正归一化分母均拒绝。这些是事件和数学
参考，不包含实际时钟、HBM控制器或有限精度硬件实现。该旧参考代码已退役，
需要复核实现时可从Git历史恢复；实验结果和本报告保留。

Reviewer-01确认语义及有限anchor后仍保留整体Gate-A未通过；Reviewer-02随后对
唯一owner、publication、fault、reset/复用与全局drain完成交叉复核，才允许定义
独立RTL入口。相关纯软件回归是功能合同证据：A2历史回归记录59项通过，R1命令
经纠正为73项通过（早先76项是错误计数），Reviewer-02的另一组8套参考测试记录
76项通过。它们是不同且有重叠的测试集合，不应相加或当作硬件正确性证明。

## 2. 方案起点：保存原mask，以一次整理服务后续多次读取

Route-A没有把KVzap mask改成规则block，而是沿用原始选择结果：

```text
creation时预测 → 最近128条hot保护 → maturity
  → DROP，或进入仍然可读的pending
  → admission/packing → packed cold页发布
  → 后续attention读取 → 最终退休与回收
```

这一路线的理由是保留原mask的容量机会，并让一次packing被未来decode的少读KV摊销。
它首先解决存储组织和供数问题；attention算术吞吐并不因packing自动提高。
短输出可能来不及回本，额外调度和partial merge也可能吃掉收益，这些负结果在
[算法R2](../algorithm_reports/02_packing_scheduling_and_amortization.md)中保留。

**Hot、pending、packed的区分是这条实现路线的组织方式。** 对当前Route-A，它们有
明确含义；但“必须恰好三个物理模块、恰好这些接口”并不是KVzap算法本身的要求。
Pending尤其不是可丢弃的临时队列：已决定保留而尚未完成搬运的KV，仍可能被attention使用。

## 3. 为什么这样划分模块

核心思路是把三个问题分开：数据在哪里、谁有权宣称它可读、当前传输是否完成。
例如HBM写入完成只能说明新数据已就绪；它不能单独证明目录、成员关系和旧来源的归属
也已经同步切换。一个模块负责一类可变状态，有助于避免重复发布、过早回收和错误关联。

| 职责/模块 | 为什么单独划出 | 当时分配的工作与实现边界 |
|---|---|---|
| R1 memory transport | 上层不应各自解释HBM响应和事务完成 | 统一请求身份、片段匹配、终结状态及reset旧响应排除；对外是core-memory接口，不是真实HBM controller/PHY |
| R2 arbiter/dependency | 多个来源争用同一传输路径，需要统一判断资格和记账 | 管FIFO、依赖、credit与grant，R1真正接受后才推进；descriptor维护也走同一R1路径 |
| R3 M2/P3 wrapper | Packing既改metadata又搬payload，两者不能独立宣称成功 | 协调M2私有prepare、P3 stage、payload durable与publication；其父级控制后来成为重要面积来源 |
| M2 metadata/control | 数据流需要知道待处理项、head/span、归属、顺序和信用 | 保存head/span控制、事务组与队列语义；抽象服务机会不等于已选多端口SRAM |
| P3 payload staging | 将pending数据组织成packed页写出，同时保留原来源直到交接 | Pending HBM为权威backing，stage是临时副本；每层一页容量是选择的映射，不是选好的宏 |
| R5 page manager | 页生命周期长于一次写入或一次attention服务 | 分配页、维护descriptor和stream目录、generation、可见性及回收；避免临时buffer释放顺带销毁长期页 |
| S2/GQA source wrapper | 页读入后可供四个query-head消费者复用，需共同管理槽位 | 两个ping-pong源页buffer与消费者完成跟踪；payload设施与公平Full-KV共有，Route-A的sidecar管理另计 |
| Direct pending endpoint | 尚未packed的合法数据也要供给attention | 从pending backing按声明顺序直接供数，不占S2页槽或另建长期payload副本；仍需在途身份与消费完成控制 |
| R4 merge boundary | 多来源attention的partial必须按数值合同组合 | 定义partial/result包、顺序、归一化与fault边界；可替换数值实现，不代表已实现QK/softmax/AV流水线 |
| R6 lifecycle adapter | 局部传输完成不能代替整个attention/session结束 | 接收post-decision事件，管理hot/pending/packed authority、dispatch、唯一terminal与全局retire排空 |

顶层只负责连接这些owner，避免再保存一套同义状态。这个安排便于对照参考模型、
验证状态守恒，并逐层激活RTL。**它是为功能实现和可验证性作出的划分，并不是经过
软硬件职责比较、宏映射和时序优化后得到的最小成本划分。**

### 用一条保留KV串起模块协作

一条KV到达后，前端提供身份、位置和payload引用。Hot阶段结束时，前端给出不可变的
RETAIN决定；它进入pending，packing尚未完成时仍须有合法读取路径。

R3组织admission，借助M2准备成员和head/span状态，P3收集对应payload与位置。
R2仲裁、R1完成搬运；R5准备页descriptor。只有payload、M2和descriptor前提齐备，
才发生本架构选定的`metadata_publish_commit`，同步建立packed可见性、交接authority，
并释放相应stage。单独的payload write commit不能完成这次交接。

以后读取该packed页时，R5给出合法页事实，R2/R1供数到S2；四个GQA消费者完成本次
partial更新后才释放S2服务槽。R4的结果/错误由R6关联为attention terminal。
**一次服务结束释放的是临时资源；仍需后续读取的packed页要继续存活。** 最终runtime
请求session retire，R6等待各owner的在途工作排空，R5再按页完成失效与回收。
这是一条预期架构路径；各阶段后来实际实现到哪里，见第6节。

## 4. 当时的软件、硬件与外部服务边界

这套架构并非把整个LLM都放进DUT，但确实把较多后端管理职责分配给了硬件owner。
前端和runtime主要提供已经作出的决定、服务请求和退休意图；目录、归属、发布及排空
则主要由DUT承担。它没有先比较“软件维护全局目录、硬件执行有界任务”等替代分工。

| 所在侧 | 已定义的职责 | 不能据此认定已经实现的部分 |
|---|---|---|
| 算法/模型前端 | Q/K/V与predictor；向后端提供arrival、位置及maturity的保留/删除决定 | DUT不接score/threshold，不等于已经支持任意裁剪算法或完成predictor集成 |
| Runtime/session manager | 提供attention服务与session retire等外部意图 | 不是完整host软件、命令队列或软件调度系统；其控制开销没有自动计入 |
| Route-A DUT | 上述R1—R6及本地buffer/状态的接口与控制 | 不代表所有存储内部、持续行为和完整数值处理已实现 |
| External memory adapter | 内存服务、init及旧响应隔离等环境承诺 | Controller/PHY/CDC、真实HBM时延/带宽与争用仍需实现或计价 |
| Partial/R4 provider及数值参考 | 按合同提供/检查partial与结果，支持功能验证 | 验证环境提供协议包不等于attention计算单元已实现，也不等于免费服务 |

选择direct pending endpoint体现了当时的取舍：复用S2需要新增pending页形成和槽位规则；
独立pending buffer又引入容量、拷贝与释放合同。直接endpoint可以延续既有record级供数
语义，少引入一种长期payload驻留。它胜出的是当时的接口与资源定义比较，而非实测性能比较。

S2则刻意作为共同设施：公平Full-KV也获得相同GQA共享读取条件。共同payload buffer
不能全记成Route-A额外面积；sidecar、packing、M2、页管理和多来源merge也不能藏进
共同设施。相同服务设施上的不同访问量，仍要分别计账。

## 5. 哪些是必须保持的语义，哪些是选择

需要区分三层：KVzap保留集合与attention正确性；当前Route-A已经约定的系统语义；
以及为落实语义而选定的接口、电路与兼容行为。后两层有历史理由，但并非算法唯一解。

| 问题 | 必须满足的要求 | 当时选定、不能视作算法必然的形式 |
|---|---|---|
| 保留集合 | 当前研究固定原KVzap mask；hot保护与maturity按既定范围执行 | 后端模块名、三来源物理边界、是否由软件下发批任务 |
| 身份与位置 | 数据、layer/head、原位置对应正确；不能漏读、重复计入或破坏因果范围 | `entry_id`公式、opaque handle、各字段位宽与packet布局 |
| 搬运与可见性 | 新来源可用前不能丢掉旧来源；读取不能看到半完成状态 | 单一`metadata_publish_commit`事件、固定M2两成员prepare及R3/R5/R6具体联动 |
| 顺序与数值 | 要符合声明的attention参考和数值标准 | 当前`hot→pending→packed`顺序、FP32包和具体容差；改顺序需另做数值验证，不能仅凭数学结合性 |
| 背压与资源 | 有限资源不足不能悄悄改变mask、丢工作或提前复用 | 具体valid/ready通道、pre-edge行为、组合ready链、credit编码及队列拓扑 |
| 复用安全 | 在途响应/消费者不能写入或读到已复用的新对象 | PageRef、generation/epoch位宽、reset/init握手及具体quiescence协议 |
| 释放与历史 | 必须保留仍被合法操作引用的事实 | 旧wrapper的迟到registration/lookup范围、journal保存到reset、入口一次/reset的实现 |
| 错误处理 | 错误不能伪装成功或破坏状态 | 当前fail-closed、无retry/Full-KV fallback的合同；不是所有KV系统的唯一错误策略 |

因此，“保持旧wrapper行为的等价优化”和“重新选择论文执行接口”是两种工作。
前者必须接受旧合同允许的所有输入；后者可以讨论关闭注册窗口、目录移交或软件owner，
但要明确新范围并验证，不能删掉历史后仍声称全部旧语义不变。

### 有限anchor也不是算法下界

Gate-A3选定Qwen3-8B、32K、单sequence、36层/8 KV heads、page64、hot128、512 B
K+V/record，以及一个packer、一个pending endpoint等有限实例。它解决“接口有多宽、
最多多少身份/页”的定义问题；不是其他模型不能实现，也不是这些实例都已通过满容量验证。

按keep-all cold上界，记录数为`(32768−128)×36×8 = 9,400,320`，页数146,880。
选定的5 GiB cold pool由pending与packed共享，包含payload、position sidecar及一个
migration page reserve，**不是pending和packed各5 GiB**。R5另选128-bit descriptor，
表容量`146,880×16 B = 2,350,080 B`，不在该pool内。

P3每层一页对应`36×64×512 B = 1,179,648 B`本地payload容量，不含sidecar。
M2的双head副本、span存储及八bank服务来自前期模型候选；抽象读/写/RMW机会不能直接
解释为物理多端口宏。以上容量、复制、并发及延迟仍要落实和计价。

原软件sidecar的8 B表示不等于所有位置必须用64 bit；但后来wrapper中的两个opaque
64-bit字段来自独立owner，现有合同也没有保证可互相推导。能否缩短必须看字段来源和
新接口，不能从“32K位置只需15 bit”推出所有64-bit引用都能删除。

## 6. 结果：这些选择实际证明了什么

Gate-A复审通过的是owner与交接合同：一个状态有明确负责人，publication与authority
一致，错误有终结路径，复用/reset有有限规则，retire等待全局排空。Gate-RTL0进一步
将层次、端口、15项断言记录和3项环境公平性/进展记录对应起来，允许分阶段实现骨架。
二者均没有证明SRAM、HBM、数值计算或顶层时序已经闭合。

后续RTL推进使上述合同接受了真实实现检验，也暴露了原先未解决的问题：

| 后续观察 | 对架构选择的反馈 |
|---|---|
| RTL3.9 C4-D完成packed首次使用、四消费者、terminal及retire/reclaim的有界功能链 | 模块可在声明memory/partial环境下协作；仍不是完整持续decode或自主attention数值实现 |
| 阶段A探针发现第二次读取缺少持续activation事实，第二组admission被入口Done阻断 | 首次publication和一次组接收被实现为一次性路径；页仍存活、credit归还并不足以自动持续服务 |
| 显式持久页v2的15项native测试通过，包括一次packing后同页两读、错误/恢复与指定retire交错 | 支持把持久页资格交给R5、每次S2服务单独建立/释放；验证范围仍小，默认v1与多组能力没有因此改变 |
| 多组journal审查发现旧合同允许迟到查询，没有已有组关闭保证 | 入口rearm之外，还必须处理历史和pending owner生命周期；不能只清64条工作表来继续接收 |
| RD1＋WCG1控制投影约129.52×Full-KV，原2 ns下setup WNS −0.469940 ns | 当前状态/访问网络与控制组合链代价仍大；不证明算法必须有同样成本，也没有完成系统面积或PPA比较 |

持久页v2使用小规模packed-only场景，数值对应未建立，sidecar及partial服务仍有环境边界；
该功能修改不在上述DC快照内。多组精确历史的288 MiB方案只是保留旧查询语义的一个容量
候选，不是算法必需存储下界，更不是已经实现的方案。

## 7. 分析：合理的起点，留下了哪些重要缺口

**当时合理之处，是没有把packing当成单纯拷贝。** Pending仍可读、目录不能先于数据
发布、四消费者完成前不能释放、旧响应不能污染新对象，这些问题是真实存在的。唯一owner、
软件参考和分阶段实现，也让首次使用路径具备了可检查的功能证据。

**不足在于，逻辑合同先详细化，低成本执行方式却没有同步确定。** 最初依赖图明确不选
端口、时钟和流水线；后来逻辑握手、兼容行为和owner关系逐步固定，物理存储与完整服务
仍未落实。到RTL映射时，保存完整事实、多路即时读取、逐成员交接以及跨owner就绪判断
已经成为具体寄存器和组合网络，等价优化的自由度随之缩小。这里既有必要工作，也有
表示方式、接口粒度和状态归属带来的成本，不能全部归咎于算法。

**持续生命周期也没有随着首次路径一并闭合。** 一次packing的价值依赖后续重复使用，
但首次使用成功并未覆盖重读资格、多组接收、历史删除和正常复用。旧wrapper又允许迟到
操作；缺少生产者“以后不会再合法访问旧组”的承诺，硬件就无法仅凭本地空闲安全丢历史。
这说明需要明确执行范围和软件/硬件双方的生命周期责任，而不是继续无界增加表项。

**前RTL正预算没有覆盖这些实现问题。** 动态访问能量预算不能作为控制面积或时序预算；
外部提供的memory、partial和数值结果也没有变成免费硬件。现有巨大控制比同时受到很小的
Full-KV控制分母和Route-A实现成本影响，既不能直接当完整系统面积比，也不能因此忽略分子。

后续讨论职责分离时，应以“谁产生决定、谁保留事实、何时交接、何时不再合法引用”为单位，
而不是先把现有模块整块搬给软件。可以重新评估全局目录、长期历史、页任务组织的归属；
实际传输完成、数据/位置对应、在途消费与安全复用仍须由可执行协议保证。软件命令与同步、
带宽和延迟也要计入。**H1到此只还原历史选择及其问题，不判定哪种新分工已经更优。**

## 8. 原始定义与结果入口

本文已在正文串起研究过程。需要核查接口或实验范围时，可直接查：
[架构规格](../archive/architecture_spec.md)、
[pending路径详细合同](../archive/mr1b_direct_pending_cross_owner_contract_proposal.md)、
[有限anchor参数](../archive/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json)、
Gate-A结论见本文第6节、
[RTL层次与owner](../archive/rtl_entry_hierarchy_owner_contract.md)、
[Gate-RTL0结论](../archive/rtl_entry_interface_manifest.json)。
硬件各职责原定义为[R1](../archive/architecture_gate_a_r1_core_memory_wrapper_contract.md)、
[R2](../archive/architecture_gate_a_r2_arbitration_dependency_contract.md)、
[R3](../archive/architecture_gate_a_r3_m2_p3_wrapper_contract.md)、
[R4](../archive/architecture_gate_a_r4_numeric_merge_contract.md)、
[R5](../archive/architecture_gate_a_r5_page_manager_descriptor_contract.md)、
[R6](../archive/architecture_gate_a_r6_top_level_lifecycle_contract.md)。

后续反馈来自[首次使用闭合](../archive/rtl3_9_c4_d_functional_completion_review_manifest.json)、
[持续执行探针](../archive/route_a_stage_a_probe_result_20261109.md)、
[持久页v2结果](../archive/route_a_persistent_page_read_r2_result_20261109.md)、
[多组journal审查](../archive/route_a_multigroup_journal_lifecycle_closure_20261109.md)和
[RD1＋WCG1结果](../archive/dc_rd1_wcg1_full_paired_result_20261109.json)。后续H2—H4分别展开
RTL功能范围、存储/完整成本、面积与时序实验；本文不复述其启动、重试、报错和哈希记录。
