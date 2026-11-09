# Route-A 论文执行范围与实现收口 — 2026-11-09

依据：[深层复审](route_a_deep_review_20261107.md)、[复审证据账本](route_a_deep_review_evidence_20261107.json)、[RD1＋WCG1 完整验收](dc_rd1_wcg1_full_paired_result_20261109.md)。本轮源码／结果截面为 `cbf2296`，分支 `research/kvzap-latest`。

本文件落实用户要求的论文范围和后续收口顺序，是研究执行与证据计划，不替代 [architecture specification](architecture_spec.md)、通用 wrapper 合同或既有冻结。这里列出的未完成项不是新验收结果。本轮只更新分析与导航文档，不修改 RTL、容量、接口、冻结输入或 EDA 策略，不启动远程任务。

## 1. 论文目标与已证明范围

**论文实现目标确定为：在固定 KVzap mask 与 Qwen3-8B 有限实例下，建立可重复执行的 Route-A 生命周期／控制原型，并用相容存储实现、完整后端增量账本和顶层时序证据检验其合理性。** 不要求实现完整 LLM/NPU 产品；现有 first-use 成功还不足以完成这个目标。

| 边界 | 本阶段采用的范围 | 当前证据与限制 |
|---|---|---|
| 算法输入 | 官方冻结 predictor／原 mask；保留 hot128、maturity、admission、page64、publication、authority 与回收语义 | 历史质量／结构／模型证据沿用原范围；same-mask 后端实验不增加 policy-on 或普适 faithful 保证 |
| 实例 | 既有 Qwen3-8B／32K／单并发 sequence anchor，36 layers、8 KV heads、4 个合法 GQA consumers | 这是待实现与评估的有限资源边界，不表示当前 RTL 已执行整个 32K 生命周期，也不表示只改参数即可跨模型 |
| 执行 | 同一 session 内有界的 admission／publication、同页后续 decode 读取、terminal 与 retire/reclaim | 当前只验收 first-use contour；重复执行桥梁仍 OPEN |
| 控制实现 | RD1＋WCG1 为有实测面积证据的候选，PM1 off、RD2 excluded | 输入／工具／制品与面积已验收；整体时序、结构清洁和实现经济性未验收 |
| 外部边界 | runtime、memory responder、partial provider、R4 reference 等逐项说明职责、服务假设和费用 | 可用参考模型验证数值语义，不将其称为已综合数值 datapath；外部实体不能凭假设制造 DUT 尚未提供的持久权限或重复激活能力 |
| 论文结论 | 机制可执行性、条件性 traffic／energy 机会、实现代价及成立条件 | 完整账本／时序未通过前，不主张硬件净收益、系统加速、物理 PPA 或完整持续 decode 后端 |

研究边界从给定 mask／maturity 事件进入后端开始。后端以外的 predictor、Q/K/V、source PE 等可以列为外部服务；若要扩展到整个系统的收益，其非共同费用仍须加回。相同名称、外部接口或“已有软件”不能作为成本抵消依据。

## 2. “功能闭合”为什么仍有缺口

[C4-D](rtl3_9_c4_d_functional_completion_review.md)闭合的是：唯一 publication／逐成员 authority、首个正确 packed read、S2 READY、四消费者、terminal、retire/reclaim，以及已登记的 stale/mismatch/fault/reset 负例。memory、partial/R4 仍是明确的环境。**相对于这个有界合同，既有 PASS 有效；相对于持续 decode 后端，当前实现尚不完整。**

当前源码中的具体限制包括：

- production ingress 最后一位成员 relay 后进入 `StateDone`；没有正常重新收集下一组的转移。
- reconciliation journal 为 64 ordinal、每 reset 一组，保留到 destructive reset；不能只给 ingress 加 rearm 就推断多组成立。
- first-use activation 消费 page-ready／member-stream 后清除事实；未证明持久页查询／遍历可以为下一次 decode 再建立合法读取。
- R6 retire 后进入 `StateRetired`；没有正常 session reopen 证据。连续 generation／ID reuse 还需要 quiescence 对应。
- 当前 measurement cut 不提供真实 KV bytes 自主驱动 attention 算术链的证据。

源码锚点见 [ingress／journal／R6](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala)和 [activation binder](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAPackedReadActivationBinder.scala)，精确历史定位见复审 §6 及 JSON。上述事实限制持续服务主张，不推翻已验收的首次使用。

### 必须补上的最小执行证据

一次 packing、多次后续读取是摊销主张的核心，不能从论文执行目标中省去。先交付一张“冻结生命周期事件 → runtime 输入 → DUT owner／状态 → 可观察结果”的对应表，并列出可执行范围和未支持范围。

1. **重复使用：** 已发布页在不同 decode step 下重复被合法读取，经过所声明的 S2／四消费者／完成链；无需重新 publication，也不以每步 reset 模拟重复使用。
2. **持续 admission：** 若保留在线 maturity/admission 主张，同一 session 须能处理多 group；journal、stage、metadata、identity／generation 和权限的存活／重用必须一致。
3. **有界并发与结束：** 在声明范围内覆盖跨 layer/head、队列占用、合法 backpressure、stale/reset/fault、最后 retire 的排空；假设与 DUT 保证分别列出。
4. **数据与数值对应：** 分别注明真实 payload／sidecar、partial 参考计算与 merge 参考计算的执行位置，建立与给定数据的可检查对应。外供数值包的控制握手通过，不能替代该数据对应。
5. **与系统模型接轨：** 将所引用冻结 workload 的 group／page/read 数量与 horizon 映射到上述执行范围。两组、同页两次读取可以作为最小定向 witness，但不能代替容量、全部合法并发或整个 workload 的验证。

本阶段不以实现多 session 产品作为前置门槛。单 session 内不靠 reset 的重复工作是核心；session 结束后的新会话支持单独声明，不能与 session 内重复执行混淆。若补桥需要接口／状态生命周期变化，先提交版本化差异与验证计划，再实施；不能借本文件默默改变 R2/R3/R6。

## 3. 存储合同：先固定必须保存和服务的内容

交付一张以每个真实 owner／存储体为行的合同表：字段来源与精确宽度、容量、最大同时存活量及其证明域、最后使用／释放点、reset/reuse、端口、同拍并发、索引／alias、accepted edge、read-during-write、响应延迟、held response、valid-low ready、原子性。区分已证明性质、环境假设、尚未证明项。

| 对象 | 已核实事实 | 本阶段必须收口的内容 |
|---|---|---|
| 两张 compact 表 | `36×64×(79+80)=366,336 bit`，已计入 DC；两个独立 opaque64 占 80.503% | 保留通用容量与 RD1 后合法读并发；证明各字段最后使用和最大 live，区分必要信息与当前表示。不能由单组 production contour 推出通用最大 live 仅 64；不能默认截断64位或同步 RAM 等价 |
| P3 staging | payload 1,179,648 B＋local sidecar 18,432 B，另有 protocol；payload W/R、sidecar W 三独立 lane | 先验证现有 1RW＋deferred-write／held-response 候选的真实 adapter：原延迟、无 consume/replace、reset-safe drain、索引／碰撞，再匹配真实 macro Q／写模式、外围及2ns时序。现有有限模型不算 RTL／macro 验收 |
| M2 entries | 19,040 B、128-bit word；lookup＋两路无 ready 的 Valid 写，可同拍不同址 | 明确双写／lookup 并发、旧值读取、两 head replicas 与 span 原子更新、bank冲突与复位。91,902 reserved bits 是后续可验证机会，尚未证明可无代价缩窄物理存储 |
| R5 availability／descriptor | availability＋generation 165,240 B；external descriptor 2,350,080 B | 覆盖 generation 而非仅1-bit bitmap；明确活跃 parent 与 backing 的职责、descriptor 维护服务、失效先于 free、wrap／quiescence、端口与外围 |

通用 wrapper 的 held payload、pre-edge、valid-low ready 和独立消费者行为继续受既有合同保护。论文采用有限实例并不授权删字段、缩表或删无 binding 路径；production specialization 如有必要须另提明确差异。

实现候选按“现有合同可等价替换／需要新实现合同／尚无可行实现”分类。后两项不能登记为优化成功。P3/M2/R5 被排除的 child 优化主要减少尚未计价的成本，不直接降低现有 129.517× 控制分子。

来源：[STORE P0](dc_compact_store_p0_audit_20261106.md)、[增量存储审计](route_a_incremental_storage_cost_ledger_p0_20261106.md)、[P3 映射评估](p3_staging_storage_mapping_feasibility_20261106.md)。

## 4. 完整增量成本：绝对差额与比值分别报告

当前同库 primary 控制面积：

```text
A_RA_ctrl = 2,990,737.008920
A_FK_ctrl =    23,091.432498
Delta_ctrl = 2,967,645.576422 cell-area units
ratio_ctrl = 129.517170889...x
```

这已经是较大的实测增量。额外 Route-A 特有成本可能增加负担；但完整比值也取决于 Full-KV 特有项和共同 provision，不能直接断言一定比130×更大。

```text
Delta_A = (A_RA_ctrl - A_FK_ctrl) + (U_RA - U_FK)
ratio_full = (C + A_RA_ctrl + U_RA) / (C + A_FK_ctrl + U_FK)
```

`C` 仅含控制面积之外、已证明相同的共同 provision。共同费用抵消不减少绝对增量；加一个大共同分母不能单独证明经济性。未计价项写 OPEN，不写0。

沿用 [17行账本](route_a_incremental_storage_cost_ledger_p0_20261106.csv)，完成每项“已映射／共同且可抵消／差分待计价”的对照，并补齐如下字段：

- 实现／proxy／有依据保守界、工艺与单位、数据容量与实际 provision、padding、bank／复制、adapter／mux／tag／ack、ECC／复位等外围；已映射 parent 不再整块加价。
- 面积、动态能量、漏电、服务延迟／带宽分别记账。P3/M2/R5、position backing、R4 numeric／partial／spill、外部 controller／interconnect、clock/wire 都须明确覆盖或缺口。
- 两侧相同的容量、geometry、端口、控制壳与服务能力是固定费用抵消前提；动态活动差分仍需计费。源 PE／数值服务如被称为共同，也要说明 Route-A 特有 merge／状态／调用。
- 历史32nm M2/S2 proxy 不能直接与当前28nm DC cell area 相加；有据的技术归一或同口径重估之前，分别保留证据等级与不确定性。
- A4.14.1 的 27.645821／40.498451／167.442185 mJ/request 是三个原 workload 的**动态能量差分余量**，不是面积／周期预算。metadata 和 payload 的服务坐标在共同 clock、依赖／仲裁／overlap 未建立前不相加成 latency。

成本闭合不要求每个共同算术块重新做 RTL，但每个必要差分须有相容实现／可信 proxy 或有依据的保守界。若缺少能支撑主张的界，保留条件性结论。没有依据可指定“控制面积降到5×／10×即可接受”；预算须来自明确的资源／服务目标，不能在看到结果后挑一个方便的倍数。

## 5. 顶层关键时序：先解释现有失败，再选择改法

当前 primary setup worst slack **−0.469940 ns**，TNS **−12,698.75 ns／36,017**；门控 enable 与 table capture 的局部正 slack 不等于顶层通过。补充 hold pass 后 Route-A 仍有825、Full-KV有46个 hold 违例；不能把所有失败归因于 WCG1 门控。

先用已有 DDC／native reports 做有限诊断，交付三项内容，再决定 RTL 候选：

1. **长控制链：** 对 arbiter pending-association → sidecar-ready、stage-valid → registry-allocate-ready 等路径，展开跨 owner ready／valid 依赖、cell/net 延迟、fanout、完整起终点和 endpoint-TNS 分布。匹配前后 endpoint／cone，区分源码变化与 remapping 关联。
2. **共同补充策略：** 对 primary／propagated raw／hold pass 三个快照检查 launch/capture clock、skew、buffer／cell sizing、约束及 hold 修复覆盖。尤其解释为何 raw hold 零违例而共同 pass 后两侧均出现负 hold。先定位，不把文件夹名 `hold_repaired` 当 closure。
3. **有限修复选择：** 优先维持现有周期、并发与握手的结构改法；如必须改变流水／ready 周期，单独版本化合同并对齐服务模型，不能在 fair-v1 内静默改变。每项先局部功能／边沿验证，再匹配小综合，最后才考虑完整 paired DC。

始终保持原2ns、两侧相同约束、timed reset，无 false/multicycle 例外。原策略结果与门控／hold 补充结果分别保留；不能用119.016×的补充分母冒充新RTL面积收益。

若论文主张该范围内的2ns实现，则相应全顶层 setup、hold、gating 均须零违例，约束覆盖完整、native gate／driver／必要状态保留；仅 WNS 变好或局部通过不算闭合。此门槛仍是映射／STA证据，不自动成为 CTS／布线／MCMM／物理PPA结论。结构 warnings 按根因分类，功能相关项不能靠删除接口或必要状态消除。

## 6. 工作顺序、判定与停止条件

| 顺序 | 交付物 | 通过依据 | 未通过时的处置 |
|---|---|---|---|
| 先定范围 | 生命周期与 runtime／DUT 对应表、已支持／目标／未支持边界 | repeated-read／在线 admission 主张有对应执行与复用方案，环境假设明确 | 维持 first-use 原型结论，不称持续 decode 已完成 |
| 并行A | compact/P3/M2/R5 存储合同与候选映射表 | 容量／存活／端口／周期行为一致，证明域和外围成本明确 | 不开始无依据压缩／缩容／换宏 |
| 并行B | 既有 DDC 顶层 setup／hold 因果诊断 | 真实长链／时钟策略问题定位到可验证候选 | 不用再一次完整综合替代定位 |
| 随A/B回填 | 完整后端差分成本及服务账本 | 数值或有据界覆盖所主张增量，同技术／功能／服务口径，无漏项／双计 | 保持成本OPEN，给出敏感性与缺口，不下净收益结论 |
| 最后评估 | 论文实现结论与下一次候选 | 执行范围成立、资源可实现、对应账本有余量、所主张时序闭合 | 明确报告实现瓶颈或收窄硬件结论；保留已证实算法／模型／面积结果 |

这是一轮有限的可行性收口，暂不扩散新的 selector 试验。新长任务只有在具体诊断／输入冻结就绪后按已授权范围安排独立 tmux，并通知用户等待。R2 class-kind 静态防护候选仍单列待定向验证，不在本轮顺带修改 arbitration。

## 7. 如何理解目前的困难

当前瓶颈包含四层：系统模型有条件机会；有界控制正确性；通用逐周期接口下的存储／组合网络实现；完整成本与服务经济性。前两层的进展不会自动满足后两层。

早期完整 typed records、寄存器和组合读取便于验证身份／转权，是可以解释的保守选择。但宏端口、共同 clock 和外围成本后置，后来又把逐周期行为固定为兼容合同，使低成本实现选择减少；production 一次性入口与通用大容量也没有形成同范围的持续执行证据。这是需要正视的实现与验证规划缺口，不能只归为“硬件本来就难”。

另一方面，metadata、compact、RD1、WCG1 的真实映射收益说明已有具体冗余被消除；相对原baseline累计面积下降55.472043%。这不证明剩余代价都是综合器错误，也不保证继续局部优化一定能跨过经济性门槛。

本阶段要回答的是：**在论文明确的执行范围内，必要状态和端口能否合理实现，完整差分能否负担，关键控制能否在2ns工作。** 若答案仍是否定／未知，应相应限制硬件主张；不通过改mask、扩大Full-KV、忽略外部服务或删必要状态恢复好看的结论。

本轮文档检查：11个本地链接、9项容量／差额／比值算术、3个live入口及2份原证据JSON解析通过；独立只读复核未发现目标／验收混淆或静默合同改变。提交前检查 `git diff --check`。这些检查只验证本文的一致性，不增加功能、成本或时序证据。
