"""Stable constants and regex patterns for the transitional runner package.

This module only defines reusable constants. It must not import execution,
approval, or CLI code.
"""

from __future__ import annotations

import re

VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
RISK_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
VALID_SYNC_PHASES = {"step_end", "plan_end"}
VALID_AUTO_APPROVAL_MODES = {"manual", "auto_low_risk"}

DEFAULT_TIMEOUT = 1800
STREAM_JOIN_TIMEOUT_SECONDS = 10
DEFAULT_TASK_ID = "default"
DEFAULT_APPROVAL_THRESHOLD = "low"

PLAN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
TASK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
STEP_OR_COMMAND_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
REMOTE_SYNC_TARGET_PATTERN = re.compile(r"^(?:[^@:/\s]+@)?[^:/\s]+:.+$")

__all__ = [
    "DEFAULT_APPROVAL_THRESHOLD",
    "DEFAULT_TASK_ID",
    "DEFAULT_TIMEOUT",
    "PLAN_ID_PATTERN",
    "REMOTE_SYNC_TARGET_PATTERN",
    "RISK_LEVEL_ORDER",
    "STEP_OR_COMMAND_ID_PATTERN",
    "STREAM_JOIN_TIMEOUT_SECONDS",
    "TASK_ID_PATTERN",
    "VALID_AUTO_APPROVAL_MODES",
    "VALID_RISK_LEVELS",
    "VALID_SYNC_PHASES",
]
