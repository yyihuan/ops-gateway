# Backup Rules

## 目标

备份不是为了“看起来安全”，而是为了在 agent 出错时尽可能减少损失，并给 rollback 提供可信输入。

## 1. 默认目录

- run 证据默认放在 `runs/`
- backup 默认放在 `backups/`
- 可以通过 CLI 改：

```bash
python3 -m devops_runner <plan.json> --backup-root <path>
```

## 2. Step 字段

高风险或需要保护的 step 使用：

```json
"backup": {
  "location": "optional-subdir",
  "paths": ["relative/or/absolute/path"],
  "rules": ["write-paths", "etc-if-touched"]
}
```

说明：

- `location`
  - 可选。相对路径会挂到 `backup_root` 之下。
- `paths`
  - 明确补充需要一起保护的路径。
- `rules`
  - 用规则自动扩展备份目标。

## 3. 当前支持的规则

### `write-paths`

把当前 step 所有命令里声明的 `effects.writes_paths` 都纳入备份目标。

用途：

- 覆盖单文件写入
- 覆盖删除前保护
- 覆盖局部目录替换

### `etc-if-touched`

如果当前 step 的 `writes_paths` 触及 `/etc` 或其子路径，就把 `/etc` 一起纳入备份目标。

用途：

- 避免配置类变更只备份了单文件，却遗漏了关联配置上下文

## 4. 当前默认保底

- `high` / `critical` step 如果没有显式给 `backup.rules`
  - 系统会默认按 `write-paths` + `etc-if-touched` 解析备份目标
- `medium` step
  - 建议显式给 `backup.rules`
  - 尤其是覆盖已有文件时

## 5. Plan 作者规则

- 所有会写、删、覆盖的目标都必须准确出现在 `effects.writes_paths`
- 删除操作也要把“将被删掉的路径”写进 `writes_paths`
- 如果还有额外依赖需要一起保护，用 `backup.paths` 补充
- 如果一个 step 的备份想单独放目录，用 `backup.location`

## 6. 当前产物

每次备份会产出：

- `*-paths.tar.gz`
- `*-paths.tar.gz.sha256`
- `*-paths.manifest.json`

manifest 会标记：

- 哪些路径被打包了
- 哪些路径当时不存在

## 7. 恢复方式

当前系统会自动做备份，但不会自动生成恢复命令。  
rollback 仍然需要 plan 或 skill 明确写出来。

默认恢复思路：

1. 找到本 step 的 pre 备份目录
2. 找到对应的 `*-pre-paths.tar.gz`
3. 用 manifest 确认成员路径
4. 用 `tar -xzf ... -C / <member>` 恢复

命令环境里可直接用：

- `RUNNER_PROJECT_ROOT`
- `RUNNER_BACKUP_ROOT`
- `RUNNER_BACKUPS_DIR`
- `RUNNER_STEP_BACKUP_DIR`

## 8. 例子

删除仓库内单文件时：

```json
"backup": {
  "rules": ["write-paths"]
}
```

修改 `/etc` 下配置时：

```json
"backup": {
  "rules": ["write-paths", "etc-if-touched"]
}
```
