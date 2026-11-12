# 同 session 多组 admission：journal 生命周期、容量与最小补齐方案

日期：2026-11-09。源码基线：`research/kvzap-latest` / `1f752ee`。
状态：**源码寿命审计与方案完成；跨组功能、物理服务和成本可行性尚未验收。**
生命周期和容量分析保留在本文；后续功能证据与适用范围见[H2](hardware_reports/02_rtl_implementation_and_sustained_execution_scope.md)。
本轮只新增本记录并更新 live 入口，不修改 RTL、规范合同或旧记录，不启动仿真、远程任务、DC/STA。

## 1. 本轮结论与方案地位

1. **保留当前 wrapper/v1 的迟到查询合同，旧 journal 历史只能在 destructive reset 时失效。** publication、全部 R6 handoff、S2 release、page reclaim 乃至 session retire ACK，都没有撤销 late lookup 的合同。工作区可以迁移，历史事实不能直接丢弃；单记录top的特殊最后使用条件见§2。
2. 保留精确 late lookup 时，最小功能组织仍是“**64 条工作 journal＋精确历史后端＋双边 close ACK 后 rearm**”。旧 281-bit binding 用完后，历史查询只需要原 214-bit 精确 key；这允许迁移时舍弃额外 67 bit，而不能删除两个 opaque64 字段。
3. 此组织让工作区的最大 live 保持 64 条，但**历史最大 live 随累计 admission 增长**。固定 32K 位置空间、hot128、36 层、8 KV heads、每 entry 一次 maturity 的 keep-all 上界为 **9,400,320 条**。不是“只剩最后一组64条”。
4. 此前 32 B 直接寻址候选需 provision **288 MiB/namespace**；cold keep-all 有效行载荷为 **286.875 MiB**。它是可核算候选，不是必要下界、实际 workload 用量或片上面积。**不能把这份历史视为已经实现或经济可行。**
5. 若要把历史也限制为64条，必须另行建立版本化的“**注册窗口关闭＋在途工作排空/事实移交**”合同。当前源码没有该保证，不能把它作为等价优化直接实施。本轮明确这一备选的释放条件与验证门槛，不据此修改默认接口。

本记录细化 [原最小方案 §3—4](route_a_continuation_minimal_proposal_20261109.md)，不废弃其精确历史方案或既有有限模型，也不把新的关闭窗口备选说成已获批。持久页重复读取的 [r2验收](route_a_persistent_page_read_r2_result_20261109.md)保持原范围；阶段 A 总体仍 OPEN。

## 2. 谁在使用 journal，最后一次使用发生在哪里

| 消费者/状态 | 必须保存的内容 | 最后使用与释放条件 |
|---|---|---|
| R3 逐成员 R6 transition / withdrawal | 原 281-bit `PendingPayloadReadBinding` | 对应真实 `authority_transition_out.fire` 产生精确 withdrawal；整组全部完成后，不能再有旧 ordinal 的 withdrawal 引用 |
| R3 late reconciliation | 214-bit精确key＋present/transitioned事实 | 旧合同允许任意迟到的精确查询；没有现成的组级最后一次查询事件，因此一直保留到reset，或迁入等价历史后端 |
| 已接受、尚被背压的 lookup result | registration 297 bit＋state2＝299 bit | result 必须保持至 `.fire`；不能在清工作区时改写。当前 result 是完整快照，不是 journal 行指针；后端 successor 必须维持此性质 |
| PendingDescriptorOwner | 自己保存的 registration、reconciliation结果和 withdrawal 后的永久不可读事实 | 当前每reset只接收一条registration、发一次lookup；收到匹配转权后永久撤销本条 direct eligibility，但**没有正常回收再注册接口** |
| R2 candidate / association / endpoint / lease | 已接收的精确 association 与局部服务状态 | 按原 cancel/ACK、abort/ACK、真实 R1 terminal、consumer/source release 排空；不能因journal清空或host声明“结束”而清除 |
| persistent-read collector / R5 | 完整成员流、post-R6 receipt、持久页read-ready与descriptor事实 | collector 发完 page notice 才重新Collect；页读取事实由R5保留到合法retire/reclaim，不依赖保留旧journal |
| metadata bridge / ingress | 组关联、credit、收集/relay状态 | metadata credit已有真实handoff归还；ingress `StateDone` 没有rearm。credit归还不等于history失效 |

精确 key＝identity5＋entry24＋layer6＋head3＋position15＋payload_ref64＋tag8＋ordinal7＋count7＋handle64＋sourcegen8＋endpoint3＝**214 bit**。额外67 bit是M2 mapping ref64＋owner3；它不参与 `reconciliationMatches`，但在281-bit原始binding使用完之前不能擅自丢弃。

生产 top 中 journal 的唯一查询消费者确实是 PendingDescriptorOwner；这不等于旧历史可自动删除：

- 如果它已注册并完成唯一一次查询，后续该实例没有第二次lookup。这只是当前单记录实现的事实。
- 如果它尚未注册，首次合法registration仍可能指向任何旧组。不能从“目前没有请求”推导“将来不会再请求”。
- top 的registration直接连到该owner，ready与R3 lookup也没有session-retired门控。故即使不能再发attention，retire ACK仍不能替代旧查询合同的关闭事件。
- `registered`、`leaseLive` 只有reset初始化，没有普通完成后的归零通路。direct source release接R6，未接回descriptor owner。不能利用“一次/reset”的限制宣称已经支持持续pending服务，也不能为归档而强制每组注册一条本来不存在的direct descriptor。

一个需要保留的特殊情况是：若范围严格限定为当前单registration的top，且唯一query/result及全部原binding/withdrawal使用确已结束，随后确实没有第二个合法查询消费者。可以另行证明该狭窄范围的历史已无用途。但它既不满足通用wrapper的可继续查询合同，也不能处理owner尚未注册的packed-only流或后续重复descriptor服务。本方案不以这个当前功能限制缩减历史容量。

源码及 [MR-1B B2c合同](mr1b_direct_pending_cross_owner_contract_proposal.md)支持以上事实；本轮没有重新验收MR-1/2，也没有将静态路径分析称为新功能测试。

## 3. 安全释放：迁移与删除是两件事

| 事件 | 可以结束什么 | 不能据此删除什么 |
|---|---|---|
| materializer读完 / payload durable | 对应搬运工作 | 待publication/R6使用的member/binding、late查询历史 |
| 唯一publication / 部分R6 handoff | 已完成的本地阶段 | 未转权成员、完整组历史 |
| 全R6 handoff＋withdrawal已消费 | 281-bit原始binding的这一使用阶段 | 214-bit精确历史；尚未接受的result/notice |
| R5 read-ready安装与notice接收 | 持久读取事实已移交R5/runtime | late reconciliation历史 |
| 每行归档ACK＋整组commit＋读写一致性成立 | **允许工作journal迁移/复用** | session内的历史记录；旧query仍应命中归档 |
| 单次attention完成 / S2 release | 当次source service和槽位 | packed page和journal历史 |
| 最终retire / descriptor invalidate / reclaim | 页权限与物理页 | 当前v1的精确查询历史 |
| destructive reset＋新namespace初始化合格 | 旧会话事实可失效、历史物理区可重用 | 未初始化的外部旧数据不能当作空历史 |

两个直接反例：G0已转packed后清journal，迟到精确lookup从`TransitionedPacked`变成`Unseen`，而owner把Unseen视为仍可按真实pending规则服务的来源；G1重新使用ordinal0覆盖G0，则旧G0的lookup/withdrawal可能读到G1。不能以“G0已经读过一次”修复这两个问题。

### 3.1 保留现语义的工作区复用屏障

`ReuseSafe(G)` 必须同时满足：

1. 本组publication成立，全部真实R6 transition和原binding使用完成；无fault被当作success。
2. collector验证整组成员/receipt，R5-ready成功；page notice已接收，或被独立稳定holding接管。初版可保守等notice `.fire`，不等待任何attention读取。
3. 本组全部精确历史行写入ACK，整组commit成功；旧lookup在迁移前后没有“暂时Unseen”的窗口。
4. 已接受lookup的结果已完成或完整快照持有，后端query与commit的观察顺序已定义；不能只检查`!lookup.valid`。
5. permit key精确匹配PageRef、layer/head、tag、stage generation和count；R3、ingress分别清自己已结束的控制并给出close ACK。**两ACK收齐后另一个edge/phase才允许open下一组**，防止迟到G0 clear擦掉G1。

这只是新增的组间reuse控制；原admission三路atomic join、publication、R6 authority以及metadata credit的真实事件不改。ready/valid背压时payload保持，不能让archive/lookup直接成为原publication或R6 transition的附加前提。

## 4. 最大同时存活量：分别计算工作区、历史和在途副本

| 范围 | 最大live/占用 | 前提与限制 |
|---|---:|---|
| 当前已实现 journal | 1组、最多64条，总量也是64条/reset | 入口不rearm，不代表完整32K持续执行 |
| 精确历史 successor 的工作区 | 1组、最多64条 | G1首成员在G0双close ACK之后才能接收；不引入双工作bank或预取G1队列 |
| 精确历史 successor 的历史 | 累计已提交admission数，cold keep-all最多9,400,320条 | 固定位置0..32767、hot128、36×8、每entry一次；不包含滚动超32K或重复maturity的新合同 |
| archive提交中的副本 | 同一组最多64条可同时在工作区和归档中 | 这是相同逻辑记录的物理重复副本，不是额外64条新admission；预算不能忽略复制阶段 |
| 已接受result | 当前最多1份299-bit快照＋1bit pending | 扩展lookup队列/多个descriptor owner必须另计；R6的4-entry attention tracker不等于4个descriptor owner |
| 有界关闭窗口备选 | 工作/待查询历史合计最多64条 | 仅在§6新合同成立、旧查询显式关闭且不提前接收G1时成立；当前不是事实 |

计算：`(32768−128)×36×8 = 9,400,320`。全部满64成员页需要146,880页，恰为当前allocator容量。任意小tail组会更早耗尽页；不能同时承诺任意singleton分组、无限新组与不增加page容量。146,880是此容量下不回收页时的完成组数上界，不能用9,400,320条记录声称可同时容纳这么多单成员页。

history是累计量，不是当前pending量或page live量。若保持旧late查询语义，页已退休也不自动缩短history寿命。实际冻结mask会降低接收记录数；本轮没有重放workload，因此不填造实际占用或平均查询频率。

## 5. 存储和服务成本：原有、增量与未覆盖项

| 项目 | 名义成本 | 归属/状态 |
|---|---:|---|
| 现有工作journal | `64×281＋2×64 = 18,112 bit = 2,264 B`，约2.21KiB | 已有；不重复记为新增 |
| 现有lookup result | 299 bit＋pending1 | 已有；registration本身297bit，不是214bit |
| 精确历史直接布局 | `32768×36×8×32 = 301,989,888 B = 288 MiB/namespace` | 新Route-A成本；一种布局，不是物理宏、下界或实测 |
| cold keep-all行数据 | `9,400,320×32 = 300,810,240 B = 286.875 MiB` | 最坏有效数据载荷；预留区仍288MiB |
| 仅两个opaque64原值载荷 | cold keep-all为143.4375MiB | 说明缩掉其余小字段仍不能轻易让精确历史变小；不是所有可复用外部表示的全系统下界 |
| archive独立holding候选 | 已识别字段小计652bit；若另存registration再加297bit | 仅字段清单，**不是全部新增寄存器上界或面积** |
| 注册窗口关闭备选 | 已识别字段小计292bit，另有未定owner/运输状态 | 条件方案；不包含现有journal、生产者buffer、完整drain/cancel、队列和物理外围，不是成本承诺 |

32 B历史格式沿用原提案：完整key214＋state2＋namespace32＋reserved8。全转权后state可研究常量化、entry坐标可研究从索引恢复，或改为稀疏日志/复用location-owner原存储；这些均需证明精确查询、重复/别名和新寿命，并计入索引/端口/延迟。不能把“没有片上复制”写成零增量。

652bit的独立archive控制字段为：namespace32、row index24、ordinal7、ACK计数7、phase3、group key58、双close ACK2、ready/notice/commit标记3、初始化/故障/忙标记3、RMW line512和valid1。字段可能复用；ACK关联、队列、独立response holding、互连及后端完整状态仍未收全。292bit备选字段见§6。

端口/流量仍是硬门槛：

- archive需要真实读、写、每行ACK、组commit和init服务；R2原maintenance类为write-only，不能冒充已有历史读端口。历史服务不得黑盒化R3父控制或自行grant authority。
- 相邻同head position在直接布局中相距`36×8×32 = 9,216 B`。不能默认8个32B行能合并一个256B动作。
- 若用既有无byte-mask的64B R1 line RMW，每归档行有64B读＋64B写＝128B core payload；沿用已声明256B/action的服务proxy为512B/record。64条组为8,192B core/32,768B proxy；cold keep-all分别1,203,240,960B/4,812,963,840B。这些是候选操作算术，**不是实测HBM流量**，也没有含查询、ACK、初始化和controller开销。
- 若fresh-region初始化需要全区scrub，单namespace又有288MiB写数据；若用epoch/fresh region替代，必须证明初值、隔离、地址范围和epoch wrap，不能假设reset清了HBM。
- 该区在原cold payload和R5 descriptor区之外，不属于Full-KV共同成本。R5 read-ready已有18,360B扩展、两张compact表366,336bit均另有归属；本轮不重复计价，也不声称journal方案解决compact面积问题。

## 6. 免长期历史的备选：需要明确改变哪个合同

可评估显式默认关闭的production successor：**每组有已确认的registration-close fence**。它不是当前v1的无条件等价替换，不能因“descriptor在maturity产生”就假设最后一次提交也在maturity。

最低合同要求：

1. 在admission/registration之前分配可观察的open-group token；既支持注册先于admission，也支持组内迟到注册。关闭前，pending/location producer确认本组所有需要提交的registration已接受或有真实取消ACK；允许“本组没有direct registration”，不能凭空生成SourceInstance/descriptor。
2. producer seal携带精确token，并确认没有尚未fire的旧valid offer。DUT还要检查已接受的query/result、withdrawal和association后果均被owner持有或排空。不能由runtime hint单方宣告历史不存在。
3. 已注册但稍后才服务的descriptor必须在自己的live状态中保留不可逆的packed/closed事实；尚在原R2/R1/endpoint链上的请求按原取消/完成路径结束。**清journal不等于清association或撤销已经发出的lease。**
4. close后的旧token首次registration/lookup必须得到显式Closed/Expired拒绝，绝不能落到Unseen。错误opaque字段同样不能借closed窗口恢复pending资格。这改变旧接口对迟到查询/不匹配的分类，需要独立版本和回归。
5. 只保留一个窗口；双close ACK后再open G1。单独的长期页查询仍走R5，G0可在G1完成后反复读取。普通未关联packing的合法direct source也要有明确合同，不能被强行塞入已关闭组。
6. tag8、stagegen8、identity5都不能当永久唯一group token。候选为session namespace32＋DUT分配的单调group sequence32，wrap前fail-closed；关闭frontier必须是已关闭连续前缀，不能越过尚未完成的洞。reset/namespace重用另有隔离合同。

在一窗口且每个异步事件带token的候选中，已识别新增字段：active token64、closed sequence32＋valid1、owner registration及R3 result两个holding各增token64、原组关联hold58、双close ACK2、phase3、seal/排空等标记4，共**292bit**。这只是清楚列出的字段；不包含为支持重复descriptor所需的回收控制、运输buffer、源owner的持有成本及新握手路径，不可据此宣称“只加36.5B就解决”。

当前尚无 producer seal、group token、Closed/Expired结果或descriptor正常再注册通路；scope文件也没有给出迟到registration的有限上界。**因此本轮只得到条件可行方案，未证明外部producer能满足它，未授权据此删历史。** 若选择这一方向，首先应冻结版本化协议并验证最后使用条件；不能先改RTL再补假设。

## 7. 最小补齐方案与下一批验收顺序

**语义保持基线：保留原64条工作区，精确历史迁移，完成双close后独立rearm。** 通用wrapper/v1保持原行为；新的production跨组路径显式版本化。原pending-before-admission、same-cycle admission/lookup、late-after-transition、精确不匹配的Unseen、held response和R6 precedence都必须保留。

实施前先过两个门槛：

- **合同选择门槛：** 若无法接受长期历史成本，先证明并明确批准§6的注册关闭合同；否则继续精确历史方案，不得静默采用“过期就是Unseen”或只存最新组。此前归档方案不因列出备选而自动废弃。
- **后端门槛：** 对精确历史方案补齐真实存取/ACK/commit/init、端口仲裁、容量和延迟/流量上界。尤其要定义lookup `.fire` 的观察切点：接受时Unseen的查询不能因稍后G1归档而被改判。可先用独立注册化局部仲裁使history读与commit有确定顺序，不增加原admission/R6组合链；服务公平性和新增组间背压必须计量。

门槛通过后，最小生产修改点才是：history owner/backing adapter、R3 journal查询路由/组结束、ingress等待permit与rearm、top的真实receipt/notice/双ACK连接及retire drain。单entry PendingDescriptorOwner若要反复注册，另加由真实cancel/abort/R1/consumer/source-release排空证明的回收确认；不能清`registered/leaseLive`冒充完成。

| 验证项 | 必须观察的结果 | 当前状态 |
|---|---|---|
| 默认v1 | 原容量、ready/valid、所有登记顺序/精确查询和publication/authority不变 | 既有结果保留；新successor未实施 |
| 两组基本witness | 无reset；G0满64后，G1从ordinal0开始；两组admission/publication/handoff独立，credit正确归还 | 计划，不是新PASS |
| admission不依赖读取 | 先完成G0/G1，再读G0；两页各可服务，最终一次retire | 计划；重复读r2单组证据不替代它 |
| 原组迟到查询 | G1期间/完成后查询G0，exact仍TransitionedPacked；任一原精确字段错则按选定版本返回，不aliasG1 | 计划 |
| 背压/交错 | response、notice、单边close ACK分别延迟；已接受query跨commit；不得丢/改reply或迟到清掉新组 | 计划 |
| 错误/容量/标识 | 写fault/缺ACK/commit失败不复用；同bank与跨bank；tag/stage/epoch边界、存储满；无隐式reset或retry | 计划 |
| retire切点 | Collect/partial R6/archive读写/held response/单ACK/已接收attention时retire，真实排空；fault不得伪装retire成功 | 计划；任意partial组切点尚未闭合 |
| repeated pending owner | 一条descriptor完成或取消后再接下一条；旧lease/association不可复活 | 单独OPEN，不能从两组packed-only推断完成 |
| 关闭窗口备选 | producer迟到/held-valid/错token/closed查询/未关联direct/namespace复用；先给出不安全提前关闭的反例 | 仅选§6后开展，未获等价结论 |

先做合同与局部真实owner验证，再做小参数whole-DUT；两组小测不替代全32K、全部并发和有限namespace复用证明。新功能合格后才另行评估综合；原2ns setup/hold/clock-gating与完整增量账本仍是独立门槛。

**当前建议：先验证注册最后使用/关闭合同是否成立，再决定能否避免长期历史；在没有该证明时，以精确历史迁移作为正确性基线，不急于实现288MiB后端或只改入口rearm。** 本轮关闭的是生命周期问题的归属、条件与成本边界，不是阶段A持续执行验收。

本批静态检查通过：18份输入hash/bytes、30份生产源码hash、15个源码锚点、15项字段/成本算术、7项文档数值、4个本地链接和3个live入口；9类后续验证均标为计划。生产RTL及既有tools/tests与源码基线无diff。提交前完成普通/staged `git diff --check`；这些检查不增加功能、形式、映射或时序证据。
