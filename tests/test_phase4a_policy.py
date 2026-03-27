"""Unit tests for shared approval policy helpers."""

from __future__ import annotations

import unittest

from devops_runner.approvals.policy import (
    mode_auto_approves_step,
    risk_meets_threshold,
    step_requires_approval,
)


def build_step(risk_level: str, *, auto_approve_modes: list[str] | None = None) -> dict[str, object]:
    """Create a minimal step payload for policy tests."""

    return {
        "id": "step.demo",
        "title": "Demo Step",
        "risk": {
            "level": risk_level,
            "auto_approve_modes": list(auto_approve_modes or []),
        },
    }


class ApprovalPolicyTests(unittest.TestCase):
    """Validate threshold and auto-approval policy behavior."""

    def test_risk_meets_threshold(self) -> None:
        """Higher risk levels should satisfy lower thresholds."""

        self.assertTrue(risk_meets_threshold("high", "medium"))
        self.assertTrue(risk_meets_threshold("low", "low"))
        self.assertFalse(risk_meets_threshold("low", "high"))

    def test_step_requires_approval_uses_threshold(self) -> None:
        """Step approval should follow the configured threshold."""

        step = build_step("medium")

        self.assertTrue(step_requires_approval(step, approval_threshold="low"))
        self.assertFalse(step_requires_approval(step, approval_threshold="high"))

    def test_mode_auto_approves_step_honors_explicit_allowlist(self) -> None:
        """Explicit allowlisted modes should auto-approve regardless of risk."""

        step = build_step("medium", auto_approve_modes=["auto_low_risk"])

        self.assertTrue(mode_auto_approves_step("auto_low_risk", step))

    def test_mode_auto_approves_step_for_low_risk(self) -> None:
        """Low-risk steps should auto-approve in auto_low_risk mode."""

        step = build_step("low")

        self.assertTrue(mode_auto_approves_step("auto_low_risk", step))
        self.assertFalse(mode_auto_approves_step("manual", step))


if __name__ == "__main__":
    unittest.main()
