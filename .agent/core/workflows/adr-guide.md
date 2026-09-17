# Architecture Decision Records (ADR) Guide

> When and how to record architecture decisions. Designed to be lightweight and low-friction.

---

## 1. When to Write an ADR

### Mandatory Triggers

Write an ADR when any of the following occur:

| Trigger | Example |
|---------|---------|
| **Tech stack change** | Switching ORM, adding a database, changing framework |
| **Architecture pattern change** | Monolith → microservice, adding message queue |
| **Build/deploy strategy change** | Docker migration, CI/CD pipeline redesign |
| **Data model breaking change** | Schema redesign, storage engine switch |
| **Security model change** | Auth mechanism switch, encryption strategy change |

### Recommended Triggers

Consider an ADR when:

- Choosing between 2+ viable approaches with meaningful tradeoffs
- Reversing or superseding a previous decision
- A decision will constrain future development options

### Not Needed

Skip ADR for:

- Routine bug fixes
- Code style changes covered by conventions
- Dependency version bumps (unless major)
- UI layout adjustments

---

## 2. ADR Format

### Lightweight Template (Preferred)

For most decisions, use this minimal 3-section format:

```markdown
# ADR-XXX: [Decision Title]

**Status**: Proposed | Accepted | Superseded by ADR-YYY
**Date**: YYYY-MM-DD

## Context
[What is the situation? What forces are at play?]

## Decision
[What did we decide to do?]

## Consequences
[What are the positive and negative effects of this decision?]
```

### Extended Template (For Major Decisions)

When the decision has broad impact, add these optional sections:

```markdown
# ADR-XXX: [Decision Title]

**Status**: Proposed | Accepted | Superseded by ADR-YYY
**Date**: YYYY-MM-DD

## Context
[Situation and forces]

## Options Considered

### Option A: [Name]
- **Pros**: [advantages]
- **Cons**: [disadvantages]

### Option B: [Name]
- **Pros**: [advantages]
- **Cons**: [disadvantages]

## Decision
[What we chose and why]

## Consequences
[Positive and negative effects]

## Implementation Notes
[Key implementation details, migration steps, or configuration changes]
```

---

## 3. ADR Lifecycle

```
Proposed → Accepted → [Superseded by ADR-YYY]
```

- **Proposed**: Under discussion
- **Accepted**: Decision is final and in effect
- **Superseded**: Replaced by a newer ADR (keep the old one for history, update status)

### Numbering

- Sequential: `001`, `002`, `003`...
- Never reuse numbers
- Superseded ADRs keep their original number

---

## 4. ADR Index

Maintain `project/adr/readme.md` as an index:

```markdown
# Architecture Decision Records

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| 001 | [Title] | Accepted | YYYY-MM-DD |
| 002 | [Title] | Superseded by 003 | YYYY-MM-DD |
| 003 | [Title] | Accepted | YYYY-MM-DD |
```

---

## 5. AI Collaboration Rules

- When AI proposes a significant technical decision, it should **suggest creating an ADR**
- The ADR should be drafted by AI but **reviewed and accepted by the human collaborator**
- ADRs capture the "why" — code captures the "what"

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 3.1.0*
