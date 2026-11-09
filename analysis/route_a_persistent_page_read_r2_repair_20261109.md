# 持久读取 r2：R5查询归属修复与父级前置验证 — 2026-11-09

**状态：修复候选已实现，本地编译/展开与验收脚本短检查通过；native验证仍待远程运行。** 本批接续[r1失败诊断](route_a_persistent_page_read_result_20261109.md)，不覆盖r1输入/产物，不扩大timeout，不修改多组admission或启动DC/STA。[JSON](route_a_persistent_page_read_r2_repair_20261109.json)保存源码、局部检查与保护区证据。

## 最小修复及不变量

R5父级原来将所有共享availability request fire都记入scanner outstanding。现在只有`scanAllowed && availability_lookup_req.fire`才置`scanOutstanding`；v2 mark/read借用端口不会产生scanner未完成事实。原scanner response归属、scanIndex/freeHint、v2 response路径均保留。

新增v2响应fire时的`!scanOutstanding`断言：若有旧scanner响应，v2必须先等其完成，再发自己的请求；这不是清除别人的标志来恢复进展。default-v1只有scanner驱动该端口，fire本身已蕴含scanAllowed，修复不改变其合法握手。没有新增状态位、端口、存储容量或仲裁策略。

唯一生产源修改局限于R5区；R3 wrapper/journal、M2 production control、admission、R2、R6及原2ns约束均保持。现有whole-DUT测试只增加read-only tap和失败时实际GET：controller state、scanOutstanding/scanAllowed、shared req/rsp、v2 response owner等。原2048-clock首次READY门槛不放宽。

## 新增真实R5父级回归

`kvpress.routea.r5.RouteAR5PersistentReadParentSpec`一个case，包真实R5和availability child，不替换内部状态或force信号。R3 durability/visibility与R1维护terminal属于显式unit环境，不能称为完整publication/authority端到端证明。

流程：真实allocation page0 → 接受实际descriptor write request/data并返回匹配terminal → descriptor prerequisite/visibility ACK → mark receipt/ACK → query1与4周期held-result → 另一stream真实allocation → scanner响应仍在途时接受query2 → 原页再次得到canonical grant。

检查PageRef/generation、owner/count/tag、payload/sidecar handles、scanner/v2实际请求归属。`scan_overlap`只在`query.valid && query.ready && scanOutstanding`同拍成立时计入，不能由期望阶段代替实际观察。两次父级allocation不是production多组admission功能；第二页无需publication，本测试不宣称retire闭合。

完整typed结果为：

```text
KVZAP_PERSISTENT_READ_R5_PARENT_PASS real_parent=1 allocations=2 marks=1 queries=2 scan_overlap=1 held_result_cycles=4 ghost_scan_outstanding=0 owner_facts_mocked=1
```

此回归会检查r1遗漏的父级端口归属；本批未在旧r1上重跑新增回归，因此不声称已经取得native负控结果。

## r2运行与验收组织

使用新增r2 runner/checker，保留r1两份文件原样。source/input schema保留版本1，另强制`validation_flow=r2_parent_gate`，不同流程不可混验。新目录无旧target/build，独立tmux运行：

1. 核全部source/archive hash及bytes，Test/compile失败即停。
2. **先跑真实R5 parent单项**，检查XML、真实ELF、编译/执行日志和完整marker，写入`parent_gate_result.json`；失败不进入长整体验证。
3. parent通过后运行原14项：v2 whole-DUT3、原owner5、default-v1功能4、旧BLOCKED诊断2。完整阶段不再运行parent，不覆盖其产物。
4. 合并7 suites／15项native；保留原14项的全部严格门槛，另核parent快照未漂移。最终`--final`要求r2 RUN_PASS、runner/tmux退出0与外层marker。

parent单项、完整14项分别有`parent_exit_status`与`test_exit_status`，compile/runner/tmux另记。parent PASS不等于完整DUT PASS；首次同页两读场景仍由真实packed write/read、S2 fresh generation、consumer/terminal、retire/reclaim验收，不以unit替代。

本地Test/compile通过；default-v1无新增optional端口及完整v2顶层Chisel/firtool lowering结构检查1/1通过，未在本地运行native。r2 checker11/11、原checker11/11通过，含完整marker、parent gate缺失/失败、ELF/XML、快照漂移、原14项缺失和outer失败拒收；脚本语法/help及diff检查通过。这些只授权启动远程功能验证。

## 保留范围与后续门槛

external descriptor backing路径仍未验收。本次独立复核发现，其legacy lookup对共享descriptor-service记账也有类似owner未限定的既有风险（在`822c4c9`已存在），属于源码条件推导、未动态复现；本次internal-backing父级/whole-DUT不展开该分支。该问题登记OPEN，不以本次scanner修复宣称external-v2服务闭合，也不扩大本轮补丁。

通用wrapper/v1、R3 sole publication、R6 authority、两张compact容量、原始mask/admission与多组journal边界均保留。无新增macro实现、映射面积、setup/hold、数值、完整32K持续decode或净收益证据。等待远程结束后分别验收parent gate、完整功能与旧回归；失败保留run并定位，不自动retry。
