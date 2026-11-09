# 持久读取 r2：修复后隔离重跑 — 2026-11-09

**已启动，完整功能验收尚未完成。** 依据[r2修复准备](route_a_persistent_page_read_r2_repair_20261109.md)，用户明确授权修复后重跑。r1失败输入/产物和旧tmux保留；不修改多组admission，不运行DC/STA。输入与阶段快照登记于[JSON](route_a_persistent_page_read_r2_launch_20261109.json)。

| 项目 | 实际值 |
|---|---|
| run ID | `persistent_page_read_v2_20261109_r2` |
| source commit | `40a74b6a259afaaf6aac8efcb7a6c01fb271862a` |
| source archive SHA | `e7a65e92cf22c9c4ab620d3094c94c05b21b6874a8e5d8d053da3196e7a293ee` |
| frozen source files | 155，含r2/原14项/stage-A三个checker |
| flow | `validation_flow=r2_parent_gate` |
| independent tmux | **`kvzap-persistent-read-v2-r2:validation`**，pane PID14445 |
| remote root | `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/persistent_page_read_v2_20261109_r2/` |
| runner log | 上述root下`runner.log` |
| live outer log | `/home/yaz80/wz_project/chisel_projects/kvpress/logs/persistent_page_read_v2_20261109_r2_outer.log` |
| resource settings | heap4GiB、ActiveProcessorCount2、MAKEFLAGS=-j1、ulimit -s unlimited；svsim生成的native build并行参数仍须按实际记录解读 |

pipeline先核输入并编译，然后运行真实R5 parent单项；只有XML/ELF/log/完整typed marker均通过并保存`parent_gate_result.json`，才进入原14项。完整阶段不再次运行parent，不覆盖短测产物。最终合并7 suites／15项native，parent与完整阶段分别记录exit。不能把parent通过、SIMULATION_BEGIN或CPU活动当成15项通过。

**实际阶段快照（2026-11-09 07:24:02 UTC）：** 155份输入hash通过，remote compile exit0、parent exit0；真实父级测试1/1通过，耗时约5.66秒，其XML、543,272-B真实ELF、编译/执行日志和typed marker已由r2 checker严格验收并保存快照。只读再次执行`--parent-only`得到相同验收，不重放native。原14项阶段已经开始，test/runner/tmux外层退出尚未产生，完整功能仍PENDING。

本地最新Test/compile和default-v1/v2完整Chisel/firtool展开检查通过；r2与原checker22项短测试通过。唯一生产源补丁在R5 scanner记账，另外29份生产源与`67459cc`逐字节相同；R3/Admission/M2保护区133,572 bytes保持。whole-DUT timeout增加实际GET快照，原2048clock门槛不变。

用户已被通知等待，结束后再验收。scope仍是小参数internal-backing功能实例、原外部position/partial/R4 reference、门控flag off；不宣称external-v2、数值、完整32K/并发、持续pending或多组admission闭合。无面积、setup/hold、PPA或净收益新结论。

结束后用r2 checker核验，不能误用只验原14项的r1入口：

```bash
python3 /home/yaz80/wz_project/chisel_projects/kvpress/artifacts/persistent_page_read_v2_20261109_r2/workspace/tools/check_persistent_page_read_validation_r2.py /home/yaz80/wz_project/chisel_projects/kvpress/artifacts/persistent_page_read_v2_20261109_r2 --final
```

严格要求compile/parent/full/runner/tmux均退出0，parent快照未漂移，155份输入hash匹配，15项XML与真实native产物闭合、原14项观察完整，r2 RUN_PASS及外层marker闭合。失败保留本run并先定位原因，不自动retry；窗口在shell结束后保留供观察。
