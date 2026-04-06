"""
Unit tests for pf-tasks/clean.py planning/report behavior.
"""

import importlib.util
import unittest
from pathlib import Path


def _load_clean_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "pf-tasks" / "clean.py"
    spec = importlib.util.spec_from_file_location("pf_clean_module", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPfCleanTask(unittest.TestCase):
    def test_determine_cleanup_method_artifacts_only_returns_none(self):
        clean = _load_clean_module()

        class Args:
            method = None
            artifacts = True
            images = False

        self.assertIsNone(clean.determine_cleanup_method(Args()))

    def test_build_cleanup_plan_for_all_with_images_and_artifacts(self):
        clean = _load_clean_module()
        plan = clean.build_cleanup_plan(
            effective_method="all",
            include_images=True,
            include_artifacts=True,
            force_images=True,
        )

        step_names = [step["name"] for step in plan]
        self.assertEqual(
            step_names,
            [
                "systemd_services",
                "compose",
                "containers",
                "images",
                "build_artifacts",
            ],
        )
        self.assertIn("forced", plan[3]["description"])

    def test_execute_cleanup_plan_dry_run_marks_steps_planned(self):
        clean = _load_clean_module()
        plan = clean.build_cleanup_plan(
            effective_method="containers",
            include_images=False,
            include_artifacts=False,
            force_images=False,
        )
        success, results = clean.execute_cleanup_plan(plan, dry_run=True)

        self.assertTrue(success)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "containers")
        self.assertEqual(results[0]["status"], "planned")
        self.assertIsNone(results[0]["success"])


if __name__ == "__main__":
    unittest.main()
