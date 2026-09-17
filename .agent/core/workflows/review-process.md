# Code Review Process

> AI-agent and human guidelines for conducting systematic code and design reviews.  
> For project-specific domain checklists and high-risk patterns, see `project/sop/code-review.md`.

---

## §1 Review Trigger Conditions

Before starting any review, select the appropriate level.

| Trigger | Recommended Level |
|---------|------------------|
| After implementing a feature or fixing a bug, before PR merge | **Standard** (§3) |
| Before releasing a new version (after freeze) | **Pre-Release** (§4) |
| After a production incident or regression | **Post-Incident** (§5) |
| Modifying core async flows, protocols, or security boundaries | **Domain Deep-Dive** (§6) |
| AI Agent completed multiple autonomous changes | **Standard** minimum |
| Significant architecture change or new dependency | **Design Review** (§7) |

---

## §2 General Principles

1. **Read first, review second** — Always read the actual source files before reviewing; do not rely on memory, summaries, or grep snippets alone.
2. **Domain isolation** — Review each domain independently and completely; do not batch-review unrelated areas together.
3. **Distinguish "no issues" from "not fully read"** — Uncovered functions/branches must be explicitly marked `TODO-REVIEW`.
4. **Observation ≠ Bug** — Design trade-offs that are not defects go in the "Observations" section; do not require changes.
5. **Check known issues first** — Before each review session, consult `project/known-issues.md` to avoid re-encountering documented pitfalls.

---

## §3 Standard Review

### 3.1 Pre-checks

```bash
# Ensure no compilation / syntax errors
<build-check-command>   # e.g. cargo check, python -m py_compile, tsc --noEmit

# Ensure tests pass
<test-command>          # e.g. cargo test, pytest, npm test
```

### 3.2 Five Core Review Dimensions

#### A. Error Handling Completeness

- [ ] Every `Result`/`Option`/exception return value is handled (panics/unwraps only where truly impossible, with a comment)
- [ ] Error propagation preserves context (no silent truncation)
- [ ] Remote/network errors vs. local errors are classified separately
- [ ] Error logs include enough context to diagnose without re-reading source

#### B. Concurrency and Race Conditions

- [ ] Lock/mutex scope is minimized (no holding locks across async awaits or long operations)
- [ ] Channel / queue send failures are handled (receiver may have exited)
- [ ] Atomic operations use correct memory ordering
- [ ] No Time-of-Check-Time-of-Use (TOCTOU) bugs in shared state updates
- [ ] Cancellation / shutdown: dropped futures or tasks do not leak resources

#### C. Persistence and Idempotency

- [ ] Critical operations are persisted before being considered complete (write-then-send, not send-then-write)
- [ ] Retried or replayed operations produce the same result (idempotent)
- [ ] DB / storage failures degrade gracefully (log warning, continue if safe; do not panic)

#### D. Security Boundaries

- [ ] No secrets, tokens, or passwords logged or exposed in error messages
- [ ] User-controlled input is validated before use in file paths, DB queries, or commands
- [ ] Authentication/authorization checks are present on all protected routes or commands
- [ ] Third-party output is sanitized before being written to logs or files

#### E. Observability

- [ ] Key state transitions produce `info`-level log entries (connect, disconnect, version change, task completion)
- [ ] Error paths produce `warn` or `error` entries (no silent discard)
- [ ] Progress or throughput metrics are reported where relevant

---

## §4 Pre-Release Review

Execute before cutting a release. Complements `project/sop/release.md`.

### 4.1 Version Consistency

- [ ] All version-bearing files (manifests, configs, docs) reference the same version number
- [ ] `project/version-state.toml` `working_version` and `status` are current

### 4.2 Release Note Completeness

- [ ] Release note exists and lists all user-visible changes
- [ ] Rollback baseline is documented
- [ ] Compatibility matrix is filled in (client ↔ server, API versions, etc.)

### 4.3 Artifact Integrity

- [ ] Build artifact size / hash is within expected range
- [ ] All required bundled resources are present (run a size/content check)
- [ ] No CDN dependencies in offline-deployable artifacts

### 4.4 Smoke Tests

- [ ] Application starts without errors in debug mode
- [ ] Core happy paths verified manually or via automated E2E tests
- [ ] No new `error` or `critical` log entries during startup

---

## §5 Post-Incident Review

Execute within 24 hours of a production incident. Output stored in `docs/operations/` or `project/known-issues.md`.

### 5.1 Root Cause Analysis Template

```
Incident: [symptom summary]
Discovered: YYYY-MM-DD
Impact: [versions, environments, users affected]

Root Cause:
  Direct cause: [code-level description]
  Enabling factors: [why it wasn't caught by tests or prior review]

Fix:
  Code changes: [file:line] [description]
  Test additions: [new tests or manual verification steps]

Prevention:
  New assertions/guards: [description]
  Documentation updates: [known-issues.md / sop/code-review.md]
```

### 5.2 High-Risk Pattern Registry

Each post-incident review should check whether the root cause matches a known class of risk. Record new classes in `project/sop/code-review.md §Known High-Risk Patterns`.

Common cross-project risk classes:

| Pattern | Prevention |
|---------|-----------|
| Async notification race (notify before awaiter starts) | Use persistent flags + notify; never rely solely on in-memory notify |
| Missing guard when optional resource is absent | Check existence before using; don't assume always-present |
| Silent option/flag not propagated through call chain | Add unit test that exercises the flag end-to-end |
| Shared state not cleared on reconnect / restart | Enumerate all session state fields; clear atomically on reset |
| Native tool stderr treated as error under strict error mode | Isolate native calls; check exit code, not stderr presence |
| Artifact built without required resources (no size guard) | Add post-build size/content assertions; fail fast |

---

## §6 Domain Deep-Dive

For high-risk or complex domains, perform a complete function-by-function review.

### 6.1 How to Structure a Domain Deep-Dive

1. **Identify the domain** — A coherent set of files/modules (e.g., authentication, file transfer, update pipeline).
2. **List all entry points** — Public APIs, command handlers, event handlers, scheduled tasks.
3. **Read each function in full** — Do not skip based on name or prior knowledge.
4. **Apply the five dimensions** (§3.2) to each function.
5. **Note interactions between functions** — Caller/callee assumptions, shared state.
6. **Check against known high-risk patterns** (§5.2 and `project/sop/code-review.md`).

### 6.2 Domain Review Table (Template)

Project-specific domains and their key files belong in `project/sop/code-review.md §Domain Deep-Dive`. Generic structure:

```
Domain: [name]
Files: [list of files/modules]

| Function | Review Points | Status |
|----------|---------------|--------|
| fn_a     | error path, concurrency | ✅ |
| fn_b     | security boundary | ⚠️ Observation noted |
| fn_c     | not reviewed | TODO-REVIEW |
```

---

## §7 Design Review

### 7.1 When to Trigger

- Before implementing a significant new feature (affects ≥ 2 modules or introduces a new dependency)
- Before an architectural change (new layer, new protocol, new storage backend)
- Before integrating with an external system or third-party service

### 7.2 Design Review Checklist

#### Scope and Requirements
- [ ] Problem statement is clear and agreed upon
- [ ] Out-of-scope items are explicitly listed
- [ ] Non-functional requirements (performance, reliability, security) are stated with measurable targets
- [ ] Dependencies on other teams or systems are identified

#### Architecture
- [ ] Component boundaries and interfaces are defined
- [ ] Data flows are documented (who writes, who reads, transformation points)
- [ ] Storage choices are justified (type, consistency model, scalability)
- [ ] Failure modes are analyzed (what happens when each component fails)

#### Security (threat modeling)
- [ ] Trust boundaries are drawn (what can call what with what credentials)
- [ ] Sensitive data identified and protection strategy documented
- [ ] Authentication and authorization model is explicit

#### Operability
- [ ] Deployment and rollback strategy is described
- [ ] Observability hooks (metrics, logs, traces) are planned
- [ ] Migration path from current state is specified (if applicable)

### 7.3 Design Review Output

Decisions and rationale belong in an ADR (see `core/workflows/adr-guide.md`). The design doc itself lives in `project/specs/<domain>.md`.

---

## §8 PR Description Template

```markdown
## Summary
[What this change does and why]

## Changes
- [File or component]: [what changed]

## Testing
[How was this tested? Unit tests, integration tests, manual steps]

## Review Level
- [ ] Standard
- [ ] Pre-Release
- [ ] Domain Deep-Dive: [domain name]

## Checklist
- [ ] Compiles / passes linting
- [ ] Tests pass
- [ ] Self-reviewed the diff
- [ ] No new secrets or PII in logs
- [ ] `project/known-issues.md` checked
```

---

## §9 Comment Conventions

| Prefix | Meaning |
|--------|---------|
| `blocking:` | Must fix before merge |
| `suggestion:` | Optional improvement |
| `question:` | Needs clarification |
| `nit:` | Minor style issue |
| `observation:` | Design trade-off, not a defect |
| `security:` | Security concern — treat as `blocking` unless explicitly accepted |

---

## §10 AI Agent Execution Guidelines

When an AI agent performs a review (triggered by "review", "check correctness", "strict review", etc.):

1. **Always use `read_file` for source files** — Do not rely solely on `grep_search` snippets; read the actual file sections.
2. **Review domains sequentially** — Complete one domain before starting the next; output a domain summary after each.
3. **Flag bugs immediately** — Do not defer to a final summary; note bugs as they are found.
4. **For large functions (> 100 lines)**, read in 150–200 line segments; note any unread sections as `TODO-REVIEW`.
5. **Distinguish clearly**:
   - **Bug** (requires fix) → describe root cause, suggest fix
   - **Observation** (design trade-off) → record, do not force change
   - **Risk** (potential issue) → record in `project/known-issues.md` + `TODO-REVIEW` comment
6. **After review**: update `project/status.md` with what was reviewed and any bugs found/fixed.
7. **`unwrap()` / `expect()` in hot paths** — Always evaluate panic risk; comment if safe, flag if unsafe.

### Estimated Time per Review Level

| Level | Typical Duration | File Read Volume |
|-------|-----------------|-----------------|
| Standard | 1 conversation turn | 3–5 files, ~50–150 lines each |
| Pre-Release | 1–2 turns | Checklist-driven, targeted code confirmation |
| Post-Incident | 1 turn | Focused on single root cause path |
| Domain Deep-Dive (per domain) | 1–2 turns | Full file coverage, 200–1500 lines |

---

## §11 Merge Criteria

- [ ] At least one approval from a reviewer (human or AI agent review completed)
- [ ] All `blocking:` comments resolved
- [ ] CI passes (lint + tests + build)
- [ ] No merge conflicts
- [ ] `project/status.md` updated if this closes a tracked task

---

*This file is a generic engine rule. Project-specific domain checklists, high-risk patterns, and function tables belong in `project/sop/code-review.md`.*  
*Protocol version: 3.0.0*
