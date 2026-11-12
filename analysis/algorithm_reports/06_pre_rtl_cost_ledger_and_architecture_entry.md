# R6：前RTL成本账本与架构入口判断

整理日期：2026-11-12。范围：A4.11—A4.14.1，解释当时怎样从软件执行和声明服务
模型走到成本账本，以及为何允许开始编写架构规格。本文提取既有合同、冻结
结果及其输入副本，没有运行模型、CACTI、服务重放、RTL或DC，也没有删除资料。
本次的输入校验与账本算术复核，不等于重做全部上游实验。

固定范围为Qwen3-8B、官方KVzap MLP、threshold −4、原始replayed mask、hot128、
page64、admission budget512、36层/8 KV heads、GQA组4，以及retrieval、
summarization、reasoning各一个内置请求的8-token上限配置。最终账本观察到的
attention位置数分别29、42、72，含相应multi-token/question与decode范围；
它们是三个固定实例，不是正式准确率benchmark或真实请求分布。

## 1. 这一阶段要把什么账算清楚

[R5](05_pending_and_metadata_resource_exploration.md)已经明确pending、metadata、
原子commit及有限服务合同。但“数据能管理、模型能排空”没有回答成本问题：
少读的KV，能否覆盖新增的搬运、存储和管理工作？

本阶段把收益链拆成四步，避免把逻辑删除率直接当成硬件收益：

```text
软件实际选择/生命周期
  → 页对齐后的容量和公平读取字节
  → 声明服务量与显式访问能量
  → 扣除已计增量，给尚未计价的差分成本留下预算
```

**最终结论是有条件地允许进入architecture specification：三个固定workload
均通过公平HBM流量的2×工程余量门槛，已计动态能量差为正，且同workload的M2
模型无损排空。完整控制、P3、merge及外围尚未全部计价，统一时序也未建立，
所以没有证明完整硬件净收益。**

| 阶段 | 实验目的与计划 | 结果及对下一步的作用 |
|---|---|---|
| A4.11 | 将三路径语义和lifecycle绑定到真正external-cold软件实现 | exact-token与trace关系有明确依据；仍需从标量事件映射到资源工作 |
| A4.12 | 评估metadata存储、服务和部分能量 | M1被拒，M2是完整SRAM-proxy候选，M3缺寄存器成本；当时成本与收益workload尚未配对 |
| A4.13 | 给KV payload声明backing、staging、GQA复用和source buffer，并计价 | 得到公平字节与目标服务模型；保留尾页、填充停顿和未计项 |
| A4.14.0 | 将M2成本重放到上述同三个软件workload | 补齐metadata与payload的workload对应；不增加新候选 |
| A4.14.1 | 汇总共同设施、固定增量、动态访问和遗漏成本 | 得到条件性架构入口决定，结束研究性DSE |

## 2. A4.11：先保证收益和成本对应同一条真实软件路径

**目的与计划。** 早期policy reference与后来的external-storage软件实现不同。
不能用一个实现的生命周期，去解释另一个实现的计时或存储。A4.11先固定三条
路径：Full-KV bypass、same-mask dense、external-storage Route-A，再把lifecycle
observer放到最终external-storage路径，且从第一次prefill append之前开始记录。

**结果。** A4.11.2b要求same-mask dense、external trace-off和trace-on的生成token
ID完全对应，mask恰好消费一次，外部两路径最终scalar状态对应；已接受的绑定
保留了这些guard。Full-KV与裁剪路径的答案相同不是必要条件，不能据此升级为
算法质量通过。数值检查继续保留各自FP32/quantization-aware标准及record-only
ULP诊断。来源：[语义合同](../route_a4110_semantic_contract.md)、
[external lifecycle合同](../route_a4112b_external_storage_lifecycle_contract.md)、
[已保存的A4.11.2b绑定结果](../experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/a4112b_source.json)。

软件直接观察的是maturity、pending、admitted和packed页状态。后续将保留token
按64-token span及append-event/layer/head组成事务组，是确定性转换；bank、
credit、micro-op完成和physical commit仍由模型声明，未由软件测得。

**分析。** 这一步补上了“算的是哪条路径”的连接。它不等于硬件已经实现完整
生命周期，也不能把转换出来的事务组称为真实总线请求或SRAM访问。

## 3. A4.12：metadata需要什么存储，哪些实现假设没有通过

**目的与计划。** 固定HA8-wide、record-granular、head-affine八bank、
`local32/shared256/staging512`及原FIFO/ownership/credit/commit语义，只比较
三种metadata映射。抽象2/2/2服务需求没有直接作为物理2R2W宏输入；CACTI宏
均是明确的1RW proxy，如何组合满足服务另用模型检查。

| 候选 | 计划实现方式 | 已有处置 |
|---|---|---|
| M1 | 每bank一份metadata 1RW SRAM，head/span争用；RMW占两个服务坐标 | 没有排空所有冻结context，被拒为完整映射 |
| M2 | 每bank两份head-control副本＋一份span-owner SRAM；head更新显式镜像 | 作为完整SRAM-proxy候选进入后续账本；镜像写不免费 |
| M3 | head-control放小寄存器热状态，span放SRAM | 有服务可行性记录，但寄存器面积/能量未估，不选为完整成本赢家 |

处置依据见[metadata侧收口记录](../route_a_research_plan.md)及
[partial-ledger合同中的候选处置](../route_a4123_metadata_partial_ledger_contract.md)；
[A4.14.0接受结果](../experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4140_source.json)
继续显式保留M1拒绝、M3未计价、只重放M2的范围。本文未重新验收M1/M3原始运行。

固定成本采用public CACTI、0.032 μm技术proxy，M2列出宏实例的面积为
**0.52857872 mm²**，包含其保守queue/staging宏provision。它是按36层作出的
声明映射，还包含最小数组padding；不是根据某一请求峰值缩小后的生产宏。
controller、arbitration、scoreboard、commit、wire/clock及未估register均在外。

动态成本则按实际模型access乘pJ/access。M2 head写/RMW要更新两份副本；M3
寄存器能量没有用CACTI的SRAM值代替。特别是，**M2 queue/staging的宏面积有
计入，queue/staging动态access没有完整映射，不能把head/span能量当总M2能量。**
来源：[宏包络合同](../route_a4121_metadata_macro_envelope_contract.md)、
[服务/能量合同](../route_a4122_metadata_cycle_energy_contract.md)。

**分析。** A4.12.3只能把metadata成本和payload机会并列呈现：168个metadata
context与三个external-storage请求当时没有逐一配对。不能拿两组独立数字相除
宣布net benefit；这成为A4.14.0必须解决的缺口。

## 4. A4.13.1：payload放在哪里，packing是否需要额外搬运

**目的与计划。** Packed cold保留在HBM，按512 B K+V/record、64 records/page
计为32 KiB/page；每record另有8 B position sidecar。本阶段只比较三个声明映射：

| 候选 | Pending与packing的组织 | 明确承担的代价 |
|---|---|---|
| P1 | 独立pending HBM backing，再写packed HBM | 保留项pending写、admission读、packed写，共三次512-B HBM搬运 |
| P2 | layer-local pending SRAM，再写packed HBM | 减少pending HBM搬运，但需要承载pending峰值的SRAM及本地访问 |
| P3 | 保留pending HBM backing，每layer加一页SRAM staging | 承担P1的HBM搬运，另外承担stage读写；按页分块而不丢弃/重排 |

在三个固定请求中，P2按观察峰值映射的pending SRAM容量分别18,656,768、
17,047,552、44,144,640 B。它是较大本地存储的参照，不是免费消除pending成本。
后续沿用P3：每层一页、共`36×64×512 = 1,179,648 B` staging（1.125 MiB），
仍需pending HBM backing。这里的P3 payload stage与R5中的metadata staging512
是不同存储。来源：[payload组织结果副本](../experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4131_source.json)。

**结果与分析。** 原mask的逻辑容量机会保留，但尾页并非零成本。三个workload
最终packed payload相对其逻辑有效payload分别放大1.3249×、1.3489×、1.1254×。
Cold删除率也不能直接用作完整驻留量下降，因为hot、页取整和sidecar仍然存在。

以下是最终账本的**末态payload＋position sidecar容量**，不是整套后端容量：

| workload | 成熟cold逻辑删除率 | Full-KV payload(B) | Route-A hot＋packed＋sidecar(B) | Route-A/Full |
|---|---:|---:|---:|---:|
| retrieval | 83.98% | 137,723,904 | 44,499,968 | 0.323110 |
| summarization | 85.16% | 137,576,448 | 43,002,368 | 0.312571 |
| reasoning | 84.42% | 310,099,968 | 70,724,608 | 0.228070 |

末态admitted与packed数量之差为0，是账本中的确定性finalization核对；没有
虚构独立的trace-end事件。上表不含P3 stage、M2、完整控制、推理过程中的
pending峰值等，也不是GPU allocator或HBM物理容量测量。来源：
[A4.14.1最终容量链](../experiments/route_a4141_accounted_net_benefit_ledger_01/a4141_accounted_net_benefit_ledger_report.json)。

## 5. A4.13.2—4.13.5：公平地少读多少，双buffer能否隐藏搬运

### 5.1 先修正Full-KV对照的GQA复用口径

**目的与计划。** 一份KV供四个query heads使用，不能让Route-A共享一次读取，
却让Full-KV重复读四次。早期A4.13.2的Full-KV no-reuse只保留作归因参考；
A4.13.3以后，headline是两边都拥有相同合法GQA复用。

合法复用要求同layer/KV head/position/phase的四个query-head事件具有相同
source长度和page状态，逐组验证，不是直接把全部字节除以4。Full-KV causal
span也按相同64-token页取整。Route-A packed页额外带512 B position sidecar。
来源：[公平GQA合同](../route_a4133_packed_kv_hbm_realization_contract.md)、
[对应结果副本](../experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4133_source.json)。

**结果。** 最终HBM字节账本包含Route-A attention源读取、packed sidecar以及P3
admission的pending写/读和packed写：

| workload | 公平Full-KV(B) | Route-A attention(B) | 另加P3 admission(B) | Route-A总量(B) | 总量/Full |
|---|---:|---:|---:|---:|---:|
| retrieval | 4,105,175,040 | 1,283,346,432 | 57,133,056 | 1,340,479,488 | 0.326534 |
| summarization | 5,898,240,000 | 1,791,810,048 | 52,835,328 | 1,844,645,376 | 0.312745 |
| reasoning | 22,262,317,056 | 5,044,422,144 | 136,094,208 | 5,180,516,352 | 0.232703 |

这些是本次固定观测范围的声明HBM accounting，不能改称真实HBM总线计数，
也不代表整个prefill/模型推理的总流量。来源：[最终流量账本](../experiments/route_a4141_accounted_net_benefit_ledger_01/a4141_accounted_net_benefit_ledger_report.json)。

### 5.2 Source buffer与partial：共享读取不等于共享全部计算

A4.13.4固定`FILL → READY → 四消费者及partial更新 → RELEASE`：四个消费者
完成之前不能回收buffer。每个活动GQA组仍需四份独立partial，按FP32接口为
`4×(128+2)×4 = 2,080 B`；它只是接口大小，没有选RF/SRAM或实现merge算术。
来源：[source复用与merge合同](../route_a4134_page_source_reuse_interface_contract.md)。

A4.13.5再比较S1单32-KiB buffer和S2双32-KiB ping-pong。每buffer用一个
128×2,048-bit、1RW public-CACTI proxy；S2通过不同buffer分别fill/consume，
不是假定一块存储免费多端口。每页128次fill write、128次multicast read，
后者广播给四个query heads，不重复计四份宏读。

目标profile固定64-B modeled transaction、read/write startup32、HBM读8 pJ/B、
写10 pJ/B、consumer每模型周期消费一个256-B内部beat。主点256 B/model-cycle，
唯一敏感性点128 B/model-cycle，其余系数相同。这些是声明参数，不是厂商HBM
规格或实测参数。来源：[profile配置](../../hardware/route_a/payload/a4135_target_profiles.json)。

**重要负结果。** Route-A一页含sidecar时，两个profile的fill分别162、292个
模型周期，consume均128，均不满足`consume ≥ 下一页fill`。S2有重叠价值，
但不能完全隐藏填充；source-buffer结果另外保留warm-up、drain与fill stalls。
来源：[目标服务/能量结果副本](../experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4135_source.json)。

最终Route-A/Full的HBM-service坐标比，主点分别0.314848/0.301090/0.226705，
半带宽点分别0.320042/0.306270/0.229371。它们表示含P3的声明HBM服务工作量，
不是完整attention流水线时间。Metadata使用另一个服务坐标；两者没有共同
时钟、arbitration或overlap模型，不能相加成latency、tokens/s或speedup。

## 6. A4.14.0：把metadata成本放回同一组workload

**目的与计划。** 补齐A4.12的非配对缺口：从相同external lifecycle恢复保留项，
按固定64-token span/append-event/layer/head构成组，只重放已接受的M2映射，
不调queue、scheduler、mask、grant、执行粒度或commit边界。

| workload | 转换事务组数 | 完成数 | 最终metadata backlog | 声明M2服务坐标 | head/span entry能量proxy(nJ) |
|---|---:|---:|---:|---:|---:|
| retrieval | 2,828 | 2,828 | 0 | 1,081 | 19.426793 |
| summarization | 3,006 | 3,006 | 0 | 1,548 | 20.649555 |
| reasoning | 7,370 | 7,370 | 0 | 2,629 | 50.627817 |

三请求在声明界内无损排空，local峰值32，shared按层最大值分别92、86、235，
staging/held观察峰值均0。它们是特定重放的高水位，不足以缩减固定provision或
证明任意请求无需staging。每组包含head-control与span-owner RMW；镜像head
更新已计为每组两次head写，而不是假定副本更新免费。来源：
[同workload M2结果](../experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4140_source.json)。

**分析。** 这使head/span访问成本能够与同一请求的payload账本相接。表中能量
很小，仅覆盖指定entry宏访问；queue/staging动态访问、控制电路和互连未计价，
不能据此断言“metadata控制几乎零成本”。面积是固定provision，只记一次，
不能按三个workload相加成三套硬件。

## 7. A4.14.1：哪些成本计入了，哪些仍然没有价格

下表按最终账本口径分类。“有数值”仍可能只是确定性容量或proxy，不表示
相应硬件已实现。所有未计项均不能默认为0。

| 项目 | 已计入/已有数值 | 尚未计价或未建立 |
|---|---|---|
| Packed payload与hot | 末态容量、页取整；指定读取的HBM字节及profile动态能量 | 实际HBM分配、控制器映射、die面积及系统物理成本 |
| Pending HBM backing及packing | P3映射下pending写/读、packed写的字节和HBM能量 | 完整backing服务实现、地址/并发/控制器成本 |
| Packed position sidecar | 容量、每packed page的512-B HBM读取及对应profile传输能量 | 本地sidecar存储/latch、page管理与关联控制实现 |
| 共同S2 payload buffers | 64 KiB；public-CACTI面积0.580656 mm²；两边分别计实际模型access能量 | fanout、consumer/partial控制、wire/clock等完整实现 |
| Route-A M2固定SRAM provision | public-CACTI面积0.52857872 mm²，含列出的queue/staging宏 | target宏、replica coherence外围、arbitration/scoreboard/commit逻辑等 |
| M2动态访问 | 显式head/span entry的CACTI pJ/access×access数 | pooled queue/staging的动态access，其他控制状态活动 |
| P3 payload stage | 1,179,648 B容量；stage读写字节有声明记录；关联HBM搬运已计 | stage宏面积、本地读写能量、buffer/访问外围 |
| Partial与多源merge | 每活动GQA组2,080-B接口及逻辑动作 | RF/SRAM/spill、数值算术、数据通路和互连能量/面积 |
| 页管理、分配与descriptor维护 | 生命周期和接口义务保留 | 完整物理存储、维护流量、控制面积及能量未覆盖 |
| 外围服务与物理实现 | 仅有声明服务参数 | controller/PHY、interconnect、clock/wire、leakage、pads及布局 |
| 完整前端/模型推理 | 固定predictor/mask作为研究前提 | 该后端账本不是完整Transformer/predictor能量账；不能由范围外推导免费抵消 |

S2是公平Full-KV/Route-A共有的声明GQA基础设施，固定面积不算Route-A增量；
两侧的动态access仍各自计价。M2固定面积属于Route-A增量。两项public-CACTI
32-nm proxy既不构成完整芯片面积，也不能直接与后来DC cell-area units相加。
来源：[最终成本合同](../route_a4141_accounted_net_benefit_ledger_contract.md)、
[最终固定设施与遗漏项](../experiments/route_a4141_accounted_net_benefit_ledger_01/a4141_accounted_net_benefit_ledger_report.json)。

## 8. 最终动态能量差与“遗漏成本预算”应怎样理解

已计Full-KV动态能量是公平HBM＋source-buffer访问；Route-A是HBM/sidecar/P3
搬运＋source-buffer访问＋M2 head/span entry访问。P3本地stage能量、queue/
staging动态访问等没有被“含P3搬运”这一名称自动覆盖。

| workload | 已计Full-KV(mJ) | 已计Route-A(mJ) | 差分遗漏成本预算B(mJ) |
|---|---:|---:|---:|
| retrieval | 39.634086 | 11.988265 | 27.645821 |
| summarization | 56.945526 | 16.447075 | 40.498451 |
| reasoning | 214.935192 | 47.493007 | 167.442185 |

“每请求”指本文固定观测与accounting范围，不是完整LLM请求的实测能耗。主点
与半带宽点在该模型中具有相同字节、access和单位能量系数，所以能量表相同；
这不证明实际带宽减半时总能耗不变。来源：
[A4.14.1能量与budget](../experiments/route_a4141_accounted_net_benefit_ledger_01/a4141_accounted_net_benefit_ledger_report.json)。

预算的精确定义是：

```text
B = Full-KV已计动态能量 − Route-A已计动态能量

维持能量优势需要：
Route-A未计动态能量 − Full-KV未计动态能量 < B
```

例如retrieval还允许Route-A未计动态成本比Full-KV未计动态成本多约27.646 mJ，
超过后该模型的正号就不再保持。这不是“Route-A遗漏模块总共只能花B”，因为
Full-KV也有未计项；更不是面积预算、时序预算或遗漏成本已经被估出来。

组合能量由声明HBM系数与public-CACTI access proxy相加，只是accounted dynamic
energy proxy，不是同工艺、同物理实现的完整能量结果。未估leakage也不因等待
时间变长而自动进入表内。正B给出了后续实现必须接受的条件，而非净收益验收。

## 9. 当时为什么允许进入架构设计

**预设入口规则。** 每个workload/profile都要求：正确的exact-token/lifecycle
绑定、同workload M2无损drain、`Route-A含P3的HBM字节 ≤ 0.5×公平Full-KV`，
以及正的差分遗漏成本预算。2×是保留工程余量的门槛，不是压缩算法的自然定律，
也不是达到它便保证加速。

**实际结果。** 三个workload的HBM比分别0.326534、0.312745、0.232703，均小于
0.5；三个预算均正，M2均无损drain。最终决定为
`conditional_go_to_architecture_spec_pending_omitted_cost_budget`。

**分析。** 当时已经同时具备了有限语义路径、明确的存储/服务候选、公平比较
和未被已计成本吃掉的条件性余量，因而有依据把下一步转向架构规格：落实谁
拥有状态、接口如何交接、什么时候commit、缺少哪些宏/控制器和成本。继续
增加A4.14变体并不能代替这些实现义务，因此研究性DSE在A4.14.1收口。

该决定只允许编写规格；规格freeze/reviewer与RTL-entry是后续独立门槛。
它没有授权宣称PPA、2-ns时序、原生HBM、实测speedup、持续decode完整实现
或完整芯片净收益。后来的[architecture spec](../architecture_spec.md)保留了
共同/增量成本、遗漏预算与metadata/payload服务坐标不得相加等条件。

## 10. 这份报告承接什么，哪些原始资料仍需保留

R1—R6已经把原始mask机会、packing/摊销、功能执行、跨模型/前端边界、资源
管理和前RTL账本串到架构入口。历史上获得的是值得进入实现检验的条件性
假设；后来控制面积、时序和持续执行暴露的问题，需要由对应硬件证据回答，
不能用A4.14.1的许可替代，也不能反过来抹掉已观察的算法和软件事实。

本次直接核对最终报告、四份直接输入副本，以及既有本地恢复记录列出的绑定/
lifecycle制品；没有重新验收全部上游CACTI raw、模型输出或metadata重放。
部分传递依赖仍缺独立原始汇总，不能因为最终有输入副本便认为整个链条可从
底层重建。必要报告、副本、生命周期和payload trace、CACTI宏配置/raw及profile
参数仍保留原位；正文不展开启动、报错、重复交接或hash明细。

所有表格直接引用既有JSON，无新增配套数据包或来源清单。未来可据原始按
phase/workload/profile数据重绘容量、流量、fill-stall与成本图，图中仍须区分
trace观察、确定性accounting、声明模型、public proxy与未计价项。本文没有
授权清理任何原始资料。
