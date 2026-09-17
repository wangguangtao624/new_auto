# .agent Protocol Self-Check Prompt

## How to Use

1. **When**: After you add or edit files under `.agent/` (core, project, adapters, or structure), or before a release/PR that touches the protocol.
2. **Where**: In an AI session that has already loaded the protocol (e.g. start-here, core-rules, conventions). Optionally load `meta/agent-protocol-rules.md` and `project/adr/` if you want to check ADR alignment.
3. **How**: Paste this entire file (or the "Instructions for the AI" and checklist sections) into the chat. Ask the AI to run the self-check and output the report using the "Report Template" at the bottom.
4. **Result**: Use the report to fix any [Fail] items or to confirm that the protocol still complies with its own rules (encoding scope, naming, no emoji in core, single source of truth for UTF-8, scope clarity, ADR consistency).

You can also run `python .agent/scripts/lint-protocol.py` for structural and manifest checks; the self-check prompt covers rule content and scope that scripts do not.

---

## Instructions for the AI

You are performing a **protocol self-check** of the `.agent` directory against the rules defined in `core/core-rules.md`, `core/conventions.md`, and the ADRs in `project/adr/`. For each item below:

1. Check only the scope stated (e.g. "under .agent" vs "entire project").
2. Report **Pass** or **Fail**. On Fail, cite concrete file path and line or snippet.
3. Do not modify files unless the user explicitly asks you to fix violations.

---

## 1. Encoding and Plain Text (Entire Project + .agent)

- [ ] **UTF-8 scope**: Rules that require UTF-8 encoding and explicit `encoding='utf-8'` in file I/O apply to the **entire project** (core-rules §3.1). Confirm that core and instructions do not state that encoding rules apply only to `.agent`.
- [ ] **No-emoji scope**: Rules that prefer ASCII over emoji apply to the **entire project** (core-rules §3.4). Confirm wording is project-wide.
- [ ] **Core content**: Under `core/`, no Unicode emoji (e.g. check/cross/heart/lock emoji) in rule text or code examples. Use ASCII (e.g. `[OK]`, `[X]`, `# Correct`, `# Wrong`, `Good:` / `Avoid:`).
- [ ] **Terminal encoding**: Rule that terminal output must use UTF-8 applies to the **entire project** (core-rules §4.3). Confirm scope is stated.

---

## 2. Naming Under .agent Only

- [ ] **Kebab-case**: Every markdown file and directory **under `.agent/`** uses lowercase + hyphens only (e.g. `start-here.md`, `bug-prevention.md`, `stack-specs/`). No `README.md`, `StartHere.md`, or `snake_case` for .agent files/dirs.
- [ ] **No conflict with IDEs**: Naming rules apply only to **contents under `.agent/`**. Adapter-generated files (e.g. `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursor/rules/*.mdc`) live outside `.agent/` and follow each IDE's required names. No rule should require those to be kebab-case.

---

## 3. Scope Clarity (No Ambiguity)

- [ ] **core-rules**: Sections 3.1 (Encoding), 3.4 (No emoji), and 4.3 (Terminal encoding) each state **Scope: entire project** (or equivalent). Section 3.2 (File naming) clearly states it applies only to markdown/dirs **under .agent**.
- [ ] **conventions.md**: Explicit that §1.1 (Protocol directory) applies to `.agent` only, and §1.2 and below apply to the **entire project**.
- [ ] **instructions.md**: States that guidelines apply to **all project development**, not only `.agent` content.
- [ ] **Workflows** (e.g. bug-prevention, design-principles, security): Each states whether it applies to the **entire project** or to a specific scope (e.g. token-budget = `.agent` protocol only).
- [ ] **Stack-specs** (python, rust, qt, git): Each states that it applies to all relevant files/commits **in the project** (and references core-rules §3.3 where appropriate).

---

## 4. Single Source of Truth (UTF-8 / Encoding)

- [ ] **Authority**: The only **full** definitions of UTF-8 encoding rules (file I/O and terminal) are in `core/core-rules.md` (§3.1, §4.3, §5) and `core/examples.md` (e.g. §1 UTF-8 explicit encoding, §3 Terminal UTF-8). Other files (bug-prevention, design-principles, stack-specs, security) should **reference** these, not duplicate full code blocks or lengthy encoding prose.
- [ ] **References**: Any mention of "always use UTF-8" or "explicit encoding" outside core-rules and examples should be a short pointer (e.g. "See core-rules §3.1 and examples.md").

---

## 5. Delivery Checklist Alignment (core-rules §5)

- [ ] **Checklist**: The "Complete Delivery Checklist" in core-rules §5 includes: code quality (naming, explicit UTF-8, error handling), test coverage (dynamic RunID / autotest_ prefix), performance, documentation sync. No conflicting checklist in other core files that omits these.

---

## 6. Engine-Instance and Adapter Rules

- [ ] **Engine files** (`core/`): No project-specific business names, paths, or logic; project-specific info only in `project/` (e.g. context.md).
- [ ] **Adapters**: Adapter templates under `adapters/*` do not hardcode long rule bodies; they point to `.agent` protocol (pointer strategy). Encoding reminders in adapters, if any, are one-line references to core-rules/examples, not duplicated full examples.

---

## 7. ADR and Meta Consistency

- [ ] **ADRs**: If `project/adr/` contains ADR 005 (UTF-8 consolidation) or 006 (scope and emoji audit), the current state of core and workflows should match the "implemented" state described there (e.g. Scope lines present, emoji removed from core).
- [ ] **meta/agent-protocol-rules.md**: Operation constraints (what may be edited by whom) are clear. Naming/encoding rules here, if mentioned, are consistent with core-rules (e.g. "protocol naming applies under .agent only; IDE file names follow vendor specs").

---

## Report Template

After running the check, reply in this form:

```
## Self-Check Report (date / branch if applicable)

| # | Item (short) | Result | Note |
|---|---------------|--------|------|
| 1 | Encoding & plain text scope + core no-emoji | Pass/Fail | ... |
| 2 | Kebab-case under .agent, no IDE conflict | Pass/Fail | ... |
| 3 | Scope clarity (core, conventions, instructions, workflows, stack-specs) | Pass/Fail | ... |
| 4 | UTF-8 single source of truth | Pass/Fail | ... |
| 5 | Delivery checklist alignment | Pass/Fail | ... |
| 6 | Engine-instance & adapters | Pass/Fail | ... |
| 7 | ADR / meta consistency | Pass/Fail | ... |

Summary: [One sentence.]
```

---

*This prompt is part of the .agent protocol; update it when new self-check criteria are agreed (e.g. in ADRs).*
