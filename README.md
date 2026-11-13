# KVzap：稀疏 KV Cache 存储与执行研究

本项目基于 NVIDIA 的 KVPress 框架，研究论文 **KVzap: Fast, Adaptive, and Faithful KV Cache Pruning** 的稀疏行为，以及如何将保留的 KV 组织成适合后续读取的存储与执行方式。当前重点是弄清算法、软件管理和硬件各自需要承担什么，并评估 packing、调度与资源管理的成本。

研究主线 Route-A 保留 KVzap 的原始 mask：在 KV 创建时预测，在最近的 hot window 内保护 KV，成熟后丢弃不保留的项，将保留项整理为按 layer/KV head 管理的 packed pages，供后续 decode 读取。项目还研究了其他模型、SnapKV 和官方训练 DMS 的适用边界；这些前端的选择时机、生命周期和对照标准并不相同。

已有结果表明指定样本存在逻辑压缩与条件性的存储机会；离线 byte/cycle 模型不是实测加速。现有 RTL 是研究原型，持续 decode、完整系统成本及统一时序仍未闭合。具体结果、适用范围和重要负结果见[项目总览](analysis/project_overview_20261111.md)和 [R1—R6](analysis/algorithm_reports/)。

## 目录结构

| 路径 | 用途 |
| --- | --- |
| [kvpress/presses/](kvpress/presses/) | 基于 KVPress 的算法和模型接口；包括 KVzap、SnapKV 以及 KVzap 路径使用的 DMSPress |
| [kvpress/research/](kvpress/research/) | 离线研究的共享计算：packing、调度、生命周期、Route-A 软件参考、资源模型和跨前端分析 |
| [tools/](tools/) | 模型采集、已有 trace 重放、模拟和结果输出的命令行入口；[download_model_cache.py](tools/download_model_cache.py) 用于下载模型缓存 |
| [tests/](tests/) | 现有算法、trace、模拟和软件参考测试 |
| [pilot_inputs/](pilot_inputs/) | 本地 pilot 请求和准备信息；部分输入可能不在其他 checkout 中 |
| [traces/](traces/) | predictor score/mask 等 trace；`traces/pilots/` 存放本地 pilot 请求的 trace |
| [analysis/experiments/](analysis/experiments/) | 历史实验结果与中间数据，按实验目录保存 |
| [analysis/algorithm_reports/](analysis/algorithm_reports/) | 算法阶段六份研究报告 R1—R6 |
| [analysis/hardware_reports/](analysis/hardware_reports/) | 架构、RTL、成本及面积/时序复盘 H1—H4 |
| [hardware/route_a/](hardware/route_a/) | 现有 Route-A Chisel/RTL 原型及相关实验；不是完整系统实现 |
| [papers/](papers/) | 论文资料，本地 `KVzap.pdf` 是原论文 |
| `.local/server/` | 本机服务器访问说明，不纳入 Git |

`pilot_inputs/`、`traces/` 和 `analysis/experiments/` 中的大部分生成数据受 `.gitignore` 规则影响，**不能假定克隆仓库就包含它们**。开始实验前先确认需要的模型权重、请求和输入数据已经在运行机器上。原始实验输出不要覆盖；入口通常要求输出目录不存在。

## 研究主线与入口

下表中的脚本从仓库根目录以 `python -m tools.<脚本名>` 运行；具体参数使用 `--help` 查看。

| 研究问题 | 主要计算或功能 | 常用入口 |
| --- | --- | --- |
| KVzap 复现与 trace | [KVzapPress](kvpress/presses/kvzap_press.py)、[trace.py](kvpress/trace.py) | [run_kvzap_baseline.py](tools/run_kvzap_baseline.py)、[export_kvzap_predictor_trace.py](tools/export_kvzap_predictor_trace.py)、[analyze_kvzap_trace.py](tools/analyze_kvzap_trace.py) |
| packed-page 容量 | [packing.py](kvpress/research/packing.py) | [simulate_kvzap_packed_pages.py](tools/simulate_kvzap_packed_pages.py) |
| 调度模拟 | [scheduling.py](kvpress/research/scheduling.py) | [simulate_kvzap_route_a1_scheduler.py](tools/simulate_kvzap_route_a1_scheduler.py) |
| decode 生命周期与摊销 | [lifecycle.py](kvpress/research/lifecycle.py)、[amortization.py](kvpress/research/amortization.py) | [run_kvzap_decode_lifecycle_trace.py](tools/run_kvzap_decode_lifecycle_trace.py)、[replay_kvzap_decode_lifecycle_pages.py](tools/replay_kvzap_decode_lifecycle_pages.py)、[simulate_kvzap_route_a3_traffic.py](tools/simulate_kvzap_route_a3_traffic.py) |
| Route-A 软件功能参考 | [route_a.py](kvpress/research/route_a.py)、[route_a_policy_backend.py](kvpress/route_a_policy_backend.py) | [run_kvzap_route_a4_reference.py](tools/run_kvzap_route_a4_reference.py)、[run_kvzap_route_a40_policy_gate.py](tools/run_kvzap_route_a40_policy_gate.py) |
| pending、metadata 与成本 | [pending.py](kvpress/research/pending.py)、[metadata.py](kvpress/research/metadata.py)、[cost.py](kvpress/research/cost.py) | [simulate_kvzap_route_a410_queue_contract.py](tools/simulate_kvzap_route_a410_queue_contract.py)、[simulate_kvzap_route_a4122_metadata_cycle_energy.py](tools/simulate_kvzap_route_a4122_metadata_cycle_energy.py)、[analyze_kvzap_route_a4141_accounted_net_benefit_ledger.py](tools/analyze_kvzap_route_a4141_accounted_net_benefit_ledger.py) |
| 跨模型与前端 | [cross_frontend.py](kvpress/research/cross_frontend.py)、[snapkv.py](kvpress/research/snapkv.py)、[dms.py](kvpress/research/dms.py) | [analyze_cross_frontend_c3_commonality.py](tools/analyze_cross_frontend_c3_commonality.py)、[analyze_snapkv_route_a_p1_packed_opportunity.py](tools/analyze_snapkv_route_a_p1_packed_opportunity.py)、[run_dms_route_a_m4_active_resident_attention_gate.py](tools/run_dms_route_a_m4_active_resident_attention_gate.py) |

生命周期采集在真实模型的 dense 生成过程中只读观察 predictor；后续 page、admission 和流量由软件重放或模型计算。Route-A 软件参考比较相同 mask 下的 attention 组织；无模型参考不是性能实现。SnapKV 的已有证据主要覆盖 terminal prefill，官方 DMS 检查使用原生活跃槽位顺序，不能直接当成 KVzap 的 append-only packed cold。

## 小规模验证

以下命令使用当前仓库的 `.venv`，不下载模型或修改环境；在其他机器上需要先有与项目依赖兼容的 Python 环境。所有命令均从仓库根目录运行。

先检查 packing、调度和 Route-A 软件参考：

```bash
.venv/bin/python -m pytest -q \
  tests/test_simulate_kvzap_packed_pages.py \
  tests/test_simulate_kvzap_route_a1_scheduler.py \
  tests/test_kvzap_route_a4_reference.py

.venv/bin/python -m tools.run_kvzap_route_a4_reference
```

第二条命令用确定性小样例比较分源 attention 合并与同一保留记录的 dense 计算；它不加载真实模型，也不测量速度。

如本地有下列 LongBench core v1 的单条 predictor trace，可以运行一次 A0 容量重放和 A1 调度模拟。输出写入新建的临时目录，不覆盖已有结果：

```bash
trace_dir=traces/pilots/longbench_core_v1_shard0/requests/00010_longbench__multi_news__row000144_04bbfd3c93
output_root=$(mktemp -d /tmp/kvzap-study-XXXXXX)

.venv/bin/python -m tools.simulate_kvzap_packed_pages "$trace_dir" \
  --page-tokens 64 --output-dir "$output_root/a0" &&
.venv/bin/python -m tools.simulate_kvzap_route_a1_scheduler \
  --a0-dir "$output_root/a0" --page-tokens 64 --pe-counts 8 \
  --batch-sizes 1 --output-dir "$output_root/a1"

printf '结果目录：%s\n' "$output_root"
```

A0 输出逐请求、逐 layer/head 的页容量及汇总；A1 输出逐 layer、batch 和策略汇总。A1 是按声明参数执行的离线模拟，单条 trace 的结果不代表真实服务延迟或吞吐。A0 接受的 predictor-only trace schema 以脚本校验为准；早期 Gate-A 的 `kvzap-predictor-trace-1.0` 不能直接用于此入口。

## 后续实验

- 对新模型或请求采集 trace 时，先通过对应入口的 `--help` 确认参数，并用小样本检查模型、predictor、mask 和输出位置；真实模型运行需要相应权重与计算资源。
- 原始输入、旧实验数据和报告分开保存；新实验使用新输出目录，避免覆盖已有结果。
- 模型观察、软件功能、声明参数下的模拟、综合和真实系统测量分别报告。逻辑压缩或模型中的 bytes/cycles 节省不能直接称为物理显存、HBM 流量或端到端加速。
- 已退役的历史脚本可从 Git 历史查看或恢复；旧硬件 scoreboard 的部分 Python 参考已退役，不能直接假定旧验证链仍可运行。
