# R1 目录整理与归档方案

日期：2026-11-11；检查起点 `64da68e`。**这是方案与本地引用检查，本轮没有移动、
删除、复制归档任何原文件，也没有改写冻结记录。** 逐项结论写入既有
[01_sources.csv](01_sources.csv)，本页说明分批执行方式。

## 1. 检查结论

R1清单249项中：**223项保留原位，19项为有条件归档候选，7项仍需核对。**
统计单位是清单条目，不是249次实验；目录条目与其中部分文件同时登记，不用于
累加磁盘大小。本次没有形成删除清单。“可归档候选”表示在已检查范围内可提出
迁移方案，不表示已证明任意外部消费者都不使用它。

最重要的修正是：**重复的科学结果不能直接覆盖其冻结路径义务。**

| 发现 | 整理决定 |
|---|---|
| `tests/test_baseline_freeze.py`读取baseline freeze并逐路径检查制品；balanced-v2测试同样检查原路径/内容 | baseline和v2冻结记录及结果保留原位，不能靠更新hash使搬迁“通过” |
| B4 freeze直接登记`accuracy_b4_m0_probe_02`和两个sentinel的run manifest/结果CSV，共6个文件 | 即使结果行被最终筛查覆盖，6个文件仍保留原位 |
| pilot freeze→analysis/run manifest→原trace，且后续复审、A0等使用相同数据路径 | v1/v2 trace和核心分析原位保留；原样本重合不构成迁移依据 |
| `reproduction_notes.md`由baseline脚本默认生成，且被AGENTS和早期说明引用 | 保留原位作复现附件 |
| structured-policy v2没有检出外围路径引用，v3是R1主来源 | 4文件作为一个历史集合，列为条件性归档候选 |
| Full-KV与原KVzap单请求probe没有检出外围路径引用，结果行与最终9请求筛查一致 | 两目录各2文件列为条件性归档候选；不是上面的冻结B4 probe |
| 两份`decoding_growth.csv`只有表头，但位于原分析集合，工具统一生成该文件 | 暂保留，不能把空观察解释成decode增长为零，也不为它们单独拆目录 |

## 2. 引用检查的范围与局限

检查了Git跟踪的本地文本，以及`analysis/experiments/`、`traces/`、`pilot_inputs/`
下的JSON和12份本地相关日志。共读取2,208份不超过5MB的文本，约109MB；另对35份
较大文件流式检查249个目标的完整路径，没有检出新增完整路径引用。

匹配分为完整路径、唯一basename、父目录范围三类；父目录出现只能说明该集合被
提及，不能证明每个子文件实际被读取。R1自身报告/清单/数据包及初始阶段索引
不计为外围共享引用，避免管理文件引用自己造成误判。逐项引用文件和匹配种类已
写入清单的`reference_evidence`列，冻结/Gate链另写`freeze_bindings`。

本次还检查了相关测试和baseline输出代码，并核对v2/v3差异、probe/sentinel与最终
筛查的结果行。未重新计算所有冻结hash、执行完整测试或运行模型。
动态拼接路径、通用通配符、未跟踪CSV里的任意引用、远程工作区、个人shell历史
和外部备份不构成穷尽检查。大型文件只做完整路径搜索，不声称解析了所有字段。
因此“0命中”仍须结合具体集合/脚本用途判断，不等于无依赖证明。

## 3. 保留原位的内容

以下内容构成稳定证据与共享接口，维持现有物理路径，用R1入口聚合阅读：

- baseline配置、结果、冻结记录；Gate A/B、v1/v2和Route-B冻结记录。
- v1/v2主分析、v3结构化结果、最终布局分析、最终9请求筛查。
- 被B4 freeze直接绑定的早期B4 probe和两个sentinel的6个文件。
- 原score/mask、Gate参考、pilot输入/manifest，以及原目录下的制品。
- 论文、共享schema、算法/分析代码、跨阶段计划和复审；不搬入R1独占目录。
- baseline复现说明，以及当前目录中的空decode观察输出。

引用链另外涉及未逐项列入原249项清单的两份`pilot_run_manifest.json`和
`pilot_inputs/longbench_balanced_v2_accuracy.{jsonl,manifest.json}`；它们仍是必要
保存对象，不能因为不在原清单中就清理。249项不是全仓所有传递依赖的全集。

## 4. 可以提出归档的三个具体集合：19项

这里只设计目标位置，**本轮不创建下面的归档树**。目标中的文件保持原内容和文件名，
保留原路径→归档路径对照，不把多次运行合并或重新序列化成一个“新结果”。

```text
analysis/archive/r1/                       # 拟建，尚未创建
  process_logs/                           # 11份过程日志
  superseded_results/
    longbench_balanced_v2_structured_policy_v2/  # 4份文件
  early_screening/
    accuracy_full_probe_01/                # 2份文件
    accuracy_kvzap_probe_01/                # 2份文件
```

**A：11份过程日志。** `logs/`当前12份R1日志中，除
`longbench_balanced_v2_accuracy_gate_01.log`外的11份，拟归入`process_logs/`。
其中`longbench_balanced_v2_first.log`和`prepare_longbench_balanced_v2.log`仍被
`analysis/kvzap_trace.md`引用；执行迁移前须处理这两处引用。旧冻结文档不应为了
归档而修改；如果引用所在资料不允许改，应保留原路径或延后迁移。

**B：structured-policy v2的4文件。** manifest和head bucketing与v3逐字节相同；
request/summary表的共有字段值相同，但v3分别增加`physical_total_padded`和
`physical_compression_factor_padded_weighted`字段。整个v2集合保存为历史版本，
不标成“四个完全重复文件”。本地扫描未检出外围路径引用，仍须确认远程脚本/个人
分析未依赖原目录；v3及其冻结记录保持原位。

**C：Full-KV/原KVzap两个probe，各2文件。** 各保留一份`request_results.csv`和
`run_manifest.json`，结果行与最终9请求同request/variant逐字段一致。本地扫描没有
检出外围路径引用。这两个probe没有被本轮检查的B4 freeze直接绑定；不能把同样
处理套到被冻结的B4 probe/sentinel。

这一步主要减少日常目录中的历史过程与前置集合；不承诺释放大量磁盘，归档也不是
删除。`.log`以及当前experiments/trace/input大量被Git忽略；未来搬到归档目录后
是否受Git跟踪必须逐项确认。归档放在同一磁盘不等于完成备份，也不能默认push
已经保存原始数据。

## 5. 仍需核对的7项

| 项目 | 为什么不能现在决定迁移 | 还需要什么 |
|---|---|---|
| `analysis/kvzap_baseline.md` | 包含命令和指标定义，并相对引用smoke/trace说明 | 决定继续作复现入口还是改为历史附件；若移动须处理相对链接 |
| `analysis/kvzap_smoke_test.md` | 被baseline说明引用；旧环境建议与冻结环境不等价 | 保留准确历史范围，提取仍有用的指导，再决定附件位置 |
| `analysis/kvzap_trace.md` | 同时含旧进度、日志路径、有效性规则和失败审计 | 先分清哪些是当前复现说明、哪些是历史过程，不能整篇当报错归档 |
| `CODEX_FIRST_TASK.md` | 被`analysis/repo_inventory.md`作为初次勘察依据引用 | 决定原位历史依据是否保留；不能破坏勘察记录的来源 |
| `EXPERIMENT_PLAN.md` | 未检出外围引用，但混有未执行设想，尚未逐项接入R1—R6 | 先明确其余报告是否还用这些计划说明，避免把设想当完成结果 |
| `logs/longbench_balanced_v2_accuracy_gate_01.log` | 仅有加载片段，不能据此判成功或失败 | 确认是否对应独有运行/结果位置；先保留 |
| `pilot_inputs/longbench_balanced_v2.jsonl` | 原文件本地缺失，冻结记录仍绑定其身份 | 定位原保存位置/副本；accuracy输入不能直接替代 |

以上仅提议后续检查，不对“仍需核对”的文件重写历史或补造结果。混合说明可以先
退出日常入口，物理位置仍保持；阅读整理不必等所有迁移问题都解决。

## 6. 后续执行顺序与验收

1. **当前批次：** 完成引用与冻结路径盘点、更新清单和本方案；不迁移。
2. **后续归档批次A：** 先处理过程日志及两处文档引用，再单独归档；状态未确认日志排除。
3. **后续归档批次B/C：** 分别处理v2集合和两个未冻结probe；按集合操作，不混入其他实验。
4. **历史说明：** 逐项完成第5节核对，才能决定物理迁移；共享规范和冻结证据继续原位保留。

实际归档前须形成该批次精确源/目标路径和原内容身份对照，确认结果及配置齐全、
外部使用已核对、保存方式可恢复。完成后检查链接、复现入口、冻结制品原路径
仍可用、Git跟踪/忽略状态，再运行适合该变更的检查和`git diff --check`，单独提交。
遇到冻结路径引用就保留原位或延后，不能默默改freeze/manifest，亦不默认用symlink
掩盖路径迁移。此方案没有安排删除或新的算法/综合实验。
