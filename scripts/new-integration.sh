#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <integration-id> <display-name>" >&2
  exit 2
}

fail() {
  echo "$1" >&2
  exit 1
}

if (( $# != 2 )); then
  usage
fi

readonly integration_id="$1"
readonly display_name="$2"
if [[ ! "$integration_id" =~ ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ ]]; then
  fail "Integration ID must be lowercase kebab-case and begin with a letter: $integration_id"
fi
if [[ -z "$display_name" || "$display_name" =~ [[:cntrl:]] ]]; then
  fail "Display name must be a non-empty single line"
fi

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly repository_root="$(cd -- "$script_dir/.." && pwd)"
readonly snake_id="${integration_id//-/_}"
readonly package_module="lakeflow_${snake_id}"
readonly function_name="integration_${snake_id}"
readonly environment_key="${snake_id}_environment"
readonly project_dir="$repository_root/integrations/$integration_id"
readonly resource_path="$repository_root/resources/$integration_id.yml"

[[ ! -e "$project_dir" ]] || fail "Integration already exists: $project_dir"
[[ ! -e "$resource_path" ]] || fail "Resource already exists: $resource_path"

escaped_display_name="${display_name//\\/\\\\}"
escaped_display_name="${escaped_display_name//\"/\\\"}"
readonly escaped_display_name

project_created=false
resource_created=false
cleanup() {
  if [[ "$project_created" == true ]]; then
    rm -rf -- "$project_dir"
  fi
  if [[ "$resource_created" == true ]]; then
    rm -f -- "$resource_path"
  fi
}
trap cleanup EXIT

if ! mkdir -- "$project_dir"; then
  fail "Could not create integration directory: $project_dir"
fi
project_created=true
mkdir -p -- "$project_dir/src/$package_module" "$project_dir/tests"

cat > "$project_dir/pyproject.toml" <<EOF
[project]
name = "lakeflow-$integration_id"
version = "0.0.1"
description = "A Lakeflow integration for $escaped_display_name."
requires-python = ">=3.12,<3.13"
dependencies = [
    "databricks-lakeflow-integrations==0.0.1",
]

[dependency-groups]
dev = [
    "hatchling==1.32.0",
    "pyyaml==6.0.3",
]

[tool.hatch.build.targets.wheel]
packages = ["src/$package_module"]

[build-system]
requires = ["hatchling==1.32.0"]
build-backend = "hatchling.build"
EOF

cat > "$project_dir/src/$package_module/integration.py" <<EOF
from databricks.lakeflow.integrations import integration


@integration(display_name="$escaped_display_name")
def $function_name() -> None:
    raise NotImplementedError("Implement $escaped_display_name")
EOF

cat > "$project_dir/tests/test_integration.py" <<EOF
import unittest

from $package_module.integration import $function_name


class IntegrationTest(unittest.TestCase):
    def test_behavior(self) -> None:
        $function_name()
        self.fail("Replace this scaffold with observable behavior assertions")


if __name__ == "__main__":
    unittest.main()
EOF

if ! (set -o noclobber; : > "$resource_path") 2>/dev/null; then
  fail "Could not create integration resource: $resource_path"
fi
resource_created=true
cat > "$resource_path" <<EOF
artifacts:
  ${snake_id}_wheel:
    type: whl
    path: ../integrations/$integration_id
    build: ../../scripts/build-integration.sh $integration_id

resources:
  jobs:
    ${snake_id}_integration_test:
      name: "[example] $escaped_display_name integration"
      tasks:
        - task_key: $snake_id
          environment_key: $environment_key
          python_operator_task:
            main: $package_module.integration.$function_name
      environments:
        - environment_key: $environment_key
          spec:
            environment_version: "5"
            dependencies:
              - ../integrations/$integration_id/dist/*.whl
EOF

python3 -c \
  'from pathlib import Path; import sys; compile(Path(sys.argv[1]).read_text(), sys.argv[1], "exec")' \
  "$project_dir/src/$package_module/integration.py"
python3 -c \
  'from pathlib import Path; import sys; compile(Path(sys.argv[1]).read_text(), sys.argv[1], "exec")' \
  "$project_dir/tests/test_integration.py"

uv lock --project "$project_dir"

# Public runners cannot access Databricks's package mirror.
lockfile_contents="$(<"$project_dir/uv.lock")"
lockfile_contents="${lockfile_contents//https:\/\/pypi-proxy.cloud.databricks.com\/simple/https:\/\/pypi.org\/simple}"
lockfile_contents="${lockfile_contents//https:\/\/pypi-proxy.cloud.databricks.com\/packages/https:\/\/files.pythonhosted.org\/packages}"
printf '%s\n' "$lockfile_contents" > "$project_dir/uv.lock"

trap - EXIT

echo "Created $integration_id."
echo "Implement its behavior, tests, and runnable job parameters, then update README.md."
echo "Then run: ./scripts/check-integration.sh $integration_id"
