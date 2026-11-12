# H3：存储实现、测量边界与完整成本

整理日期：2026-11-12。本文承接[算法R6](../algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md)、
[H1](01_architecture_and_software_hardware_boundaries.md)与[H2](02_rtl_implementation_and_sustained_execution_scope.md)，
串起存储需求、SRP/MBR测量范围、MR-2数组隔离、compact审计及完整增量账本的探索。
只整理已有定义和结果；没有修改RTL、重跑模型/仿真/综合或新增存储实现。

**当前DC量到了真实父级控制和compact等寄存器状态，但没有完整量到P3、M2、R5、S2
的物理存储及外围，也没有量到全部外部数值和内存服务。前RTL模型有部分容量、字节和
能量proxy，不能直接拿来填补当前RTL的缺项。存储是否经济，需要同时看信息、存活期、
访问方式和实际存储单元；字节数小不保证电路便宜，写成`Mem`也不等于已经用了SRAM。**

## 1. 目的：从“少留多少KV”走到“为此新增多少东西”

原mask减少有效KV，为容量与读取节省提供机会。但Route-A还要保存待整理数据、形成
packed页、记住位置与目录、追踪在途服务，并保留仍会被引用的事实。本阶段要回答：
这些状态为什么存在，实际放在哪里，支持怎样的访问，哪些已经进入成本比较？

前期A4.14.1以三个固定workload得到条件性正预算，允许进入架构设计；随后RTL暴露了
更具体的状态与端口要求。H3关注两者怎样对应，面积/时序优化的逐项实验留给H4。

| 推进步骤 | 目的与方案 | 结果及对下一步的作用 |
|---|---|---|
| A4存储/服务模型 | 计入packed容量、pending搬运、M2候选及共同S2访问 | 得到条件性机会，同时留下P3本地stage、完整控制、数值与外围等未计项 |
| SRP划分 | 将功能实现拆成控制、存储、外部服务和验证环境 | 明确Chisel可导出不等于宏/综合已准备好；未估项不能按0处理 |
| MBR测量边界 | 选择保留真实控制、对数组与外部服务显式设边界的Full-KV/Route-A对照 | 避免把测试平台当硬件，也避免把整个父模块黑盒化来隐藏管理成本 |
| MR-1/2与测量DUT | 接通生产父控制，隔离P3/S2/M2/R5逻辑数组内部 | 功能边界通过；保留prepare/commit/abort、READY、generation、credit与reclaim等控制 |
| Paired DC | 在同库、同2 ns条件下映射上述控制投影，数组使用typed代理 | 得到实际控制面积与时序；数组实现和外部服务仍需另计 |
| STORE P0与存储选项 | 检查compact字段来源、重复、寿命、访问及最大live | 两个opaque64不能按旧合同截短；发现存储单元/读取网络和有条件复用等方向 |
| 增量账本与P3映射评估 | 逐项对照实际RTL、旧proxy、端口并发及遗漏外围 | 明确当前M2与旧proxy不同；P3有有限模型支持的1RW候选，但未落实RTL、宏或价格 |

## 2. 测量边界：DC数字里有什么，没有什么

功能实现中的数组可以存取字节；物理实现还需选宏、端口、bank、读写延迟、初始化与外围。
MR-2先把存储内部与父控制分开，后续DC用typed array proxies替代内部实现，让控制
映射能够进行。Proxy是测量接口，不是一块已计价或已经满足时序的存储宏。

**保留在DC中的部分**包括M2/P3 wrapper、M2生产控制、metadata bridge、page manager、
R1/R2/registry/router、source/activation等实际父级控制，以及compact表、journal和
其他未被隔离的寄存器。它们已在顶层面积中，不能再作为“待增加的metadata宏”重复收费。

**排除的部分**包括typed存储子模块内部及明确外部服务。实际代理替换的是整个子模块
body，因此缺项不只裸存储位，还包括其中的索引、访问、响应/ACK保持等逻辑。例如账本
识别了P3子模块558 bit、M2子模块178 bit的声明协议状态；这些和其他子模块外围都需要
在真实替代实现中计价。父级适配与状态机仍留在DC中。

| 存储/状态 | 为什么需要 | 当前容量或组织 | 当前DC覆盖 |
|---|---|---|---|
| 两张compact表 | 保存已接收成员及pending读取关联，供搬运、校验和转权使用 | `36×64×(79+80)=366,336 bit`，44.71875 KiB | **已计**；wrapper内寄存器及访问网络 |
| Reconciliation journal | 精确withdrawal和旧合同允许的迟到查询 | 64条281-bit binding及标志，共2,264 B | **已计**；寿命不同于compact工作表 |
| P3 payload stage | 将pending数据组织为packed页写出 | 36层×32 KiB＝1,179,648 B | 子模块内部**未计**，父控制已计 |
| P3 local sidecar | 为stage保留位置关联与写入状态 | `36×64×8=18,432 B` | 与P3内部一起未计 |
| M2 head/span entries | 保存head/span元数据及镜像更新对象 | 双head共9,216 B，span共9,824 B；合计19,040 B | 子模块内部未计，生产prepare/发布控制已计 |
| R5 availability/generation | 分配页、排除旧引用、安全回收 | `146,880×(1+8) bit=165,240 B` | 数组内部未计，选择/回收等父控制已计 |
| R5活动stream与其他控制 | 维护当前stream、可见性及操作关联 | 架构曾定义288×96-bit stream描述；RTL有具体父级状态 | 父级状态已计，不能另加一份规格表当新成本 |
| S2 payload | 暂存读入页，供四个GQA消费者复用 | 两侧各两槽，共64 KiB/侧 | 两侧payload内部均未计；各自父控制已计 |
| Route-A S2 sidecar | 为本次packed服务提供位置 | 两槽共1,024 B | 内部未计，关联控制已计 |
| Pending/packed HBM与位置backing | 保存长期KV及搬运期间的合法来源 | Anchor选择共享5 GiB cold pool，含payload、位置及migration reserve | 外部；部分历史容量/流量模型已计，不是DC面积 |
| R5 HBM descriptor region | 提供长期页目录、链接、状态与generation记录 | `146,880×16=2,350,080 B`，独立于cold pool | 外部服务未计，局部维护控制已计 |
| Partial/result及外部服务状态 | 完成attention计算、合并与传输 | Anchor四消费者partial接口合计2,080 B；物理组织未选 | 结构控制部分已计；数值、RF/SRAM、spill与服务实现未完整计价 |

这里的容量是不同对象的账目，不是可以直接相加的面积表。P3 stage、S2 buffer和HBM
中的packed页可存有同一KV的不同阶段副本；功能上有联系，成本上是不同存储资源。
两张compact表也不是P3 payload数组或M2 head/span数组，不能混为同一个热点。

## 3. Compact：为什么只有约45 KiB，却成为大面积来源

**目的与方案。** 在去掉重复坐标等字段后，STORE P0继续检查剩余字段是否可缩短、
重复保存能否复用、哪些消费者延长寿命，以及小规模production范围是否允许缩表。

| 一对member/suffix记录的字段 | bit数 | 信息来源/用途 |
|---|---:|---|
| Logical position | 15 | 成员位置、sidecar及R6观察 |
| Payload reference | 64 | Frontend提供的opaque逻辑引用，参与精确关联 |
| Transaction identity | 5 | 请求与incarnation匹配 |
| Pending handle/address | 64 | 独立pending owner提供，实际读取定位 |
| Source generation | 8 | 排除旧来源/旧响应 |
| Destination endpoint | 3 | 精确选择和检查目的端 |
| 合计 | 159 | Member79 bit、suffix80 bit，分别有独立写使能 |

**结果。** 两个64-bit字段占294,912 bit，即表数据的80.503%。旧接口没有高位为零、
对齐、固定步长或彼此可推导的保证，不能从32K位置空间推出它们可截成15 bit。
小索引可以指向其他存储，但完整值仍要有合法backing，索引/查询也要付费。

通用wrapper保留36×64个member槽；production ingress当前最多一组64条/reset。
这两者是不同边界：不能用当前一次性入口的限制，直接宣称通用容量只需64条或持续执行
也只需64条。这里compact的36个bank按layer组织，与M2的八个head-affine bank不同。
Suffix的有效bound量另受全局64条journal约束，不能与member容量混算。

Member在publication后还用于观察和R6交接；suffix在materializer发出工作后，独立的
checked-work端口仍可能需要它；journal又继续服务迟到查询。按“搬运读完”统一释放，
会删掉仍被合法引用的事实。更短寿命可能降低实际占用，但没有最大live证明，也不会自动
缩小一个固定分配的寄存器数组。

**面积分析。** 早期compact映射归因确实找到182,016个member和184,320个suffix存储
单元，合计恰好366,336 bit；其enabled-DFF存储面积约1,292,433 cell-area units。
这个历史数字不是最新WCG1表面积，但说明大状态与声明一致，未证明是综合误把KV
payload展开进来。另有大量索引选择、关联比较、写译码和输出生成成本。

RD1后，member reference按字段需要仍可有每bank最多四路逻辑读，position最多两路，
suffix有M/C两路独立读；这些是保守访问需求，不是已选宏端口。寄存器提供组合读和旧值
可见性，代价是存储单元加多路选择网络。现有同步单端口SRAM不能直接替代：banking
不保证任意同bank请求不冲突，复制读口会增加容量，串行化又可能改变接口周期。

存储方向得到了不同层次的结果：

| 方向 | 已有结果 | 不能据此声称什么 |
|---|---|---|
| ST1：删大suffix表、改读journal | Production全局ordinal不复用不足以成为通用wrapper保证，简单替代未获通用等价资格 | 未证明所有journal复用都不可能，也没有完整RTL等价或面积收益 |
| 反向复用：保留大表，journal借读suffix | 有缩小重复数据的抽象关系，最多涉及`64×80=5,120 bit`；额外bank选择可能抵消收益 | 不是ST1同一方案；没有实际映射净收益 |
| 共享读取/写译码 | RD1取得完整顶层收益；其他选择网络表示需单独实测 | 网络优化不消除存储位，也不能把各方案收益直接叠加 |
| WCG1共享字门控 | 最新顶层保留366,336普通DFF及4,608个native gates，实际面积降低 | 位数没有减少；根fanout降低不等于同幅功耗降低或时序闭合 |
| 多路异步register file | 能保持组合读取的候选方向，尚无匹配实现/价格 | 不得用免费array proxy代替真实RF、端口和外围 |

这里同时存在三种成本：**必要信息、所选接口要求的访问能力，以及每bit采用怎样的
物理存储。** 当前无法截短字段，不代表必须永远付出原enabled-DFF的成本；WCG1已经
提供实例。但若重新讨论全局引用与软件目录，也属于接口/职责变化，不能当旧wrapper等价优化。

## 4. P3：为什么需要一大块stage，能否映射到合理存储

**目的与方案。** 已保留但未packed的KV仍须可读，因此P3选择pending HBM backing，
每层另留一页临时stage形成packed写入。Pending保持权威，直到真实publication交接；
stage不产生第二份逻辑归属。每层一页是本路线的映射选择，不是KVzap必须规定的容量。

**结果。** Payload共18,432个512-bit word，另有2,304个64-bit sidecar word。
实际子模块有三路独立逻辑通道：payload写、payload读、sidecar写；跨层填充和写出可以
重叠。36个stage不等于36个读写端口；反过来，只有一个packed writer也不证明一页stage
足够，因为其他层可能仍在reserved/filling/durable或等待publication。

P3映射评估利用已有握手特点：每路response/ACK保持期间不能接新请求，消费当拍也不
立即补入新请求。因此同时接受payload读写后，下一拍必有一个可排空机会。候选用
**一个逻辑1RW存储＋一个延后写buffer＋读响应保持**，在接受边沿读R并保存W，下一拍
写回W，外部仍按原时间得到响应。Sidecar写通道独立保留，不与payload抢同一裸端口。

有限payload模型在非alias范围检查160状态/37,888转移，无不匹配；负对照发现丢写、
reset清掉待写数据、后续写破坏held read等真实风险。该结果只支持协议可行性，未形成
候选RTL或选定宏；sidecar没有包含在payload模型枚举内，同地址碰撞语义也仍需落实。

**分析。** 这条候选有望用较窄端口服务满足既有逻辑并发，但不能直接报面积收益。
除全部容量，还要计buffer、地址/标志、保持寄存器、mux、宏读出时序和外围。
若宏深度由18,432向上取整成32,768个512-bit word，就会从1.125 MiB变成2 MiB，
padding与bank/tiling均要实价。原2 ns、响应延迟与reset下已接受写入的保存要求不能被忽略。

P3本地sidecar目前只有写/ACK口，没有子模块读口；materialized位置另来自R3成员事实，
packed位置服务又在外部。这个现象值得继续追踪职责和重复表示，尚未证明可以安全删除
该存储。P3 child已在DC之外，合理实现它是在补齐漏账，不能冒充减少了现有控制面积。

## 5. M2：旧SRAM proxy为什么不能直接套到当前RTL

**目的与方案。** 早期M2用双head副本和span store满足声明metadata服务，后来RTL将
head/span对象、private prepare/abort、publication与handoff具体化。要比较成本，先核对
容量、字段、并发和外围，而不是只看都叫“M2”。

**结果。** 当前数组为288个key的两份128-bit head和614个128-bit span，名义152,320 bit。
账本中head有效字段42 bit/entry，span按当时profile为59 bit/entry；合计60,418个非reserved
bit及91,902个reserved bit。这提供格式紧凑化的审查对象，但数组已被DC排除，减少其
声明位宽不会直接改变当前控制数字，也未证明能减少宏形状或端口成本。

端口要求比容量更关键：lookup可与写入重叠；publication commit和all-member handoff
release是两路无ready的Valid事件，可以同拍写不同head/span地址，并可能连续发生。
不同地址不等于不同物理bank；两份head副本都要更新，也不能用复制1RW宏自动解决两写
冲突。Lookup读取旧值、镜像/跨度更新的原子性、reset与保持行为都需要真实映射。

历史public-CACTI估计为**0.52857872 mm²，0.032 μm proxy**。旧构造采用64-bit modeled
word、225个head对象、614个span、八bank及1RW宏；含padding和保守queue/staging后
重建provision为319,488 B（312 KiB），其中294,912 B来自pooled queue/staging假设。

**分析。** 这个312 KiB与当前19,040 B名义entry数组既不是同一实现，也不是两份必须
相加的存储。当前metadata bridge有credit计数器和按层group记录，没有由这些计数器
自动推导出的36,864条物理queue。需要将必须保留的事实映射到runtime、ingress和owner，
才能判断是否还缺队列；不能因为旧模型计过queue就机械补一整池，也不能宣称队列免费消失。

旧M2动态能量主要覆盖head/span entry访问，queue/staging动态access与完整控制活动未计。
历史1RW服务坐标也没有证明当前两写＋lookup接口在2 ns可实现。因此旧proxy保留为研究
结果，不能作为当前M2的匹配价格，更不能直接与DC面积相加。

这里还有一条历史分叉：曾通过4/4单元测试的`RouteAM2EntryStorage`保存private/shared
FIFO头尾、birth/sequence/remaining和链接；它没有成为production实例。后来采用的是
admission-derived append、private prepare、publication commit及post-R6 handoff的较小
生产分支，当前42/59非reserved字段属于后者。两者128-bit外形相同，不表示数据格式、
服务事件或成本相等。也不能把旧FIFO单元的allocator/RMW与当前生产owner再重复相加。
生产entry集成已完成其有界功能范围；物理宏、端口和完整成本仍未完成。

## 6. R5、S2和外部存储：共有设施与Route-A增量要分开

**R5。** 页分配与安全复用需要availability、generation、目录及在途排除信息。规格早期
仅availability bitmap就有18,360 B；当前availability加8-bit generation为165,240 B。
两者比较口径不同，不是一次测得的面积增加。页选择、reclaim与可见性父控制已经映射，
数组内部和外部descriptor服务仍未完整计价。Bitmap、逐页generation和全局目录究竟
由谁保存，是职责/接口选择；旧引用不能访问新对象则是必须保持的安全要求。

**S2。** 两个32 KiB payload buffer服务GQA共享读取，属于公平Full-KV/Route-A共同设施；
Route-A另外需要packed位置sidecar及相关管理。A4曾给共同S2 **0.580656 mm²**的public
CACTI proxy及分路径访问能量，但这不构成当前两侧wrapper实现相同的证明。共有容量不能
全记Route-A增量，具体父控制差异、侧信息与动态活动也不能凭“共有”名称直接抵消。

S2后续已有同一9-bit/512-fragment几何下的配对回归：Full-KV 5/5、Route-A 6/6，
合计11项通过，消除了早期focused Full-KV测试只用3-bit索引的比较缺口。该结果确认
相同payload访问角色与指定reset/stale/fault/response-hold/释放行为，未证明两个shell
是同一实现。Route-A还有sidecar、packed lease/page与R6来源身份；Full-KV使用自己的
producer和terminal/retire链，因此payload/adapter仍不能直接抵消。

当前配对成本的具体处置是：R1/R2/registry/router在配置和shell相同时才有共有资格；
两侧delivery bridge分别计价；lifecycle/status按各自实现保留；实际source list中的hot
owner只在Route-A一侧，暂作该配对的差分控制。不能为抵消而虚构Full-KV hot模块。
这些是当前测量边界的处置，不是所有Full-KV系统都无需hot管理的结论。

**外部HBM。** Anchor的5 GiB是pending/packed共用的cold池，包含位置与迁移reserve，
不是两份5 GiB；R5约2.35 MB descriptor区另计。算法实际保留率、页取整、pending与
packed交接时的副本决定使用量，预留上界不等于workload实占或硬件面积。
部分读写字节及声明HBM动态能量早已进入A4，但controller/PHY、物理组织、争用及完整
维护流量没有因此完成。多个逻辑服务不应各虚构一套controller，共用服务也需要计差分活动。

**数值与服务状态。** 四消费者partial接口共2,080 B，不等于只需这么多物理寄存器。
RF/SRAM、holding/spill、算术、供数与merge互连还需根据执行方式确定。外部参考输出数值
结果，可以支持功能研究，不能成为面积、能量或服务延迟为0的依据。

## 7. 开销从哪里来：算法需求、职责划分与具体实现

| 层次 | 必须解决的问题/当前选择 | 成本含义 |
|---|---|---|
| 算法与attention正确性 | 保留集合正确，KV身份/位置关系正确，不漏读或重复计入，满足数值标准 | 这些信息与工作必须由系统某处承担；不规定必须采用当前表、字段位宽或硬件owner |
| Route-A组织 | Hot/pending/packed、一次packing后多次读、按页供数与多来源partial | 引入搬运、目录、临时stage、位置与合并工作；是所选路线的责任，不是所有KVzap实现的唯一组织 |
| 职责与接口 | 硬件保存完整member/binding，接受迟到查询，多路即时读取，逐成员交接，按层预留stage | 决定保存多久、最大live、查询/端口与并发；可讨论新软硬件划分，但必须重新定义和验证合同 |
| RTL与物理表示 | Enabled-DFF或字门控DFF、组合mux、复制head、128-bit padding、bank/tiling与宏外围 | 同样语义可以有不同代价；RD1/WCG1体现已有改善，其他映射尚需实现证据 |

因此，容量大不能全部归因于算法，也不能全部视为可删冗余。Opaque字段缩短需要新表示
与owner保证；长期历史限制需要关闭条件；SRAM需要匹配端口与延迟。改由软件保存全局
事实可能减少硬件状态，但仍要计软件目录、命令、查询、同步和服务成本，目前未证明净收益。

## 8. 已计与未计的总判断：现在还不能给出完整面积比

最新RD1＋WCG1 primary在同库同2 ns下：Route-A cell area为**2,990,737.008920**，
Full-KV为**23,091.432498**，比值**129.517×**。Wrapper约占67.46%，且setup仍未闭合。
这个快照有真实控制映射价值；它不包括后加持久页v2，也不包括上表全部缺项。

完整账本应分别回答：

- **固定面积/容量：** 两侧控制、真实存储宏/复制/端口/外围、必要计算与系统集成的差分。
- **动态能量：** KV访问节省减去packing、metadata、buffer、partial/merge、命令与服务等新增活动。
- **静态能量与时间：** Leakage、时钟/互连，以及真实执行时长；服务坐标不能直接拼成时间。

DC cell-area units、32-nm CACTI mm²、HBM容量B和每请求mJ属于不同技术/单位/范围，
不能直接加总。父层次包含子控制，不能与顶层重复相加；将来计宏，也要分清已映射父外围
和此前被代理排除的内部外围。完整Route-A/Full-KV比例会同时受到共同设施、额外管理
和少存KV的影响，不能由129.517×直接推断最终比例必然更大或更小。

前RTL的正动态能量遗漏预算只给出一个条件：Route-A未计能量比Full-KV未计能量多出的
部分必须小于原已计节省。它没有给控制面积、存储宏或时序违例买单。**目前已完成的是
主要存储与成本边界的识别及部分映射证据；同技术、同功能、同服务的完整差分成本和
净收益仍未建立。**

## 9. 原始定义与结果入口

测量过程参见[SRP结论](../srp5_completion_review.md)、[MBR边界](../measurement_boundary_selection.md)、
[MR-2](../mr2_completion_review.md)及[测量DUT](../measurement_dut_cut_freeze_20261025.md)。
具体成本来自[增量账本](../route_a_incremental_storage_cost_ledger_p0_20261106.md)、
[STORE P0](../dc_compact_store_p0_audit_20261106.md)、
[历史compact映射归因](../dc_compact_wrapper_hotspot_attribution_20261104.md)、
[存储选项](../dc_compact_storage_realization_options_20261106.md)、
[ST1范围结果](../dc_st1_scope_key_validation_result_20261106.md)、
[P3映射评估](../p3_staging_storage_mapping_feasibility_20261106.md)及
[最新RD1＋WCG1结果](../dc_rd1_wcg1_full_paired_result_20261109.md)。
前RTL各项proxy与遗漏预算的完整解释见算法R6；当前持续功能及其环境边界见H2。
