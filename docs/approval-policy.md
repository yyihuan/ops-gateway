# Approval Policy

## 目的

明确 agent 与人工审批对象在操作闸门中的职责边界。

当前默认前提是：

- agent 负责起草、校验、解释和发起 plan
- 人工审批对象负责决定是否允许进入执行
- 建议在 plan 顶层 `operator` 字段里显式写出当前人工审批对象

## 当前人工审批对象

当前仓库里已有两类人工审批对象：

- `tty`
  - 直接在终端输入 `yes / no / edit`
- `web`
  - 在审批页面中点击按钮

后续如果产品化为更完整系统，审批对象应从“后端类型”进一步抽象成显式的 reviewer/approver 配置。

## Agent 可以做什么

- 生成、修改、校验 plan
- 根据 `skills/ops-gate/references/review-rules.md` 判断是否必须进闸
- 根据 `skills/ops-gate/references/backup-rules.md` 为中高风险 step 填写 `step.backup`
- 在执行前解释整份 plan 的目的、风险和阶段顺序
- 在执行某个 step 前，逐条解释该 step 的命令意图和影响
- 在得到明确许可后，发起：

```bash
python3 -m devops_runner <plan.json> --step-id <step_id>
```

- 续跑已有 run：

```bash
python3 -m devops_runner <plan.json> --step-id <step_id> --resume-run <runs/<task_id>/<run_id>>
```

## Agent 不可以做什么

- 代替人工在审批点输入 `yes / no / edit`
- 代替人工在 rollback 提示处做决定
- 把 agent 自身的“准备执行”说明，当成审批动作本身

## 人工审批对象必须做什么

- 在 step 审批点亲自决定是否执行
- 在 rollback 提示处亲自决定是否回滚
- 若使用 `web` 后端，亲自点击审批按钮
- 若切换到 `auto_low_risk`，明确知道这是对当前审批模式的人工变更

## 推荐工作流

1. agent 生成或修改 plan。
2. agent 校验 plan。
3. agent 解释：
   - plan 目标
   - 风险
   - 人工审批对象
   - step 顺序
   - 本次审批阈值
   - 备份范围
4. agent 在执行前逐 step 解释命令与影响。
5. 人工审批对象决定是否放行。
6. 执行完成后，再看 `runs/<task_id>/<run_id>/` 中的证据。

## 当前产品方向

如果下一步要进一步产品化，建议把“审批对象”提升成一等配置，而不是只停留在 `tty/web` 后端层面。这样可以明确：

- 谁是当前人工审批对象
- 谁可以切换审批模式
- 谁对某次运行的放行动作负责
