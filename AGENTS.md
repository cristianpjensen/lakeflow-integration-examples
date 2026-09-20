# Agent instructions

## Repository invariants

Keep each integration in its own package under `integrations/<integration-id>`.
Use lowercase kebab-case integration IDs that begin with a letter.
Name the Python package `lakeflow_<integration_id>` with hyphens converted to underscores.
Give each package exactly one `@integration` entry point in `integration.py`.
Keep behavior tests under the integration package and infrastructure tests out of them.
Give each integration its own `uv.lock` and virtual environment.

Keep the matching wheel artifact and runnable verification job together in `resources/<integration-id>.yml`.
The root bundle and CI discover integrations through globs; do not add per-integration entries to shared configuration.
Build wheels through `scripts/build-integration.sh` so local checks and bundle deployment use the same locked toolchain.

Use the published `databricks-lakeflow-integrations` package for the authoring interface and YAML generator.
Keep generator implementation code outside this repository.
Pin Python packages in each integration's `pyproject.toml` and `uv.lock`.
Keep committed lockfile URLs on public PyPI so public GitHub runners can install them.
Databricks-internal dependency downloads must use the approved package proxy.
Pin GitHub Actions by full commit SHA.

Treat `artifacts` as a machine-published branch.
Publish the latest complete artifact set under `<integration-id>/`.
Keep `integration.py`, `integration.yaml`, and the wheel in sync.
Keep `{{WHEEL_PATH}}` exactly once in every generated definition.
Use an artifact commit SHA, not the mutable branch name, in frontend URLs.

## Development

Create integration boilerplate with:

```bash
./scripts/new-integration.sh <integration-id> "<Display name>"
```

Verify an integration from the repository root with:

```bash
./scripts/check-integration.sh <integration-id>
```

The verification command must build and test the installed wheel, generate exactly one definition, validate its runnable resource, and stage exactly three catalog files.
Add positive, boundary, and invalid-input coverage for behavior changes.
Run `databricks bundle validate` while authenticated after changing bundle configuration.

## Documentation

Update `README.md` when the layout, build command, artifact contract, or deployment flow changes.
Put each full Markdown sentence on its own line.
