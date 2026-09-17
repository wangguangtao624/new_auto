# Naming Conventions

This file defines project naming conventions, Git conventions, and documentation format standards.

- **Scope**: Section 1.1 applies to the **`.agent` directory only**. Sections 1.2 and below apply to the **entire project** (source code, docs, repo).

---

## 1. File Naming Conventions

### 1.1 Protocol Directory ($AGENT_DIR/)

**Mandatory kebab-case (zero exceptions)**

| Type | Correct [OK] | Wrong [X] |
|------|-----------|----------|
| Markdown | `start-here.md`, `bug-prevention.md` | `StartHere.md`, `bug_prevention.md` |
| Directory | `stack-specs/`, `ai-integration/` | `StackSpecs/`, `ai_integration/` |
| JSON | `banned_patterns.json` | `BannedPatterns.json` |

### 1.2 Source Code Directory

Follow tech stack conventions:

| Tech Stack | File | Directory |
|------------|------|-----------|
| Python | `snake_case.py` | `snake_case/` |
| Rust | `snake_case.rs` | `snake_case/` |
| C++/Qt | `PascalCase.cpp` | `PascalCase/` |
| QML | `PascalCase.qml` | `components/` |

---

## 2. Code Naming Conventions

### 2.1 Python

```python
# Class name: PascalCase
class UserManager:
    pass

# Function/method: snake_case
def get_user_by_id(user_id: int) -> User:
    pass

# Variable: snake_case
user_count = 0
current_user = None

# Constant: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30

# Private attribute: single underscore prefix
class Config:
    def __init__(self):
        self._cache = {}      # private
        self.timeout = 30     # public

# Module-level private: single underscore prefix
_internal_cache = {}
```

### 2.2 Rust

```rust
// Type: PascalCase
struct UserManager {
    users: Vec<User>,
}

// Enum: PascalCase, variants also PascalCase
enum Status {
    Active,
    Inactive,
    Pending,
}

// Function/method: snake_case
fn get_user_by_id(user_id: u64) -> Option<User> {
    None
}

// Variable: snake_case
let user_count = 0;
let mut current_user = None;

// Constant: UPPER_SNAKE_CASE
const MAX_RETRY_COUNT: u32 = 3;
static DEFAULT_TIMEOUT: u64 = 30;

// Module: snake_case
mod user_manager;
```

### 2.3 C++/Qt

```cpp
// Class name: PascalCase
class UserManager {
public:
    // Public method: camelCase
    User* getUserById(int userId);
    
private:
    // Private member: m_ prefix + camelCase
    int m_userCount;
    QList<User*> m_users;
};

// Function: camelCase
void processUserData();

// Constant/macro: UPPER_SNAKE_CASE
#define MAX_RETRY_COUNT 3
const int DEFAULT_TIMEOUT = 30;
```

---

## 3. Git Conventions

### 3.1 Branch Naming

```
main              # Main branch, always deployable
develop           # Development branch
feature/xxx       # Feature branch
bugfix/xxx        # Bug fix branch
hotfix/xxx        # Emergency fix branch
release/x.x.x     # Release branch
```

### 3.2 Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation update |
| `style` | Code format (no logic change) |
| `refactor` | Refactor (no new feature or bug fix) |
| `perf` | Performance optimization |
| `test` | Test-related |
| `chore` | Build/tool changes |

#### Example

```
feat(auth): add JWT token refresh mechanism

- Implement automatic token refresh before expiry
- Add refresh token storage in secure cookie
- Update auth middleware to handle refresh flow

Closes #123
```

### 3.3 Pre-Commit Checklist

Before commit, must confirm:

- [ ] Code follows naming conventions
- [ ] No lint errors
- [ ] Tests passing
- [ ] Commit message follows convention

### 3.4 Shell Compatibility for Git Commit

On **Windows / PowerShell**, bash heredoc (`<<'EOF'`) is not supported.
Use `-F` with a temp file — this is the most reliable cross-shell method:

```powershell
# Write message to temp file, commit, then delete
"feat: subject line`n`nBody line 1`nBody line 2" | Out-File -Encoding utf8 .git/COMMIT_MSG_TMP
git commit -F .git/COMMIT_MSG_TMP
Remove-Item .git/COMMIT_MSG_TMP
```

For single-line messages with no double quotes, single-quoted `-m` also works:

```powershell
git commit -m 'chore: simple message'
```

**Never use `<<'EOF'` heredoc in PowerShell — it always fails.**

## 4. Documentation Format Standards

### 4.1 Markdown Conventions

```markdown
# H1 Title (document title, only one)

> Document intro or important note

---

## H2 Title (main sections)

### H3 Title (subsections)

#### H4 Title (deepest level, avoid going deeper)
```

### 4.2 Code Blocks

Must specify language tag:

````markdown
```python
def hello():
    print("Hello, World!")
```
````

### 4.3 Tables

Alignment and format:

```markdown
| Col1 | Col2 | Col3 |
|------|------|------|
| A    | B    | C    |
```

### 4.4 Links

- Internal links use relative paths
- External links use complete URLs

```markdown
[Internal doc](../project/context.md)
[External link](https://example.com)
```

---

## 5. Version Number Convention

### 5.1 Semantic Versioning (SemVer)

```
MAJOR.MINOR.PATCH

1.0.0  → First stable version
1.1.0  → Backward-compatible new feature
1.1.1  → Backward-compatible bug fix
2.0.0  → Incompatible API change
```

### 5.2 Pre-release Versions

```
1.0.0-alpha.1  → Alpha test version
1.0.0-beta.1   → Beta test version
1.0.0-rc.1     → Release candidate
```

---

## 6. Comment Conventions

### 6.1 Python Docstring

```python
def calculate_total(items: list[Item], tax_rate: float = 0.1) -> float:
    """
    Calculate order total (including tax).
    
    Args:
        items: Order item list
        tax_rate: Tax rate, default 10%
    
    Returns:
        Total amount including tax
    
    Raises:
        ValueError: When items is empty
    
    Example:
        >>> items = [Item(price=100), Item(price=200)]
        >>> calculate_total(items)
        330.0
    """
    if not items:
        raise ValueError("Items cannot be empty")
    subtotal = sum(item.price for item in items)
    return subtotal * (1 + tax_rate)
```

### 6.2 Rust Doc Comments

```rust
/// Calculate order total (including tax).
///
/// # Arguments
///
/// * `items` - Order item list
/// * `tax_rate` - Tax rate, default 10%
///
/// # Returns
///
/// Total amount including tax
///
/// # Errors
///
/// Returns `CalculationError::EmptyItems` when `items` is empty
///
/// # Examples
///
/// ```
/// let items = vec![Item::new(100.0), Item::new(200.0)];
/// let total = calculate_total(&items, 0.1)?;
/// assert_eq!(total, 330.0);
/// ```
pub fn calculate_total(items: &[Item], tax_rate: f64) -> Result<f64, CalculationError> {
    // ...
}
```

---

## 7. Logging Convention

### 7.1 Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Debug info, dev environment only |
| `INFO` | Regular runtime info |
| `WARNING` | Warning, doesn't affect operation |
| `ERROR` | Error, needs attention |
| `CRITICAL` | Critical error, affects service |

### 7.2 Log Format

```
[Time] [Level] [Module] Message
2026-01-23 10:30:00 INFO  [auth] User login successful: user_id=123
2026-01-23 10:30:01 ERROR [db] Connection failed: timeout after 30s
```

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
