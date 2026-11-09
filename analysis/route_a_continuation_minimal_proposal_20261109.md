# 阶段 A：重复读取与多组 admission 的最小补齐方案 — 2026-11-09

**状态：方案与有界模型检查完成；生产 RTL、接口合同及任何综合输入均未修改。**
本方案接续[两个已验收的阻断诊断](route_a_stage_a_probe_result_20261109.md)，不是新的架构冻结，也不宣布持续 decode 已闭合。基线为 `research/kvzap-latest` / `dbb85b0`；[JSON](route_a_continuation_minimal_proposal_20261109.json)登记输入 hash、字段成本、模型收据和未关闭门槛。当前仍属于阶段 A；存储、关键时序与增量账本在这里作为功能方案的准入条件。

最小方向是：**页的持久读取资格由 R5 保存；R3 的当前组 journal 在精确历史归档后复用。** 两项均通过显式 production-v2 successor 实施，保留通用 wrapper/v1 的原容量、并发、握手和 late lookup 行为。不能仅把 binder 的 valid 保留、或把 ingress Done 改回 Collect。

## 1. 需要保持的事实与约束

| 已定位事实 | 最小方案必须满足的要求 |
|---|---|
| 首次服务后 session Active、底层页仍可读、S2 Empty；缺失的是 binder 消费掉的一次性事实 | 不重新 publication、不复制 payload、不用旧 lease；从真正的持久 owner 恢复资格，每次创建新的 S2 服务实例 |
| R5 `descriptorReadable` 在 visibility ACK 即设置，早于最后一个 R3→R6 handoff | 不能直接把现有 readable 当作完整 post-R6 读取许可 |
| SourceCompletionPlan 没有 PageRef、layer/head；当前 top 也没有供 runtime 获得真实已发布 PageRef 的通知 | 增加显式查询选择与通知，且 runtime hint 不构成 authority；不能假设现有端口已携带这些事实 |
| M2 head/span 在 handoff 后释放，不能承担持久页目录 | 不以已释放的 M2 状态恢复读资格；R5 保持唯一 page/location/liveness owner |
| 入口 Done；64-slot journal 保留到 reset；late lookup 精确比较原始 binding | rearm 之前处理 journal 的跨组寿命；清旧记录不能把 TransitionedPacked 变回 Unseen |
| 单次 attention terminal、S2 release、最终 page retire 是不同事件 | 释放瞬态服务不释放页；新状态必须加入最终 drain/reclaim 条件 |

保持原始 mask、hot128、maturity、page64、R2 全局仲裁、R3 sole publication、R6 authority、原 2ns 公平约束。PM1 关闭、RD2 排除，保留 RD1＋WCG1 已验收基线。两张 compact 表、P3/M2 容量和两个 opaque 64-bit 字段均不在本方案中削减。

## 2. 重复读取：持久事实归属和查询

### 2.1 一次性校验与持久资格分开

增加一个**独立于 attention 的组 receipt collector**，校验原 R3 member stream 的顺序、layer/head、tag、entry 坐标与最终 count，并 join 原 post-R6 page-ready。head 由实际 member/组上下文得到，不能伪称旧 page-ready 已含 head。R3 仍是唯一 publication 发起者，R6 仍逐成员接受 authority；collector 只见证这些真实 fire，不能制造它们。

collector 完成后向 R5 安装 `read_ready(PageRef, owner, tag, count)`。R5 核对 allocated、page generation 和 canonical descriptor；只有全部 R6 handoff 完成，才能置位。原 P3 stage generation 用于组 receipt/close 的精确关联，不另存成每页字段；这一省略需在 successor 中证明 PageRef generation、owner/tag/count 及 live 检查足以排除旧组。不能重构一份假的旧 stage observation 送回 legacy binder。

| 持久事实 | owner／候选位置 | 生命周期 |
|---|---|---|
| allocated、page generation、post-R6 read_ready | R5 availability child，由现有 9 bit/page 增为 10 bit/page | allocation/reset/reclaim 清 ready；匹配的完整 receipt 才置位；attention 完成不清 |
| owner、valid_count、page generation、next PageRef、payload/sidecar 派生位置 | 原 R5 descriptor/backing | 原 publication／最终 invalidation 生命周期 |
| transaction group tag | **descriptor v2** `[59:52]`；仍为 128-bit record，`[127:60]`保留为零 | allocation/new-page 时写入，tail/link 更新保留，free 清理 |
| layer/head/tag、member 顺序、stage generation | collector／当前组 close 状态 | 仅到精确 receipt 安装、归档及双方 reuse ACK；不为每次读保留 member stream |
| 每次读取 identity、selector、lease、source generation | attention context／activation／S2 | 每次服务单独分配、释放；与 page generation 分离 |

v1 descriptor 的 `[127:52]` 必须为零，因此以上格式只能作为显式 v2。增加 tag 不增加名义 descriptor bytes，但会激活原来的零位，并影响读写逻辑；不是免费修改。R5 的既有 visibility/readable 机制保持，不用新位替代其 publication 含义。

### 2.2 runtime 选择页，但不授予权限

候选新增端口/内部消息如下，位宽为当前 production profile 下的字段数，不是门面积：

| 消息 | 字段 | bits |
|---|---|---:|
| `packed_page_available_out_v2` | PageRef26、owner(layer6/head3)、count7、tag8 | 50 |
| `packed_page_select_in_v2` | attention identity5、PageRef26 | 31 |
| `R3GroupReceiptV2` | 原 page-ready55＋owner head3 | 58 |
| `R5ReadQueryV2` | identity5、PageRef26、实际 attention owner9 | 40 |
| `R5ReadResultV2` | 原 grant174＋owner9＋tag8＋status2 | 193 |

runtime 从真实 available 通知保存 page hint，按当前外供 source-set 合同选择 PageRef。DUT 必须与**实际接受的 attention layer/head**匹配，而不是信任 runtime 重复声明。候选为四个 attention tracker 对应的有界 context/selector 表：每项 identity5＋owner9＋PageRef26＋两个 valid＝42 bit，共168 bit；不新增无界 CAM。

R5 query 返回 canonical count/tag/handles，不能沿用“调用者先知道 expected_count 才能查询”的循环依赖。status 为 `OK / NOT_READY / INVALID / FAULT`。只有 allocated、generation、owner、read_ready 都匹配才返回 OK。runtime notice/selector 必须有 ready/valid 稳定与唯一匹配规则；notice 阻塞可以产生有界背压，但不允许要求先完成一次 attention 才消费下一组 publication。

### 2.3 每次服务与错误收束

正常路径：新 attention → 匹配 PageRef selector → **注册化** R5 query/response → 新 S2 lease → 原真实 packed fill/sidecar/四消费者/terminal → S2 release。第二次可读同一 PageRef、相同 page generation，复用的 S2 slot 必须推进 source generation。已有页不会再次执行 admission、payload write 或 publication。

当前 activation binder 只有 rejected observation，R5 非法请求也可能一直不 ready；不能把它们直接接成 v2，否则已接受 attention 会永久占住 tracker。最小候选采用 **source-plan preflight**：在 SourcePlanBinder 的 completion-plan 尚未 fire 时读取稳定 declaration，完成 R5 检查和 S2 lease；成功后才与 R6 accept 做 joint fire，再 fork 所有 source。必须保留该 fire 与 `accepted_pending_association_out` 的耦合。

取得 lease **之前**，先由R6核验live未装plan的attention及其真实owner，完成所有selector/R5错误判断。S2必须提供自己核验的 `BUSY / INVALID / GRANTED` 结果：现有ready低把busy、非法slot/source-kind、错误next-generation混在一起，不能照搬为无限等待。BUSY可在不锁住R5查询口的条件下背压；INVALID走故障。R5的NOT_READY也仅在存在精确receipt安装在途时允许等待；不允许占住唯一端口阻止该安装。四entry context表必须是R6-owned或由真实accepted-attention只读复制，不能凭上游declaration构造。

原S2 lease接口要求已经接受的R6 plan，因此这里需要显式**v2 pre-plan reservation**，先取得R6对live attention和稳定候选plan的授权，不能偷用原端口。只预留瞬态slot，不构成page publication或source authority变更。成功preflight保存identity-bound descriptor grant和**同一份**S2 lease，joint fire后交给activation使用；原binder不得再次query/lease。lease之后原则上只等待不可撤销的joint accept，retire须允许已有票据继续。若仍需取消，必须有真实S2 abort/return确认，不能直接清tracker。

失败时用新增的 exact-identity pre-plan reject/cancel 事件，held直到SourcePlanBinder与R6双方确认；清除held declaration/association缓存，R6对真实存在、尚未接受plan的attention发**恰一次fault terminal**，outward terminal接受后才释放tracker。foreign identity仅拒绝declaration，不能制造一个不存在的attention或terminal。不冒用现有仅针对pending的failure，不提前发pending association，不制造lease/release或消费者commit。它需要版本化接口和排空证明；若实现中已经让hot/pending source开始，则还必须真实取消/排空，不能仅清tracker。此时应拒收该实现为“最小preflight方案”。mixed-source合法正例与失败例必须回归，不能靠只支持packed-only缩小原合法行为。

## 3. 多组 admission：工作 journal 与持久历史

### 3.1 选择保留精确 late lookup，不直接清除历史

保留当前 **64-entry × 281-bit** working binding journal 和 present/transitioned 位；当前组内的 withdrawal、transition 与 late lookup 仍从它取得全部原始字段。新增由 **R3 ReconciliationHistoryOwner** 管理的归档后端。归档存储只是保存权威 journal 事实，不自行决定 pending/packed authority，也不是将现有单 entry PendingDescriptorOwner 当成完整历史表。

选择 `(history namespace, entry_id)` 定位归档，继续精确比较完整原始 reconciliation key。单 session 每个 entry 只 arrival/maturity 一次来自本研究固定生命周期合同，不推广到通用 wrapper。group tag/ordinal 可在不同组复用，不能作为唯一历史地址。

原 `reconciliationMatches` 比较214 bit；binding 另外67 bit M2 mapping provenance不参与该查询。候选归档 word：**完整214-bit key＋state2＋namespace epoch32＋reserved-zero8＝256 bit（32 B）**。保留两个独立64-bit字段和原 transaction identity，不从坐标推断或压缩它们；也不必为这个32 B格式引入坐标重构。withdrawal 所需完整281-bit binding仍在 working journal 内，用完后才归档；归档不能被用来重建已省略的 M2 字段。

### 3.2 正常周转顺序

1. ingress 收集、claim、prepare、relay G0，原 publication 与逐成员 R6 handoff 完整执行；Done 改为等待精确 reuse permit，而不是立即回 Collect。
2. **全部 R6 handoff 和 collector 校验完成后**，并行推进 R5 read_ready 安装和 journal archive。归档流复用已不再用于本组 withdrawal 的 journal read mux；不把 archive ACK 串到 R3→R6 每成员 authority 链上。
3. 每条 archive write 有精确 ACK；整组还有 commit ACK。archive 尚未 commit 时，旧组 late lookup 仍从 working journal回答。
4. R5-ready ACK、archive group-commit ACK、publication sink 的对应状态已安全接收/持有后，产生 `GroupReusePermit`。key＝PageRef26＋layer6＋head3＋tag8＋stage generation8＋count7＝58 bit。
5. permit 向 ingress 和 R3 分别 held-until-ACK；R3 清本组 working present/control，ingress 清本组 present、valid、claim/relay 等控制。**控制器收齐两侧精确close ACK后，才单独rearm/open，允许ingress回Collect及下一组R3 claim/admission。** 两个ACK不能被假设同拍，迟到G0 clear不能清掉G1。metadata bridge原credit返回仍按原真实事件执行，不新增一份“伪credit”。
6. G1 可从 ordinal0 开始。G0 lookup改查 archive，G1 查 working；不存在把旧记录临时回答成 Unseen 的窗口。**不要求先读取 G0**，必须支持先完成 G0/G1 admission、随后才 attention。

缺 ACK、archive fault 或容量不足：保留 working、停止下一组、上报故障；不覆盖、不自动 retry、不隐式 reset/fallback。R5 可在 archive 未完成但 working 历史仍完整时服务旧页；group reuse 必须等两项 ACK。与 late lookup 的竞争需注册化局部仲裁和真实进展证明，不能增加未计价组合读口。

### 3.3 历史寿命、reset 与 retire

archive 保留至 destructive reset，包含已 TransitionedPacked 的旧组，保持原 late lookup 的否定 pending-eligibility 语义。最终 retire 停止新组，但必须允许已接收的 receipt/archive/query 完成；新状态加入 R6 drain、R5 `reclaimLocalSafe`，所有 accepted attention/lease 消失前不得回收其页。当前 R5 lookup 的 `!drain_collection_enable` 不能照搬到已接受但尚未完成的读票据，否则 retire 可能卡住这批在途工作。

reset 不清 HBM。必须有独立 `HistoryInitAck`：选择 fresh logical region，或明确初始化/scrub，使旧 namespace 不再有效，之后才允许 R6 session start。32-bit epoch 只是候选字段，不能凭 session_id=0 或假设 HBM 初值为零保证隔离；epoch wrap 必须有 region/quiescence/scrub 合同。初始化容量、流量和延迟同样计价。新 session reopen 仍按原 R6 合同需要 destructive reset，本方案不增加产品级多 session 能力。

## 4. 存储、端口与新增成本的可行性

### 4.1 确定的字段数与候选 provision

| 项目 | 确定数值／候选 provision | 尚未证明的部分 |
|---|---:|---|
| R5 read_ready | 146,880 bit＝**18,360 B**；availability 从165,240 B变183,600 B | 宏/银行/更新冲突、映射面积、动态功耗 |
| descriptor v2 tag | 激活1,175,040 bit＝146,880 B信息；总 descriptor名义仍2,350,080 B | 全部 new-page/link/invalidate writer和backing适配，不能认为零成本 |
| 既有 working journal | 64×281＋128＝18,112 bit，不是新增 | 原 lookup/withdrawal mux保留，新增归档复用控制 |
| 直接寻址归档，32K×36×8槽 | 9,437,184×32＝**301,989,888 B＝288 MiB**／namespace | 一种简单候选布局，**不是必要下界、不是每请求实测用量、不是片上SRAM面积** |
| keep-all cold最大记录数据量 | (32768−128)×36×8×32＝300,810,240 B＝286.875 MiB | 实际冻结mask admission计数应更少；本轮不伪造 workload占用 |
| runtime page hint，如8 B/页 | 最多1,175,040 B | 能否复用现有runtime目录、实际存储/访问成本 OPEN；不是新DUT authority |

归档区在原5 GiB cold payload与2.35 MB descriptor区**之外**，Full-KV没有这份等价 journal历史，不能作为共同成本抵消。288 MiB对应最直接、可核算的精确历史实现；稀疏目录/日志可能降低容量，但需要额外索引、端口和查询延迟，未在本轮选定。只将若干组总记录限制在64条并跨组追加可用于小 witness，不能代替32K范围的合同闭合。

新增明确 holding fields 的初步清单为：四entry context/selector168、collector26、receipt59、reuse permit61、双close ACK/phase3、query41、response194、runtime notice51、archive control136、RMW line512、preflight failure8，合计**1,259 bit**；若独立增加registration hold另计297 bit。这只是已枚举字段小计，**不是完整寄存器上界或映射面积**。S2 status/abort与其holding、双边cancel ACK、局部FSM/仲裁/drain、运输队列、宏外围与外部controller尚未收全；部分可复用旧holding，后续必须避免重复计价。18,360 B也只表示名义存储位，若展开为DFF，其面积可能显著；本方案尚不能保证低成本。

### 4.2 端口、访问延迟与 R2 边界

| 状态/服务 | 最小候选访问组织 | 冲突与未关闭门槛 |
|---|---|---|
| R5 availability | 复用 registered keyed lookup，新增 ready install | alloc/reclaim 更新为无ready的Valid，不能丢失；ready置位需 generation检查，clear优先；不能直接声称单1RW宏可容纳全部并发 |
| R5 descriptor | 复用现有单 outstanding lookup，与 append/reclaim串行 | held response＋局部公平仲裁；v2读结果新增latency须进入模型；不能增加父级大Vec目录 |
| working journal | 全R6完成后复用 withdrawal 读mux归档；late lookup保留 | 不新建281-bit×64多路组合归档读口；证明并发late lookup与归档均能前进 |
| archive | 一次一个64-B line RMW，精确 row/group ACK；一个512-bit line buffer | 32-B row无现成write mask；要保护邻居row，不能整行覆盖另一组记录；读返回/fault必须关联原query |

当前 `entry_id = position×288＋layer×8＋head`。直接布局下，同stream相邻position的32-B记录相隔**9,216 B**，不能假设8条天然合成一个256-B HBM beat。无write mask时，每条row先读64 B、再写64 B，即128 B core数据负载；若分别按原declared256-B transfer口径计价，是**512 B/record代理**，不是实测HBM请求数。64-member组名义archive2 KiB，但该代理为32 KiB额外一次性数据流量；一次old late query另计64 B core／256 B declared代理。cold keep-all记录数量包络、每row恰一次RMW时，分别是1,203,240,960 B core数据负载与4,812,963,840 B declared代理；均未计请求/ACK、group commit、初始化和额外查询，**不是全部流量上界**。不能只按32 B/record估访问成本。

原 R2 descriptor-maintenance 合同是 **one-fragment write**，不是history read类别。候选后端的 raw-line read 可参考现有R5外部backing接口，但必须由一个**显式计价、共享真实memory资源**的服务承接；不添加免费HBM端口。durable archive write可在本组原new-page/tail-link完成后、下一组获准前，经原maintenance write通路串行化；需版本化本地operation及ACK路由，并证明与append/reclaim互斥。不能借当前RTL的class/kind检查缺口把read塞入maintenance。若物理映射必须改变R2全局仲裁/新增read类别，超出本方案，须先停止并单独评审。

这使multi-group方案仍有实际可行性门槛：**精确历史的物理服务、容量和带宽不是现成的**。288 MiB不是算法的信息下界，也不证明整个方案一定不合算；它证明保留现有任意晚到精确查询合同有真实成本，不能在阶段A略过。后续若能证明某个owner确认后绝不再发生旧registration，可研究显式版本化的历史退休合同；目前没有这项证明，不能把它当成等价删状态。本方案不建议未经存储/服务合同核算就实现288-MiB直接布局。

## 5. 2ns 时序与有限 namespace 的准入条件

本轮只检查组织，不运行 STA。现有未闭合的 arbiter→sidecar READY、stage valid→registry ready、reclaim链仍存在，不会因增加功能自动改善。

- collector、R5 query/result、permit、archive ACK均使用held registered边界；不把HBM返回、archive complete或runtime notice ready组合串进R3 publication/R6 authority或现有顶层READY长链。增加的周期必须计入服务延迟，不能宣传保持原每次服务cycle数。
- source-plan preflight不能破坏稳定payload和joint-fire条件，不能新增从S2 lease ready经R5查询回到R2 arbiter的组合环；失败与retire均需exactly-one terminal/drain证明。
- 新read_ready进入现有R5 child，不能将146,880-entry compare或异步读展开回父控制。native门控clock、setup/hold检查仍沿原2ns流程；不新增false/multicycle例外来通过。
- RID3＋incarnation2、candidate ID4、group tag8、stage/source/page generation8、ordinal7均有限。32K可能产生远多于32个操作，archive RMW还会增加事务。必须逐项证明quiescence/wrap或显式有界stop；本模型两组不提供全horizon结论。
- 若额外外部服务延迟使admission无法在maturity节奏内drain，或oldquery饿死，方案不予功能/性能验收，即使协议安全没有违反。

## 6. 仍须单列的功能依赖

当前 PendingDescriptorOwner 是一个 `registered` 记录/reset，`leaseLive`也没有普通完成后的重用入口。它不是可直接复用的历史数据库，也不足以证明完整持续 pending/direct 服务。后续必须定义其**普通association完成、注销、下一次登记**以及immutable admission identity与新attention identity的关系。此项是既有后端的额外生命周期缺口，不以重新审查MR-1/MR-2或改变R2/R3/R6规则处理。

因此，两处补齐可形成“多组packing后重复packed服务”的最小原型，但不能单独支持“全部hot/pending/packed持续decode后端已完整”的论文主张。Q→实际K/V/position→partial/R4的数值对应、完整容量/并发、P3/M2/R5物理存储、完整增量账本也仍独立OPEN。

## 7. 已做的有限方案检查

本地[纯Python模型](../tools/check_route_a_continuation_plan_model.py)不加载ML/RTL/EDA。两组、每组两条，覆盖ordered R6/collector、组后archive write/ACK/commit、R5 ready、permit、独立R3/ingress close ACK、rearm和attention交错：**224 states、499 transitions，0 mismatch、0有限模型deadlock、9 goal states**。六项覆盖包括第二组在没有任何attention时接收、两组完成归档/清理、G1 ready后仍可读G0、两页各读两次及两种close ACK先后顺序。

四个坏组织都给出反例：handoff后直接清working使旧lookup变Unseen；visibility即ready早于all-R6；只留最新页使G0丢失；仅ingress close ACK就rearm使G1早于R3 close。候选32-B格式另通过8,192精确正例、106,496单字段篡改负例、各8,192个namespace/state/reserved拒绝、2,496次边界pack/unpack及32个越界拒绝。它们支持协议方案的初步一致性；不证明RTL等价、真实R5/S2/preflight错误/cancel、ready/valid实现、全32K、reset/retire/wrap、外部公平性、2ns、面积或净收益。

## 8. 后续实施与验收顺序（本轮不实施）

1. **先补重复读取**：版本化receipt、R5 v2资格/查询、runtime notice/selector、preflight错误路径；保留单组journal。先跑局部真实owner与whole-DUT功能测试，不立即完整DC。
2. **再补跨组**：在archive初始化/存取/commit、物理服务与成本合同明确后，接入ReusePermit和rearm。只放开Done而不解决历史不接受；64-total-history的小测试不能冒充full范围方案。
3. 正向：原v1 first-use不变；v2同页两读；G0/G1都先admit再读G0；同bank full64组后合法下一组；跨layer/head；真实packed write/read、sidecar、四consumer、两次terminal、新S2generation以及最终一次retire。
4. 负向/交错：错owner/PageRef generation、未all-R6、同ordinal旧组late lookup、任一64-bit字段/原identity不匹配、ACK缺失/fault及双close-ACK偏斜、邻row RMW、reset旧history、attention/query/lease/archive中的retire、mixed-source失败取消、所有有限ID wrap边界。特别检查lease已GRANTED但joint fire被背压时保持稳定、同identity accept与reject互斥。不能通过force权限、重publication、重preload或reset分段通过。
5. 按实际冻结workload回填archive记录数/读写/初始化、runtime目录、R5与external服务成本；确认完整functional successor和输入覆盖后，才考虑新的paired DC/STA。报告原2ns setup、hold、clock-gating与新增延迟，另保留历史控制映射结果。

结论：持久读取资格有一个小且明确的状态扩展候选；多组journal有合同保持的组织候选，但外部历史成本和服务还未闭合。当前可以进入**有边界的接口/功能实施准备**，不能越过这些门槛宣称完整持续执行或硬件净收益。本轮不修改生产RTL、不启动远程任务/完整DC、不放宽任何约束。

本批检查：19份输入hash/bytes、15个源码锚点、24份生产文件与`dbb85b0`逐字节相同、原probe的140份源码仍匹配；34项算术/接口检查、3个本地链接和3个live入口通过。新鲜有限模型收据与JSON一致；读取/preflight、journal屏障、成本/R2边界经三项独立只读复核。提交前执行`git diff --check`及staged检查；这些检查不增加RTL功能或映射证据。
