# Skill Module Interface Specification

> Defines standard structure, interface, and lifecycle for skill modules.

---

## 1. Overview

Skills are reusable capability modules in the `.agent` protocol, encapsulating domain-specific knowledge and automation scripts.

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Single Responsibility** | Each skill focuses on one domain |
| **Self-Contained** | All docs, scripts, rules within directory |
| **Discoverable** | Metadata declared via manifest.json |
| **Loosely Coupled** | No strong dependencies between skills |

---

## 2. Directory Structure

```
skills/
├── {skill-name}/              # Protocol / portable skills (cokodo)
│   ├── SKILL.md               # Main doc (required, uppercase)
│   ├── manifest.json          # Metadata (recommended)
│   ├── rules/                 # Rule definitions (optional)
│   ├── scripts/               # Automation scripts (optional)
│   ├── templates/             # Template files (optional)
│   └── references/            # Progressive disclosure Level 3 (optional)
│       ├── REFERENCE.md
│       ├── api.md
│       ├── patterns.md
│       └── gotchas.md
└── _project/
    └── {skill-name}/          # Project-specific skills (not protocol-locked)
        └── SKILL.md
```

> **Note**: Entry file must be `SKILL.md` (uppercase) for [agentskills.io](https://agentskills.io) compatibility.

### 2.1 Skills roots (dual-root convention)

| Root | Purpose | Who owns it |
|------|---------|-------------|
| `.agent/skills/` | Protocol / portable cokodo skills | cokodo-agent sync (locked standard skills) |
| `.agent/skills/_project/` | Project-only skills and overrides | Project team (not overwritten by sync) |
| `.agents/skills/` | Cross-tool Agents Skills (Cursor / Codex / upstream Cline) | Host / team; optional mirror of project skills |

Hosts that load cokodo skills should scan **both**:

1. `.agent/skills/<name>/SKILL.md` — protocol skills
2. `.agent/skills/_project/<name>/SKILL.md` — project skills

Do **not** place custom project skills as siblings of locked skills at `.agent/skills/<name>/` (linter rule `skills-placement`).

### 2.2 Recommended SKILL.md skeleton

Align with Agents Skills progressive disclosure and Cline-style skill writing:

```markdown
---
name: example-skill
description: One-line trigger description
---

# Example Skill

## Critical Rules
- Non-negotiable constraints the agent must follow when this skill is active.

## Decision Tree
- When X → do A
- When Y → do B

## Workflow
1. Step one
2. Step two

## References
Load on demand from `references/` (api.md, patterns.md, gotchas.md).
```

---

## 3. Manifest Specification

```json
{
  "name": "guardian",
  "version": "1.0.0",
  "description": "Code quality and security check skill",
  
  "triggers": {
    "explicit": ["check code", "review", "validate"],
    "automatic": ["pre-commit", "pull-request"]
  },
  
  "capabilities": [
    {
      "name": "banned-pattern-check",
      "description": "Check for forbidden code patterns"
    }
  ],
  
  "entry_points": {
    "main": "SKILL.md",
    "check": "scripts/check_all.py"
  },
  
  "tags": ["quality", "security", "automation"]
}
```

---

## 4. Skill Lifecycle

```
Discovery → Activation → Execution → Deactivation
```

**Progressive Disclosure**:
1. **Level 1**: Load YAML frontmatter (~100 tokens/skill)
2. **Level 2**: Load SKILL.md body on trigger (<5k tokens)
3. **Level 3**: Load additional files on demand (unlimited)

---

## 5. Capability Interface

### Input/Output

```python
# Standard input
SkillInput = {
    "capability": str,
    "params": dict,
    "context": {
        "project_root": str,
        "tech_stack": list,
    }
}

# Standard output
SkillOutput = {
    "success": bool,
    "results": list | dict,
    "errors": list,
    "warnings": list,
}
```

---

## 6. Parameterized Skills (Multi-Backend Pattern)

When a skill addresses a common concern (e.g., schema comparison, migration) but the implementation varies by tech stack, use the **parameterized skill** pattern instead of forking the skill per project.

### 6.1 Design

```
skills/
└── db-schema-compare/
    ├── SKILL.md              # Unified documentation
    ├── manifest.json          # Declares supported backends
    └── scripts/
        ├── compare_schema.py  # Main entry, dispatches by backend
        ├── backends/
        │   ├── prisma.py      # Prisma-specific logic
        │   ├── sqlalchemy.py  # SQLAlchemy-specific logic
        │   └── typeorm.py     # TypeORM-specific logic
        └── base.py            # Shared interface / base class
```

### 6.2 Manifest Declaration

```json
{
  "name": "db-schema-compare",
  "version": "2.0.0",
  "description": "Compare ORM schema with actual database",
  
  "parameters": {
    "backend": {
      "type": "string",
      "required": true,
      "enum": ["prisma", "sqlalchemy", "typeorm"],
      "description": "ORM backend to use"
    },
    "connection": {
      "type": "string",
      "required": false,
      "description": "Database connection string (or use Docker auto-detect)"
    }
  },
  
  "backends": {
    "prisma": {
      "description": "Prisma schema comparison",
      "schema_path": "backend/prisma/schema.prisma"
    },
    "sqlalchemy": {
      "description": "SQLAlchemy model comparison",
      "model_path": "backend/app/models/"
    }
  }
}
```

### 6.3 When to Parameterize

| Situation | Approach |
|-----------|----------|
| Same concern, different tech stack | Parameterized skill with backends |
| Completely different concern | Separate skill |
| Minor project-specific tweak | Config override in `skills/_project/` |

### 6.4 Project-Level Skills and Overrides

Project-specific skills and overrides live under `skills/_project/`:

```
skills/_project/
└── my-project-skill/
    ├── SKILL.md           # Full project skill
    └── config.json        # Or parameter override extending a protocol skill
```

```json
{
  "extends": "db-schema-compare",
  "parameters": {
    "backend": "sqlalchemy",
    "connection": "postgresql://localhost:5432/mydb"
  }
}
```

**Host scan list (recommended):** `.agent/skills/*/SKILL.md` and `.agent/skills/_project/*/SKILL.md`. Optional: also load `.agents/skills/*/SKILL.md` when the IDE uses the Agents Skills layout (see §2.1).

---

## 7. Best Practices

### Development Checklist

- [ ] Create `SKILL.md` with YAML frontmatter
- [ ] Create `manifest.json` (recommended)
- [ ] Scripts support CLI invocation
- [ ] Scripts output structured results
- [ ] Provide usage examples
- [ ] Complete documentation
- [ ] Consider parameterization if the skill could serve multiple tech stacks

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Skill directory | kebab-case | `code-guardian` |
| Script file | snake_case | `check_all.py` |
| Rule ID | kebab-case | `no-bare-except` |
| Capability name | kebab-case | `banned-pattern-check` |

---

*This file is the skill module interface specification*
*Protocol version: 3.1.0*
