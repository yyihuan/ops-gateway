"""Pure approval policy helpers shared by all backends."""

from __future__ import annotations

from typing import Any

from devops_runner.constants import RISK_LEVEL_ORDER
from devops_runner.errors import RunnerError


def _validate_risk_level(value: str, field_name: str) -> str:
    """Return a validated risk level or raise a stable runner error."""

    if value not in RISK_LEVEL_ORDER:
        raise RunnerError(f"{field_name} must be one of {', '.join(RISK_LEVEL_ORDER)}")
    return value


def risk_meets_threshold(risk_level: str, threshold: str) -> bool:
    """Return whether a risk level meets or exceeds the approval threshold."""

    resolved_risk = _validate_risk_level(risk_level, "risk_level")
    resolved_threshold = _validate_risk_level(threshold, "approval_threshold")
    return RISK_LEVEL_ORDER[resolved_risk] >= RISK_LEVEL_ORDER[resolved_threshold]


def step_requires_approval(step: dict[str, Any], *, approval_threshold: str) -> bool:
    """Return whether the current step requires explicit approval."""

    return risk_meets_threshold(step["risk"]["level"], approval_threshold)


def mode_auto_approves_step(mode: str, step: dict[str, Any]) -> bool:
    """Return whether the current approval mode auto-approves the step."""

    if mode == "manual":
        return False
    if mode in step["risk"].get("auto_approve_modes", []):
        return True
    if mode == "auto_low_risk":
        return step["risk"]["level"] == "low"
    return False


__all__ = [
    "mode_auto_approves_step",
    "risk_meets_threshold",
    "step_requires_approval",
]
