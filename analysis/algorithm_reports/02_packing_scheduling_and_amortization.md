# R2：Packing、调度与摊销

整理日期：2026-11-12。范围：Route-A的A0—A3.20探索。固定Qwen3-8B官方KVzap
MLP、threshold −4、hot window128；原始mask不变。本报告提炼已有数据，未重跑模型。
文中容量、bytes、cycles和利用率均按各阶段声明的模型解释，不是硬件实测。

## 1. 先用直白的话说明这一阶段

[R1](01_reproduction_and_route_selection.md)发现：保留的token很零散，但把它们紧凑
存放有较大的容量机会。R2继续问：**为了以后少读KV，先搬运、打包和管理一次，
这笔开销能不能赚回来？机器能不能把不同head长短不一的工作合理分配？**

可以把packing理解成整理仓库：留下的东西重新装箱，空位变少了；但整理要花时间，
装好后还要查箱号。如果只取货一次就结束，整理可能不值得；后面取货很多次，
每次少搬一些，才可能赚回来。有人东西多、有人东西少，又需要安排谁先做什么。

本阶段得到的答案是：**容量机会能够保留；部分调度能改善负载；回本取决于未来
读取次数和实际服务成本。长请求有模型中的正向区域，短请求和错误的长度承诺
确实可能亏损。** 它支持继续验证可执行后端，没有证明任意请求都获益。

| 推进阶段 | 实验目的 | 计划与尝试 | 结果如何推动下一步 |
|---|---|---|---|
| A0 | 打包后是否仍接近原逻辑压缩？ | 45条静态mask，page16/32/64/128，统计尾页与metadata | 容量损失较小；下一步考虑长短不一的head怎么执行 |
| A1 | 调度能否回收不均衡？ | static head、length-aware whole-head、dynamic page；离线batch1/2/4/8 | whole-head在部分点有效；dynamic page的merge可能抵消收益 |
| A2 | 一次packing后到底还会读多少次？ | 不改dense生成，记录创建、maturity、admission和decode长度 | 得到有时间顺序的输入，发现实际输出长度差异明显 |
| A3初始与edge | 加入搬运和执行成本后还赚不赚？ | Full-KV→ideal→实际分配→调度，扫描带宽、PE和admission服务 | 少读bytes不一定少cycles；admission可成为瓶颈 |
| A3.5—A3.11 | 持续admission、pending和延迟启动是否可自洽？ | shadow打包、分批预算、双源读取、bank/burst/staging、可观察gate及逐位置分支重放 | 明确“继续整理但读dense”和“完全延迟整理”不同，不能借用另一条分支的状态 |
| A3.12—A3.15 | 怎样保护短输出？ | 跨workload比较、零admission对照、请求cap及高cap早停反例 | cap是上限，无法保证剩余长度 |
| A3.16—A3.19 | 外部承诺多长才足以回本？ | 最小continuation、共同配置、违约与逐前缀检查 | 有条件可行，但承诺必须可信，短前缀余量很小 |
| A3.20 | 没有承诺时，延迟启动能否消除风险？ | 同一候选点密集扫描D=0…32，检查最终值与每个前缀 | 长样本最终为正，中途仍有亏损窗口；没有得到普遍安全策略 |

## 2. A0：先检验打包后的容量，而不是直接推断加速

**目的与计划。** 使用R1冻结的45条predictor-only trace，把每个layer/head的cold
保留项依序装进固定page，最近128条hot仍规则保存。比较page大小、总分配槽位、
冷页数量、尾页空槽和metadata。这里是最终mask的静态重放，没有在线admission。

| Page tokens | 分配槽位压缩 | 加16 B/cold-page metadata后的压缩 | Cold槽位碎片 | 45请求冷页总数 |
|---|---:|---:|---:|---:|
| 16 | 2.9502× | 2.9448× | 0.39% | 1,719,421 |
| 32 | 2.9384× | 2.9357× | 0.81% | 863,351 |
| 64 | 2.9147× | 2.9133× | 1.66% | 435,406 |
| 128 | 2.8660× | 2.8654× | 3.39% | 221,617 |

同一批请求的理想逻辑压缩为2.9609×。上表是对所有请求条目求总量的加权结果，
不是R1中head capacity bucketing的request均值。KV按512 B/(layer,KV-head,token)
计；cold碎片分母是已分配cold槽位，压缩同时包含hot存储。

原结果的`physical_compression_factor`实际是总逻辑槽位/总分配槽位，**没有加上
单独报告的metadata bytes**；上表第二列费用后的压缩由原byte列直接加回计算。
每head的page数为`ceil(cold_kept/P)`，因此page小会减少尾页空槽，却增加页和
metadata数量。原始数据：[A0汇总](../experiments/longbench_balanced_v2_route_a0_packed_pages_01/packed_page_replay_summary.csv)。

**分析。** 原始mask不规则不妨碍容量紧凑，但这只回答“装得下多少”。page64是
后续研究的候选折中点，不是已证明的全局最优。打包搬运、查表、调度和控制成本
还没有被这张容量表覆盖，必须分别计账。

**现有代码入口。** [packed-page 重放脚本](../../tools/simulate_kvzap_packed_pages.py)
先通过 [trace 分析工具](../../tools/analyze_kvzap_trace.py)读取并检查已有predictor-only
trace，再由 `PackedKVSimulator.replay` 按layer/head计算hot、cold pages及尾页；
`replay_trace` 汇总单请求与逐head结果，`replay_traces` 汇总多个请求和page大小，
最后写出请求、逐head和分组三个CSV及运行说明。SnapKV静态布局分析也复用
`PackedKVSimulator`，因此保留原类和字段接口。输入trace与历史结果无需移动。

运行入口为 `python -m tools.simulate_kvzap_packed_pages TRACE目录 --output-dir 新目录`；
可选 `--pilot-manifest` 提供分类信息，`--page-tokens` 指定page大小。输出中的
bytes是参数化容量估计，不是实际显存或HBM测量。

## 3. A1：任务分得细，不一定完成得快

**目的与计划。** 将A0的每head长度/page数变成工作量，比较三种策略：固定head归属；
按长度把整个head交给较空闲引擎；把head拆成page分发，再合并partial attention。
扫描8/16/32/64个PE、四种page和离线组合的batch1/2/4/8。layer之间有顺序屏障，
只允许同层已进入batch的请求共同调度；不是原生多请求服务实验。

下面选取page64、8 PE这一具体点，展示收益与代价：

| 离线batch | 策略 | 完成周期P50 | 完成周期P95 | 有效工作利用率 |
|---|---|---:|---:|---:|
| 1 | Static head | 86,619 | 234,096 | 41.37% |
| 1 | Whole-head按长度分配 | 86,619 | 234,096 | 41.37% |
| 1 | Dynamic page | 102,147 | 296,861 | 93.28% |
| 4 | Static head | 417,822 | 648,987 | 41.46% |
| 4 | Whole-head按长度分配 | 199,231 | 302,157 | 85.94% |
| 4 | Dynamic page | 499,121 | 810,299 | 94.14% |

该点采用声明的1024 B/cycle、4096 ops/cycle、512 ops/KV条目；每page metadata
lookup为1 cycle，每dynamic任务dispatch为2 cycles，额外segment串行merge为8 cycles，
whole-head dispatch设为0。完成周期包含merge；利用率只按PE工作阶段计算，
**不包含之后串行merge的时间**，因此不能把94%当成整条路径的有效吞吐。

45条请求按源顺序离线组合，batch4共有12组，最后一组不足4条仍保留；表里的P50/P95
是batch完成周期的分位数，不是单请求延迟。来源：[A1汇总](../experiments/longbench_balanced_v2_route_a1_scheduler_01/scheduler_summary.csv)
及同目录`scheduler_manifest.json`。

**分析。** batch1时8个KV heads对应8 PE，把整个head换个顺序不能解决长head的尾部，
所以该点whole-head与static相同；batch4有更多head可重新分配，whole-head明显改善。
Dynamic page虽然让PE更忙，却引入更多分发和合并，总周期反而更高。结论是应比较
包含开销的完成时间，而不是单看利用率，也不能外推某种调度始终最好。

**现有代码入口。** [A1调度脚本](../../tools/simulate_kvzap_route_a1_scheduler.py)
的 `load_a0` 读取A0逐head CSV和运行说明；`PageCostModel` 根据已声明的带宽、
计算吞吐和metadata成本计算任务时间；`simulate_workloads` 构造模拟batch并调用
static、whole-head LPT或dynamic-page调度，最后输出逐layer、逐batch和汇总CSV。
可用 `python -m tools.simulate_kvzap_route_a1_scheduler --a0-dir A0目录 --output-dir 新目录`
运行；page、PE和batch的扫描范围及各项开销均由参数指定。

**请求完成时间统计修复与重算。** 旧代码按任务首次调度时的出现顺序保存请求
完成时间，跨层汇总时却按batch顺序相加；不同层排序不同时会混淆请求身份。
最小的两请求、两层例子中，两请求原本各为10 cycles，旧算法却汇成18和2。
现已按trace ID对应，并使用原A0的45条请求、原page/PE/batch/策略和成本参数
完整重算；原结果不覆盖，[修正后A1结果](../experiments/route_a1_request_finish_corrected_20261112_r1/scheduler_summary.csv)
与[旧A1结果](../experiments/longbench_balanced_v2_route_a1_scheduler_01/scheduler_summary.csv)并存。

逐层结果148,608行全部一致；4,128条batch结果中383条发生变化，均为
length-aware whole-head策略的batch 2、4或8，变化只涉及跨层请求local-finish
的CV、P50、P95和max。192条汇总中48条的local-finish CV均值变化；本批
static-head、dynamic-page及batch1未见差异，但不能据此推断其他输入均不会受影响。

例如page64、8 PE、batch4，whole-head的请求local-finish CV均值从约2.261%
修正为2.295%；batch makespan P50/P95仍为199,231/302,157 cycles。上表的
makespan、利用率及“dynamic page的分发和merge抵消部分收益”的结论不变。
这里local finish仍是各层PE局部完成偏移的和，不包括串行merge，也不是
端到端单请求延迟；重算不能用来声明真实请求公平性或硬件性能。

## 4. A2：从最终mask走向实际decode生命周期

**目的与计划。** 静态mask不知道一个KV在创建后何时离开hot窗口、何时需要打包、
之后又被读多少次。于是增加read-only observer，在正常dense Full-KV生成时观察
score和maturity，再离线模拟drop/admission/page，不改变模型的attention选择。
用正常、观察但不记录、观察并记录三个路径检查生成与事件一致性。

| 样本 | 输出cap | 观察到的decode calls | 如何解释 |
|---|---:|---:|---|
| 内置retrieval | 32 | 8 | 提前结束 |
| Qasper row37 | 32 | 17 | 自然早停，后续关键负例 |
| GovReport row96 | 32 | 31 | 达到配置上限附近的观察前缀 |
| 2WikiMQA row62 | 32 | 5 | 很短的输出 |
| GovReport row109 | 128 | 127 | 达到配置上限的长前缀 |
| GovReport row180，两次运行 | 128 / 256 | 127 / 255 | 同输入的有界扩展，不能解释成两条独立请求 |

这里的call是生成过程中`q_len=1`的模型调用，不等于文本重新tokenize后的长度；
prompt/question forward已生成第一个token。冻结记录有7次收集，但包含同输入的
不同cap，不能称为7条独立自然长度样本。来源：[A2冻结](../route_a2_lifecycle_freeze.json)。

row180的255-call前缀在P64下得到约2.9502×容量压缩，cold-page碎片约2.11%；第二段
128 calls中观察到14,100次admission/36,864个layer/head maturity槽位，约38.25%。
这说明decode期间的新增工作非零，但prefill仍占总maturity/admission的大部分。
**不能只算decode中少量新token的打包，而漏掉prefill历史的启动成本。**

**分析。** 生命周期输入建立了“先付费、后省读”的时间顺序，也暴露输出长度风险。
但dense生成始终权威，A2不是实际执行稀疏attention或验证裁剪精度，功能软件后端
要到后续R3才验证。

**代码入口与边界。** 真实模型采集由[生命周期采集入口](../../tools/run_kvzap_decode_lifecycle_trace.py)
调用[只读观察器及生命周期状态](../../kvpress/lifecycle.py)：正常dense生成时观察
predictor分数，再由软件模拟maturity及admission。事件中的page、admission及bytes
是根据这些观察计算的模型账目，并非物理packing控制器或HBM计数器。
[生命周期校验](../../tools/validate_kvzap_decode_lifecycle_trace.py)检查已有记录；
[离线page重放](../../tools/replay_kvzap_decode_lifecycle_pages.py)的 `replay` 对单种
page重建状态，`replay_page_sizes` 对多种page汇总，输出事件、最终状态和摘要。
它不再加载模型或重新预测，也不改变原始admission决定。

## 5. A3：少读bytes，不一定减少执行周期

**目的与计划。** 在相同生命周期上建立四层对照：Full-KV；零管理成本的ideal packed；
按实际页分配的packed＋static；再加入whole-head调度。把启动搬运、后续读写、
metadata、queue/dispatch和计算/带宽上限显式计入，并扫描page、带宽、PE等条件。

一个早期模型点：P64、8 PE、1024 B/cycle、head dispatch4 cycles、queue64 B/head。
下表取packed＋static，展示同一个模型里的反差：

| Workload | Decode calls | 累计bytes节省 | 累计cycles节省 |
|---|---:|---:|---:|
| Qasper row37 | 17 | +57.61% | −46.06% |
| 2WikiMQA row62 | 5 | +39.84% | −189.25% |
| GovReport row109 | 127 | +63.74% | +4.09% |

来源：[初始跨任务模型](../experiments/route_a3_conservative_cross_task_01/a3_baseline_summary.csv)。
负189.25%表示候选模型周期约为Full-KV的2.89倍，不是负执行时间。原表
`break_even_decode_step`按**累计bytes**计算；它标为第2步不意味着cycles第2步回本。
周期节省应独立检查，不能混用两个门槛。

最简单的固定工作量近似为`回本读取次数=一次admission费用/每次读取节省`，
仅在分母为正、前后费用同单位时适用。真实重放中head长度、pending、页分配和
服务竞争都随调用变化，因此应逐前缀检查`累计Route-A费用≤累计Full-KV费用`。
容量压缩、字节回本和周期回本应分别报告，不能用字节回本点替代周期回本点。

**分析与承接。** 更快的attention引擎可能使一次性admission反而主导关键路径。
因此A3-edge进一步把共享packing引擎数量、每引擎bytes/cycle、burst取整、page setup
和服务窗口分开扫描。这里的早期负结果是模型发现，不是工具运行失败；也不能将
它与后面不同服务模型的40%节省直接相减，称为实现优化幅度。

**离线计算入口。** [A3 traffic/cycle脚本](../../tools/simulate_kvzap_route_a3_traffic.py)
读取A2事件和对应page重放，`build_rows` 按call/layer/head对应记录，`simulate`
按decode step计入一次性及持续admission、读取、metadata和调度成本，再输出
逐步结果、累计节省及byte回本点。A1在此提供调度策略和成本口径；A3自己重新计算
单请求逐步cycles，不读取A1的batch请求完成时间或CV。A1公平性统计修复因此不
自动改写既有A3结果。这里的bytes/cycles和回本仍是指定假设下的离线模型。

## 6. A3.5—A3.11：把持续admission和pending读清楚

**目的与计划。** 一次性把历史全部搬走可能产生大启动突发。先建立shadow打包参考，
保持dense attention权威，实际组织独立packed副本；再将逐head提交改成逐layer分批，
明确planning、submission和GPU envelope。随后加入oldest-first FIFO和每call/layer
最多处理B条的预算，避免把整段历史瞬间清空。shadow计时是软件组件观察，不能
当成硬件服务率，也没有直接导入下面的硬件周期模型。

GovReport row180、defer5的预算比较：

| 每call/layer预算B | 实际单批最大处理数 | 批处理bytes P99 | 最大pending/layer | 观察结束剩余pending |
|---|---:|---:|---:|---:|
| 256 | 256 | 128 KiB | 28,404 | 0 |
| 512 | 512 | 256 KiB | 28,404 | 0 |
| 1024 | 1024 | 512 KiB | 28,404 | 0 |

三点累计处理452,503条，均在该前缀结束前排空；单条按512 B计。来源为
`route_a35c_govreport_n5_budget{256,512,1024}_01_analysis/admission_budget_summary.json`。
**B是每次服务量，不是pending总容量。** 最大pending相同，表明初始积压不能靠
设置一个较小batch预算就消失；处理得更快也不自动证明缓冲足够小。

接下来的探索围绕五个实现问题推进：

| 阶段 | 问题和尝试 | 必须保留的判断 |
|---|---|---|
| A3.6 | 尚未打包的保留项放在pending，已打包项在cold pages；比较hybrid与等待FIFO清空才启用packed | pending读、索引和partial-softmax merge都必须计费，不能只读已打包部分 |
| A3.7 | 增加bank、burst、pending mapping、staging容量，以及逐layer的hybrid/Full-KV选择 | 同call看完成本再选择属于oracle式对照；bank/burst是声明假设，不是实际HBM测量 |
| A3.8 | 用attention前可见的pending深度、预计bank突发和overflow代替oracle | 与oracle一致率高也不保证累计收益为正；阈值需要跨workload验证 |
| A3.9 | Full-KV只作为读取fallback，但admission继续并在两种读路径都计费 | 不能一边暂停付款，一边继续使用另一路已经打包好的未来状态 |
| A3.10—A3.11 | 若真的延迟admission，则记录原保留位置，逐head重放各分支FIFO/page，再计bytes/cycles | 每种启动策略必须有自己的状态演化；不能复用continue-admission分支的packed状态 |

例如A3.9固定pending阈值2048、bank突发阈值128的跨workload比较中，各有72个声明
硬件点：Qasper最差cycles节省−1.43%，均值−0.29%，即使平均仍省约9.69% bytes；
两个GovReport样本的最差cycles节省则分别为+17.34%和+41.24%。这保留了
“短请求/启动成本没有被gate普遍解决”的负结果。来源：
[A3.9跨workload结果](../experiments/route_a39_cross_workload_b512_01/cross_workload_gate_summary.csv)。

## 7. A3.12—A3.15：等待一会儿，或者看cap，仍不能保证安全

**目的与计划。** 使用各分支真实重放状态后，再比较相同硬件点下的不同workload。
为了避免短请求先花packing成本，尝试延迟D个decode calls，以及按调用者提供的
`max_new_tokens`判断是否启动。另设完全不admission的Full-KV对照。

两项关键结果：

- 在17-call请求上，defer16仍可能在最后一次attention之后开始admission，已经没有
  足够后续读取偿还成本。只有整个请求不启动，才能退化为零admission的Full-KV对照；
  用已知完整trace长度做到这一点是诊断对照，不是在线长度预测器。
- 同一个Qasper row37，将cap从32提高至128，仍只执行17个decode calls，答案相同，
  留下111个未用cap额度。高cap允许“最多生成很长”，没有承诺“至少还会生成很长”。

来源：[高cap早停对照](../experiments/route_a315_retrieval_cap128_mismatch_01/cap_mismatch_summary.csv)。
这否定了仅靠cap保证回本的假设，而不是否定所有deferred policy。真正的选择是：
接受投机亏损风险，或使用可信的未来工作下界，或走整请求Full-KV bypass。

## 8. A3.16—A3.19：有可信continuation时，条件性回本区域是什么

**目的与计划。** 将“允许的输出上限”改成外部API/调度器承诺的最小continuation。
模型只用声明作选择，实际trace长度用于事后检查承诺是否兑现；它不是从完成的
trace推断出的在线特征。短Qasper声明0，三条长摘要声明64，对齐同样的硬件点。

以下为一个固定候选：P64、oldest-first budget512/(call,layer)、16 banks、burst64 B、
64 B/cycle/bank、round_robin_token pending mapping、staging8192条/layer。
这些是声明参数，不是当前RTL已实现配置或宏/端口/频率证据。

| 初始延迟D | 三条active长样本的最小最终cycles节省 | 共同观察到的非负前缀要求N | 在该N处最小节省 |
|---|---:|---:|---:|
| 0 | +40.96% | 22 calls | +0.98% |
| 5 | +39.04% | 27 calls | +0.78% |
| 16 | +34.88% | 38 calls | +0.77% |

短样本bypass的节省为0，所以包括它在内的四workload最小值也是0，不能写成
“所有请求至少改善40.96%”。N是从这些已观察轨迹求得的最早位置，使其后**直到
已观察终点**的每个累计前缀均非负；不是对任意未来轨迹的安全保证。前缀第一次
转正时的余量不到1%，也不是宽裕的部署预算。

**违约负例。** 把已知17-call短Qasper虚假赋予64-call承诺后，defer0的最差模型节省
变为−10.99%；defer5和16分别为−18.65%和−3.91%。等待更久没有单调消除亏损，
因为启动时积压与剩余读取机会都在变化。这是反事实性能敏感性，不是一次新的
裁剪质量实验，也不能把虚假声明行当成有效部署条件。

来源：[共同策略结果](../experiments/route_a317_cross_longoutput_contract_policy_01/contract_policy_sweep_cross_summary.csv)、
[前缀门槛](../experiments/route_a319_long_summary_prefix_contract_01/prefix_contract_cross_summary.csv)、
[违约结果](../experiments/route_a318_contract_breach_summary_01/contract_breach_cross_summary.csv)。

## 9. A3.20：没有承诺时，长样本的终点收益会掩盖启动亏损

**目的与计划。** 普通请求未必能提供可信continuation，因此保持上节同一候选配置，
独立密集扫描D=0…32。逐项计算最终节省和每个已观察前缀，而不是只挑几个有利D。

| Workload | 已观察decode calls | D=0最终cycles节省 | D=16最差前缀节省（出现call） | D=16首次恢复非负call |
|---|---:|---:|---:|---:|
| GovReport row109 | 127 | +40.96% | −10.59%（23） | 38 |
| MultiNews row129 | 127 | +42.02% | −2.90%（23） | 31 |
| QMSum row44 | 91 | +46.56% | −1.83%（20） | 25 |

三个样本所有33个D在最终观察点都为正，D0均最好。但这组只包含较长摘要；GovReport
和MultiNews达到128-token cap附近，只能称有界长前缀，不能称已测完整自然输出长度。
它既不能取代17-call早停负例，也不能估计真实请求中亏损有多常见。

**分析。** 没有承诺的defer策略是投机：启动前不付packing费，启动后出现一次亏损，
继续读取才有机会恢复。等待本身不创造剩余工作量；收益取决于何时结束。
来源：[最终D曲线](../experiments/route_a320_longoutput_speculative_curve_local_01/speculative_defer_final_curve.csv)、
[逐前缀曲线](../experiments/route_a320_longoutput_speculative_curve_local_01/speculative_defer_prefix_curve.csv)。
这里的cycles savings是`(Full模型周期−候选模型周期)/Full模型周期`，不是tokens/s
提升率，更不是实测加速倍数。

## 10. 阶段结论、留下的问题与数据来源

R2建立了三件事：原mask的packing容量机会较好；whole-head等调度在适当条件下
能改善不均衡；显式计入admission后仍存在有条件的正收益模型区域。同时保留了
四个负判断：高利用率不等于低完成时间、省bytes不等于省cycles、cap不等于未来
长度保证、长样本最终回本不等于所有前缀或所有请求回本。

这些结果**没有证明完整后端已实现、真实HBM少读、实际推理加速或硬件净收益**。
早期模型也不能替代后面R6统一公平GQA和差分成本口径的最终账本。P64、budget512、
N22及长摘要上的40%—47%都属于指定模型/轨迹，不能当通用常数或当前RTL指标。

因此研究推进到R3：让hot/pending/packed与partial-softmax merge实际执行，验证给定
mask的attention数值和状态；之后还需要解决真实存储/控制成本与共同服务时序。
R2本身的正向模型不要求把Route-A无限推进，也不排除未来重新评估Route-B。

本报告直接引用原结果，未来绘图/复核保留：A0的逐请求和逐head replay、A1的
layer/batch/summary与cost manifest、A2的lifecycle事件和page replay、admission shadow
的task/head-progress/位置记录、A3各候选配置与逐步ledger，以及A3.17—20的逐workload/
逐前缀表。它们均在正文链接的原实验目录及[A2冻结](../route_a2_lifecycle_freeze.json)
指向的目录中。只保留本报告中的均值/几个模型点，不足以恢复全部曲线。

复核时按正文直接进入A0容量表、A1调度表/参数、A2冻结所指的事件，以及A3逐步
ledger和前缀曲线；A3.20的[分析实现](../../tools/analyze_kvzap_route_a320_speculative_defer_curve.py)
保留了D扫描与前缀口径。静态mask、dense生命周期、shadow副本和分支重放是不同
证据层次，不能把它们拼成已经运行的持续稀疏后端。研究顺序和条件性判断已在
本文给出，理解本阶段无需再读旧计划或交接；原始数据仍保留原位。
