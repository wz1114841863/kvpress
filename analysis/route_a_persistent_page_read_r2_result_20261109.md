# 持久页读取 r2：有界功能验收通过 — 2026-11-09

**结论：本轮范围内的v2持久页重复读取、错误拒绝/恢复及指定retire排空通过。** 真实父级短测1项＋完整阶段14项，共7 suites／15项native测试全部成功；compile/parent/test/runner/tmux五层退出均0。该结论不包含多组admission、数值对应、全32K/并发、external-v2、2ns或增量成本闭合。

本轮按用户完成通知只读核验[冻结r2](route_a_persistent_page_read_r2_launch_20261109.md)，不修改RTL/输入，不重放native或运行DC/STA。[JSON证据](route_a_persistent_page_read_r2_result_20261109.json)保存fresh最终严格核验、独立复核、原生报告/ELF/log的hash和逐场景结果。r1失败记录继续保留。

## 1. 执行与输入/产物闭合

| 项目 | 已核实结果 |
|---|---|
| run | `persistent_page_read_v2_20261109_r2` |
| source | `40a74b6a259afaaf6aac8efcb7a6c01fb271862a` |
| archive SHA-256 | `e7a65e92cf22c9c4ab620d3094c94c05b21b6874a8e5d8d053da3196e7a293ee` |
| source闭合 | 155份source的hash/bytes、manifest、archive重新核验；与当前checkout对应源文件一致 |
| native闭合 | 7份XML、15个真实ELF、各自compile log/execution script/simulation log均核验，0 fail/error/skip |
| parent gate | 独立1/1 PASS，snapshot在后续14项之后仍完全一致，未被重建覆盖 |
| 五层退出 | compile／parent／test／runner／tmux＝**0／0／0／0／0** |
| markers | r2 RUN_PASS、parent gate、runner exit0、tmux exit0均恰一次 |
| 完整阶段 | 14/14，约44分40秒；2026-11-09 16:07:50完成；加parent共15/15 |
| 进程 | pane14445仅为保留的bash，无运行子孙任务 |

执行归档checker的`check(root, require_outer=True)`，直接输出stdout进行只读复核，不写远程result_final。fresh结果与runner保存的result.json除新增final outer证据外一致；独立audit得到同一结论。simulation-log可为空，实际执行由原生ELF、非空execution-script、XML及typed观察共同核验，未把空日志误当作没运行。

| 测试层次 | 数量 | 本轮结果 |
|---|---:|---|
| v2完整DUT | 3 | 同页两读、错误/恢复、retire交错全部PASS |
| 真实R5父级＋原owner/controller/R6 | 6 | mark/query/query、共享扫描交错、背压、generation/取消等定向PASS |
| default-v1 R3功能回归 | 4 | 原first-use、hot、fault、withdrawal回归PASS |
| default-v1旧诊断 | 2 | 仍复现READ_REUSE/ADMISSION_REUSE两个预期BLOCKED；测试PASS不代表v1获得新能力 |

## 2. 同页两读：一次打包，两个真实服务

[测试源](../hardware/route_a/chisel/src/test/scala/kvpress/routea/RouteAPersistentPageReadSpec.scala#L319)没有中途reset、内部force、第二次publication或重新preload packed payload。仅原pending对象预载；packed对象来自真实R1写入。第二次沿用R5 canonical handle，每个返回fragment都核对原数据。

SAME_PAGE_TWICE的实际观察：

| 事实 | 结果 |
|---|---:|
| 实际packed payload write commit | 1 |
| publication／post-R6 ready通知 | 各1 |
| 两次payload fill fragments | 16（每次8） |
| sidecar fragments | 2 |
| consumer commits／source releases／成功terminals | 8／2／2 |
| 两次服务的PageRef | 同一page0／page generation0 |
| 同一S2 slot的source generation | 1→2 |
| 最终retire／reclaim | 均完成；descriptor不可读、allocation释放、R6 Retired |

这证明持久资格不再依赖一次性publication/member事实：R5可以为仍存活的同页提供新的读取事实，S2每次建立、消费并释放独立服务实例。它不代表退休后page generation仍为0；该数值表示两次服务使用的原PageRef，回收后的安全重新分配未在此whole-DUT witness证明。

## 3. 错误路径与恢复

错误suite先完成真实首次正向服务，再依次发送：错误PageRef generation、错误attention owner、非法S2 slot、错误S2 next-generation。**每项恰一个真实fault terminal**；没有新增read、consumer commit或source release，S2没有残留live slot，下一合法generation仍为2。

foreign declaration没有对应live attention，仅有一次local rejection，**没有制造attention terminal**。随后合法generation2服务再次完成并成功退休，验证错误后能够恢复，而不是只观察到拒绝后停止测试。详细检查见[错误场景](../hardware/route_a/chisel/src/test/scala/kvpress/routea/RouteAPersistentPageReadSpec.scala#L423)。

## 4. retire期间完成已接受工作

[retire场景](../hardware/route_a/chisel/src/test/scala/kvpress/routea/RouteAPersistentPageReadSpec.scala#L480)在首次服务后，先接受第二个attention及declaration，但暂不提供selector，确认S2尚空。此时实际接受runtime retire，进入Retiring；16周期内页保持live，不能提前retire ACK。

之后补入原attention的selector，完成第二次实际fill、四消费者和terminal；最后才完成descriptor失效、allocator释放和一次retire ACK。RETIRE_DURING_PREFLIGHT记录同样有一次write/publication、两次服务、8 commits、2 releases、2成功terminals且无memory fault。v2的前端停止/在途工作完成/transport drain分期在该切点具备动态证据。

该验证限于**已发布页、attention/declaration已接受、selector尚缺**的切点，不覆盖任意partial admission退休、全部lease/cancel切点或无界environment stall。

## 5. r1缺陷的修复验收与保留边界

真实R5父级短测验证mark后连续两次query成功，第二次与实际scanner outstanding握手交错，结果背压4周期保持，始终不残留ghost scanner work。完整DUT首次服务及第二次服务均通过，r1共同的首次R5查询阻断不再复现。父级typed R3/R1事实仍是明确unit环境，完整DUT提供独立真实owner集成证据。

本次验收对象是**显式开启persistentReadEnabled的有界production-v2实例**，默认v1/通用wrapper保持原行为。仍须保留：

- small fixture：allocator8、stream16、source/tag/stage generation2bit、handle32bit；单有效record的partial tail、packed-only顺序attention；非full32K、满并发或wrap验证。
- `gateCompactMembershipWords=false`；不把本轮称为WCG1 full-anchor动态验收。
- position sidecar backing由环境在首次canonical grant后写入真实R3 position；不是已实现的硬件sidecar写服务。partial/R4仍是固定协议包，`numeric_correspondence=0`，未建立Q/K/V数值对应。
- external descriptor backing及其已登记的service-owner风险、完整mixed-source、持续pending owner生命周期仍OPEN。
- 多组admission/journal未修改；旧v1诊断仍BLOCKED。阶段A的重复读取项通过本次范围验收，**阶段A总体尚未完成**。
- 未进行DC/STA、宏实现或完整增量成本核算；没有新面积、setup/hold、能量、系统加速或净收益结论。

本轮收口结果检查与live文档，不自动进入多组admission实现或新综合。下一项功能工作仍需先明确跨组journal历史寿命与资源复用合同，再独立验证。
