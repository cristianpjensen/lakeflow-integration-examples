#!/usr/bin/env bash
set -euo pipefail

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
readonly project_dir="$repository_root/integrations/$integration_id"
readonly lockfile_path="$project_dir/uv.lock"
readonly output_dir="$project_dir/dist"

[[ -f "$project_dir/pyproject.toml" ]] || fail "Integration does not exist: $integration_id"
[[ -f "$lockfile_path" ]] || fail "Integration lockfile is missing: $lockfile_path"

if uv lock --project "$project_dir" --check --offline >/dev/null 2>&1; then
  uv sync --project "$project_dir" --locked --no-install-project
else
  # A configured mirror changes lockfile URLs, so compare normalized content and restore it.
  temporary_lockfile="$(mktemp "${TMPDIR:-/tmp}/lakeflow-uv-lock.XXXXXX")"
  normalized_lockfile="$(mktemp "${TMPDIR:-/tmp}/lakeflow-uv-lock.XXXXXX")"
  cp -- "$lockfile_path" "$temporary_lockfile"
  restore_lockfile() {
    cp -- "$temporary_lockfile" "$lockfile_path"
    rm -f -- "$temporary_lockfile" "$normalized_lockfile"
  }
  trap restore_lockfile EXIT

  uv lock --project "$project_dir"
  sed \
    -e 's#https://pypi-proxy.cloud.databricks.com/simple#https://pypi.org/simple#g' \
    -e 's#https://pypi-proxy.cloud.databricks.com/packages#https://files.pythonhosted.org/packages#g' \
    "$lockfile_path" > "$normalized_lockfile"
  if ! cmp -s "$temporary_lockfile" "$normalized_lockfile"; then
    fail "Integration lockfile is out of date: $lockfile_path"
  fi
  uv sync --project "$project_dir" --locked --no-install-project

  restore_lockfile
  trap - EXIT
fi

uv build "$project_dir" \
  --project "$project_dir" \
  --wheel \
  --out-dir "$output_dir" \
  --clear \
  --no-build-isolation \
  --no-create-gitignore
