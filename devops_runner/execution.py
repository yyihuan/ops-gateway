"""Execution helpers for the ops-gate engine."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import threading
from collections.abc import Callable
from typing import Any

from devops_runner.errors import CommandFailure


def tee_stream(stream: Any, target: Any, prefix: str) -> None:
    """Mirror a process stream to a log file and the live console."""

    for line in iter(stream.readline, ""):
        target.write(line)
        target.flush()
        sys.stdout.write(f"{prefix}{line}")
        sys.stdout.flush()


def build_command_env(
    command: dict[str, Any],
    *,
    task_id: str,
    project_root: pathlib.Path,
    base_run_root: pathlib.Path,
    task_run_root: pathlib.Path,
    run_id: str,
    run_dir: pathlib.Path,
    backup_root: pathlib.Path,
    backups_dir: pathlib.Path,
    step_backup_dir: pathlib.Path,
    logs_dir: pathlib.Path,
    steps_dir: pathlib.Path,
    plan_id: str,
    plan_title: str,
    target_host: str,
    target_os: str,
) -> dict[str, str]:
    """Build the environment payload injected into every command."""

    env = os.environ.copy()
    env.update(command.get("env", {}))
    env["RUNNER_TASK_ID"] = task_id
    env["RUNNER_PROJECT_ROOT"] = str(project_root)
    env["RUNNER_BASE_RUN_ROOT"] = str(base_run_root)
    env["RUNNER_TASK_RUN_ROOT"] = str(task_run_root)
    env["RUNNER_RUN_ID"] = run_id
    env["RUNNER_RUN_DIR"] = str(run_dir)
    env["RUNNER_BACKUP_ROOT"] = str(backup_root)
    env["RUNNER_BACKUPS_DIR"] = str(backups_dir)
    env["RUNNER_STEP_BACKUP_DIR"] = str(step_backup_dir)
    env["RUNNER_LOGS_DIR"] = str(logs_dir)
    env["RUNNER_STEPS_DIR"] = str(steps_dir)
    env["RUNNER_PLAN_ID"] = plan_id
    env["RUNNER_PLAN_TITLE"] = plan_title
    env["RUNNER_TARGET_HOST"] = target_host
    env["RUNNER_TARGET_OS"] = target_os
    return env


def execute_command(
    *,
    step_id: str,
    phase: str,
    command: dict[str, Any],
    command_index: int,
    steps_dir: pathlib.Path,
    env: dict[str, str],
    default_timeout: int,
    stream_join_timeout: int,
    slugify_func: Callable[[str], str],
    log_event: Callable[..., None],
) -> None:
    """Run a single phase command and emit stable audit events."""

    phase_dir = steps_dir / step_id / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{command_index:02d}-{slugify_func(command['id'])}"
    stdout_path = phase_dir / f"{base_name}.stdout.log"
    stderr_path = phase_dir / f"{base_name}.stderr.log"
    timeout = command.get("timeout_seconds", default_timeout)
    shell = command.get("shell", "/bin/bash")
    cwd = command.get("cwd")
    log_event(
        "command_started",
        step_id=step_id,
        phase=phase,
        command_id=command["id"],
        command_name=command["name"],
        run=command["run"],
        cwd=cwd,
        timeout_seconds=timeout,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w",
        encoding="utf-8",
    ) as stderr_handle:
        process = subprocess.Popen(
            command["run"],
            shell=True,
            executable=shell,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        stdout_thread = threading.Thread(
            target=tee_stream,
            args=(process.stdout, stdout_handle, f"[{step_id}:{phase}:{command['id']}:stdout] "),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=tee_stream,
            args=(process.stderr, stderr_handle, f"[{step_id}:{phase}:{command['id']}:stderr] "),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        timed_out = False
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            returncode = process.wait()
        stdout_thread.join(timeout=stream_join_timeout)
        stderr_thread.join(timeout=stream_join_timeout)
        if stdout_thread.is_alive() or stderr_thread.is_alive():
            log_event(
                "stream_join_timeout",
                step_id=step_id,
                phase=phase,
                command_id=command["id"],
                join_timeout_seconds=stream_join_timeout,
                stdout_alive=stdout_thread.is_alive(),
                stderr_alive=stderr_thread.is_alive(),
            )
    log_event(
        "command_finished",
        step_id=step_id,
        phase=phase,
        command_id=command["id"],
        returncode=returncode,
        timed_out=timed_out,
    )
    if timed_out and not command.get("allow_failure", False):
        raise CommandFailure(step_id, phase, command["id"], returncode)
    if returncode != 0 and not command.get("allow_failure", False):
        raise CommandFailure(step_id, phase, command["id"], returncode)


def execute_phase(
    *,
    step: dict[str, Any],
    phase: str,
    command_runner: Callable[[str, str, dict[str, Any], int], None],
    log_event: Callable[..., None],
) -> None:
    """Run all commands for one step phase through the provided executor."""

    commands = step[phase]
    log_event("phase_started", step_id=step["id"], phase=phase, command_count=len(commands))
    for command_index, command in enumerate(commands, start=1):
        command_runner(step["id"], phase, command, command_index)
    log_event("phase_finished", step_id=step["id"], phase=phase, command_count=len(commands))


__all__ = [
    "build_command_env",
    "execute_command",
    "execute_phase",
    "tee_stream",
]
