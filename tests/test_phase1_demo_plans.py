"""Validate repository demo and template plans remain schema-valid."""

from __future__ import annotations

import pathlib
import unittest

from devops_runner import validate_plan
from devops_runner.plan import load_json


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAN_PATHS = [
    REPO_ROOT / "plans" / "examples" / "smoke-test.json",
    REPO_ROOT / "plans" / "examples" / "web-auto-approval-test.json",
    REPO_ROOT / "plans" / "templates" / "cleanup-plan-template.json",
    REPO_ROOT / "tasks" / "01-local-baseline-audit" / "plans" / "01-capture-local-baseline.json",
    REPO_ROOT / "tasks" / "02-local-file-lifecycle" / "plans" / "01-create-and-delete-demo-file.json",
]


class DemoPlanValidationTests(unittest.TestCase):
    """Keep repository demo plans aligned with the current schema."""

    def test_demo_plans_validate(self) -> None:
        """All checked-in demo plans should pass validation."""

        for path in PLAN_PATHS:
            with self.subTest(plan=path.relative_to(REPO_ROOT).as_posix()):
                validate_plan(load_json(path))


if __name__ == "__main__":
    unittest.main()
