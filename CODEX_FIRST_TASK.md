# CODEX_FIRST_TASK.md

请先不要实现结构化剪枝或硬件模型。完成以下仓库勘察任务。

## 任务

1. 阅读：
   - `AGENTS.md`
   - `RESEARCH_CONTEXT.md`
   - 仓库 README
   - `papers/` 中的 KVzap 论文
2. 定位：
   - 主推理入口；
   - benchmark/evaluation 入口；
   - KVzap predictor 加载位置；
   - score 生成位置；
   - threshold comparison 位置；
   - sliding-window 实现；
   - K/V 实际压缩或索引位置；
   - decoding 中 score buffer 的实现；
   - 结果保存位置。
3. 创建 `analysis/repo_inventory.md`，包括：
   - 目录结构；
   - 关键文件和函数；
   - 张量 shape；
   - 当前 pruning timing；
   - 官方运行命令；
   - 可用模型/checkpoint/benchmark；
   - 可能的 trace hook 点；
   - 风险与未知项。
4. 提出一个最小 trace patch 计划，但暂不修改代码。计划必须说明：
   - 修改哪些文件；
   - 如何保证默认行为不变；
   - 如何只导出一个 request；
   - 如何验证输出不变；
   - trace 的预期大小。

## 禁止事项

- 不运行长 benchmark；
- 不下载新模型；
- 不训练 predictor；
- 不修改 pruning 语义；
- 不假设 CLI 参数；
- 不重构官方代码。

