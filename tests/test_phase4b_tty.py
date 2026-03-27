"""Unit tests for TTY approval editing helpers."""

from __future__ import annotations

import unittest

from devops_runner.approvals.tty import choose_editor
from devops_runner.errors import RunnerError


class TTYHelperTests(unittest.TestCase):
    """Validate low-level TTY helper behavior."""

    def test_choose_editor_prefers_editor_env(self) -> None:
        """The EDITOR environment variable should win over fallback probing."""

        editor = choose_editor(env={"EDITOR": "nvim"})

        self.assertEqual(editor, "nvim")

    def test_choose_editor_raises_when_no_editor_is_available(self) -> None:
        """Missing editor configuration should raise a stable runner error."""

        with self.assertRaises(RunnerError):
            choose_editor(env={}, which_func=lambda _: None)


if __name__ == "__main__":
    unittest.main()
