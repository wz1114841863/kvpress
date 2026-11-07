# Route-A 深层复审：研究目标、证据链、实现边界与完整增量成本

复审日期：2026-11-07。源码截面：`research/kvzap-latest`，`9045350dbd3fc0d6cd889a1507327691f99c2218`。

本报告服务于两件事：重新串起从 KVzap 算法研究到当前 RTL/DC 的研究过程；判断哪些结论已经站住、哪些桥梁仍未接上，以及下一阶段如何有限地收口。它是只读复审及决策建议，不是新的架构冻结、RTL 授权、实验结果或 Gate-B 验收。配套的[证据与问题账本](route_a_deep_review_evidence_20261107.json)记录可机器读取的结论、来源、范围及核验情况。

## 1. 先给出判断

**已有证据支持继续研究 Route-A，但尚不足以证明当前硬件实现经济可行。当前最需要补齐的是算法机会到可实现、可计价的硬件之间的连接，单独继续优化选择器不足以完成这个任务。**

1. 原始 predictor、mask 结构、有限生命周期与条件性 traffic/energy 机会有实物记录支持。不能因为当前控制电路很大，就倒推这些历史事实不成立。
2. 当前 RTL 的身份、durability、publication、authority 和回收链路确实有重要的有界功能证据；它没有完成长期 decode 的自主数据与数值闭环，也没有完整实现原研究模型的全部持续服务行为。
3. 面积优化并非只有 RD1 生效。metadata bridge 与 compact membership 已有完整顶层映射收益，RD1 又进一步降低面积；WCG1 的真实 wrapper 隔离结果也正向。但 PM1 的小面积收益伴随 setup 退化，RD2 隔离结果负向，不能把所有候选合并为成功方案。
4. 当前基线 RD1 面积比约 **146.747× 是控制投影对控制投影**。它既不能称为整芯片面积比，也不能因为 Full-KV 分母小就忽略 Route-A 约 338.86 万 library cell-area units 的实现成本。
5. 两张 compact 表是当前已映射面积的首要问题之一；同时，P3、M2、R5 等被代理掉的存储和外围还有大量非零成本。只解决 compact，不等于解决完整增量；只优化排除在 DC 外的 P3，也不会直接降低当前控制面积。
6. 没有证据证明“KVzap 算法必然需要这么大的寄存器实现”，也没有证据证明“这些状态只是综合器错误展开，换个写法就一定消失”。当前接口要求、通用容量、持久身份与组合读取共同导致了这一实现。应逐项检查必要性，而不是把当前实现当作算法下界。
7. 全顶层 Route-A 在原 2 ns 约束下始终没有 setup closure；WCG1 隔离 wrapper 的零违例不能清除顶层时序问题。
8. 建议先完成本报告列出的实现可行性收口，再决定是否继续局部优化、提出版本化的实现合同调整，或缩小论文硬件结论。无需重开已经冻结的 pruning、admission、R2 arbitration、R3 publication 或 R6 authority。

## 2. 本轮检查了什么，哪些检查没有做

本轮并行复核算法/历史、架构/RTL、成本/映射三条证据链，并做本地小规模哈希及账本算术检查。没有修改 Scala/RTL、冻结输入、EDA 脚本或约束，没有加载模型、运行仿真/综合，也没有连接远程或操作正在等待结果的 tmux/进程。

| 检查层次 | 本轮得到的证据 | 不应扩大成的结论 |
|---|---|---|
| 原始冻结制品 | 224 个主登记对象中 223 个存在且 SHA-256 匹配，0 mismatch；唯一缺项是 v2 preparation JSONL | 全研究历史、所有传递依赖都完整可重跑 |
| predictor 原始 trace | v1/v2 合计 63 个 trace 实例（18+45）的 126 个 manifest/score-mask 文件均在本地且哈希匹配；v1 的 18 个 request_id 均包含在 v2 中，去重为 45 个请求 | 本轮重新运行 predictor 或逐条重新执行 schema validator |
| 汇总重算 | baseline 9 行、v1 18 行、v2 45 行和 A4.14.1 三 workload 的相关算术重算 | 新的准确率、模型、HBM 或性能实验 |
| A4.14.1 provenance | 报告及四份直接输入副本匹配；再追一层的 22 个登记引用中仅 6 个内容可在本地已审计对象中匹配，余 16 引用对应 13 个独立内容 hash 缺失 | 从最底层全部 payload/native proxy 数据重新推导整个 A4 账本 |
| 当前 RTL | 复核当前源码、合同和已有测试覆盖描述，定位状态/端口/一次性路径 | 新 RTL 仿真、形式等价或完整功能证明 |
| DC/STA 历史结果 | 重审本地已验收结果、其保存的 native 数值/哈希/检查记录 | 本轮再次远程核验 DDC、mapped HDL、DB 或运行状态 |
| 当前 RD1+WCG1 流水线 | 只引用最后登记的本地 launch 快照 | 断言远程目前仍在运行、已经失败或已经完成 |

原始哈希检查明细、主表之外的传递依赖缺项和算术重算保存在配套 JSON 中。哈希匹配证明内容身份，不单独证明实验正确性。旧文档曾记录某些 trace 未同步；本轮实际检查的 126 个 trace 文件已经存在（63 个 trace 实例，不是 63 个独立请求），应使用这次的可用性结论。

## 3. 几个月的研究是怎样推进到这里的

下表按已登记阶段梳理，日期采用冻结/交接记录，不能把文件名或提交时间当作每次实验的真实起止时间。

| 阶段 | 当时要回答的问题 | 得到什么 | 留给后续的边界 |
|---|---|---|---|
| 8 月上旬：官方 baseline | predictor 与 KVPress 是否能在选定模型环境运行 | Qwen3-8B、官方 MLP、threshold -4、window 128，9 个组合功能检查通过 | 三个内置请求；不是正式准确率/加速评测 |
| 8 月中下旬：trace gate、18 条 v1、45 条 balanced v2 | 原始 mask 是否有稳定可利用结构 | retention 宏观轮廓稳定，token mask 重叠较低、fragmentation 明显 | predictor-only，不能充当在线 admission 生命周期 |
| 8 月：Route-B 筛查 | block coalescing 是否更适合硬件 | B=4,m=+0.25 仅对受限 timeline-page 假设有小幅 proxy 优势 | 对任意 token packing 不占优；冻结备选，未扩大准确率结论 |
| 8 月至 9 月初：A0/A1 | packed pages 容量、尾部和调度是否可行 | P64 packing 接近 logical 容量；特定 whole-head 调度可恢复不均衡 | capacity、调度模型分别成立；dynamic-page 并非自动更好 |
| A2/A3：生命周期与 break-even | 一次 packing 能否由未来 decode reads 摊销 | 条件性长 horizon 机会；短输出存在真实模型反例和启动亏损 | 未来 horizon/服务假设必要，不能保证每个请求获益 |
| A4.0—A4.11：语义绑定 | mask、token、position、pending/packed 权限是否保持 | same-mask 控制、external-storage exact-token 与有限 lifecycle 绑定 | 独立在线 mask 曾出现翻转；不是跨模型质量保证 |
| 9 月中旬：M/P/DMS、C0—C5 | 能否形成跨模型/前端的统一稀疏 KV 后端 | 有限 Qwen/Llama/前端语义比较；C5 保留 frontend-bound 有序遍历抽象 | 没有统一 cache/lifecycle/resource/temporal 合同，主线仍为 Route-A |
| 9 月末：A4.12—A4.14.1 | metadata、payload 与省略成本后还有余量吗 | 三固定 workload 的 public proxy/declared-service 账本通过条件性工程门槛 | 允许编写架构规格；异构坐标、遗漏项和物理实现仍未闭合 |
| Gate-A / Gate-RTL0 | 谁拥有状态，何时原子转权，接口如何验证 | R1—R6、sole publication、fault/reset/retire、有限参数及验证计划 | architecture/planning PASS 不意味着低成本硬件或时序 PASS |
| RTL1—RTL3.9-C4-D，10 月中旬 | 把语义链变为可执行控制与有界功能路径 | 首次 packed read、S2 READY、四消费者、terminal、reclaim 与负例覆盖 | 外部 memory/partial/R4 环境仍在；未形成持续推理实现 |
| 10 月中下旬：SRP/MBR/MR、投影冻结 | 怎样公平测控制成本并隔离未选实现的数组 | paired Full-KV/Route-A control cut、typed array proxies、真实父控制保留 | proxy 不计价；共同资源尚不能仅凭名字抵消 |
| 10 月 29 日至 11 月 7 日：DC 与 refinement | 现有控制实现面积/时序有多差，能否局部改进 | 大幅减少重复状态和组合网络；得到真实正、负结果 | 仍未 setup closure；完整增量、统一服务和物理成本未完成 |

这条路径累计建立了很多可复核的局部结论。其主要缺口是：**前一阶段的条件性系统机会，并不会随着接口和功能测试越来越多而自动变成后一阶段的实现经济性。**

## 4. 算法与系统模型：哪些结论仍然有效

最初问题来自“逻辑删除”和“实际少存、少读”之间的差别。[原论文](../papers/KVzap.pdf)的 KVzip+ oracle 与 Linear/MLP predictor 提供 token/head importance 前端；本项目固定使用已有官方 predictor，不重新训练。当前 [KVzapPress](../kvpress/presses/kvzap_press.py) 从 hidden state 产生分数，[DMS 路径](../kvpress/presses/dms_press.py)保存新 token 的 score，并在其离开 128-token window 时使用阈值决定删除。[兼容 attention patch](../kvpress/attention_patch.py)用 fake keys 模拟 head-wise 删除，源码明确保留 dense storage、不能降低 peak memory。因此，研究目标始终是让给定 mask 的逻辑稀疏转化为可证伪的物理系统收益，而不是再证明一次删除率很高。

### 4.1 已证明的原始事实

- Phase 0 冻结的 9 个组合均通过内置功能检查。冻结环境、checkpoint 与配置只适用于原记录，`elapsed_ms_diagnostic` 不用于性能结论。
- balanced v2 的 45 请求重算：token-weighted removed fraction **66.2269449%**，request mean **66.4705205%**，logical compression **2.9609403×**。这些是 predictor-only 结构证据。
- layer/head retention 的跨请求相关性很高，但 mean keep-mask Jaccard **0.2046184**、扣除 marginal-rate 的 excess **0.0689306**。因此不能用稳定 retention 直接推导共享 token mask，也不能假设天然 block locality。
- Route-A 保留原 mask 的 arbitrary-token packing，和受限 Route-B 有明确区别。Route-B 的 36/36 mask gate 及筛查指标不能替代正式 LongBench accuracy。

来源：[baseline freeze](baseline_freeze.json)、[v1 freeze](longbench_core_v1_freeze.json)、[v2 freeze](longbench_balanced_v2_freeze.json)、[Route-B freeze](b4_route_b_screening_freeze.json)、[研究阶段归档](route_a_stage_archive_20260902.md)。

### 4.2 条件性收益与必须保留的负结果

A4 后段的硬件路径也有明确筛选：M1 unified 1RW 被拒绝，M2 replicated/duplicated control 成为 public-CACTI 候选，M3 register 尚未估价；A4.13.2 的 Full-KV no-reuse 对照后来被 A4.13.3 的两侧相同合法 GQA reuse 纠正，当前 headline 不再使用旧 no-reuse baseline。这些失败与公平性修正应保留。

A0 的 P64 payload-slot compression 约 **2.914681×**，把显式 metadata 加回后的同口径值约 **2.913338×**；不能把只算 slot 的字段叫完整物理容量收益。A1 的某些 anchor 中 whole-head LPT 优于 static，但 dynamic-page 会被额外串行 merge 等成本抵消；高 PE utilization 不等于较低 end-to-end makespan。

A2/A3 的 dense-authoritative、read-only trace 用于生命周期与费用推演，不是 policy-on 模型质量评估。短请求的 admission 开销可能无法摊销；A3.15 的 17-call 反例、A3.20 的启动 dip/recovery 仍有效。Full-KV bypass 是严格性能安全对照，deferred admission 仅是语义安全的投机策略，不能因为随后长 horizon 的账本好看就删除短请求风险。

也不能写成“没有任何软件实测”：A4.1 存在 Python reference 的时间/allocator 测量，其部分 workload 明显慢于 Full-KV。这证明那一 reference 路径没有 wall-clock 收益；它不是优化 GPU kernel benchmark，也不能据此外推所有硬件实现都不可行。配套账本保留具体样本、数值与 manifest 路径。

A4.0 独立在线分支曾出现 **5/268,992** 个 mask 决策翻转；后续 same-mask replay 明确固定决策以控制变量。它支持给定 mask 的物理方案分析，不能换成“动态执行下任意请求与官方 predictor 决策始终完全一致”。

### 4.3 A4.14.1 的价值与限度

| 固定 workload | declared payload HBM + P3 admission bytes / fair legal-GQA Full-KV | 对应减少倍数 | differential omitted dynamic-energy budget |
|---|---:|---:|---:|
| retrieval | 0.3265341 | 3.06247× | 27.645821 mJ/request |
| summarization | 0.3127451 | 3.19749× | 40.498451 mJ/request |
| reasoning | 0.2327034 | 4.29732× | 167.442185 mJ/request |

这是在选定三 workload、生命周期、proxy 与 declared service 下重算的账本。A4.14.1 使用 retrieval/summarization/reasoning 三个内置 preset、8 generated tokens；A3.20 使用三条 LongBench 长摘要、127/127/91 decode calls，二者不是相同 workload/horizon。账本的 29/42/72 attention positions 也不等于生成 token 数。metadata replay 分别完成 2,828/2,828、3,006/3,006、7,370/7,370 个由 token→span 确定性转换得到的 transaction groups，只证明该 replay 模型的有限 drain，不能称为直接观测到的硬件事务。

**上表 budget 是动态能量余量，不是允许增加多少标准单元面积、寄存器、mm² 或额外周期。** Metadata service 坐标和 payload service 坐标也不能直接相加为统一 latency。缺少 common clock、依赖图、仲裁和 overlap，就不能由此声称 tokens/s 或硬件净收益。budget 的条件是 `E_RA_unestimated - E_FK_unestimated < B`：M2 仅计 control-entry 动态访问，P3、queue/staging、merge、controller 等仍有未估项；S2 固定 proxy 属共同 provision，差分活动仍需计费。

权威：[A4.14.1 合同](route_a4141_accounted_net_benefit_ledger_contract.md)、[规格 §12](architecture_spec.md#12-parameters-unestimated-costs-and-timing-boundary)。本轮核对报告 hash `0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb`；传递依赖缺失范围见 §2。

## 5. 架构/接口约束要分清四种来源

| 类别 | 例子 | 本轮处理 |
|---|---|---|
| 研究语义与正确性要求 | 原 mask、hot/maturity/pending/packed 生命周期、精确 position、单一 publication、durability 前不得转权、retire 排空 | 保留；当前局部 refinement 不改变 |
| 已冻结的架构/anchor | page64、S2 两槽、HA8、M2/P3 owner、R1—R6、Qwen3-8B/32K/s1 有限界 | 不是算法的普适定理，也不能在当前实验中暗改；如需改变须独立版本化论证 |
| 通用 wrapper 的兼容行为 | 多 bank unbound 容量、独立消费者、valid-low ready 的数据依赖、pre-edge 与 held payload | 当前承诺下必须等价；它们不是由 KVzap 论文自动推导出的要求 |
| 可替换的物理实现 | enabled DFF 或共享 clock gate、读网络分解、宏 bank/复制、编码、流水组织 | 可以研究，但必须证明既定合同；不能预设同步 SRAM 或加一级流水自动等价 |

早期先用完整 typed records、显式寄存器和组合匹配验证 ownership，是可解释的保守选择；它减少了在功能未明时隐藏状态和关联错误的风险。问题在于：宏/端口/共同 clock 被留待以后，而这些接口行为后来又成为“必须逐周期保留”的兼容约束，导致低成本实现的选择变少。**这说明 realization 需要单独审查，不足以断言最初算法规划整体错误。**

36 layers 和 8 KV heads 是当前 Qwen anchor 的实例取值，R6 接口本身不传 predictor score/threshold。不过当前 RTL 多处硬编码了 `stages=36`、head 界限 8 和坐标乘数 288；并非只改参数对象就能迁移。换模型需要重定字段宽度、容量、GQA、pool/service，并修改和验证这些实例化假设；尚无跨模型硬件证据。语义接口的抽象性与当前源码的可参数化程度是两件事。

权威：[Gate-A review](architecture_gate_a_reviewer_02.md)、[paired profile](paired_control_projection_profile_20261028.md)、[接口 manifest](rtl_entry_interface_manifest.json)。AGENTS 与早期 README 中“当前 architecture specification、不是 RTL”的措辞属于历史阶段；后续单独授权的 RTL/DC 阶段有对应冻结，不应把旧 next-step 文字当作今天的状态。

## 6. 当前 RTL 到底完整到哪里

### 6.1 已有的功能闭合是真实且有界的

C4-D 验收的是：R3 唯一 publication、逐成员 R6 authority acceptance、首个 owner-correct packed read，经 R2/R1 与 descriptor/sidecar/association 到 S2 READY、四消费者服务、terminal，再 retire/reclaim；并有 stale/mismatch/fault/reset 的定向负例。后续 metadata、compact、RD1、WCG1 等也各有其明确回归范围。

这些既不是“没有功能”，也不是“全功能产品”。外部 memory responder、partial provider、R4 reference 仍是环境。当前 measurement top 将 S2 functional payload/sidecar read 口置 inactive；partial/R4 数值由外部供给，不能声称真实 KV bytes 已驱动自主 attention 算术链。

### 6.2 长期 decode 与首次使用之间仍有具体缺口

- production admission ingress 每次 reset 只收集一组、最多 64 成员；最后一个 relay 后进入 `StateDone`，没有正常运行时返回 Collect 的转移。
- R3 reconciliation journal 是固定 64 ordinal/reset，并有重复 ordinal assertion。仅把 ingress 改为 rearm 不会使其自然支持多个 group。
- page-ready fact 和 activation binder 的当前路径消费一次后清除活跃事实；没有已证明的持久 authoritative-page lookup/遍历机制来驱动同一 packed page 后续每一步 decode。
- direct-pending 仍是批准的单记录有界 contour。规范对 namespace/generation wrap 要求 quiescence，当前有界实现尚未证明连续 wrap/reuse；R6 retire 后进入 `StateRetired`，也没有正常运行时的 session reopen。

因此，A4 中较长生命周期/多事务 replay 的 drain，不能直接标记为“当前 production RTL 已执行同样的完整持续 workload”。论文原型不必变成完整 NPU，但若想解释 repeated-read 摊销，至少要用一个有界、可重复使用的执行模型接上这条桥梁，并明确哪些由外部 runtime 驱动。

来源：[C4-D review](rtl3_9_c4_d_functional_completion_review.md)、[MR-1B contour](mr1b_direct_pending_cross_owner_contract_proposal.md)、[当前 incremental 源码](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala)、[measurement top](../hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAMeasurementDut.scala)。精确源码锚点及 hash 在配套账本。

### 6.3 一项新发现的静态正确性候选

`RouteACommonSkeletons.scala` 的 `protocolCompatible` 计算了 `readCompatible`、`writeCompatible`，但返回表达式只处理 descriptor 格式例外，没有使用前两项。按当前表达式，某些 source class 与 request kind 不匹配的 candidate，满足其余 eligibility 时可能被接收。已有 producer 生成合法 kind，现有 first-use PASS 未被这个静态发现推翻。

本轮没有仿真，**把它登记为需独立定向验证的 R2 边界防护问题，不登记为已复现 bug**。应先确认合同/环境前提、构造 mismatch 与合法对照，再决定修复。不能顺带改变 arbitration、顺序或当前冻结远程输入。详见配套账本的 `RTL-CLASS-KIND`。

## 7. 两张 compact 表：真正的问题与可行方向

### 7.1 它们存了什么，为什么还这么大

当前两张表是 R3 父控制中的 member record 与 binding suffix：

| 内容 | 位宽与容量 | 数据位数 | 用途 |
|---|---:|---:|---|
| member record | 36 × 64 × 79 | 182,016 | position15 + payload_ref64；present/count 在独立 mask/header，供 materialization/关联/观察等使用 |
| suffix record | 36 × 64 × 80 | 184,320 | identity5 + 独立 opaque handle64 + generation8 + destination3 |
| 合计 | 2,304 个逻辑槽位，每槽 159 bit | **366,336 bit = 44.71875 KiB** | 不含 present/materialized masks、headers、journal 与读写/时钟网络 |

两个 64-bit 字段合计 294,912 bit，占表数据 **80.503%**。当前外部 owner 没有给出高位为零、对齐、固定步长或互相可推导的保证。它们可能碰巧相同，不能据此合并。

数据不是“materializer 发出后就过期”：member 还供 C/F/B 检查、publication 后 O/R6 观察；suffix 由 M/C 读取，不能在 M 发出后就释放；journal 另承担 reset 前的 late lookup。STORE P0 的生命周期发现必须逐项作为优化 proof obligation，不能直接变成可释放量。

### 7.2 读写与容量比字段总位数更影响实现

RD1 已共享每 bank 的 M/S/O member-record 读取。仍存在 member payload_ref 的四路独立逻辑选择（M/S/O 共享一路，加 C/F/B），position 与 suffix 还有各自读取要求；写入与读取也不能随意串行化。

在 stage/presence 等条件成立时，C/F/B 的 ready 即使在 valid=0 时仍组合依赖所读数据，且有 pre-edge、held bits 和并发合同。这种接口对普通同步单口 SRAM 不是直接替换关系。简单复制存储以增加读口又会增加存储位与写分发开销；“用了 RAM”并不自动更便宜。

production 的每 reset ≤64 和 generic 的 36×64 unbound 能力是不同边界。若未来明确只为 production contour 做 specialization，可能减少容量/关联成本，但必须单独确定论文范围与兼容合同；本轮不把这个建议当作已获准容量裁剪。

### 7.3 已研究方向的准确处置

| 方向 | 当前结果/范围 | 下一步判断 |
|---|---|---|
| metadata bridge compact | 全顶层映射已证实大幅正向 | 保留；不是仍待尝试的假设 |
| compact membership | 全顶层面积正向，entry_id 映射失驱动后已定向修复 | 保留；修复不算新的独立面积优化 |
| RD1 | 全顶层面积 -6.454%，寄存器/clock load 不变，setup 变差 | 保留候选，不能称全方面改善 |
| RD2 | 隔离映射面积 +0.303751%；buffer/inverter 开销抵消其余组合收益 | 负结果，不集成；WR1 没有一项独立负结果可等同引用 |
| WCG1 | 真实 wrapper 隔离、matched hold-pass 面积 -15.624812%，全位宽/容量保留 | 等待完整 paired 证据；不是已经获得同等顶层收益 |
| ST1：大 suffix 表复用 journal | production 条件下有重复；通用兼容所需全局 ordinal 前提未获合同支持，source-predicate replay 暴露边界 | 简单无条件替换不实施；不是证明所有 journal reuse 都不可能 |
| 反向复用：从大表供 journal | 最多先涉及 5,120 bit 的 suffix 副本，还须新增读取/持久关联 | 理论空间小，不是被 ST1 一概否定；优先级低 |
| 字段压缩/释放/容量池化 | 当前没有不损信息的保证，也缺跨全部合法 trace 的最大同时存活证明 | 先做合同与 occupancy 证明，未证明前不改位宽或容量 |
| register file / banked macro | 物理选项未匹配当前组合多读口语义 | 需要真实端口、宏价格、外围、延迟与等价验证，不能按名义 bit 数估净省面积 |

若保持当前全部数据都用同库普通 DFQD2 保存，仅 `366336 × 2.520 = 923166.72` cell-area units，已经约为 Full-KV 控制面积的 **39.979×**；这是特定 DFF 假设下的算术，不是算法、存储宏或未来实现的物理面积下界。它说明继续只改 selector 很难消除寄存器存储本身的成本。

来源：[STORE P0](dc_compact_store_p0_audit_20261106.md)、[ST1 scope validation](dc_st1_scope_key_validation_result_20261106.md)、[RD1 结果](dc_rd1_full_paired_dc_result_20261106.md)、[RD2 结果](dc_rd2_read_screen_result_20261106.md)。

## 8. 面积与时序：所有主要优化放回同一张表

以下均为原 `dc_feasibility_fair_v1` 的完整 paired primary 结果；area 是同一 library 的 cell-area units，不能换成物理 core/mm²。Full-KV 一直精确复现 **23,091.432498**、5,060 sequential cells、setup/hold 零违例。

| Route-A 阶段 | cell area | / Full-KV control | sequential cells | setup WNS(ns) | setup TNS(ns) | violating paths |
|---|---:|---:|---:|---:|---:|---:|
| immutable r5desc baseline | 6,716,537.642416 | 290.867× | 1,298,150 | -0.31 | -7,318.06 | 34,814 |
| metadata bridge compact | 3,952,935.893452 | 171.186× | 653,138 | -0.33 | -7,891.18 | 31,458 |
| compact membership + entry_id repair | 3,622,375.558791 | 156.871× | 577,106 | -0.31 | -8,577.41 | 35,897 |
| RD1 | 3,388,597.345862 | 146.747× | 577,106 | -0.36 | -9,774.02 | 35,959 |
| RD1+PM1 候选 | 3,358,045.877079 | 145.424× | 577,106 | -0.44 | -12,096.60 | 35,976 |

另有一次未修复 entry_id 的 compact diagnostic：面积 3,624,318.814461、约 156.955×，但映射后 driver 门槛失败，不能冒充可集成验收结果；完整记录仍保留在账本中。

metadata 首次优化 -41.146%，compact/修复相对前项 -8.362%，RD1 再 -6.454%。RD1 相对最早 baseline 累计 -49.548%，这说明以前确有显著实现冗余。不能把全部累计节省记给 RD1，也不能把 raw generated state 减少当作 mapped flop 或 area 减少。

### 8.1 当前已映射面积的主要差异

以当前选择的 RD1 为准：

| 层次 | mapped area | 占 Route-A | 范围说明 |
|---|---:|---:|---|
| M2/P3 wrapper | 2,387,543.1337 | 70.458% | compact tables、journal、present/header、读写选择及父控制；不包含 P3 array child 的真实成本 |
| Page Manager | 407,306.5906 | 12.020% | 活跃状态、allocated-line/control、选择与协议；R5 availability child 被排除 |
| M2 production control | 175,735.2263 | 5.186% | grouped 控制、typed carriers 与匹配；M2 entry child 被排除 |
| metadata bridge | 85,833.3851 | 2.533% | 已紧凑后的组/credit/mapping 状态 |
| 其余控制 | 332,179.0102 | 9.803% | R1/R2/R6、registry、delivery、association 等 |

RD1 comb/noncomb 为 **1,392,283.363726 / 1,996,313.982136**；顺序面积占约 58.91%。clock alias 为 **577,110** 直接 loads，约等于 sequential cells 加四。旧 1,298,154-load 的 directPending 命名已定位为 clock alias，不是 130 万个语义上的 pending 消费者。

所以面积差距既有小分母，也有真实而较大的分子；两者不能二选一。已发现并修掉了具体重复状态，没有充分证据把其余所有大表都归因于“综合错误”。

### 8.2 PM1 与全局时序退化

PM1 完整结果面积只再省 **0.901596%**，Page Manager 本身省 **4.243364%**；flop/clock load 数量不变。saved-DDC 精确 STA 指出 reclaim 的低六位 bank-priority/indexed-offset 路径是局部瓶颈，worst reclaim slack **-0.348932 → -0.439257 ns**，失败 reclaim 位从 12/16 增至 16/16。

总新增 absolute TNS 中，**4.119904%** 落在 PM endpoints，**95.880096%** 落在其他 endpoints。这是 endpoint 记账，不是“PM1 导致全部退化”或“PM1 只造成 4% 退化”的因果证明。其他未改 RTL 在全顶层 remapping 后也变差；采样的 ready/request 路径跨越 arbiter、memory、ingress、sidecar/registry 等控制链，部分并不经过 PM。

结论：PM1 需要先独立改善 selector/验证等价，暂不作为 WCG1 的集成基线；同时顶层还需要独立审查长组合 ready/valid 依赖，不能等 PM1 修好就假定 2 ns 自动闭合。

### 8.3 WCG1 隔离结果不能直接折算为顶层

真实 wrapper r2 matched hold-pass：reference **2,295,026.201759**，WCG1 **1,936,432.671921**，省 **358,593.529838 / 15.624812%**；保留 366,336 table bits，4,608 native CKLNQD1 gates，TE=0。setup/hold 零违例，但 candidate worst setup slack **0.000000 ns**，没有已证明的正 setup 余量。gate-enable setup/hold slack 分别 **+0.740547/+0.211413 ns**。

根时钟直接 fanout **400,110 → 38,382**，下游时钟与其负载仍然存在；不能据此称 clock power 减少 90%。两侧仍有 lint/min-cap、TIM-134 等，结构清洁未完成。完整顶层与隔离 wrapper 的上下文、端口裁剪和 STA policy 不同，不得把隔离节省直接减去 RD1 顶层面积。

当前登记的下一轮是 **RD1+WCG1，PM1 off，RD2 excluded**。本轮仅引用[launch 记录](dc_rd1_wcg1_full_paired_launch_20261107.md)：最后本地快照还在 contextual export/guarded pipeline，source freeze 与正式 paired DC 尚未验收；本轮没有刷新远程。应保持原策略 primary、propagated-clock supplemental、matched hold-pass 三层结果各自独立。

### 8.4 结构清洁和时序的结论边界

entry_id 的 48 个映射后 output bits 已有 driver 检查通过，LINT-3/LINT-5 为零；这是定向缺陷闭合。RD1 仍有约 44,536 Warning lines、两个高 fanout nets；大量 typed feedthrough/unused-pin 需要逐端口分类，不能靠删必要字段“消 lint”。Full-KV 的同一 VER-41 baseline diagnostic 被保留，并非整次运行 warning/error-free。

所有完整 Route-A primary 结果 setup 都失败。没有 CTS、布线、MCMM、物理 hold 或功耗证据；现有逻辑 hold 零违例不能替代这些。时钟不放宽，Full-KV 不扩大，父控制不黑盒化，不删必要状态。

主要结果来源：[metadata](dc_control_refinement_result_20261103.md)、[compact](dc_m2_p3_wrapper_compact_membership_result_20261104.md)、[entry_id repair](dc_m2p3_entry_id_repair_result_20261105.md)、[RD1](dc_rd1_full_paired_dc_result_20261106.md)、[PM1 full](dc_rd1_pm1_full_paired_result_20261107.md)、[STA diagnosis](dc_rd1_pm1_setup_diagnosis_result_20261107.md)、[WCG1 wrapper](dc_wcg1_wrapper_mapping_retry_result_20261107.md)。

## 9. 完整增量成本：DC 之外还有什么

下表沿用 [17 行增量账本](route_a_incremental_storage_cost_ledger_p0_20261106.csv)；“排除”指 child body 在控制投影中被 typed proxy 替换，不是该项没有硬件成本。重复的容量、parent 和外围必须分开，只计一次。

| 成本项 | 当前实例容量/需求 | 当前 DC 覆盖 | 尚须证明或计价 |
|---|---|---|---|
| P3 payload staging | 36×512×512 bit = **1,179,648 B** | child 排除 | 全宏、padding、bank/width mux、外围、能量/时序 |
| P3 local sidecar | 36×64×64 bit = **18,432 B** | 同 child 排除 | 独立写资源、position 服务映射及代价 |
| P3 child protocol | **558 declared bits** | 同 child 排除 | tags/acks/held response/access logic |
| 两张 compact 表 | **366,336 bit** | parent 已映射 | 当前实现已计 cell area；动态能量/物理开销未闭合 |
| M2 head replicas | 2×288×128 bit = **9,216 B** | child 排除 | lookup 与双写原子性、宏/外围 |
| M2 spans | 614×128 bit = **9,824 B** | 同 child 排除 | 双写带宽/冲突、bank、padding |
| M2 child protocol | **178 declared bits** | 同 child 排除 | response、ack 与外围 |
| M2 parent control | mixed state/control | 已映射 | activity/energy、实现级时序；不要整块再次加价 |
| metadata bridge/credit | 36 group slots 等 | 已映射 | 与历史 queue provision 对齐及活动代价 |
| R5 allocated/generation | 146,880×9 bit = **165,240 B** | child 排除 | 不是只需 18,360 B 的 1-bit bitmap；generation 及端口必须计入 |
| R5 active parent | 规格 active descriptor image 3,456 B；不等于 parent 全部 bit 数 | parent 已映射 | 区分现有 parent 与未来新增宏/外围，避免双计 |
| common S2 payload | **65,536 B/contour** | 两侧 child 均排除 | 固定面积需证明相同 geometry、宏与 shell；动态活动的差分单独计价 |
| Route-A S2 sidecar | **1,024 B** | Route-A child 排除 | 增量 array/peripheral |
| R5 external descriptor | 146,880×16 B = **2,350,080 B** | 外部服务 | 独立 descriptor region、maintenance 交通/控制/能量；不是单独免费 controller |
| pending/packed backing | workload/共享 HBM pool 相关 | 外部服务 | pending authority、位置、迁移 reserve、服务与拥塞 |
| R4 numeric/partial state | 尚未选择具体算术/放置 | structural adapter/control 部分已映射，numeric/partial 外部 | exp/precision、merge、spill/state、source-PE 差分 |
| core-memory service | controller/PHY/CDC 等未选择 | 本地 R1/R2 已映射，外部服务未计 | 共享服务可实现性、Route-A 增量流量、仲裁与能量 |

还须补齐未覆盖的 integration shell、interconnect、clock/reset tree、wire、leakage、ECC/alignment、real HBM provision 等。当前 top 中已映射的 shell/mux/parent adapters 已包含在控制面积内，不能再加一遍。共同项和 Route-A 特有项要分别证明，不能全部加给 Route-A，也不能全部说成共有而抵消。

排除在本地 array children 中的互异**名义数据容量**合计 Route-A **1,448,920 B**、Full-KV **65,536 B**，差 **1,383,384 B**。这不含协议位、外围和 padding，不是额外外部 HBM 总量，也不是物理面积下界。

历史 A4 的 M2 proxy 是 **32 nm、旧 64-bit word/profile、约 312 KiB 包络**；当前逻辑 entries 是 **128-bit word、19,040 B**，且双写/lookup 合同不同。历史 M2 **0.52857872 mm²**、common S2 proxy **0.580656 mm²** 不能与当前 28 nm DC area 直接相加或视为当前 macro 已计价。

### 9.1 P3 与 M2 的可实现性，不能只看 byte 数

P3 具有 payload W、payload R、sidecar W 三条独立 lane。read response 可停顿，ready=`!pending` 且没有同拍 consume/replace；这给了 read/write 冲突后一个 drain edge。现有模型支持“1RW payload + deferred write buffer + held response”的候选组织：主有限模型 **160 states / 37,888 transitions** 未出现 mismatch，并有三种错误组织的反例。

这只是两地址/二值 payload 的协议模型，不是参数通用证明、candidate RTL、宏映射或 2 ns 实现。额外 adapter 草图是 **529 bit**，连现有 558 bit 为 1,087 bit，宏 Q 与外围还要单独核对。可以继续验证，但不能宣称 P3 已有面积优化；P3 当前本就不在 mapped area 中。

M2 的 lookup 至多一笔 outstanding，但有两路**不带 ready 的 Valid 写**，可同拍到达不同地址；简单复制 1RW 存储不能自动满足两路写。必须先证明双写吞吐、lookup 返回与原子性，再讨论具体 bank/复制/宏选型。

来源：[P3 feasibility](p3_staging_storage_mapping_feasibility_20261106.md)、[增量 P0](route_a_incremental_storage_cost_ledger_p0_20261106.md)。P0 的 32 个登记 source hashes 本轮 31 个仍匹配；`RouteAMeasurementDut.scala` 因后来的 WCG1 contextual constructor forwarding 已漂移，账本不能宣称当前 32/32 匹配。核心 storage 定义与历史证据仍有各自匹配记录。

### 9.2 什么面积比可以接受

当前没有研究证据能指定“控制面积 5×、10× 或 100× 就可接受”。应先确定论文原型的 common provision、目标资源/时序与增量预算，再按同技术、同功能和同服务口径判断。

设当前已测控制面积分别为 `A_RA_ctrl`、`A_FK_ctrl`，在这两项已测控制面积之外、已证明相同的额外共同面积为 `C`，尚未计入的特有成本为 `U_RA/U_FK`，完整比值应是：

```text
(C + A_RA_ctrl + U_RA) / (C + A_FK_ctrl + U_FK)
Delta_A = (A_RA_ctrl - A_FK_ctrl) + (U_RA - U_FK)
```

已测控制面积中本就含有部分 common 控制；这里的 C 只允许加入额外、未计入 A_ctrl 的共同 provision，以免双计。同加 C 会降低表观比值，却不会消掉增量。`U_RA-U_FK` 可能进一步增加负担，现有材料没有足够价格给出最后数值。因此既不能拿 146.747× 宣判整机失败，也不能靠补一个大 common 分母宣称设计合理。当前 RD1 已测控制差额为 **3,365,505.913364 cell-area units**；先完整说明它，再处理缺项。

## 10. 主要问题与有限的解决门槛

下面按对论文论证的影响排序；这是后续建议，不是本轮修改或启动授权。

| ID / 问题 | 性质与当前证据 | 有限验收门槛 | 不满足时的处置 |
|---|---|---|---|
| BRIDGE-LIFETIME：模型与持续 RTL 服务之间缺桥 | A4 drain 与 production 一组/reset、one-shot activation 不同 | 明确论文 execution envelope；有界多 group/重复 page reads、reset-free reuse、identity/retire 的可执行对应，外部驱动职责显式列出 | 收窄为 first-use/control 原型，不能宣称完整 decode 后端 |
| COST-COMPLETE：完整增量未计价 | 17 行账本及 controller/numeric/shell 缺项 | 同技术/接口/活动口径的逐行数值或有依据的保守上界，避免双计；动态能量预算独立核验 | 保留条件性 DSE，不下硬件净收益结论 |
| STORE-CONTRACT：通用容量/多读口与成本 | 366,336 bit，opaque64、valid-low ready、独立读取已核对 | 每字段来源/最后使用/最大 live 与 reset/reuse 的证明；区分 generic 必须保留与 production 可提议 specialization | 不凭单组测试删字段、缩容量或共享非法端口 |
| TIMING-TOP：长组合控制依赖 | RD1 -0.36 ns、35,959 violating paths | 原 2 ns 同约束的因果路径分类；任何改法先验证 handshake/并发，再映射 setup/hold | 如需改变周期接口，独立版本化评审；不放宽约束冒充修复 |
| WCG1-INTEGRATION：隔离收益能否保留 | wrapper 正向，整顶层尚无本轮验收 | 收取既有流水线；full input/tool closure、mapped area、primary 与 gated-clock/hold 各 tier、lint 全部独立判断 | 保留已知隔离正结果，完整结果如实正/负；不自动重试 |
| PM1：小面积换较差 setup | full -0.901596%，reclaim 低位路径退化 | 独立 selector 等价与匹配 context STA，确认同周期和 top 影响 | 暂不集成；不为等 PM1 阻断 WCG1 |
| RTL-CLASS-KIND：R2 静态防护候选 | compatibility 计算结果未被返回式使用；未仿真 | 核对合同；定向 mismatch/合法对照，证明接收或拒绝行为 | 如确认缺陷，单独修复/回归，不改 arbitration 语义 |
| QUALITY-SCOPE：same-mask 与 policy-on 的边界 | predictor-only、在线 5 flips、有限 same-mask | 与论文主张匹配的正式质量证据或清楚保留原方法/固定 mask 的范围 | 不新增“任意模型/请求 faithful”主张 |
| DOC-AUTHORITY：长文档的 current 字样漂移 | header/README 历史 next-step 与末尾新记录混合 | 新复审入口、阶段时间线、证据级别和 source pin | 不靠聊天回忆或标题判断当前状态 |

不要把每个未知都变成新实验。先判断它是否阻断目标论文主张；只为必要且尚无证据的项建立有限验证。现有失败产物/负结果全部保留，新的候选使用独立版本与单独提交。

## 11. 论文到什么程度可以说明设计合理

目标不必是完整产品或完整 NPU。一个可信的研究原型至少应使以下链条在同一声明范围内成立：

1. **机会真实。** 原 mask 与 lifecycle 来源清楚；短请求、不确定 horizon 与失效情形公开，不用长输出覆盖它们。
2. **机制可执行。** 指明哪些控制 RTL 真正执行、哪些由环境提供；对所主张的 repeated decode/多组范围有对应的有界验证，而不仅是首次使用成功。
3. **资源可实现且计价完整。** 对每个必要增量给出相容的实现/proxy/保守上界，端口、延迟、外围、存储和外部服务不漏项。无需把所有共同 PE 都重做一遍，但必须给出共同抵消依据。
4. **收益在完整账本上仍有余量。** traffic、动态能量、面积和性能分别评价；若论文主张某 2 ns 硬件实现，则相应 setup/hold 必须有闭合证据。若没有，只能明确写成未闭合的 feasibility/conditional 结论。
5. **可复现且可被反驳。** 公布 frozen 输入、对照、native metrics、负结果和 stop criteria，使失败条件也清楚。

| 目前可写的表述 | 当前不能写的表述 |
|---|---|
| 指定模型/请求上原 predictor 可运行并产生给定 logical 稀疏率 | 已完成官方全面准确率或跨模型 faithful 保证 |
| 固定 trace/service 假设下 Route-A 有条件 traffic/energy 机会 | 逻辑压缩等于实测 HBM/显存/速度收益 |
| 有界 RTL owner/publication/first-use/retire 路径通过已登记测试 | 长期完整 decode 数据/数值闭环已完成 |
| 特定 control projection 的同库同约束映射面积已降低 | 全芯片 PPA、硬件净收益或外部服务零成本 |
| WCG1 隔离 wrapper 有正向面积结果及局部门控 STA | WCG1 全顶层已按同比例节省，或已解决全局 2 ns |

“目前做不到最终硬件净收益”与“之前几个月没有结果”是两个不同判断。已有研究清楚回答了 mask、packing、摊销条件、ownership 和一部分 realization 成本；尚未完成的是把这些连接为成本和时序都可接受的同一实现。

## 12. 建议的下一阶段顺序

**先收取正在等待的 RD1+WCG1 结果，再围绕执行范围、存储合同、完整成本和关键时序做一次有限收口；暂不扩散更多局部 selector 优化。**

1. 用户通知远程结束后，只读验收既有流水线。保持 PM1 off/RD2 excluded，完整核对外层/双边 markers、hashes、DDC/mapped HDL、原策略与补充 STA、setup/hold/clock-gating、hierarchy/seq/comb/fanout/lint。失败先定位，不能自动重启。
2. 形成一份论文 execution envelope 与合同差异表：哪些长期行为由 runtime/模型驱动，哪些由 RTL 支持；哪些 generic 行为必须保留，哪些可以另提明确受限的 production specialization。这个决定先于任何容量缩减或同步 RAM 替换。
3. 并行做有界存储实现与成本补齐：compact 的访问合同/最大 live 证明，P3 的真实 adapter/宏候选，M2 的双写映射，R5 的 generation/descriptor 服务；每项先明确是否影响当前 mapped numerator、遗漏成本或二者。
4. 独立梳理顶层关键组合依赖。先修不改变周期行为的具体长链；若仍不可行，再提出带新版本、全握手回归和系统服务模型对齐的接口实现方案。不能在当前 fair-v1 下静默换周期合同。
5. 将上述结果一次性回填成本/服务账本。若保守计价后有余量、执行范围接上且所主张时序满足，推进论文实现论证；若仍没有，明确缩小硬件主张或报告 realization 的局限。不要通过重新改 mask/DSE、扩大 Full-KV 或忽略外部服务来恢复好看的数字。

本报告没有批准以上新的长任务、RTL 变更或冻结合同修改。它也不暂停或干预用户已授权的远程流水线。

## 13. 下次讨论的最短阅读路径

- 重新理解研究过程：本报告 §§1—4、11—12；细节查 [research plan](route_a_research_plan.md) 和 [A0—A3 archive](route_a_stage_archive_20260902.md)。
- 判断算法证据：baseline/v1/v2/Route-B freezes、A3.15/A3.20 与 A4.14.1；配套 JSON 保留精确来源。
- 判断功能范围：[architecture spec](architecture_spec.md)、[C4-D review](rtl3_9_c4_d_functional_completion_review.md)、[paired profile](paired_control_projection_profile_20261028.md)、本报告 §6。
- 判断硬件成本/时序：本报告 §§7—10、[增量账本](route_a_incremental_storage_cost_ledger_p0_20261106.md)、[RD1](dc_rd1_full_paired_dc_result_20261106.md)、[PM1 STA](dc_rd1_pm1_setup_diagnosis_result_20261107.md)、[WCG1 wrapper](dc_wcg1_wrapper_mapping_retry_result_20261107.md)。
- 接续远程实验：仅从 [RD1+WCG1 launch](dc_rd1_wcg1_full_paired_launch_20261107.md) 与其 JSON 查状态；本报告的 launch 快照不替代远程完结验收。

本轮检查结果、源文件 pins、数值与问题关闭条件以 [JSON](route_a_deep_review_evidence_20261107.json) 为补充；它不取代原冻结记录。
