"""Phase 3a tests for the extracted audit logger."""

from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from devops_runner.audit import AuditLogger


class Phase3AuditTest(unittest.TestCase):
    """Validate JSONL writes and listener fan-out for audit events."""

    def test_log_writes_jsonl_and_notifies_listener(self) -> None:
        """Each audit event should be persisted and forwarded once."""

        received: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = pathlib.Path(temp_dir) / "runner.jsonl"
            logger = AuditLogger(log_path, base_fields={"task_id": "default", "run_id": "run-1", "plan_id": "plan-1"})
            logger.add_listener(received.append)

            payload = logger.log("phase_started", step_id="smoke.readonly", phase="commands")

            self.assertEqual(payload["event"], "phase_started")
            self.assertEqual(payload["task_id"], "default")
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["step_id"], "smoke.readonly")

            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            written = json.loads(lines[0])
            self.assertEqual(written["event"], "phase_started")
            self.assertEqual(written["plan_id"], "plan-1")
            self.assertIn("ts", written)


if __name__ == "__main__":
    unittest.main()
