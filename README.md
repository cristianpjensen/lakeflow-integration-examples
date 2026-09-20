# Lakeflow Integrations

This repository contains official Databricks-authored Lakeflow integrations that users can install as starting points.
Each integration is an independently locked Python package with one generated catalog definition and one runnable Databricks Asset Bundle job.

## Available integrations

| Integration | Description |
| --- | --- |
| Echo | Prints a message a specified number of times. |

## Repository layout

```text
integrations/<integration-id>/     Python package, lockfile, and behavior tests
resources/<integration-id>.yml    Wheel artifact and runnable verification job
scripts/check-integration.sh      Local and CI verification
scripts/new-integration.sh        Integration scaffolding
databricks.yml                    Shared bundle configuration
```

Every integration has its own `uv.lock` and virtual environment so integrations can use incompatible dependencies without affecting each other.
The published `databricks-lakeflow-integrations` package provides the authoring interface and YAML generator.

## Verify an integration

Install Python 3.12 and [uv](https://docs.astral.sh/uv/), then run:

```bash
./scripts/check-integration.sh echo
```

The command installs locked dependencies, builds and installs the wheel, runs behavior tests, generates the catalog definition, and stages the complete artifact under `build/catalog/echo/`.

## Add an integration

Create the package and bundle boilerplate with:

```bash
./scripts/new-integration.sh my-integration "My Integration"
```

Then implement the integration, replace the generated test scaffold with behavior coverage, add runnable sample parameters to `resources/my-integration.yml`, and add the integration to the table above.
Verify the result with:

```bash
./scripts/check-integration.sh my-integration
```

CI discovers integration directories automatically, so adding an integration does not require editing shared CI or bundle configuration.

## Run the Echo job

Install Databricks CLI 1.17.0 or later and authenticate to a workspace where Lakeflow Integrations are enabled.
Then run:

```bash
databricks bundle validate
databricks bundle deploy
databricks bundle run echo_integration_test
```

The job succeeds after printing `Hello from Lakeflow Integrations` three times.

## Published artifacts

Pull requests build and test every integration and generate its catalog definition.
Pushes to `main` publish the complete catalog to the machine-managed `artifacts` branch:

```text
echo/
├── integration.py
├── integration.yaml
└── lakeflow_echo-0.0.1-py3-none-any.whl
```

Generated definitions contain `{{WHEEL_PATH}}` exactly once.
The Databricks installer replaces that value with the uploaded workspace wheel path.

Use the artifact commit SHA printed by CI in immutable frontend URLs:

```text
https://raw.githubusercontent.com/<owner>/<repo>/<artifact-commit-sha>/echo/integration.py
https://raw.githubusercontent.com/<owner>/<repo>/<artifact-commit-sha>/echo/integration.yaml
https://raw.githubusercontent.com/<owner>/<repo>/<artifact-commit-sha>/echo/lakeflow_echo-0.0.1-py3-none-any.whl
```

The repository must allow GitHub Actions to write repository contents before the publication job can create or update the `artifacts` branch.
