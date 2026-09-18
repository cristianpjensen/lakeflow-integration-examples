# Lakeflow Integration Examples

This repository contains small, runnable examples for Lakeflow Jobs integrations.
Each example is a Databricks Asset Bundle resource, a Python wheel, and generated integration YAML that the Databricks frontend can install into a user's workspace.

The repository starts with Echo, which accepts a message and a repeat count and prints the message that many times.

## Layout

```text
.
├── integrations/echo/              # Echo package, lock, source, and tests
├── resources/echo.job.yml          # Runnable Echo verification job
├── scripts/                         # Catalog packaging and CI bundle validation
├── databricks.yml                   # Bundle definition
├── tests/                            # Repository wiring checks
└── .github/workflows/ci.yml          # Verification and artifact publication
```

Each integration owns its `pyproject.toml`, `uv.lock`, and virtual environment so future examples can use incompatible dependencies without destabilizing unrelated wheels.
The YAML generator comes from the pinned `databricks-lakeflow-integrations` package and is not vendored here.

## Develop locally

Install Python 3.12, [uv](https://docs.astral.sh/uv/), and Databricks CLI 1.7.0 or later.
Databricks employees must route package downloads through the approved internal package proxy.
The proxy may rewrite registry URLs in a local lockfile; restore those changes before committing because public CI uses the public PyPI URLs.

Run the local equivalents of the CI checks:

```bash
uv sync --project integrations/echo
uv build integrations/echo --project integrations/echo --wheel --out-dir dist --clear --no-build-isolation --no-create-gitignore
uv pip install --python integrations/echo/.venv/bin/python --reinstall --no-deps dist/lakeflow_echo-0.0.1-py3-none-any.whl
integrations/echo/.venv/bin/python -m unittest discover -s integrations/echo/tests
integrations/echo/.venv/bin/python scripts/package_catalog_artifact.py \
  --integration-id echo \
  --package-module lakeflow_echo \
  --main lakeflow_echo.integration.echo \
  --source integrations/echo/src/lakeflow_echo/integration.py \
  --wheel dist/lakeflow_echo-0.0.1-py3-none-any.whl \
  --environment-key echo_environment \
  --source-sha local \
  --output-dir build/catalog
python -m unittest discover -s tests
databricks bundle validate
```

The packaging command generates and validates `build/catalog/integrations-examples/local/echo/integration.yaml` and places it beside the source and wheel.
Both catalog packaging and the DAB artifact build put `__DATABRICKS_CURATED_INTEGRATION_WHEEL_PATH__` in generated YAML.
The frontend installer replaces that value with the workspace path where it uploads the wheel.

## Deploy the bundle

Authenticate the Databricks CLI to a workspace where Lakeflow Integrations are enabled, then run:

```bash
databricks bundle validate
databricks bundle deploy
databricks bundle run echo_integration_test
```

Deployment builds the Echo wheel and integration YAML, uploads them as bundle artifacts, and creates the Echo verification job.
The job succeeds after printing `Hello from Lakeflow Integrations` three times.

## Artifact publication

Pull requests and pushes to `main` install and test each built wheel, generate the YAML, validate the frontend artifact contract, and validate the bundle.
Pushes to `main` also publish immutable artifacts to the `artifacts` branch under this layout:

```text
integrations-examples/<source-sha>/
└── echo/
    ├── integration.py
    ├── integration.yaml
    ├── lakeflow_echo-0.0.1-py3-none-any.whl
    └── SHA256SUMS
```

The workflow creates the `artifacts` branch on its first successful run.
Concurrent publishers retry against the latest branch head for up to eight minutes.
An identical rerun is a no-op, while a byte-different rerun for an existing SHA fails instead of changing pinned URLs.
The repository must allow GitHub Actions to write repository contents.
The repository must be public before the frontend can fetch these URLs without GitHub credentials.

After publication, use the artifact commit SHA printed by the workflow in the frontend URLs:

```text
https://raw.githubusercontent.com/<owner>/<repo>/<artifact-commit-sha>/integrations-examples/<source-sha>/echo/integration.py
https://raw.githubusercontent.com/<owner>/<repo>/<artifact-commit-sha>/integrations-examples/<source-sha>/echo/lakeflow_echo-0.0.1-py3-none-any.whl
https://raw.githubusercontent.com/<owner>/<repo>/<artifact-commit-sha>/integrations-examples/<source-sha>/echo/integration.yaml
```

Pin both SHAs in frontend definitions so branch changes cannot alter a reviewed artifact set.
