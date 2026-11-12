# R3：功能参考与执行观察

整理日期：2026-11-12。范围：A4.0、A4.1软件功能/测量支线及A4.2的接口与事件观察，
固定Qwen3-8B官方KVzap MLP、threshold −4、hot128、page64。本文提炼已有记录和
原始结果，未重跑模型。软件实验中的全层功能与后来的RTL功能范围分别成立，
不能把这里的数值验证或软件时间直接赋给现有硬件。

## 1. 这一阶段想把什么事情真正做出来

[R2](02_packing_scheduling_and_amortization.md)找到了packing可能回本的模型条件，
但模型默认这些事情能执行：保留项从hot进入pending，再被打包；attention可以
同时读取不同位置的数据；最后把结果正确合并。R3就是把这条路径做成软件参考，
确认“模型里说能做”与“真正执行时发生什么”之间的差距。

可以把它理解成：前面已经画好仓库分区并算过运输账，这次实际按分区取货，检查
有没有遗漏、重复、顺序错误，随后观察取货和整理本身花多少时间。

**本阶段得到的结论是：在明确的固定mask、请求和数值容差下，三源attention及
external-cold存储参考能够执行；但这份Python参考没有展示软件加速，部分配置显著
更慢。** 执行观察还揭示了哪些工作可共享、哪些必须逐query独立完成，以及资源
设计尚缺哪些信息。

| 推进阶段 | 目的与计划 | 主要发现及下一步 |
|---|---|---|
| A4.0 | 从无模型harness、单层单head，逐步替换到36层/8 KV heads | 三源合并有有界数值对应；独立在线mask会少量分歧，转为固定mask配对 |
| A4.1早期组件/整段测量 | 区分组件开销和完整执行时间 | 参考较慢，而且早期仍保留dense cold副本，需要先证明数据真正由Route-A提供 |
| Cold ownership及数值扩展 | 使原生cold不可被偷偷读取，覆盖多token question、全head和全层 | 修正对照/bridge边界；局部微小舍入差可向后传播，数值标准必须显式定义 |
| 真正的cache接口替换 | 区分逻辑长度和物理存储，移除持久selected native cold | external-cold职责得到功能验证，但transient view和软件开销仍存在 |
| 执行模式与空源省略 | 将验证工作移出计时，跳过空pending/packed计算，重复配对测量 | 空源省略有局部软件收益，完整三路径比较仍明显慢于Full-KV |
| A4.2 | 从profiler汇总推进到有序事件、fan-in与GQA共享边界 | 可以明确接口依赖；调用顺序不是完成时序，仍不能据此选硬件队列和带宽 |

## 2. 先分清三个比较对象

| 路径 | 它做什么 | 用来回答什么 |
|---|---|---|
| Full-KV bypass | 使用完整KV，零Route-A admission | 不启用本方案的对照；无需与裁剪路径输出相同 |
| Same-mask dense KVzap | 按固定KVzap mask保留数据，用dense保留项参考计算 | 检查同一选择下的数值和存储路径差异 |
| Same-mask Route-A | 相同mask，按hot/pending/packed取数并合并 | 检查packing后的功能与执行开销 |

**代码关系。** 无模型入口 [run_kvzap_route_a4_reference.py](../../tools/run_kvzap_route_a4_reference.py)
调用[共享功能参考](../../kvpress/research/route_a.py)：调用者提供K/V和keep mask，
`RouteAPackedAttentionState` 管理hot/pending/packed，分源计算后用online-softmax
合并。该入口的dense计算使用**同一Route-A状态导出的记录**，主要检查分源计算和
合并，不能独立证明记录没有被遗漏；保留的测试另用原始输入和mask直接构造参考。

原 `kvpress.route_a_attention` 路径继续提供兼容导入。

真实模型入口 [run_kvzap_route_a40_policy_gate.py](../../tools/run_kvzap_route_a40_policy_gate.py)
通过 [route_a_policy_backend.py](../../kvpress/route_a_policy_backend.py) 将参考状态接入
选定的模型attention层。它包含Full-KV bypass、独立online dense同mask参考与
Route-A路径；只有显式启用配对及mask replay时，后两条才复用同一决策。
后续external-cold路径还使用[存储adapter](../../kvpress/route_a_external_cold_storage.py)
和[Qwen cache适配](../../kvpress/route_a_qwen_cache.py)，以检查所选cold数据归属。
这些代码是软件功能原型，不是RTL、物理存储控制器或性能加速实现。

后续固定mask配对中，后两者共用一份计时外采集的mask事件，要求每个事件恰好消费一次。这样才能把
“选择了不同token”与“同样token换一种存储和计算组织”分开。

独立在线dense与Route-A初始对照曾出现**5/268,992个threshold决策翻转**。这使得
两次独立运行不能直接叫same-mask，也不能把固定mask replay说成在线predictor
永远一致。后续配对固定了决策，保留这项局限。来源：
[在线mask诊断](../experiments/route_a40_policy_on_qwen_all_layers_dense_drift_02/a40_online_mask_drift_diagnostic.json)。

## 3. A4.0：把hot、pending、packed真正用于attention

**目的与计划。** 无模型参考先覆盖hot保护、maturity、oldest-first、空源、尾页、
跨页及不同head长度；再做真实Qwen的read-only比较，之后逐步替换单层单head、
单层全head、早中晚层`{0,18,35}`，最终覆盖36层和8 KV heads。

三类源各自计算局部attention统计，再用数值稳定的online-softmax合并。它不是
简单平均三份输出：不同源的局部最大值、归一化量和value累积必须正确加权，
最终对应于把相同保留KV放在一起做dense attention。

初始全层replayed-mask检验采用budget1以显式制造未排空pending：

| 观察项 | 结果 |
|---|---:|
| 覆盖 | 36层×8 KV heads×7 decode calls |
| Dense / Route-A比较数 | 各2,016 |
| 实际读取pending的比较行 | 1,696 |
| 实际读取packed的比较行 | 1,383 |
| 最大FP32差 | 1.5259×10⁻⁵ |
| 最大执行dtype ULP诊断 | 13，配置界限16 |

pending与packed覆盖行可以重叠，不可相加当作不同attention数。该请求三路径答案
恰好相同，只能按该请求记录，不能提升为普遍准确率结论。来源：
[全层paired功能结果](../experiments/route_a40_policy_on_qwen_all_layers_replayed_mask_01/a40_policy_on_qwen_manifest.json)。

**分析。** 已证明了指定场景中三源计算的功能可行，但尚未证明原生dense cache
没有被依赖，也没有建立低成本软件实现，因此进入ownership和测量研究。

## 4. 数值与ownership：检查“算得对”也要检查“读的是谁的数据”

### 4.1 从组件覆盖到真实cold来源

单层head0的budget1点最多观察到pending21条、packed1条；budget512点则为pending0、
packed22条。head6用于覆盖多页、完整page和tail。它们测试不同状态，不能把某个
head没有pending误作实现失败，也不能把跨调用的多个最大值拼成同一时刻状态。

早期模型仍有dense native cache，并额外维护Route-A副本。为确认Route-A没有偷偷
读取native cold，测试将selected mature native K/V置为不可用，再验证所选GQA组
仍能从Route-A源计算。这个方法证明读取归属，**不释放原生tensor，也不证明显存
下降**。

多token question forward曾暴露一个真实问题：仅替换`q_len=1` decode还不够，question
路径可能回落到native attention。因此增加逐token因果bridge，并让dense对照也走
相同mask语义，避免把“裁剪与不裁剪的差别”误认成packing数值误差。

### 4.2 局部误差小，不代表最后logits逐位相同

| 定向观察 | 结果 | 应保留的解释 |
|---|---|---|
| 单层head6、22-token bridge | FP32最大差约5.22×10⁻⁸，执行dtype约1 ULP | 支持该窄场景的同mask对应 |
| 单层全head | 最终logits最大差0.4492，首argmax相同 | 多个局部舍入差可能经后续层传播，不能要求所有中间值逐位一致 |
| 相同请求budget1与512对照 | 两种状态下逐层activation差异表相同 | 支持该场景差异来自数值传播，而非pending/packed布局选择 |
| 固定8-token forced与独立greedy对照 | 单层全head未观察token变化；最大paired logit差0.6406，最小dense top1/top2间隔21.5 | 本次差异未跨过决策边界，不代表其他请求也如此 |
| 首次严格全层ULP检验 | 近零值出现26 ULP，cast绝对差约3.03×10⁻⁹，FP32差约1.71×10⁻⁷ | 固定ULP界限对近零值敏感；原严格标准的失败仍保留 |

随后直接沿用FP32容差检查cast结果，也会拒绝可解释的相邻BF16舍入。因此另行
定义quantization-aware cast envelope：FP32同mask检查继续强制执行，cast输出还需
落在FP32容许量加双方局部dtype间距形成的显式界内；ULP超限则有界记录。
这是**版本化的数值验收标准**，不能称原16-ULP条件从此全部通过。

该标准下，全层budget1完成replay、ownership、bridge及forced/独立greedy检查，
原来7个大于16-ULP的事件仍记录。来源：[全层quantization-aware结果](../experiments/route_a4133_all_layers_budget1_quantization_aware_continuation_01/a4133_alllayer_quantization_aware_continuation_manifest.json)。
这些对照分别检查局部attention、后续logits传播与执行dtype误差；不能因为其中
一项通过，就将其余两项也判为通过。表中边界也是后续所有软件与硬件比较的前提。

## 5. Cache替换：让逻辑长度与实际保存的数据分开

**目的与计划。** 仅验证cold读取归属还不够，必须去掉持久native cold副本。
Stock DynamicCache的逻辑长度与tensor物理长度相连，直接切掉旧prefix会破坏位置
和mask。因此新增external-cold adapter及Qwen cache接口：显式记录逻辑长度，
selected hot由adapter保存，成熟保留项由pending/packed保存，成熟drop项不再持久
保存为selected native cold。

从单层单head、单层全head、三层推进到全层，并分别覆盖budget1 pending和budget512
page状态。全层结果要求36×8个selected head均被替换、selected persistent native
cold tensor条目为0、相关replay和数值检查通过。

来源：[全层budget1](../experiments/route_a4145_qwen_all_layers_allheads_budget1_quantization_aware_01/a4145_qwen_alllayer_allhead_quantization_aware_native_storage_manifest.json)、
[全层budget512](../experiments/route_a4146_qwen_all_layers_allheads_budget512_quantization_aware_pages_01/a4146_qwen_alllayer_allhead_quantization_aware_native_storage_page_state_manifest.json)。

**分析。** 这比“旁边多保存一份packed副本”更进一步，建立了真实存储归属的参考。
但兼容Qwen attention接口仍会构造临时dense形状view，权重、临时tensor和allocator
reserved状态也还在，不能由持久native cold为0推导实际显存按2.96×下降。
此处external指软件adapter持有cold数据，不代表已接入外部硬件存储控制器。

## 6. 软件测量：功能成立，参考实现依旧很慢

### 6.1 先区分测量范围

- 组件测试逐callback同步CUDA，用于归因；callback次数不是独立请求重复数，其
  时间之和不能当自然执行下的decode延迟。
- 整段测试每次重置cache，context prefill在计时外；同步计时question forward加
  greedy generation，排除warm-up后统计。它仍不是完整prompt-to-answer时间。
- Profiler另行捕获，不混入重复计时分布。含数值检查的调试执行与后续execution-only
  测量分开；后者依赖同配置、同source的前置功能资格，不能自行当作再次逐项验算。

### 6.2 有效的负结果不能省略

早期仅替换三层、仍保留dense cache的8-token实验，各路径10次reset-run，其CUDA
event均值为Full-KV0.2905秒、same-mask dense1.3478秒、Route-A1.6085秒。
Route-A比配对dense约慢19.3%。该配置的dense/Route-A allocator峰值相同，不能
据此声称packing没有容量价值，因为原native cache尚未移除。
来源：[早期整段测量](../experiments/route_a412_whole_decode_layers_0_18_35_budget512_01/a412_whole_decode_manifest.json)。

移除持久native cold并建立execution-only/空源省略后，对固定summarization请求的
全层三路径测量如下；均为10次有效reset-run，各有2次warm-up：

| 输出horizon | 路径 | CUDA event P50（秒） | P95（秒） | PyTorch peak allocated中位数（MiB） |
|---|---|---:|---:|---:|
| 16 | Full-KV bypass | 0.5691 | 0.5723 | 15,779.72 |
| 16 | Same-mask dense replay | 31.6138 | 31.8430 | 15,853.19 |
| 16 | Route-A external-cold＋空源省略 | 53.5347 | 53.7679 | 15,741.34 |
| 32 | Full-KV bypass | 1.1309 | 1.1350 | 15,779.72 |
| 32 | Same-mask dense replay | 42.6175 | 42.8819 | 15,853.19 |
| 32 | Route-A external-cold＋空源省略 | 72.5268 | 72.7688 | 15,741.34 |

来源：[h16三路径](../experiments/route_a4162_summarization_all_layers_budget512_three_path_02/a4162_cross_workload_three_path_measurement_manifest.json)、
[h32三路径的实际child结果](../experiments/route_a4166_summarization_all_layers_budget512_horizon32_three_path_02/three_path_measurement/a4162_cross_workload_three_path_measurement_manifest.json)。
两个horizon各自新采source，内部配对有效，但不能假定跨horizon mask逐字节一致。
两条same-mask路径在这两个固定horizon的token摘要相同，Full-KV输出关系另记，不
要求与裁剪路径相同。

**分析。** Route-A的P50约为配对dense的1.69/1.70倍；dense replay本身也比原生
Full-KV慢很多，说明这里测的是逐head/逐token Python参考与原生执行的巨大实现
差别。不能把表格包装成优化GPU kernel或硬件加速结果。

Route-A在该请求中比dense replay少约111.85 MiB peak allocated，但整段峰值包含
权重与临时分配，reserved峰值在各自三路径间相同。这个软件观察既不等于KV自身
的物理压缩率，也不代表HBM流量变化。不同年代/覆盖范围的测量不可拼成优化曲线。

## 7. Profiler与空源省略：把开销解释到实际调用

**目的与计划。** 先观察hot、pending、packed、merge、list/stack及管理路径；将
same-mask数值reference检查移出计时，再验证没有数据的源可返回显式skip，省去空
partial调用。正确性仍由匹配的功能实验限定，省略空源不能省略合法非空数据。

在固定retrieval的15个配对有效reset-run中，execution-only未省略版本CUDA event
P50约44.021秒，空源省略为38.562秒。逐配对candidate-minus-baseline中位数为
−5.849秒，15对全部为负，allocator差为0。这是**局部软件改进**，仍不代表对
Full-KV或硬件获得净收益。来源：[重复配对结果](../experiments/route_a4157_qwen_all_layers_allheads_budget512_empty_source_elision_reproducibility_01/a4157_empty_source_elision_reproducibility_manifest.json)。

summarization的h16/h32 profiler accounting给出：

| 指标 | h16 | h32 |
|---|---:|---:|
| Merge调用数 | 57,600 | 76,032 |
| Hot partial数 | 57,600 | 76,032 |
| Packed partial / skip | 55,200 / 2,400 | 72,864 / 3,168 |
| Pending partial / skip | 436 / 57,164 | 436 / 75,596 |
| 相对每次固定3 partial的调用省略比例 | 34.47% | 34.53% |
| 实际partial/merge | 1.966 | 1.964 |

来源：[跨horizon accounting](../experiments/route_a4168_summarization_cross_horizon_accounting_01/a4168_cross_horizon_accounting_report.json)。
这些数含question的多token因果bridge，不是仅生成16/32个token的单步成本，更不是
DMA/硬件操作次数。Hot、packed与merge在参考软件中仍是重要开销；分源执行使一次
dense attention变成接近两次partial加一次merge。Profiler的嵌套/重叠范围不能简单
加和成延迟；34.5%的partial省略不等于34.5%的总时间或能量节省。

## 8. A4.2：从“调用很多次”推进到可用的接口证据

**目的与计划。** profiler总量不知道三种源是否在同一次evaluation里同时存在，也
不知道工作何时完成。先声明同引擎source＋merge与split-source的不同接口费用，
再采集有序、无服务时间戳的逻辑事件；对齐workload的实际decode调用，重建依赖
和dispatch epoch，最后检查GQA共享范围。没有用聚合次数直接推队列深度。

### 8.1 A4.2.0—4.2.5：先分清放在哪里，再补充顺序证据

最初将hot/pending/packed和merge放在同一`(layer,KV-head group)`引擎，保持
head内归属，不产生跨引擎partial传输。split-source则让非空源分别服务，每个
源须输出局部max、归一化量、value累积及valid/empty信息，再由reducer合并。
潜在并行收益伴随额外dispatch、状态传输和在途存储；两种组织都仍只有一次逻辑merge。

A4.2.1只将既有A3的候选范围对应到观察到的接口，未选定硬件参数。
A4.2.2显式扫描partial payload16/64 B、传输/dispatch工作和状态容量轴；这些
是抽象敏感性标签，不是已经实现的partial格式。后续R6才声明每query的FP32
partial为520 B，不能拿早期16 B轴作真实数值数据通路的成本。
来源：[放置/传输模型](../experiments/route_a422_scheduler_merge_placement_01/a422_scheduler_merge_placement_report.json)。

A4.2.3发现边际调用量只能约束fan-in，不能恢复共同出现关系：h32共有76,032
次hot、72,864次packed、436次pending，仅凭这些总量，三源同时出现次数可以
在0—436之间。因此不能从调用均值直接推断merge队列；A4.2.4增加有序逻辑事件，
A4.2.5再保持源与merge依赖进行逻辑重建，仍未记录source完成或服务时间戳。
来源：[边际服务敏感性](../experiments/route_a423_scheduler_merge_service_sensitivity_01/a423_scheduler_merge_service_sensitivity_report.json)、
[有序逻辑重建](../experiments/route_a425_summarization_all_layers_budget512_horizon32_ordered_logical_schedule_02/a425_ordered_logical_schedule_report.json)。

### 8.2 A4.2.6—4.2.8：确切fan-in与同horizon比较

h32的76,032个事件被精确分为hot-only3,168、hot＋packed72,428、三源436，合计
守恒。它比仅知道pending和packed各调用多少次更精确，但依然不知道物理并发数。
来源：[确切fan-in](../experiments/route_a426_summarization_all_layers_budget512_horizon32_exact_fanin_01/a426_exact_fanin_distribution_report.json)。

随后三类请求均对齐cap8、实际7次policy decode，得到：

| Workload | 逻辑evaluation数 | 1源比例 | 2源比例 | 3源比例 |
|---|---:|---:|---:|---:|
| Retrieval | 33,408 | 4.17% | 94.07% | 1.76% |
| Summarization | 48,384 | 4.17% | 94.93% | 0.90% |
| Reasoning | 82,944 | 3.47% | 92.95% | 3.58% |

事件数仍不同，因为question bridge工作量不同；相同decode horizon不能直接形成
同一需求分布。来源：[matched-horizon三workload](../experiments/route_a428_matched_horizon_three_workload_budget512_cap8_01/a428_matched_horizon_workload_stability_report.json)。

### 8.3 A4.2.9—4.2.12：额外接口需求与背压，仍需声明服务假设

A4.2.9按上表同一组事件，对split-source数出以下工作：

| Workload | 逻辑merge数 | 需导出的partial状态数 | 相对每merge一个输入的额外reduction输入 |
|---|---:|---:|---:|
| Retrieval | 33,408 | 66,012 | 32,604 |
| Summarization | 48,384 | 95,188 | 46,804 |
| Reasoning | 82,944 | 165,976 | 83,032 |

单位是声明的接口状态/输入个数，不是bytes、总线事务或cycle。co-located对应
跨引擎导出为0，但本地partial和merge工作仍在。结果说明“把源拆开”不能只算
并行好处；还须算状态出口、reducer和数据生命周期。来源：
[匹配workload的接口需求](../experiments/route_a429_matched_interface_demand_01/a429_matched_interface_demand_report.json)。

A4.2.10使用声明的source/reducer工作量与容量轴1/2/4/8/16/32。修正版把一次
evaluation的全部源聚成一个fan-in merge task，容量单位不再是单个partial。
例如summarization在容量轴1、balanced服务下，背压task数为0；将reducer工作
从1改为2后，48,384个task中有48,383个经历背压。**是否积压高度依赖未校准的
服务假设**，既不能由前者宣布FIFO足够小，也不能由后者宣称真实硬件必然堵塞。
来源：[fan-in task背压模型修正版](../experiments/route_a4210_modeled_backpressure_envelope_02/a4210_modeled_backpressure_envelope_report.json)。

A4.2.11进一步比较global/per-layer/per-layer-KV-head放置、三种arrival合同、
flat/tree merge、并行轴1/2及容量轴1—16，每workload共180个模型组合。
改变放置也改变服务资源组织，不能把虚拟finish work的差值当作免费加速。
A4.2.12为其中的`trace_dispatch_epoch`补上依赖依据：三workload分别有
1,044/1,512/2,592个layer dispatch epoch，每epoch对应32条query-head事件；
它们使用同层append后的不可变source snapshot，而跨层仍保留顺序。原Python
调用是串行的，“同层允许重叠”只表示依赖上有资格，未观察真实并发执行。
因此这一支线最终保留了需求与敏感性，没有定下FIFO、引擎数或时钟。
来源：[分区背压敏感性](../experiments/route_a4211_partitioned_backpressure_sensitivity_03/a4211_partitioned_backpressure_sensitivity_report.json)、
[dispatch epoch依据](../experiments/route_a4212_dispatch_epoch_evidence_02/a4212_dispatch_epoch_evidence_report.json)。

### 8.4 A4.2.13—4.2.14：共享边界与接口收口

GQA检查进一步明确：同一source snapshot下，一个KV head对应的4个query heads
可以共用source/page-descriptor dispatch描述，但各query的partial-softmax和merge
状态必须独立。retrieval中独立dispatch控制单位66,012，对应共享描述16,503，
merge实例仍为33,408。**逻辑控制描述减少75%，不是已测控制面积或访问下降75%。**
来源：[同层KV-head-group共享边界](../experiments/route_a4213_same_layer_group_contract_01/a4213_same_layer_group_contract_report.json)。

最终A4.2.14收口了原mask、位置/归属、三源partial-or-skip、一次merge、跨层顺序、
共享dispatch与独立query状态等语义接口。仍未选择pending容量/overflow、PTE与
allocator/seal、bank/burst/gather、merge精度/PE调度、bypass/admission服务时序。
来源：[Qwen core-contract收口](../experiments/route_a4214_core_contract_closure_01/a4214_core_contract_closure_report.json)。

## 9. 这一阶段留下什么，下一步为什么转向资源与成本

**已建立：** 指定请求/数值标准下的三源功能对应；真正external-cold存储职责的
软件参考；软件时间、allocator及调用结构的观察；有界逻辑依赖与GQA共享边界。

**保留的重要负结果：** 独立在线mask翻转；早期原生cold/多token fallback问题；
局部舍入差传播与严格ULP标准失败；Python参考显著较慢；局部空源优化不能兑现
整体加速。没有用功能PASS代替性能，也没有用少量输出相同替代正式精度评测。

**仍未建立：** 优化GPU kernel速度、真实HBM流量、统一时钟下的存储服务、SRAM
端口/容量选择、RTL数值闭环、PPA或系统净收益。有序调用不能当物理完成时间，
逻辑source集合不能当硬件同时存活量，因此资源与成本仍须专门研究。

这解释了后续方向：先区分哪些语义可迁移到其他模型/前端（R4），再明确pending/
metadata的容量、归属与服务（R5），最后做同口径成本账本（R6）。

本报告仅保留一份正文。未来复核或绘图使用原目录中的功能manifest、mask replay
NPZ、`a41_raw_repetitions.jsonl`、测量summary、独立profiler、ordered JSONL及
fan-in/dispatch及背压敏感性结果；不要只保留本报告的P50或调用均值。
复核A4.2可直接使用正文各JSON；历史接口需求和分区敏感性分析脚本可从Git恢复。
输入/轴定义与结果里的config配对，不能用新假设覆盖旧结果。
上述研究解释已在本文给出，不再需要旧测量计划或纵向交接补充；原始资料保留原位。
