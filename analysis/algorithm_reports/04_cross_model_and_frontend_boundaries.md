# R4：跨模型与前端边界

整理日期：2026-11-12。范围：Llama M0—M6、SnapKV P0—P3/P2、官方训练DMS
M0—M4，以及C0—C5共同性研究。本文提炼已有实验和原始结果，未重跑模型。
这里只讨论软件语义、逻辑事件和明确假设下的静态映射，不把它们当成RTL跨模型
支持、硬件资源定型或性能证据。

## 1. 这一阶段为什么要做

[R3](03_functional_reference_and_execution_observations.md)在Qwen3-8B上做出了
hot/pending/packed三源软件参考。随之产生两个问题：换一个模型，这条路径还
成立吗？换一种KV选择算法，是否也需要同样的后端？

这里的“前端”指决定哪些KV保留、何时生效的算法及其控制语义。它不等于模型
本身：同一个Qwen可以配KVzap、SnapKV或官方训练DMS，但三者的KV生命周期不同。

**这一阶段支持了两个模型上的有界KVzap语义迁移，也划清了适用边界：SnapKV
提供一次性prefill选择后的打包证据，DMS提供动态驻留槽位的对照；尚未得到三者
共用的cache、调度器或硬件资源合同。**

| 探索顺序 | 目的与计划 | 结果如何推动下一步 |
|---|---|---|
| Llama M0—M2 | 绑定另一模型自己的官方predictor，再检查同mask计算与生命周期 | hot/pending/packed可以执行；仍须扩展workload并保留数值限制 |
| Llama M3—M6 | 对齐Qwen/Llama描述字段、三类workload与实际decode次数 | 共同语义成立的范围更清楚，但fan-in和资源形态不同 |
| SnapKV P0—P3/P2 | 把prefill最终保留集合映射到packed状态，再检查同mask计算 | 不规则保留集合可静态打包；未观察生成期生命周期 |
| 官方DMS M0—M4 | 观察延迟淘汰、槽位复用和原生attention | 动态驻留集合可以独立重放，但不对应Route-A的append-only cold |
| C0—C5 | 用已有证据检查共同字段、各自机制和方向选择 | 保留Route-A研究主线，共同遍历抽象未升级为统一硬件方案 |

## 2. Llama：换模型后，Route-A的语义是否还成立

### 2.1 先换成正确的模型与predictor组合

**目的与计划。** 使用固定的`NousResearch/Meta-Llama-3.1-8B-Instruct`快照，
绑定官方`nvidia/KVzap-linear-Llama-3.1-8B-Instruct`，检查模型结构和predictor
维度，再逐步运行全层同mask与生命周期验证。这里有显式predictor仓库覆盖，
不能写成未经适配的Meta原仓复现，也没有把Qwen的MLP权重直接迁移给Llama。

| 条件 | Qwen KVzap主线 | Llama支线 |
|---|---|---|
| 模型层数 | 36 | 32 |
| Q heads / KV heads | 32 / 8 | 32 / 8 |
| 官方predictor | Qwen专用MLP | Llama专用Linear |
| threshold | −4 | −7 |
| hot window / 参考page大小 | 128 / 64 | 128 / 64 |

来源：[Llama模型/predictor绑定](../experiments/llama31_m0_provenance_02/llama31_m0_provenance_manifest.json)、
[M1实际配置与结果](../experiments/llama31_m1_semantic_02/llama31_m1_semantic_manifest.json)。
共同的hot/page参数只是本次参考输入；相同接口语义不代表两种predictor、阈值
或保留分布相同。

### 2.2 从独立在线运行，转向同一mask的严格配对

**结果。** 初始独立在线dense与Route-A运行，237,824个共同决策中有194个
keep/drop不同，事件本身没有缺失。与R3的Qwen现象一样，这阻止了把两次独立
运行直接叫作same-mask对照。因此M1改为dense侧在线产生mask，Route-A恰好
消费一次，单独检查“同样的选择换一种实现能否算对”。来源：
[独立在线mask差异](../experiments/llama31_m1_semantic_01/llama31_m1_online_mask_drift_diagnostic.json)。

M1覆盖32层和全部8个KV heads，执行FP32及执行dtype检查。M2进一步用两个
admission预算制造不同状态：budget1观察到hot、非空pending和packed；budget512
观察到hot/packed、多页、完整页和尾页。两点均验证mask恰好消费一次，Full-KV
bypass不产生Route-A admission。来源：
[M2生命周期结果](../experiments/llama31_m2_lifecycle_01/llama31_m2_lifecycle_manifest.json)。

**分析。** 这支持了另一个模型/predictor组合上的Route-A软件语义，但没有证明
两条独立在线生成路径永远选择相同token。实验仍保留原生cache，也不能据此
声称物理显存已经释放。

### 2.3 扩展三类请求，数值超限不能被“完成”状态掩盖

M4把覆盖扩展到retrieval、summarization、reasoning各一个固定请求。摘要出现
执行dtype的严格16-ULP超限，随后三类请求采用显式`record_only`收集诊断，
FP32同mask检查仍执行；这不是三个workload全部通过严格16-ULP合同。

M4.1追查摘要：记录到3次超限、涉及2个独有位置，最大199 ULP；这些超限样本
记录的最大FP32差约5.96×10⁻⁸，且对应标量接近零。它解释了为什么ULP数
可能很大而绝对差仍小，**并未把严格16-ULP未通过改成通过，也未选定硬件精度**。
来源：[M4三请求结果](../experiments/llama31_m4_bounded_workload_envelope_02/llama31_m4_bounded_workload_envelope_report.json)、
[M4.1数值诊断](../experiments/llama31_m41_summarization_ulp_diagnostic_02/llama31_m41_summarization_ulp_diagnostic_report.json)。

随后M5发现：把`max_new_tokens`都设为8，仍可能因自然EOS使实际观察长度不同。
M5.1于是规定固定8-token continuation，关闭EOS提前停止，由dense提供token轨迹
和mask，Route-A按此执行，三请求各得到7次`q_len=1` policy decode调用。
这个实验刻意包含固定续写，不要求强制越过EOS后整词表logits相等；它不能证明
自然生成长度、答案质量或两条独立生成路径始终一致。摘要的非严格ULP背景也
继续保留。来源：[M5.1固定观察范围](../experiments/llama31_m51_fixed_horizon_workload_descriptor_02/llama31_m51_fixed_horizon_workload_descriptor_report.json)。

### 2.4 M6对齐后的关键观察：共用语义不等于共用资源规模

M6把上述Llama与Qwen A4.2.8的三个请求放到相同的7次policy decode调用、
hot128、page64参考条件下，保留各模型自己的原始请求和数值合同。下表是各行
已记录逻辑attention决策的归一化fan-in比例；包含原实验覆盖的调用，不能用
`层数×KV heads×7`直接重建全部决策数。

| 模型 | 固定workload | 一源 | 两源 | 三源 |
|---|---|---:|---:|---:|
| Qwen3-8B | retrieval | 4.17% | 94.07% | 1.76% |
| Qwen3-8B | summarization | 4.17% | 94.93% | 0.90% |
| Qwen3-8B | reasoning | 3.47% | 92.95% | 3.58% |
| Llama-3.1-8B | retrieval | 0.78% | 87.44% | 11.77% |
| Llama-3.1-8B | summarization | 0.78% | 87.72% | 11.50% |
| Llama-3.1-8B | reasoning | 0.78% | 48.33% | 50.89% |

按两位小数显示可能不恰好相加为100%。来源：
[M6六行跨模型对照](../experiments/route_a_m6_cross_model_fixed_horizon_envelope_03/m6_cross_model_fixed_horizon_envelope_report.json)。

**分析。** Llama reasoning的三源比例显著高于Qwen对应行，说明即使使用相同
预算和存储划分，pending/merge的需求也可不同。这里的“不同”是模型、predictor、
阈值和固定请求共同作用下的观察，不能单独归因于模型架构。六行不合并统计，
其最小/最大值也不是请求分布、FIFO容量或bank/端口保证。M6是无时间戳的
描述对齐，没有观测source-ready、完成时刻或真实backpressure。

## 3. SnapKV：一次性选择后的不规则集合，能否规则地存起来

**目的与计划。** 不急着把SnapKV放进持续decode后端，先检查其prefill最终
选择能否形成明确token集合，再映射为规则packed页，最后用真实模型的query
作有界同mask计算检查。

P0从`SnapKVPress`提取score及最终top-k选择，固定`compression_ratio=0.5`、
window64、kernel5，保留受保护的observation suffix；没有KVzap的threshold。
它不调用原生SnapKV cache替换。选中集合确定后，P1按原始position递增排列，
而非照搬score排名后的gather顺序；选择集合与实现遍历顺序在这里分别处理。
来源：[P0选择合同及配置](../experiments/snapkv_route_a_p0_contract_qwen3_8b_01/snapkv_p0_contract_manifest.json)。

### 3.1 P1静态容量结果

同一个Qwen摘要请求有891个context positions、36层×8 KV heads；每条layer/head
流保留445项，其中64项是resident hot，381项进入cold。约一半的保留量由上述
top-k预算规定，不是新测出的无约束压缩能力。这里的64来自SnapKV observation
window，不能当成KVzap的hot128合同。

| 观察项 | 结果及范围 |
|---|---|
| Full-KV逻辑槽位 | 256,608 |
| 理想保留槽位 | 128,160，对应2.00225×槽位压缩 |
| 页对齐后分配槽位 | 129,024，对应1.98884×槽位压缩 |
| P=16/32/64/128每条流的cold页数 | 24 / 12 / 6 / 3 |
| P=64具体形态 | 5个满页＋含61项的尾页；每条流浪费3个槽位 |
| P=64声明metadata | 27,648 B，按16 B/cold page计 |

四种page大小在本例恰好都把381个cold项圆整至384，故分配槽位相同，而页数
和metadata不同。这是该请求的整除关系，不是一般性的page大小无关结论。
压缩比不含metadata；metadata是声明的布局计价，尚非真实allocator/控制器
实现。来源：[P1布局报告](../experiments/snapkv_route_a_p1_packed_opportunity_qwen3_8b_01/snapkv_p1_packed_opportunity_report.json)。

### 3.2 P3计算检查与P2最终边界

P3使用实际模型最后一个prefill位置的query，只读地比较同mask dense与功能
Route-A状态，覆盖36层/8 KV heads；没有替换模型原有prefill attention。
budget4096排空了本次terminal状态，得到hot/packed和零pending。

FP32同mask检查通过；执行dtype采用记录模式，出现79-ULP超限，其对应样本
记录的FP32最大差约2.98×10⁻⁸。因此这里也不能声称严格16-ULP通过。更重要的
是，P3执行了**零次generated-token forward**，没有验证原生SnapKV cache或
decode行为。来源：[P3有界语义检查](../experiments/snapkv_route_a_p3_semantic_qwen3_8b_01/snapkv_p3_semantic_manifest.json)。

P2汇总得到5项字段可用、8项不可用，明确不支持decode/pending、scheduler或
物理资源合同。来源：[P2最终描述](../experiments/snapkv_route_a_p2_lifecycle_resource_descriptor_qwen3_8b_01/snapkv_p2_lifecycle_resource_descriptor.json)。

**分析。** 不规则保留集合可以映射为规则存储，这是有效的局部证据。但本次
pending=0只是该terminal probe排空后的状态，不能推断未来没有pending或生成期
KV零成本。约1.99×不能与R1不同请求上的KVzap压缩直接作算法优劣比较，也没有
完成“保留prompt集合＋后续生成KV”的持续执行验证。

## 4. 官方DMS：为什么不能把所有稀疏KV都叫作packed cold

**目的与计划。** 使用官方训练的`nvidia/Qwen3-8B-DMS-8x`及其原生cache和
FlashAttention，逐步记录控制决策、复用槽位和attention来源。模型名中的8x是
所用checkpoint标识，不是本实验测得的压缩比。这里不是早先用KVPress
`DMSPress`承载KVzap mask的路径，也没有使用KVzap predictor。

| 阶段 | 计划与关键结果 |
|---|---|
| M0—M1 | 绑定官方模型和实现；固定retrieval、625-token输入、4次显式decode forward。36层×5次prefill/decode更新，共180个控制事件 |
| M2 | 捕获官方二值决策，由独立控制参考重放延迟淘汰和复用；逐事件长度及最终36×8状态对应，trace开关不改变原生执行结果 |
| M3 | 跟踪活跃native slot对应的arrival serial及ring状态；最终288个layer/head状态中269个按native槽位遍历时arrival serial非单调 |
| M4 | 保持原生执行不变，按官方logical-slot/block-table顺序取活跃K/V，独立FP32重放一源attention，检查144次decode调用 |

原生DMS配置窗口为512；该请求M4观察到resident长度513—629，不能把512直接
当成全生命周期驻留量上界。来源：
[M0原生配置](../experiments/dms_route_a_m0_official_provenance_qwen3_8b_debug_env_tf457_base_tokenizer_prefill_01/dms_m0_official_provenance_manifest.json)、
[M2控制重放](../experiments/dms_route_a_m2_adapter_contract_qwen3_8b_retrieval_01/dms_m2_adapter_contract_manifest.json)、
[M3活跃槽位](../experiments/dms_route_a_m3_active_topology_qwen3_8b_retrieval_04/dms_m3_active_topology_manifest.json)。

M4的144次调用为36层×4次decode，全部满足该实验自己的`atol=rtol=0.03`比较
标准；最大绝对差约0.062956，每调用平均绝对差再取均值约0.0003104。相对与
绝对容差联合判断，最大差不能单独和0.03比较。这一标准也不等于KVzap/SnapKV
的FP32或ULP标准，不能用三者都“通过”推导共同精度合同。来源：
[M4 active-resident attention](../experiments/dms_route_a_m4_active_resident_attention_qwen3_8b_retrieval_01/dms_m4_active_resident_attention_manifest.json)。

**分析。** DMS的淘汰项会离开活跃集合，槽位会复用；它们不是先进入pending，
再永久追加到Route-A cold页。269个非单调状态说明arrival顺序与native遍历顺序
不能视为同一个字段，后续适配必须保留既有合同，不能未经验证便替换顺序。
这没有证明所有重排都会改变输出，也没有进行重排不变性实验。

此外，arrival serial只标识源的到达身份，不是普遍捕获到的原始token position。
原始position、arrival身份、attention要求的native顺序应分别保存。M4支持的是
一个活跃驻留源的有界重放，没有实例化Route-A后端，也没有证明packed容量、
多源merge、流量或速度收益。

## 5. C0—C5：共同性研究最后到底保留了什么

**目的与计划。** 不再增加模型或前端，先把以上已完成证据投影成共同字段：
C0索引已有证据，C1定义描述字段，C2作各前端映射，C3区分共同/专用/未知，
C4复核各自attention比较依据，C5决定研究方向。它们没有新增六轮模型实验，
跨主机复核也不增加独立模型样本。来源：
[C0既有证据索引](../experiments/cross_frontend_c0_evidence_index_01/cross_frontend_c0_evidence_index_report.json)。

### 5.1 C1—C2：统一描述问题，不强行统一数据格式

描述粒度为`(model,layer,kv_head,epoch)`，包括八类字段：

| 字段 | 回答的问题与必须保留的区别 |
|---|---|
| model_topology | 哪个模型、多少层/head、query与KV如何分组；不能合并成共同硬件尺寸 |
| identity | 哪一条记录；明确身份是原始position还是arrival serial |
| epoch | 哪个phase、forward/decode index和q_len；一次terminal状态不是完整在线时间线 |
| decision | 选择结果何时已知、何时生效；未观察的时刻仍未知 |
| visibility | 此时attention语义上必须看见哪些记录；与物理搬运完成不同 |
| position_provenance | 是否真的捕获原始位置；不能由DMS slot或arrival编号冒充 |
| traversal_order | 按什么顺序读取、该顺序为何有约束 |
| attention_binding | query/KV对应关系及该前端自己的正确性比较依据 |

每个值带五种状态之一：`observed`为直接观察，`derived`为确定性推导，
`modeled`为声明假设，`unknown`为缺乏证据，`not_applicable`为该实现不适用。
例如SnapKV生成期状态是unknown，不能填0；DMS的原始position未知，不能用
已知arrival serial替代。八类字段都被描述，不表示八类值在各前端都已观察到。
来源：[C1描述与字段可用性](../experiments/cross_frontend_c1_semantic_descriptor_01/cross_frontend_c1_semantic_descriptor_report.json)。

C2再分别投影为KVzap的`persistent_packed`、SnapKV的`one_shot_packed`和DMS的
`dynamic_resident_slot`。pending、page descriptor、free-slot list、native block
table均属各自实现扩展；不能因为某种后端需要它，就提升为全部算法的共同字段。
这些是语义描述，不是建议硬件逐项存一份表，也没有证明共同抽象的实现开销为零。
来源：[C2三类实现映射](../experiments/cross_frontend_c2_realization_adapters_01/cross_frontend_c2_realization_adapters_report.json)。

### 5.2 C3—C5：哪些共同，哪些仍然专用

| 比较维度 | KVzap Qwen/Llama | SnapKV本次证据 | 官方DMS本次证据 |
|---|---|---|---|
| 选择和生效 | creation预测，hot保护后maturity生效 | 一次prefill terminal选择 | 延迟淘汰与槽位复用 |
| 数据实现 | hot/pending/append-only packed | terminal保留集合的静态canonical映射 | 动态活跃native slots |
| 身份与顺序 | 原始position、source及append顺序 | 保留集合不变，canonical原始position顺序 | arrival serial与native槽位/block-table顺序分开 |
| 实际attention依据 | same-mask dense与三源参考 | 最后prefill位置的有界probe | 原生FlashAttention与一源FP32重放 |
| 多源合并是否共同必需 | Route-A可有1—3个非空源 | 未建立原生多源需求 | 接受的一源检查不需要 |
| pending/maturity | Route-A生命周期的一部分 | decode未观察，不能填零 | 不适用于所接受的DMS realization |
| 持续执行与物理资源 | 仅各指定实验范围/显式模型 | 未建立 | 未建立Route-A对应关系或硬件合同 |

P3为SnapKV试验性拆成hot/packed，不等于其原生算法必须提供多源接口。C4允许
把其已选集合视为一个有序源，不把这次验证工具的组织方式强加给算法。

C3保留下来的共同项只有明确的记录身份、epoch/决策作用域、各前端要求的遍历
顺序，以及各自接受的数值比较依据。它没有得到共同的position来源、在线时间线
或统一精度。C4把共同部分概括为：**在各自语义依据下遍历有序的变长数据源**。
source-ready、完成时序、队列、backpressure、allocator、容量和端口仍未形成
跨前端合同。来源：[C3共同性矩阵](../experiments/cross_frontend_c3_commonality_matrix_01/cross_frontend_c3_commonality_matrix_report.json)、
[C4 attention抽象](../experiments/cross_frontend_c4_attention_primitive_study_01/cross_frontend_c4_attention_primitive_study_report.json)。

C5因此保留Route-A persistent-packed作为主研究路径，将共同遍历留作语义抽象，
没有选择统一硬件后端。其依据是KVzap特有的稳定决策、maturity和持久packed
生命周期值得继续研究，而不是已经算出了它比所有替代方案更经济。它既不证明
通用后端不可能，也没有解决后来RTL的面积、时序或持续执行问题。来源：
[C5方向决定](../experiments/cross_frontend_c5_hardware_direction_decision_01/cross_frontend_c5_hardware_direction_decision_report.json)。

## 6. 本阶段最终留下的结论与数据

本阶段把“适用于其他模型/算法”拆成了三个不同层次：Llama支持有限实例上的
**语义迁移**；C0—C4支持有限的**共同描述抽象**；统一低成本硬件和跨模型资源
保证仍没有证据。SnapKV和DMS的价值包括暴露边界，不能因没有进入Route-A
主线就丢弃它们的结果。

最重要的负结果是：独立在线mask并非始终相同；严格ULP合同在部分场景未通过；
相同token cap并非相同自然horizon；arrival顺序不能冒充native顺序；共同的
attention遍历不足以推出共同cache和调度器。没有观察到的字段应保留未知，
不能把“未观察”“零”和“不适用”互相替换。

正文表格已直接引用原结果，无需另建数据包。M6保留逐模型/workload的fan-in、
source长度和尾页统计；SnapKV P1保留request及layer/head CSV；DMS M3保留控制
和活跃槽位NPZ。未来可据已有数据重绘相应图表，但不能重建当时没有记录的
生成期行为、物理时序或性能。本文没有移动或删除原资料，也未重新验收全部
原始trace；必要制品由正文直链的M0—M6、P0—P3、M0—M4及C0—C5 JSON登记，
无需经由旧的共同性计划或证据归档理解本文结论。

这条支线结束后，主线回到R5：既然继续研究KVzap特有的持久packed生命周期，
就要在具体workload、activation和服务假设下收口pending、归属及metadata资源，
再进入完整成本判断。跨模型语义实验不能替代这一步。
