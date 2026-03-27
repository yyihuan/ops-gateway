"""Pure rendering helpers for runner summaries and approval views.

This module returns strings. It must not print directly, start web servers, or
execute commands.
"""

from __future__ import annotations

from typing import Any


def command_review_note(command: dict[str, Any]) -> str:
    """Return the most useful human-facing note for a command."""

    return command.get("review_note") or command["name"]


def unique_preserve_order(items: list[str]) -> list[str]:
    """Deduplicate a string list while preserving the first occurrence order."""

    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def command_effects(command: dict[str, Any]) -> dict[str, Any] | None:
    """Return the declared effects object when present."""

    effects = command.get("effects")
    if isinstance(effects, dict):
        return effects
    return None


def command_is_read_only(command: dict[str, Any]) -> bool | None:
    """Infer whether a command is read-only from its declared effects."""

    effects = command_effects(command)
    if effects is None:
        return None
    if "read_only" in effects:
        return effects["read_only"]
    if effects.get("writes_paths") or effects.get("service_actions"):
        return False
    return True


def format_items(items: list[str], *, limit: int = 4) -> str:
    """Format short human-readable lists used in approval summaries."""

    if not items:
        return "none"
    if len(items) <= limit:
        return ", ".join(items)
    shown = ", ".join(items[:limit])
    return f"{shown} (+{len(items) - limit} more)"


def summarize_write_scope(writes_paths: list[str], service_actions: list[str]) -> str:
    """Summarize how broadly a step writes to the system."""

    if not writes_paths and not service_actions:
        return "none"
    if service_actions:
        return "system state change"
    if all("RUNNER_" in path or path.startswith("runs/") for path in writes_paths):
        return "run artifacts only"
    return "filesystem writes"


def build_step_effect_summary(step: dict[str, Any]) -> dict[str, Any]:
    """Aggregate the declared effects of a step for approval rendering."""

    main_commands = step["pre_checks"] + step["commands"] + step["post_checks"]
    rollback_commands = step["rollback"]
    main_effectful = [command for command in main_commands if command_effects(command) is not None]
    rollback_effectful = [command for command in rollback_commands if command_effects(command) is not None]

    main_reads = unique_preserve_order(
        [
            path
            for command in main_commands
            for path in (command_effects(command) or {}).get("reads_paths", [])
        ]
    )
    main_writes = unique_preserve_order(
        [
            path
            for command in main_commands
            for path in (command_effects(command) or {}).get("writes_paths", [])
        ]
    )
    network_targets = unique_preserve_order(
        [
            target
            for command in main_commands
            for target in (command_effects(command) or {}).get("network_targets", [])
        ]
    )
    service_actions = unique_preserve_order(
        [
            action
            for command in main_commands
            for action in (command_effects(command) or {}).get("service_actions", [])
        ]
    )
    rollback_writes = unique_preserve_order(
        [
            path
            for command in rollback_commands
            for path in (command_effects(command) or {}).get("writes_paths", [])
        ]
    )
    rollback_service_actions = unique_preserve_order(
        [
            action
            for command in rollback_commands
            for action in (command_effects(command) or {}).get("service_actions", [])
        ]
    )
    if main_commands and len(main_effectful) == len(main_commands):
        read_only = "yes" if all(command_is_read_only(command) for command in main_commands) else "no"
        requires_root = (
            "yes"
            if any((command_effects(command) or {}).get("requires_root", False) for command in main_commands)
            else "no"
        )
        network_summary = format_items(network_targets)
    else:
        read_only = "unknown"
        requires_root = (
            "yes"
            if any((command_effects(command) or {}).get("requires_root", False) for command in main_commands)
            else "unknown"
        )
        network_summary = format_items(network_targets) if network_targets else "unknown"
    return {
        "main_total": len(main_commands),
        "main_effectful": len(main_effectful),
        "rollback_total": len(rollback_commands),
        "rollback_effectful": len(rollback_effectful),
        "read_only": read_only,
        "requires_root": requires_root,
        "write_scope": summarize_write_scope(main_writes, service_actions),
        "network_targets": network_summary,
        "reads_paths": main_reads,
        "writes_paths": main_writes,
        "service_actions": service_actions,
        "rollback_available": "yes" if bool(rollback_commands) else "no",
        "rollback_writes": rollback_writes,
        "rollback_service_actions": rollback_service_actions,
        "phase_counts": {
            "pre_checks": len(step["pre_checks"]),
            "commands": len(step["commands"]),
            "post_checks": len(step["post_checks"]),
            "rollback": len(step["rollback"]),
        },
    }


def render_step_effect_summary(step: dict[str, Any], *, indent: str = "") -> str:
    """Render the detailed effect summary block for a single step."""

    summary = build_step_effect_summary(step)
    lines = [
        f"{indent}approval quick summary:",
        (
            f"{indent}  command_counts: "
            f"pre_checks={summary['phase_counts']['pre_checks']} "
            f"commands={summary['phase_counts']['commands']} "
            f"post_checks={summary['phase_counts']['post_checks']} "
            f"rollback={summary['phase_counts']['rollback']}"
        ),
        (
            f"{indent}  effect_metadata: "
            f"main={summary['main_effectful']}/{summary['main_total']} declared "
            f"rollback={summary['rollback_effectful']}/{summary['rollback_total']} declared"
        ),
        f"{indent}  requires_root: {summary['requires_root']}",
        f"{indent}  read_only: {summary['read_only']}",
        f"{indent}  write_scope: {summary['write_scope']}",
        f"{indent}  network_targets: {summary['network_targets']}",
        f"{indent}  rollback_available: {summary['rollback_available']}",
    ]
    if summary["reads_paths"]:
        lines.append(f"{indent}  key_reads: {format_items(summary['reads_paths'])}")
    if summary["writes_paths"]:
        lines.append(f"{indent}  key_writes: {format_items(summary['writes_paths'])}")
    if summary["service_actions"]:
        lines.append(f"{indent}  service_actions: {format_items(summary['service_actions'])}")
    if summary["rollback_writes"]:
        lines.append(f"{indent}  rollback_writes: {format_items(summary['rollback_writes'])}")
    if summary["rollback_service_actions"]:
        lines.append(
            f"{indent}  rollback_service_actions: {format_items(summary['rollback_service_actions'])}"
        )
    return "\n".join(lines)


def render_step_approval_snapshot(step: dict[str, Any], *, indent: str = "") -> str:
    """Render the compact per-step approval snapshot used in plan summaries."""

    summary = build_step_effect_summary(step)
    lines = [
        (
            f"{indent}approval_snapshot: "
            f"main_effects={summary['main_effectful']}/{summary['main_total']} "
            f"read_only={summary['read_only']} "
            f"requires_root={summary['requires_root']} "
            f"write_scope={summary['write_scope']} "
            f"network={summary['network_targets']} "
            f"rollback={summary['rollback_available']}"
        )
    ]
    if summary["reads_paths"]:
        lines.append(f"{indent}touches.reads: {format_items(summary['reads_paths'])}")
    if summary["writes_paths"]:
        lines.append(f"{indent}touches.writes: {format_items(summary['writes_paths'])}")
    if summary["service_actions"]:
        lines.append(f"{indent}touches.services: {format_items(summary['service_actions'])}")
    return "\n".join(lines)


def render_command_list(
    title: str,
    commands: list[dict[str, Any]],
    *,
    indent: str = "",
    rollback: bool = False,
) -> str:
    """Render a compact command list for summary views."""

    header = f"{title} (only runs if the step fails and rollback is approved)" if rollback else title
    lines = [f"{indent}{header}:"]
    if not commands:
        lines.append(f"{indent}  - (empty)")
        return "\n".join(lines)
    for item in commands:
        lines.append(f"{indent}  - {item['id']}: {item['name']}")
        lines.append(f"{indent}    does: {command_review_note(item)}")
    return "\n".join(lines)


def render_command_script(command: dict[str, Any], indent: str = "      ") -> str:
    """Render a single command preview line."""

    preview = command["run"].replace("\n", r"\n")
    return f"{indent}{preview}"


def render_phase_preview(
    phase: str,
    commands: list[dict[str, Any]],
    *,
    rollback: bool = False,
    indent: str = "",
) -> str:
    """Render the verbose execution preview for one phase."""

    lines = [
        f"{indent}{phase} (only runs if the step fails and rollback is approved):"
        if rollback
        else f"{indent}{phase}:"
    ]
    if not commands:
        lines.append(f"{indent}  - (empty)")
        return "\n".join(lines)
    for index, item in enumerate(commands, start=1):
        lines.append(f"{indent}  [{index}] {item['id']} - {item['name']}")
        lines.append(f"{indent}      does: {command_review_note(item)}")
        if item.get("cwd"):
            lines.append(f"{indent}      cwd: {item['cwd']}")
        if item.get("env"):
            lines.append(f"{indent}      env:")
            for key, value in sorted(item["env"].items()):
                lines.append(f"{indent}        {key}={value}")
        if item.get("timeout_seconds"):
            lines.append(f"{indent}      timeout_seconds: {item['timeout_seconds']}")
        if item.get("allow_failure"):
            lines.append(f"{indent}      allow_failure: true")
        lines.append(f"{indent}      command:")
        lines.append(render_command_script(item, indent=f"{indent}      "))
    return "\n".join(lines)


def render_execution_preview(step: dict[str, Any]) -> str:
    """Render the verbose execution preview for a step."""

    return "\n".join(
        [
            "execution preview:",
            render_phase_preview("pre_checks", step["pre_checks"]),
            render_phase_preview("commands", step["commands"]),
            render_phase_preview("post_checks", step["post_checks"]),
            render_phase_preview("rollback", step["rollback"], rollback=True),
        ]
    )


def render_step(step: dict[str, Any]) -> str:
    """Render the full TTY approval view for a single step."""

    lines = [
        "=" * 80,
        f"Step: {step['id']} - {step['title']}",
        f"goal: {step['goal']}",
        f"reason: {step['reason']}",
        f"risk: {step['risk']['level']} | {step['risk']['summary']}",
    ]
    if step["risk"].get("approval_hint"):
        lines.append(f"approval_hint: {step['risk']['approval_hint']}")
    auto_approve_modes = step["risk"].get("auto_approve_modes", [])
    if auto_approve_modes:
        lines.append(f"auto_approve_modes: {', '.join(auto_approve_modes)}")
    if step.get("notes"):
        lines.append(f"notes: {step['notes']}")
    lines.append(render_step_effect_summary(step))
    lines.append(render_command_list("pre_checks", step["pre_checks"]))
    lines.append(render_command_list("commands", step["commands"]))
    lines.append(render_command_list("post_checks", step["post_checks"]))
    lines.append(render_command_list("rollback", step["rollback"], rollback=True))
    lines.append(render_execution_preview(step))
    lines.append("approval options: yes / no / edit")
    lines.append("=" * 80)
    return "\n".join(lines)


def render_rollback_prompt(step: dict[str, Any], *, error: Any) -> str:
    """Render the rollback approval prompt shown after a failed step."""

    return "\n".join(
        [
            "=" * 80,
            f"Rollback Prompt: {step['id']} - {step['title']}",
            f"failure: {error}",
            f"failed_phase: {error.phase}",
            f"failed_command: {error.command_id}",
            f"returncode: {error.returncode}",
            render_phase_preview("rollback", step["rollback"], rollback=True),
            "approval options: yes / no",
            "=" * 80,
        ]
    )


def render_plan_summary(
    plan: dict[str, Any],
    *,
    task_id: str,
    approval_threshold: str,
    selected_step_mode: bool,
    resumed_run: bool,
    remote_sync_enabled: bool,
) -> str:
    """Render the plan summary shown before execution starts."""

    remote_sync = plan.get("remote_sync")
    lines = [
        "=" * 80,
        f"Plan: {plan['plan_id']} - {plan['plan_title']}",
    ]
    if plan.get("description"):
        lines.append(f"description: {plan['description']}")
    if plan.get("operator"):
        lines.append(f"operator: {plan['operator']}")
    lines.extend(
        [
            f"task_id: {task_id}",
            f"approval_threshold: {approval_threshold}",
            f"target: host={plan['target']['host']} os={plan['target']['os']}",
            f"invocation_mode: {'selected_steps' if selected_step_mode else 'full_plan'}",
            f"resume_run: {'yes' if resumed_run else 'no'}",
        ]
    )
    if remote_sync and remote_sync.get("enabled"):
        phases = ",".join(remote_sync.get("phases", ["plan_end"]))
        required = "true" if remote_sync.get("required", False) else "false"
        if remote_sync_enabled:
            lines.append(
                "remote_sync: "
                f"enabled target={remote_sync['target']} phases={phases} required={required}"
            )
        else:
            lines.append(
                "remote_sync: "
                f"configured target={remote_sync['target']} phases={phases} required={required} "
                "(suppressed for this invocation)"
            )
    else:
        lines.append("remote_sync: disabled")
    lines.append(f"step_count: {len(plan['steps'])}")
    lines.append("plan execution summary:")
    for index, step in enumerate(plan["steps"], start=1):
        lines.extend(
            [
                "-" * 80,
                f"[{index}] {step['id']} - {step['title']}",
                f"  goal: {step['goal']}",
                f"  reason: {step['reason']}",
                f"  risk: {step['risk']['level']} | {step['risk']['summary']}",
            ]
        )
        if step["risk"].get("approval_hint"):
            lines.append(f"  approval_hint: {step['risk']['approval_hint']}")
        auto_approve_modes = step["risk"].get("auto_approve_modes", [])
        if auto_approve_modes:
            lines.append(f"  auto_approve_modes: {', '.join(auto_approve_modes)}")
        lines.append(render_step_approval_snapshot(step, indent="  "))
        lines.append(render_command_list("pre_checks", step["pre_checks"], indent="  "))
        lines.append(render_command_list("commands", step["commands"], indent="  "))
        lines.append(render_command_list("post_checks", step["post_checks"], indent="  "))
        lines.append(render_command_list("rollback", step["rollback"], indent="  ", rollback=True))
    lines.append("=" * 80)
    return "\n".join(lines)


def format_event_line(payload: dict[str, Any]) -> str:
    """Render a compact, human-readable event line for the web event stream."""

    parts = [payload.get("ts", "?"), payload.get("event", "unknown")]
    for key in [
        "step_id",
        "phase",
        "command_id",
        "sync_phase",
        "status",
        "reason",
        "returncode",
        "error",
    ]:
        value = payload.get(key)
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return " | ".join(parts)


__all__ = [
    "build_step_effect_summary",
    "command_effects",
    "command_is_read_only",
    "command_review_note",
    "format_event_line",
    "format_items",
    "render_command_list",
    "render_command_script",
    "render_execution_preview",
    "render_phase_preview",
    "render_plan_summary",
    "render_step",
    "render_step_approval_snapshot",
    "render_step_effect_summary",
    "summarize_write_scope",
    "unique_preserve_order",
]
