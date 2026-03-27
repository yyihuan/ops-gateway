"""Unit tests for phase 3b execution and sync helper extraction."""

from __future__ import annotations

import pathlib
import unittest

from devops_runner.execution import build_command_env
from devops_runner.sync import split_remote_sync_target


class ExecutionHelperTests(unittest.TestCase):
    """Validate stable environment injection helpers."""

    def test_build_command_env_injects_runner_context(self) -> None:
        """Command environments should include stable RUNNER_* metadata."""

        env = build_command_env(
            {"env": {"EXTRA_FLAG": "1"}},
            task_id="task-02",
            project_root=pathlib.Path("/repo"),
            base_run_root=pathlib.Path("/runs"),
            task_run_root=pathlib.Path("/runs/task-02"),
            run_id="run-123",
            run_dir=pathlib.Path("/runs/task-02/run-123"),
            backup_root=pathlib.Path("/repo/backups"),
            backups_dir=pathlib.Path("/runs/task-02/run-123/backups"),
            step_backup_dir=pathlib.Path("/repo/backups/task-02/run-123"),
            logs_dir=pathlib.Path("/runs/task-02/run-123/logs"),
            steps_dir=pathlib.Path("/runs/task-02/run-123/steps"),
            plan_id="smoke-plan",
            plan_title="Smoke Plan",
            target_host="localhost",
            target_os="Ubuntu 24.04",
        )

        self.assertEqual(env["EXTRA_FLAG"], "1")
        self.assertEqual(env["RUNNER_TASK_ID"], "task-02")
        self.assertEqual(env["RUNNER_PROJECT_ROOT"], "/repo")
        self.assertEqual(env["RUNNER_BASE_RUN_ROOT"], "/runs")
        self.assertEqual(env["RUNNER_TASK_RUN_ROOT"], "/runs/task-02")
        self.assertEqual(env["RUNNER_RUN_ID"], "run-123")
        self.assertEqual(env["RUNNER_RUN_DIR"], "/runs/task-02/run-123")
        self.assertEqual(env["RUNNER_BACKUP_ROOT"], "/repo/backups")
        self.assertEqual(env["RUNNER_STEP_BACKUP_DIR"], "/repo/backups/task-02/run-123")
        self.assertEqual(env["RUNNER_PLAN_ID"], "smoke-plan")
        self.assertEqual(env["RUNNER_TARGET_HOST"], "localhost")


class SyncHelperTests(unittest.TestCase):
    """Validate remote sync target parsing helpers."""

    def test_split_remote_sync_target_returns_host_and_path(self) -> None:
        """A valid rsync target should be split into host and path components."""

        host, path = split_remote_sync_target("zcj@example:/tmp/output")

        self.assertEqual(host, "zcj@example")
        self.assertEqual(path, "/tmp/output")


if __name__ == "__main__":
    unittest.main()
