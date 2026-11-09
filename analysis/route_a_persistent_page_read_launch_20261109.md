# 持久页读取 v2：隔离功能验证启动 — 2026-11-09

**已启动，尚未功能验收。** [实现准备](route_a_persistent_page_read_preparation_20261109.md)中的source candidate已独立冻结并上传；不修改多组admission，不运行DC/STA，不影响旧tmux/结果。输入、上传、启动快照见[JSON](route_a_persistent_page_read_launch_20261109.json)。用户已被通知等待，后续结束后由用户通知再验收，不自动重启。

| 项目 | 实际值 |
|---|---|
| run ID | `persistent_page_read_v2_20261109_r1` |
| 冻结源码 | `1d49fc8a8716c6b3e117e62bb6d5ae97f5693118` |
| archive SHA-256 | `40973dc895eb4a72798aeb9da760efdac8d71a1f79614857f392ddacef7ab119` |
| 输入闭合 | 152 files，archive/manifest/每文件hash与bytes实际核验通过 |
| tmux | **`kvzap-persistent-read-v2-r1:validation`**，pane PID4056 |
| remote root | `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/persistent_page_read_v2_20261109_r1/` |
| runner log | 上述root下`runner.log`，最终`outer.log`也在该root |
| live outer log | `/home/yaz80/wz_project/chisel_projects/kvpress/logs/persistent_page_read_v2_20261109_r1_outer.log` |
| 资源 | Java heap4GiB、ActiveProcessorCount2、MAKEFLAGS=-j1、ulimit -s unlimited；新workspace无旧target/build |

2026-11-09 05:56:50 UTC快照：`INPUT_PASS files=152`、`COMPILE_PASS`、`SIMULATION_BEGIN`各一次，**remote compile exit0**；test/runner/tmux wrapper的退出文件均尚未产生。主30份、test90份Scala源码已编译；验证流程已进入仿真构建/执行阶段，不能由此宣称14项PASS。

14项native验收包含：v2 whole-DUT3、S2 owner1、R5 availability1、controller/真实R6 owner3、default-v1 R3回归4、default-v1旧BLOCKED诊断2。新功能证据必须有首次真实packed write、同PageRef两次实际读取、fresh S2 generation、两次四消费者完成、无错误资源副作用、真实retire/reclaim。旧诊断的BLOCKED不能算新功能成功。外部position/partial/R4与小参数、门控flag off/numeric未闭合边界保持。

默认v1无optional端口和完整v2 top的本地Chisel/firtool检查通过，Scala Test/compile通过，新checker11/11＋旧checker9/9短测试通过；这些是启动准入，不是native结果。R3/Admission/M2与R2保护源区逐字节相同；R6 authority规则、R3 publication与原2ns条件不变。

运行结束后须执行：

```bash
python3 /home/yaz80/wz_project/chisel_projects/kvpress/artifacts/persistent_page_read_v2_20261109_r1/workspace/tools/check_persistent_page_read_validation.py /home/yaz80/wz_project/chisel_projects/kvpress/artifacts/persistent_page_read_v2_20261109_r1 --final
```

该检查要求所有source/archive哈希、14项XML无fail/error/skip、14套真实native ELF/编译日志/执行脚本、逐项精确结果与owner marker、runner exit0/RUN_PASS和tmux wrapper exit0/outer marker闭合。shell结束后保持tmux窗口供观察；窗口存在或CPU活跃不表示成功。失败先定位具体原因，保留本run，不自动retry或覆盖。功能、完整持续范围、数值对应、成本与时序分别下结论。
