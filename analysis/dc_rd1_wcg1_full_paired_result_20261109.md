# RD1＋WCG1 完整 paired DC r2：结果验收与分析

验收日期：2026-11-09（Asia/Shanghai）。Run ID：
`dc_feasibility_fair_rd1_wcg1_20261108_r2`。

**完整流程正常结束，工具／输入／制品闭合通过。原策略下，Route-A 顶层映射面积比 RD1 再降低 11.741151%，控制面积比从 146.747× 降到 129.517×；setup 变差。门控补充流程的 hold pass 也没有使整体 setup/hold 收敛。**

这是已测得面积收益、同时有时序代价的结果，不能笼统称为全部成功。以下 area 均为同库 cell-area units，不是物理 core area、整机面积或 PPA。

本轮只读检查远程进程、日志、标记、输入和 native reports；重新运行的是 Python 制品检查函数，不调用 DC/STA、不加载 DDC、不仿真、不修改远程文件或进程。原结果、脚本、r1 失败和资源等待记录全部保留。机器证据见 [结果 JSON](dc_rd1_wcg1_full_paired_result_20261109.json)。

## 1. 完成与输入闭合

- Full-KV、Route-A 两侧持久化 exit 均为 0；两侧实际 SIDE_PASS 和全部六个 STAGE_PASS 标记齐全。
- native binding 的实际 PASS、postcheck、`FULL_PAIRED_RUN_PASS_TOOL_ARTIFACT_ONLY`、原 runner outer exit 0、q1 dispatcher outer exit 0 与对应状态文件一致。标记按整行匹配，排除 DC 回显 Tcl 源码造成的假阳性。
- 当前实验没有活跃 native 进程；独立 `kvzap-rd1-wcg1-r2q1:paired-dc` pane 为 idle bash。窗口状态只是辅助证据。
- 独立只读重算 `check(root)` 与保存的 `result.json` 完全一致，136 个 native artifact hashes 全部重算；DDC、mapped HDL、SDC、QoR、层次面积、时序／gating／driver 等报告均非空。
- 4 项实际输入、19 个 bundle 文件、189 个 proxy 树文件和 49 个 composed SV 文件分别重哈希；与运行登记、launch pins 和 composition 对应。实际 Full-KV primary 的面积、cell counts 与已比较 QoR 指标精确复现不可变 baseline／RD1。
- reference wrapper 与 RD1 逐字节相同；47 个 Route-A 单元未改，仅换 contextual wrapper 并加精确 inline gate。PM1 关闭、RD2 排除，121 个 accepted source 检查保持其冻结范围；16 typed port families、12 real owners、4 个 raw Route-A array interiors 及 5 个 paired proxies 通过。实际 mapped 层次也保留 12 个有非零面积的 owner。
- 所有 tier 都保持原 2 ns、setup/hold uncertainty .10/.02 ns、I/O .20 ns、transition .05 ns、load .005 pF，reset timed，无 false/multicycle 例外。primary 保持原 ideal-clock policy；补充 tier 在两侧使用同一 propagated-clock／hold pass。

| 输入 | SHA-256 |
|---|---|
| paired archive | `59306981d8a7fbda704170b48cc69799b6c2424fcb545805032c93d845c4642e` |
| library | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| proxy manifest | `72d80385a0b6997b7facfa875e519da87b61b506f0184c5c85cd2c812fe33cbd` |
| constraint Tcl | `3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007` |
| 19-file script archive | `281d23783cbba22a27ff1e8908e27a6e25241dc3ff43c18ae7d8f2b8da0cf5fc` |

Full-KV 保留与此前相同的单条 VER-41 verification-include diagnostic；未新增 native Error/Fatal，redirected reports 无 Error/Fatal。这不是 warning/error-free 的工具宣称。之前的哈希域错误已在真实冻结中越过，不能把本次完整结果与旧 r1 的 pre-DC 失败混为一谈。

## 2. 原策略的公平面积比较

对照是 [RD1](dc_rd1_full_paired_dc_result_20261106.md)，不是 RD1＋PM1。下面两项都使用 original primary mapping policy，Full-KV 均为 **23,091.432498**。

| 指标 | RD1 | RD1＋WCG1 primary | 变化 |
|---|---:|---:|---:|
| 顶层 cell area | 3,388,597.345862 | **2,990,737.008920** | **−397,860.336942（−11.741151%）** |
| combinational area | 1,392,283.363726 | 1,380,195.762880 | −0.868185% |
| noncombinational area | 1,996,313.982136 | 1,610,541.246040 | **−19.324252%** |
| / Full-KV control | 146.747× | **129.517×** | −17.230 ratio points |
| sequential cells | 577,106 | **581,714** | +4,608（native gates 的内部 latch） |
| 根时钟直接 fanout | 577,110 | **215,382** | −361,728（−62.679212%） |

映射后的两个快照（primary 和 hold pass）均实际保留 **366,336 个 DFQD2 table flops、4,608 个 CKLNQD1 native gates**；所有 gate 的 TE 经 `Logic0` 连接到 native TIEL 低电平输出，全部 48 个 entry_id 输出 bit 有 driver。数据容量、两个 64-bit 字段与必要状态没有因面积优化而减少。

机制与隔离实验一致：降低每 bit 的 enabled-flop 保存成本，改由 word 共享 gate 控制，并承担 gate/latch、tie、decode、buffer 与尺寸选择的成本。这里是完整顶层实际映射，不能拿隔离 wrapper 的 15.624812% 当顶层收益。

根直接负载减少量恰为 `366336 − 4608 = 361728`；时钟负载移到 gate 后面，数据 flops 和下游 clock network 仍在。DC 仍使用高 fanout 近似，不能由直接 fanout 降幅推导同等 clock power/电容或 CTS 收益。

相对最早 immutable r5desc 顶层面积 6,716,537.642416，本轮累计减少 **55.472043%**。这是整条 refinement 的累计收益，本次 WCG1 的增量是 11.741151%。

### 层次归因

| 层次 | RD1 | WCG1 primary |
|---|---:|---:|
| M2/P3 wrapper | 2,387,543.1337 | **2,017,663.5311** |
| Page Manager | 407,306.5906 | 407,353.1266 |
| M2 production control | 175,735.2263 | 176,117.9304 |
| metadata bridge | 85,833.3851 | 85,833.0491 |

Wrapper 降低 **369,879.6026（15.492059%）**，仍占当前顶层约 **67.46%**。未改源码的其他 owner 也发生小幅映射变化；不能把顶层所有变化都归给某个子层次。Page Manager 的变化不是 PM1，因为本轮明确关闭 PM1。

## 3. 时序：面积改善，没有整体 closure

### Primary 与 RD1

Route-A setup worst slack 从 RD1 已登记的约 −0.36 ns 变为 **−0.469940 ns**；TNS magnitude 从 9,774.02 增至 **12,698.75 ns（+29.923512%）**，violating paths 从 35,959 增至 **36,017**。Primary hold 仍无违例，最差 slack **+0.005394 ns**。

当前 worst setup 从 arbiter 的 pending-association generation register 到
`io_functional_sidecar_read_issue_in_ready`。这是跨 owner 控制路径。样本不经过 native gate，gate-enable 自身的 setup/hold 也为正；这不能排除 WCG1 集成对全局 mapping 的间接影响，更不能证明所有退化的因果。定位需要另行有界诊断，本轮不启动。

### 三个测量 tier 分开保留

| Tier | Full-KV area | Route-A area | 同 tier 面积比 |
|---|---:|---:|---:|
| primary_raw | 23,091.432498 | 2,990,737.008920 | **129.517×** |
| propagated_raw | 23,091.432498 | 2,990,737.008920 | **129.517×** |
| propagated_hold_repaired | 25,372.872553 | 3,019,776.817078 | **119.016×** |

**119.016× 不是另一项 WCG1 面积节省。** Hold pass 使 Route-A 面积增加 29,039.808158（0.970992%），同时使 Full-KV 增加 2,281.440055（9.880028%）；分母增长更快，才使比值进一步变小。不得把这个 ratio 与历史 ideal-clock RD1 当作纯 RTL 优化增量比较。

下表 slack 来自 6-digit precision reports；TNS/count 来自 native QoR，TNS 按违例负号呈现：

| Top / tier | setup slack(ns) | setup TNS(ns) / count | hold slack(ns) | hold TNS(ns) / count |
|---|---:|---:|---:|---:|
| Full-KV primary | +0.000043 | 0 / 0 | +0.016214 | 0 / 0 |
| Route-A primary | **−0.469940** | −12,698.75 / 36,017 | +0.005394 | 0 / 0 |
| Full-KV propagated raw | −0.008623 | −0.06 / 27 | +0.019996 | 0 / 0 |
| Route-A propagated raw | **−0.482178** | −12,912.35 / 36,021 | +0.006092 | 0 / 0 |
| Full-KV hold pass | −0.064103 | −3.92 / 79 | **−0.009376** | −0.39 / 46 |
| Route-A hold pass | **−0.575940** | −12,713.58 / 34,624 | **−0.034459** | −12.19 / 825 |

目录名 `propagated_hold_repaired` 表示执行了规定的 hold pass，不表示 hold closure。原 raw hold 零违例；该 pass 后两侧都出现负 hold，并且 worst setup 变差。工具正常完成与这项测量负结果同时成立。必须保留它，不能自动调整流程、放宽门槛或重新综合掩盖。

### Gate 本身与整体时序的区别

| Gate 检查 | primary | propagated raw | hold pass |
|---|---:|---:|---:|
| enable setup slack(ns) | +0.589114 | +0.576777 | +0.594329 |
| enable hold slack(ns) | +0.103826 | +0.106806 | +0.092528 |
| gated table data 最差 hold(ns) | 本 tier 不要求补充报告 | +0.029247 | +0.017546 |

补充 capture 路径含正的 native gate-Q 延迟（sample increments 0.095563/0.094088 ns），不是零延迟理想 gate。Gate 和 table 的这些局部检查通过，**不等于全顶层时序通过**。

Hold pass 后 worst setup 为 `m2P3/stageValidRecords_5_reg[1]` 到 registry-allocate ready；worst hold 为 activationBinder 的 valid-record register 到 Page Manager lookup-request register。它们指向控制／时钟分布问题的进一步审查入口，不是本轮已经证明的完整根因。

## 4. 结构清洁度与边界

- Primary warning lines：**44,536 → 44,552**。其中 LINT-29 增 5、LINT-31 增 11，其余已比较类别不变。没有 broad lint 改善。
- LINT-28 主要为 typed carrier 未连接字段；LINT-29 为直接 feedthrough；LINT-31 为 shorted outputs；LINT-33 为同 cell 多 pin 共网；LINT-52 的 922 个 constant-output warnings 与 RD1 相同。应逐字段核对，不能靠删必要状态或外部接口消除。
- 所有 tier 的 LINT-3/LINT-5 为零，48 个 entry_id drivers 通过，native gate/data inventories 完整；这是定向结构检查闭合，不是 warning-free。
- `check_timing` 没有新增 unconstrained/missing-delay 类警告，TIM-134 的高 fanout 近似仍在。Constraint report 仍有 min-capacitance 违例：Full-KV 522，Route-A raw 1,327、hold pass 1,328。QoR 中 max-cap/max-transition 为零不清除这些 min-cap 问题。
- Hold pass 后 root direct fanout 变为 Full-KV 56、Route-A 201，且 buffer/clock 分布被重新映射；不能把它作为 WCG1 单独的结构／功耗收益或物理 clock tree 结果。

Array proxies、P3/M2/R5 存储及外围、R4 numeric/partial、controller、clock/wire/物理实现等完整增量仍未闭合。129.517× 只属于当前 control projection；既不是整芯片面积比，也不能据此声称硬件净收益或其相反结论。

## 5. 分项处置

| 维度 | 结论 |
|---|---|
| tool/input/artifact closure | **PASS**；保留已知 Full-KV baseline diagnostic |
| mapped-area improvement | **PASS**；primary 顶层 −11.741151%，wrapper −15.492059% |
| timing closure | **FAIL**；primary setup 退化，补充 hold pass 后两侧仍有 setup/hold 违例 |
| structural cleanliness | **OPEN**；定向 driver/gate/state 检查通过，broad lint/high-fanout/min-cap 未闭合 |
| PPA／外部服务零成本／系统加速／硬件净收益 | **未建立** |

保留 WCG1 为有完整顶层面积证据的候选。它没有解决当前设计的整体时序和完整增量成本；不应直接宣布整个实现已经可接受，也不应因为时序问题而丢掉已证实的面积结果。下一步建议优先有界定位 global ready/setup 路径与补充 hold 策略的退化，再决定集成处置。本次不启动新诊断、RTL 修改或综合。
