# AI Collaboration Guidelines

This file defines AI assistant collaboration guidelines and behavior standards during project development.

- **Scope**: These guidelines apply to **all project development** (source code, tests, docs, tooling), not only to content under `.agent`.

---

## 1. Session Initialization

AI assistant must establish context at each new session start:
1. **First**: Read `project/status.md` for current development state (goals, tasks, blockers, recent context).
2. **Active change (SDD) — when present**: If `status.md` contains a section **Active change (SDD)** with a current change name, or if `project/changes/.active` exists, that change is the **working scope** for this session. Before writing or refactoring code, read `project/changes/<name>/tasks.md` first; then read `specs.md`, `design.md`, and `proposal.md` in that directory as needed. Treat unchecked items in `tasks.md` as the implementation checklist; mark them done when completed. If no active change is set, proceed with the rest of the session init only.
3. **Required**: `start-here.md`, `project/context.md`, `project/tech-stack.md`.
4. **Check**: `project/known-issues.md` for historical pain points.
5. **Confirm**: Current task goals, constraints, and risks.

---

## 2. Coding Collaboration Standards

- **Style specs**: Strictly follow corresponding language specs under `core/stack-specs/`.
- **Core requirement**: Explicitly specify UTF-8 encoding, never omit. See [core/examples.md](examples.md) for details.
- **Consistency**: Maintain consistency with existing codebase architecture and naming style.

---

## 3. Task Execution Flow

### 3.1 Task Lifecycle
1. **Before task**: Understand requirements, check `bug-prevention.md`, make incremental plan.
2. **During execution**: **Develop → Verify → Continue**. Each step must close loop, avoid modifying too many files at once.
3. **After task**: Run compliance check scripts, ensure no newly introduced warnings or errors.

### 3.2 Incremental Verification
> Always maintain minimal changeset, ensure system stability through frequent test verification.

---

## 4. Communication and Confirmation

- **Problem clarification**: Must proactively ask when requirements are vague, boundaries unclear, or potential conflicts exist.
- **Solution tradeoffs**: When proposing solutions, briefly explain reasoning and potential risks/tradeoffs.
- **Progress reporting**: Complex tasks should sync progress in stages, marking current blockers.

---

## 5. Behavior Boundaries and Risk Control

### 5.1 Autonomy Principles
- **L3 (Execute directly)**: Code generation, refactoring, formatting, adding comments.
- **L2 (Notify after execution)**: Create non-sensitive files, update non-core configs.
- **L1 (Ask before execution)**: **Delete files**, modify core project dependencies, production environment operations.
- **L0 (Forbidden)**: Access/store sensitive credentials, unauthorized financial transactions, modify security policies.

See [core/workflows/ai-boundaries.md](workflows/ai-boundaries.md) for detailed capability lists and boundary definitions.

---

## 6. Error Handling and Prevention

1. **Found bug**: Record symptoms -> Locate root cause -> Fix -> Update `bug-prevention.md`.
2. **When uncertain**: Prefer conservative approach, clearly mark assumptions.

### 6.1 Evidence Discipline

AI must not present an inferred diagnosis as fact without current, inspectable evidence.

1. **Root-cause claims require evidence**: Before saying a failure is caused by an environment issue, is pre-existing, is unrelated to the current change, or is not a product bug, inspect primary evidence from the current work session.
2. **Accepted evidence**: At least one of: current failing command output, relevant source/test file content, current runtime inspection, or git history/diff proving the claim.
3. **Hypotheses must be labeled**: If evidence is incomplete, state the explanation as a hypothesis and continue investigation. Do not use hypothesis language as a completion summary.
4. **Failed verification blocks completion**: If targeted tests or full regression fail, do not mark the task complete until failures are fixed or a verified blocker is recorded with exact command, failing tests, observed output, and next action.
5. **No risk-bearing changes from unverified diagnosis**: Do not modify product behavior based on an unverified root cause. Reproduce, inspect, and narrow scope first.
6. **Completion evidence**: Before reporting success, verify and report the actual command/result used to support the claim.

### 6.2 Safe Long-Command Runner

Agent tool calls have a wall-clock timeout. A timed-out command can leave a zombie
process, and a result that existed only on stdout is lost. Treat any command that
may run longer than ~20 seconds as a **long command**.

1. **Split steps**. One compile, one test file, or one script — not `build && test && lint`.
2. **Write a result file first**. Redirect the useful output to a path the agent can
   read *after* the tool times out (for example `out/autotest_check.json`).
3. **Bound the process**. Prefer a wrapper that sends SIGTERM, waits ~2 seconds, then
   SIGKILL. On Windows, stop the process tree; do not leave orphaned `node` / `cargo`
   children.
4. **Do not use bash heredoc on PowerShell**. `<<'EOF'` always fails. Use
   `-F .git/COMMIT_MSG_TMP` for git commits (see `core/conventions.md` §3.4) and
   `Out-File` / a script file for other multi-line input.
5. **Read the result file, not the timed-out tool payload**, before claiming the
   command succeeded or failed.

---

## 7. Project State Maintenance

AI must keep `project/status.md` up to date by updating it at **natural checkpoints** during work, not just at session end.

### 7.1 Update Triggers (when to update)

Update `project/status.md` when ANY of these occur:

1. **Task completion** — After finishing a user-requested task or sub-task.
2. **Before git commit** — **Product PRs** (`feat/`, `fix/`): record completed work in `project/journal.d/`; do **not** edit `status.md`. **Agent-status PRs** (`chore/agent-status-*`): run `co journal-flush` and update `status.md`. See `project/AGENT-GIT-PR-WORKFLOW.md`.
3. **Task switching** — When moving from one task to a different task.
4. **Blocker discovered or resolved** — Immediately record new blockers or remove resolved ones.
5. **Session ending signals** — When the user says "done", "thanks", "commit", or indicates work is complete.

### 7.2 What to update

1. **Task Board**: Mark completed tasks, add new tasks discovered during work.
2. **Active Goals**: Update goal statuses if progress was made.
3. **Blockers**: Add new blockers or remove resolved ones.
4. **Session Context**: Replace with key information the next session needs to know (uncommitted changes, in-flight decisions, important caveats).
5. **Recently Completed**: Do **not** edit this section directly. Instead use the fragment model (see §7.4).

**Product vs agent-status PRs:** Prefer updating Task Board / Blockers / Session Context only in dedicated `chore/agent-status-*` PRs when parallel agents are active. Product PRs must not touch `status.md` (see `project/sop/agent-git-pr-collaboration.md`).

### 7.3 Principle

Update **during** work, not only at the end. Frequent small updates are better than one large update that may never happen. This ensures **session continuity** -- the next AI session (or human developer) can read one file and immediately understand the current state.

### 7.4 Journal Fragment Model

To avoid AI re-summarization of long `Recently Completed` lists, completed work is recorded as small **fragment files** rather than direct edits to `status.md`.

**To record completed work:**
1. Create a file at `.agent/project/journal.d/<YYYYMMDD-HHMMSS>-<slug>.md` (one new file per task or session).
2. Write one or more `- [x] <description>` lines.
3. Run `co journal-flush` to sync all pending fragments into `status.md`.

**Fragment file format** (`20260424-153000-add-auth.md`):
```markdown
- [x] Implement JWT auth middleware
- [x] Add login/logout endpoints
```

**`co journal-flush` behavior:**
- Prepends new items to `Recently Completed` (newest first).
- Archives items beyond the 5-item cap to `session-journal.md` under `## YYYY-MM-DD Archived`.
- Deletes processed fragment files.

**Release boundary:** Run `co journal-flush --for-release vX.Y.Z` just before cutting a release. This archives **all** current `Recently Completed` items under `## vX.Y.Z Released (YYYY-MM-DD)` in `session-journal.md` and leaves only the release entry in `status.md`.

### 7.5 Git/PR Task Completion (Done)

A Git/PR task is **NOT complete** until all of the following are true:

1. **PR merged** (or explicitly discarded without merge).
2. **Post-merge cleanup executed** — run `co branch cleanup <head>` (or the project's `post_merge_cleanup_script` from `project/git-config.toml`). **Remote head branch MUST be deleted** (hard rule P1).
3. **Local checkout on trunk**, synced with `{{REMOTE}}/{{TRUNK}}` (fetch + pull).
4. **Product PR journal fragment written** — new file under `project/journal.d/` when applicable; batch `status.md` via `chore/agent-status-*` + `co journal-flush`, not in the product PR.

Task completion reports MUST confirm remote head deletion — never tell the user to delete branches manually.

---

## 9. Consultation Before Implementation (是否类问题)

When the user asks **whether something is needed**, **whether it should be done**, or **whether to adopt an option** (e.g. "是否需要…", "该不该…", "要不要…"):

1. **Evaluate and recommend first** — Give analysis, options, pros/cons, and a clear conclusion or recommendation. Do **not** proceed to code, config, or doc changes by default.
2. **Wait for explicit agreement** — Only implement (edit code, add files, change config) after the user has **explicitly agreed** to a course of action. You may end your reply with a question such as "需要我按某方案改吗？" or "你确认后再动手."
3. **Short rule**: **是否类问题：先评估与建议，不默认实施。**

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 3.2.1*
