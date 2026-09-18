import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from databricks.lakeflow.integrations.generate import main as generate_integration_yaml

WHEEL_DEPENDENCY_PLACEHOLDER = "__DATABRICKS_CURATED_INTEGRATION_WHEEL_PATH__"
INTEGRATION_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SUPPORTED_CONFIG_TYPES = frozenset({"boolean", "integer", "number", "string"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one frontend-installable Lakeflow integration artifact.")
    parser.add_argument("--integration-id", required=True)
    parser.add_argument("--package-module", required=True)
    parser.add_argument("--main", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--environment-key", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not INTEGRATION_ID_PATTERN.fullmatch(args.integration_id):
        raise ValueError("integration ID must be lowercase kebab-case")
    if not args.source.is_file() or args.source.suffix != ".py":
        raise ValueError("source must be an existing .py file")
    if not args.wheel.is_file() or args.wheel.suffix != ".whl":
        raise ValueError("wheel must be an existing .whl file")


def generate_definition(args: argparse.Namespace, output_dir: Path) -> Path:
    generate_integration_yaml(
        [
            "--package-module",
            args.package_module,
            "--output-dir",
            str(output_dir),
            "--environment-version",
            "5",
            "--environment-key",
            args.environment_key,
            "--dependency",
            WHEEL_DEPENDENCY_PLACEHOLDER,
        ]
    )
    generated = sorted([*output_dir.glob("*.yaml"), *output_dir.glob("*.yml")])
    if len(generated) != 1:
        raise ValueError(f"expected exactly one generated integration definition, found {len(generated)}")
    return generated[0]


def load_and_validate_definition(path: Path, expected_main: str) -> dict[str, Any]:
    definition = json.loads(path.read_text())
    if definition.get("schema") != "lakeflow-integration-v0.1.0":
        raise ValueError("generated definition has an unsupported schema")
    if definition.get("main") != expected_main:
        raise ValueError(f"generated definition main must be {expected_main!r}")

    environment = definition.get("environment")
    if not isinstance(environment, dict) or environment.get("environment_version") != "5":
        raise ValueError("generated definition must use environment version 5")
    if environment.get("dependencies") != [WHEEL_DEPENDENCY_PLACEHOLDER]:
        raise ValueError("generated definition must contain exactly one wheel dependency placeholder")

    config = definition.get("config")
    if not isinstance(config, dict) or config.get("type") != "object":
        raise ValueError("generated definition must contain an object config schema")
    properties = config.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("generated definition config properties must be an object")
    unsupported_types = set()
    for property_definition in properties.values():
        if not isinstance(property_definition, dict):
            raise ValueError("generated definition config properties must contain objects")
        property_type = property_definition.get("type")
        if property_type not in SUPPORTED_CONFIG_TYPES:
            unsupported_types.add(property_type)
    if unsupported_types:
        sorted_types = sorted(unsupported_types, key=str)
        raise ValueError(f"generated definition contains unsupported config types: {sorted_types}")
    required = config.get("required", [])
    if not isinstance(required, list) or not set(required).issubset(properties):
        raise ValueError("generated definition requires unknown config properties")

    serialized = json.dumps(definition)
    if serialized.count(WHEEL_DEPENDENCY_PLACEHOLDER) != 1:
        raise ValueError("wheel dependency placeholder must occur exactly once")
    return definition


def package_artifact(args: argparse.Namespace) -> Path:
    integration_dir = args.output_dir / args.integration_id
    shutil.rmtree(integration_dir, ignore_errors=True)
    integration_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as temporary_dir:
        generated_path = generate_definition(args, Path(temporary_dir))
        load_and_validate_definition(generated_path, args.main)
        yaml_path = integration_dir / "integration.yaml"
        shutil.copyfile(generated_path, yaml_path)

    source_path = integration_dir / "integration.py"
    wheel_path = integration_dir / args.wheel.name
    shutil.copyfile(args.source, source_path)
    shutil.copyfile(args.wheel, wheel_path)
    return integration_dir


def main() -> None:
    args = parse_args()
    validate_args(args)
    print(package_artifact(args))


if __name__ == "__main__":
    main()
