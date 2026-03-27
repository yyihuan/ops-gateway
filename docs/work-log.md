# 仓库工作日志

## 1. 当前状态

- 仓库名称方向已经收口为 `Ops Gate`。
- 本地 Git 仓库已初始化，默认分支为 `main`。
- 远程仓库已绑定并完成首推：
  - `git@github.com:yyihuan/ops-gateway.git`
- 当前代码、文档、demo task、许可证文件已经处于可继续开发的基线状态。

## 2. 已完成事项

- 从旧 MVP / 历史任务仓库继续收口为产品骨架。
- 删除根目录 `runner.py` 兼容入口，统一入口为：
  - `python3 -m devops_runner <plan.json>`
- 删除历史领域 demo 和旧样本 run，只保留两个本地化 demo task：
  - `tasks/01-local-baseline-audit/`
  - `tasks/02-local-file-lifecycle/`
- skill 从 `audit-runner` 调整为 `ops-gate` 方向。
- 文档统一改成相对路径和产品级表述。
- 备份机制从 `/etc` 特判收口为：
  - `step.backup`
  - `write-paths`
  - `etc-if-touched`
- 新增 `skills/ops-gate/references/`，把审查分级和备份规则拆成独立 Markdown。
- 补齐仓库发布所需根文件：
  - `README.md`
  - `LICENSE`
  - `LICENSE-docs.md`
  - `NOTICE`
  - `.gitignore`

## 3. 当前目录分工

- `devops_runner/`
  - 产品核心。
- `skills/ops-gate/`
  - repo skill。
- `skills/ops-gate/references/`
  - agent 读的规则文件。
- `tasks/`
  - 本地化 demo task。
- `plans/`
  - 示例和模板。
- `docs/`
  - 产品文档、工作日志。
- `runs/`
  - 默认运行证据目录。
- `backups/`
  - 默认备份目录。
- `state/`
  - 项目内状态目录。
- `tests/`
  - 回归测试。

## 4. 关键文档入口

- `README.md`
- `START_HERE.md`
- `docs/ops-gate-workflow-and-boundaries.md`
- `docs/design.md`
- `docs/approval-policy.md`
- `skills/ops-gate/SKILL.md`
- `skills/ops-gate/references/review-rules.md`
- `skills/ops-gate/references/backup-rules.md`

## 5. 当前产品定义

产品第一目标：

- 把非基础操作收口到结构化 plan
- 在执行前经过人工审批对象确认
- 在中高风险步骤前后保留保底备份
- 尽可能减少 agent 误操作带来的数据损失

产品第二目标：

- 保留 run 证据和历史追溯

## 6. 当前已知缺口

- 还没有独立的“基础操作 allowlist / guard”模块。
- 还没有在执行前对危险 shell 做机器强制拦截。
- 还没有把人工审批对象建模成一等配置对象，目前仍偏后端层。
- 备份已经能自动生成，但 rollback 仍需 plan 或 skill 明确写出，尚未自动生成恢复命令。
- GitHub 仓库的 `About / topics` 还没有自动写入；当前环境没有 `gh`，所以这一步需要手工在 GitHub 页面补，或后续在有 GitHub CLI / Token 的环境里补。

## 7. GitHub About 建议

建议的仓库描述：

`Safety gate for agent operations: structured plans, manual approval, scoped backups, and run evidence.`

建议的 topics：

- `ops-gate`
- `agent-ops`
- `approval-workflow`
- `change-management`
- `backup`
- `rollback`
- `audit-trail`
- `devops`
- `codex-skill`

## 8. 维护与调试建议

- 先看 `README.md` 和 `START_HERE.md`，不要直接从历史直觉推断产品边界。
- 改动 plan / schema / skill 时，要同步检查：
  - `schema/step_schema.json`
  - `devops_runner/plan.py`
  - `skills/ops-gate/references/*.md`
  - demo task 和模板
- 改动备份逻辑时，要同步检查：
  - `devops_runner/backups.py`
  - `devops_runner/orchestrator.py`
  - `tests/test_phase3c_backups.py`
- 改动 demo plan 或模板时，要跑回归测试，至少执行：
  - `PYTHONPATH=/home/zcj/devops_dev/devops python3 -m unittest discover -s /home/zcj/devops_dev/devops/tests -p 'test_phase*.py'`

## 9. 已验证项

- 当前回归测试通过：
  - `25` 个测试通过
- SSH 远程访问已验证可用。
- 首个提交已推到远程 `main`。

## 10. 本轮遇到过的问题

- 一开始存在路径边界歧义：
  - `/home/zcj/devops`
  - `/home/zcj/devops_dev`
  后续已明确操作范围只在 `/home/zcj/devops_dev`。
- 历史仓库里混有旧 demo、旧 run、兼容入口和旧路径，已经完成清理。
- 机器上没有 `gh`，因此不能直接通过 CLI 更新 GitHub 仓库元信息。

## 11. 后续优先级建议

1. 做“非基础操作识别 + 强制入闸”的 guard 模块。
2. 把人工审批对象提升成显式配置，而不是只停留在 `tty/web`。
3. 为高风险 step 继续打磨自动恢复能力，减少手写 rollback 负担。
4. 视需要补 GitHub About / topics / branch protection / issue 模板。
