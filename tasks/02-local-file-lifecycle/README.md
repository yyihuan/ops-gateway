# 02 Local File Lifecycle

这个 task 用来演示一个最小但完整的写操作链路：

- 在仓库 `sandbox/` 下创建文件
- 对删除动作触发高风险审批
- 为删除前状态生成备份
- 在 rollback 中从备份恢复

执行示例：

```bash
python3 -m devops_runner tasks/02-local-file-lifecycle/plans/01-create-and-delete-demo-file.json
```
