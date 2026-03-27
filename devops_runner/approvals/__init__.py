"""Approval backend interfaces and shared policy helpers."""

from devops_runner.approvals.base import ApprovalBackend
from devops_runner.approvals.mode_store import ApprovalModeStore
from devops_runner.approvals.policy import (
    mode_auto_approves_step,
    risk_meets_threshold,
    step_requires_approval,
)
from devops_runner.approvals.tty import TTYApprovalBackend
from devops_runner.approvals.web import WebApprovalBackend
from devops_runner.approvals.web_state import WebApprovalState

__all__ = [
    "ApprovalBackend",
    "ApprovalModeStore",
    "TTYApprovalBackend",
    "WebApprovalBackend",
    "WebApprovalState",
    "mode_auto_approves_step",
    "risk_meets_threshold",
    "step_requires_approval",
]
