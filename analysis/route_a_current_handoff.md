# Route-A当前状态

更新：2026-11-12。研究阅读从[项目总览](project_overview_20261111.md)进入；本页只保留接续工作所需状态。

- **功能：** 有界首次packing/publication/read/retire路径已验证。显式、默认关闭的持久页v2 r2通过15/15定向测试，包含同页重读、错误恢复与指定retire排空切点。通用wrapper/v1未改合同；这不是完整持续decode验收。
- **未闭合功能：** 同session多组admission、journal历史安全释放、合法未入组pending的生产归属服务、全容量/并发及数据到数值结果的完整连接。关窗与pending归属参考检查不能替代生产RTL。
- **控制映射：** 已验收RD1＋WCG1，PM1关闭、RD2未集成。原2ns约束下Route-A primary cell area为2,990,737.008920，Full-KV为23,091.432498，约129.517倍；较最初控制映射下降55.47%。
- **时序与成本：** 顶层setup未闭合，补充hold修复亦未实现统一收敛。DC不含后加持久页v2；存储宏/外围、数值与外部服务仍未完整计价，不能据此宣称PPA、系统加速或净硬件收益。
- **当前工作：** 整理研究资料、恢复可读的研究脉络。职责重划与算法—软硬件协同仍待讨论；本轮没有修改RTL、重跑实验或启动DC。

功能、边界与缺口读[H2](hardware_reports/02_rtl_implementation_and_sustained_execution_scope.md)，
存储与遗漏成本读[H3](hardware_reports/03_storage_measurement_boundary_and_complete_cost.md)，
优化结果及负结果读[H4](hardware_reports/04_area_timing_optimization_and_design_review.md)。
原始结果：[持久页r2](route_a_persistent_page_read_r2_result_20261109.json)、
[RD1＋WCG1](dc_rd1_wcg1_full_paired_result_20261109.json)。

当前技术定义仍保留[架构规格](architecture_spec.md)、[端口矩阵](rtl_entry_port_parameter_contract.md)、
[持续执行补齐方案](route_a_continuation_minimal_proposal_20261109.md)和
[pending归属／关窗合同](route_a_pending_origin_and_window_contract_20261109.md)。
冻结记录中的旧硬件路径在Git版本`636c19b`中可查；它们不要求当前目录保留重复研究说明。
