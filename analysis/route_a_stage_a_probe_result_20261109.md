# 阶段 A 当前 RTL 两项连续执行探针：结果验收 — 2026-11-09

Run ID：`stage_a_continuation_probe_20261109_r1`。输入／启动依据：[launch](route_a_stage_a_probe_launch_20261109.md)；规范场景：[阶段A执行范围](route_a_stage_a_execution_envelope_20261109.md)。独立核验证据见 [JSON](route_a_stage_a_probe_result_20261109.json)。

**两个诊断正常完成，2/2测试通过；两项持续能力均在现有RTL中复现了具体阻断。** 通过的是“首轮正向前提成立后，准确复现128拍有界阻断”的诊断资格，不是同页两次读／两组admission功能通过。本轮只读验收，没有修改RTL、重启测试或运行DC／STA。

## 1. 工具、输入与制品闭合

- compile、test、runner outer、tmux wrapper四个持久退出状态全部0；实际input／compile／postcheck／diagnostic-run／outer markers逐行各出现一次。
- native ScalaTest XML为2 tests、0 failures、0 errors、0 skipped，两个testcase分别存在。两组`FIRST_USE_COMPLETE → PROBE_RESULT`顺序一致；没有将源码回显或setup/build异常认作阻断。
- 两个case的Verilator ELF各12,027,352 bytes，连各自compilation log／execution script／simulation log共8个native制品重哈希；两份simulation log为空而功能观察来自host-side测试日志，不能将空log本身当结果。
- 输入archive SHA-256仍为`e595ed19730dd393693589d7c884ba90eb1cd7febd1c03fd1d6fbb844bad8301`；source manifest、独立runner、tmux wrapper均与launch pins一致。140个workspace输入重新hash，全部对应冻结manifest和当前checkout；24个生产main文件同时对应`097533d`原内容。
- 重执行的仅是只读`check(root)`函数，结果与保存的`result.json`完全相同；关闭Python bytecode写入，不调用会写result的CLI，不加载仿真器／DDC。
- `kvzap-stage-a-probes-r1:probes`为idle bash；run root下没有存活进程exe／cwd。旧tmux、结果与输入全部保留。
- 测试流程约10分钟（含两个case的仿真构建／运行）；这是工具耗时，不是decode延迟或吞吐。Scala编译保留deprecation／feature warnings，本轮不声称warning-free。

## 2. 两项都有成功的首轮正向前提

每个独立case都先完成同一session内的首次服务，再尝试新增行为；两个case各自有初始reset，case内部首轮与第二次尝试之间没有reset。

| 每个case实际观察 | 数值／结果 |
|---|---|
| 成功packed payload write commit | 1；8片段与pending源数据一致 |
| S2接受payload／sidecar片段 | 8／1，逐片段核对实际数据／position |
| publication／membership handoff | 1／1 |
| consumer commits／成功attention terminal | 4／1 |
| session／S2槽 | R6仍Active；首轮S2槽已释放为Empty |
| packed page | page_id=0、page generation=0，descriptor仍readable |
| metadata credit | group已清理；localCredit占用计数归0 |
| memory fault | 0 |

packed payload来自本次真实接受的写入，不是第二次由host预装。sidecar明确由外部position backing按实际R3位置与R5 handle供给；partial/R4是结构性参考包，数值对应仍未建立。

## 3. READ_REUSE：页还在，第二次读取停在activation

第二次attention（新identity与下一step坐标）及source plan均已接受。在后续128拍内逐拍观察到：

| 观察 | 实际值 | 含义 |
|---|---:|---|
| R6 Active／packed page readable／S2 Empty | 1／1／1 | session仍运行、页仍存在、临时槽空闲 |
| binder havePlan | 1 | 新读取计划已经到达 |
| binder havePageReady／haveMemberStream | 0／0 | 缺少再次激活所需的页／成员事实 |
| descriptor request／lease request | 0／0 | 卡在R5 descriptor查询与S2 lease申请之前 |
| 第二次read request／第二terminal | 0／0 | 第二次读取根本尚未发起 |
| S2 source generation | 仍为1 | 未获得第二次lease，尚未推进到请求的2 |

根因对应：[binder:220](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAPackedReadActivationBinder.scala#L220)的descriptor／lease请求要求`havePlan && havePageReady && memberStreamMatchesReady`；[成功Emit后的清理](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAPackedReadActivationBinder.scala#L363)将page-ready／member-stream事实清掉，R3的page-ready observation也在fire后清active。当前没有从仍存活页恢复这些读取事实的持续通路。

这次排除了“首次terminal结束session”“S2尚被占用”“底层页已经回收”作为该场景第一阻断。没有绕过owner重新注入publication／成员／lease。结论限定为当前场景的有界动态观察及对应源码逻辑，不是任意输入下的形式死锁证明。

## 4. ADMISSION_REUSE：第二组已送达，入口仍在Done

首轮完成后，同一session送入G1：layer1/head0、entry_id8、不同group tag2／payload binding，各组ordinal从0开始。测试stream slots显式为16，坐标合法。

| 观察 | 实际值 | 含义 |
|---|---:|---|
| R6 context valid／authority valid／binding valid | 1／1／1 | 第二组需要的三元输入均持续存在 |
| ingress Done | 1 | 第一组结束后入口没有重新进入Collect |
| context ready／binding ready／第二join接受 | 0／0／0 | 第二组在接收入口被挡住 |
| R6 Active／页仍可读 | 1／1 | session与旧页仍然有效 |
| localCredit占用／ordinal0 journal present | 0／1 | credit已归还；旧journal记录仍保留 |

根因对应：[admission:1387](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala#L1387)的接受条件要求`StateCollect`；[最后成员relay:1496](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala#L1496)进入`StateDone`，没有正常返回Collect的转移。第二组并非因本地credit耗尽而受阻；这里的`localCredit=0`是已占用数量为0，不是可用credit为0。

**journal是后续独立义务，不是本次已经触发的动态失败。** 第二组尚未越过ingress，因而没有执行到R3重复ordinal断言。其64-slot/reset-only寿命仍须在任何rearm方案中处理，并保留旧组late lookup语义，不能直接清掉旧binding来接新组。

## 5. 结论与下一步边界

| 维度 | 本轮结论 |
|---|---|
| build/input/tool/artifact closure | PASS |
| 两项诊断的首轮正向前提 | PASS，保留显式外部服务条件 |
| 同页第二次服务 | BLOCKED：缺持久activation事实／查询通路 |
| 同session第二组admission | BLOCKED：ingress停在Done；journal仍有后续寿命义务 |
| 持续功能闭合／数值对应 | 未建立 |
| 本轮最终retire/reclaim | 阻断处停止，未到达；不增加旧C4-D退休覆盖 |
| 新面积／2ns时序／PPA／硬件净收益 | 没有新增证据 |

现在已将阶段A的两项源码假设提升为有首轮成功前提的动态阻断证据。修复范围可以据此分别界定：保留页权威的重复读取激活，以及入口／组状态／journal的跨组周转。不是只改一个ready或将Done改回Collect就能宣告闭合；新增状态、查询与服务应同步入成本账本。任何生产RTL／接口successor仍须单独明确差异与验证，本轮不实施、不重新综合。

实际配置仍是小参数functional contour、`gate_compact=0`、16 stream slots、外部position backing、`numeric_correspondence=0`；不称full32K或WCG1全顶层动态验收。源码／测试证据以冻结输入和[结果JSON](route_a_stage_a_probe_result_20261109.json)为准。
