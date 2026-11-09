# 持久页读取 v2 r1：失败结果与共享查询归属诊断 — 2026-11-09

**运行已结束；整体功能验收FAIL：14项测试中11通过、3失败。** 本轮只读检查已结束的`persistent_page_read_v2_20261109_r1`，不修改生产RTL、冻结输入或验收门槛，不重跑模拟器/DC/STA。依据为[冻结启动记录](route_a_persistent_page_read_launch_20261109.md)、远程原生报告/交互记录、冻结生成RTL及[证据JSON](route_a_persistent_page_read_result_20261109.json)。

## 1. 完成、输入与测试分布

| 项目 | 实际结果 |
|---|---|
| 冻结source/archive | `1d49fc8a8716c6b3e117e62bb6d5ae97f5693118`；SHA `40973dc895eb4a72798aeb9da760efdac8d71a1f79614857f392ddacef7ab119` |
| 输入 | 152份source的hash/bytes、source/input manifest及archive核验匹配 |
| compile / test / runner / tmux退出 | **0 / 1 / 1 / 1**；无FUNCTIONAL_RUN_PASS |
| 6 suites / 14 cases | 11成功、3失败、0 error/skip/abort |
| native产物 | 14个真实ELF及各自compile log、execution script、simulation log均存在并登记hash；simulation logs为空，交互记录保留在execution script |
| 运行时间 | 测试约44分18秒；2026-11-09 14:40:48结束 |
| tmux | `kvzap-persistent-read-v2-r1:validation`保留为bash，pane4056无子孙任务；不存在后台native仍在跑的情况 |

| 测试层次 | 结果 | 能说明什么 |
|---|---:|---|
| v2完整DUT | **0/3** | 三者均在首次packed读取的同一前置阶段失败 |
| v2 owner/controller/R6 unit | 5/5 | 子array更新、S2预约、mock-R5 controller及真实R6 no-replan场景通过；未覆盖R5父级共享端口记账 |
| default-v1 R3回归 | 4/4 | 本次保留旧first-use/hot/fault/withdrawal行为的动态证据 |
| default-v1旧诊断 | 2/2 | 重新复现原来的READ_REUSE/ADMISSION_REUSE两个BLOCKED，不算新增持续功能成功 |

归档中的严格checker以`--final`只读核验，按预期在`test_exit_status != 0`拒绝，退出1。runner因native测试失败未进入postcheck；没有通过文本或XML覆盖非零退出。这次不是汇总脚本误拒收。

## 2. 三项失败实际发生在何处

三项完整DUT测试的失败栈都停在`Driver.completeRead`的**第一次**调用，分别为测试源425/436/452行：`packed source did not reach READY after 2048 clocks`。因此：

- SAME_PAGE_TWICE没有到第二次读；
- 错误路径测试没有到bad owner/generation/slot或foreign等负例；
- retire测试没有发出其目标retire请求。

三份已保存execution-script逐字节相同：1,948,770 B，SHA **`74fe8d27fe8de7e0eb3f47db057b16395dce82fd0e6f84a50de4a2785c146f5a`**。本轮使用generated testbench中的`// Port hex: name`映射，配对记录里的`G u port`与`b width value`，只读还原已发生的GET，**未重放ELF或新增仿真**。2160条tick命令包含初始化，2159次主流程采样；时序索引不换算成ns或吞吐。

| 已记录观察 | 三项共同结果 |
|---|---|
| 实际R3 publication / post-R6 ready | 各1次，记录cycle97/100 |
| runtime page_available | valid与ready同在cycle108；PageRef0/gen0、count1/tag1 |
| 首次attention / selector / source declaration | driver依次接受RID3、PageRef0/gen0、packed slot1/source-gen1；对应cycle109/110/111 |
| R5正向descriptor grant | 2159次采样全部0 |
| S2 slot状态 | 2050次GET全部Empty |
| payload/sidecar填充、consumer commit、source release | 各2159次采样全部0 |
| typed rejection、attention terminal、receipt fault | 已记录valid全部0 |

`publishOne`已越过真实一次8-fragment packed write及内容一致性的断言，publication/receipt/notice已完成；但首次新read未获得R5成功grant，所以尚未进入S2实际服务。不是三类场景各自出现不同问题。

**观测边界：** `preflight_busy`和`declaration_live`虽然被导出，但失败前driver没有GET；`attention_live`只在attention前采样一次。不能声称从日志直接读到了它们的超时末态，也没有直接采样内部`scanOutstanding`。下述寄存器锁死结论来自确定的源码/冻结RTL推导，并由已记录I/O链支持。

## 3. 确定根因：R5将v2请求误记为scanner请求

源位置为[共享request记账](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala#L4291)、[旧scanner response清除](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala#L4294)、[v2 request guard](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala#L4711)。

1. 旧scanner对共享`availability_lookup_req.fire`无条件执行`scanOutstanding := true`。该when读取的是端口最终fire，并不限定为上方scan驱动语句的请求。
2. v2 mark安装读取资格也使用该端口，因而把**自己的查询**记进了scanner的未完成位。
3. mark的响应由v2 FSM消费；旧scanner清除分支明确排除`persistentAvailabilityOutstanding`。该请求没有对应的scanner清除，留下虚假的`scanOutstanding=1`。
4. mark仍能完成，collector正常给出page_available。后续read query即使已被接受并进入AvailabilityRequest，其发请求条件`!scanOutstanding`也不再满足，因此无法发出下一次availability lookup，也就没有R5结果、S2预约或错误响应。内部query状态没有被直接GET；这是由完整状态更新关系推出的阻断，不排除修复后还会暴露后续问题。

冻结native的`primary-sources/route_a_page_manager_persistent_v2.sv`确认同一关系：1330行`state==AvailabilityRequest & ~scanOutstanding`；1848行`_GEN_74`是不区分owner的共享request fire；607–609行清除项排除v2 response；2258行将这些项用于scanOutstanding更新。该逻辑保留在真实参与native构建的RTL中，没有被优化消除。

本轮已核对原binder与新controller的packed eligibility mask相同、四份association carrier字段相容；测试的slot1/gen1与S2初始next-generation相符。sidecar reference仅在成功R5grant后被使用，本次尚未到该处。没有证据把此次失败归因于payload/sidecar数值、第二读generation、R2仲裁或retire改动。

## 4. 为什么已有检查没有检出，以及下一步最小范围

R5 unit只检查availability **child** 的ready-bit/clear/ACK；controller unit直接mock R5结果；真实R6 unit不经过R5。这些通过的测试绕过了发生错误的父级共享端口。Chisel/firtool展开能检查连线与组合结构，不能证明该状态机具备进展。

最小修复候选是让scanner仅对**真实scanner拥有的请求**记账，例如`scanAllowed && availability_lookup_req.fire`。不能仅加`!persistentAvailabilityOutstanding`，因为v2发请求时尚未处于等待响应状态；也不应随意在v2 response清除scanner位，掩盖端口归属。

建议后续按顺序：先修父级记账归属并加入真实R5 parent的mark→query→query、scan交错与held-response定向测试；在测试timeout快照中加入请求owner/scanOutstanding/v2状态等实际只读观察；短验证通过后，再定向运行完整DUT首个同页两读case，最后恢复错误/retire及v1回归。保留本r1失败产物，新运行使用新ID，不通过扩大2048 timeout掩盖永久阻断。

本轮只完成失败验收和根因定位，没有实施上述修复或重跑。新v2的同页两读、完整错误路径和retire排空仍未验收；默认v1回归保留。无新面积、2ns时序、数值、完整持续decode或硬件净收益结论。
