# Quality Assurance Process

> Standards and processes for ensuring code quality.

---

## 1. Code Quality Thresholds

| Metric | Threshold | Tool |
|--------|-----------|------|
| Cyclomatic complexity | ≤ 10 | ruff, pylint |
| Function lines | ≤ 50 | - |
| File lines | ≤ 500 | - |
| Parameter count | ≤ 5 | - |
| Nesting depth | ≤ 4 | - |
| Test coverage | ≥ 60% | pytest-cov |

---

## 2. Static Analysis

### 2.1 Python

```bash
# Linting
ruff check src/

# Type checking
mypy src/

# Formatting
ruff format src/
```

### 2.2 Rust

```bash
# Linting
cargo clippy

# Formatting
cargo fmt

# Check
cargo check
```

---

## 3. Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ruff
        name: ruff
        entry: ruff check --fix
        language: system
        types: [python]
      
      - id: mypy
        name: mypy
        entry: mypy
        language: system
        types: [python]
```

---

## 4. Review Checklist

### Code Quality
- [ ] Follows naming conventions
- [ ] No code duplication
- [ ] Functions are focused (single responsibility)
- [ ] Error handling is complete
- [ ] No hardcoded values

### Security
- [ ] No hardcoded secrets
- [ ] Input validation present
- [ ] SQL injection prevented
- [ ] Proper authentication/authorization

### Performance
- [ ] No obvious N+1 queries
- [ ] No unnecessary loops
- [ ] Resources properly managed

### Testing
- [ ] Tests cover main scenarios
- [ ] Edge cases handled
- [ ] Test data properly isolated

---

## 5. Continuous Integration

```yaml
# Basic CI pipeline
stages:
  - lint
  - test
  - build

lint:
  script:
    - ruff check src/
    - mypy src/

test:
  script:
    - pytest tests/ -v --cov=src

build:
  script:
    - python -m build
```

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
