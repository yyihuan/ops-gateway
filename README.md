# Ops Gate

Safety gate for agent operations: structured plans, manual approval, scoped backups, and run evidence.

`Ops Gate` 是一个面向 agent 运维的操作闸门骨架。

它的第一目标不是“记录历史”，而是把所有非基础操作收口到结构化 plan、人工审批和保底备份流程里，尽量降低 agent 误操作带来的数据损失。运行历史追溯仍然保留，但它是第二目标。

## 当前能力

- 用结构化 JSON plan 描述运维步骤
- 对 step 做风险分级与人工审批
- 为中高风险 step 生成 pre/post 备份
- 把执行证据写到 `runs/`
- 用 repo skill 驱动 agent 按规则生成和审查 plan

## 仓库结构

- `devops_runner/`
  - 核心执行引擎
- `skills/ops-gate/`
  - 当前 skill 与 agent 参考规则
- `tasks/`
  - 两个本地化 demo task
- `plans/`
  - 示例与模板
- `docs/`
  - 设计、流程和边界说明
- `runs/`
  - 默认运行证据目录
- `backups/`
  - 默认备份目录
- `state/`
  - 项目内状态目录

## 快速开始

```bash
python3 -m devops_runner tasks/01-local-baseline-audit/plans/01-capture-local-baseline.json
```

```bash
python3 -m devops_runner tasks/02-local-file-lifecycle/plans/01-create-and-delete-demo-file.json
```

优先阅读：

1. `START_HERE.md`
2. `docs/ops-gate-workflow-and-boundaries.md`
3. `docs/design.md`
4. `skills/ops-gate/SKILL.md`
5. `skills/ops-gate/references/review-rules.md`
6. `skills/ops-gate/references/backup-rules.md`

## 许可证

本仓库按内容类型分层许可：

- 代码：`AGPL-3.0-or-later`
- skill、文档和 Markdown 规则文件：`CC BY-SA 4.0`

具体范围见：

- `LICENSE`
- `LICENSE-docs.md`
- `NOTICE`
