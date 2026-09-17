---
name: guardian
description: |
  Code and documentation quality gate skill.
  Provides automated checks for code patterns, architecture layers, and content quality.
---

# Guardian Skill

> Code and documentation quality gate - automated checks before commit.

---

## Overview

| Attribute | Value |
|-----------|-------|
| Name | Guardian |
| Version | 2.0.0 |
| Type | Quality Assurance |
| Trigger | Pre-commit, PR |

---

## Capabilities

1. **Banned Pattern Check** - Detect forbidden code patterns
2. **Layer Dependency Check** - Verify architecture layer rules
3. **Test Policy Check** - Ensure test coverage requirements
4. **Content Quality Check** - Validate documentation standards

---

## Usage

```bash
# Run all checks
python $AGENT_DIR/skills/guardian/scripts/check_all.py

# Code checks only
python $AGENT_DIR/skills/guardian/scripts/check_code.py src/

# Content checks only
python $AGENT_DIR/skills/guardian/scripts/check_content.py docs/
```

---

## Configuration

### Banned Patterns (rules/banned_patterns.json)

```json
{
  "patterns": [
    {
      "id": "no-bare-except",
      "pattern": "except:\\s*$",
      "severity": "error",
      "message": "Use specific exception types"
    }
  ]
}
```

---

## CI Integration

```yaml
name: Quality Check
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Guardian
        run: python $AGENT_DIR/skills/guardian/scripts/check_all.py
```

---

*This skill is a portable component, reusable across projects*
*Version: 2.0.0*
