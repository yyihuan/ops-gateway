# 01 Local Baseline Audit

这个 task 用来演示最小只读审计流程。

它的目标很简单：

- 收集本机基线信息
- 验证 `ops-gate` 的只读审批链路
- 验证 run 目录和本地化路径注入是否正常

执行示例：

```bash
python3 -m devops_runner tasks/01-local-baseline-audit/plans/01-capture-local-baseline.json
```
