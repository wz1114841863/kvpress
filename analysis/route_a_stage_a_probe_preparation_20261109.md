# 阶段 A 当前 RTL 连续执行探针：测试准备 — 2026-11-09

用户授权基于现有 RTL 分别验证同页重复读与同 session 第二组 admission，定位具体阻断点；禁止修改生产 RTL／启动完整 DC，远程长测试使用独立 tmux。本批落实 [阶段 A 场景](route_a_stage_a_execution_envelope_20261109.md)，不是实现修复或新的持续功能验收。

## 测试与观察范围

新增 [Scala suite](../hardware/route_a/chisel/src/test/scala/kvpress/routea/RouteAStageAContinuationProbeSpec.scala)，保留完整 `RouteAMeasurementDutR3Harness` 为唯一功能子树，通过 test-only `BoringUtils.tapAndRead` 导出只读观察；不驱动内部 publication、authority、lease、source release、terminal、reclaim 或 drain。

两个独立 `it` 都先完成同一正向前提：init/session、边界事件、第一组 packing／publication、实际 payload／sidecar fill、四消费者与一个成功 attention terminal。然后：

| 场景 | 合法刺激 | 必须观察的定位证据 |
|---|---|---|
| READ_REUSE | 不retire/reset；新identity、下一step坐标、同S2槽的新source generation | 第二attention与plan已接受，R6 Active、页可读、S2 Empty；若binder持plan却缺page-ready/member且descriptor／lease未发，记录具体阻断 |
| ADMISSION_REUSE | 不retire/reset；layer1/head0、tag2、ordinal0、独立binding | 第二组context／authority／binding合法并held；若ingress Done且join ready持续低，记录此第一阻断；journal后续义务仍仅为静态，不伪称已动态复现 |

阻断窗口为128个功能仿真clock；首轮未成功、memory fault、错误输入或证据不一致都必须使测试失败。该窗口只证明有界观察，不是无界死锁／吞吐证明。两个探针各自从初始reset开始，**各自首轮与第二轮之间不reset**。

## 真实数据与外部服务边界

- pending payload只在外部源地址55预置；packed payload必须来自该次实际接受的写数据及成功terminal后的functional store commit，之后S2所接收8片段逐一核对。
- 目前没有生产HBM sidecar写路径可由此探针证明。明确模拟外部position backing：数据取实际接受的R3 materialized position，地址取真实R5 descriptor grant；S2接收sidecar后核对。该服务不是packed payload写事务的一部分，不是零成本存储。
- partial／R4使用关联正确的结构性参考包，`numeric_correspondence=0`。不声称Q/K/V自主数值执行；hot128完整前端历史也是外部事件级前提。
- 小测试档沿用既有R3Spec，唯一参数扩展为`r5StreamSlots:8→16`，使layer1/head0的stream index8合法；不改生产profile或generic容量。`gateCompactMembershipWords=false`，不冒充full 32K或WCG1全顶层动态验证。

## 执行与验收

[独立runner](../hardware/route_a/dc/run_stage_a_continuation_probes.sh)验证新的源码archive／文件hash，使用离散workspace，依次执行`Test / compile`与该suite；Java11／heap4GiB／2 active processors／MAKEFLAGS=-j1／unlimited stack，绝不调用DC／STA。

[postcheck](../tools/check_stage_a_continuation_probes.py)要求compile/test exit0、XML恰2测试且无fail/error/skip、两条实际整行marker、正向前提／具体状态一致、archive与全部源文件复核。结果区分：

```text
build_and_probe_execution = PASS         # 仅当执行和证据资格均通过
same_page_reuse / multi_group_admission = BLOCKED_CURRENT_RTL...  # 若预期阻断实际复现
continuous_functional_closure = NOT_ESTABLISHED
```

`ScalaTest PASS`和`DIAGNOSTIC_RUN_PASS_NOT_CONTINUOUS_FUNCTIONAL_PASS`不表示持续功能已通过。意外进展／不同阻断需要独立分析，不能套用预期根因。runner保留compile/test/outer exit文件、native测试XML、日志和result JSON，失败不自动重跑。

若两个用例在新目标的阻断点结束，本轮最终retire/reclaim也未到达；历史C4-D退休验收继续沿用，不能将这两个有界探针叫作新的完整持续witness。

本地准备检查：Scala2.13.18 parser通过；postcheck的9项单元测试通过（缺少首轮／正向证据、重复或回显marker、source/archive漂移、native exit失败、XML skip和意外进展均拒收）；runner语法／help及`git diff --check`通过。未本地构建大型Verilator仿真。生产`src/main`与旧R3Spec保持原内容。

**当前仅测试准备完成，远程compile/elaboration与两个实际场景尚未验收。** 启动前单独冻结源码archive、记录run ID／tmux／日志／hash，并更新live入口；用户通知运行结束后再验收，不从启动推断结果。
