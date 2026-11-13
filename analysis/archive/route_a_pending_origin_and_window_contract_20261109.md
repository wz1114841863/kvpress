# Pending来源、成员归属与组窗口关闭：production v3合同细化

日期：2026-11-09；源码基线`research/kvzap-latest` / `a7a92df`。
状态：**身份、正向归属验证和关闭条件在候选合同层明确，并通过本地参考检查；生产者/RTL实现及完整成本未验收。**
输入hash、源码锚点、原生模型收据见 [JSON](route_a_pending_origin_and_window_contract_20261109.json)。检查器为 check_route_a_pending_origin_contract.py（旧文件 `check_route_a_pending_origin_contract.py` 可在 Git 历史查阅）。本轮不改RTL、通用wrapper/v1、原算法或architecture规范，不运行native仿真、远程任务或DC/STA。

## 1. 本轮推进了什么

[前轮关窗验证](route_a_registration_window_contract_validation_20261109.md)停在“当前token必须有真实归属，合法unbound来源不能误杀”。本轮选择的合同组织为：

- **成员路径：** registration声明属于W时，查由真实accepted ingress形成的成员关联，并校验独立pending数据/descriptor事实。
- **对象路径：** registration没有当前组归属时，查pending location/descriptor owner的**正向live/pending证明**。不以“R3没查到”作为pending资格，也不要求它属于当前组。
- **组窗口关闭：** 仅关闭W的成员及相关注册/查询责任；其他pending数据、descriptor和服务实例保持有效。旧W数据已packed后，对象路径也必须拒绝新的pending issue。

这解决合同定义中的循环：既不把R3当成所有pending的目录，也不让unbound旁路通过Unseen复活旧packed数据。它是显式production successor候选，**不是v1精确查询的无条件等价改写**；旧方案、旧模型和旧验收原样保留。

## 2. “未入组pending”确实是必要路径

算法参考`RouteAPackedAttentionState`先把matured retained数据放入各head pending FIFO，每次append再按跨head最旧位置服务至多`admission_budget`条。attention按`hot→pending→packed`读取。external backend明确禁止把一次prefill拆成逐token append以多花admission预算。

因此预算512是**每次服务量，不是pending容量，也不是512条descriptor全局上界**。metadata local32/shared256/staging512同样是另一类资源，不能当作payload/descriptor容量。

本轮从原源码规则构造一个纯标量反例：8 heads、1024-token prefill、hot128、synthetic keep-all；maturity产生`896×8=7,168`条，budget512每head服务64条，仍有**832/head、总6,656条pending**。这是合法容量包络的合成示例，不是冻结predictor mask、实际workload占用或新GPU实验。它足以排除“pending全局只需64条”与“attention前全部额外drain掉”的未经证明假设；本轮不改变预算或原mask。

### 2.1 三种不同边界

| 类别 | 身份/权利来自哪里 | R3 journal未命中的含义 |
|---|---|---|
| 已被production ingress收下、尚未relay到R3 | 原R6 Hot→Pending、context/binding原子接收及ingress成员记录 | 只说明尚未进入R3；可以是当前组的合法pending成员 |
| 已mature/仍pending，但尚未关联当前packing组，或属于其他组 | 真正pending/location owner的现存对象与descriptor，以及原生命周期事件 | 不能据此否定；走独立对象证明，之后可按原调度进入未来组 |
| 已完成真实R6 Pending→Packed的旧对象 | 真实转权事实；后续page读由R5负责 | 不能新开pending读取；不能把absence当成Unseen恢复资格 |

当前production top的Hot→Pending输出实际与ingress context/binding接收相连，所以第一类有具体可观测位置。第二类在算法、架构与MR-1B合同中合法，但当前top没有独立、已验收的birth/location服务输入；registration本身不能充当该证明。新的外部owner服务必须补齐，不能声称当前RTL已经覆盖了这类身份验证。

## 3. 四种身份及字段来源

| 身份 | 候选逻辑键 | 保证/不能替代的内容 |
|---|---|---|
| 数据对象E | `{session namespace32, entry_id24}`＝56bit | 固定32K、每entry一次arrival/maturity范围内标识一个KV对象；不是payload地址，不据此推导两个opaque64 |
| descriptor D | `{session namespace32, PendingDescriptorKey(ref18, generation8)}`＝58bit | 由descriptor/location owner创建，显式映射到E；保留其`pending_ordinal/source_last/valid_count`原值 |
| packing成员M | `{GroupUID(namespace32, sequence32), ordinal7}`，另有immutable group count/header | 只有真实accepted ingress才能形成E→M关联；调用方填写token不能创建成员 |
| attention服务S | `{attention identity5, selected Pending SourceInstance34, D58, endpoint generation8}`＝105bit | 与已选plan精确配对；SourceInstance不是E或payload地址；三种generation分别保留，不相互替代 |

在v1里，registration的`transaction_identity`既参与binding精确比较，又用于attention关联。本候选明确保留**原binding的creation/reconciliation identity**，另设服务attention identity。不能为第二次attention改写原binding，也不能强令未来attention复用maturity时的identity。这是版本化侧带/owner合同差异，不修改v1 bundle或冻结的`SourceCompletionPlan`。

E的稳定性使用既有一次maturity合同：R6软件reference检查arrival唯一、stream position单调、maturity只能从Hot发生一次。RTL lifecycle adapter没有重复保存完整token authority表；本轮不偷偷增加该表，也不声称硬件已能检测任意重放。若未来要求硬件自行验证非法重复maturity，检测状态与成本要另计。

### 3.1 正向证明的来源

候选逻辑服务称为`PendingOriginOwnerV3`。它只是**原pending/location职责的实现合同与生命周期事实副本**，不选择mask、source、admission或authority：

1. **Birth观察：** 从原accepted Hot→Pending事实/原权威owner状态，加上同一对象的immutable location/descriptor builder事实，建立E与D。registration/lookup不能自行创建记录。仅frontend maturity valid、请求方自称live、R3 Unseen均不够。
2. **Member观察：** 从原accepted ingress三元事实建立E→W/ordinal关联，逐字段核对entry/coords、payload_ref、handle、storage generation、endpoint及原creation identity；tag/count和M2 provenance按原group合同保留。候选可以利用ingress已有binding存储，但新增lookup/read口不是现成的。
3. **Packed观察：** 原R6实际接受的Pending→Packed立即撤销E的新pending-issue资格。观察不得依赖“当前R3 journal是否有descriptor binding”：未绑定descriptor也不能漏掉真实转权。entry_id用于定位已验证E，不能当作payload key或生成地址。
4. **服务关联：** 请求的attention identity、SourceInstance、descriptor key必须与真实selected declaration三者一致，再读取D→E的原始事实。不能只校验一对identity而忽略plan实际选择的是另一个D。

这些都是有明确来源的观察/查询，不新增authority grant。原R3 sole publication、R6转权及R2 issue顺序不改；物理adapter和backing尚未实现。

## 4. 两条查询路径与失败分类

`MemberQuery(W, ordinal, D, data facts, S)`需要：正确namespace、W未关闭、真实E→W/ordinal/count关联、D→E精确映射、immutable facts一致，以及E当前仍Pending。

`ObjectQuery(D, data facts, S)`不要求W：同样校验D/E/S与正向Pending证明。它可以指向未入组、其他组、甚至当前组的对象；**它不是绕过转权检查的Unseen旁路**。

| 情况 | 候选结果 | 后果 |
|---|---|---|
| 对象/descriptor存在、事实与selected plan一致、E为Pending | PendingVerified | 只建立服务/eligibility证据；真实lease仍在原joint issue边沿重检 |
| D不存在或已回收 | NotLiveDescriptor | 明确拒绝；不返回“未见过所以可能pending” |
| 任一opaque64、坐标、storage generation或descriptor事实不一致 | NotOwned | 不创造/修复映射，不成为Unseen |
| MemberQuery的W关闭、错窗口或成员关系不符 | Closed/WrongWindow/NotMember | 不能换个新token复活旧E |
| ObjectQuery的E已经Packed/不再Pending | NotPending | 即使去掉group token，仍不能新开pending读取 |
| attention/SourceInstance/D未与selected plan配对 | BadServicePair | 不把另一个合法对象的数据冒充本次选择 |

v1仍按原exact reconciliation返回Unseen/PendingMember/TransitionedPacked；上述结果仅属于新production合同。没有accepted attention的拒绝只产生local disposition；已有unplanned attention要走R6一次fault；已接受plan则沿原cancel/abort/failure；已issued lease继续完成。此错误路由仍需实现验证，不自动fallback、重试或另选packed。

## 5. 生命周期与释放条件

| 状态/对象 | 必须保留什么 | 何时能释放 |
|---|---|---|
| Pending E，尚未入当前组 | live location、D→E及literal descriptor事实 | **不能因G0关闭或一次attention完成而释放**；后续attention仍可能读取它 |
| E已关联W，但尚未R3 admission/publication | 同上＋真实成员关联 | 持续到真实转权和本组最后使用；R3 absence不缩短寿命 |
| E已真实转为Packed | 立即禁止新pending issue；保留未交接的query/transition责任 | 所有引用排空或由有界owner持有完整副本/不可逆否定事实，且backing状态更新可见后，pending目录可删除该E/D；packed page仍由R5保留 |
| 已有lease或取消中的S | exact location/generation/association、response pin与consumer责任 | 原真实typed terminal、cancel/abort ACK和source completion分别结束其责任；关窗不能覆盖context或提前释放payload |
| 背压中的查询reply | 完整D/E事实快照、query ticket与独立sticky revocation | reply `.fire`并转交责任后释放；**revocation不能改写held valid payload** |
| D/key generation或namespace复用 | 已有offer、query、declaration、lease与旧响应的隔离 | 旧引用真实排空/精确独立接管且无alias才可复用；wrap fail-closed或明确quiescence |

真实转权后的旧pending目录可以不留永久墓碑，因为新版本对不存在/不live的对象明确拒绝。这与v1对任意迟到exact lookup保留原分类的合同不同；它不允许假称通用v1等价，也不需要继续保存已经packed且无引用的对象全部214-bit历史。
组关闭本身不授权D/key复用：旧Object offers、declaration与服务引用仍须满足该key的quiescence。目录/free-key pool和生产者队列必须有显式有限provision；容量不足时背压，不把迟到旧引用变成不计费、无限增长的保留表。

### 5.1 慢backing、迟到reply与unknown-target查询

不能假设外部owner/backing与R6同拍更新。候选必须立即捕获当前成员的转权，给已解析query/context置独立sticky revoke；backing更新ACK前不得丢掉这份局部保护。

Q先采用一个有界directory lookup/response holding。若lookup已接受但D→E尚未知，关闭切点先停止接收新的此类lookup，并完成旧lookup的目标解析；不能因为它没有W就假定与G0无关。目标已知后：

- 若E属于G0，结果/服务要么完成，要么由独立holding/context接管完整snapshot和不可逆revoke，保证不再读旧journal。
- 若E不属于G0，允许继续持有reply或运行服务，不清除其live资格，也不要求整个pending目录为空。
- 一个转权前产生的positive snapshot可能晚到；接收方需要owner状态/独立sticky标记来禁止新issue。保持reply payload稳定，不能在背压时直接改status。真实实现需明确这种侧状态与ticket的移交、寿命和同拍优先级。

所有当前成员的backing NotPending更新已ACK、相关unknown-target旧query已解析/交接之后，才允许清本组局部保护。新lookup则从已更新的目录取得明确NotPending/NotLive。Q/K均是有限非零资源，绝不把旧记录移入无限软件队列。

## 6. 收口后的组关闭条件

设`Members(W)`为真实ingress记录确定的至多64个E。`CloseSafe(W)`必须满足：

1. 该集合与group header冻结，原R3 publication、逐成员R6转权、post-R6/R5-ready/notice责任完成或已稳定接管。
2. pending/location producer给出**仅针对W的ProjectionSeal**：不再增添W成员；W的Member registration offers及ACK全部处置/接管。不能全局冻结不属于W的Pending E/D。
3. `Members(W)`全为NotPending；局部capture完整，其backing更新可见；任意新ObjectQuery也不可能重新取得这些E的PendingVerified。
4. 已接收unknown-target lookup完成解析；W成员的query/result/withdrawal/lease后果都已排空或有界独立接管，held payload稳定；旧服务可以尚未读完。
5. 旧W关闭分类与namespace隔离成立；R3、ingress两侧精确close ACK收齐后，另一个phase才Open G1。旧页继续可重复读取；**不以先attention G0为条件**。

因此W关闭后仍可存在合法的unbound pending B、B的registration或已issued服务；B随后可以按原admission顺序进入G1，而不重建其数据对象或改写descriptor。这里冻结的是组成员/组注册权，不是所有数据对象的未来attention服务。

关闭也不等于假设线路上永远没有旧消息：迟到ObjectQuery可以正常收到NotPending/NotLive拒绝。必须保证的是旧E不再取得**成功的新pending资格**，同时所有迟到消息仍有精确的握手、负响应和有界存放位置。ProjectionSeal据此细化前轮候选，不能被解释成全局清空所有pending生产者。

本轮只把该关闭谓词的身份、事件来源和责任范围定义明确。当前RTL仍缺positive owner服务、版本化negative response、ProjectionSeal/custody和正常context recycle接口；单记录MR-1B及重复页读r2的既有验收均保持原范围。

## 7. 容量与成本：64约束的是journal，不是pending总量

只允许一个W写其unique ordinal、双close后再Open，且旧请求只能正向查live目录/显式拒绝，支持journal最大64条的条件归纳。旧组历史不随已完成组数累加。

但live目录要覆盖**全部合法Pending E和live descriptor D**，不是只有64个组成员。数据已Packed且所有引用交接后删除，避免把历史换个名字永久存起来。H/D的最大live、访问端口与更新带宽仍要按workload/物理容量另行闭合；不能拿预算512、metadata credit或K=1服务并发替代它们。

可核算的独立未合并字段候选：

- data row：namespace32＋entry24＋layer6/head3/position15＋payload_ref64＋handle64＋storagegen8＋endpoint3＋creation identity5＝**224bit/E**。
- descriptor row：D58＋E56＋pending ordinal15＋source_last1＋valid_count7＝**137bit/D**。保持所有literal事实，不从group count或位置推导last。
- 64-slot成员索引：`64×(E56＋valid1)＋W64 = 3,712bit = 464B`；可研究复用ingress，而不是宣称免费。
- raw字段量为`224H＋137D＋3712 bit`，另加state/ref/ACK、Q holding、K context、adapter、bank/ports与payload pin费用。仅计目录行、不含464B索引时，H=D=64的字段为2,888B；合成例H=D=6,656时为300,352B；若H=D取cold keep-all上界9,400,320，则为424,189,440B。**这都是候选未合并载荷，不是实际新增量、必需下界或mapped面积。**

例如在“一E一D、合并公共identity字段”的明确条件下，目录字段可以组织为273bit/对象-描述符对；这只是表示候选，不能套用到多D映射同E或忽略端口复制。目录究竟复用哪些原存储、H/D实际有多大，仍是B1必须计价的问题。

真实实现可能复用原pending-HBM location/descriptor记录、M2/ingress存储并避免字段重复，也可能因端口/更新要求更贵。本轮不选择宏，不把目录当零成本，更不把464B当作该方案总成本。它也没有缩小两张compact表。

## 8. 本轮检查结果与边界

本地纯Python参考检查：**4类正向身份场景、22类身份/字段篡改负例**；creation identity与新attention identity独立、SourceInstance不等于entry、pending ordinal不等于position、`source_last=false` literal均保留。另查旧W请求、旧E去掉W/重标G1、目录回收后的明确拒绝，以及B在G0关闭后仍有效并随后进入G1。

有限图检查 **1,009状态、2,697转移，0 invariant violation**，每个有限状态都存在到G1 open且B入G1的ACK完成路径。覆盖：G0关闭时B的context/held reply保留，A的已issued lease继续，A旧positive reply与sticky revoke并存，directory更新ACK前局部保护有效。4个错误策略各找到反例：信旧positive、忽略unknown-target、全局撤销B、背压时改reply payload。

这不是whole-DUT或硬件等价证明；coherent目录、真实producer与Q/K握手仍是候选假设。source/consumer真实drain被抽象成精确ACK，不声称覆盖多record/source_last=false continuation、全部fault/retire/reset/wrap或2ns。软件算法与R6 reference只提供语义/来源证据，没有冒充RTL事件时序。

下一步的实施前门槛已具体化：实现级producer/owner服务与ProjectionSeal/查询/负响应/custody接口；H/D最大live与真实backing/端口；pending preplan fault及正常context recycle；随后才局部真实owner与whole-DUT验证。当前可据此继续接口准备，不能登记为生产功能、面积或净收益验收。

本批静态检查通过：22份输入hash/bytes、30份生产源码hash、20个源码锚点、3个本地链接、3个live入口及两份一致的新鲜模型收据；Python优化模式正确拒绝运行。RTL、算法、既有tests与前轮模型均与`a7a92df`无diff。提交前完成普通/staged `git diff --check`；这些检查不增加native功能或映射证据。
