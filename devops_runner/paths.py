"""Path and identifier helpers for run layout compatibility."""

from __future__ import annotations

import pathlib

from devops_runner.constants import DEFAULT_TASK_ID


def slugify(value: str) -> str:
    """Convert an arbitrary identifier into a stable filesystem-safe slug."""

    allowed: list[str] = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_", "."}:
            allowed.append(char)
        else:
            allowed.append("-")
    slug = "".join(allowed).strip("-._")
    return slug or "run"


def infer_task_id_from_run_dir(base_run_root: pathlib.Path, run_dir: pathlib.Path) -> str | None:
    """Infer a task id from either flat or task-scoped run directories."""

    try:
        relative = run_dir.relative_to(base_run_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    if len(relative.parts) >= 2:
        return relative.parts[0]
    return DEFAULT_TASK_ID


def resolve_resume_run_path(raw_resume_run: str, base_run_root: pathlib.Path, task_id: str) -> pathlib.Path:
    """Resolve an explicit, flat, or task-scoped resume target."""

    candidate = pathlib.Path(raw_resume_run)
    if candidate.is_absolute():
        return candidate.resolve()
    resolved_as_given = candidate.resolve()
    if resolved_as_given.exists():
        return resolved_as_given
    flat_candidate = (base_run_root / candidate).resolve()
    if flat_candidate.exists():
        return flat_candidate
    task_scoped_candidate = (base_run_root / task_id / candidate).resolve()
    if task_scoped_candidate.exists():
        return task_scoped_candidate
    if len(candidate.parts) == 1:
        return task_scoped_candidate
    return resolved_as_given


__all__ = ["infer_task_id_from_run_dir", "resolve_resume_run_path", "slugify"]
