# KVzap研究资料入口

从[项目总览](project_overview_20261111.md)开始。算法阶段读R1—R6，硬件阶段读H1—H4；
这些报告按目的、方案、结果与分析串起研究过程。

| 算法报告 | 硬件报告 |
|---|---|
| [R1 复现与路线筛选](algorithm_reports/01_reproduction_and_route_selection.md) | [H1 架构与职责边界](hardware_reports/01_architecture_and_software_hardware_boundaries.md) |
| [R2 Packing、调度与摊销](algorithm_reports/02_packing_scheduling_and_amortization.md) | [H2 RTL与持续执行范围](hardware_reports/02_rtl_implementation_and_sustained_execution_scope.md) |
| [R3 功能参考与执行观察](algorithm_reports/03_functional_reference_and_execution_observations.md) | [H3 存储与完整成本](hardware_reports/03_storage_measurement_boundary_and_complete_cost.md) |
| [R4 跨模型与前端边界](algorithm_reports/04_cross_model_and_frontend_boundaries.md) | [H4 面积／时序优化与复盘](hardware_reports/04_area_timing_optimization_and_design_review.md) |
| [R5 Pending与metadata](algorithm_reports/05_pending_and_metadata_resource_exploration.md) | |
| [R6 前RTL成本与架构入口](algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md) | |

需要复核时，从报告进入原始JSON/CSV和源码。[experiments/](experiments/)保存运行结果，
[架构规格](architecture_spec.md)与[端口矩阵](rtl_entry_port_parameter_contract.md)用于核查技术定义。
研究过程不再依赖启动、重试和重复交接。冻结记录保留原样，其中旧硬件路径按Git版本
`636c19b`解释。大型trace、日志或数据可能被Git忽略，文档提交不等于数据备份。
