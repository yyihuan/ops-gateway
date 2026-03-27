"""Phase 1 unit tests for extracted pure runner helpers."""

from __future__ import annotations

import copy
import pathlib
import tempfile
import unittest

from devops_runner import validate_plan
from devops_runner.paths import resolve_resume_run_path, slugify
from devops_runner.plan import extract_task_id, load_json, select_steps


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SMOKE_PLAN_PATH = REPO_ROOT / "plans" / "examples" / "smoke-test.json"


class Phase1FoundationsTest(unittest.TestCase):
    """Validate the pure helpers extracted during Phase 1."""

    def test_validate_plan_accepts_repo_smoke_plan(self) -> None:
        """The repository smoke plan should remain valid under extracted validation logic."""

        plan = load_json(SMOKE_PLAN_PATH)
        validate_plan(plan)

    def test_extract_task_id_defaults_to_default(self) -> None:
        """Plans without metadata should fall back to the default task id."""

        self.assertEqual(extract_task_id({"plan_id": "abc"}), "default")

    def test_extract_task_id_reads_metadata_override(self) -> None:
        """A valid metadata.task_id should be returned unchanged."""

        self.assertEqual(extract_task_id({"metadata": {"task_id": "task-phase1"}}), "task-phase1")

    def test_select_steps_preserves_original_order(self) -> None:
        """Step selection should filter by id without reordering the original plan."""

        plan = load_json(SMOKE_PLAN_PATH)
        second_step = copy.deepcopy(plan["steps"][0])
        second_step["id"] = "smoke.second"
        second_step["title"] = "Second step"
        plan["steps"].append(second_step)

        selected = select_steps(plan, ["smoke.second", "smoke.readonly"])

        self.assertEqual([step["id"] for step in selected["steps"]], ["smoke.readonly", "smoke.second"])

    def test_slugify_normalizes_unsafe_characters(self) -> None:
        """Slug generation should preserve allowed characters and normalize separators."""

        self.assertEqual(slugify("GPU MVP / Phase 1"), "gpu-mvp---phase-1")
        self.assertEqual(slugify("..."), "run")

    def test_resolve_resume_run_path_prefers_task_scoped_layout(self) -> None:
        """A missing relative run id should map to the task-scoped run layout."""

        with tempfile.TemporaryDirectory() as temp_dir:
            run_root = pathlib.Path(temp_dir) / "runs"
            task_dir = run_root / "task-phase1"
            task_dir.mkdir(parents=True)
            expected = task_dir / "20260326T000000Z-smoke"

            resolved = resolve_resume_run_path("20260326T000000Z-smoke", run_root, "task-phase1")

            self.assertEqual(resolved, expected.resolve())

    def test_resolve_resume_run_path_uses_existing_flat_run(self) -> None:
        """Legacy flat run directories should remain resumable for compatibility."""

        with tempfile.TemporaryDirectory() as temp_dir:
            run_root = pathlib.Path(temp_dir) / "runs"
            flat_run = run_root / "legacy-run"
            flat_run.mkdir(parents=True)

            resolved = resolve_resume_run_path("legacy-run", run_root, "task-phase1")

            self.assertEqual(resolved, flat_run.resolve())


if __name__ == "__main__":
    unittest.main()
