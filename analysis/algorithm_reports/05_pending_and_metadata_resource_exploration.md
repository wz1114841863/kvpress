# R5：Pending与metadata资源探索

整理日期：2026-11-12。范围：A4.3—A4.10，包括激活/保护、pending服务与容量、
共享归属、span表示、metadata事务、抽象服务和有限队列。本文整理既有软件实验、
trace和模型结果，未运行模型、重放实验、修改RTL或启动综合。Qwen与Llama的
请求、predictor、数值标准和continuation条件分别保留，不能合并成请求分布。
功能参考沿用Qwen官方MLP/threshold −4、Llama官方Linear/threshold −7、hot128/
page64；每模型为retrieval、summarization、reasoning各一个固定内置请求，不是
正式准确率benchmark。各阶段的服务与组织敏感性在下文另述。
本轮在已有远程项目中找回A4.9.2/A4.10原始汇总，并核对其与下游冻结输入的
身份关系；§9补充真实对照数据，原件仍在远程，没有新建本地数据副本。

## 1. 这一阶段为什么逐步走向资源管理

[R3](03_functional_reference_and_execution_observations.md)证明了给定mask下的
三源软件路径；[R4](04_cross_model_and_frontend_boundaries.md)划清了跨模型和
算法边界。接下来的问题是：被保留的KV离开hot后，未必立即有条件完成packing。
这段等待中的数据仍要能被attention读取，也要能在未来正确完成转移。

可以把pending理解成“已经决定留下、正在等候整理入库的KV”。容量不足与整理
速度不足是两个问题；把容量集中共享又会引入“属于谁、谁最老、何时可以释放”
的管理工作。由此，研究从pending峰值走到了metadata和服务合同。

**本阶段的主要成果是：在固定轨迹和声明服务条件下，共享能够回收明显的逻辑
容量，带出生/顺序的span能保持归属与FIFO，原子事务及服务模型能显式暴露管理
代价。它没有证明这些状态已经以低成本硬件实现，也没有得到任意请求的容量或
持续稳定性保证。**

| 推进阶段 | 实验目的与计划 | 得到什么，为什么还要继续 |
|---|---|---|
| A4.3 | 从attention快照走到append前后事件，改变prefill粒度和声明服务量 | pending确实随服务机会改变；快照不能直接选FIFO |
| A4.4—4.5 | 执行延迟激活、压力保护及退出 | 软件模式转换可验证；保留Full-KV的回退成本仍在 |
| A4.6.0—4.6.5 | 分离激活库存和后续到达，加入竞争、因果服务和容量观察 | 服务不足与容量偏斜必须分开，未来信息对照不能当在线控制器 |
| A4.6.6—4.6.7 | 固定服务，比较私有、共享、分层及归属管理 | 共享回收容量，但有额外管理工作，需要可验证表示 |
| A4.6.8 | 验证birth-ordered span，记录其生命周期和访问原语 | 不能只保存source总数；还需要顺序、归属和oldest信息 |
| A4.7—4.8 | 固定记录、事务、commit和依赖，再研究映射与积压 | 即时依赖阻塞可能由早先服务不足传播；RMW拆分没有免费收益 |
| A4.9—4.10 | 声明候选执行、有限队列和lossless credit | 得到供后续成本核算使用的模型合同，仍需实现级计价 |

阅读本报告需要区分三种“量”：pending中的KV记录数、管理它们的metadata记录数、
等待执行的metadata事务数。它们不是同一个队列。逻辑机会/检查点也没有ns或硬件
周期含义；各阶段的Q、service quantum不能互相换算。

## 2. A4.3：pending大，是否只是一次性append造成的

**目的与计划。** A4.3.1先在三类Qwen请求的attention比较时观察pending；A4.3.2
记录每次append的maturity前、maturity后、参考服务后三个状态，要求trace开关
不改变答案和mask。A4.3.3用标量递推检查声明Q/C条件，再以真实功能重放检验
prefill拆分，而非只修改离线数字。

基本守恒关系是：`新pending = 原pending + 新成熟保留项 − 实际admitted项`。
服务多少和什么时候有服务机会都会影响状态。A4.3.4把prefill拆成连续chunk64；
A4.3.5—4.3.7比较Q={1,8,32}，并加入条件化Llama实例。

下表为chunk64下，所记录layer/head事件的**单流、服务后pending最大值**：

| 模型 | 固定workload | Q=1 | Q=8 | Q=32 |
|---|---|---:|---:|---:|
| Qwen3-8B | retrieval | 803 | 773 | 692 |
| Qwen3-8B | summarization | 802 | 774 | 699 |
| Qwen3-8B | reasoning | 1,960 | 1,897 | 1,729 |
| Llama-3.1-8B | retrieval | 800 | 777 | 719 |
| Llama-3.1-8B | summarization | 801 | 781 | 727 |
| Llama-3.1-8B | reasoning | 1,883 | 1,843 | 1,719 |

Qwen reasoning的单流packed最大值同时从34增至273、1,071；Q提高使更多数据
完成逻辑admission，但本次Q=32仍未清除全部pending峰值。各Q点保持其规定的
同mask/输入轨迹与答案关系。Qwen使用其请求特定decode路径，Llama使用固定
8-token continuation，数值与自然输出条件不同，不对六行取共同容量范围。
来源：[跨anchor Q敏感性结果](../experiments/route_a437_cross_anchor_microevent_envelope_01/a437_cross_anchor_microevent_envelope_report.json)。

**分析。** pending并非仅是观察时刻的假象，也不能用“多给几个机会”就假定
已经解决。此处Q是功能参考的admission动作数，没有建立传输时间、端口或
服务完成时间，因此不能写成“需要Q深FIFO”或“Q=32硬件足够”。

## 3. A4.4—4.5：什么时候进入Route-A，压力过大如何退出

**目的与计划。** R2中的延迟admission只是收益模型。这里实际执行模式转换，
先验证不启用时纯Full-KV，再验证一次激活，以及激活后的保护边界。

| 场景 | 已验证的软件行为 | 保留的代价/边界 |
|---|---|---|
| D=8、请求在激活前结束 | 保持Full-KV；不创建Route-A逻辑hot/pending/packed状态 | predictor决策journal可以存在；未承担Route-A逻辑physicalization |
| D=1、进入ACTIVE | 从已有Full-KV历史恢复hot、成熟保留/删除项，按声明动作admission；每层恰一次激活commit | 激活时已有较大历史库存，native cache仍保留 |
| C=1024层内压力触发 | 触发层冻结Route-A状态，改用native attention | C是逻辑敏感性点，不是已选物理容量 |
| 请求级保护 | 本轮观察到触发后锁存，待全部层完成本轮，再于下一decode epoch全层fallback | 无法追溯改变本轮已经执行的较早层 |
| 保护后的shadow处置 | 下一epoch将Route-A shadow变为不可访问tombstone，不再append、admit、read或重入 | 仅证明逻辑不可访问，未测allocator释放或物理回收 |

Qwen与Llama各三个固定请求完成了相应合同覆盖。早期layer-local hook不能冒充
request-global控制器，因此增加了A4.5.2的边界对齐和A4.5.3的下一epoch验证。
来源：[激活合同六行对照](../experiments/route_a442_cross_anchor_activation_contract_01/a442_cross_anchor_activation_contract_report.json)、
[Qwen保护/shadow结果](../experiments/route_a454_protected_shadow_state_reclamation_qwen_fixed8_single_gpu3_c1024_01/a454_protected_shadow_state_reclamation_gate_report.json)、
[Llama保护/shadow结果](../experiments/route_a454_protected_shadow_state_reclamation_llama31_fixed8_single_gpu3_c1024_01/a454_protected_shadow_state_reclamation_gate_report.json)。

**分析。** 这些实验补上了“如何切换模式”的功能证据。回退依赖保留的native
Full-KV，不能把它当成不占存储的保护办法；tombstone也不能直接记为显存节省。
保护合同成立后，研究回到始终ACTIVE的正常路径，检查有限服务是否能处理积累。

## 4. A4.6.0—4.6.5：激活库存、持续到达与服务不足

**目的与计划。** A4.6.0使用固定64-token输入续写：一个Full-KV前缀decode后
激活，余下decode始终ACTIVE，不进入fallback。两个模型的六个固定请求，在
末32次append机会的检查中，持续非递减pending增长witness均为0、服务后pending
最大值均为0。这支持本次有限正常路径，不能证明无限运行稳定。
来源：[Qwen正常路径](../experiments/route_a460_steady_state_qwen_fixed64_single_gpu3_01/a460_route_a_active_steady_state_gate_report.json)、
[Llama正常路径](../experiments/route_a460_steady_state_llama31_fixed64_single_gpu3_01/a460_route_a_active_steady_state_gate_report.json)。

A4.6.1随后把激活瞬间库存与之后62次append机会的新增成熟项分开；A4.6.2比较
1/2/4/8/16/32/62机会的drain horizon。每head独享服务只作为无竞争乐观边界，
layer共享服务则显式轮询非空head，不能把两者的量当成同一个资源需求。

A4.6.3进一步声明eager copy与sealed-page copy＋tail reference，区分attention
持续读取与admission整理工作，比较attention-first、保留份额和可借用服务。
未来到达可见的deadline策略只作离线对照；A4.6.4再用相同的全局因果策略，
仅看当前/历史backlog、age和迟滞，在声明的16/64/256三级间切换。改变未来
到达不能改变过去决策，检查其因果性。A4.6.5只观察容量越界，不准改grant、
丢弃数据或暗中fallback。

以62机会的reasoning、固定因果轨迹为例，跨全层/head合计的逻辑记录数为：

| 模型 | 激活enqueue库存 | 后续enqueue | 最大backlog | terminal drain机会 | 最终pending |
|---|---:|---:|---:|---:|---:|
| Qwen3-8B | 70,294 | 2,185 | 70,338 | 23 | 0 |
| Llama-3.1-8B | 107,590 | 3,332 | 107,658 | 34 | 0 |

这里的drain是所记录机会上的终端排空位置，不是硬件周期。激活库存占大头，
但后续仍有到达；改变horizon会改变是否留下未完成前缀。来源：
[固定轨迹与管理账本](../experiments/route_a4671_pending_organization_tax_recovery_01/a4671_pending_organization_tax_recovery_report.json)，
其中继承A4.6.4的实际grant/outcome，并分别保存各horizon。

**分析。** 必须同时区分激活burst、持续到达、可分配服务和head间偏斜。
声明service budget表示一次能处理多少工作，不能据此把全局pending容量限制为
相同数值。这个区别也是后续比较存储组织时固定grant、不重新调度的原因。

## 5. A4.6.6—4.6.7：共享容量能回收多少，又新增什么管理工作

**目的与计划。** 固定A4.6.4的到达、grant和每head FIFO，只改变容量归属：
各head等额私有、一个layer共享池、私有额度＋共享overflow。容量观察不能反过来
改变服务。`Cmin`表示在覆盖轨迹上不越界所需的每层统一逻辑预算。

以下是62机会、post-arrival/pre-grant观察下的结果；每层8个KV heads：

| 模型 | workload | 等额私有Cmin | 全共享Cmin | 共享降幅 | 分层q=128/head的Cmin |
|---|---|---:|---:|---:|---:|
| Qwen3-8B | retrieval | 5,416 | 2,151 | 60.28% | 2,468 |
| Qwen3-8B | summarization | 5,416 | 1,952 | 63.96% | 2,414 |
| Qwen3-8B | reasoning | 14,728 | 5,811 | 60.54% | 6,145 |
| Llama-3.1-8B | retrieval | 5,680 | 3,438 | 39.47% | 3,537 |
| Llama-3.1-8B | summarization | 5,696 | 3,283 | 42.36% | 3,394 |
| Llama-3.1-8B | reasoning | 14,400 | 8,381 | 41.80% | 8,396 |

单位为逻辑KV记录/层，不是字节、SRAM条目或硬件FIFO深度。source模型固定
轨迹下计算精确Cmin；表内降幅是本次重算的`1−共享/私有`。来源：
[等预算组织对照](../experiments/route_a466_pending_organization_contract_01/a466_pending_organization_contract_report.json)。

**结果与分析。** 私有容量可能在某些head闲置，另一些head却越界；共享能吸收
这种偏斜。小私有额度的分层点保留了多数逻辑容量收益，但这没有计入共享管理
的物理成本，也没有证明“全共享一定最经济”。

A4.6.7进一步规定：每项的birth、head内sequence和入队source不可变，不能为了
简化而迁移；grant到来时必须在private/shared两端中选择真正最老者。单纯优先
private会在“旧shared、新private”场景破坏FIFO。

reasoning、horizon62、q=128/head的具体管理量为：

| 模型 | 相对私有回收的逻辑容量/层 | 创建source-affiliation segments | oldest比较 | source切换 |
|---|---:|---:|---:|---:|
| Qwen3-8B | 8,583 | 2,514 | 804 | 165 |
| Llama-3.1-8B | 6,004 | 3,648 | 1,606 | 193 |

segments、比较和切换是不同的逻辑事件，未赋统一成本权重，不能相加成access、
cycle或能量。全共享单source端点没有private/shared跨源选择，但仍有归属和
记录管理。来源：[容量恢复与管理暴露](../experiments/route_a4671_pending_organization_tax_recovery_01/a4671_pending_organization_tax_recovery_report.json)。

## 6. A4.6.8：用span压缩管理状态，先证明没有丢掉顺序

**目的与计划。** 不必每个pending token单独建完整管理记录，但压缩表示必须
能重建相同集合、归属和oldest。候选span保存`source、birth、sequence_start、
count`，只合并同source、同birth、sequence连续的项；不能跨出生机会随意合并。

在前述两个reasoning分层点，Qwen的72,479个累计入队记录单位可由2,514个
创建span表达，Llama的110,922个单位对应3,648个span，分别约28.83和30.41项/
创建span。最终均排空；同时存活的单head span峰值分别24、34，不能把累计
创建数当成同时存储容量，也不能把项/span比例当成物理metadata压缩倍数。

每次activation、append、dequeue后均检查集合、birth/order、source和最老项；
只保留source总数的负对照被“旧shared、新private”反例拒绝。来源：
[span表示充分性及负对照](../experiments/route_a4680_pending_representation_sufficiency_remote_replica_01/a4680_pending_representation_sufficiency_report.json)。

A4.6.8.1—4.6.8.2.1再记录创建、更新、选择、释放及有序检查点，保留仍存活span
的右删失生命周期，分离activation、append、dequeue。只保留总事件数不足以
判断访问集中度；logical checkpoint也不是硬件周期。

A4.6.8.2.2把非payload原语收敛成四类逻辑记录：

| 记录 | 主要职责 |
|---|---|
| frontier_control | 当前source头部/进度信息 |
| span_descriptor | span身份、剩余数量和生命周期 |
| ownership_link | span与owner/source的连接 |
| selection_control | 双源oldest选择所需信息，可选 |

只允许相邻、同一检查点和同一span的`partial_dequeue＋remaining_update`合并。
汇总记录操作从2,252,366降至1,936,987，少315,379（14.00%），payload-reference
创建/释放另外保留，不算K/V搬运。该汇总跨多个模型上下文，不是单请求访问量。
来源：[recordization结果](../experiments/route_a468220_metadata_recordization_remote_replica_01/a468220_metadata_recordization_report.json)。

**分析。** span给出了可验证的紧凑管理表示，仍没有选择descriptor宽度、存储宏
或物理端口。接下来要回答的，是多个记录能否并发更新，以及哪些更新必须一起
对外生效。

## 7. A4.7：从记录操作走到原子事务与可容纳的namespace

**目的与计划。** A4.7.0只加入预先声明的same-record、same-head-control、
span-lifecycle、ownership-order四类依赖，检查逻辑关键链和并行工作；这不等于
获得了硬件并行度或时序路径。

该阶段还区分“连续多个检查点有依赖”与“存在一条长的直接依赖链”，并保留
关键路径节点/边及其类型、checkpoint并行余量的min/P1/P5。高P95或平均并行
余量不能排除少量检查点串行；热点bucket、head偏斜与跨bucket fanout也不能
直接换算端口。由此才进入事务、锁和服务模型，而不是从访问总量直接选bank。
来源：[最终依赖/低尾观察](../experiments/route_a470_metadata_access_concurrency_remote_replica_02/a470_metadata_access_concurrency_report.json)。

A4.7.1将记录组成有唯一commit边界的事务：admission创建/连接、非终端dequeue、
终端dequeue/释放。要求所有成员完成后才可发布状态，避免读到半更新的归属。
tail extension虽被定义，实际观察计数为0，不得因接口存在便称已覆盖。

两个负对照说明原子边界为何必要：只完成admission的span写入，会出现没有
ownership link的pending；先释放span而未更新其他记录，会留下指向已释放span
的owner/frontier。来源：[事务与原子性结果](../experiments/route_a471_metadata_transaction_contract_remote_replica_01/a471_metadata_transaction_contract_report.json)。

A4.7.2接着区分per-head/per-layer/global namespace、从不复用与terminal commit
后复用、generation位和无效编码。`peak live`只有配合明确复用规则才足以讨论
slot宽度；不能直接给仍会迟到的引用分配过小编号。布局合并也只发生在既有
事务内部，保留单一commit和直接frontier比较键。

**结果与分析。** 某个上下文的最大metadata位数不能直接作为统一固定配置。
后续采用最大字段宽度与最大对象数量组合成跨上下文保守界；该界的成本可能
大于任一个单独上下文。A4.9.0保存了修正后的joint-safe参考及来源，避免把
旧的逐context峰值替换为固定provision。来源：
[最终metadata包络](../experiments/route_a490_eager_rmw_envelope_03/a490_eager_rmw_envelope_report.json)。

## 8. A4.8：到底是结构依赖，还是服务不足把等待传下去了

**目的与计划。** 将固定事务放入有依赖和commit的服务重放，保留无限服务对照，
再比较因果服务与固定q={1,2,4,8,16}。分开记录`B_ready`和`B_dep`：前者已满足
前驱，只等服务；后者仍在等前驱。某事务今天等前驱，可能源于前驱早先遇到
RMW服务不足，不能把所有即时dependency计数都解释成不可消除的结构串行。

例如Llama reasoning、horizon62、hierarchical q128、head-affine八bucket的因果
重放中，即时dependency阻塞观察有1,088,489次；沿canonical root追踪，RMW
shortage传播的依赖深度最大109。次数是重复观察，不是独立事务数量，root追踪
也不是完整硬件因果图。来源：[readiness与根因传播](../experiments/route_a481a_readiness_root_cause_01/a481a_readiness_root_cause_report.json)。

### 8.1 提高声明服务量，能排空但不能据此选择物理端口

以下汇总固定eager-RMW模板的336个context/profile组合。模型上下文来自多个
workload、horizon和组织变体，336不是独立请求数。停止到达后最多再给512个
逻辑机会；未排空表示在该界内删失，不等于数学上永远不能排空。

| 固定metadata服务q | 界内排空组合数 | 删失组合数 | 最大额外drain机会 |
|---|---:|---:|---:|
| 1 | 0 | 336 | 512（达到观察上限） |
| 2 | 319 | 17 | 512（部分达到上限） |
| 4 | 336 | 0 | 301 |
| 8 | 336 | 0 | 89 |
| 16 | 336 | 0 | 15 |

**分析。** 服务量确实影响积压，q=4在所覆盖轨迹上能有限排空；同时它仍可能
留下较长尾部。这个q是每逻辑机会、每模型bank/operation的声明量，不是每周期
端口数，不能直接选“4路SRAM”。来源：
[固定服务重放及原模板复现](../experiments/route_a482b_contract_simplification_replay_01/a482b_contract_simplification_replay_report.json)。

### 8.2 重要负结果：把RMW拆成读＋写没有消除成本

A4.8.2只接受同record read＋write的等价展开，写在原commit发布；中间仍需
commit exclusion，不能引入未计价的shadow/version selector。下表的工作按事务
内每条记录的访问集合计量，与§6逐原语recordization口径不同，不能相减当作
另一项优化收益。比较结果如下：

| 对照 | eager RMW | 同record读＋写 |
|---|---:|---:|
| 唯一context汇总的metadata记录工作 | 1,398,341 | 2,029,099（＋45.11%） |
| q=2界内排空组合数 | 319/336 | 252/336 |
| q=4最大额外drain机会 | 301 | 456 |
| q=8最大额外drain机会 | 89 | 166 |
| q=16最大额外drain机会 | 15 | 28 |

没有新增语义record类型，但额外读写和互斥义务仍然存在；所测点上并未获得
预期的排空改善。因此结束这条语义改写支线，保留eager-RMW进入候选实现与
成本研究。来源：[RMW拆分的最终对照](../experiments/route_a482b_contract_simplification_replay_01/a482b_contract_simplification_replay_report.json)。

## 9. A4.9—A4.10：有限metadata包络、执行粒度与队列合同

**代码与依赖。** [A4.9.1候选模型](../../tools/simulate_kvzap_route_a491_candidate_metadata_engine.py)
定义布局和服务候选；[A4.9.2记录级模型](../../tools/simulate_kvzap_route_a492_record_granular_engine.py)
沿用这些候选，将事务拆成 `MicroOp` 并重放记录锁、端口和单一commit；
[A4.10队列模型](../../tools/simulate_kvzap_route_a410_queue_contract.py)再复用候选和
micro-op构造，模拟local/shared/staging队列、credit与排空。三者均是轨迹上的
离散模型，模型坐标不等同于实际硬件时钟。

这些文件虽带阶段号，当前仍互相导入：A4.10还被A4.12/A4.14工作负载计价
使用，不能将它们当作互不相关的历史启动脚本直接删除。A4.6—A4.8中供这些
模型使用的事务、bank和依赖计算也应保留；其他旧参数扫描是否退役，需先检查
具体导入和是否要重算对应结论，不能只按文件名划分。

### 9.1 先建立可计数的状态，再声明执行模型

A4.9.0检查joint-safe持久metadata、每原子组临时commit/exclusion状态和fanout
在覆盖轨迹中有限。reasoning的112个context/profile组合在q=4下均于既定512
机会继续段内排空，最大额外drain301。这是有限轨迹结论，不是任意未来的界。

A4.9.1选择一个明确候选布局作执行DSE：per-head namespace、terminal commit后
复用、generation=0；joint-safe raw字段为43,975 bit，64-bit对齐后是53,696 bit，
来自225个head-control对象和614个span-owner对象，各对齐64 bit。generation=0
只是该模型选项，不能替代生产RTL的防stale-generation义务。

候选在whole-bank执行中把一个原子组涉及的bank保留至该组完成。结果为：

| 声明候选 | 模型bank数 | R/W/RMW能力 | 界内排空context数 | 发生queue溢出观察的context数 |
|---|---:|---|---:|---:|
| HA4-base | 4 | 1/1/1 | 137/168 | 168/168 |
| HA8-base | 8 | 1/1/1 | 168/168 | 168/168 |
| HA8-wide | 8 | 2/2/2 | 168/168 | 168/168 |
| ST8-base | 8，object-striped | 1/1/1，单commit slot | 43/168 | 168/168 |

队列按每bank32组观察溢出，工作仍保留而未丢弃；“最终排空”不能代替“有限
队列足够”。2/2/2是声明服务能力，不代表已经有2R2W SRAM和两条物理RMW lane。
53,696 bit也不含完整pending payload、事务队列或实现外围。来源：
[A4.9.1候选模型与结果](../experiments/route_a491_candidate_metadata_engine_02/a491_candidate_metadata_engine_report.json)。

### 9.2 A4.9.2：内部交错能改善服务，但未消除队列问题

A4.9.2把比较轴收窄为whole-bank与record-granular：允许不同组的内部记录操作
交错，但同record锁保持到原子组commit，前驱释放和对外可见性仍由原commit
决定；不再改FIFO、ownership、RMW模板或增加第三种语义变体。

原始汇总有4候选×168个context，共672行。与原whole-bank基线比较：

| 候选 | Whole-bank界内排空 | Record-granular界内排空 | Record-granular仍观察到queue溢出 | 两者均排空时的服务坐标差范围 |
|---|---:|---:|---:|---:|
| HA4-base | 137/168 | 147/168 | 168/168 | −734…−118 |
| HA8-base | 168/168 | 168/168 | 168/168 | −623…−69 |
| HA8-wide | 168/168 | 168/168 | 168/168 | −626…−69 |
| ST8-base | 43/168 | 161/168 | 168/168 | −3,197…−1,865 |

差为record-granular减whole-bank的声明服务坐标；只比较两者均在界内排空的
样本，不拿删失端点算加速。其负号说明保守的整bank占用确有可释放的内部并行
机会，但168/168的溢出观察继续存在。ST8显著改善也仍有7个context未在界内
排空，不能宣布所有映射都已解决。这里没有测面积、物理cycle或硬件加速。

### 9.3 A4.10：有限队列须交代工作留在哪里

A4.10随后固定HA8-wide主点、HA8-base对照和record-granular执行，比较bank-local、
local＋layer-shared overflow、有限shared/staging及lossless credit。队列满时
延迟接收并持有工作，不通过丢弃、改grant或默认Full-KV回退来清空。

对HA8-base/HA8-wide各168个context，三种组织都最终完成全部事务、末态残留0。
但“排空”背后的存储/背压责任不同：

| 候选 | local32之后的组织 | 界内排空 | 有背压的context | 最大layer-shared / staging占用 | 最大外部held事务 |
|---|---|---:|---:|---:|---:|
| HA8-base | shared无界参照 | 168/168 | 0/168 | 719 / 0 | 0 |
| HA8-base | shared256＋credit | 168/168 | 70/168 | 256 / 0 | 2,173 |
| HA8-base | shared256＋staging512＋credit | 168/168 | 0/168 | 256 / 463 | 0 |
| HA8-wide | shared无界参照 | 168/168 | 0/168 | 719 / 0 | 0 |
| HA8-wide | shared256＋credit | 168/168 | 70/168 | 256 / 0 | 2,170 |
| HA8-wide | shared256＋staging512＋credit | 168/168 | 0/168 | 256 / 463 | 0 |

local按bank，shared/staging峰值按layer，held是重放中全部被暂缓接收的事务
高水位；各列独立取最大值，不代表同一时刻。只有shared256时，多出的工作
留在模型的外部held集合，需要生产者可保持数据或可背压的真实合同，不能当作
工作消失或“总共只需256项”。加staging512后，本次覆盖峰值463且held为0，
提供了有限候选的依据，仍不是任意流量的容量保证。

队列组织也有模型代价：相对A4.9.2基线，HA8-base/HA8-wide增加的服务坐标
最大分别528/380，不能只报无损排空而省略接收、搬移与仲裁的工作。两候选的
168行及三种组织是同批context的对照，不是1,008个独立请求。

最终被下游成本研究继承的合同为`local32/shared256/staging512`：local按bank、
shared/staging按layer，条目属于metadata工作队列。这里staging512不是P3 payload
的512个fragment，也不是admission budget512。继承关系可直接检查：
[现有A4.14.0冻结输入副本](../experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4140_source.json)。

### 9.4 找回的原始结果与仍有的资料边界

2026-11-12在`algorithm`主机的既有项目找到两份complete JSON，根目录为
`/home/myserver/workplace1/zsy/zsy_2/kvpress/analysis/experiments/`：

- `route_a492_record_granular_engine_01/a492_record_granular_engine_report.json`。
- `route_a410_queue_staging_credit_contract_04/a410_queue_staging_credit_contract_report.json`。

A4.10与本地A4.14.0登记的冻结输入一致，并且其上游摘要与找到的A4.9.2一致；
远程A4.12.0和A4.14.0中的A4.10输入副本也与原件一致。上表直接汇总原JSON，
核对了schema、complete状态、semantic guards和完成计数；没有重新运行模拟。
可结合[record-granular实现](../../tools/simulate_kvzap_route_a492_record_granular_engine.py)、
[queue/credit实现](../../tools/simulate_kvzap_route_a410_queue_contract.py)检查计数定义。

**本地仍缺这两份独立汇总及A4.10输入副本，本轮未同步，也未验收全部上游
原始trace。** 因而从“独立结果未找到”更新为“结果已在远程核验、本地副本
缺失”，不能升级成完整离线复现链已恢复。资料位置在本文给出，阅读研究结论
无需跳转旧计划或交接；后续清理仍须保全远程原件和未同步的输入。

## 10. 这一阶段最终证明什么，哪些问题仍留到后面

本阶段把“pending看起来很多”推进为一条可检查的管理路径：

```text
明确到达和服务 → 固定轨迹比较容量组织 → 保存不可变归属和FIFO
→ 用span表达 → 显式记录访问与依赖 → 原子commit与安全复用
→ 声明执行及lossless队列合同 → 等待真实存储、外围与成本核算
```

应保留的结论是：共享能在覆盖轨迹上回收逻辑容量；span表示需要birth/order；
原子commit有实际语义理由；服务不足会通过依赖传播；RMW拆分增加工作并恶化
所测排空结果；有界排空和队列容量充足需要分别检查。

仍未证明的是完整物理容量、真实并发端口、周期与能量、所有请求的持续稳定性，
以及保留Full-KV回退的净成本。这些模型的head/span metadata也不等于后来RTL
的R3 compact admission关联表，不能用53,696 bit直接作为后者应有的容量或
面积预算。算法mask与grant被冻结，不意味着后续表示和物理实现自动经济。

本文保持一份正文，关键表直接来自已有JSON。未来可以用原始按context/phase
数据重绘容量前沿、服务/drain曲线和热点分布；正文中的累计事件数不能替代
唯一原始轨迹。已读取关键汇总和相关脚本，未重算全部原始trace或传递依赖。
没有移动、覆盖或删除原始资料。

下一份R6承接的是成本问题：把明确的metadata、payload、队列和外部服务按
统一比较口径计账，检查剩余收益，并区分已计价、声明假设和仍遗漏的部分。
