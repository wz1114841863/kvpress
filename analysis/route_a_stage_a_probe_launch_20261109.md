# 阶段 A 当前 RTL 连续执行探针：远程启动 — 2026-11-09

用户授权的两个独立场景已冻结并启动，**没有修改生产RTL，也没有启动DC／STA**。本记录是启动快照，尚不是编译、仿真或持续功能验收。准备细节见 [probe preparation](route_a_stage_a_probe_preparation_20261109.md)，全部输入／脚本／资源与启动状态见 [JSON](route_a_stage_a_probe_launch_20261109.json)。

| 项目 | 值 |
|---|---|
| Run ID | `stage_a_continuation_probe_20261109_r1` |
| Source commit | `0aa5472a25d5dd4451dee39ef370c57706f57f79` |
| 生产RTL对照 | `097533d`；24个tracked `src/main`文件逐字节相同 |
| Archive | 17,109,911 bytes，140个输入文件 |
| Archive SHA-256 | `e595ed19730dd393693589d7c884ba90eb1cd7febd1c03fd1d6fbb844bad8301` |
| Source manifest SHA-256 | `50248fb6d429fd64d5a554b926d48f6f759944e0ba73f81cbe1fb2dae39e78da` |
| 独立tmux | **`kvzap-stage-a-probes-r1:probes`** |
| 启动时间 | 2026-11-09 11:32:08 Asia/Shanghai（03:32:08 UTC） |

远程base为 `/home/yaz80/wz_project/chisel_projects/kvpress`：

```text
日志：logs/stage_a_continuation_probe_20261109_r1.log
结果：artifacts/stage_a_continuation_probe_20261109_r1/
输入：bundles/stage_a_continuation_probe_20261109_r1.tar.gz
外层状态：artifacts/stage_a_continuation_probe_20261109_r1_tmux_exit_status
```

观察命令：

```bash
ssh dc-server
tmux attach -t kvzap-stage-a-probes-r1
```

## 已核验与仍在等待的事项

- 本地9项postcheck边界测试、Scala parser、runner语法／help、旧阶段A的16份input pins和diff检查通过。代码／准备批次单独提交为`0aa5472`。
- 上传后的archive／runner／tmux wrapper分别重哈希；没有覆盖旧目录／日志。启动前内存可用129,762,880 KiB，未观察到其他native/java任务；旧tmux均保留，不清理／kill／合并。
- runner实际输出 `KVZAP_STAGE_A_PROBES_INPUT_PASS files=140`，Java11／SBT成功加载隔离workspace。最后启动快照为 **正在编译24个main Scala sources**；compile/test/outer markers尚不存在。
- 随后依次执行`Test / compile`和`testOnly kvpress.routea.RouteAStageAContinuationProbeSpec`，最后独立postcheck；若任一阶段失败，保留现场，不自动重跑。
- 两项各自先完成真实packed写读、四消费者和首个terminal，再定位第二次读取／第二组admission。test-only taps只观察，不制造内部权限。
- 测试档为16 stream slots、gate关闭；外部position backing和固定partial/R4协议包明确保留。不能称full32K或WCG1全顶层动态验证、数值闭合、面积／时序结果。

用户已收到独立tmux与等待通知。待用户通知远程结束后，检查compile/test/outer退出状态、XML恰2项、实际marker、source／archive hashes、首轮数据与内部证据。**诊断PASS仅说明具体有界阻断被复现，不代表持续功能PASS。** 若阻断处停止，最终retire/reclaim未到达，也不能冒充新的完整持续witness。

## 编译启动后核验

同一run的随后只读快照确认`compile_exit_status=0`，实际`KVZAP_STAGE_A_PROBES_COMPILE_PASS`齐全；SBT编译耗时39s，于2026-11-09 11:32:52 Asia/Shanghai完成。runner已进入`KVZAP_STAGE_A_PROBES_SIMULATION_BEGIN`，test／outer exit仍不存在。这里只提升编译完成状态，未接受elaboration／Verilator构建／两个实际场景结果；上面的初始启动快照保持原记录。
