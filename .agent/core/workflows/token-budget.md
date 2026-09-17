# Token Budget Management

> Guidelines for controlling protocol document volume to prevent context window bloat.

- **Scope**: **`.agent` protocol documents only** (controls what is loaded into AI context).

---

## 1. Why Token Budgets Matter

AI models have finite context windows. Every token spent on protocol documents is a token unavailable for actual code, conversation, and reasoning. Protocol documents should be **lean, high-signal, and layered**.

---

## 2. Budget Targets

### Per-Layer Budgets

| Layer | Target | Max | Notes |
|-------|--------|-----|-------|
| **Essential** (always loaded) | ~2,000 | 3,000 | start-here.md, core-rules.md |
| **Context** (session start) | ~2,000 | 4,000 | project context, tech stack, known issues |
| **Stack Specs** (on demand) | ~1,500 | 3,000 | Per selected stack spec |
| **Workflows** (on demand) | ~1,000 | 2,000 | Per selected workflow |
| **Skills** (on demand) | ~500 | 5,000 | SKILL.md frontmatter → full load |

### Total Session Budget

| Scenario | Typical Load | Target |
|----------|-------------|--------|
| Quick fix | Essential + Context | ~4,000 tokens |
| Feature dev | Essential + Context + Stack + Workflows | ~7,000 tokens |
| Full load | Everything | ~12,000 tokens max |

---

## 3. Measurement

### Quick Estimate

- English: ~4 characters per token (or ~250 tokens per KB)
- Chinese: ~2 characters per token (or ~500 tokens per KB)
- Code blocks: ~3 characters per token

### Using the Token Counter

```bash
python .agent/scripts/token-counter.py
```

This produces a per-file and per-layer breakdown.

---

## 4. Controlling Document Size

### Do

- Use tables instead of verbose prose
- Put examples in `core/examples.md` and reference them
- Use layered loading (`manifest.json`) — not everything needs to load every session
- Keep `project/context.md` focused on **what AI needs to know**, not comprehensive documentation
- Archive resolved issues from `known-issues.md` periodically

### Don't

- Duplicate content across files (use cross-references)
- Include full code examples in rule files (reference `examples.md`)
- Keep extensive session journal history in the active file (archive old entries)
- Put deployment playbooks in protocol docs (reference external docs)

---

## 5. Review Triggers

Check token budget when:

- Adding a new file to `project/`
- Session journal exceeds 10 entries
- Known issues exceeds 5 active items
- Total protocol size exceeds 50 KB

### Archival Strategy

| File | Archive When | Archive To |
|------|-------------|------------|
| `session-journal.md` | >10 entries | `project/archive/sessions-YYYY.md` |
| `known-issues.md` (resolved) | >5 resolved | `project/archive/issues-resolved.md` |
| `adr/` (superseded) | Never delete | Keep in place, update status |

---

## 6. Manifest Integration

The `manifest.json` `loading_strategy` controls what gets loaded when. Review it periodically:

```json
{
  "layers": {
    "essential": {
      "token_budget": 3000,
      "files": ["start-here.md", "core/core-rules.md"]
    },
    "context": {
      "token_budget": 2000,
      "files": ["project/context.md", "project/tech-stack.md"]
    }
  }
}
```

When adding new files, assign them to the correct layer and verify the budget.

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 3.1.0*
