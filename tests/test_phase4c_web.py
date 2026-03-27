"""Unit tests for Web approval asset loading and rendering helpers."""

from __future__ import annotations

import unittest

from devops_runner.approvals.web import _load_static_text
from devops_runner.render import render_rollback_prompt


class WebAssetTests(unittest.TestCase):
    """Validate Web approval assets and rollback rendering."""

    def test_load_static_index_contains_title(self) -> None:
        """The bundled Web index asset should be readable from package resources."""

        index_html = _load_static_text("index.html")

        self.assertIn("Runner Approval", index_html)

    def test_render_rollback_prompt_contains_failure_context(self) -> None:
        """Rollback prompts should include the failed phase and command identifiers."""

        class DummyError:
            phase = "commands"
            command_id = "cmd.demo"
            returncode = 17

            def __str__(self) -> str:
                return "dummy failure"

        prompt = render_rollback_prompt(
            {
                "id": "step.demo",
                "title": "Demo Step",
                "rollback": [],
            },
            error=DummyError(),
        )

        self.assertIn("Rollback Prompt: step.demo - Demo Step", prompt)
        self.assertIn("failed_phase: commands", prompt)
        self.assertIn("failed_command: cmd.demo", prompt)


if __name__ == "__main__":
    unittest.main()
