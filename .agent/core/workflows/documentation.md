# Documentation Standards

> Guidelines for writing and maintaining documentation.

---

## 1. Documentation Types

| Type | Purpose | Location |
|------|---------|----------|
| Protocol entry | AI session starting point | `start-here.md` |
| Core rules | Non-negotiable principles | `core/` |
| Project context | Business info | `project/` |
| Skill modules | Reusable capabilities | `skills/` |

---

## 2. Markdown Standards

### 2.1 Structure

```markdown
# Document Title (H1, only one)

> Brief description or important note

---

## Main Section (H2)

### Subsection (H3)

#### Detail (H4, deepest recommended)
```

### 2.2 Code Blocks

Always specify language:

````markdown
```python
def example():
    pass
```
````

### 2.3 Tables

```markdown
| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
```

---

## 3. README Template

```markdown
# Project Name

> One-line description

## Quick Start

\`\`\`bash
# Installation
pip install -r requirements.txt

# Run
python main.py
\`\`\`

## Features

- Feature 1
- Feature 2

## Documentation

- [User Guide](docs/user-guide.md)
- [API Reference](docs/api.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT
```

---

## 4. API Documentation

### 4.1 Function Documentation

```python
def calculate_total(items: list[Item], tax_rate: float = 0.1) -> float:
    """
    Calculate order total including tax.
    
    Args:
        items: List of order items
        tax_rate: Tax rate (default: 10%)
    
    Returns:
        Total amount with tax
    
    Raises:
        ValueError: When items list is empty
    
    Example:
        >>> calculate_total([Item(100), Item(50)], 0.1)
        165.0
    """
```

---

## 5. Changelog Format

```markdown
## [1.2.0] - 2026-01-23

### Added
- New feature X

### Changed
- Improved performance of Y

### Fixed
- Bug in Z (#123)

### Removed
- Deprecated API W
```

---

## 6. Documentation Checklist

Before committing:

- [ ] Code comments are clear and concise
- [ ] README reflects current functionality
- [ ] API changes are documented
- [ ] Examples are tested and working

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
