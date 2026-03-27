# Ops Gate Workflow And Boundaries

## 1. 当前定位

当前仓库的第一目标是“操作闸门”，不是“事后审计平台”。

更准确地说，它现在在做两件事：

1. 把非基础操作包装成结构化 plan 并在执行前停在审批点
2. 把执行结果写成可追溯的 run 证据

其中第一件事优先级更高。

## 2. 当前工作流

当前执行流程可以压缩成 7 步：

1. 编写 plan JSON
2. 用 `schema/step_schema.json` 和 `devops_runner/plan.py` 校验
3. 通过 `devops_runner/render.py` 生成审批视图
4. 由 `devops_runner/approvals/` 决定是否进入人工审批
5. 由 `devops_runner/backups.py` 为高风险或显式声明了 `step.backup` 的 step 解析备份目标并产出 pre 备份
6. 由 `devops_runner/execution.py` 执行命令
7. 由 `devops_runner/backups.py` 产出 post 备份，并由 `devops_runner/audit.py` 和 `orchestrator.py` 写 run 证据

统一执行入口：

```bash
python3 -m devops_runner <plan.json>
```

## 3. 当前硬边界和软边界

### 软边界

以下内容目前主要还是“声明”，不是强约束：

- `effects.read_only`
- `metadata.execution_mode`
- `audit.*` 之类的 step 命名
- `rollback = []`

它们主要服务于：

- 审批展示
- 人类理解
- 风险摘要

### 硬边界

当前真正起作用的硬边界主要只有：

- 风险阈值
- 人工审批对象
- step 级执行停顿点
- 中高风险步骤的 pre/post 备份产物
- run 级结构化留痕

这意味着当前系统已经是“可审批、可追溯”，但还不是“所有非基础操作都能被自动判定并强制入闸”的最终产品形态。

## 4. 当前缺口

如果把目标定义成“除基础读操作外，其他动作都必须进闸”，当前还缺 4 层能力：

1. 基础操作 allowlist
   - 需要明确什么属于闸门外的基础只读动作，例如 `ls`、`cat`、`sed -n`、`find`
2. 非基础操作识别
   - 当前仓库还没有一个独立模块专门判断“这条动作是否必须入闸”
3. 审批对象抽象
   - 当前更像“审批后端”，还不是显式的 approver/reviewer 模型
4. 审计守卫
   - 当前可以审计和审批，但还缺执行前自动拒绝危险 shell 的 guard
5. 自动恢复能力
   - 当前已经能自动按规则备份目标路径，但还不会自动生成恢复命令；rollback 仍需 plan/skill 明确写出

## 5. 当前保留样本

仓库里现在只保留两个本地化 demo，不再保留历史领域 run：

- 本地只读 demo：
  - `tasks/01-local-baseline-audit/`
- 本地写入/删除 demo：
  - `tasks/02-local-file-lifecycle/`
- 最小样例：
  - `plans/examples/smoke-test.json`
  - `plans/examples/web-auto-approval-test.json`

## 6. 建议的产品化拆分

如果要继续打磨成产品，建议按下面 6 层拆：

1. `basic_ops.py` 或同类模块
   - 定义闸门外 allowlist
2. `gate_policy.py` 或同类模块
   - 判定哪些动作必须进入 plan/approval
3. `skills/ops-gate/references/review-rules.md`
   - 把分级和审批建议固化成 agent 可读规则
4. `skills/ops-gate/references/backup-rules.md`
   - 把备份覆盖面和恢复建议固化成 agent 可读规则
5. `approver.py` 或同类模块
   - 抽象人工审批对象
6. `audit.py`
   - 继续只负责 run 证据和结构化事件

## 7. 当前 skill 的正确定位

repo skill 的主要职责应该是：

- 识别哪些操作不该直接跑
- 把非基础操作收敛到 plan
- 明确当前审批对象和审批模式
- 为中高风险步骤明确备份范围和恢复路径
- 在执行前解释边界
- 在执行后保留 run 证据

所以它更像一个“ops gate skill”，而不是单纯的“audit skill”。
