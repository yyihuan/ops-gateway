# START HERE

这个仓库现在是一个“面向 agent 运维的操作闸门”产品骨架。

它的第一目标不是“记录历史”，而是：

- 把所有非基础操作收口到可审阅的 plan 流程
- 在执行前经过人工审批对象确认
- 对中高风险步骤先做保底备份
- 降低 agent 误操作导致的数据损失风险

运行历史追溯仍然保留，但它是第二目标。

## 当前目录

- `backups/`
  - 默认备份输出目录。高风险步骤和显式声明了 `step.backup` 的步骤会在这里生成 pre/post 备份。
- `devops_runner/`
  - 产品核心代码。负责 plan 校验、审批、执行、审计日志和同步。
- `docs/`
  - 产品级文档。优先看这里，而不是历史任务材料。
- `schema/`
  - plan/step 结构约束。
- `plans/examples/`
  - 最小 smoke 和审批模式样例。
- `plans/templates/`
  - 高风险 cleanup 模板。
- `runs/`
  - 默认运行输出目录。平时保持为空，真正执行时再生成 run 证据。
- `skills/ops-gate/`
  - 当前 repo skill，以及给 agent 用的审查/备份规则参考。
- `state/`
  - 审批模式状态默认落点，默认文件为 `state/approval_mode.json`。
- `tasks/`
  - 本地化 demo task：
    - `01-local-baseline-audit/`
    - `02-local-file-lifecycle/`
- `tests/`
  - 当前回归测试。

## 推荐阅读顺序

1. `docs/ops-gate-workflow-and-boundaries.md`
2. `docs/design.md`
3. `docs/approval-policy.md`
4. `skills/ops-gate/SKILL.md`
5. `skills/ops-gate/references/review-rules.md`
6. `skills/ops-gate/references/backup-rules.md`
7. `tasks/01-local-baseline-audit/plans/01-capture-local-baseline.json`
8. `tasks/02-local-file-lifecycle/plans/01-create-and-delete-demo-file.json`

## 当前执行入口

不再以根目录 `runner.py` 作为入口。

当前统一入口是：

```bash
python3 -m devops_runner <plan.json>
```

## 默认本地路径

- run 输出默认写到 `runs/`
- backup 输出默认写到 `backups/`
- 审批模式状态默认写到 `state/approval_mode.json`
