# CI/CD Integration Templates

> Templates for integrating protocol checks into CI pipelines.

---

## Available Templates

| Template | Purpose |
|----------|---------|
| `github-actions.template.yml` | GitHub Actions workflow |
| `qg0-version-drift.template.yml` | QG-0 Drift Guard job (verify-versions + lint) |
| `pre-commit-config.template.yaml` | Pre-commit hooks |

---

## GitHub Actions Setup

```bash
cp $AGENT_DIR/adapters/ci/github-actions.template.yml .github/workflows/ci.yml
```

---

## Version Governance Release Gate Example

When a project uses `project/version-state.toml`, keep release-state checks separate from the project build/deploy job.

Copy the QG-0 template for CI:

```bash
cp $AGENT_DIR/adapters/ci/qg0-version-drift.template.yml .github/workflows/qg0-version-drift.yml
cp $AGENT_DIR/templates/scripts/verify-versions.py .agent/scripts/verify-versions.py
```

Example GitHub Actions job:

```yaml
jobs:
  version-governance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install cokodo-agent
        run: pip install cokodo-agent
      - name: Validate structured release state
        run: co lint --rule version-state
      - name: Drift Guard
        run: python .agent/scripts/verify-versions.py
      - name: Preview release freeze
        run: co prepare-release --track primary
      - name: Preview release finalize
        run: co cut-release --track primary
```

Recommended split:

- PR gate: `co lint --rule version-state`
- release candidate gate: preview `co prepare-release`
- final release job: run project-local version sync/build/deploy/tag flow first, then `co cut-release --track <name> --apply`

---

## Pre-commit Setup

```bash
cp $AGENT_DIR/adapters/ci/pre-commit-config.template.yaml .pre-commit-config.yaml
pip install pre-commit
pre-commit install
```

---

*Adapt $AGENT_DIR to your actual directory name*
