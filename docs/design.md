# 设计说明

## 产品目标

当前产品骨架的第一目标是做“agent 运维操作闸门”：

- 允许基础只读动作留在闸门外
- 把所有非基础操作收进结构化 plan
- 在执行前经过人工审批对象确认
- 为执行结果保留结构化 run 证据

历史追溯仍然重要，但它不是第一目标。

## 当前目录结构

```text
.
├── backups/
├── devops_runner/
├── docs/
├── plans/
│   ├── examples/
│   └── templates/
├── runs/
├── schema/
├── skills/
│   └── ops-gate/
│       └── references/
├── state/
├── tasks/
│   ├── 01-local-baseline-audit/
│   └── 02-local-file-lifecycle/
└── tests/
```

## 目录职责

- `backups/`
  - 默认备份根目录。
  - 每个 step 的备份文件会落到 `backups/<task_id>/<run_id>/`，也可以在 `step.backup.location` 下拆分子目录。
- `devops_runner/`
  - 核心执行引擎。
  - 当前主要模块：
    - `plan.py`：plan 校验与 step 选择
    - `render.py`：审批展示渲染
    - `approvals/`：TTY / Web 审批后端与策略
    - `execution.py`：命令执行、stdout/stderr 落盘、环境变量注入
    - `backups.py`：备份目标解析、备份目录解析和归档生成
    - `audit.py`：结构化事件写入 `runner.jsonl`
    - `orchestrator.py`：把校验、审批、执行、同步组装成一次 run
    - `sync.py`：可选同步
- `docs/`
  - 产品和边界说明。
- `schema/step_schema.json`
  - plan 的统一结构约束。
- `plans/examples/`
  - 最小本地样例：
    - `smoke-test.json`
    - `web-auto-approval-test.json`
- `plans/templates/`
  - 通用模板，当前保留 cleanup 模板。
- `skills/ops-gate/`
  - 让 Codex 以“安全闸门”视角理解并修改这个仓库。
- `skills/ops-gate/references/`
  - 专门给 agent 读的规则文件，当前包括审查分级规则和备份规则。
- `runs/`
  - 运行证据输出目录。仓库默认不再保留历史样本 run。
- `state/`
  - 项目内状态目录，当前默认保存审批模式状态文件。
- `tasks/`
  - 两个本地化 demo：
    - `01-local-baseline-audit/`：纯只读基线采集
    - `02-local-file-lifecycle/`：创建并删除仓库内演示文件，覆盖审批、备份和回滚
- `tests/`
  - 针对 plan、渲染、审计、策略和审批后端的回归测试。

## 当前执行模型

统一入口：

```bash
python3 -m devops_runner <plan.json>
```

一次执行的基本流程是：

1. 读取并校验 plan。
2. 渲染 plan/step 审批视图。
3. 根据风险阈值与审批后端决定是否停下来等人工确认。
4. 对高风险 step 或显式声明了 `step.backup` 的 step 先生成 pre 备份。
5. 执行 `pre_checks`、`commands`、`post_checks`。
6. 为同一批目标生成 post 备份，并将结构化事件写入 `logs/runner.jsonl`。
7. 按需执行 rollback 或 `remote_sync`。

## 当前边界

当前系统在“审批链路”和“审计产物”上已经比较清楚，但在“非基础操作强制入闸”这件事上还没有完全产品化：

- 现在能强制的是 step 级审批、备份落盘和 run 级留痕。
- 现在还不能仅凭 `effects.read_only` 自动阻止危险 shell。
- “哪些动作算基础操作、哪些动作必须入闸”目前仍主要靠约定，而不是独立 allowlist/guard 模块。

这个缺口的详细说明见：

- `docs/ops-gate-workflow-and-boundaries.md`
