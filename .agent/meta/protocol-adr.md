# Protocol Architecture Decision Records

> Documents the evolution and key decisions of the AI collaboration protocol.

---

## ADR-001: Intelligence Layer Isolation (ILI)

**Status**: Accepted
**Date**: 2026-01-01

**Decision**: Establish physical and logical isolation between `.agent` protocol layer and business code.

**Rationale**: Prevent AI tools from polluting business code, maintain codebase purity.

---

## ADR-002: Engine-Instance Separation

**Status**: Accepted
**Date**: 2026-01-05

**Decision**: Separate generic governance rules (engine) from project-specific information (instance).

**Implementation**:
- `core/` - Engine files, no project-specific content
- `project/` - Instance files, project-specific only

---

## ADR-003: Skill Module Architecture

**Status**: Accepted
**Date**: 2026-01-10

**Decision**: Introduce modular skill system for reusable capabilities.

**Structure**:
```
skills/
└── skill-name/
    ├── SKILL.md
    └── scripts/
```

---

## ADR-004: AI Tool Adapter Pattern

**Status**: Accepted
**Date**: 2026-01-15

**Decision**: Create adapter layer for different AI tools (Copilot, Cursor, Claude).

**Rationale**: 
- Tool-specific configs act as "connectors" to main protocol
- Actual rules remain in `.agent` protocol stack

---

## ADR-005: kebab-case Zero-Exception Naming

**Status**: Accepted
**Date**: 2026-01-18

**Decision**: All markdown files in `.agent/` must use kebab-case. No exceptions.

**Rationale**: Zero exceptions = no judgment calls = no errors.

---

## ADR-006: Progressive Disclosure Loading

**Status**: Accepted
**Date**: 2026-01-20

**Decision**: Implement layered loading strategy to optimize token usage.

**Layers**:
1. Essential - Always load (~3k tokens)
2. Context - Session start (~2k tokens)
3. On-demand - Load when needed

---

## ADR-007: Directory Name Placeholder

**Status**: Accepted
**Date**: 2026-01-23

**Decision**: Use `$AGENT_DIR` placeholder in docs, actual name in `manifest.json`.

**Rationale**: Allows directory renaming without mass document updates.

---

*Protocol version: 2.1.0*
