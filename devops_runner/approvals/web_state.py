"""Mutable state container shared by the Web approval backend and its API."""

from __future__ import annotations

import pathlib
import threading
from collections import deque
from typing import Any

from devops_runner.audit import utc_now
from devops_runner.constants import DEFAULT_APPROVAL_THRESHOLD, DEFAULT_TASK_ID, VALID_AUTO_APPROVAL_MODES
from devops_runner.render import format_event_line


class WebApprovalState:
    """Thread-safe state store for the Web approval API."""

    def __init__(self) -> None:
        """Initialize empty state for a new backend instance."""

        self.condition = threading.Condition()
        self.plan_summary_text = ""
        self.server_url = ""
        self.task_id = DEFAULT_TASK_ID
        self.run_id = ""
        self.run_dir = ""
        self.audit_log_path = ""
        self.plan_id = ""
        self.plan_title = ""
        self.prompt: dict[str, Any] | None = None
        self.pending_submission: dict[str, Any] | None = None
        self.recent_events: deque[str] = deque(maxlen=80)
        self.current_step_id: str | None = None
        self.current_phase: str | None = None
        self.current_command_id: str | None = None
        self.final_status: str | None = None
        self.final_error: str | None = None
        self.last_event = ""
        self.global_default_mode = "manual"
        self.run_approval_mode = "manual"
        self.approval_threshold = DEFAULT_APPROVAL_THRESHOLD
        self.shutdown = False

    def configure(
        self,
        *,
        server_url: str,
        task_id: str,
        run_id: str,
        run_dir: pathlib.Path,
        audit_log_path: pathlib.Path,
        plan_id: str,
        plan_title: str,
        plan_summary_text: str,
        global_default_mode: str,
        run_approval_mode: str,
        approval_threshold: str,
    ) -> None:
        """Store immutable per-run metadata once the server is ready."""

        with self.condition:
            self.server_url = server_url
            self.task_id = task_id
            self.run_id = run_id
            self.run_dir = str(run_dir)
            self.audit_log_path = str(audit_log_path)
            self.plan_id = plan_id
            self.plan_title = plan_title
            self.plan_summary_text = plan_summary_text
            self.global_default_mode = global_default_mode
            self.run_approval_mode = run_approval_mode
            self.approval_threshold = approval_threshold
            self.condition.notify_all()

    def set_prompt(self, prompt: dict[str, Any]) -> None:
        """Publish a new approval prompt for the browser."""

        with self.condition:
            self.prompt = prompt
            self.pending_submission = None
            self.current_step_id = prompt.get("step_id")
            self.current_phase = prompt.get("kind")
            self.current_command_id = None
            self.condition.notify_all()

    def clear_prompt(self) -> None:
        """Clear the active prompt after a decision has been processed."""

        with self.condition:
            self.prompt = None
            self.pending_submission = None
            if self.current_phase in {"step_approval", "rollback_prompt"}:
                self.current_phase = None
            self.condition.notify_all()

    def wait_for_submission(self, prompt_id: str) -> dict[str, Any] | None:
        """Block until a matching browser decision is submitted or the backend stops."""

        with self.condition:
            while True:
                if self.shutdown:
                    return None
                if (
                    self.pending_submission is not None
                    and self.pending_submission.get("prompt_id") == prompt_id
                ):
                    submission = dict(self.pending_submission)
                    self.pending_submission = None
                    return submission
                self.condition.wait()

    def get_run_approval_mode(self) -> str:
        """Return the current approval mode for this run."""

        with self.condition:
            return self.run_approval_mode

    def set_run_approval_mode(
        self,
        mode: str,
        *,
        auto_submit_current_prompt: bool = False,
    ) -> dict[str, Any]:
        """Update the current run approval mode and optionally auto-submit the prompt."""

        if mode not in VALID_AUTO_APPROVAL_MODES:
            return {"ok": False, "message": f"unsupported approval mode: {mode}"}
        with self.condition:
            self.run_approval_mode = mode
            auto_submitted = False
            if (
                auto_submit_current_prompt
                and self.prompt is not None
                and self.prompt.get("kind") == "step_approval"
                and self.prompt.get("auto_approvable") is True
            ):
                self.pending_submission = {
                    "prompt_id": self.prompt["id"],
                    "decision": "yes",
                    "edited_step_json": None,
                }
                auto_submitted = True
            self.condition.notify_all()
            return {
                "ok": True,
                "message": "run approval mode updated",
                "run_approval_mode": self.run_approval_mode,
                "global_default_mode": self.global_default_mode,
                "auto_submitted": auto_submitted,
            }

    def set_global_default_mode(
        self,
        mode: str,
        *,
        apply_to_run: bool = False,
        auto_submit_current_prompt: bool = False,
    ) -> dict[str, Any]:
        """Update the global default mode and optionally align this run with it."""

        if mode not in VALID_AUTO_APPROVAL_MODES:
            return {"ok": False, "message": f"unsupported approval mode: {mode}"}
        with self.condition:
            self.global_default_mode = mode
            if apply_to_run:
                self.run_approval_mode = mode
            auto_submitted = False
            if (
                auto_submit_current_prompt
                and self.prompt is not None
                and self.prompt.get("kind") == "step_approval"
                and self.prompt.get("auto_approvable") is True
                and self.run_approval_mode == "auto_low_risk"
            ):
                self.pending_submission = {
                    "prompt_id": self.prompt["id"],
                    "decision": "yes",
                    "edited_step_json": None,
                }
                auto_submitted = True
            self.condition.notify_all()
            return {
                "ok": True,
                "message": "global approval mode updated",
                "run_approval_mode": self.run_approval_mode,
                "global_default_mode": self.global_default_mode,
                "auto_submitted": auto_submitted,
            }

    def submit_decision(
        self,
        *,
        prompt_id: str,
        decision: str,
        edited_step_json: str | None = None,
    ) -> dict[str, Any]:
        """Record a browser approval decision for the active prompt."""

        with self.condition:
            if self.prompt is None:
                return {"ok": False, "message": "no pending approval"}
            if self.prompt["id"] != prompt_id:
                return {"ok": False, "message": "stale prompt id"}
            self.pending_submission = {
                "prompt_id": prompt_id,
                "decision": decision,
                "edited_step_json": edited_step_json,
            }
            self.condition.notify_all()
            return {"ok": True, "message": "decision accepted"}

    def update_prompt_error(self, message: str) -> None:
        """Attach a validation error message to the active prompt."""

        with self.condition:
            if self.prompt is not None:
                self.prompt["error"] = message
            self.condition.notify_all()

    def record_event(self, payload: dict[str, Any]) -> None:
        """Project audit events into browser-visible state."""

        line = format_event_line(payload)
        with self.condition:
            self.recent_events.append(line)
            self.last_event = line
            event_type = payload.get("event")
            if payload.get("step_id"):
                self.current_step_id = payload["step_id"]
            if event_type == "phase_started":
                self.current_phase = payload.get("phase")
                self.current_command_id = None
            elif event_type == "command_started":
                self.current_phase = payload.get("phase")
                self.current_command_id = payload.get("command_id")
            elif event_type == "command_finished":
                self.current_command_id = payload.get("command_id")
            elif event_type in {"phase_finished", "step_finished", "step_failed"}:
                self.current_command_id = None
                if event_type in {"step_finished", "step_failed"}:
                    self.current_phase = None
            elif event_type == "plan_finished":
                self.final_status = payload.get("status")
                self.final_error = payload.get("error") or payload.get("sync_error")
            self.condition.notify_all()

    def mark_shutdown(self) -> None:
        """Wake waiting request handlers during backend shutdown."""

        with self.condition:
            self.shutdown = True
            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        """Return the browser-visible approval state."""

        with self.condition:
            prompt = dict(self.prompt) if self.prompt is not None else None
            return {
                "server_url": self.server_url,
                "task_id": self.task_id,
                "run_id": self.run_id,
                "run_dir": self.run_dir,
                "audit_log_path": self.audit_log_path,
                "plan_id": self.plan_id,
                "plan_title": self.plan_title,
                "plan_summary_text": self.plan_summary_text,
                "prompt": prompt,
                "recent_events": list(self.recent_events),
                "current_step_id": self.current_step_id,
                "current_phase": self.current_phase,
                "current_command_id": self.current_command_id,
                "final_status": self.final_status,
                "final_error": self.final_error,
                "last_event": self.last_event,
                "global_default_mode": self.global_default_mode,
                "run_approval_mode": self.run_approval_mode,
                "approval_threshold": self.approval_threshold,
                "server_time": utc_now(),
            }


__all__ = ["WebApprovalState"]
