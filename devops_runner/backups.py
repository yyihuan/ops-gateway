"""Backup planning and filesystem protection helpers."""

from __future__ import annotations

import hashlib
import json
import pathlib
import tarfile
from collections.abc import Callable
from typing import Any


SUPPORTED_BACKUP_RULES = {"write-paths", "etc-if-touched"}


def _sha256_file(path: pathlib.Path) -> str:
    """Return the SHA-256 digest for a local file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_backup_dir(
    step: dict[str, Any],
    *,
    backup_root: pathlib.Path,
    task_id: str,
    run_id: str,
) -> pathlib.Path:
    """Resolve the destination directory for one step's backup artifacts."""

    backup_config = step.get("backup") or {}
    raw_location = backup_config.get("location")
    if raw_location:
        base_dir = pathlib.Path(raw_location).expanduser()
        if not base_dir.is_absolute():
            base_dir = backup_root / base_dir
    else:
        base_dir = backup_root
    return base_dir.resolve() / task_id / run_id


def resolve_repo_path(raw_path: str, *, project_root: pathlib.Path) -> pathlib.Path:
    """Resolve a backup target path relative to the repository root when needed."""

    path = pathlib.Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def collect_write_targets(step: dict[str, Any], *, project_root: pathlib.Path) -> list[pathlib.Path]:
    """Collect declared write targets from command effects across all step phases."""

    resolved: list[pathlib.Path] = []
    for phase in ["pre_checks", "commands", "post_checks", "rollback"]:
        for command in step.get(phase, []):
            effects = command.get("effects") or {}
            for raw_path in effects.get("writes_paths", []) or []:
                resolved.append(resolve_repo_path(raw_path, project_root=project_root))
    return resolved


def collect_backup_targets(step: dict[str, Any], *, project_root: pathlib.Path) -> list[pathlib.Path]:
    """Resolve the files/directories that should be protected for a step."""

    backup_config = step.get("backup") or {}
    targets: list[pathlib.Path] = [
        resolve_repo_path(raw_path, project_root=project_root)
        for raw_path in backup_config.get("paths", []) or []
    ]
    rules = list(backup_config.get("rules", []) or [])
    write_targets = collect_write_targets(step, project_root=project_root)

    if step["risk"]["level"] in {"high", "critical"} and not rules:
        rules.extend(["write-paths", "etc-if-touched"])

    if "write-paths" in rules:
        targets.extend(write_targets)
    if "etc-if-touched" in rules and any(
        target == pathlib.Path("/etc") or target.is_relative_to(pathlib.Path("/etc")) for target in write_targets
    ):
        targets.append(pathlib.Path("/etc"))

    unique_targets: list[pathlib.Path] = []
    seen: set[str] = set()
    for target in targets:
        key = str(target)
        if key in seen:
            continue
        seen.add(key)
        unique_targets.append(target)
    return unique_targets


def snapshot_paths(
    *,
    step_id: str,
    label: str,
    targets: list[pathlib.Path],
    backup_dir: pathlib.Path,
    log_event: Callable[..., None],
) -> pathlib.Path:
    """Create a tarball snapshot for an explicit set of filesystem targets."""

    backup_dir.mkdir(parents=True, exist_ok=True)
    archive_path = backup_dir / f"{step_id}-{label}-paths.tar.gz"
    sha_path = backup_dir / f"{step_id}-{label}-paths.tar.gz.sha256"
    manifest_path = backup_dir / f"{step_id}-{label}-paths.manifest.json"
    log_event(
        "backup_started",
        step_id=step_id,
        label=label,
        archive=str(archive_path),
        target_count=len(targets),
    )

    included: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    with tarfile.open(archive_path, "w:gz") as tar:
        for target in targets:
            record = {
                "path": str(target),
                "exists": target.exists(),
                "is_dir": target.is_dir() if target.exists() else False,
            }
            if target.exists():
                tar.add(target, arcname=target.as_posix().lstrip("/"), recursive=True)
                included.append(record)
            else:
                missing.append(record)

    manifest_path.write_text(
        json.dumps(
            {
                "step_id": step_id,
                "label": label,
                "included": included,
                "missing": missing,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    digest = _sha256_file(archive_path)
    sha_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    log_event(
        "backup_finished",
        step_id=step_id,
        label=label,
        archive=str(archive_path),
        manifest=str(manifest_path),
        sha256=digest,
        included_count=len(included),
        missing_count=len(missing),
    )
    return archive_path


__all__ = [
    "SUPPORTED_BACKUP_RULES",
    "collect_backup_targets",
    "collect_write_targets",
    "resolve_backup_dir",
    "resolve_repo_path",
    "snapshot_paths",
]
