# H2：RTL实现与持续执行范围

整理日期：2026-11-12。本文承接[H1](01_architecture_and_software_hardware_boundaries.md)，
按目的、方案、结果和分析串起RTL1—RTL3、测量DUT及持续执行验证的推进过程。
结论来自已有实现记录和已验收结果；本轮没有修改RTL、重跑测试或启动综合。
“硬件R1—R6”指架构职责，不是算法阶段六份报告。

**目前已证明：在明确外部服务和有限测试参数下，真实控制owner能够完成packed页
首次使用；显式v2又证明了一次packing后同页两次服务、指定错误恢复和retire排空。
尚未证明：同session多组admission、持续pending服务、实际Q/K/V到attention结果的
完整数值对应，以及目标容量/并发下的持续decode。** 这些结论属于不同实现范围，不能
把各阶段的通过项拼成一个已经完成的后端。

## 1. 目的与推进顺序：从“模块会响应”到“真实工作能连续完成”

H1定义了谁负责传输、打包、页管理、消费与退休，但接口齐全不代表数据真正流动。
因此实现先建立局部控制，再激活数据和跨owner关联，最后检查能否在同一session中复用。

| 阶段 | 目的与方案 | 主要结果 | 仍需下一步解决 |
|---|---|---|---|
| RTL1 | 先实现身份、握手、publication、消费者完成与retire控制 | 局部owner和跨owner控制关联通过；R4保留可替换包边界 | 多个数据生产入口仍inactive，不能证明真实KV搬运 |
| RTL2 | 逐段激活admission、pack-read/write、typed delivery、S2与终结/回收 | 测试平台中同一实例完成一条retained事务链，并支持事件回放 | 部分关联和结果仍由验证入口/fixture供给，尚未成为完整生产连接 |
| RTL3 | 用明确owner与命名功能环境替代验证便利入口 | 接通packed首次使用；C4-D验收有界功能子系统 | 外部memory/partial/R4仍存在，未覆盖重复使用和多组周转 |
| MR-1/2与测量DUT | 保留真实父级控制，明确数组与外部服务边界，并建立Full-KV对照 | 形成Route-A测量实例；direct-pending单记录路径和逻辑存储边界有功能证据 | 不是物理宏或完整数值实现，也没有自动扩大持续服务范围 |
| 阶段A现状探针 | 不改RTL，分别尝试同页两读、同session两组admission | 首轮成功后，两项都定位到具体阻断 | 将“预期可以持续”转为需要独立补齐的功能 |
| 持久页v2 | 将长期页读取资格与一次性publication观察分开 | 15项native测试通过，重复读及指定错误/retire场景验收 | 多组admission、journal/pending生命周期及完整范围仍未闭合 |
| 多组与关窗合同探索 | 明确历史何时可删、哪些pending不属于当前组 | 找到旧合同义务，提出有条件的版本化关闭方案 | 当前生产者和RTL还不提供这些保证，没有新多组功能验收 |

表中的“完成”都带范围。模块级通过、测试平台组合通过、真实父级DUT通过、持续执行
通过是不同结论；各阶段大量复用模块和测试，也不能累加测试数当作独立覆盖量。

## 2. RTL1：先建立控制骨架，为何没有立即实现完整数据通路

**目的与方案。** 先确认请求不会认错、状态不会提前可见、资源不会提前释放，再逐步接入
payload。实现顺序覆盖R1事务/片段/初始化，R2仲裁与credit，R3/R5 publication，
S2/direct四消费者完成，R6 authority/terminal/全局drain，以及R4包与错误边界。

**结果。** 实现不只停留在空模块：后续跨owner步骤接通初始化/状态收集、逐成员转权、
source完成与R6终结关联，以及descriptor durable invalidation后再free的回收链。
RTL1-V补上局部断言、有限合法停顿场景和事件到Python参考的适配。跨owner连接依次
处理外部初始化与状态排空、admission/publication逐成员关联、source完成关联，以及
R5 descriptor失效后的reclaim；这些是控制组合结果，payload和数值计算仍由后续阶段补齐。

**分析。** 这些验证解决“控制是否守规则”，但当时P3 payload、S2填充、source plan和
partial等入口仍有inactive部分。R4会校验包并接受匹配结果，不代表它能计算softmax。
环境最终解除停顿的假设只支持进展检查，不是DUT延迟或吞吐保证。

## 3. RTL2与RTL3：数据流逐段接通，首次完整使用最终证明了什么

### RTL2：从分段正确走到同一实例的事务链

**目的与方案。** 将保留决定变成不可变的成员组，经过页分配、P3 claim、pending
pack-read、packed-write、descriptor durable和publication，再读取到S2并完成消费。
同时引入delivery context registry和typed router，让读片段与写终结返回各自真实owner。
早期一次仅处理一个最多64成员的admission组；group字段由生产者提供并保持一致，
不能将一次组关联或成员响应误当成最终publication。R3写完成与R5 descriptor durable
是不同事实，source packet/R4 stub只负责协议关联，不生成attention数值。

**结果。** 初次完成复核发现，若干事件只有schema，分段测试也还不是同一实例上的完整
事务。中间复核因缺少同一实例的真实owner链而不予通过；后续的同实例witness
覆盖R3到publication、S2四消费者到terminal、R5 durable reclaim到retire ACK，
并检查stale关联拒绝和terminal背压不改变状态。之后补齐实际握手事件捕获，串起：

```text
RETAIN → pending → pack-read → P3 → packed-write
  → descriptor durable → publication → packed authority
  → packed-read → S2 READY → 四消费者 → R4/R6 terminal
  → 外部retire请求 → descriptor失效 → page free → retire ACK
```

**分析。** 这是有价值的控制/数据流证据，但当时仍有验证专用的publication→S2关联、
结果stub和测试平台连接。RTL2的最终通过明确限定为testbench-only functional dataflow，
没有证明对应的全部生产连接已经实现。单次attention terminal也从未被定义成自动退休。

### 分阶段定向验证：已覆盖什么

RTL2并不是一次性完成：read descriptor、read ingress、R2双入口与共享allocation
先在隔离单元或harness中检查握手、背压、次序及错误拒绝；当时有些生产入口仍inactive。
R3 pack-read、direct-pending和packed-S2随后分别在功能harness中验证成功与stale、
identity/generation不匹配、错误fragment和terminal fault；这不是持续decode。

Source plan/packet和四消费者完成的定向测试覆盖七种非空来源组合、每个存在来源的
四个consumer、背压及错误身份拒绝。RTL2.3最终一次合并控制协议回归报告29项通过；
其中单独C9相关的4项pack-read、11项direct/packed及3项结构测试与回归有重叠，不能相加
当作独立覆盖。R4结果stub局部及R4→R6终结组合分别记录8项和14项通过，覆盖匹配成功、
stale、numeric fault及reset后的抑制；结果来自stub，不能证明实际attention数值实现。

退休路径的定向观察包括reset后的旧响应抑制和重新初始化、错误终结保持、缺失drain
时阻止retire、descriptor失效得到匹配成功后才能free，以及generation和重复事件拒绝。
这些是有限参数、有限停顿下的功能观察，不是任意环境进展、时序或PPA证明。

RTL3.4-A还记录了19项Python参考测试和25项Chisel定向测试通过，覆盖每consumer
结果关联、四个成功结果聚合、匹配的numeric fault、背压及reset/stale拒绝；这些结果
仍不等于真实Q/K/V到硬件attention结果的端到端数值验证。测试源码保留在
[Chisel测试目录](../../hardware/route_a/chisel/src/test/scala/kvpress/routea/)；被归并的
阶段摘要可在整理前Git版本`636c19b`查阅，原始实验目录没有清理。

### RTL3：替换验证入口，保持外部数值服务的明确边界

**目的与方案。** 给尚缺的工作指定真实生产者：packed activation精确连接R6计划、
R3成员/发布事实、R5 descriptor及S2 lease；sidecar通过typed read送达；R3根据真实
pending binding生成pack-read，随后走durable write、publication与逐成员R6转权。

同时建立功能memory、Python partial和R4参考，分别处理“内存保存什么”“给定Q/K/V
怎样得到partial”“partial怎样合并”。这些参考模型与Chisel中的协议检查分开。 功能memory
作为测试环境保存和返回事务数据，并观察request、fragment和write-commit事件；
早期packed-read组合仍显式依赖sidecar边界。RTL3.6阶段因没有同次live partial→R4→R6
闭合、完整sidecar与reset组合而保留no-PASS，后续见证逐步缩小缺口。

**结果。** 早期复核没有因为分段通过就宣告端到端完成，继续补上数据对象连续性、
sidecar、生产owner连接、完成顺序和drain。RTL3.7的testbench witness检查association
release后才能retire，以及stale response、fault、有限背压和reset；之后的cross-owner
复核仍因真实来源替换未完成而保留no-PASS。RTL3.8.5覆盖七种非空source组合及每来源
四消费者的协议路径；它使用命名外部包和测试观察器，不是七种完整数值attention测试。 对应的事件schema和coverage记录继续用于语义检查；
历史源码哈希回放只反映当时快照，不构成当前功能或数值正确性的证明。

RTL3.9 C0—C3b进一步让真实R3全部成员被R6接受后，才建立首次packed读；随后实际
payload/sidecar到达S2、四消费者完成、R6终结，最后完成retire/reclaim。C4-D于
2026-10-15验收这条**有界packed首次使用链**。其定向复核包含一个成功/事件回放测试
和三个stale/mismatch、numeric fault、reset负例；这是该次检查数量，不是全部历史测试总数。

**分析。** 这里的“numeric fault”证明错误能够正确终结，“四消费者commit”证明协议
消费与释放顺序正确；它们不等于实际QK/softmax/AV数学结果已经被验证。功能memory、
partial provider和R4 reference仍是外部环境，完整LLM推理也没有接入该验收。

更细的推进顺序是：先让packed activation关联真实R6计划、R3成员与R5/S2事实，
再替换sidecar验证注入，接着限定P3/direct ingress及partial provider边界，最后接入
外部R4参考。各阶段曾分别记录15、7、7、7项定向或结构检查通过；阶段间会重复运行
测试，不能累加成独立样本。后续pending binding、packed-write和descriptor durable
逐项接通；B2的匹配descriptor terminal和B3的publication→visibility ACK→R6转权
各有1项同实例定向通过，均限功能测试。原子publication顺序和错误拒绝是已检查的协议
事实，外部memory和数值provider仍须按实际方案计价与验证。

## 4. 从功能组合到测量DUT：哪些父级控制真正保留了下来

**目的与方案。** 为比较Full-KV与Route-A，进一步明确可测量DUT，而不是拿早期
composition-only顶层或验证harness直接当完整实现。`RouteAMeasurementDut`保留
R3/M2/P3、R5、R6、R2/R1、S2等真实控制；MR-2只将P3/S2/M2/R5的逻辑数组内部隔离。

**结果。** 2026-10-25测量边界记录了Full-KV定向5/5、Route-A父级4/4，以及所选
跨阶段10 suites/40项检查。Route-A父级覆盖packed、hot、stale packed响应和发出前
direct withdrawal/fault。MR-1B另已验收单记录direct-pending的descriptor关联、joint
issue lease、转权前取消/abort、R6错误终结和已issue后的合法完成。

**分析。** 这些证据支持“实际父控制参与功能路径”，不支持所有来源任意并发或重复运行。
Direct-pending限定`valid_count=1`；其正常context回收、重新注册和多记录范围仍缺。
数组划成`Mem`/寄存器子模块也没有选定真实宏、端口与访问延迟。功能测试实例和后来的
DC控制投影必须区分：数组proxy用于成本测量边界，不能拿来证明真实存储读写功能。

### M2的两条实现分支不能合并理解

早期曾尝试把A4的private/shared、birth-ordered span模型直接落实为存储单元。
`RouteAM2EntryStorage`使用双128-bit head和614个128-bit span，接受显式声明，支持
append、选择、dequeue与release；其4/4定向通过只属于fixture驱动的单元测试，未接入
production DUT。现有非连续成员组和opaque mapping也不能自行生成birth/sequence/count。

随后选择较小的生产职责：保留A4详细FIFO生命周期为replay/accounting证据，先实现
admission所需的metadata append。最初生产owner只检查provenance和两成员响应，仍不足
以证明entry内容：group的opaque mapping reference和owner只是归属事实，不能当作
entry值、物理地址或更新数据。后来才接入真实`MetadataAppendOperand`、私有prepare、head lookup、
slot/generation/credit与abort。Member响应不提前改可见entry；匹配publication才原子写
双head及span，真实post-R6 all-member handoff再清对应entry并归还资源。

MR-2最终验证和隔离的是这条较小生产分支的entry数组。两个分支名义上都有128-bit
head/span，不代表字段含义或生命周期相同。当前生产功能不因此获得A4完整source-FIFO
select/dequeue/release引擎，也不能用早期“仍blocked”的提案描述后来的实际实现。
历史分支见Git整理前版本；当前访问与控制以[最终M2数组合同](../mr2_m2_array_boundary_contract.md)
及实际接口/源码为准。

## 5. 外部环境到底承担了哪些工作

外部服务有些可以是论文系统的正式组成部分，不必全部塞入RTL。但必须说明其工作、
代价及对DUT的假设，且不能由环境替DUT制造内部权限或完成事件。

| 外部角色 | 当前允许承担的工作 | 因而尚未证明的能力 |
|---|---|---|
| Frontend/runtime | 按原mask与hot/maturity规则提供arrival、disposition、attention、source声明和retire | 没有完成模型前端集成；DUT不自主生成完整算法决策或遍历计划 |
| Pending/location owner | 提供immutable payload binding、descriptor registration、数据位置与来源事实 | 完整pending目录、未入当前组对象的正向归属服务和持续owner复用尚未实现闭合 |
| Functional memory responder | 保存实际写入对象，精确回应已接受的R1请求，提供可控错误/合法停顿 | 不是HBM controller/PHY/CDC，也没有校准真实服务时延、争用或带宽 |
| Position sidecar backing | 按真实association/handle和R3位置提供sidecar数据 | Typed读取可以经过真实DUT，但最新两读场景的sidecar backing仍由环境写入，硬件写服务未完成 |
| R5 descriptor backing | 功能实例可有内部image；投影实例通过声明的外部服务读写descriptor | 外部backing的端口、owner服务、延迟和成本不能当作已实现或免费 |
| Functional partial provider | Python参考可从声明的Q/K/V/position产生partial；Chisel场景接收相应协议包 | 当前whole-DUT重复读测试没有建立实际返回K/V→partial的数值对应 |
| R4 reference/provider | 按包和merge work提供匹配result或fault，DUT校验关联并终结 | Python有数值参考不等于Chisel已有FP/exp流水线，也不等于已做实时跨语言数值联调 |

最关键的未连接处是：当前阶段A记录的top没有实际Q向量入口，S2 payload/sidecar的
数值消费读取接口未接入partial计算；近期DUT场景使用固定partial/result协议包。
因此既有“数据搬运正确”与“Python数值参考成立”是两类证据，尚未在同一次DUT执行中
完整连成attention数值结果。后续即使继续使用外部attention计算单元，也要补这条连接，
并声明服务能力和成本；不必因此先实现完整NPU。

合法且唯一的arrival/maturity等输入仍有前端合同前提。R6没有复制完整逐token authority表，
不能把合法场景中的归属检查解释成已经检测所有非法重放或任意输入序列。

## 6. 从首次使用回到持续执行：两个探针与持久页v2

### 先验证现状：首轮通过，第二轮在哪里停住

**目的与方案。** 2026-11-09阶段A把持续目标收窄为两个可检查场景：同一session内，
同页在不同step读两次；同session接收两组admission。先不改RTL，运行真实首轮后再尝试第二轮。

**结果。** 两项诊断测试均正常通过，但通过的是“复现阻断”，不是新增功能成功。
两个case首轮都完成一次实际packed write、8个payload片段与1个sidecar片段填充、
四消费者commit和一个成功terminal。随后观察128拍：

| 尝试 | 具体阻断 | 排除了什么误判 |
|---|---|---|
| 同页第二次读 | R6已接收新attention/plan，但binder缺已消费的一次性page-ready/member事实，尚未发descriptor查询或S2 lease | 页仍readable、S2已Empty、session仍Active；不是页被读完就回收或session已结束 |
| 第二组admission | 第一组relay后ingress停在`StateDone`，没有回`Collect`，第二组三元join无法接受 | Metadata credit占用已归零；不是credit没有归还。Journal是越过入口后仍须处理的独立义务 |

这两个结果把缺口落到了具体控制阶段，而不是笼统认为“连续运行可能有问题”。128拍是
该有界诊断的观察窗口，不是任意输入下的形式死锁证明或硬件服务时限。

### 持久页v2：只补重复读取，不顺带宣称多组已经解决

**方案。** 保持默认v1/通用wrapper，显式开启`persistentReadEnabled`的v2。将仍存活页
的持久read-ready资格归给R5，通过合法查询为每次服务取得新读取事实；S2每次建立独立
lease和消费者状态。Publication/member流负责建立页，不再要求每次重读重新publication。

**结果。** 首轮v2为11/14，三个完整DUT场景都停在首次读取，尚未证明第二次服务。
原因是R5共享lookup的scanner outstanding归属处理留下未清状态；修复后先以真实R5
父级mark/query/query检查确认，再验证完整场景。这是功能缺陷的修复，不是面积优化。

r2验收共7 suites/15项native测试全部通过：v2完整DUT3项、真实R5父级及
关联owner/controller/R6的6项、默认v1功能回归4项、默认v1原阻断诊断2项。后两项仍
正确报告v1的READ_REUSE/ADMISSION_REUSE阻断，不代表v1新增了持续能力。

同页两读的关键数据如下，来自同一次session，中间没有reset、第二次publication或
host重新预装packed页；packed payload由本次真实R1写入产生：

| 实际事件/身份 | 已验收结果 |
|---|---|
| Packed payload write / publication | 各1次 |
| 两次payload fill / sidecar fill | 共16 / 2个片段，每次核对原数据与位置 |
| Consumer commits / source releases / 成功terminals | 8 / 2 / 2 |
| Packed PageRef | 两次均为page0、page generation0 |
| 同一S2槽的source generation | 1→2，说明两个独立服务实例 |
| 最终退休 | Descriptor不可读、allocation释放、R6到Retired |

错误场景在真实首次服务后，分别检查错误page generation、attention owner、S2 slot
及next-generation：每项恰一个fault terminal，没有额外read或source release，随后合法
第二次服务仍可成功。未对应live attention的foreign declaration只有本地拒绝，不制造terminal。

Retire交错场景在第二个attention/declaration已接受、selector尚未到达时请求退休；页在
16拍观察中保持live，随后补齐原selector，完成第二次服务，再失效/free并返回一次retire ACK。
这只覆盖指定切点，不代表任意partial admission或全部cancel/lease交错都已验证。

**分析与边界。** 这项结果证明“长期页”和“每次临时服务”可以分开管理，但验收使用
allocator8、stream16、handle32、相关generation2 bit、单有效record尾页、packed-only
顺序attention，且`gateCompactMembershipWords=false`、`numeric_correspondence=0`。
它不覆盖满64记录页、全部32K、mixed-source持续执行、generation wrap、external-v2
或WCG1完整anchor动态验证；也没有产生包含这次v2修改的新DC/STA结果。

## 7. 为什么第二组还没补齐：入口、历史与pending是三件事

**目的与方案。** 多组讨论先检查旧记录的最后使用点，而不是直接把`Done`改回`Collect`。
需要分清四种存活期：packed页留给后续读取；S2槽按次释放；组/credit按交接归还；
journal及pending descriptor要覆盖仍合法的查询、withdrawal和服务。

**结果。** 当前journal最多64条，原binding和标志合计2,264 B；旧wrapper允许迟到精确
查询，publication、读完、page reclaim或retire ACK都没有自动关闭它。直接清旧组，可能
把已转packed的对象查成`Unseen`；用新组ordinal覆盖，又可能让旧查询/withdrawal碰到新记录。
另外，pending descriptor owner每reset只注册一次，没有正常完成后重新接收的闭环。

因此有两类尚未实施的方案：保留旧合同，就迁移精确历史并保证查询连续；改变生产合同，
就由生产者明确冻结/关闭旧组注册，并排空或移交在途责任，才复用64条工作区。前者的
288 MiB直接归档只是一个最坏容量候选，非算法下界；后者的有限参考模型已得到条件性
正结果，但当前RTL没有相应生产者seal、归属查询、负响应和正常context回收能力。

进一步审查确认：**不属于当前packing组的pending也可能完全合法。** Admission budget512
限制一次服务量，不是所有pending的容量上限。参考规则下的合成keep-all例子中，8 heads、
1024-token prefill、hot128得到7,168条matured记录；服务512条后仍有6,656条pending。
这是用于排除错误容量假设的标量示例，不是实际KVzap请求结果。

候选关窗因此区分“真实组成员”和“独立合法pending对象”：成员由accepted ingress证明，
未入组对象由location/descriptor owner正向证明live/pending。R3没查到不能自动授权，
关闭G0也不能把无关pending一起清掉。已发出的lease继续履行；未知目标查询先解析或
移交，held result保持稳定，旧页仍可重复读取。这些是候选合同/参考检查结果，尚不是
多组admission的native RTL通过结果，也没有确定必须把新目录放在硬件还是软件。

## 8. 当前功能边界与持续decode的剩余缺口

| 能力 | 已验证范围 | 仍缺什么 |
|---|---|---|
| Admission→packing→publication | 有界组、真实owner、payload与descriptor前提、逐成员转权 | 同session多组接收、工作区安全周转及累计容量验证 |
| Packed页读取 | 首次使用通过；显式小规模v2同页两读通过 | 多页遍历、完整workload、多记录页及mixed-source持续场景 |
| Pending来源 | 单记录关联、lease、取消/转权交错有证据 | 未入组来源的生产归属服务、正常重复注册/释放、多记录与容量覆盖 |
| GQA/merge/terminal | 四消费者协议完成、包/identity检查、声明成功/错误路由 | 实际Q/K/V/position→partial→merge的同次执行数值对应 |
| Retire/reclaim | 原首次路径和v2指定preflight切点通过；失效先于free | 更多在途切点、partial admission、服务交接与fault cleanup覆盖 |
| 身份与资源复用 | 小测试验证部分generation与背压情形 | 目标命名空间边界、wrap/quiescence、真实最大live与服务压力；没有最大持续步数结论 |
| 物理服务与成本 | 有控制映射证据，独立于本报告的功能验收 | 存储/外围、外部计算/内存服务、统一时序与完整差分成本；原DC不包含后加v2 |

阶段A要求的是一个session内的有界持续执行；最终retire后无reset重新开session不是
已约定目标，不能将产品级session reopen混进当前缺口。32K/单sequence同样只是目标
包络，小参数测试不能替代全容量或所有合法并发验证。

**实现过程的价值，是逐步把验证平台便利条件换成真实owner，并用动态探针纠正了
“首次能用就能持续”的假设。主要不足，是持续生命周期与数据—数值连接没有在首次
功能路径完成时一起验收。** 继续讨论职责分离时，应保留这些真实证据，同时明确哪些
工作仍由环境完成；不能把当前缺失都称为局部门控问题，也不能将协议包通过当作数值加速。

## 9. 原始定义与结果入口

实现库存可核查[RTL入口接口清单](../rtl_entry_interface_manifest.json)、[RTL2/3推进](../rtl2_0_activation_manifest.json)、
[七种source协议覆盖](../rtl3_8_5_full_path_closure_coverage_manifest.json)、
[C4-D首次使用结论](../rtl3_9_c4_d_functional_completion_review_manifest.json)、
[MR-1B单记录路径](../mr1b_direct_pending_cross_owner_contract_proposal.md)、
[MR-2边界](../measurement_dut_cut_freeze_20261025.json)与[测量DUT范围](../measurement_dut_cut_freeze_20261025.md)。

持续执行参见[阶段A范围与环境](../route_a_stage_a_execution_envelope_20261109.md)、
[两项现状探针](../route_a_stage_a_probe_result_20261109.md)、
[持久页r2结果](../route_a_persistent_page_read_r2_result_20261109.md)、
[多组journal寿命](../route_a_multigroup_journal_lifecycle_closure_20261109.md)、
[关窗条件验证](../route_a_registration_window_contract_validation_20261109.md)和
[pending归属合同](../route_a_pending_origin_and_window_contract_20261109.md)。这些链接用于
技术复核；研究过程与边界已在本文串联，不需要逐份阅读启动、重试或哈希记录。
