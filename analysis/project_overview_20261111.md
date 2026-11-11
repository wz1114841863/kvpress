# KVzap 项目总览与管理入口

整理日期：2026-11-11。整理时分支 `research/kvzap-latest`，已有研究源码 HEAD
`8a7ea4e`。这是一份**人能快速读懂的状态快照和导航**；某项结果的具体输入、
适用范围和验收仍以对应原始记录为准。项目正在整理，下一项研究计划尚未决定。

## 先看这一页：我们做到了哪里

我们研究的是：KVzap 删除 KV 后，能否通过实际存储组织和调度，把**逻辑上的稀疏**
变成有价值的物理节省。当前针对 Qwen3-8B 进行了算法分析、系统建模、Route-A
硬件原型和控制逻辑综合。**已经有可复核的算法结构、模型和有界硬件功能结果；
还没有证明完整硬件实现的时序闭合或系统净收益。**

| 研究部分 | 已取得的结果 | 目前不能直接得出的结论 |
|---|---|---|
| 原始算法 | 指定环境的 baseline 功能检查通过；45 条 balanced v2 predictor-only trace 的 token 加权逻辑删除约 66.23%，逻辑压缩约 2.96× | 正式任务准确率、物理显存下降或加速 |
| 系统模型 | 已分析 packed page、调度、生命周期和 admission；A4.14.1 在三个固定 workload 与明确服务/proxy 假设下得到条件性机会 | 实际硬件成本已覆盖、统一时钟下的真实延迟或系统净收益 |
| 硬件功能 | 早期 first-use 路径有测试；显式 v2 的小规模场景验证一次 packing 后同页读取两次，以及指定错误和 retire 排空场景 | 默认 v1 具有重复读取、多组 admission 已实现、全 32K 并发或真实数值计算闭环 |
| 控制面积 | 最后验收的 RD1＋WCG1 paired DC：Route-A 2,990,737.01、Full-KV 23,091.43，同库 cell-area units，控制投影约 129.52× | 整芯片面积比、完整 Route-A 成本、PPA 或净硬件收益 |
| 时序 | 同一 2 ns 约束下，RD1＋WCG1 primary 的 Route-A setup WNS 为 −0.469940 ns；补充 hold-pass 后 setup/hold 也未闭合 | 顶层 2 ns 已可实现，或孤立门控检查通过等于全局通过 |

上表的面积数字来自指定冻结输入的综合快照；后续增加的持久页 v2 功能**没有**计入
该次综合结果。`129.52×` 只比较控制投影，不能推断最终完整系统面积比一定更大或更小。
详细依据：[深层复审](route_a_deep_review_20261107.md)、
[RD1＋WCG1 结果](dc_rd1_wcg1_full_paired_result_20261109.md)、
[持久页读取结果](route_a_persistent_page_read_r2_result_20261109.md)。

## 几个月的工作，按一条线看

算法至前 RTL 系统探索的详细脉络、六份紧凑报告归并建议，见
[算法阶段整编评估](algorithm_stage_review.md)。它按研究目的、计划、结果和分析整理，
不以运行报错和校验过程作为阅读主线。

1. **算法与 trace。** 复现指定 KVzap predictor，用 baseline 和 18/45 条 trace 了解
   稀疏结构。不同请求的 layer/head 保留比例轮廓较稳定，但 token 级 mask 重叠较低，
   不能直接当成共享 mask。
2. **物理方案筛选。** Route-A 保留原 mask、按 token packing；Route-B 曾筛查 B=4
   结构化策略。B=4 在特定 timeline-page 模型里有小幅 proxy 优势，但逻辑压缩更低，
   现有生成质量结果只属于小样本筛查。两者都是带条件的证据。
3. **Route-A 系统建模。** A0—A4 逐步研究 page、调度、生命周期、流量和服务成本。
   短输出存在 admission 不易摊销的反例；A4.14.1 的收益是固定工作负载和假设下的
   账本，不能自动转成硬件实测收益。
4. **规格与原型。** 在后续阶段授权下实现并验证部分 owner、publication、authority、
   读取和回收路径；持续 decode 的全部数据和数值服务尚未完成。
5. **面积与时序诊断。** 依次验证 metadata bridge、compact membership、RD1、WCG1
   等改动，面积比最初综合快照下降，但顶层时序和完整增量成本仍是问题。RD2 隔离
   映射无面积收益；PM1 在完整顶层有小面积收益，但其选择器 setup 退化，未纳入
   最后的 RD1＋WCG1 基线。
6. **持续执行缺口。** 默认 v1 的同页第二次读取与第二组 admission 曾被定向探针
   阻断。显式 v2 已在有限场景补齐前者；后者及 journal/pending 生命周期尚无生产
   实现验收。最新候选合同和参考模型有助于界定问题，不能当作 RTL 或成本验证。

继续追溯：
[45 条 trace 冻结](longbench_balanced_v2_freeze.json) ·
[Route-B 冻结](b4_route_b_screening_freeze.json) ·
[A4.14.1 合同](route_a4141_accounted_net_benefit_ledger_contract.md) ·
[两项持续执行探针](route_a_stage_a_probe_result_20261109.md) ·
[多组 journal 生命周期](route_a_multigroup_journal_lifecycle_closure_20261109.md) ·
[pending 来源候选合同](route_a_pending_origin_and_window_contract_20261109.md)。

## 现在真正还没有解决什么

- **功能范围：** 一次打包后重复读取已有小规模 v2 证据，但同一 session 的多组
  admission、合法 pending 来源、旧 journal 的安全释放和真实数值链仍未闭合。
- **存储：** compact 两张表及其并发读写是已映射控制面积的重要来源；P3、M2、R5
  等存储、端口和外围仍有未计价部分。当前 64-bit 字段不能在现有通用接口合同下
  直接假定能截短；当前寄存器实现也不能被当成算法必然面积下界。
- **时序：** 跨 owner 的 ready/控制链和其他路径在原 2 ns 下有 setup 违例；当前
  结果也不能证明完整时钟树和 hold 已收敛。
- **收益：** 逻辑删除、模型中的 traffic/动态能量余量、控制逻辑面积分别属于
  不同证据层次，不能直接相加或相互替代。完整存储、服务、能量和延迟账本仍开放。
- **路线选择：** 原 mask 与硬件适配、保持 mask 换存储表示、改变 mask 的算法—硬件
  协同都可作为未来讨论对象；目前尚未决定新路线，也没有以此覆盖历史冻结结果。

存储/服务范围见[增量成本账本](route_a_incremental_storage_cost_ledger_p0_20261106.md)
和 [P3 staging 可行性](p3_staging_storage_mapping_feasibility_20261106.md)；
当前论文原型范围见[执行范围文件](route_a_paper_execution_scope_and_closure_20261109.md)。

## 仓库怎么找：先找入口，再看具体证据

| 位置 | 放什么 | 何时进入 |
|---|---|---|
| [README](../README.md)、[AGENTS.md](../AGENTS.md) | 上游 KVPress 使用说明与本研究的规则、历史冻结状态 | 环境、项目规则、baseline 范围 |
| [analysis/](README.md) | 研究结论、设计合同、阶段交接、冻结清单 | 要找“为什么这样设计、结论依据是什么” |
| [analysis/experiments/](experiments/) | 各次运行的报告和数据；大量路径被 Git 忽略，部分不在 Git 历史中 | 按原报告/manifest 指定路径追溯，不能假设换机器后仍在 |
| [kvpress/](../kvpress/) | KVPress 算法和推理集成；[KVzapPress](../kvpress/presses/kvzap_press.py)、[DMS](../kvpress/presses/dms_press.py) 与 [attention patch](../kvpress/attention_patch.py) 是重要入口 | 找 predictor、mask、压缩实际软件路径 |
| [kvzap/](../kvzap/)、[evaluation/](../evaluation/) | KVzap 相关训练/数据脚本；上游评估入口 | 追溯前端实现与 benchmark，不等于当前已完成正式评测 |
| [hardware/route_a/chisel/](../hardware/route_a/chisel/) | Chisel 硬件源码、测试和部分导出；`src/main` 是源码，`src/test` 是测试 | 找具体 RTL 行为或有界测试 |
| [hardware/route_a/dc/](../hardware/route_a/dc/) | 综合、STA、冻结和产物检查脚本 | 追溯某次映射条件；先看对应结果，不把脚本存在当成实验通过 |
| [hardware/route_a/mem/](../hardware/route_a/mem/)、[payload/](../hardware/route_a/payload/) | 存储 proxy 工具和 payload 配置 | 找成本模型的假设与覆盖范围 |
| [tools/](../tools/)、[tests/](../tests/) | 大量阶段性分析工具及其 Python 测试 | 由阶段报告反查对应脚本；文件名相似不证明能互相替代或可以删除 |
| [traces/](../traces/)、[papers/](../papers/) | trace 与原论文 | 核查原始输入和研究背景；大数据不一定被 Git 跟踪 |

硬件里可先从 [顶层](../hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala)、
[增量控制](../hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala)、
[共同控制](../hardware/route_a/chisel/src/main/scala/kvpress/routea/common/RouteACommonSkeletons.scala)、
[持久页测试](../hardware/route_a/chisel/src/test/scala/kvpress/routea/RouteAPersistentPageReadSpec.scala)
进入；不能把这些文件当作实现的全部依赖。

## 如何区分当前资料和历史资料

1. **结果或冻结文件**回答“当时实际完成了什么”；先看实验范围、run ID 和输入，再引用数值。
2. **规格和接口合同**回答“该版本要求什么”；不能把候选合同或参考模型当成已实现功能。
3. **launch/准备/失败记录**解释过程与可复现性；旧 launch 上的“正在运行”只表示当时的快照，
   要查同 run 的最终结果。失败记录仍有价值。
4. **导航/交接文件**帮助找到资料，可能随时间积累；本总览也有日期。若概括与指定实验
   的最终结果冲突，查看该结果的输入与验收，不按文件名新旧直接覆盖。
5. 根目录 `AGENTS.md` 及部分旧文档保留了“尚未进入 RTL”等历史阶段描述；后续明确授权
   的 RTL 与 DC 工作及各自验收实际存在。不要把当时的下一步自动当成今天的进度，
   也不要据此改写冻结记录。

要完整追踪时，再读 [文档地图](route_a_document_map.md)、
[当前交接](route_a_current_handoff.md)、[架构规格](architecture_spec.md)；
不需要每次从头读完全部文件。详细研究过程与依赖缺项见
[深层复审](route_a_deep_review_20261107.md)。

## 管理现状与保留原则

2026-11-11 本地只读快照：Git 跟踪 1,584 个文件，其中 `analysis/` 581、`tools/` 290、
`tests/` 293、`hardware/` 234；`analysis/` 中可见 339 个 Markdown，
`analysis/experiments/` 有 405 个直接子目录。这些是盘点数，不是有效实验数、唯一
成果数或冗余文件数。`analysis/experiments/` 约 7.3 GB，
`hardware/route_a/chisel/build/` 约 19 GB，`.venv/` 约 5.1 GB；本地大小会变化。

很多实验数据及构建输出被忽略，不会随普通 Git push/clone 自动保存；一个结果文件、
一份 manifest 和它所指向的原始制品必须分开看。11 月 7 日复审也记录了部分传递依赖
缺项，本次没有重新核验全部文件或远程备份。**不要在确认依赖、恢复方式和保存位置
之前批量删除、移动或归档。**

整理时工作树已有 9 个 `.github/` 文件的删除改动，本整理不判断其来源，也不恢复或
提交这些改动。此信息是当时快照，之后应以 `git status` 为准。

今后每次完成一项工作，可只更新本页的当前状态和相关权威入口；具体日志、hash 和
逐项证明放在该实验自己的记录中。旧记录不因导航简化而删除。对于疑似冗余代码，
先确认调用方、冻结依赖和验证覆盖，再决定是否需要单独整理；本次尚未逐文件判断
可删性，也没有修改生产代码、运行研究实验或操作远程任务。
