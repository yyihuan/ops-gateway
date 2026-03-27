# Cleanup Plan Template

## 用途

这是为“单独的高风险 cleanup plan”准备的写作模板说明。  
不要把 cleanup 混进别的 plan；cleanup 必须单独成 plan。

模板文件在：

- `plans/templates/cleanup-plan-template.json`

该模板默认**不能直接执行**：其中的占位命令会故意失败，目的是防止有人忘记替换就直接跑高风险清理。

## 编写 cleanup plan 的最低要求

1. cleanup plan 之前，必须已经明确：
   - 当前人工审批对象
   - 精确的 cleanup 范围
   - 可信 rollback 是否存在
   - 需要保护的备份目标
2. 每条命令都必须填写：
   - `review_note`
   - `effects`
3. 真实会改宿主机状态的 step，必须准确声明：
   - `risk.level`
   - `step.backup.rules`
   - `step.backup.paths`（如有额外依赖）
   - `step.backup.location`（如需要单独落点）
   - `effects.requires_root`
   - `effects.writes_paths`
   - `effects.network_targets`（如有）
   - `effects.service_actions`（如有）
4. cleanup plan 至少应拆成 3 类 step：
   - `preflight`：只读确认范围和前置条件
   - `execute`：真正执行清理
   - `verify`：只读验证结果
5. 若存在可信 rollback，就必须写进 `rollback`；若没有可信 rollback，也要在 step 的 `notes` 中明确写清楚原因。

## 审批友好写法

- `review_note` 不要复述命令本身，要直接说明：
  - 这条命令在确认什么、删除什么、停什么、写什么
- `effects` 要站在审批者视角写：
  - `read_only`: 这条命令是不是纯读
  - `requires_root`: 是否必须 root
  - `reads_paths`: 它主要读取哪些路径
  - `writes_paths`: 它主要写入、删除或覆盖哪些路径
  - `network_targets`: 它会访问哪些远端目标
  - `service_actions`: 它会改变哪些服务或系统状态

## 建议的 cleanup 拆分方式

- step 1: 停止和确认 service
- step 2: 清理 runtime / kubelet / control-plane 目录
- step 3: 清理 CNI / 网络残留
- step 4: 验证宿主机已回到可进入 `02-prepare-os` 的状态

不要把这些动作硬塞进一个超大 step；审批者需要看得清楚每一步到底会改什么。

## 使用方式

1. 复制 `plans/templates/cleanup-plan-template.json`
2. 替换 `plan_id`、`plan_title`、`operator`、`target`
3. 把所有占位 `run`、`review_note`、`effects`、`approval_hint` 和 `backup` 改成真实内容
4. 再用 `python3 -c "from devops_runner import validate_plan; validate_plan(...)"` 或直接用 `python3 -m devops_runner <plan.json> --step-id <step_id>` 做审批前校验
