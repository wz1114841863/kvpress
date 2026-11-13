# R1：算法复现、稀疏结构与路线筛选

整理日期：2026-11-12。研究阶段：2026 年 8 月 baseline、predictor trace、LongBench
结构分析及 Route-B 筛查。模型 Qwen3-8B，官方 KVzap MLP，threshold −4，最近
128 token 保护窗口，seed42。本文依据已有结果表重新提炼数据，不重新运行模型。

本阶段最终得到的判断是：**原始 KVzap 提供了较大的逻辑压缩机会，但具体 token
位置并不规则。保留 mask、整理每个 head 的存储比直接强制 block 化保留了更多容量
机会，因而当时选择 Route-A。** 这是结构与布局模型支持的研究路线选择，尚未包含
完整硬件实现成本，也没有建立正式准确率或加速结论。

可以把本报告当成下面这个故事来读：

1. **先试能不能用。** 官方算法在几个简单请求上能运行，能删掉很多KV。
2. **再看删在哪里。** 扩大到45个请求后，发现不同head虽然保留比例有规律，留下
   的token却不一样，不能简单共用一张表，也不能指望保留项天然连续。
3. **试着按块整理。** 每4个或8个token一起留/删，存储可能更规则，却会多留一些
   原本能删除的token；提高删除门槛又引入质量风险。
4. **再试只整理存储。** 不改算法选出的token，把留下的KV紧凑排列，容量损失
   比强制改mask小；因此当时优先研究Route-A。
5. **留下一个大前提。** 只有搬运、查表和管理不太贵，较高压缩才值得。R1当时
   还没有把这笔硬件账算完整，所以它给出了继续研究的理由，没有证明最终方案胜出。

例如，4个位置里只需要保留1个：沿原位置整块存放可能仍占4个槽；先紧凑排列则
能把不同块里需要的KV聚在一起，减少空槽，但要付出搬运和管理的代价。这正是
两条路线需要权衡的地方，不能只比较删除率。

## 1. 探索怎样一步步推进

| 阶段 | 实验目的 | 计划与比较 | 得到什么，为什么进入下一步 |
|---|---|---|---|
| 官方路径复现 | 确认选定模型/predictor 能工作 | 三个内置请求，Full-KV/prefill/prefill+decode 三种模式 | 9 个组合的功能检查通过；需要真实请求和位置结构，而非只看删除比例 |
| Predictor-only Gate A/B | 获得适合离线结构分析的 score/mask | 先匹配一个 hardware 请求，再覆盖 retrieval/summarization/reasoning | 完整 layer/head score 和保护窗口规则可检查；进入多请求收集 |
| LongBench v1 | 原始稀疏结构是否跨请求稳定 | 三类别×三长度桶×每桶2条，共18条 | 保留比例轮廓稳定，但任务组成偏斜，促使扩展 v2 |
| LongBench v2 | 减少选样偏斜并确认结构结论 | 每类别/长度桶5条，共45条；补入 qmsum，扩大 task 覆盖 | 保留比例稳定、具体 mask 重叠低、block 内碎片明显 |
| 存储与规则化比较 | 规则性应来自 mask 还是存储？ | keep-any block、B4/B8与margin、head容量取整、timeline/packed 布局 | 改 mask 损失压缩；保持 mask 的紧凑存储更有容量潜力 |
| 小样本生成筛查 | B4候选是否值得扩大评测？ | 9请求×4变体；另有单请求 probe/sentinel | QA筛查未显示差异，摘要有正负变化；未扩大为45条正式准确率实验 |

Gate、v1/v2 和结构化筛查的样本/用途不同，不能将其数量相加成独立准确率样本数。
v1 的18个 request_id 都包含在 v2 中，两个 pilot 去重后仍是45个请求。

## 2. 官方算法复现：先确认能运行与逻辑压缩

**目的与计划。** 固定官方 predictor，greedy decoding、thinking disabled，比较
Full-KV、只在 prefill 裁剪、prefill+decode 裁剪。三个内置请求分别检查检索代码、
摘要关键词及长硬件回答所需关键词；它们是功能检查，不是正式 benchmark。

| 内置请求 | Full-KV检查 | Prefill 删除率 / 逻辑压缩 | Prefill+decode 删除率 / 逻辑压缩 |
|---|---|---|---|
| Retrieval | 通过 | 69.54% / 3.282× | 70.36% / 3.373× |
| Article summary | 通过 | 70.66% / 3.408× | 72.65% / 3.657× |
| Long hardware answer | 通过 | 74.34% / 3.897× | 74.91% / 3.986× |

裁剪侧六项检查也全部通过。来源：[逐请求 baseline](../archive/baseline_results.csv)、
[冻结范围](../archive/baseline_freeze.json)。原 CSV 的 elapsed 字段仅为诊断，不用于性能分析。

**分析。** 结果确认指定配置可执行，并且内置样本有较高逻辑删除率；它既不代表
所有回答保持精度，也不能说明 KVPress fake-key 路径已经少存了对应物理 KV。
因此下一步改为独立观察 predictor 的 score 和位置结构。

### 2.1 实际软件路径与最小复现入口

逐层predictor输入为hidden state `[batch,T,hidden_dim]`，输出score
`[batch,KV_heads,T]`；K/V为`[batch,KV_heads,T,head_dim]`。本次Qwen有36层、
8个KV heads。软件在attention之后观察hidden state并作预测，score严格小于−4
时标为drop；最近128项先受保护，离开窗口才生效。不能用此结果支持prefill
attention之前删除KV。实现见[KVzap predictor](../../kvpress/presses/kvzap_press.py)、
[DMS包装](../../kvpress/presses/dms_press.py)。这里的DMSPress是KVPress包装，
不同于R4的官方训练DMS模型。

原软件的head-wise mask通过dense K/V上的fake-key attention实现，未真正缩短
各head的物理tensor；论文中的逻辑索引表达不能替代本仓库的实际存储行为。
这正是后来需要packing后端的原因。来源：[attention实现](../../kvpress/attention_patch.py)。

冻结baseline环境为A100-SXM-64GB、PyTorch2.10.0+cu128、Transformers5.0.0；
模型/predictor revision及解码配置见[原配置](../archive/baseline_config.yaml)。旧的
Transformers4.57.3 smoke建议不是该baseline的精确复现环境。新运行入口为：

```bash
.venv/bin/python tools/run_kvzap_baseline.py --output-dir analysis/experiments/baseline_recheck_20261112_01
```

以上是供后续复现的命令示例，目录ID需按新运行命名，本次没有执行模型。脚本默认输出指向已冻结的
`analysis/`，复现时必须使用新目录。自定义`--input-jsonl`每行必需
`request_id/context/question`，可选`subset/required_substrings/max_new_tokens`。
输出配置YAML、逐请求CSV和说明；CSV保存答案但不保存原context/question。
`generated_tokens_retokenized`也不等于内部decode调用数，不能与R2的call混算。

## 3. 从单请求 trace 到45条结构样本

### 3.1 Gate A/B：确认观测对象，再扩大样本

Predictor-only collector 观察 attention 输入 hidden state，调用官方逐层 predictor，
保存 score，并按 `score < −4` 重建预测 drop；final mask 再保护最近128 token。
score 的结构为 `[36 layers, 8 KV heads, T tokens]`。这是 prefill 结构观察，
不是实际 decode pruning 或在线 admission trace。

Gate A 在匹配的987-token hardware 请求上最大 score 差为0，逻辑删除率74.34%。
Gate B 扩展到三种内置请求，得到：

| Gate B请求 | T | 保护窗口后的总逻辑删除率 | Cold 区域删除率 |
|---|---:|---:|---:|
| Retrieval | 905 | 71.88% | 83.72% |
| Summarization | 891 | 72.66% | 84.85% |
| Reasoning | 2,031 | 78.96% | 84.27% |

来源：[Gate A](../archive/predictor_trace_gate_a.json)、[Gate B](../archive/predictor_trace_gate_b_freeze.json)。
这些请求与 baseline 的输入范围不完全相同，删除率不能逐项当作相同请求的重测差。

有效的predictor-only trace只做一次正常prefill，逐层观察输入并独立调用官方
predictor，将score复制到CPU后重建mask；不调用有状态DMS裁剪hook，不修改
native cache，也不生成答案。要求全部layer/head齐全、score有限、shape明确、
阈值mask与hot保护正确，并记录输入、模型和schema身份。Gate A先与987-token
参考匹配；Gate B及后续新请求沿用已通过的Gate A，每请求独立运行。
采集入口为[export_kvzap_predictor_trace.py](../../tools/export_kvzap_predictor_trace.py)：
用`--preset hardware --reference-trace traces/qwen3_8b_single_384`重查Gate A，
或用`--input-jsonl <input> --request-id <id>`选一条新请求，两者均需
`--output-dir <new_trace_dir>`。已冻结trace不可覆盖。早期有状态采集的残缺层、
无有效manifest或未通过观测等价检查的输出不属于本报告结果，不能与有效trace混用。

### 3.2 v1暴露选样问题，v2检验结论是否保留

长度桶固定为 `[1024,4096)`、`[4096,8192)`、`[8192,16384)`，依据 preparation
的 tokenizer 长度选样；实际 score 序列长度另记在 trace 中。

| 指标 | v1 | v2 |
|---|---:|---:|
| 请求数 | 18 | 45 |
| 每类别 / 每类别×长度桶 | 6 / 2 | 15 / 5 |
| Request-mean逻辑删除率 | 66.26% | 66.47% |
| Token加权逻辑删除率 | 65.92% | 66.23% |
| Token加权逻辑压缩 | 2.934× | 2.961× |
| 单请求删除率范围 | 63.86%—67.00% | 63.86%—72.24% |

v1 retrieval 的6条有5条是 qasper，且无 qmsum，故不足以支撑 task-balanced
解释。v2 task构成为 qasper12、narrativeqa3、gov_report5、qmsum5、multi_news5、
2wikimqa10、musique5；类别/长度桶平衡，但各 task 数量仍不等，不能叫总体分布。

| v2类别 | n | Token加权删除率 | 单请求范围 |
|---|---:|---:|---:|
| Retrieval | 15 | 65.61% | 63.86%—67.00% |
| Summarization | 15 | 67.06% | 65.83%—72.24% |
| Reasoning | 15 | 66.02% | 64.22%—67.72% |

v2 实际 score 序列长2,143—16,042；删除率 request P50为66.25%、P90为67.47%。
Token加权与request均值不同：前者对有效layer/head/token条目求总删除/总数，
后者对每请求比例等权平均。逻辑压缩是 `1/(1−删除率)`；平均压缩不能用平均
删除率直接替代计算。来源：[v1冻结](../archive/longbench_core_v1_freeze.json)、
[v2冻结](../archive/longbench_balanced_v2_freeze.json)、v2 `request_summary/request_group_summary.csv`。

## 4. 稀疏结构：比例稳定，位置不规则

**目的与计划。** 检验是否能共享 head mask，是否有天然 block locality，是否可
只利用相对稳定的 layer/head 容量轮廓。分析跨请求 retention、同层不同 head
token集合、run-length、block occupancy，以及阈值附近 score。

| v2指标 | 数值 | 可支持的分析 |
|---|---:|---|
| 跨请求 layer retention Pearson均值，990对 | 0.9720 | layer级保留比例轮廓稳定 |
| 跨请求 layer/head retention Pearson均值 | 0.9801 | 更细粒度保留比例也较稳定；不比较跨请求token位置 |
| 同层不同head keep-mask Jaccard，request均值 | 0.2046 | 不同head保留的具体token重叠较低 |
| 扣除独立mask期望后的Jaccard excess | 0.0689 | 仅靠marginal retention不能解释为强共享位置 |
| score距−4在±0.25内的比例，request均值 | 6.53% | margin修改会影响一部分决策，需要独立质量评估 |

更粗的块只要含一个keep就整块分配，会浪费更多cold槽位：

| 原mask keep-any块大小 | 混合块比例 | Cold分配内碎片 | 总容量压缩proxy |
|---|---:|---:|---:|
| 4 | 32.54% | 34.67% | 2.0067× |
| 8 | 45.19% | 43.34% | 1.7525× |
| 16 | 55.31% | 49.33% | 1.5750× |
| 32 | 63.59% | 53.82% | 1.4405× |

表中为45请求等权均值，尾块按整块padding，hot128规则存储；碎片分母为cold已分配
槽位，总容量压缩包含hot，未计metadata。这些是布局估算，不是实际显存测量。

此外，单独改变 threshold 后，保护窗口覆盖前的 predicted-drop request均值如下：

| Threshold | −4.50 | −4.25 | −4.00 | −3.75 | −3.50 |
|---|---:|---:|---:|---:|---:|
| Predicted drop | 61.00% | 64.70% | 68.23% | 71.70% | 74.90% |

它们不是final mask删除率，也不是同等质量的可选配置。实验只说明阈值敏感性，
没有授权改变原阈值。上述数据来自v2 `request_pair_similarity.csv`、
`head_similarity.csv`、`block_occupancy.csv`、`score_threshold_sensitivity.csv`。

**分析。** 应把“容量轮廓有规律”和“具体token可共用mask”分开。前者提供配置、
调度研究动机；后者缺少证据。keep-any大块的容量损失推动了两种比较：改变mask
使块更规则，或保持mask、把保留token紧凑存放。

## 5. 两类规则化：改mask，还是只整理容量

### 5.1 Route-B：B4/B8与margin的离线筛查

每个成熟cold块只有在所有有效score均低于 `−4+margin` 时才drop；hot128保持。
比较B4/B8与margin −0.25/0/+0.25，共6个候选，每个使用45条trace。

| Block | Margin | Token加权删除率 | Token加权逻辑压缩 |
|---|---:|---:|---:|
| 原始KVzap | — | 66.23% | 2.9609× |
| 4 | −0.25 | 45.31% | 1.8283× |
| 4 | 0 | 49.22% | 1.9694× |
| 4 | +0.25 | 53.22% | 2.1376× |
| 8 | −0.25 | 37.81% | 1.6079× |
| 8 | 0 | 41.75% | 1.7167× |
| 8 | +0.25 | 45.73% | 1.8425× |

margin0不额外删除原keep，却重新保留了原本可drop的token。B4,+0.25相对margin0
恢复约4个百分点删除率，但仍比原mask低13.01个百分点；它对原本keep的cold token
也可能新增drop。按cold有效总条目计，新增drop的request均值1.12%，重新保留原drop
的均值13.97%，两者不应误作“对原keep集合的比例”。B8在这组数据里损失更大。

来源：`longbench_balanced_v2_structured_policy_v3/structured_policy_summary.csv`。
这一结果支持选择B4作有限生成筛查，不能推断相同质量。

### 5.2 不改mask：对每个head的cold保留量按quantum取整

| Capacity quantum | 容量压缩request均值 | Cold分配内碎片request均值 |
|---|---:|---:|
| 16 | 2.9723× | 0.57% |
| 32 | 2.9557× | 1.18% |
| 64 | 2.9220× | 2.44% |
| 128 | 2.8538× | 4.94% |

原mask逻辑压缩的request均值为2.9876×，可与本表同口径比较。该模型按每个
layer/head保留量取整，不要求原时间轴上的token连续；尚未包括搬运、索引、
metadata、并发或控制实现成本。来源：v3 `head_length_bucketing.csv`。

**分析。** 规则化物理分配与规则化选择mask是不同手段。前者显示较低容量碎片，
由此产生Route-A的动机；这不是已经证明token compaction的实现便宜。

## 6. 生成筛查与布局对照：保留收益，也保留不足

### 6.1 9请求×4变体的生成筛查

从三个类别、三个长度桶各取一条，共9条，比较Full-KV、原KVzap、B4,m0和B4,m+0.25。
该组retrieval实际均为qasper，summarization均为qmsum，reasoning为2wikimqa/musique；
不能把9条称为覆盖所有task。36次运行的mask gate通过；6条QA的筛查F1在四变体间
相同，其中也有F1为0的样本，所以“未变差”不等于任务都正确。

| qmsum请求尾号 | Full-KV | 原KVzap | B4,m0 | B4,m+0.25 | +0.25相对原KVzap差值 |
|---|---:|---:|---:|---:|---:|
| 000042 | 0.1585 | 0.1548 | 0.1350 | 0.1341 | −0.0207 |
| 000016 | 0.1401 | 0.1538 | 0.1436 | 0.1858 | +0.0319 |
| 000010 | 0.2393 | 0.3571 | 0.3529 | 0.3200 | −0.0371 |

摘要指标为whitespace-token ROUGE-L，QA为筛查F1；不是官方LongBench评测。
摘要变化有正有负，小样本不能判断质量等价。来源：
`accuracy_b4_stratified9_01/request_results.csv`，单请求probe/sentinel保留为前置记录。

### 6.2 改mask的好处依赖存储模型

timeline布局保留原token位置，一个page中只要还有keep就分配；packed布局先将每个
head的keep紧凑排列，再按page取整。下表压缩均按token加权总槽位计算，包含hot128、
不包含metadata字节；read proxy另按512 B/KV条目、16 B/cold page计费。

| Page tokens | 原mask timeline压缩 | B4,+0.25 timeline压缩 | Timeline容量/read proxy变化 | 原mask packed压缩 | B4,+0.25 packed压缩 |
|---|---:|---:|---:|---:|---:|
| 4 | 1.9691× | 2.1373× | −7.87% | 2.9588× | 2.1373× |
| 16 | 1.5418× | 1.6417× | −6.09% | 2.9502× | 2.1328× |
| 32 | 1.4130× | 1.4950× | −5.48% | 2.9384× | 2.1268× |
| 64 | 1.3139× | 1.3815× | −4.89% | 2.9147× | 2.1148× |

变化列按timeline分配容量、以及含metadata的read proxy计算，四舍五入后相同。
但样本中的平均请求内layer/head page-count P95和最大值没有实质改善：例如page16
的P95均值与max均值在原mask和+0.25均为407.44；page64均为102.24。
来源：`longbench_balanced_v2_phase3_layout_01/layout_cost_summary.csv`。

**阶段判断。** B4,+0.25在不能任意token compaction的timeline假设下有小幅好处；
如果能实现低成本packing，原mask提供更大的容量机会。因此当时冻结B4为受限备选，
没有扩展45条生成质量评测，转向Route-A的packing、调度和admission摊销研究。
当时尚未计入后来RTL中的完整metadata、compact表、访问网络和顶层时序成本，
所以不能把本阶段选择解释为“Route-A完整硬件已优于结构化方案”。

### 6.3 为什么当时保留Route-B，而没有把2.14×判为无价值

**2.14×已经是可观的逻辑压缩。** 用100份原KV作直观例子，2.96×约留下33.77份，
2.14×约留下46.78份。Route-B多留约13份原KV；如果因此能省去更多搬运、索引、
并发查表和控制开销，它仍可能更合算。不过B4规则不能自动保证这些逻辑都消失，
需要给出具体后端再比较。两种压缩也尚未代表相同质量。

当时考虑了以下因素，而不仅是逻辑删除率：

| 已考虑的因素 | 当时的证据与判断 |
|---|---|
| 存储是否支持任意token compaction | 用timeline与packed两种布局比较；B4在timeline下有约5—8%的proxy好处，故保留为受限备选 |
| 原mask能否用较少空槽存放 | head容量取整的碎片较小，支持继续探索packing，但未给出packing控制实现成本 |
| 是否解决最重head/page尾部 | 样本page-count尾部没有明显改善，尚不能证明减少最坏资源需求 |
| 改mask的生成质量风险 | 正margin会新增drop；9请求筛查有摘要分数下降，质量等价未建立 |
| 研究范围与变量 | 固定原mask可将存储后端问题与mask变化分开，减少同时变化的因素；这只是研究组织理由，不是硬件优势 |

**当时未完成的权衡**是：在同质量要求、同工作负载和同技术下，为A/B各建立实际
控制/存储实现，比较面积、端口、时序、能量，以及packing/admission与访问开销。
现存冻结筛查没有提供这种完整对照。不能据此说“当时没有考虑硬件”，也不能说
“当时已经证明Route-A更容易实现、更经济”。

当时的备选条件是：若目标系统不能提供token compaction，或后续同口径系统比较
显示Route-B有Pareto优势，就重新评估Route-B。当前报告保留这一条件，不将
历史主线选择视为不可被后续硬件证据推翻的结论。R2继续检验packing的代价。

## 7. 应保留的结论与负结果

1. 指定官方模型/predictor的内置检查可复现；大于内置功能检查的准确率结论仍需独立评测。
2. 45条trace支持约2.96×逻辑压缩与较稳定容量轮廓；它们是predictor-only结构数据。
3. 共享token mask和直接粗块存储缺少结构依据；不是所有形式的共享/结构化都被否定。
4. B4/B8规则化明显损失逻辑压缩；正margin会新增drop，质量筛查也有摘要下降样本。
5. v1选样偏斜被v2部分纠正；v2和9请求生成筛查仍有样本边界。
6. head容量取整损失较小，但压缩机会能否抵消packing与控制成本，留给后续R2—R6。

## 8. 数据来源与保留决定

R1只保留本报告作为阅读入口。正文中的表格直接提炼自以下既有结果，不再另存一套
关键数据包、逐文件管理清单或归档方案。未来绘图直接使用原表和trace；均值不能
重建完整分布，因此相关原始数据继续保留。

| 用途 | 原位置与必要数据 |
|---|---|
| 官方路径复现 | [baseline结果](../archive/baseline_results.csv)、[配置](../archive/baseline_config.yaml)、[冻结记录](../archive/baseline_freeze.json) |
| 单请求及三类请求观测 | [Gate A](../archive/predictor_trace_gate_a.json)、[Gate B](../archive/predictor_trace_gate_b_freeze.json)，以及[Gate原trace](../../traces/hardware_predictor_gate_a_01/)和三个Gate B trace目录 |
| 选样与18条→45条的推进 | [v1冻结](../archive/longbench_core_v1_freeze.json)、[v2冻结](../archive/longbench_balanced_v2_freeze.json)、[选样资料](../../pilot_inputs/)、对应pilot run manifest |
| 删除率分布、head热图、相关性、run-length与阈值曲线 | [v2主分析](../experiments/longbench_balanced_v2_analysis/)中的request_summary、request_group_summary、layer_head_retention、request_pair_similarity、head_similarity、run_length_distribution、block_occupancy和score_threshold_sensitivity各CSV；[v1分析](../experiments/longbench_core_v1_analysis/)保留选样演进证据 |
| B4/B8、margin与head容量取整 | [v3结构化分析](../experiments/longbench_balanced_v2_structured_policy_v3/)中的structured_policy_request、structured_policy_summary和head_length_bucketing各CSV及evaluation manifest |
| Timeline/packed布局比较 | [布局分析](../experiments/longbench_balanced_v2_phase3_layout_01/)中的request_layout_cost、layout_cost_summary、layer_head_page_cost各CSV及evaluation manifest |
| 生成质量筛查 | [9请求结果](../experiments/accuracy_b4_stratified9_01/request_results.csv)、对应run manifest、答案/参考及metric定义；[Route-B冻结](../archive/b4_route_b_screening_freeze.json)限定其结论范围 |
| 新位置统计、重新生成候选mask | [原pilot trace](../../traces/pilots/)中的逐请求score_mask.npz和manifest；[字段定义](../../TRACE_SCHEMA.md)、[分析实现](../../tools/analyze_kvzap_trace.py)、[规则化实现](../../tools/evaluate_kvzap_structured_masks.py)、[布局实现](../../tools/evaluate_kvzap_physical_layout.py) |

原始`pilot_inputs/longbench_balanced_v2.jsonl`当前本地缺失，preparation manifest仍在；
accuracy输入不能直接替代它。现有结果可用于许多图表，但不能据此保证所有实验
都能从本地重新运行。数据、trace和日志很多被Git忽略，提交代码不等于备份这些数据。

以上原始结果、冻结登记的早期B4 probe/sentinel、共享代码和schema仍需保留。
仅有加载片段的旧accuracy日志不能算新增的成功或失败实验。研究解释由本报告
承接，技术复核直接查表中数据与源码；本轮没有移动、删除或改写原始资料。
