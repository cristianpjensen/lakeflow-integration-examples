import argparse
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.package_catalog_artifact import (
    WHEEL_DEPENDENCY_PLACEHOLDER,
    load_and_validate_definition,
    package_artifact,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = REPOSITORY_ROOT / "integrations/echo/src/lakeflow_echo/integration.py"
WHEEL_NAME = "lakeflow_echo-0.0.1-py3-none-any.whl"
WHEEL_PATH = REPOSITORY_ROOT / "dist" / WHEEL_NAME


class EchoArtifactTest(unittest.TestCase):
    def test_packages_frontend_and_job_contract(self) -> None:
        self.assertTrue(WHEEL_PATH.is_file(), f"build the wheel first: {WHEEL_PATH}")

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            artifact_dir = package_artifact(
                argparse.Namespace(
                    integration_id="echo",
                    package_module="lakeflow_echo",
                    main="lakeflow_echo.integration.echo",
                    source=SOURCE_PATH,
                    wheel=WHEEL_PATH,
                    environment_key="echo_environment",
                    output_dir=output_dir,
                )
            )

            relative_files = sorted(
                path.relative_to(output_dir).as_posix()
                for path in output_dir.rglob("*")
                if path.is_file()
            )
            self.assertEqual(
                relative_files,
                [
                    "echo/integration.py",
                    "echo/integration.yaml",
                    f"echo/{WHEEL_NAME}",
                ],
            )
            self.assertEqual((artifact_dir / "integration.py").read_bytes(), SOURCE_PATH.read_bytes())
            self.assertEqual((artifact_dir / WHEEL_NAME).read_bytes(), WHEEL_PATH.read_bytes())

            definition = json.loads((artifact_dir / "integration.yaml").read_text())
            self.assertEqual(definition["main"], "lakeflow_echo.integration.echo")
            self.assertEqual(
                definition["config"],
                {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "repeat_count": {"type": "integer", "x-ui": {"widget": "number"}},
                    },
                    "required": ["message", "repeat_count"],
                },
            )
            self.assertEqual(
                definition["environment"],
                {
                    "environment_key": "echo_environment",
                    "environment_version": "5",
                    "dependencies": [WHEEL_DEPENDENCY_PLACEHOLDER],
                },
            )

            job_definition = (REPOSITORY_ROOT / "resources/echo.job.yml").read_text()
            job_parameter_names = re.findall(r"^\s+- name: ([a-z_][a-z0-9_]*)$", job_definition, re.MULTILINE)
            self.assertEqual(job_parameter_names, ["message", "repeat_count"])
            self.assertRegex(job_definition, r"(?m)^\s+main: lakeflow_echo\.integration\.echo$")

    def test_rejects_unsupported_generated_parameter_type(self) -> None:
        definition = {
            "schema": "lakeflow-integration-v0.1.0",
            "main": "lakeflow_echo.integration.echo",
            "config": {
                "type": "object",
                "properties": {"message": {"type": "array"}},
                "required": ["message"],
            },
            "environment": {
                "environment_key": "echo_environment",
                "environment_version": "5",
                "dependencies": [WHEEL_DEPENDENCY_PLACEHOLDER],
            },
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            definition_path = Path(temporary_directory) / "integration.yaml"
            definition_path.write_text(json.dumps(definition))

            with self.assertRaisesRegex(ValueError, r"unsupported config types: \['array'\]"):
                load_and_validate_definition(definition_path, "lakeflow_echo.integration.echo")


if __name__ == "__main__":
    unittest.main()
