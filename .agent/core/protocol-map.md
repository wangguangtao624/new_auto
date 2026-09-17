# Protocol map (on-demand reference)

> **Load when**: you need to write or update a project artifact (plan, research report,
> review, spec, event, journal fragment), or a task involves another project on this machine.
> **Do not** inline this file into always-on adapter output — it is reference material and
> is loaded on demand by design. See `core/workflows/token-budget.md`.

---

## 1. Project directory roles (`project/`)

| Directory / file | Role |
|------------------|------|
| `status.md` | Session state — read first every session; update at checkpoints (product PRs: journal.d only). |
| `AGENT-GIT-PR-WORKFLOW.md` | Git/PR/collaboration entry — three hard rules + read order. |
| `context.md` | Business context and project name. |
| `tech-stack.md` | Stack and tooling decisions. |
| `commands.md` | Build/test/run commands. |
| `deploy.md` | Deployment and infra. |
| `known-issues.md` | Pitfalls and workarounds. |
| `sop/` | Release / debug / git SOPs. |
| `changes/` | SDD change units (`co change`); active scope in `tasks.md`. |
| `events/` | Local linkage events — machine-discoverable cross-project change notices. Index: `events/events-index.md`; MCP resource `agent://events-index`. |
| `plan/` | Canonical plans — shareable roadmaps, milestones, approved execution plans. Index: `plan/plan-index.md`; MCP resource `agent://plan-index`. |
| `research/` | Research — surveys, comparisons, spike notes. Index: `research/research-index.md`; MCP resource `agent://research-index`. |
| `review/` | Formal reviews — PR reviews, release audits, design reviews. Index: `review/review-index.md`; MCP resource `agent://review-index`. |
| `specs/` | Living specs by domain (functional, UI, API). Index: `specs/specs-index.md`; MCP resource `agent://specs-index`. |
| `journal.d/` | Completion fragments — product PRs write `- [x]` lines here; sync via `co journal-flush`. |
| `versioning.md` | Version policy — tracks, canonical sources, tags, release notes, rollback. |
| `version-state.toml` | Version state — machine-readable facts (`current_release`, `working_version`, `status`, tag, rollback baseline). |

Run `co scaffold` if directories are missing.

---

## 2. Artifact write rules

Every artifact directory has an index. **Writing an artifact without registering it in the
index is incomplete work** — agents discover artifacts through the index, not by listing files.

| When you | Write to | Then update |
|----------|----------|-------------|
| Plan approved or long-lived work | `project/plan/<kebab-name>.md` | `plan/plan-index.md` |
| Research, survey, comparison | `project/research/<name>.md` | `research/research-index.md` |
| Formal review or audit | `project/review/<name>.md` | `review/review-index.md` |
| Add or change a spec | `project/specs/<name>.md` | `specs/specs-index.md` |
| A local change may affect another same-machine project | `project/events/<date>-<name>.md` | `events/events-index.md` |
| Complete work in a product PR | `project/journal.d/<date>-<name>.md` | batch via `co journal-flush` |

Index rows reference the file in backticks; keep the filename column exact so
`co lint --rule artifact-indexes` can match it against disk.

---

## 3. Plan governance

- `project/plan/` is the canonical team/project plan store.
- IDE-native plan directories (for example `.cursor/plans/`) are local drafts or review
  artifacts. They are **not** authoritative unless mirrored into `project/plan/`.
- If a plan is created or approved in an IDE plan mode and should survive the session,
  copy or summarize it into `project/plan/<kebab-name>.md` and update `plan-index.md`.
- When SDD is active, `project/changes/<name>/tasks.md` remains the implementation
  checklist; plan files do not replace it.

---

## 4. Cross-project context

When a task involves **another project** (integration, API docking, migration, referencing
external docs), prefer MCP tools over file-system search on other directories.

| Need | Tool |
|------|------|
| Discover projects on this machine | `list_global_projects` |
| Read another project's `.agent/` context | `get_global_project_context(project)` |
| Read another project's status | `get_global_project_status(project)` |
| Search across all projects | `global_search(keyword)` |
| Declared references and collaborations | `list_relations` |
| Shared cross-project content | `get_related_context(relation)` / `get_collaboration_context(collaboration)` |
| Same-machine event linkage | `list_project_events(project)` / `get_related_events()` / `get_local_linkage_status()` |

Typical flow: `list_global_projects` -> `get_global_project_context("X")` -> use the returned
context. Fall back to direct file access only if these do not cover the need.

**Auto-loading**: references declared `use_when: session_start` or `always` are included in
`get_project_context` output. Collaborations are always auto-loaded with drift detection.
On-demand references appear as actionable hints.

**Setup for recurring cross-project work**:

- `co ref add <path> --name <name> --use-when session_start` — auto-loaded every session
- `co ref add <path> --name <name>` — on-demand via `get_related_context`
- `co collab add <partner> --name <name> --role replica` — shared files + sync tracking

When repeated cross-project access shows up (for example frequently reading another
project's API docs), suggest declaring a relation with `co ref add` or `co collab add`.

---

*Engine file. Must not contain project-specific names or paths.*
