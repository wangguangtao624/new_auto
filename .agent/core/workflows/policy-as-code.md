# Policy as Code (OPA / Rego / Conftest)

cokodo-agent ships reusable Rego policy packs that formalize the
recurring "release SOP consistency" checks (version-state vs. release
notes vs. tags vs. status hygiene). Policies live under
`cokodo_agent/bundled/agent/policies/<kind>/*.rego` and are evaluated by
[Conftest](https://www.conftest.dev/).

## Why

Manual / scripted SOP checks (PowerShell-only release scripts, ad-hoc
README rules) tend to drift and silently pass. Encoding the rules in
Rego gives us:

- a single, version-controlled spec for every "release-blocker" rule,
- the same rules runnable by humans (`co policy check`), CI
  (`conftest test`), and pre-commit hooks,
- clear, machine-readable failure messages.

## Available packs

| Name      | What it checks |
|-----------|----------------|
| `release` | `version-state.toml` invariants (status enum, tag format `vX.Y.Z` or `<track>/vX.Y.Z`, prefixed tag required when multiple tracks are enabled, `rollback_tag` when released, release-note existence and required topics: compatibility / rollback / validation), plus `status.md` "Recently Completed" cap. |

List at any time:

```bash
co policy list
```

## Local usage

```bash
# Inspect the bundled policy directory.
co policy show release

# Dump the JSON input that policies will see.
co policy data release

# One-shot: collect + run conftest.
co policy check release
```

`co policy check` exits with:

- `0` — all rules pass
- `1` — at least one `deny` matched
- `2` — conftest is not installed (data collection still works via
  `co policy data`)

## CI usage

The `show` / `data` commands are intentionally side-effect-free so any
CI can wire them up without depending on cokodo-agent's `check`
wrapper:

```bash
POLICY_DIR=$(co policy show release)
co policy data release | conftest test --policy "$POLICY_DIR" \
    --namespace release --parser json -
```

## Pre-commit integration

cokodo-agent ships a ready-to-use Git hook at
`templates/hooks/pre-commit.policy` (synced into `.agent/templates/hooks/`
when you run `co scaffold`) that runs `co policy check release` and
blocks commits with violations.

### Agent-driven flow (recommended)

The AI agent should drive bootstrap end-to-end via CLI — no manual `cp`
required:

```bash
# 1. Verify conftest is installed; offer install commands per platform.
#    --install attempts the first detected package manager
#    (winget / scoop / choco / brew / apt-get / dnf / pacman).
co policy doctor          # diagnose
co policy doctor --install  # diagnose + auto-install when possible

# 2. Install the policy hook into .git/hooks/pre-commit.
#    Idempotent; --force overwrites with a timestamped backup.
co policy install-hook
```

`co policy install-hook` refuses to run when the project is not a git
repository (run `git init` first), is a no-op when the bundled hook is
already installed verbatim, and warns before overwriting a divergent
hook unless `--force` is passed.

`co policy doctor` exits with:

| Code | Meaning |
|------|---------|
| 0 | conftest detected (or `--install` succeeded) |
| 2 | conftest missing and not installed |
| other | propagated from the package manager when `--install` fails |

### Manual fallback (when CLI is unavailable)

POSIX:

```sh
cp .agent/templates/hooks/pre-commit.policy .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Windows / PowerShell:

```powershell
Copy-Item .agent\templates\hooks\pre-commit.policy .git\hooks\pre-commit
```

### Bypass

The hook treats conftest absence as a warning (not a block) so
contributors without conftest installed can still commit. CI is expected
to enforce the gate strictly.

- One commit (emergency): `git commit --no-verify`
- Current shell: `export COKODO_SKIP_POLICY=1`

## Built-in enforcement points

cokodo-agent automatically evaluates bundled packs at two control points:

| Command | Behaviour | Bypass |
|---------|-----------|--------|
| `co lint` | Adds a `policy` rule that runs every bundled pack. conftest absence → SKIP (does not fail). | `co lint --rule <other>` |
| `co prepare-release --apply` | Runs the `release` pack before freezing the track; violations abort the freeze. conftest absence → **exit 2** (fail-closed). | `--allow-no-policy --reason "..."` (journal.d) or `--skip-policy` |

## Authoring

- Each pack is a directory of `.rego` files. The package name (`package
  release`) must match the namespace passed to conftest.
- Use `deny[msg]` rules. Conftest will fail the run when any `deny`
  matches.
- Document the input schema in a METADATA block at the top of each
  file. The Python-side collector
  (`cokodo_agent.policies.collect_data`) is the source of truth for
  that schema.
- Add tests in `tests/test_policies.py` whenever you change the
  collector or add a pack.
