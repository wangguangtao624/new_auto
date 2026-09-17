# Release Documentation Refresh Workflow

> Generic engine rule for refreshing public release/help documentation **before** a release is cut. This workflow is IDE-neutral. Cokodo agents, CLI wrappers (`co release-docs ...`), MCP tools, Cursor commands, and human operators all delegate to this rule and to the project SOP at `project/sop/release-doc-refresh.md`.

- **Scope**: Applies whenever the task is to publish, release, or finalize a track and the public-facing documentation must reflect the delivered behavior before the tag is created.
- **Authority**: This workflow is mandatory before `Cut Release` (see `version-governance-workflow.md` §6 / §11). Skipping it is a release defect.

---

## 1. When This Workflow Applies

Apply when any of the following is true:

- The user asks to release, publish, tag, or cut a deliverable for any track.
- A working version is moving from `developing` / `frozen` toward `released`.
- A previously released track has new user-visible behavior since its last note.
- A scheduled audit of public docs is requested (e.g. weekly drift check).

Do **not** treat internal design notes, research reports, or SDD task files as substitutes for public release/help documentation.

---

## 2. Mandatory Reading Before Doc Refresh

1. **This file** — `core/workflows/release-doc-refresh-workflow.md`
2. **Project doc-refresh SOP** — `project/sop/release-doc-refresh.md`
3. **Version policy + state** — `project/versioning.md`, `project/version-state.toml`
4. **Release SOP** — `project/sop/release.md`
5. **Per-track release note** — the file referenced by `tracks.<name>.release_note` in `version-state.toml`
6. **Active SDD task file** — if `project/changes/.active` exists
7. **Project status** — `project/status.md` for current stage

For UI/admin-visible changes, also read `core/workflows/ui-design-workflow.md` and the relevant UI/spec files. For deployment-visible changes, also read `project/deploy.md` and `project/sop/deployment-log-governance.md` (when present).

---

## 3. Two Modes

| Mode | Side effects | Purpose |
|------|--------------|---------|
| `audit` | **Read-only** | Report missing notes, placeholders, stale index links, version drift. Used as a release gate and as a health check. |
| `apply` | **Edits docs** | Update release notes, public help/guide, indexes, generated assets. Re-runs deterministic checks. |

The deterministic gate is provided by `co release-docs check` (CLI) and is also exposed as the `audit` mode of `co release-docs refresh`. **Passing the deterministic gate does not prove prose completeness** — the agent owns content review.

---

## 4. Required Task Decomposition

Execute in order:

| Phase | Action | Outcome |
|-------|--------|---------|
| **4.1 Confirm scope** | Identify target track(s), version(s), and audit-vs-apply intent. | Explicit refresh scope. |
| **4.2 Read state + SOP** | Load version-state, release SOP, doc-refresh SOP, current release note. | Shared facts for all subsequent edits. |
| **4.3 Run audit** | `co release-docs check [--track ...]` → list missing files, placeholders, stale links. | Mechanical gap list. |
| **4.4 Apply edits** (apply mode only) | Update release note, help/guide, indexes, generated assets per project SOP. | Public docs match delivered behavior. |
| **4.5 Re-run audit** | `co release-docs check` (without `--allow-draft` for a formal release). | Gate is green. |
| **4.6 Update status** | Refresh `project/status.md`; record the doc-refresh outcome. | Traceable handoff. |

Apply mode must be followed by audit re-run before declaring the workflow complete.

---

## 5. Mandatory Constraints

These are non-negotiable for any release-doc work:

| Constraint | Rule |
|------------|------|
| **Track must be explicit** | Every action declares the target track from `version-state.toml`. |
| **Single source of truth for versions** | All public docs derive their version strings from `version-state.toml`. Hand-edited drift is a defect. |
| **Release notes are handoff contracts** | They must describe scope, exclusions, artifacts, validation, compatibility, risks, rollback, traceability. |
| **No placeholders for formal releases** | `<VERSION>`, `<X.Y.Z>`, `x.y.z`, `<release-id>`, `TODO` are always rejected. `TBD` / `Draft` / `<...>` URLs are rejected unless `--allow-draft` is set (development checkpoints only). |
| **Public docs ≠ design notes** | Internal design or research files cannot replace user-facing help / release-note prose. |
| **Generic layer stays generic** | Do not hardcode product-specific assets (Admin Help, NSIS, manifest formats) in the engine layer. Project-specific files are declared via the project SOP and `[tracks.<name>.release_docs]` in `version-state.toml`. |
| **`--allow-draft` is not a release-shipping flag** | Use only for in-flight development snapshots; a formal release must pass without it. |

---

## 6. Standard Agent Prompt

When a wrapper (Cursor command, MCP tool, CI job) needs to invoke an agent for this workflow, use exactly:

```text
Run Release Documentation Refresh.

Inputs:
- track: <track-name> | all
- version: <x.y.z> or read from .agent/project/version-state.toml
- mode: audit | apply

Follow .agent/project/sop/release-doc-refresh.md and
.agent/core/workflows/release-doc-refresh-workflow.md.
Use .agent/project/status.md, version-state.toml, the active change tasks (if any),
release notes, and git diff to determine what the public docs must say before release.
Do not rely on IDE-specific commands.
```

CLI shorthand (when `co release-docs` is available in the project's installed Cokodo runtime):

```bash
co release-docs refresh --track <track> --mode audit
co release-docs refresh --track <track> --mode apply
co release-docs check    --track <track> [--allow-draft]
```

---

## 7. Verification Checklist

Before marking the doc refresh complete, confirm:

- [ ] Per-track release note exists at the path declared by `version-state.toml`.
- [ ] Release notes contain all required sections (scope, exclusions, artifacts, validation, compatibility, risks, rollback, traceability).
- [ ] No placeholders remain (and for formal releases, `--allow-draft` is not used).
- [ ] Index docs (declared via `[tracks.<name>.release_docs] index_files`) link the current per-track release note.
- [ ] Version strings in indexes match `current_release` / `working_version` for each enabled track.
- [ ] Project-specific generated assets (when declared) are refreshed.
- [ ] `co release-docs check` passes for every enabled track.
- [ ] `project/status.md` records the refresh result and version state.

---

## 8. Relationship to Other Workflows

- **Pre-condition for `Cut Release`** (`version-governance-workflow.md` §6.3 / §11): a release that has not passed `release-docs check` without `--allow-draft` MUST NOT be cut.
- **Companion to drift guard** (`version-governance-workflow.md` §4): the drift guard ensures the canonical version source equals `working_version`; this workflow ensures the public documentation describes that working/released version truthfully.
- **Wraps `release_planner` output**: `co release draft-note` produces a release-note skeleton; this workflow makes it production-ready.

---

## 9. Summary for AI

- **Before action**: Read this file, the project doc-refresh SOP, version-state, and release SOP.
- **Audit first**: Always run `co release-docs check` before editing.
- **Apply with discipline**: Edits must be track-explicit, version-state-derived, and free of placeholders for formal releases.
- **Verify last**: Re-run the gate and update `project/status.md`.

*This file is a generic engine rule; project-specific doc paths, generated assets, and helper scripts belong in `project/`.*
