"""Phase 2 tests for extracted render helpers."""

from __future__ import annotations

import pathlib
import unittest

from devops_runner.render import format_event_line, render_plan_summary, render_step
from devops_runner.plan import load_json


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SMOKE_PLAN_PATH = REPO_ROOT / "plans" / "examples" / "smoke-test.json"


class Phase2RenderTest(unittest.TestCase):
    """Validate the pure string rendering introduced in Phase 2."""

    def test_render_step_returns_text(self) -> None:
        """A single step render should return one multiline string."""

        plan = load_json(SMOKE_PLAN_PATH)
        text = render_step(plan["steps"][0])

        self.assertIsInstance(text, str)
        self.assertIn("Step: smoke.readonly - Read-only runner smoke test", text)
        self.assertIn("approval options: yes / no / edit", text)
        self.assertIn("execution preview:", text)

    def test_render_plan_summary_returns_text(self) -> None:
        """The plan summary render should remain suitable for the TTY wrapper."""

        plan = load_json(SMOKE_PLAN_PATH)
        text = render_plan_summary(
            plan,
            task_id="default",
            approval_threshold="high",
            selected_step_mode=False,
            resumed_run=False,
            remote_sync_enabled=False,
        )

        self.assertIsInstance(text, str)
        self.assertIn("Plan: repo-smoke-test - Repository Smoke Test", text)
        self.assertIn("remote_sync: disabled", text)
        self.assertIn("approval_snapshot:", text)

    def test_format_event_line_compacts_known_fields(self) -> None:
        """Event rendering should preserve the compact line format used by the web state."""

        line = format_event_line(
            {
                "ts": "2026-03-26T22:00:00+00:00",
                "event": "command_finished",
                "step_id": "smoke.readonly",
                "phase": "commands",
                "command_id": "cmd.env",
                "returncode": 0,
            }
        )

        self.assertEqual(
            line,
            "2026-03-26T22:00:00+00:00 | command_finished | step_id=smoke.readonly | phase=commands | command_id=cmd.env | returncode=0",
        )


if __name__ == "__main__":
    unittest.main()
