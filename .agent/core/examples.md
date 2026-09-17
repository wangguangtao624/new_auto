# Protocol Code Examples

> This file contains best practice code examples referenced in the protocol. Load on demand.

---

## 1. UTF-8 Explicit Encoding

In all file read/write operations, must explicitly specify UTF-8 encoding.

### Python
```python
# Correct
with open('file.txt', 'r', encoding='utf-8') as f:
    content = f.read()

with open('output.txt', 'w', encoding='utf-8') as f:
    f.write(content)
```

### Rust
```rust
// Rust uses UTF-8 by default
use std::fs;
let content = fs::read_to_string("file.txt")?; 
```

### PowerShell
```powershell
# Set default encoding at script start
$InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

---

## 2. Test Data Isolation

Use dynamically generated `RunID` and unified prefix `autotest_` for data isolation.

### Python
```python
import uuid

RUN_ID = uuid.uuid4().hex[:8]
TEST_USER = f"autotest_user_{RUN_ID}"
TEST_DATA = f"autotest_data_{RUN_ID}"

# Pre-cleanup logic
def cleanup():
    old_test_data = db.query(User).filter(User.name.startswith('autotest_')).all()
    for item in old_test_data:
        db.delete(item)
```

### TypeScript / JavaScript
```typescript
const RUN_ID = Math.random().toString(36).substring(2, 7);
const TEST_USER = `autotest_user_${RUN_ID}`;

// Pre-cleanup logic
async function cleanup() {
  const oldTestData = await db.findMany({
    where: { name: { startsWith: 'autotest_' } }
  });
  for (const item of oldTestData) {
    await db.delete(item.id);
  }
}
```

---

## 3. Terminal UTF-8 Setup

### PowerShell
```powershell
# Set console output encoding to UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
chcp 65001
```

### Bash
```bash
# Ensure locale settings are correct
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
```

---

*This file is a reference example, load on demand.*
