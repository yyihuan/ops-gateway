"""Plan loading, validation, and step-selection helpers.

This module contains pure validation and transformation logic. It must not
depend on approvals, execution, or runner-global mutable state.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

from devops_runner.constants import (
    DEFAULT_TASK_ID,
    PLAN_ID_PATTERN,
    REMOTE_SYNC_TARGET_PATTERN,
    RISK_LEVEL_ORDER,
    STEP_OR_COMMAND_ID_PATTERN,
    TASK_ID_PATTERN,
    VALID_AUTO_APPROVAL_MODES,
    VALID_RISK_LEVELS,
    VALID_SYNC_PHASES,
)
from devops_runner.backups import SUPPORTED_BACKUP_RULES
from devops_runner.errors import RunnerError


def load_json(path: pathlib.Path) -> dict[str, Any]:
    """Load a JSON document from disk.

    Raises:
        RunnerError: The file is missing or contains invalid JSON.
    """

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunnerError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"invalid json in {path}: {exc}") from exc


def write_json(path: pathlib.Path, payload: Any) -> None:
    """Write a JSON document using the repository's stable formatting."""

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return an embedded `plan` payload when present."""

    embedded_plan = payload.get("plan")
    if isinstance(embedded_plan, dict):
        return embedded_plan
    return payload


def validate_string(value: Any, field: str) -> str:
    """Validate that a field is a non-empty string."""

    if not isinstance(value, str) or not value.strip():
        raise RunnerError(f"field '{field}' must be a non-empty string")
    return value


def validate_pattern(value: str, field: str, pattern: re.Pattern[str]) -> None:
    """Validate that a string matches the expected regex pattern."""

    if not pattern.fullmatch(value):
        raise RunnerError(f"field '{field}' must match pattern '{pattern.pattern}'")


def validate_task_id(value: Any, field: str) -> str:
    """Validate a task identifier and return the normalized string."""

    task_id = validate_string(value, field)
    validate_pattern(task_id, field, TASK_ID_PATTERN)
    return task_id


def validate_risk_level(value: Any, field: str) -> str:
    """Validate a risk-level string and return it."""

    level = validate_string(value, field)
    if level not in VALID_RISK_LEVELS:
        raise RunnerError(f"field '{field}' must be one of {list(RISK_LEVEL_ORDER.keys())}")
    return level


def validate_string_list(value: Any, field: str) -> None:
    """Validate a list that contains only non-empty strings."""

    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise RunnerError(f"field '{field}' must be a non-empty string array")


def validate_effects(effects: dict[str, Any], field: str) -> None:
    """Validate the optional command effects object."""

    allowed_fields = {
        "read_only",
        "requires_root",
        "reads_paths",
        "writes_paths",
        "network_targets",
        "service_actions",
    }
    unexpected = sorted(set(effects.keys()) - allowed_fields)
    if unexpected:
        raise RunnerError(f"field '{field}' contains unsupported keys: {unexpected}")
    for key in ["read_only", "requires_root"]:
        if key in effects and not isinstance(effects[key], bool):
            raise RunnerError(f"field '{field}.{key}' must be a boolean")
    for key in ["reads_paths", "writes_paths", "network_targets", "service_actions"]:
        if key in effects:
            validate_string_list(effects[key], f"{field}.{key}")


def validate_command(command: dict[str, Any], phase: str, index: int) -> None:
    """Validate a single command entry inside a step phase."""

    required = ["id", "name", "run"]
    for field in required:
        validate_string(command.get(field), f"{phase}[{index}].{field}")
    validate_pattern(command["id"], f"{phase}[{index}].id", STEP_OR_COMMAND_ID_PATTERN)
    if "review_note" in command:
        validate_string(command.get("review_note"), f"{phase}[{index}].review_note")
    if "effects" in command:
        effects = command["effects"]
        if not isinstance(effects, dict):
            raise RunnerError(f"field '{phase}[{index}].effects' must be an object")
        validate_effects(effects, f"{phase}[{index}].effects")
    if "timeout_seconds" in command:
        timeout = command["timeout_seconds"]
        if not isinstance(timeout, int) or timeout < 1:
            raise RunnerError(f"field '{phase}[{index}].timeout_seconds' must be a positive integer")
    if "allow_failure" in command and not isinstance(command["allow_failure"], bool):
        raise RunnerError(f"field '{phase}[{index}].allow_failure' must be a boolean")
    env = command.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise RunnerError(f"field '{phase}[{index}].env' must be a string map")


def validate_step(step: dict[str, Any], index: int) -> None:
    """Validate a step definition in the execution plan."""

    for field in ["id", "title", "goal", "reason"]:
        validate_string(step.get(field), f"steps[{index}].{field}")
    validate_pattern(step["id"], f"steps[{index}].id", STEP_OR_COMMAND_ID_PATTERN)
    risk = step.get("risk")
    if not isinstance(risk, dict):
        raise RunnerError(f"field 'steps[{index}].risk' must be an object")
    validate_risk_level(risk.get("level"), f"steps[{index}].risk.level")
    validate_string(risk.get("summary"), f"steps[{index}].risk.summary")
    if "approval_hint" in risk:
        validate_string(risk.get("approval_hint"), f"steps[{index}].risk.approval_hint")
    if "auto_approve_modes" in risk:
        auto_approve_modes = risk["auto_approve_modes"]
        if not isinstance(auto_approve_modes, list) or not all(isinstance(item, str) for item in auto_approve_modes):
            raise RunnerError(f"field 'steps[{index}].risk.auto_approve_modes' must be a string array")
        invalid_modes = sorted(set(auto_approve_modes) - VALID_AUTO_APPROVAL_MODES)
        if invalid_modes:
            raise RunnerError(
                f"field 'steps[{index}].risk.auto_approve_modes' contains unsupported values: {invalid_modes}"
            )
    backup = step.get("backup")
    if backup is not None:
        if not isinstance(backup, dict):
            raise RunnerError(f"field 'steps[{index}].backup' must be an object")
        if "location" in backup:
            validate_string(backup.get("location"), f"steps[{index}].backup.location")
        if "paths" in backup:
            paths = backup["paths"]
            if not isinstance(paths, list) or not all(isinstance(item, str) and item for item in paths):
                raise RunnerError(f"field 'steps[{index}].backup.paths' must be a string array")
        if "rules" in backup:
            rules = backup["rules"]
            if not isinstance(rules, list) or not all(isinstance(item, str) for item in rules):
                raise RunnerError(f"field 'steps[{index}].backup.rules' must be a string array")
            invalid_rules = sorted(set(rules) - SUPPORTED_BACKUP_RULES)
            if invalid_rules:
                raise RunnerError(
                    f"field 'steps[{index}].backup.rules' contains unsupported values: {invalid_rules}"
                )
    for phase in ["pre_checks", "commands", "post_checks", "rollback"]:
        value = step.get(phase)
        if not isinstance(value, list):
            raise RunnerError(f"field 'steps[{index}].{phase}' must be an array")
        if phase == "commands" and not value:
            raise RunnerError(f"field 'steps[{index}].commands' must contain at least one command")
        for command_index, command in enumerate(value):
            if not isinstance(command, dict):
                raise RunnerError(f"field 'steps[{index}].{phase}[{command_index}]' must be an object")
            validate_command(command, f"steps[{index}].{phase}", command_index)


def validate_plan(plan: dict[str, Any]) -> None:
    """Validate a full plan payload against the current runner schema."""

    for field in ["schema_version", "plan_id", "plan_title"]:
        validate_string(plan.get(field), field)
    if plan["schema_version"] != "1.0.0":
        raise RunnerError("only schema_version=1.0.0 is supported")
    validate_pattern(plan["plan_id"], "plan_id", PLAN_ID_PATTERN)
    if "operator" in plan:
        validate_string(plan.get("operator"), "operator")
    target = plan.get("target")
    if not isinstance(target, dict):
        raise RunnerError("field 'target' must be an object")
    for field in ["host", "os"]:
        validate_string(target.get(field), f"target.{field}")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RunnerError("field 'steps' must be a non-empty array")
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise RunnerError(f"field 'steps[{index}]' must be an object")
        validate_step(step, index)
    remote_sync = plan.get("remote_sync")
    if remote_sync is not None:
        if not isinstance(remote_sync, dict):
            raise RunnerError("field 'remote_sync' must be an object")
        if not isinstance(remote_sync.get("enabled"), bool):
            raise RunnerError("field 'remote_sync.enabled' must be a boolean")
        validate_string(remote_sync.get("target"), "remote_sync.target")
        validate_pattern(remote_sync["target"], "remote_sync.target", REMOTE_SYNC_TARGET_PATTERN)
        phases = remote_sync.get("phases", ["plan_end"])
        if not isinstance(phases, list) or not all(isinstance(item, str) for item in phases):
            raise RunnerError("field 'remote_sync.phases' must be a string array")
        invalid_phases = sorted(set(phases) - VALID_SYNC_PHASES)
        if invalid_phases:
            raise RunnerError(f"field 'remote_sync.phases' contains unsupported values: {invalid_phases}")
    metadata = plan.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise RunnerError("field 'metadata' must be an object")
        if "task_id" in metadata:
            validate_task_id(metadata["task_id"], "metadata.task_id")


def extract_task_id(plan: dict[str, Any]) -> str:
    """Return the effective task identifier from plan metadata."""

    metadata = plan.get("metadata")
    if not isinstance(metadata, dict):
        return DEFAULT_TASK_ID
    task_id = metadata.get("task_id")
    if task_id is None:
        return DEFAULT_TASK_ID
    return validate_task_id(task_id, "metadata.task_id")


def select_steps(plan: dict[str, Any], requested_step_ids: list[str]) -> dict[str, Any]:
    """Filter a plan down to a requested subset while preserving original order."""

    if not requested_step_ids:
        return plan
    available_steps = {step["id"]: step for step in plan["steps"]}
    missing = [step_id for step_id in requested_step_ids if step_id not in available_steps]
    if missing:
        raise RunnerError(f"requested step ids not found in plan: {missing}")
    selected_ids = set(requested_step_ids)
    filtered_plan = dict(plan)
    filtered_plan["steps"] = [step for step in plan["steps"] if step["id"] in selected_ids]
    if not filtered_plan["steps"]:
        raise RunnerError("step selection produced an empty plan")
    return filtered_plan


__all__ = [
    "extract_plan_payload",
    "extract_task_id",
    "load_json",
    "select_steps",
    "validate_command",
    "validate_effects",
    "validate_pattern",
    "validate_plan",
    "validate_risk_level",
    "validate_step",
    "validate_string",
    "validate_string_list",
    "validate_task_id",
    "write_json",
]
