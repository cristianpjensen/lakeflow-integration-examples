import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WHEEL_DEPENDENCY_PLACEHOLDER = "__DATABRICKS_CURATED_INTEGRATION_WHEEL_PATH__"


class RepositoryContractTest(unittest.TestCase):
    def test_builds_do_not_depend_on_runner_python_packages(self) -> None:
        for relative_path in [".github/workflows/ci.yml", "databricks.yml"]:
            path = REPOSITORY_ROOT / relative_path
            self.assertNotIn("--no-build-isolation", path.read_text(), relative_path)

    def test_every_integration_is_wired_into_ci_and_the_bundle(self) -> None:
        integration_ids = sorted(
            path.name for path in (REPOSITORY_ROOT / "integrations").iterdir() if (path / "pyproject.toml").is_file()
        )
        workflow = (REPOSITORY_ROOT / ".github/workflows/ci.yml").read_text()
        bundle = (REPOSITORY_ROOT / "databricks.yml").read_text()
        matrix_ids = sorted(re.findall(r"^\s+- integration_id: ([a-z0-9-]+)$", workflow, re.MULTILINE))

        self.assertEqual(integration_ids, matrix_ids)
        self.assertEqual(bundle.count(WHEEL_DEPENDENCY_PLACEHOLDER), len(integration_ids))
        self.assertNotIn("${workspace.artifact_path}", bundle)
        for integration_id in integration_ids:
            resource_id = integration_id.replace("-", "_")
            lockfile = REPOSITORY_ROOT / f"integrations/{integration_id}/uv.lock"
            self.assertTrue(lockfile.is_file())
            self.assertNotIn("pypi-proxy.cloud.databricks.com", lockfile.read_text())
            self.assertTrue((REPOSITORY_ROOT / f"resources/{integration_id}.job.yml").is_file())

            self.assertIn(f"  {resource_id}_wheel:\n", bundle)
            self.assertIn(f"  {resource_id}_integration_yaml:\n", bundle)


if __name__ == "__main__":
    unittest.main()
