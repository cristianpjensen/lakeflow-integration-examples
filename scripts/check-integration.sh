#!/usr/bin/env bash
set -euo pipefail

readonly wheel_placeholder="{{WHEEL_PATH}}"

usage() {
  echo "Usage: $0 <integration-id>" >&2
  exit 2
}

fail() {
  echo "$1" >&2
  exit 1
}

if (( $# != 1 )); then
  usage
fi

readonly integration_id="$1"
if [[ ! "$integration_id" =~ ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ ]]; then
  fail "Integration ID must be lowercase kebab-case and begin with a letter: $integration_id"
fi

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly repository_root="$(cd -- "$script_dir/.." && pwd)"
readonly snake_id="${integration_id//-/_}"
readonly package_module="lakeflow_${snake_id}"
readonly environment_key="${snake_id}_environment"
readonly project_dir="$repository_root/integrations/$integration_id"
readonly source_path="$project_dir/src/$package_module/integration.py"
readonly lockfile_path="$project_dir/uv.lock"
readonly resource_path="$repository_root/resources/$integration_id.yml"
readonly artifact_dir="$repository_root/build/catalog/$integration_id"

[[ -f "$project_dir/pyproject.toml" ]] || fail "Integration does not exist: $integration_id"
[[ -f "$source_path" ]] || fail "Integration source is missing: $source_path"
[[ -f "$lockfile_path" ]] || fail "Integration lockfile is missing: $lockfile_path"
[[ -f "$resource_path" ]] || fail "Integration resource is missing: $resource_path"

cd -- "$repository_root"
rm -rf -- "$artifact_dir"
mkdir -p -- "$artifact_dir"
"$script_dir/build-integration.sh" "$integration_id"

shopt -s nullglob
wheel_paths=("$project_dir/dist"/*.whl)
if (( ${#wheel_paths[@]} != 1 )); then
  fail "Expected exactly one wheel, found ${#wheel_paths[@]}"
fi

readonly python_path="$project_dir/.venv/bin/python"
uv pip install --python "$python_path" --reinstall --no-deps "${wheel_paths[0]}"
"$python_path" -m unittest discover -s "$project_dir/tests"
cp -- "${wheel_paths[0]}" "$artifact_dir/"

"$python_path" -m databricks.lakeflow.integrations.generate \
  --package-module "$package_module" \
  --output-dir "$artifact_dir" \
  --environment-version 5 \
  --environment-key "$environment_key" \
  --dependency "$wheel_placeholder"

definition_paths=("$artifact_dir"/*.yaml "$artifact_dir"/*.yml)
if (( ${#definition_paths[@]} != 1 )); then
  fail "Expected exactly one generated definition, found ${#definition_paths[@]}"
fi

readonly definition_path="$artifact_dir/integration.yaml"
if [[ "${definition_paths[0]}" != "$definition_path" ]]; then
  mv -- "${definition_paths[0]}" "$definition_path"
fi
cp -- "$source_path" "$artifact_dir/integration.py"

placeholder_count="$(
  "$python_path" -c \
    'from pathlib import Path; import sys; print(Path(sys.argv[1]).read_text().count(sys.argv[2]))' \
    "$definition_path" \
    "$wheel_placeholder"
)"
if (( placeholder_count != 1 )); then
  fail "Generated definition must contain the wheel placeholder exactly once"
fi

artifact_paths=("$artifact_dir"/*)
if (( ${#artifact_paths[@]} != 3 )); then
  fail "Expected exactly three catalog files, found ${#artifact_paths[@]}"
fi

"$python_path" - "$definition_path" "$resource_path" "$integration_id" <<'PY'
import json
import sys
from pathlib import Path

import yaml


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


definition_path = Path(sys.argv[1])
resource_path = Path(sys.argv[2])
integration_id = sys.argv[3]
snake_id = integration_id.replace("-", "_")

definition = json.loads(definition_path.read_text())
main = definition.get("main")
expected_main_module = f"lakeflow_{snake_id}.integration"
require(isinstance(main, str) and main.rpartition(".")[0] == expected_main_module, f"Entry point must be in {expected_main_module}")
try:
    resource = yaml.safe_load(resource_path.read_text())
except yaml.YAMLError as error:
    raise SystemExit(f"Invalid resource YAML: {resource_path}: {error}") from error

require(isinstance(resource, dict), f"Resource must be a mapping: {resource_path}")

artifact_key = f"{snake_id}_wheel"
artifacts = resource.get("artifacts", {})
require(isinstance(artifacts, dict) and artifact_key in artifacts, f"Missing artifact: {artifact_key}")
artifact = artifacts[artifact_key]
require(isinstance(artifact, dict), f"Artifact must be a mapping: {artifact_key}")
expected_artifact = {
    "type": "whl",
    "path": f"../integrations/{integration_id}",
    "build": f"../../scripts/build-integration.sh {integration_id}",
}
for key, expected in expected_artifact.items():
    require(artifact.get(key) == expected, f"Artifact {artifact_key}.{key} must be {expected!r}")

job_key = f"{snake_id}_integration_test"
resources = resource.get("resources", {})
require(isinstance(resources, dict), "Resources must be a mapping")
jobs = resources.get("jobs", {})
require(isinstance(jobs, dict) and job_key in jobs, f"Missing job: {job_key}")
job = jobs[job_key]
require(isinstance(job, dict), f"Job must be a mapping: {job_key}")
tasks = job.get("tasks", [])
require(isinstance(tasks, list), f"Job tasks must be a list: {job_key}")
matching_tasks = [
    task
    for task in tasks
    if isinstance(task, dict)
    and isinstance(task.get("python_operator_task"), dict)
    and task["python_operator_task"].get("main") == definition["main"]
]
require(len(matching_tasks) == 1, f"Job must have exactly one task for {definition['main']}")
task = matching_tasks[0]
require(task.get("task_key") == snake_id, f"Task key must be {snake_id}")

environment = definition["environment"]
require(task.get("environment_key") == environment["environment_key"], "Task environment key is out of date")
parameters = task["python_operator_task"].get("parameters", [])
require(isinstance(parameters, list), "Task parameters must be a list")
parameter_names = [parameter.get("name") for parameter in parameters if isinstance(parameter, dict)]
require(
    len(parameter_names) == len(parameters) and all(isinstance(name, str) for name in parameter_names),
    "Every task parameter must be a mapping with a string name",
)
require(len(parameter_names) == len(set(parameter_names)), "Task parameter names must be unique")
properties = set(definition["config"].get("properties", {}))
required = set(definition["config"].get("required", []))
require(required <= set(parameter_names) <= properties, "Task parameters do not match the generated definition")

environments = job.get("environments", [])
require(isinstance(environments, list), f"Job environments must be a list: {job_key}")
matching_environments = [
    item
    for item in environments
    if isinstance(item, dict) and item.get("environment_key") == environment["environment_key"]
]
require(len(matching_environments) == 1, f"Job must define environment {environment['environment_key']}")
spec = matching_environments[0].get("spec", {})
require(str(spec.get("environment_version")) == str(environment["environment_version"]), "Environment version is out of date")
wheel_path = f"../integrations/{integration_id}/dist/*.whl"
require(spec.get("dependencies") == [wheel_path], f"Environment dependencies must contain only {wheel_path}")
PY

echo "Verified $integration_id and built $artifact_dir"
