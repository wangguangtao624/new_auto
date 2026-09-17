# Version Governance Workflow

> Rules and task decomposition for release/version-governance work. Projects define their own tracks, version sources, and release scripts; this workflow defines the generic structure and checkpoints that AI must follow.

- **Scope**: Applies whenever the task involves **release planning**, **version bumps**, **tags**, **release notes**, **rollback baselines**, or **machine-readable version state**.
- **Authority**: This workflow is mandatory for release/version-governance tasks. Do not cut a release or mutate version state without reading the required files first.

---

## 1. When This Workflow Applies

Apply this workflow when any of the following is true:

- The user asks to release, publish, tag, bump a version, or cut a deliverable.
- The task touches version policy, release SOP, release notes, or rollback guidance.
- The task introduces or updates machine-readable version state such as `project/version-state.toml`.
- The task asks which version is currently being developed, frozen, or released.

Before changing release or version-governance assets, you must read this workflow and the project's version-governance files (see §2).

---

## 2. Mandatory Reading Before Version Work

1. **This file** — `core/workflows/version-governance-workflow.md`
2. **Project version policy** — `project/versioning.md`
3. **Project machine-readable state** — `project/version-state.toml` (if present)
4. **Project release SOP** — `project/sop/release.md`
5. **Track-specific release note** referenced by the version state or release SOP

If the project does not yet have structured version-governance files, do not improvise a one-off release flow. Propose adding the missing policy/state/SOP files first, then run the bootstrap gate:

1. `co version audit` — classify state as `missing`, `unconfigured`, `drift`, or `configured`
2. `co version bootstrap --track <name> --canonical <path> --version <x.y.z> --apply` — explicit first-time setup (dry-run without `--apply`)
3. `co lint --rule version-state` — confirm machine-readable state passes policy checks

Session start (`co session-init` / MCP `session_gate`) surfaces `unconfigured` or `drift` with remediation hints.

---

## 3. Three-Layer Model

Version governance should be organized into three layers:

| Layer | Role | Typical files |
|-------|------|---------------|
| **Policy layer** | Human-readable governance rules | `project/versioning.md` |
| **State layer** | Machine-readable version facts | `project/version-state.toml` |
| **Execution layer** | Step-by-step release actions and project helpers | `project/sop/release.md`, release notes, local scripts |

Rules:

- Policy explains the rules; it is not the execution state.
- State records the current facts; it must be machine-readable.
- Execution assets consume the state and apply the policy.

---

## 4. Required Version-State Concepts

When a project uses machine-readable version governance, the state file should answer at least:

- Which **track** is being changed
- Which file is the **canonical version source**
- What the latest **stable release** is
- What the current **working version** is
- What the current **status** is
- Which **release note** belongs to that track/version
- Which **release tag** should be created
- Which **rollback baseline** applies

Recommended minimum status values:

- `planning`
- `developing`
- `frozen`
- `released`
- `hotfix`

Important rule:

- Opening the next working version does not always require immediately bumping the canonical source.
- The state model may allow `current_release` and `working_version` to differ during planning/developing/frozen stages, if the project policy says so.
- **Drift guard (mandatory once code lands for the working version)**: as soon as the first runtime change for `working_version` is committed, the canonical version source MUST equal `working_version`. The project MUST ship (a) a local validation script that asserts `canonical_source.version == version_state.working_version`, and (b) a CI quality gate (e.g. `QG-0`) that runs the same assertion and fails the pipeline on drift. Reference the script and gate from `project/versioning.md` and from `project/known-issues.md` so the rule is discoverable across IDEs without depending on editor memory.

---

## 5. Required Task Decomposition

Break every release/version-governance task into these phases and execute in order.

| Phase | Action | Outcome |
|-------|--------|---------|
| **5.1 Confirm scope** | Identify the target track, release intent, and affected files. | Clear release/version-governance scope. |
| **5.2 Read policy/state/SOP** | Read `versioning.md`, `version-state.toml` (if present), `sop/release.md`, and relevant release notes. | Shared understanding of rules and current facts. |
| **5.3 Check state consistency** | Verify canonical source, current release, working version, release note path, tag format, and rollback baseline are coherent. | No silent drift before action. |
| **5.4 Plan the stage transition** | Decide whether the task is `Start Next Version`, `Freeze Version`, `Cut Release`, or `Open Next Iteration`. | Explicit stage change plan. |
| **5.5 Execute project-specific scripts** | Use the project's declared sync/build/package/deploy scripts from policy/SOP. | Execution stays in the project layer, not hardcoded in the generic layer. |
| **5.6 Verify and record** | Confirm runtime/package version output, finalize release note, update state/status docs. | Track state and deliverables are traceable. |

---

## 6. Standard Stage Language

Use the following stage language consistently:

1. **Start Next Version**
   - Select a track
   - Set a new working version
   - Initialize or point to a release-note draft
   - Move state to `planning` or `developing`
   - Prefer explicit helper commands such as `co start-next-version` when available

2. **Freeze Version**
   - Freeze release scope
   - Stop adding non-blocker changes
   - Finalize validation and risk notes
   - Move state to `frozen`
   - Prefer explicit helper commands such as `co prepare-release` when available

3. **Cut Release**
   - Bump canonical version source when required by policy
   - Sync derived files
   - Run project build/package/deploy flow
   - **`co release-docs check`** MUST pass for the target track (without `--allow-draft`) before state transition
   - Create the release tag
   - Move state to `released`
   - Prefer explicit helper commands such as `co cut-release` when available (`co cut-release --apply` runs the release-docs gate internally)

4. **Open Next Iteration**
   - Preserve the current stable release as baseline
   - Set a new working version
   - Initialize the next release-note draft
   - Move state back to `planning` or `developing`

---

## 7. Mandatory Constraints

These constraints are non-negotiable:

| Constraint | Rule |
|------------|------|
| **Track must be explicit** | Never assume "the whole repo has one version" unless the project policy says so. |
| **Single canonical version source per track** | Do not hand-edit derived files as the primary version source. |
| **Release note is an execution contract** | Release notes must capture scope, exclusions, validation, compatibility, and rollback guidance, not just a summary. |
| **Tags must be unambiguous** | Use project-declared tag format; multi-track projects should prefer track-prefixed tags. |
| **Rollback must be recorded** | Every release flow must define the rollback baseline or a migration note explaining why it is temporarily missing. |
| **Drift guard is mandatory** | Once the working version has any committed runtime change, the canonical version source must equal `working_version`; the project must enforce this with both a local script and a CI gate. |
| **Doc-refresh gate is mandatory before `Cut Release`** | Before tagging, run `co release-docs check` (without `--allow-draft`) for the target track and complete `core/workflows/release-doc-refresh-workflow.md`. A formal release that has not passed the doc-refresh gate is a release defect. |
| **Generic layer must stay generic** | Do not hardcode Cargo, Docker, Tauri, NSIS, SSH, or other project-specific tooling in protocol-level workflow logic. |

---

## 8. What Stays Generic vs Project-Specific

The generic protocol layer should provide:

- workflow guidance
- policy/state/SOP templates
- version-state schema guidance
- consistency checks
- helper orchestration boundaries

The project layer should keep:

- build/package/deploy commands
- artifact naming rules
- environment-specific validation
- infrastructure topology

---

## 9. Verification Checklist

Before marking release/version-governance work complete, confirm:

- [ ] The project policy/state/SOP were read before editing.
- [ ] The target track is explicit.
- [ ] Canonical source and derived files follow the documented ownership model.
- [ ] Release note matches the current track/version intent.
- [ ] Tag and rollback guidance are documented.
- [ ] Drift guard satisfied: canonical source version equals `working_version` (or working version has no committed runtime change yet); local validation script and CI gate both pass.
- [ ] `project/status.md` reflects the new governance or release state.

**For major (`x.0.0`) or minor milestone (`x.y.0`) releases, additionally confirm:**

- [ ] Full doc audit completed per `project/sop/release.md` · "Major / Minor Version Doc Audit" section.
- [ ] Every CLI command is documented in README and usage-guide.
- [ ] Options and examples in user-facing docs match current CLI behavior.
- [ ] Bundled copy synced and `co update-checksums` run.

---

## 11. Release Documentation Refresh (mandatory before `Cut Release`)

A release MUST NOT be cut until the public release/help documentation reflects the delivered behavior of the target track.

Delegate the doc-refresh execution to:

- engine rule: `core/workflows/release-doc-refresh-workflow.md`
- project SOP: `project/sop/release-doc-refresh.md`
- CLI gate: `co release-docs check [--track <name>]` (and `co release-docs refresh --mode audit|apply` for the agent prompt)

Minimum sequencing relative to §6 stages:

| Stage | Doc-refresh action |
|-------|--------------------|
| `developing` | Periodic `co release-docs check --allow-draft` to keep notes / indexes from drifting. |
| `frozen` | Run `co release-docs refresh --mode audit`; resolve any failures by editing public docs. |
| `Cut Release` | `co release-docs check` (without `--allow-draft`) MUST pass for the target track before the tag is created. |
| `released` | Update `project/status.md` and verify index docs link the new release; re-run the gate. |

Project-specific extensions (Admin Help manifest sync, generated sidebar configs, language packs, etc.) are declared via `[tracks.<name>.release_docs]` in `project/version-state.toml`; do not hardcode them in the engine layer.

---

## 10. Summary for AI

- **Before action**: Read `versioning.md`, `version-state.toml`, and `sop/release.md`.
- **During work**: Treat policy, state, and execution as separate layers.
- **When releasing**: Use explicit track + explicit stage language.
- **When automating**: Use explicit helper commands for state transitions; orchestrate project-declared scripts and do not replace them with protocol-specific assumptions.

*This file is a generic engine rule; project-specific release details belong in `project/`.*
