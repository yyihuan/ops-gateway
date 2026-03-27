"""Shared run-context data structures.

This module only defines structured state. It does not execute commands,
render output, or talk to approval backends.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RunPaths:
    """Filesystem locations associated with a single run."""

    backup_root: pathlib.Path
    run_root: pathlib.Path
    run_dir: pathlib.Path
    logs_dir: pathlib.Path
    steps_dir: pathlib.Path
    backups_dir: pathlib.Path
    audit_log_path: pathlib.Path
    resolved_plan_path: pathlib.Path
    plan_copy_path: pathlib.Path
    schema_copy_path: pathlib.Path


@dataclass(slots=True)
class RunContext:
    """Mutable run state shared across extracted modules.

    The `plan` field intentionally remains mutable because approval editing can
    update step definitions in place during a run.
    """

    plan: dict[str, Any]
    plan_path: pathlib.Path
    schema_path: pathlib.Path
    base_run_root: pathlib.Path
    task_id: str
    run_id: str
    resume_run: pathlib.Path | None
    selected_step_mode: bool
    remote_sync_enabled: bool
    approval_backend_name: str
    approval_threshold: str
    approval_mode_state_file: pathlib.Path
    web_host: str
    web_port: int
    paths: RunPaths


__all__ = ["RunContext", "RunPaths"]
