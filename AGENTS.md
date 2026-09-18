# Agent instructions

## Repository invariants

Keep each integration in its own package under `integrations/<integration-id>`.
Give each package exactly one `@integration` entry point so its wheel, source, and generated YAML form one installable catalog item.
Keep the matching runnable verification job under `resources/`.
Give each integration its own `uv.lock` and virtual environment so incompatible example dependencies stay isolated.
Add every integration to the CI matrix and DAB artifacts; the repository contract test enforces this wiring.

Use the published `databricks-lakeflow-integrations` package for the authoring API and YAML generator.
Invoke its generator as a dependency; keep generator implementation code outside this repository.

Treat `artifacts` as a machine-published branch.
Publish immutable outputs under `integrations-examples/<source-sha>/<integration-id>/`, and never edit generated branch contents manually.
Keep `integration.py`, `integration.yaml`, and the wheel in sync through `scripts/package_catalog_artifact.py`.
Keep `__DATABRICKS_CURATED_INTEGRATION_WHEEL_PATH__` in every generated YAML until the frontend installer substitutes the uploaded wheel path.
Use an artifact commit SHA, not the mutable `artifacts` branch name, in frontend URLs.

Pin Python packages in the integration's `pyproject.toml` and `uv.lock`.
Keep committed lockfile URLs on public PyPI so public GitHub runners can install them.
Pin GitHub Actions by full commit SHA.
Databricks-internal dependency downloads must use the approved package proxy.

## Verification

Run these checks from the repository root after changing an integration:

```bash
uv sync --project integrations/echo
uv build integrations/echo --project integrations/echo --wheel --out-dir dist --clear --no-create-gitignore
uv pip install --python integrations/echo/.venv/bin/python --reinstall --no-deps dist/lakeflow_echo-0.0.1-py3-none-any.whl
integrations/echo/.venv/bin/python -m unittest discover -s integrations/echo/tests
integrations/echo/.venv/bin/python scripts/package_catalog_artifact.py --integration-id echo --package-module lakeflow_echo --main lakeflow_echo.integration.echo --source integrations/echo/src/lakeflow_echo/integration.py --wheel dist/lakeflow_echo-0.0.1-py3-none-any.whl --environment-key echo_environment --source-sha local --output-dir build/catalog
python -m unittest discover -s tests
databricks bundle validate
```

Add positive, boundary, and invalid-input coverage for behavior changes.
Confirm generated YAML contains the wheel placeholder exactly once; the frontend installer replaces it with the uploaded workspace wheel path.
Confirm publication tests reject byte changes beneath an existing source SHA and preserve both sides of a non-fast-forward race.

## Documentation

Update `README.md` when the layout, build commands, artifact contract, or deployment flow changes.
Put each full Markdown sentence on its own line.
