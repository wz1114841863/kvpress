# 阶段 A：Route-A 执行范围与生命周期对应 — 2026-11-09

**本阶段结论：执行范围和职责已定义；持续执行验证尚未完成。** 本轮按用户要求执行阶段 A，限定为当前源码到论文执行目标的定点映射及最小场景定义；不重做 MR-1/MR-2，不改 RTL／接口／容量，不运行仿真、DC、STA、模型或远程任务。

源码截面：`research/kvzap-latest`，`2a613f5`。上位执行计划为 [11月9日论文范围](route_a_paper_execution_scope_and_closure_20261109.md)，规范仍是 [architecture specification](architecture_spec.md)与各既有合同。生命周期、环境职责与未闭合问题见本文和[H2](hardware_reports/02_rtl_implementation_and_sustained_execution_scope.md)。该文件不是新的架构冻结或持续 decode PASS。

## 1. 本阶段明确的执行范围

| 层次 | 范围 | 证据身份 |
|---|---|---|
| 已验收基础 | first-use publication／authority → packed read → S2 READY → 四消费者 → attention terminal → 最终 retire/reclaim，及登记负例 | 沿用 [C4-D](rtl3_9_c4_d_functional_completion_review_manifest.json)，本轮不增加历史验收覆盖 |
| 最小持续原型目标 | 一个 session 内无需 reset：同一已发布 packed page 在两个不同 decode step 完成合法读取；至少两组 admission 完成各自 publication／handoff；瞬态资源按合同复用 | 下一批独立定向验证目标，**尚未执行**；不是已有完整后端 |
| 论文有限实例 | Qwen3-8B，context envelope 32K，单并发 sequence，36 layers／8 KV heads／4 GQA consumers，原 mask、hot128、maturity、page64 | 资源与语义边界，不表示已覆盖全部32K数据、全部合法并发或整个冻结 workload |
| 数据／数值目标 | 给定 Q、实际 K/V 与 logical position，经外部 reference partial／merge 建立可检查对应；控制 DUT 保留真实 owner／权限／传输 | 独立于协议包验证，当前尚未接通；不要求本阶段实现 attention PE／exp 产品 datapath |
| 后续覆盖目标 | 将所引用冻结 workload 的 group、page、read、horizon 映射到上述实现；按各 namespace／容量界和 wrap quiescence 扩展验证 | 最小两组／两次读取不能替代此覆盖；当前尚无持续服务率或最大安全运行步数结论 |

固定入口是 **post-decision 生命周期事件**，predictor／threshold 不进入 DUT；runtime 必须保证事件与冻结 mask、hot/maturity 时机及原始 token 对应。先保留单 active KV-head group等既有有限资源界，不新增跨模型、无界 decode、多 sequence、长期 session reopen 或任意 namespace wrap 主张。单 session 内的重复执行是本阶段必要目标；最终退休后重新启动 session 不列入该目标。

`rtl_entry_qwen3_8b_32k_s1_v1` 是架构参数档，`qwen3_8b_32k_s1_control_projection_v1` 是当前控制映射档。现有 `RouteAMeasurementDutR3Spec` 使用更小的测试参数及默认 `gateCompactMembershipWords=false`。三者分别登记；未来测试必须记录实际参数与门控 flag，不能将小测试或未门控测试自动称为 full-anchor／WCG1 全顶层动态验收。

## 2. 生命周期 → 输入 → owner → 状态／可观察结果

下表“已有机制”来自本轮源码核对；端到端历史验收仍以 C4-D 范围为准。内部观察可以由只读 monitor 捕获，不能由 testbench 驱动成前提。

| 事件 | runtime／环境输入或内部连接 | DUT owner 与状态／输出 | 当前边界 |
|---|---|---|---|
| 初始化 | `external_core_mem_if_v1.init_ack`；内部 statusCollector 收集 R1/M2P3/R5 init | R6 `initAcks`齐全，`StateReset→StateIdle` | 普通 response 不能代替 init；外部须隔离 reset 前旧响应 |
| session start | `frontend_lifecycle_req` 的 start kind，session_id=0、context_tokens=32768 | R6 `StateIdle→StateActive`；输入 fire | 不是模型前端或完整 prefill 已执行的证明 |
| KV arrival | 同一 lifecycle 口的 arrival kind、坐标、payload_ref | R6 向 hot owner 发 control／authority，hot 获得对应所有权 | 正确顺序／坐标／原始数据由 frontend/location owner 负责 |
| maturity DROP／RETAIN | lifecycle disposition；RETAIN另需 `pending_payload_read_binding_in` | R6 发 hot disposition、authority；RETAIN admission 三元事实进入 ingress | 不重算 mask；pending transport binding 不能由 payload_ref 猜出 |
| 收集 admission group | R6 context＋authority＋pending binding 同拍接受 | admission 保存 present／members／bindings；全员后 `Collect→Allocate` | 当前仅一组/reset |
| 分配／claim／prepare | ingress→R5 allocation→R3 P3 claim→metadata bridge→M2 control | allocation／claim／prepare 各自 fire；R5生成PageRef；P3 reserve | 所有 grant 来自真实内部 owners |
| relay 到 R3 | ingress 的 R3 admission triple | `StateRelay`逐成员发出；最后一位后 `StateDone` | 没有回 Collect 的正常转移，第二组首先在此被阻断 |
| packing／durability | pending owner 的数据与位置；R1 accepted requests／responses | R3 pack-read/P3 stage/packed-write；R5 descriptor durability | memory responder 只能回应真实请求；不能直接制造 packed publication |
| publication／转权 | R3 的 M2/P3/descriptor prerequisites，R5 visibility apply/ack | 唯一 publication；逐成员 R3→R6 authority fire；R3 member/page-ready observation | payload durable 不单独转权；部分组不得可见 |
| metadata handoff | `post_r6_packed_page_ready_observation.fire` | metadata bridge 清 groupActive／member mask，归还对应 logical credit | **credit已有归还机制**；与 journal reset-only 不同 |
| attention／plan | lifecycle attention kind＋`source_plan_declaration_in`，共同 identity | R6分配attention tracker，接受source-plan；fork送activation／packet owners | 已选source set外供；不是DUT自主遍历全部页的证明 |
| packed activation | R6 accepted plan＋R3 member/page-ready＋R5 descriptor grant＋S2 lease | binder精确join，内部发demand／publication authorization／descriptor／lease | page-ready与member事实消费后清除；重复activation缺持久事实通路 |
| payload／sidecar fill | R1→真实endpoint→S2；sidecar reference只处理owner已发work | S2 Filling→READY，identity／page／source generation精确对应 | 搬运完成不等于已经计算attention partial |
| 四消费者完成 | 外部partial/R4包经内部校验／commit | S2 consumer mask逐位清零；release fire后slot→Empty | 只释放本次source槽，不释放底层packed page |
| attention terminal | 匹配的四consumer merge结果或fault | outward terminal fire清attention tracker／plan／pending | **R6仍Active**；没有因此进入Retired |
| 同页第二次服务 | 新attention identity／step及合法source declaration | 应通过原页权限重新获得服务，使用新的source lease／消费者完成链 | 目标OPEN；不能重新注入publication或强改内部事实 |
| 第二 admission group | 同session的新组tag／成员／binding | 应完成独立join、prepare、publication、handoff与credit归还 | 入口StateDone＋journal ordinal寿命是独立缺口 |
| 最终 retirement | `runtime_retire_req.fire` | R6 Active→Retiring，停止新工作；先drain、给R5 permit，失效/free后final drain | 与单次attention terminal分离 |
| retirement ack | R5完成＋全部最终drain＋外部ack ready | `session_retire_ack.fire`，R6→StateRetired | 现有R6合同明确新session需destructive reset；不是本阶段待“修复”的产品能力 |

## 3. 四类身份／存活期必须分开

| 对象 | 两次读取之间的要求 | 何时释放／更新 |
|---|---|---|
| packed page／PageRef | 同一页的 page_id、page generation、有效内容与权威继续存在 | 最终合法retirement/reclaim；descriptor invalidation先于free／generation推进 |
| S2服务实例 | 每次合法服务使用对应lease与owner generation | 四消费者commit后release；复用同一slot时 **source generation推进**，不要求等于page generation |
| attention identity／tracker | 两个step使用不同的合法identity，不与live请求冲突 | 各自attention terminal接受后释放tracker；有限namespace复用／wrap另受quiescence约束 |
| group／membership／credit／journal | 组tag、成员和late lookup不可混淆 | metadata credit与R3 membership present已有handoff清理；journal binding保留到reset。不能为接收第二组直接清掉仍需late lookup的旧记录 |

源码特别确认：S2 release只接R6，未接Page Manager free；R6 attention terminal也不改变session state。因此不能把重复读取缺口归因于“读一次就把页回收／把session结束”。

## 4. 环境职责与 DUT 保证

| 角色 | 允许承担的工作／假设 | 不得替DUT制造的事实 |
|---|---|---|
| Runtime／冻结frontend | session／arrival／maturity／attention／retire；给定source set与对应identity；遵守mask、时序前提、ready/valid稳定 | publication、page authority、lease、source release、terminal、reclaim、drain |
| Pending payload/location owner | immutable binding、descriptor registration、hot/pending数据与position | packed visibility／新generation的合法性；不能用猜测替代两个opaque64事实 |
| Memory responder | 精确回应已接受R1请求，保留同一functional store；进展依赖最终完成假设 | 不从response臆造metadata／generation／authority；不能预装第二份packed页替代首次实际写入结果 |
| Sidecar transport reference | 根据association owner已发work生成精确allocation/read issue；functional默认内部、projection外置 | 不能凭空为第二次读创造page-ready、成员或publication authorization |
| R5 backing service | projection中精确提供Lookup／ReadLine／CommitLine；functional默认内部descriptor image | 不拥有allocator、liveness、转权或reclaim决定；费用不为0 |
| Partial provider | 供给同identity/source/consumer的已计算partial；数值目标中由明确Q/K/V/position参考计算产生 | DUT当前只校验协议关联，不能把合法carrier当作其数学值已正确的证明 |
| R4 provider | 根据accepted packets／merge work，返回对应consumer的一次result或numeric fault | 不可凭空回terminal，也不能把外部reference称为已实现exp／attention datapath |

安全性质由DUT保证；外部memory／consumer最终响应等公平性只支持progress。合法背压不能改变事件payload、mask、归属或顺序。有限test timeout只用于定位阻断，不是硬件吞吐保证。

当前top没有实际Q向量输入，且S2 payload／sidecar read接口被置inactive；现有R3Spec使用固定partial/result包。故首批场景命名为**协议／控制重复执行验证**。后续数据—partial—merge对应必须定义外部Q与实际返回K/V的可观察连接／参考计算，不能由包计数PASS代替。默认functional bodies与控制投影typed proxies也必须分开，proxy不得用于证明真实存储功能。

## 5. 下一批两个独立最小场景（本轮未运行）

### READ-REUSE：一次packing、同页两次后续服务

1. 一次reset/init/start；用真实functional array bodies与同一memory store完成组G0的admission、packing和publication。允许从一个合法tail页起步，page64容量不变。
2. 为step t提供attention A与source declaration；完成实际payload／sidecar搬运、四consumer协议commit、一次outward terminal。捕获PageRef及实际packed写入／后续读取对应。
3. 不发runtime retire，不再publication；为step t+1提供不同attention identity B。第二轮明确复用第一轮已释放的同一S2槽，按合同推进source generation，PageRef generation保持不变。
4. 要求第二轮合法activation、fill／READY、四consumer commit与一次独立terminal；第二轮数据来自G0原packed对象。观察恰一次G0 publication、两次attention完成及中间瞬态资源归还。
5. 最后只发一次retire，核验descriptor失效、reclaim、final drain与一次retire ack。旧page引用排除须有对应owner／状态证据，不能只以全局Retired拒收新请求冒充R5 stale校验。

禁止reset分段、内部poke／force、重新注入R3 member/page-ready／authorization／lease、host-side重新preload packed页、复用旧partial身份或把两次响应消费当两个独立decode服务。当前预期阻断在一次性activation事实，尚未动态复现。

### ADMISSION-REUSE：同session两组独立admission

1. 保留同一次init/session。G0完成publication与membership handoff后、最终retire前送G1，使用不同组tag、成员坐标／payload事实。
2. 起步用不同layer bank的G0/G1，各自ordinal从0开始，避免假定global ordinal永不复用；后续增加同bank合法stage复用变体。可各用一个合法tail成员，但不将其当容量缩减或最大live证明。
3. 检查G1是否真正被admission join接受并走到独立prepare／publication／handoff；核对各组credit归还、旧G0 late lookup／权限不被覆盖。
4. 当前预期先被ingress StateDone阻断；即使入口rearm，journal重复ordinal仍需独立处理。记录可达的第一阻断与后续静态义务，不把未执行的后续步骤称为动态失败。

两个最小场景均不等价于全部容量／并发覆盖，也不证明最大持续decode horizon。实施前明确实际p、门控flag和观测绑定；使用现有完整functional contour，不用黑盒父控制、数组proxy或人为权限输入“做通”。必要RTL补齐另以版本化差异定义，保留R2 arbitration、R3 sole publication、R6 authority及原2ns公平约束。

## 6. 当前差距、B1/B2与成本账本的接续输入

| ID | 本轮定位／目标 | 处置与需登记成本 |
|---|---|---|
| A-READ | 页仍存活，但R3/binder的一次性事实不足以重新activation | 先做READ-REUSE现状probe，再定义持久页事实／查询的最小补齐；其存储、查询、协议和关键链成本OPEN |
| A-GROUP | ingress StateDone；journal64 ordinal/reset，不同于已归还的metadata credit | ADMISSION-REUSE现状probe；group namespace、late lookup与rearm的状态寿命和成本OPEN，不能只清journal |
| A-DATA | Q缺少数值入口、S2读取未接partial；当前只能证明carrier控制对应 | 明确外部reference数据链及职责；numeric／partial服务成本OPEN，不要求先实现完整NPU |
| A-BOUNDS | 架构anchor、映射profile和小测试参数不同；尚无全workload／wrap映射 | 每次验证记录实际参数／flag／事件数量；后续量化占用、ID／generation quiescence和覆盖，不能从32K标签推断全通过 |
| A-SERVICE | R6 tracker、S2槽及metadata credit已有局部归还机制 | 在新场景记录实际重复使用；既有状态不重复计价，新增控制／buffer如有则登记；当前不宣称0增量 |

B1使用本表的存活／复用边界继续compact/P3/M2/R5合同工作，尤其区分page、stage、service、journal。B2使用原RD1＋WCG1的saved DDC诊断现有ready/setup与hold流程，不能将旧时序结果冒充未来生命周期successor的结果。成本账本从本阶段登记OPEN项，阶段C再汇总；本轮未产生新的面积／能量／延迟估计。

## 7. 本阶段完成标准与检查

本轮交付范围、生命周期对应、环境假设／保证、身份寿命、两个场景规范、精确缺口与后续成本责任。**只关闭阶段A的范围定义项**；READ-REUSE、ADMISSION-REUSE、数值对应、全workload覆盖、存储实现、2ns时序和完整净收益均保持OPEN。现有C4-D及RD1＋WCG1各自原验收不变。

提交前只做文档／JSON一致性、source hashes／行锚点、端口名、参数数值与local links检查及`git diff --check`；不将这些静态检查称为仿真／形式／行为等价证据。每个后续批次单独记录验证、更新live文档、检查diff并提交；长任务按既定独立tmux流程通知用户等待。

本轮静态检查通过：16份输入hash／bytes、44个源码行锚点、98个证据引用、26处环境端口名称、anchor参数对应、4个本地文档链接、3个live入口；18行生命周期与7类环境职责经独立只读复核。行为场景运行数为0，精确检查收据保存在配套JSON。
