# 注册窗口关闭合同验证：64条journal的条件与剩余缺口

日期：2026-11-09。源码基线：`research/kvzap-latest` / `f9f8adf`。
判定：**候选版本合同的有限模型通过；当前生产者/RTL尚不能保证该合同，不能据此集成64条滚动历史。**
输入hash、源码锚点、完整模型结果和反例见 [JSON](route_a_registration_window_contract_validation_20261109.json)。
本轮新增 [独立Python合同检查器](../tools/check_route_a_registration_window_contract.py)和文档，更新live入口；不修改RTL、通用wrapper/v1或规范合同，不启动native仿真、远程任务或DC/STA。

## 1. 这次实际验证了什么

[前一轮寿命审计](route_a_multigroup_journal_lifecycle_closure_20261109.md)提出“注册窗口关闭”可避免保留全部旧历史。本轮分开检查三件事：

| 问题 | 本轮结论 |
|---|---|
| 现有生产者是否已经保证旧组不再产生合法registration？ | **没有此交付/关闭保证。** MR-1B要求在accepted pending maturity创建registration，但允许迟到提交；生产top直接接外部registration，仓库没有实现带freeze/seal的location/descriptor生产者 |
| 明确增加版本化freeze、disposition、seal与owner接管后，64条是否可能安全周转？ | **条件成立时可以。** 有限模型检查及单窗口容量归纳支持该组织；不需要等待旧packed page被读取或旧lease完成 |
| 能否立即按此修改生产RTL？ | **不能。** token的真实成员归属证明、未计划attention的Closed失败路径、unbound direct来源以及正常owner回收接口尚未闭合；它们不是已有端口的别名 |

因此结果既不是“注册关窗不可能”，也不是“现有实现已保证64条足够”。旧精确历史方案仍是兼容性参照；本轮没有证明288MiB归档是必需的，也没有证明可以无条件删除它。

## 2. 生产者何时才真正拥有最后使用保证

必须区分**创建、送达、最后一次合法提交、实际服务完成**。MR-1B约束创建时点，不提供后三者的同拍或有限延迟保证。

候选production successor `registration_window_v3_candidate` 采用以下顺序，默认不影响v1：

1. **Open：** DUT/明确的group owner分配`{session namespace32, group sequence32}`。每组不超过64条；token必须绑定该组真实pending-maturity/member事实，而不是只由请求方填写。允许registration先于R3 admission，但必须有相应真实maturity归属证据。
2. **CreationFreeze：** 生产者已知道该组完整成员集合，全部对应maturity已发生，确认每个成员的descriptor创建决策已结束，不再为该token生成新的descriptor/registration。这里不能把“当前队列为空”当作未来创建权已结束。
3. **Disposition：** 全部真实R6 pending→packed完成后，尚未使用的pending descriptor已不适合开启新的pending服务。未offer的记录可在生产者内部明确退休；**已拉高valid的offer必须被接受，或经版本化拒绝/取消握手消费并收到精确ACK**，不能直接撤valid。已接受的registration转入DUT的query/owner责任，不因生产者退休而消失。
4. **ProducerSealAck：** freeze已成立，所有旧offer及其disposition/ACK完成，生产者确认没有合法旧registration待提交，也没有隐藏重试队列或延迟生成路径。ACK携带精确token；生产者以后对该token只能形成协议错误/显式Closed请求，不能重新取得合法注册权。零direct-registration的组也必须有明确seal事实。
5. **DutClose：** DUT另行确认§3的query/withdrawal/lease接管或排空，以及原post-R6/R5-ready/notice责任。然后收齐R3、ingress两侧close ACK，下一phase才Open G1。

namespace必须由明确的session初始化/隔离握手建立，不能在每次reset后恒置0并假设外部旧offer已消失；重用前须完成旧provider/服务quiescence，wrap必须fail-closed或采用已证明的隔离机制。本轮namespace分类不证明真实32-bit wrap或reset隔离。

**生产者能保证“以后不会再有合法提交”的时点是第4步，DUT能安全清journal的时点是第5步。** 这两个时点都不是现有publication或membership handoff的自动含义。若生产者或下游永远不ACK，只能停在原组并施加背压，不能超时清记录、隐式reset、重试或改mask。

全组R6完成是这里退休尚未提交pending注册的安全依据：真实authority已经变为packed，不应再开启一个新pending读取。它不授予runtime转权权限，也不使已经发出的pending read失效。后续合法packed page访问继续由R5和原R6/S2路径完成。

### 2.1 token必须与真实成员绑定，不能成为新的漏洞

反例：G0已关闭；调用方把G0旧binding换上G1的token；G1 journal查不到该旧binding，于是返回Unseen；若owner据此重新开放pending资格，旧事实就绕过了关闭frontier。

因此，namespace/sequence检查之后，还必须有**不可被请求方自行重标的member/pending ownership检查**。当前组已接受的ingress maturity/binding记录可以作为候选证据来源：它早于R3 relay，保存完整binding，可能支持“R3 admission前注册”。但目前没有这样的查询/证明端口，更没有已验收的读口、时序或成本方案；不能把这个候选说成现成保证。

候选分类顺序为：旧namespace→StaleNamespace；已关闭token→Closed；错误窗口→WrongWindow；token正确但没有真实归属→NotOwned；只有归属合格后，才允许原精确Unseen/PendingMember/TransitionedPacked分类。两个opaque64仍按原合同提供和比较，不能由token或坐标推导。

这与v1“精确不匹配可以是Unseen”有明确差别，所以必须是独立版本；不改变通用wrapper/v1的原查询。

## 3. 在途责任怎样排空或移交

| 在途对象/切点 | 允许清journal前的条件 | 清journal后仍由谁负责 |
|---|---|---|
| registration已接受、lookup尚未fire | 先完成lookup并形成精确结果；本轮保守合同还要求owner接受结果。不能只看到`lookup.valid=0`就清空 | descriptor owner保留完整registration与最终资格 |
| lookup result被背压 | 299bit完整result快照稳定，最终交给owner；不得在原行复用后重新读取或重算 | R3 response holding→原owner；旧token不能误接G1 |
| snapshot为Unseen/Pending，随后真实转权，最后才收到result | 已捕获的`revoked/TransitionedPacked`必须单调，迟到result不得把它清零 | descriptor owner的sticky否定事实；当前v1相关赋值已具有此性质 |
| 已注册、尚未形成association | 精确withdrawal或TransitionedPacked查询已使owner永久禁止新issue；关闭后的新association查询必须能显式拒绝 | 版本化Closed路径；有accepted attention时必须交R6处理，不能永久ready-low |
| association已形成、候选未issue | 原binding在真实R6 `.fire`时产生Valid-only withdrawal；接收owner已保存精确association和withdrawal责任 | materializer继续原cancel→ACK→abort→ACK→R6 failure；journal清空不撤销这些责任 |
| 已缓存positive eligibility，但尚未joint fire | 转权后不能依赖旧缓存放行；commit边沿重新检查authority，转权同拍优先 | 原R2/descriptor owner；不修改R2排序或cursor规则 |
| joint R2/R1/external/lease已经fire | 精确handle、storage generation、identity和服务状态已由独立owner持有 | **继续已有读取，pin到匹配typed terminal。** 不可因关窗取消已发出请求或提前释放payload |
| R1 terminal后，四consumer/source release尚未结束 | journal已可独立释放，但服务记录和endpoint/source责任继续存在 | consumer/source owner；lease终止与source release是两个事件 |
| R1 fault或取消未完成 | 保持旧context或明确fault quarantine；不能伪造source release或成功terminal | 原fault/cleanup owner；正常再注册能力另需验证 |

R3 withdrawal是原R6 fire的无背压镜像。候选`OwnerCustodyAck`只是确认接收方已有独立稳定副本/责任，**不在R3→R6链上新增ready，不创造第二个authority owner**。

### 3.1 journal释放不等于owner slot释放

K先保持现有**一个direct descriptor/service context**，不以关窗增加pending并发。旧context可能来自G0，journal已经用于G1；旧lease/取消/consumer责任未结束时，这个slot不得被新registration覆盖。

因此无需把“读完旧页”或“旧lease完全结束”作为下一组admission的前提。若新pending服务需要已占用的K=1 slot，它仍要按有限资源背压；不能把这项容量约束藏到无限外部队列中。若以后增加K，每个context的字段、端口和费用必须分别计入。

现有`PendingDescriptorOwner.registered/leaseLive`没有正常完成归零输入，materializer正常issue后也没有从`AwaitIssue`接收成功完成并回Idle的通路。当前单记录MR-1B验收不因此失效，但它不能当作上述重复服务回收已经实现。fault后模型允许context留在quarantine；**没有把整个fault服务排空列为通过**。

## 4. 不能遗漏的attention/declaration关闭切点

当前binder允许先持有source declaration，随后才查询descriptor owner；owner在TransitionedPacked后会阻止association query，而查询接口没有负响应。packed-v2控制器位于binder的`completion_plan_out`之后，pending-only计划走legacy分支，不能自动覆盖“association尚未形成”的关闭拒绝。

| 关闭时刻 | 必需处置 | 当前实现/模型边界 |
|---|---|---|
| 只有registration/declaration，尚无accepted attention | 精确local reject/ACK，清对应未接受工作；**不制造attention terminal** | 新版本协议要求 |
| R6已接受attention，pending plan仍未接受 | 终止该preplan并由R6发且仅发一次fault；不得凭空source release或靠ready-low排空 | R6 v2存在preplan拒绝基础，但此pending关联失败的发现/路由未闭合 |
| R6已接受完整plan，direct候选尚未issue | 原cancel/abort/ACK后走R6 failure | 复用已验收的单记录路径，另需验证关窗交错 |
| lease已经issue | 继续已有读与匹配terminal；保留source消费责任 | 不能改成pre-issue取消或重新publication |

关闭frontier和token必须也能覆盖declaration/association查询，不能只扩registration接口；冻结的`SourceCompletionPlan`不必因此增加descriptor字段。新token/provenance carrier、负响应及R6错误路由仍需明确设计和验证，不能擅自重开R6 authority或source selection。

## 5. 能否覆盖所有合法direct-pending来源

**这是目前完整production合同尚未闭合的主要原因之一。** MR-1B明确：R3 pack-member ledger不是所有合法direct-pending的目录，Unseen可以是尚未进入packing的合法来源。不能把“没有当前组归属”一律当成错误而仍声称保留了原功能。

完整候选必须为这些来源提供独立的、真实pending owner的live/未packed证明和有限生命周期；或明确版本化收窄论文执行范围。前者的目录、端口、状态与服务费用未实现/计价，后者是scope变更，本轮不默认采用。也不能让旧v1旁路接受任意未命中的Unseen，从而绕过关闭检查。

故本轮证明的是**满足当前窗口真实归属条件的packing-bound子合同可有界化**，并指出一般direct来源需要什么保证；没有证明所有合法direct来源都已经满足它。实际location/descriptor producer是外部职责，仅依据当前repo不能验证其隐藏队列/未来提交行为。

## 6. 64条容量论证与成本边界

条件归纳：初始journal为空；只写当前open组的唯一ordinal，范围0..n−1且`n≤64`；旧组在所有条件满足前不clear，也不Open G1；双close ACK后才允许新组写；旧token此后显式Closed，不再访问被清行；旧服务依赖的事实已移入有界K个owner。因此**journal工作/待查询历史最大64行**，不随累计组数增长。

该结论有明确范围：

- §2的创建/交付关闭、§2.1的归属验证、§3—4的后果接管、§5的来源覆盖均需成立。外部不响应只能阻塞，不能破坏容量上界；没有给出无界公平性/吞吐保证。
- 同时存在64条当前组记录和最多K=1条旧组服务context时，系统仍保存旧服务信息。**“journal64行”不等于全系统只保留64份descriptor，更不等于外部服务零成本。**
- 现有journal本体仍为18,112bit＝2,264B。独立owner原registration为297bit，新增token等字段另计；K增加也另计。两张compact表、R5 read-ready和P3/M2/R5存储均未因此缩减。
- 若production producer采用最多64份完整registration的队列，原字段载荷为`64×297=19,008bit=2,376B`；再计valid64和共享token64，得到**2,392B**的一个独立队列候选。它可能与既需保留的descriptor目录复用，但没有现成实现/端口证据；不含ACK holding、计数、控制、运输和payload lease存储。
- 前一轮292bit只是已列holding字段小计。此次新增归属验证、declaration token/拒绝路径和producer寿命责任后，**292bit不能作为完整新增成本估计**。本轮不提供mapped area或经济可行性结论。
- 若这些条件最终不能满足，精确历史迁移仍是保持旧查询合同的参照；不允许以本轮有限模型删除历史或排除unbound来源。

## 7. 实际检查与反例

执行：`python3 tools/check_route_a_registration_window_contract.py --output-json <receipt.json>`；`--help`可用，无第三方依赖，正常模式要求assertions开启。精确执行结果嵌入配套JSON，检查器hash与源码hash一起冻结。

| 检查 | 规模/结果 | 能证明的范围 |
|---|---|---|
| 窗口交错 | 1/2/3成员×0/1个direct registration，共6个有限图 | 创建/offer/disposition/seal、延迟query/result、sticky revoke和双close ACK |
| 独立lease/cancel custody | 270状态、599转移 | 从已接受association开始，成功消费分支限一条source-ending record；并非全部preplan/data/fault或多record/source_last=false continuation |
| 64份producer关闭排空 | 194状态、383转移的计数模型 | creation已freeze、全部已packed后，未offer退休与held offer/拒绝ACK守恒；不模拟64份payload/key |
| 正确组织合计 | **1,693状态、4,070转移；0 invariant violation** | 每个有限状态都存在到该组件目标的ACK完成路径；不是无界/公平RTL liveness |
| 不安全策略 | **7个自动穷举反例＋3个定向反例** | 下述错误组织可被区分，检查器不是仅仅重放一条成功路径 |
| 分类与边沿 | 72个namespace/window/归属/state分类；4个plan切点；4个same-cycle issue条件 | 抽象字段等价/身份类别；不是完整bit级RTL验证 |
| full64工作区 | 198事件定向轨迹 | 无attention的G0关闭并Open G1；不声称穷举全部64成员并发 |

自动反例：假seal但仍有未处置记录；accepted lookup还要读journal就clear；只等一边ACK就Open G1；迟到Pending/Unseen结果覆盖已撤销资格；转权时取消已issued lease；缓存positive eligibility覆盖commit-edge检查；清journal同时复用live owner。

定向反例：closed旧token被当Unseen；旧binding换当前token而无归属验证；只有registration而无accepted attention却制造fault terminal。

有限图覆盖了：两种close ACK顺序、seal后仍pending的lookup、R6后迟到registration、Unseen/Pending快照晚于转权送达、held offer精确拒绝，以及**G1在cancel ACK、R1 terminal或source release之前Open**。lease fault分支保留quarantine，不冒充所有fault cleanup已实现。

这些是带接口前提的组合式合同模型，不是合并后的whole-DUT状态图。真实生产者、字段归属、每个ACK和跨组件同拍关系仍需后续实现提供对应证据。
尤其没有把`valid_count=1`推导为`source_last=true`：consumer/source-release的正向模型只选择该合法子情形，其他literal值/连续记录需独立覆盖，生产合同不改该字段。

## 8. 下一步最小合同收口点

进入生产RTL前，先明确并审阅以下接口/证据，不再把“注册关窗”当作一个Bool：

1. production pending/location producer的freeze→disposition→seal参考状态机及有限queue；精确界定一条descriptor的创建、送达与后续attention关联，不能由未来selection再次创造旧pending registration。
2. ActiveWindow真实member/maturity归属查询，以及unbound direct来源的独立证明与容量；明确哪部分能复用ingress/既有目录、增加什么读口与延迟。
3. declaration/association的Closed负响应，accepted-unplanned attention的R6 fault握手，以及与原plan接受同拍互斥；local reject不得发明terminal。
4. K=1 context的custody与正常recycle ACK：真实cancel/abort、R1 terminal、consumer/source release之间的独立寿命；不得清`registered/leaseLive`替代完成。新hold/ACK加入retire排空，namespace wrap必须fail-closed或明确quiescence。

本轮完成的是**版本合同的条件验证与缺口定位**。它支持继续收口上述有限合同；不支持现在宣称完整production可安全滚动64条、不支持实现接受、2ns闭合或净收益。通用wrapper/v1、R3 sole publication、R6 authority和R2 arbitration均保持原状。

本批检查：20份输入hash/bytes、30份生产源码hash、22个源码锚点、模型两份新鲜收据逐字节一致、Python优化模式正确拒绝运行、3个本地链接与3个live入口通过。生产硬件/既有tests与`f9f8adf`无diff；提交前完成普通及staged `git diff --check`。以上静态检查不增加native功能或物理证据。
