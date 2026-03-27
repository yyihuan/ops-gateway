"""Command-line entrypoint for the ops-gate package."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import sys
from collections.abc import Sequence

from devops_runner.constants import DEFAULT_APPROVAL_THRESHOLD, DEFAULT_TASK_ID, RISK_LEVEL_ORDER
from devops_runner.context import RunContext, RunPaths
from devops_runner.errors import RunnerError
from devops_runner.orchestrator import PlanOrchestrator
from devops_runner.paths import infer_task_id_from_run_dir, resolve_resume_run_path, slugify
from devops_runner.plan import (
    extract_task_id,
    load_json,
    select_steps,
    validate_plan,
    validate_task_id,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the stable runner CLI arguments."""

    parser = argparse.ArgumentParser(description="Auditable step runner with approval gates")
    parser.add_argument("plan", help="path to the JSON execution plan")
    parser.add_argument(
        "--schema",
        default="schema/step_schema.json",
        help="path to step_schema.json (default: schema/step_schema.json)",
    )
    parser.add_argument(
        "--run-root",
        default="runs",
        help="directory used to store run outputs (default: runs)",
    )
    parser.add_argument(
        "--backup-root",
        help="directory used to store backup artifacts (default: <run-root>/../backups)",
    )
    parser.add_argument(
        "--task-id",
        help=(
            "logical task identifier; new runs are stored under <run-root>/<task-id>/ "
            "and this overrides metadata.task_id when set"
        ),
    )
    parser.add_argument(
        "--step-id",
        action="append",
        default=[],
        help="run only the specified step id; repeat to select multiple steps in original order",
    )
    parser.add_argument(
        "--resume-run",
        help="reuse an existing run directory so multiple selected-step invocations share one run",
    )
    parser.add_argument(
        "--approval-backend",
        choices=["tty", "web"],
        default="tty",
        help="approval backend to use: tty or web (default: tty)",
    )
    parser.add_argument(
        "--approval-threshold",
        choices=list(RISK_LEVEL_ORDER.keys()),
        default=DEFAULT_APPROVAL_THRESHOLD,
        help="minimum risk level that requires explicit approval; lower-risk steps auto-run (default: low)",
    )
    parser.add_argument(
        "--web-host",
        default="127.0.0.1",
        help="bind host for the web approval backend (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=0,
        help="bind port for the web approval backend; 0 chooses a free port (default: 0)",
    )
    parser.add_argument(
        "--approval-mode-state-file",
        default="state/approval_mode.json",
        help="path to the persisted global approval mode state file (default: state/approval_mode.json)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _resolve_effective_task_id(
    *,
    plan: dict[str, object],
    cli_task_id: str | None,
    base_run_root: pathlib.Path,
    resume_run: pathlib.Path | None,
) -> tuple[str, pathlib.Path | None]:
    """Resolve the final task id, accounting for plan metadata and resume paths."""

    plan_task_id = extract_task_id(plan)
    effective_task_id = cli_task_id or plan_task_id
    if resume_run is None:
        return effective_task_id, None
    resolved_resume_run = resolve_resume_run_path(str(resume_run), base_run_root, effective_task_id)
    inferred_task_id = infer_task_id_from_run_dir(base_run_root, resolved_resume_run)
    if inferred_task_id is not None and cli_task_id is not None and inferred_task_id != cli_task_id:
        raise RunnerError(
            f"resume run directory {resolved_resume_run} belongs to task_id={inferred_task_id}, not {cli_task_id}"
        )
    if inferred_task_id is not None:
        effective_task_id = inferred_task_id
    return effective_task_id, resolved_resume_run


def build_run_context(args: argparse.Namespace) -> RunContext:
    """Build a validated run context from parsed CLI arguments."""

    plan_path = pathlib.Path(args.plan).resolve()
    schema_path = pathlib.Path(args.schema).resolve()
    approval_mode_state_file = pathlib.Path(args.approval_mode_state_file)
    base_run_root = pathlib.Path(args.run_root).resolve()
    backup_root = pathlib.Path(args.backup_root).resolve() if args.backup_root else (base_run_root.parent / "backups")
    plan = load_json(plan_path)
    validate_plan(plan)
    cli_task_id = validate_task_id(args.task_id, "task_id") if args.task_id else None
    resume_arg = pathlib.Path(args.resume_run) if args.resume_run else None
    effective_task_id, resolved_resume_run = _resolve_effective_task_id(
        plan=plan,
        cli_task_id=cli_task_id,
        base_run_root=base_run_root,
        resume_run=resume_arg,
    )
    selected_step_mode = bool(args.step_id)
    selected_plan = select_steps(plan, args.step_id)
    if resolved_resume_run is not None:
        run_root = resolved_resume_run.parent
        run_id = resolved_resume_run.name
        run_dir = resolved_resume_run
    else:
        run_root = base_run_root / effective_task_id
        run_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{run_stamp}-{slugify(selected_plan['plan_id'])}"
        run_dir = run_root / run_id
    paths = RunPaths(
        backup_root=backup_root,
        run_root=run_root,
        run_dir=run_dir,
        logs_dir=run_dir / "logs",
        steps_dir=run_dir / "steps",
        backups_dir=backup_root / effective_task_id / run_id,
        audit_log_path=run_dir / "logs" / "runner.jsonl",
        resolved_plan_path=run_dir / "resolved_plan.json",
        plan_copy_path=run_dir / "input_plan.json",
        schema_copy_path=run_dir / "step_schema.json",
    )
    return RunContext(
        plan=selected_plan,
        plan_path=plan_path,
        schema_path=schema_path,
        base_run_root=base_run_root,
        task_id=effective_task_id,
        run_id=run_id,
        resume_run=resolved_resume_run,
        selected_step_mode=selected_step_mode,
        remote_sync_enabled=not selected_step_mode,
        approval_backend_name=args.approval_backend,
        approval_threshold=args.approval_threshold,
        approval_mode_state_file=approval_mode_state_file,
        web_host=args.web_host,
        web_port=args.web_port,
        paths=paths,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the runner CLI with the supplied arguments."""

    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print(
            "warning: not running as root. steps requiring elevated privileges will fail.",
            file=sys.stderr,
        )
    args = parse_args(argv)
    context = build_run_context(args)
    orchestrator = PlanOrchestrator(context)
    return orchestrator.run()


__all__ = ["build_run_context", "main", "parse_args"]
