"""TTY approval backend and JSON step editing helpers."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from typing import Any, TextIO

from devops_runner.approvals.base import ApprovalBackend
from devops_runner.errors import CommandFailure, RunnerError


def choose_editor(
    *,
    env: Mapping[str, str] | None = None,
    which_func: Callable[[str], str | None] = shutil.which,
) -> str:
    """Return the preferred editor command for interactive step editing."""

    effective_env = dict(env or {})
    editor = effective_env.get("EDITOR")
    if editor:
        return editor
    for candidate in ["vi", "vim", "nano"]:
        if which_func(candidate):
            return candidate
    raise RunnerError("no editor found; set EDITOR to enable step editing")


def edit_step(
    step: dict[str, Any],
    *,
    load_json: Callable[[pathlib.Path], Any],
    validate_step: Callable[[dict[str, Any], int], None],
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Open a step in an editor, reload it, and validate the edited payload."""

    temp_path: pathlib.Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            temp_path = pathlib.Path(handle.name)
            handle.write(json.dumps(step, ensure_ascii=False, indent=2) + "\n")
        editor = choose_editor(env=env)
        subprocess.run([editor, str(temp_path)], check=True)
        edited = load_json(temp_path)
        if not isinstance(edited, dict):
            raise RunnerError("edited step must be a JSON object")
        validate_step(edited, 0)
        return edited
    except subprocess.CalledProcessError as exc:
        raise RunnerError(f"editor exited with code {exc.returncode}") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


class TTYApprovalBackend(ApprovalBackend):
    """Approval backend that interacts with the operator via stdin/stdout."""

    def __init__(
        self,
        *,
        plan: dict[str, Any],
        render_step: Callable[[dict[str, Any]], None],
        log_event: Callable[..., None],
        approval_threshold: str,
        initial_run_approval_mode: str,
        step_requires_approval: Callable[[dict[str, Any]], bool],
        mode_auto_approves_step: Callable[[str, dict[str, Any]], bool],
        edit_step: Callable[[dict[str, Any]], dict[str, Any]],
        sync_plan_copy: Callable[[], None],
        execute_phase: Callable[[dict[str, Any], str], None],
        input_func: Callable[[str], str] = input,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> None:
        """Store explicit dependencies for TTY approval operations."""

        self._plan = plan
        self._render_step = render_step
        self._log_event = log_event
        self._approval_threshold = approval_threshold
        self._initial_run_approval_mode = initial_run_approval_mode
        self._step_requires_approval = step_requires_approval
        self._mode_auto_approves_step = mode_auto_approves_step
        self._edit_step = edit_step
        self._sync_plan_copy = sync_plan_copy
        self._execute_phase = execute_phase
        self._input = input_func
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def approve_step(self, step_index: int) -> dict[str, Any] | None:
        """Render a step prompt, collect a decision, and mutate the step if edited."""

        current = self._plan["steps"][step_index]
        if not self._step_requires_approval(current):
            print(
                f"auto-approving step {current['id']} because risk {current['risk']['level']} "
                f"is below approval threshold {self._approval_threshold}",
                file=self._stdout,
            )
            self._log_event(
                "step_auto_approved",
                step_id=current["id"],
                step_title=current["title"],
                approval_origin="threshold",
                approval_threshold=self._approval_threshold,
            )
            return current
        active_mode = self._initial_run_approval_mode
        if self._mode_auto_approves_step(active_mode, current):
            print(f"auto-approving step {current['id']} via {active_mode}", file=self._stdout)
            self._log_event(
                "step_auto_approved",
                step_id=current["id"],
                step_title=current["title"],
                approval_origin="mode",
                approval_mode=active_mode,
            )
            return current
        while True:
            self._render_step(current)
            decision = self._input("decision [yes/no/edit]: ").strip().lower()
            if decision in {"yes", "y"}:
                self._log_event("step_approved", step_id=current["id"], step_title=current["title"])
                return current
            if decision in {"no", "n"}:
                self._log_event("step_rejected", step_id=current["id"], step_title=current["title"])
                return None
            if decision in {"edit", "e"}:
                try:
                    edited = self._edit_step(current)
                    self._plan["steps"][step_index] = edited
                    current = edited
                    self._sync_plan_copy()
                    self._log_event("step_edited", step_id=current["id"], step_title=current["title"])
                except RunnerError as exc:
                    self._log_event(
                        "step_edit_failed",
                        step_id=current["id"],
                        step_title=current["title"],
                        error=str(exc),
                    )
                    print(f"edit error: {exc}. please try again.", file=self._stderr)
                continue
            print("please enter yes, no, or edit", file=self._stdout)

    def prompt_rollback(self, step: dict[str, Any], error: CommandFailure) -> None:
        """Prompt for rollback execution after a failed step."""

        if not step["rollback"]:
            self._log_event("rollback_skipped", step_id=step["id"], reason="empty_rollback")
            return
        while True:
            answer = self._input(
                f"step {step['id']} failed in {error.phase}/{error.command_id}. run rollback? [y/N]: "
            ).strip().lower()
            if answer in {"y", "yes"}:
                self._log_event("rollback_approved", step_id=step["id"], reason=str(error))
                try:
                    self._execute_phase(step, "rollback")
                    self._log_event("rollback_finished", step_id=step["id"], status="success")
                except RunnerError as rollback_exc:
                    rollback_data: dict[str, Any] = {
                        "step_id": step["id"],
                        "status": "failed",
                        "error": str(rollback_exc),
                    }
                    if isinstance(rollback_exc, CommandFailure):
                        rollback_data.update(
                            {
                                "phase": rollback_exc.phase,
                                "command_id": rollback_exc.command_id,
                                "returncode": rollback_exc.returncode,
                            }
                        )
                    self._log_event("rollback_failed", **rollback_data)
                    print(f"rollback also failed: {rollback_exc}", file=self._stderr)
                return
            if answer in {"", "n", "no"}:
                self._log_event("rollback_declined", step_id=step["id"], reason=str(error))
                return
            print("please enter y or n", file=self._stdout)


__all__ = ["TTYApprovalBackend", "choose_editor", "edit_step"]
