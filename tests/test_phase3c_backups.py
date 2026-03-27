"""Unit tests for backup target resolution and snapshot helpers."""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from devops_runner.backups import collect_backup_targets, resolve_backup_dir, snapshot_paths


class BackupHelperTests(unittest.TestCase):
    """Validate backup target resolution and archive materialization."""

    def test_collect_backup_targets_includes_write_paths_and_etc(self) -> None:
        """High-risk steps should collect declared write targets and `/etc` when touched."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = pathlib.Path(temp_dir)
            step = {
                "id": "file.delete_demo",
                "risk": {"level": "high", "summary": "delete demo file"},
                "pre_checks": [],
                "commands": [
                    {
                        "id": "cmd.delete",
                        "name": "Delete file",
                        "run": "rm -f demo_state/demo.txt",
                        "effects": {
                            "writes_paths": [
                                "demo_state/demo.txt",
                                "/etc/hosts",
                            ]
                        },
                    }
                ],
                "post_checks": [],
                "rollback": [],
            }

            targets = collect_backup_targets(step, project_root=project_root)

            self.assertIn((project_root / "demo_state" / "demo.txt").resolve(), targets)
            self.assertIn(pathlib.Path("/etc"), targets)

    def test_resolve_backup_dir_uses_default_and_custom_locations(self) -> None:
        """Backup directories should default under backup_root and allow step overrides."""

        backup_root = pathlib.Path("/repo/backups")
        default_dir = resolve_backup_dir(
            {"id": "demo.step"},
            backup_root=backup_root,
            task_id="task-demo",
            run_id="run-001",
        )
        custom_dir = resolve_backup_dir(
            {"id": "demo.step", "backup": {"location": "custom-location"}},
            backup_root=backup_root,
            task_id="task-demo",
            run_id="run-001",
        )

        self.assertEqual(default_dir, pathlib.Path("/repo/backups/task-demo/run-001"))
        self.assertEqual(custom_dir, pathlib.Path("/repo/backups/custom-location/task-demo/run-001"))

    def test_snapshot_paths_writes_archive_and_manifest(self) -> None:
        """Snapshots should archive existing paths and record missing ones in a manifest."""

        events: list[dict[str, object]] = []

        def log_event(event_type: str, **data: object) -> None:
            events.append({"event": event_type, **data})

        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            existing = root / "demo.txt"
            existing.write_text("demo\n", encoding="utf-8")
            missing = root / "missing.txt"
            archive_path = snapshot_paths(
                step_id="file.delete_demo",
                label="pre",
                targets=[existing, missing],
                backup_dir=root / "backups",
                log_event=log_event,
            )

            self.assertTrue(archive_path.exists())
            manifest = json.loads((root / "backups" / "file.delete_demo-pre-paths.manifest.json").read_text())
            self.assertEqual(len(manifest["included"]), 1)
            self.assertEqual(len(manifest["missing"]), 1)
            self.assertEqual(events[0]["event"], "backup_started")
            self.assertEqual(events[-1]["event"], "backup_finished")


if __name__ == "__main__":
    unittest.main()
