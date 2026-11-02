# Active handoff: Route-A control-refinement paired DC — 2026-11-02

## Current objective

The active task is to determine whether the first bounded Route-A control
realization refinement produces a real mapped improvement under the unchanged
paired `dc_feasibility_fair_v1` contract.  It is not a new architecture stage
and does not reopen pruning, admission, R3 publication, R6 authority, R2/R1
ordering, page size, scheduling, or the bounded single-record direct-pending
scope.

The comparison must keep Full-KV and Route-A under the same TSMC28 candidate
library and numerical constraints: 2.0 ns clock, 0.10/0.02 ns setup/hold
uncertainty, 0.20 ns input/output delay, 0.05 ns input transition, and 0.005 pF
lightweight output load.  Reset remains synchronous and timed.  There is no
false-path or multicycle exception.

## Why the refinement exists

The first paired DC feasibility run
`dc_feasibility_fair_r5desc_20261029_r1` completed tool/link/provenance closure
but did not close Route-A timing or structural cleanliness:

| result | Full-KV | Route-A |
| --- | ---: | ---: |
| cell area | 23,091.432498 | 6,716,537.642416 |
| WNS | 0.00 ns | -0.31 ns |
| TNS | 0.00 ns | -7,318.06 ns |
| setup violations | 0 | 34,814 |

Saved-DDC diagnosis found that `route_a_metadata_admission_bridge` duplicated
the complete `36 x 64 x 281-bit` pending-member binding ledger already owned
by R3/P3.  It contributed 662,404 mapped sequential cells and 42.2% of the
old Route-A mapped area.  The apparent 1,298,154-load direct-pending net was
also proved to be a transient compiler alias of the top clock, not a semantic
direct-pending broadcast.

The bounded RTL change removes only that duplicate ledger.  The bridge now
retains the 64-bit member mask, mapping reference/owner, and the group,
credit, and append-order state it actually consumes.  R3/P3 remains the full
membership owner.  No authority or functional semantic moved.

## Completed refinement evidence

- RTL/source state commit: `a6acd4a`.
- Directed production tests: 8/8 passed.
- Same-instance Route-A measurement-DUT tests: 4/4 passed after the bounded
  ChiselSim root repair.
- Full cross-stage non-regression: 10 suites / 41 actual tests passed.
- Refined split successor: 48 SystemVerilog files, source closure PASS.
- Required typed port families: 16/16 present.
- Required production control owners: 12/12 present and non-black-box.
- Raw Route-A typed array interiors: 4/4 present.
- Paired typed array proxies: 5/5 passed, including Full-KV S2.
- Old R5 functional descriptor backing tokens: absent.
- Raw generated metadata-bridge state: 662,504 -> 17,492 bits, a reduction of
  645,012 generated logical state bits.

The generated-state result is not mapped area.  The prior DDC had optimized
100 of the old raw bits, so only the active successor DC can determine the
new mapped sequential count and area.

The frozen paired input archive is
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/control_refine_a6acd4a_p6_paired_input.tar.gz`,
SHA-256
`1b5ac01cd35c77c37c6d7a08843c8554ec2458eb25cc9d7d6cafbefc873ec33d`.
The active DC input is proxy root
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/control_refine_a6acd4a_p6_dc_array_proxy_r2`.
Arrays and external services remain nonzero/unestimated.

## Active remote run

The authorized paired successor DC run is active in:

```text
host:       dc-server
tmux:       kvzap-control-refine:p7-dc
run id:     dc_feasibility_fair_control_refinement_20261102_r1
run root:   /home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/
            dc_feasibility_fair_control_refinement_20261102_r1/
live log:   /home/yaz80/wz_project/chisel_projects/kvpress/logs/
            control_refine_p7_dc_20261102.log
```

Snapshot when this handoff was written:

- `KVZAP_DC_FEASIBILITY_FULL_KV_EXIT=0` is present.
- Full-KV exactly reproduces the old fair-v1 result: cell area
  23,091.432498, WNS/TNS 0, and zero violating paths.
- Route-A is still running in its 48-file analyze/elaborate flow; `dc_shell`
  is live and consuming one CPU core.
- There is no Route-A exit marker and no paired `RUN_PASS` yet.  This snapshot
  must not be treated as completion evidence.

The Full-KV analyze log prints the same nonfatal verification-include `VER-41`
seen with the earlier layout; verification files remain in the unchanged
`route_a_control_projection_split/verification/` closure and DC continues to
elaborate/map.  Preserve it as a cleanliness item rather than misclassifying
it as a new successor RTL failure.

## First actions in the next conversation

Do not restart or kill the run merely because output is quiet.  First inspect:

```bash
ssh dc-server 'tmux display-message -p -t kvzap-control-refine:p7-dc \
  "dead=#{pane_dead} status=#{pane_dead_status}"; \
  tmux capture-pane -p -t kvzap-control-refine:p7-dc -S -120; \
  grep -E "KVZAP_DC_FEASIBILITY_(FULL_KV|ROUTE_A)_EXIT|KVZAP_DC_FEASIBILITY_RUN_PASS|KVZAP_CONTROL_REFINE_P7_DC_EXIT" \
  /home/yaz80/wz_project/chisel_projects/kvpress/logs/control_refine_p7_dc_20261102.log || true; \
  ps -u yaz80 -o pid,etime,pcpu,pmem,rss,cmd | grep -E "common_shell_exec|dc_shell" | grep -v grep || true'
```

If the run is still active, report its exact stage and wait for user notice.
If it has finished, verify native artifacts rather than accepting a shell
marker alone:

1. Require Full-KV and Route-A exit 0, paired `RUN_PASS`, and outer P7 exit 0.
2. Recheck copied manifests, archive/library/proxy hashes, filelists, and all
   five array-proxy instance reports.
3. Require both DDCs, mapped HDL, QoR, hierarchy area, timing, constraint,
   check-design/check-timing, reference, port, and setup/hold reports.
4. Compare against the immutable baseline run
   `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/dc_feasibility_fair_r5desc_20261029_r1/`.
5. Report total/sequential/combinational area; hierarchy deltas for
   `route_a_metadata_admission_bridge`, `route_a_m2_p3_wrapper`,
   `route_a_page_manager`, and M2 production control; WNS/TNS and violating
   paths; high-fanout warnings; and lint grouped by root cause.
6. Keep separate verdicts for tool/input closure, mapped-area improvement,
   timing closure, structural cleanliness, and PPA/net benefit.

Do not selectively relax Route-A constraints, black-box parent control,
delete real state, enlarge Full-KV, or count arrays/external services as zero.
Do not claim PPA, physical implementation, system speedup, or KVZap net
benefit from this logic-only feasibility comparison.

## Repository state at handoff

- Branch: `research/kvzap-latest`.
- Preparation HEAD before this handoff document: `4d8ca85`.
- Important commits: `0107c09` compact RTL, `1465900` full-root test repair,
  `a6acd4a` functional acceptance, `961f19e` successor state checker,
  `328ed75` successor generator, `cc6a4b6` proxy materializer, `3eaf5ff`
  successor gate documentation, and `4d8ca85` fair-v1 run preparation.
- Preserve the user's worktree and remote artifacts; never reset/clean or
  overwrite an immutable run directory.

## Ready-to-paste prompt for a new conversation

> 在 `/home/wz/AI/kvpress` 的 `research/kvzap-latest` 分支继续 KVZap
> Route-A control-realization refinement。开始前完整阅读 `AGENTS.md`、
> `analysis/architecture_spec.md`、`analysis/route_a_current_handoff.md`、
> `analysis/route_a_document_map.md`、
> `analysis/dc_control_realization_diagnosis_20261101.md`、
> `analysis/dc_control_refinement_successor_20261102.md` 和
> `analysis/dc_control_refinement_active_run_handoff_20261102.md`。当前不是
> 新架构规划，也不是 PPA 阶段；目标是在完全相同的
> `dc_feasibility_fair_v1` 条件下，验证 compact metadata-admission bridge
> 是否真正降低 Route-A 映射面积、时钟负载和 lint，并观察时序变化。
> 已完成 8/8 directed、4/4 full-root、41/41 cross-stage 非回归；新的
> 48-file successor、16/16 typed ports、12/12 production owners、5/5 array
> proxies 均已通过。metadata bridge 的 raw generated state 从 662,504 bit
> 降到 17,492 bit，但这还不是 mapped area。远程 paired DC 正在
> `dc-server` 的 tmux `kvzap-control-refine:p7-dc` 运行，run ID 为
> `dc_feasibility_fair_control_refinement_20261102_r1`，总日志为
> `/home/yaz80/wz_project/chisel_projects/kvpress/logs/control_refine_p7_dc_20261102.log`。
> 交接快照中 Full-KV 已 EXIT=0 且精确复现旧结果，Route-A 仍在运行。
> 首先只读检查 tmux、进程、exit markers 和 native reports；不要重启、
> kill 或重复综合，除非确认失败并定位原因。结束后逐项核验 hashes、
> DDC/mapped HDL、area hierarchy、sequential/combinational area、WNS/TNS、
> violating paths、fanout 和 lint，并与不可变 baseline
> `dc_feasibility_fair_r5desc_20261029_r1` 比较。分别给出 tool/input、
> area、timing、cleanliness verdict；不得宣称 PPA、外部服务零成本、
> 系统加速或硬件净收益。每个完成批次运行检查、更新 live 文档、
> `git diff --check` 并单独提交。
