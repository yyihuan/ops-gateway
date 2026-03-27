"""Main orchestration flow for auditable plan execution."""

from __future__ import annotations

import pathlib
import shutil
import sys
from typing import Any

from devops_runner.approvals.base import ApprovalBackend
from devops_runner.approvals.mode_store import ApprovalModeStore
from devops_runner.approvals.policy import (
    mode_auto_approves_step as mode_auto_approves_step_policy,
    step_requires_approval as step_requires_approval_policy,
)
from devops_runner.approvals.tty import TTYApprovalBackend, edit_step as edit_step_payload
from devops_runner.approvals.web import WebApprovalBackend
from devops_runner.audit import AuditLogger, utc_now
from devops_runner.backups import (
    collect_backup_targets as collect_backup_targets_payload,
    resolve_backup_dir as resolve_backup_dir_payload,
    snapshot_paths as snapshot_paths_payload,
)
from devops_runner.constants import DEFAULT_APPROVAL_THRESHOLD, DEFAULT_TIMEOUT, STREAM_JOIN_TIMEOUT_SECONDS
from devops_runner.context import RunContext
from devops_runner.execution import (
    build_command_env as build_command_env_payload,
    execute_command as execute_command_payload,
    execute_phase as execute_phase_payload,
)
from devops_runner.errors import CommandFailure, RunnerError
from devops_runner.paths import infer_task_id_from_run_dir, slugify
from devops_runner.plan import extract_plan_payload, extract_task_id, load_json, validate_risk_level, validate_step, write_json
from devops_runner.render import (
    render_plan_summary as render_plan_summary_text,
    render_rollback_prompt as render_rollback_prompt_text,
    render_step as render_step_text,
)
from devops_runner.sync import sync_remote_run


class PlanOrchestrator:
    """Drive plan approval, execution, audit logging, and artifact sync."""

    def __init__(self, context: RunContext) -> None:
        """Initialize the orchestrator from a validated run context."""

        self.context = context
        self.plan = context.plan
        self.plan_path = context.plan_path
        self.schema_path = context.schema_path
        self.base_run_root = context.base_run_root
        self.project_root = self.base_run_root.parent
        self.task_id = context.task_id
        self.run_id = context.run_id
        self.resume_run = context.resume_run
        self.selected_step_mode = context.selected_step_mode
        self.remote_sync_enabled = context.remote_sync_enabled
        self.approval_backend_name = context.approval_backend_name
        self.approval_threshold = validate_risk_level(context.approval_threshold, "approval_threshold")
        self.approval_mode_state_file = context.approval_mode_state_file.resolve()
        self.web_host = context.web_host
        self.web_port = context.web_port
        self.run_root = context.paths.run_root
        self.run_dir = context.paths.run_dir
        self.logs_dir = context.paths.logs_dir
        self.steps_dir = context.paths.steps_dir
        self.backup_root = context.paths.backup_root
        self.backups_dir = context.paths.backups_dir
        self.audit_log_path = context.paths.audit_log_path
        self.resolved_plan_path = context.paths.resolved_plan_path
        self.plan_copy_path = context.paths.plan_copy_path
        self.schema_copy_path = context.paths.schema_copy_path
        self.resumed_run = self.resume_run is not None
        self.approval_mode_store = ApprovalModeStore(self.approval_mode_state_file)
        self.global_default_approval_mode = self.approval_mode_store.read_mode()
        self.initial_run_approval_mode = self.global_default_approval_mode
        self.audit_logger = AuditLogger(
            self.audit_log_path,
            base_fields={
                "task_id": self.task_id,
                "run_id": self.run_id,
                "plan_id": self.plan["plan_id"],
            },
        )
        if self.resumed_run:
            self._validate_resume_dir()
        self._prepare_dirs()
        self._materialize_inputs()
        self.approval_backend = self._build_approval_backend()
        self.audit_logger.add_listener(self.approval_backend.on_event)

    def _validate_resume_dir(self) -> None:
        """Verify that a resumed run directory matches the selected plan and task."""

        if not self.run_dir.exists():
            raise RunnerError(f"resume run directory does not exist: {self.run_dir}")
        if not self.run_dir.is_dir():
            raise RunnerError(f"resume run path is not a directory: {self.run_dir}")
        for candidate in [self.plan_copy_path, self.resolved_plan_path]:
            if not candidate.exists():
                continue
            existing_payload = load_json(candidate)
            existing_plan = extract_plan_payload(existing_payload)
            existing_plan_id = existing_plan.get("plan_id")
            existing_task_id = existing_payload.get("task_id")
            if existing_task_id is None:
                try:
                    existing_task_id = extract_task_id(existing_plan)
                except RunnerError:
                    existing_task_id = None
            if existing_task_id and existing_task_id != self.task_id:
                raise RunnerError(
                    f"resume run directory {self.run_dir} belongs to task_id={existing_task_id}, "
                    f"not {self.task_id}"
                )
            if existing_plan_id and existing_plan_id != self.plan["plan_id"]:
                raise RunnerError(
                    f"resume run directory {self.run_dir} belongs to plan_id={existing_plan_id}, "
                    f"not {self.plan['plan_id']}"
                )
            existing_target = existing_plan.get("target")
            if isinstance(existing_target, dict):
                if existing_target.get("host") and existing_target["host"] != self.plan["target"]["host"]:
                    raise RunnerError(
                        f"resume run directory {self.run_dir} belongs to target.host="
                        f"{existing_target['host']}, not {self.plan['target']['host']}"
                    )
                if existing_target.get("os") and existing_target["os"] != self.plan["target"]["os"]:
                    raise RunnerError(
                        f"resume run directory {self.run_dir} belongs to target.os="
                        f"{existing_target['os']}, not {self.plan['target']['os']}"
                    )

    def _prepare_dirs(self) -> None:
        """Create the stable directory tree for this run."""

        for directory in [
            self.base_run_root,
            self.run_root,
            self.run_dir,
            self.logs_dir,
            self.steps_dir,
            self.backups_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def _materialize_inputs(self) -> None:
        """Copy plan inputs and write the resolved execution manifest."""

        shutil.copy2(self.plan_path, self.plan_copy_path)
        if self.schema_path.exists():
            shutil.copy2(self.schema_path, self.schema_copy_path)
        timestamp = utc_now()
        write_json(
            self.resolved_plan_path,
            {
                "task_id": self.task_id,
                "run_id": self.run_id,
                "run_root": str(self.base_run_root),
                "approval_threshold": self.approval_threshold,
                "generated_at": timestamp,
                "updated_at": timestamp,
                "plan": self.plan,
            },
        )

    def _build_approval_backend(self) -> ApprovalBackend:
        """Instantiate the configured approval backend with explicit dependencies."""

        if self.approval_backend_name == "tty":
            return TTYApprovalBackend(
                plan=self.plan,
                render_step=self.render_step,
                log_event=self.log_event,
                approval_threshold=self.approval_threshold,
                initial_run_approval_mode=self.initial_run_approval_mode,
                step_requires_approval=self.step_requires_approval,
                mode_auto_approves_step=self.mode_auto_approves_step,
                edit_step=lambda step: edit_step_payload(
                    step,
                    load_json=load_json,
                    validate_step=validate_step,
                    env=None,
                ),
                sync_plan_copy=self.sync_plan_copy,
                execute_phase=self.execute_phase,
            )
        if self.approval_backend_name == "web":
            return WebApprovalBackend(
                plan=self.plan,
                task_id=self.task_id,
                run_id=self.run_id,
                run_dir=self.run_dir,
                audit_log_path=self.audit_log_path,
                plan_id=self.plan["plan_id"],
                plan_title=self.plan["plan_title"],
                plan_summary_text=render_plan_summary_text(
                    self.plan,
                    task_id=self.task_id,
                    approval_threshold=self.approval_threshold,
                    selected_step_mode=self.selected_step_mode,
                    resumed_run=self.resumed_run,
                    remote_sync_enabled=self.remote_sync_enabled,
                ),
                approval_threshold=self.approval_threshold,
                global_default_mode=self.global_default_approval_mode,
                initial_run_approval_mode=self.initial_run_approval_mode,
                approval_mode_state_file=self.approval_mode_state_file,
                approval_mode_store=self.approval_mode_store,
                host=self.web_host,
                port=self.web_port,
                log_event=self.log_event,
                step_requires_approval=self.step_requires_approval,
                mode_auto_approves_step=self.mode_auto_approves_step,
                validate_step=validate_step,
                sync_plan_copy=self.sync_plan_copy,
                execute_phase=self.execute_phase,
                render_step_text=render_step_text,
                render_rollback_prompt=lambda step, error: render_rollback_prompt_text(step, error=error),
            )
        raise RunnerError(f"unsupported approval backend: {self.approval_backend_name}")

    def log_event(self, event_type: str, **data: Any) -> None:
        """Write a structured audit event for the current run."""

        self.audit_logger.log(event_type, **data)

    def sync_plan_copy(self) -> None:
        """Refresh the resolved plan snapshot after an in-run step edit."""

        write_json(
            self.resolved_plan_path,
            {
                "task_id": self.task_id,
                "run_id": self.run_id,
                "run_root": str(self.base_run_root),
                "approval_threshold": self.approval_threshold,
                "updated_at": utc_now(),
                "plan": self.plan,
            },
        )

    def step_requires_approval(self, step: dict[str, Any]) -> bool:
        """Return whether a step crosses the approval threshold."""

        return step_requires_approval_policy(step, approval_threshold=self.approval_threshold)

    def mode_auto_approves_step(self, mode: str, step: dict[str, Any]) -> bool:
        """Return whether the active mode auto-approves the step."""

        return mode_auto_approves_step_policy(mode, step)

    def render_step(self, step: dict[str, Any]) -> None:
        """Render the full TTY approval summary for a step."""

        print(render_step_text(step))

    def render_plan_summary(self) -> None:
        """Render the plan summary before execution begins."""

        print(
            render_plan_summary_text(
                self.plan,
                task_id=self.task_id,
                approval_threshold=self.approval_threshold,
                selected_step_mode=self.selected_step_mode,
                resumed_run=self.resumed_run,
                remote_sync_enabled=self.remote_sync_enabled,
            ),
        )

    def approve_step(self, step_index: int) -> dict[str, Any] | None:
        """Delegate approval for a step to the active backend."""

        return self.approval_backend.approve_step(step_index)

    def backup_dir_for_step(self, step: dict[str, Any]) -> pathlib.Path:
        """Resolve the backup output directory for one step."""

        return resolve_backup_dir_payload(
            step,
            backup_root=self.backup_root,
            task_id=self.task_id,
            run_id=self.run_id,
        )

    def collect_backup_targets(self, step: dict[str, Any]) -> list[pathlib.Path]:
        """Resolve the filesystem targets that should be protected for a step."""

        return collect_backup_targets_payload(step, project_root=self.project_root)

    def should_backup_step(self, step: dict[str, Any]) -> bool:
        """Return whether this step should emit pre/post backup artifacts."""

        if step["risk"]["level"] in {"high", "critical"}:
            return True
        backup_config = step.get("backup") or {}
        return bool(backup_config.get("paths") or backup_config.get("rules"))

    def snapshot_step_targets(self, step: dict[str, Any], label: str) -> pathlib.Path:
        """Create an auditable snapshot for the resolved targets of one step."""

        return snapshot_paths_payload(
            step_id=step["id"],
            label=label,
            targets=self.collect_backup_targets(step),
            backup_dir=self.backup_dir_for_step(step),
            log_event=self.log_event,
        )

    def build_command_env(self, step: dict[str, Any], command: dict[str, Any]) -> dict[str, str]:
        """Build the execution environment for a single command."""

        return build_command_env_payload(
            command,
            task_id=self.task_id,
            project_root=self.project_root,
            base_run_root=self.base_run_root,
            task_run_root=self.run_root,
            run_id=self.run_id,
            run_dir=self.run_dir,
            backup_root=self.backup_root,
            backups_dir=self.backups_dir,
            step_backup_dir=self.backup_dir_for_step(step),
            logs_dir=self.logs_dir,
            steps_dir=self.steps_dir,
            plan_id=self.plan["plan_id"],
            plan_title=self.plan["plan_title"],
            target_host=self.plan["target"]["host"],
            target_os=self.plan["target"]["os"],
        )

    def execute_command(self, step_id: str, phase: str, command: dict[str, Any], command_index: int) -> None:
        """Run a single command inside a step phase."""

        step = next(candidate for candidate in self.plan["steps"] if candidate["id"] == step_id)
        execute_command_payload(
            step_id=step_id,
            phase=phase,
            command=command,
            command_index=command_index,
            steps_dir=self.steps_dir,
            env=self.build_command_env(step, command),
            default_timeout=DEFAULT_TIMEOUT,
            stream_join_timeout=STREAM_JOIN_TIMEOUT_SECONDS,
            slugify_func=slugify,
            log_event=self.log_event,
        )

    def execute_phase(self, step: dict[str, Any], phase: str) -> None:
        """Run one named phase for a step."""

        execute_phase_payload(
            step=step,
            phase=phase,
            command_runner=self.execute_command,
            log_event=self.log_event,
        )

    def prompt_rollback(self, step: dict[str, Any], error: CommandFailure) -> None:
        """Delegate rollback approval to the active backend."""

        self.approval_backend.prompt_rollback(step, error)

    def attempt_remote_sync(self, phase: str, step_id: str | None = None) -> RunnerError | None:
        """Run best-effort remote sync and return the follow-up error when it fails."""

        try:
            self.sync_remote(phase, step_id=step_id)
            return None
        except RunnerError as exc:
            self.log_event("rsync_followup_failed", sync_phase=phase, step_id=step_id, error=str(exc))
            return exc

    def sync_remote(self, phase: str, step_id: str | None = None) -> None:
        """Sync run artifacts to the configured remote target for the given phase."""

        sync_remote_run(
            plan=self.plan,
            phase=phase,
            step_id=step_id,
            base_run_root=self.base_run_root,
            run_dir=self.run_dir,
            remote_sync_enabled=self.remote_sync_enabled,
            log_event=self.log_event,
        )

    def execute_step(self, step: dict[str, Any]) -> None:
        """Run one approved step including snapshots and rollback prompt wiring."""

        self.log_event("step_started", step_id=step["id"], step_title=step["title"])
        needs_backup = self.should_backup_step(step)
        pre_snapshot_done = False
        try:
            if needs_backup:
                self.snapshot_step_targets(step, "pre")
                pre_snapshot_done = True
            self.execute_phase(step, "pre_checks")
            self.execute_phase(step, "commands")
            self.execute_phase(step, "post_checks")
            self.log_event("step_finished", step_id=step["id"], status="success")
        except CommandFailure as exc:
            self.log_event(
                "step_failed",
                step_id=step["id"],
                status="failed",
                phase=exc.phase,
                command_id=exc.command_id,
                returncode=exc.returncode,
            )
            self.prompt_rollback(step, exc)
            raise
        finally:
            if needs_backup and pre_snapshot_done:
                try:
                    self.snapshot_step_targets(step, "post")
                except RunnerError as exc:
                    self.log_event("backup_post_failed", step_id=step["id"], error=str(exc))

    def run(self) -> int:
        """Execute the configured plan end to end."""

        self.approval_backend.start()
        self.log_event(
            "plan_started",
            plan_title=self.plan["plan_title"],
            target=self.plan["target"],
            invocation_mode="selected_steps" if self.selected_step_mode else "full_plan",
            resumed_run=self.resumed_run,
            selected_step_ids=[step["id"] for step in self.plan["steps"]],
            remote_sync_active=self.remote_sync_enabled,
            approval_backend=self.approval_backend_name,
            approval_threshold=self.approval_threshold,
            global_default_approval_mode=self.global_default_approval_mode,
            run_approval_mode=self.initial_run_approval_mode,
            approval_mode_state_file=str(self.approval_mode_state_file),
        )
        print(f"task id: {self.task_id}")
        print(f"base run root: {self.base_run_root}")
        print(f"task run root: {self.run_root}")
        print(f"run directory: {self.run_dir}")
        print(f"audit log: {self.audit_log_path}")
        print(f"approval backend: {self.approval_backend_name}")
        print(f"approval threshold: {self.approval_threshold}")
        print(f"approval mode state file: {self.approval_mode_state_file}")
        print(f"global default approval mode: {self.global_default_approval_mode}")
        print(f"initial run approval mode: {self.initial_run_approval_mode}")
        print(
            "operator policy: decisions inside runner (yes/no/edit and rollback prompts) "
            "must be entered manually by the human operator."
        )
        print(
            "operator policy: Codex may prepare the plan and may start runner only after "
            "explicit permission, but must not answer runner prompts on the operator's behalf."
        )
        if self.plan.get("remote_sync", {}).get("enabled") and not self.remote_sync_enabled:
            self.log_event("remote_sync_suppressed", reason="selected_step_mode")
        self.render_plan_summary()
        try:
            for step_index, _ in enumerate(self.plan["steps"]):
                approved_step = self.approve_step(step_index)
                if approved_step is None:
                    self.log_event("plan_aborted", reason="step_rejected", step_index=step_index)
                    sync_error = self.attempt_remote_sync("plan_end")
                    log_data: dict[str, Any] = {
                        "status": "aborted",
                        "reason": "step_rejected",
                        "step_index": step_index,
                    }
                    if sync_error is not None:
                        log_data["sync_error"] = str(sync_error)
                    self.log_event("plan_finished", **log_data)
                    print("plan aborted by operator")
                    return 2
                self.execute_step(approved_step)
                self.sync_remote("step_end", step_id=approved_step["id"])
            self.sync_remote("plan_end")
            self.log_event("plan_finished", status="success")
            print(f"plan completed successfully: {self.run_dir}")
            return 0
        except RunnerError as exc:
            sync_error = self.attempt_remote_sync("plan_end")
            log_data = {"status": "failed", "error": str(exc)}
            if sync_error is not None:
                log_data["sync_error"] = str(sync_error)
            self.log_event("plan_finished", **log_data)
            print(f"plan failed: {exc}", file=sys.stderr)
            if sync_error is not None:
                print(f"plan-end sync also failed: {sync_error}", file=sys.stderr)
            return 1
        finally:
            self.approval_backend.stop()


__all__ = ["PlanOrchestrator"]
