# 持久页读取 v2：最小实现与功能验证准备 — 2026-11-09

**状态：实现候选；本地编译/展开检查与短验收脚本测试均已通过；远程native功能结果尚未验收。**
本批按[最小方案](route_a_continuation_minimal_proposal_20261109.md)只推进持久页读取，基线`822c4c9`。不实现多组admission、journal归档或新算法，不运行DC/STA。配套[JSON](route_a_persistent_page_read_preparation_20261109.json)保存源码、检查、保护区及验证范围。后续launch/result分别记录，不能由本准备文档推断功能PASS。

## 实现与兼容边界

显式constructor flag **`persistentReadEnabled: Boolean = false`** 位于measurement DUT、R6、SourcePlanBinder、R5/availability、S2。默认v1无新增optional端口/状态，control projection也仍走原默认路径；通用M2/P3 wrapper未修改。新模式是有界production-v2候选，不静默替换冻结v1合同。

数据流为：

```text
真实R3 member stream + all-R6 post-ready
  -> 独立receipt collector检查owner/tag/ordinal/坐标/count
  -> R5检查canonical descriptor，child安装read_ready
  -> runtime收到page_available（仅hint）

新attention + source declaration + PageRef hint
  -> R6真实live/unplanned attention owner
  -> R5 canonical query / typed result
  -> S2 v2 reservation / typed result
  -> declaration与R6 joint accept
  -> 原accepted-plan fork
  -> 同一份descriptor/lease进入原association、payload/sidecar、四consumer、terminal/release
```

- **R5持久事实**：availability child新增每页1bit read_ready，allocation/reclaim/reset清除；只有真实collector receipt可置位。descriptor-v2在`[59:52]`保存tag，原128-bit容量不变；tail保留、invalidate清理。旧visibility与R3唯一publication不由新controller制造。
- **runtime边界**：optional `persistentRead.page_available_out`、`page_select_in`、`rejected_out`、`receipt_fault_out`。hint无权限含义；R6提供真实attention layer/head，R5提供canonical count/tag/handles。selector表按tracker数有界、支持乱序，落表前核验live attention；foreign输入明确拒绝。
- **preflight**：held declaration尚未被R6接受前完成R5/S2检查；所有source在joint accept后才fork，pending association仍与同一fire耦合。取得的同一S2 lease只交付一次，不重新申请；R6 copy与下游背压期间保持。
- **错误**：R5有OK/NOT_READY/INVALID/FAULT；NOT_READY必须对应真实receipt安装在途并释放查询口。S2先判kind/coordinate/next-generation是否合法，再判BUSY；仅GRANTED改变slot/generation。无lease的失败通过binder cancel和R6 reject双边ACK收束，真实fault terminal被接受后才释放tracker。foreign identity不制造attention或terminal；已GRANTED不走普通reject丢资源。
- **禁止同attention二次装plan**：R6 v2新增unplanned位，在实际attention接受时置位、plan/reject/terminal时清除，不能把source release后清除的`sourcePlanValid`误当成“从未装plan”。v1行为保持。
- **retire分期**：R6进入Retiring立即停止新frontend工作；在已有attention/owner工作完成前保持transport drain低，允许R5查询、S2预约与R2普通请求继续。tracker、source-plan copy/context、collector/controller及现有metadata bridge active-group归零后才收集drain、发reclaim permit。R2的仲裁、类别和eligibility没有修改。R5 init状态不受preflight busy遮挡，防止初始化闭环。

R3/member/authority/journal与admission连续保护区133,572 bytes、R2及其后common owner区119,992 bytes，与基线逐字节相同。新top仍保留legacy binder对象以兼容旧只读harness引用；v2下该对象全部输入inactive、输出discard，不参与authority/activation，后续映射若涉及应检查DCE，不能假定其面积为零。

## 存储与成本边界

在production页数146,880下，read_ready名义新增146,880bit＝18,360B；descriptor tag激活原zero位但不增加名义128-bit字数。当前functional实现仍使用可替换array child，**不是已选SRAM宏或面积收益**。

新增controller具有selector/probe、注册化context、R5结果、lease、错误/ACK holding；R6新增owner/unplanned/context状态；R5增加共享端口操作状态，S2增加typed response holding，collector增加receipt/notice/fault holding。这些均需进入后续增量账本，不能沿用方案中的1,259bit枚举小计当成实际完整成本。新路径增加preflight周期，本批不建立2ns、吞吐、能量或净收益结论。

**未新增**288-MiB历史归档、第二组rearm、compact容量削减、第二次publication或payload副本；journal reset-only与单组Done边界保留。外部descriptor-v2 service需要相同schema的provider，当前定向whole-DUT使用内部functional backing，不据此声称external模式或full-anchor闭合。

## 检查与远程验收计划

本地只做受限资源Scala编译、完整v2 top的Chisel展开/firtool lowering和短Python验收测试，不运行native仿真。结构检查明确default-v1无optional端口、新v2保留真实owners；它不代替动态行为验证。新checker11项＋旧checker9项短测试包括：源码/归档/ELF/XML漂移、skip/非零exit、伪echo marker、完整typed counts、错误路径资源副作用、runner和tmux外层退出。

远程独立tmux执行**14项native测试**：

| suite/层次 | 数量 | 检查重点 |
|---|---:|---|
| v2 complete DUT | 3 | 一次真实packing后同页两读；四类bad page/owner/S2选择、foreign declaration与恢复；已接受attention但selector未到时retire，继续完成旧服务后回收 |
| S2真实owner | 1 | 四次INVALID不分配，GRANTED回复背压16周期保持，合法next-generation的BUSY不修改slot |
| R5 availability真实child | 1 | mark/ACK背压、allocation/reclaim无ready更新、clear优先、generation与stale拒绝 |
| controller／R6 owner | 3 | 同一reservation跨joint/copy背压、mixed hot+packed plan精确转发；cancel ACK偏斜与foreign；真实R6 source release后不可二次装plan |
| default-v1 R3 | 4 | 原first-use/hot/fault/direct withdrawal回归 |
| default-v1旧diagnostic | 2 | 保留原两个BLOCKED verdict，不能混计为v2功能PASS |

whole-DUT使用小参数：allocator8、stream16、source/tag/stage generation2bit、handle32bit、`gateCompactMembershipWords=false`。真实packed payload只由首次R1 accepted write形成；第二次不能preload新packed副本、重publication或内部force。sidecar position backing及partial/R4 reference仍外部，numeric correspondence仍未建立。

本批retire动态目标是**已有已发布页、attention已接受而preflight未完成**的排空；metadata-active guard也覆盖precollector工作，但没有增加“任意partial admission途中retire/abort”的完整动态证明。多组、全部mixed-source全顶层、reset/wrap、完整32K/并发与持续pending owner生命周期仍OPEN。

runner冻结source commit、所有输入SHA/bytes与archive，在新工作目录编译/构建，禁止携带旧target/build。先Test/compile，失败即停；然后14项serial native测试。checker同时核XML、实际ELF/编译日志/执行脚本、精确typed结果、一次packed write/两次service/四消费者及最终回收。运行后必须以`--final`再核runner exit0、RUN_PASS、tmux wrapper exit0和outer marker。旧tmux和结果不清理，不自动retry；启动后通知用户等待。

本地检查与独立静态复核只允许本批进入远程功能验收。远程运行结束后的功能、数值、范围、成本和时序结论必须分别报告；本批不启动完整DC，也不更新已冻结的面积结果。
