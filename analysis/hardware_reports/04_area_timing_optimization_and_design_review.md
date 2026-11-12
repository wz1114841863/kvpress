# H4：面积／时序优化与设计复盘

整理日期：2026-11-12。本文承接[H1](01_architecture_and_software_hardware_boundaries.md)、
[H2](02_rtl_implementation_and_sustained_execution_scope.md)与
[H3](03_storage_measurement_boundary_and_complete_cost.md)，按目的、方案、结果和分析串起
2026-10-29首轮DC至11-09 RD1＋WCG1的优化。不重跑仿真、DC或STA，不修改RTL，
不重新验收远程制品；以下数值来自已有结果记录。工具启动、重试和哈希过程不展开。

**完整顶层已经验证四类面积改善：metadata bridge去重、compact membership、RD1共享
读取、WCG1共享字门控。最后primary控制面积比从约290.87×降至129.52×，累计减少
55.47%，但setup仍失败。PM1小幅省面积却使setup变差，RD2隔离映射无净面积收益，
ST1简单替代没有通用等价资格，均不能列成已集成成功。** 面积下降没有同时证明持续
功能、存储宏、完整成本、物理PPA或系统净收益。

## 1. 目的与比较方式：在相同条件下定位真实成本

首轮DC的目标是检查控制实现能否综合、热点在哪里，而非直接评定芯片净收益。
后续保留同一fair-v1口径：同TSMC28候选库，周期2 ns，setup/hold uncertainty
0.10/0.02 ns，I/O delay各0.20 ns，transition0.05 ns，load0.005 pF，reset正常计时，
不加false/multicycle例外。Full-KV不为改善比值而扩大，真实父级控制不黑盒化。

M2/P3/R5/S2数组内部仍用typed代理，外部memory、descriptor、partial/R4等仍需计价。
因此以下面积单位均为**library cell-area units**，不是mm²物理core面积；比较范围是
控制投影。各次功能回归、局部等价/筛查和完整顶层映射也分别记账，不能互相替代。

Primary比较中Full-KV面积持续复现23,091.432498。主线及一个独立分支如下：

| 顶层快照 | Route-A cell area | 本次相对谁、降低多少 | / Full-KV | Setup WNS(ns) |
|---|---:|---|---:|---:|
| 原始r5desc基线 | 6,716,537.642416 | 起点 | 290.867× | −0.31 |
| Metadata bridge去重 | 3,952,935.893452 | 原始基线，41.146% | 171.186× | −0.33 |
| Compact＋entry_id修复 | 3,622,375.558791 | Bridge后，8.362% | 156.871× | −0.31 |
| RD1 | 3,388,597.345862 | Compact修复后，6.454% | 146.747× | −0.36 |
| RD1＋PM1（分支） | 3,358,045.877079 | RD1，0.901596% | 145.424× | −0.44 |
| RD1＋WCG1（最后主线） | 2,990,737.008920 | RD1，11.741151% | 129.517× | −0.469940 |

前五行WNS按原记录两位小数呈现；最后一行有六位精度。PM1没有进入WCG1最终输入，
RD2也未集成；WCG1的11.74%不能再算成“在RD1＋PM1上降低”。Entry_id修复不是
第五项独立面积优化，各项百分比也不能直接相加成累计降幅。

## 2. 原始诊断：先确定大在哪里，而不是盲目改selector

**目的与方案。** 从原始DDC、mapped HDL和层次报告定位状态与组合网络，而不从
Chisel代码长短推测成本。原始Route-A有1,298,150个mapped sequential cells；
M2/P3 wrapper与metadata bridge分别占面积约44.2%、42.2%，合计86.4%。

**结果。** Bridge独立保存`36×64×281=647,424 bit`完整pending binding，但R3/P3
已有该事实，M2只需要组、成员mask与mapping provenance。Wrapper也保存宽成员记录，
其中有可从坐标/组头恢复的字段。由此先选状态表示去重，再考虑读取和选择网络。

另一个易误判点是报告中挂在`directPendingIssue`名下的约130万负载网络。保存DDC
查询确认它是编译器临时clock alias，负载数恰为sequential cells＋4，不是一个pending
事务字段广播给130万个语义消费者。对direct carrier加寄存器不能解决这个根因。

**分析。** 第一轮热点有明确重复表示，适合不改功能的局部优化；巨大面积不全是
布尔逻辑难优化。同时，时钟负载与lint需要追到真实对象，不能仅按临时网络名或warning
总数选择修改。原始约291×只暴露控制实现问题，不是完整系统面积比。

## 3. Bridge去重：第一项、也是最大的完整面积改善

**目的与方案。** 删除metadata bridge的完整重复binding ledger，改为每组保留不可变
mapping reference、owner与accepted-member mask。R3/P3仍保存完整成员；M2继续
校验它真正消费的字段与组一致性，错误mapping不能通过prepare。

**结果。** 定向8/8、完整父级4/4及跨阶段41/41等既有检查通过，之后进入同约束DC。
Raw generated bridge由662,504 bit降到17,492 bit，少645,012 bit；mapped顶层也减少
645,012个sequential cells，从1,298,150降至653,138。该次两者恰好相等，不是通用换算律。

Bridge层次面积由2,835,164.2069降到85,832.8811；顶层降低41.146%。Clock alias
负载由1,298,154降至653,142。Warning记录由56,677降至44,513，主要消除了M2不使用
完整binding所带来的大量未连接字段。

**分析。** 这项优化有清晰因果：重复状态与其读取/传递网络被移除，完整映射证实了收益。
但是WNS由−0.31变−0.33 ns，TNS由−7,318.06变−7,891.18 ns；setup没有改善。
面积、clock直接负载和部分lint下降，不能推导等比例功耗或时序收益。

## 4. Compact membership与entry_id：压缩记录后仍须检查映射接口

**目的与方案。** 对wrapper的两套宽记录去除可恢复字段：member只留position与
payload_ref共79 bit；suffix只留identity、handle、source generation和endpoint共80 bit。
Layer/head等来自组头或索引，entry_id由原坐标公式重建；必要成员和绑定信息不删。

**结果。** 既有57/57功能检查通过，raw wrapper状态从990,322降至400,498 bit，少
589,824 bit。但DC早已删除大量不用的原字段，实际mapped sequential只再减少76,032，
顶层变为577,106。初次compact面积为3,624,318.814461，出现entry_id输出失驱动，
因此保留为诊断快照，不能直接当结构闭合结果。

Raw HDL有重建驱动，mapped层次却只剩output alias；下游实际逻辑没有消费完整entry_id
重建锥。随后仅增加定向综合驱动保留策略，功能RTL和接口不变，48个输出bit均恢复真实
driver，LINT-3/LINT-5归零。修复后面积3,622,375.558791，相对bridge后省8.362%。
它比未修复结果小约0.054%，属于映射变化，不计作另一项优化。

**分析。** 这一步证明“源码少了多少bit”不能直接当面积收益；综合前功能通过也不能
替代mapped接口检查。修复后wrapper仍占顶层约72.8%，WNS约−0.31 ns，TNS与违例
数量比bridge后更差。两张compact表仍保留366,336 bit，其中两个独立64-bit字段占80.5%。

## 5. RD1与RD2：共享合法访问有效，改写选择器表达式未必有效

### RD1：先证明哪些消费者真的可以共享

**目的与方案。** 逐个列出materialized work(M)、sidecar(S)、publication/authority(O)
及校验C/F/B的读口和并发。在同一bank，M/S分属materializer未激活/已激活阶段，O又
属于观察阶段，因此M/S/O可以共用一次member读取；不同bank仍可同时服务。
C/F/B与两路suffix读保持独立，不新增仲裁、寄存器、延迟或ready/fire依赖。

**结果。** 局部miter覆盖全部6,912消费者/地址选择及随机跨bank并发、held请求、写入
边沿等。隔离纯组合读取网络面积342,379.460369→126,874.772938，省62.943%，
但setup slack从+1.121480降至+1.065261 ns，增加约56 ps延迟，仍通过该隔离约束。

完整paired DC只省顶层6.454%，wrapper约省9.502%；组合面积下降15.119%，
577,106个sequential cells与577,110个clock直接负载不变。顶层WNS−0.31→−0.36 ns，
TNS−8,577.41→−9,774.02 ns。主线保留RD1为已验证面积候选，同时保留其setup代价。

**分析。** 合法互斥可以减少重复读取网络，但不能将隔离62.94%当完整wrapper或顶层
收益。共享前的索引选择本身也有延迟；省面积不等于关键链变短。

### RD2：布尔网络更小，额外极性和驱动成本抵消收益

**目的与方案。** 两侧都保留RD1，针对剩余独立读口改用共享ordinal decode与分级
Mux1H，保持C/F/B及suffix读口并发和valid低时的原始读取可观察性。没有修改production
wrapper，先做4×8、36×64合法索引miter和隔离映射。

**结果。** 隔离total cell area由689,972.294920增至692,068.096534，**增加0.30375%**。
非buffer/inverter组合面积少60,167.69，但buffer/inverter多62,263.49；candidate出现
171,761个inverter，其中大部分直接接数据输入，符合AOI/OAI映射引入极性成本的结构。
最坏setup slack+1.046292→+1.026872 ns，增加19.42 ps逻辑延迟；两侧仍无该隔离
setup/hold违例，但最坏路径位于共有M/S/O网络，不能断言每个修改读口都变慢。

**分析。** RD2是有效执行后得到的负面积结果，未集成，也没有更新完整Route-A比值。
它不证明所有decoded读取都无效；也没有证明纯fanout膨胀是唯一原因。当前局部等价
只覆盖合法索引，out-of-range与完整连续ready范围仍待处理。更短代码/显式decode
不保证该库下更小电路。WR1写译码仍是研究方向，没有独立完整收益或负结果可记。

## 6. PM1：准确的优先选择，取得小面积收益却增加时序风险

**目的与方案。** Page Manager只读P0定位到36,720个`allocatedLine`状态及其大reclaim
选择锥。PM1保留全部bit和精确最低索引，用574个64-entry bank先求局部结果，再选
最低非空bank及其offset；末bank补零。无新增生产流水级、扫描周期或回收顺序变化。

**结果。** 先用8,192个小域全向量和全尺寸one-hot/边界/随机检查验证选择函数，连空
输入原有terminal index约定也保留。早期孤立selector映射未形成完整可比结果，后续改用
真实父级、已有DDC上下文characterization/replacement；不能将失败工具运行当性能负例。

有效bottom-up筛查：Page Manager面积407,451.238597→390,334.056566，省4.201%；
重连旧top仅省0.473%，setup WNS不变，出现一个约−0.01 ns hold违例。后续完整
RD1＋PM1映射顶层省0.901596%，Page Manager省约4.243%，状态数不变；但WNS
−0.36→−0.44 ns、TNS绝对值增加23.76%。Primary hold无违例，不能据此抹去隔离
上下文的hold负结果；两次上下文与映射不同。

**诊断与分析。** Saved-DDC STA比较同16个reclaimLine寄存器端点，最坏slack
−0.348932→−0.439257 ns，损失90.325 ps，正延迟组合输出arc数107→147。
“Bank priority编码后，再用该索引从574个局部offset中选一个”仍形成长链，banked
并未自动得到浅层平衡树。这是已确认的局部时序退化。

全顶层新增TNS绝对值2,322.58 ns中，按端点归属PM占4.12%、其他占95.88%。
后者是端点记账，不能证明其因果独立于PM1。Common sidecar READY路径不进入PM，
但同样变差；其结构仍是原跨owner组合链，cell sizing/映射变化与退化相符，未隔离出
DC优化策略的精确因果，不能笼统称为随机波动。

PM1因小面积收益伴随确认的selector退化，未纳入WCG1最终基线。平衡`{valid,index}`
树是待测修复候选，没有实现收益可填；修好PM1也不等于修好其他控制链。

## 7. STORE/ST1与WCG1：从删信息转向降低同样信息的保存成本

**目的与方案。** 热点归因确认compact表与其读网络占wrapper大部。STORE审计继续
检查两个opaque64能否缩短、能否复用journal。旧合同缺少对齐/范围/可推导保证；简单
ST1用全局journal代替按bank suffix，又需要通用caller未承诺的ordinal不复用范围。
因此没有直接删除大表。反向复用journal最多涉及5,120 bit且新增读取有成本，异步RF
也未有匹配实现。它们是范围/实现尚未闭合的候选，不是已测出的新面积收益。

WCG1则保留全容量、字段、组合读和握手，把每bit enabled-DFF改为普通DFF，每条
79/80-bit word共享一个真实门控单元；member与suffix仍用独立写使能，不能用裸
`clock & enable`或混合使能代替。Enable边沿、reset、旧数据保持和实际时钟arc需分别验证。

**分层结果。** 各层测量包含的shell/控制及映射策略不同，不能乘36或叠加百分比：

| 范围 | 已验收面积结果 | 时序与功能边界 |
|---|---|---|
| 同容量单bank | Matched hold修复后省16.5262% | Raw hold最差−0.017921 ns、9,992违例；修复成本计入后setup/hold通过，hold余量仅3.529 ps |
| 真实wrapper功能 | Reference4/4＋candidate4/4，共8/8定向通过 | 比较真实wrapper输出/握手和边沿行为；不是全输入形式等价 |
| 真实wrapper隔离映射 | Matched hold-pass面积2,295,026.201759→1,936,432.671921，省15.624812% | Native gate绑定闭合，2 ns下setup/hold无违例，但candidate最差setup恰0，没有正余量 |
| 完整RD1＋WCG1 primary | 顶层省11.741151%，wrapper省15.492059% | 顶层setup仍失败且变差，不能沿用隔离通过的结论 |

**完整映射证据。** 实际保留366,336个普通table DFF和4,608个native gate，两个64-bit
字段及全部容量不变；gate test-enable真实tie低，48个entry_id bit都有driver。
顶层noncombinational面积下降19.324%，组合面积仅下降0.868%；总sequential cells
由577,106增至581,714，是gate内部latch被计入，不是增加了4,608条KV状态。

Root直接fanout577,110→215,382，减少361,728，恰为366,336−4,608。数据flop
时钟负载移到gate后面，叶负载与下游网络仍在；没有测得同幅clock power/电容或CTS收益。
这是降低每bit实现成本的真实面积结果，没有解决信息与访问接口本身的规模。

## 8. 最后STA与结构结果：局部通过为何没有变成顶层通过

最后WCG1流程分别保留原ideal-clock primary及两侧匹配的propagated/hold补充结果。
Full-KV primary面积不变且setup/hold无违例；补充策略不得与历史primary混着比较。

| Route-A测量层次 | Setup slack(ns) | Setup TNS(ns) / 违例数 | Hold slack(ns) / 违例数 |
|---|---:|---:|---:|
| Primary | −0.469940 | −12,698.75 / 36,017 | +0.005394 / 0 |
| Propagated raw | −0.482178 | −12,912.35 / 36,021 | +0.006092 / 0 |
| Propagated hold pass后 | −0.575940 | −12,713.58 / 34,624 | −0.034459 / 825 |

Primary相对RD1的TNS绝对值恶化29.92%。最坏路径从arbiter关联generation寄存器到
sidecar-read-issue READY；样本不经过native gate，gate enable局部setup/hold为正。
这不证明WCG1对全局映射没有间接影响，只说明不能把全部时序失败归为gate自身未通过。

已诊断的sidecar READY链跨越arbiter→coreMemory→arbiter→readIngress→
packedReadIngress→packedSidecarIssue；另有stageValidRecords到registry-allocate
READY的关键链，以及PM reclaim selector。这些是握手/资格/分配判断跨模块组合传播的
实现问题，单独减少存储bit或某个读取网络没有切断整条依赖。

补充hold pass之后两侧均出现负hold，Route-A setup也进一步变差。目录名中的
“hold_repaired”只表示执行了pass，不表示验收通过。同tier面积比虽降到119.016×，
但Route-A面积实际增加0.971%，Full-KV增加9.880%，是分母增长更快；不能列成另一项
WCG1节省，更不能当作有效的时序闭合实现。

结构方面，bridge曾显著减少lint，但最后primary Warning记录仍44,552，比RD1多16。
Entry_id特定driver问题已闭合；typed未用字段、feedthrough、shorted/constant outputs、
高fanout与min-capacitance仍在。没有unconstrained/missing-delay新问题，不等于整体
约束/结构clean；LINT计数也不能单独证明功能错误或授权删字段。

## 9. 设计复盘：为什么优化有效，瓶颈却一直存在

### 已提出但没有实施结果的结构候选

以下来自早期结构审查，保留探索线索，不升级为后续计划或已验证收益：

| 候选 | 当时想改什么 | 证据与边界 |
|---|---|---|
| SEL1 | 改进36个64-bit materializer候选mask、prefix和最低layer/ordinal选择 | 有stageValidRecords到ready的热点依据；没有新映射收益，不能与RD2重复记账 |
| RC1 | 按完整ordinal先读一条journal，再保留全部精确比较 | 需保持转权、同拍admission、已存记录、Unseen的优先级与高位范围检查；新增宽mux可能抵消收益 |
| MC1 | 优化M2的614-slot first-free与handoff匹配/更新 | 需先做mapped锥归因；36层不证明只需36个live slot，历史owner面积占比不是可节省比例 |
| PM2 | 从stream索引恢复layer/head，payload-durable事件做indexed查找 | 历史归因给出2,592个坐标寄存器、约8,128.5面积的状态上界，约旧顶层0.22%；比较网络收益未测 |
| EQ1 | 在M/C或S/B确实同地址时复用读取 | Production连接相等不能代替通用wrapper保证；要保留独立输入、非法/stale及fallback，可能反而增面积 |

这些候选与WR1及存储实现方向一起，说明尚有结构可以研究；没有证据表明它们能单独
解决当前整体差距。PM2也不同于已测PM1，不应把PM1负面时序结论移给未实施的PM2。

### 从实际优化结果得到的设计问题

**重复状态确实来自表示与职责实现。** Bridge去重与compact成功，证明早期宽记录复制
付出了可避免成本；这些面积不能视为KVzap算法的必然下界。但去重后剩余信息、访问口和
寿命成为主导，后续收益不应继续按第一轮41%外推。

**组合访问合同比“存多少bit”更限制存储实现。** Compact保留36×64及独立opaque值，
多个消费者要求即时读取，C/F/B还在valid低时影响ready。通用wrapper比当前一次/reset
生产入口宽，ST1遇到的正是两种范围不能混用。固定旧接口下换同步SRAM、缩成64条或
缩短历史，都需要额外保证，不能靠源码重写自动成立。

**模块职责明确，没有同时给出合理的顶层时序预算。** 正确性上分开的资格、传输和目录
判断在RTL中形成长组合链；PM1分bank仍有编码后大mux，RD2布尔化又带来逐bit极性成本。
这些例子说明抽象上“共享、分级、分bank”并不自动对应低延迟、低面积。

**局部筛查与完整集成的差异是真实研究结果。** RD1隔离省62.94%但顶层省6.45%，
WCG1隔离wrapper时序通过但顶层失败，PM1小收益伴随退化。周围未改源码的层次也会
因全局映射改变；必须比较最终实现，不能将各小实验最好的百分比拼成系统收益。

**功能范围和成本范围仍未对齐。** 本轮最后DC不含H2的后加持久页v2；多组admission、
pending周转和真实数据—数值连接未完成。H3所列数组、外围及外部服务仍缺价。当前
控制比受小Full-KV分母与昂贵Route-A分子共同影响，既不能直接代表整系统，也不能用
“分母小”解释掉分子；已有证据同样不能给算法、职责和RTL成本各分配一个可靠百分比。

因此，阶段结论分开保留：**四项完整面积改善已证实；PM1/RD2及hold-pass负结果保留；
统一2 ns setup/hold与广义结构清洁度未通过；PPA、持续decode性能和完整硬件净收益
未建立。** 这些结果为审查职责、接口、存储与端到端执行方式提供了依据，尚未证明某种
新的软硬件划分一定更优。本轮仅整理已有结论，没有确定新的职责划分或后续实验方案。

## 10. 原始结果入口

主线数据：[原始DC](../dc_feasibility_result_r5_descriptor_externalized_20261030.md)、
[状态诊断](../dc_control_realization_diagnosis_20261101.md)、
[Bridge结果](../dc_control_refinement_result_20261103.md)、
[Compact诊断结果](../dc_m2_p3_wrapper_compact_membership_result_20261104.md)、
[Entry_id修复](../dc_m2p3_entry_id_repair_result_20261105.md)、
[RD1完整结果](../dc_rd1_full_paired_dc_result_20261106.md)、
[RD1＋WCG1完整结果](../dc_rd1_wcg1_full_paired_result_20261109.md)。

局部与分支：[RD1访问/并发分析](../dc_compact_membership_read_sharing_plan_20261104.md)、
[RD1局部实现/筛查](../dc_rd1_member_read_sharing_implementation_20261104.md)、
[RD2负结果](../dc_rd2_read_screen_result_20261106.md)、
[PM1选择器](../dc_pm1_exact_priority_selector_implementation_20261104.md)、
[PM1 saved-DDC筛查](../dc_pm1_saved_ddc_validation_result_20261106.md)、
[RD1＋PM1完整结果](../dc_rd1_pm1_full_paired_result_20261107.md)、
[PM1/全局STA诊断](../dc_rd1_pm1_setup_diagnosis_result_20261107.md)、
[ST1范围结果](../dc_st1_scope_key_validation_result_20261106.md)、
[WCG1单bank结果](../dc_wcg1_saved_artifact_validation_result_20261106.md)、
[WCG1 wrapper功能](../dc_wcg1_wrapper_retry_result_20261106.md)和
[WCG1 wrapper映射/STA](../dc_wcg1_wrapper_mapping_retry_result_20261107.md)。
需要核查字段、存储和功能范围时读H1—H3；这些链接只用于追溯原始结果，不是另一套必读过程记录。
