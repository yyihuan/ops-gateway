# 仓库工作日志

## 2026-03-27

- 仓库从 MVP/兼容形态继续收口为产品骨架。
- 去掉了根目录 `runner.py` 兼容入口。
- 去掉了历史领域 demo 和旧样本 run，改成两个本地化 demo task。
- skill 从 `audit-runner` 调整为 `ops-gate` 方向。
- 文档统一改成相对路径与产品级表述。
- 备份机制从 `/etc` 特判改成 `step.backup` + 规则驱动模型。
- 新增 `skills/ops-gate/references/`，把审查分级和备份规则拆成独立 Markdown。
