# Bug Prevention Knowledge Base

> Record common pitfalls and prevention measures. Keep updated when new issues found.

- **Scope**: Applies to the **entire project** (all source, tests, configs).

---

## Encoding Issues

### BUG-001: File Read/Write Encoding Error

**Symptoms**: Garbled characters, `UnicodeDecodeError`
**Root cause**: Not specifying encoding when opening files
**Prevention**: Always explicitly specify `encoding='utf-8'`. See [core-rules](../core-rules.md) and [examples](../examples.md).

```python
# Wrong
with open('file.txt', 'r') as f:
    content = f.read()

# Correct
with open('file.txt', 'r', encoding='utf-8') as f:
    content = f.read()
```

---

## Test Data Conflicts

### BUG-002: Test Data Conflicts with Production

**Symptoms**: Tests fail intermittently, data pollution
**Root cause**: Using fixed test data names
**Prevention**: Use `autotest_` prefix + dynamic RunID

```python
# Wrong
test_user = "test_user"

# Correct
import uuid
run_id = uuid.uuid4().hex[:8]
test_user = f"autotest_user_{run_id}"
```

---

## Exception Handling

### BUG-003: Swallowing Exceptions

**Symptoms**: Silent failures, hard to debug
**Root cause**: Bare except blocks
**Prevention**: Catch specific exceptions, always log

```python
# Wrong
try:
    do_something()
except:
    pass

# Correct
try:
    do_something()
except SpecificError as e:
    logger.error(f"Failed: {e}")
    raise
```

---

## Path Issues

### BUG-004: Path Separator Issues

**Symptoms**: File not found on different OS
**Root cause**: Hardcoded backslashes
**Prevention**: Use `pathlib` or forward slashes

```python
# Wrong
path = "src\\main\\file.py"

# Correct
from pathlib import Path
path = Path("src") / "main" / "file.py"
```

---

## Async Issues

### BUG-005: Blocking in Async Context

**Symptoms**: Event loop blocked, poor performance
**Root cause**: Calling sync functions in async code
**Prevention**: Use async versions or run_in_executor

```python
# Wrong
async def fetch():
    time.sleep(1)  # Blocks!

# Correct
async def fetch():
    await asyncio.sleep(1)
```

---

## Resource Management

### BUG-006: Resource Leaks

**Symptoms**: Memory growth, connection exhaustion
**Root cause**: Not properly closing resources
**Prevention**: Use context managers

```python
# Wrong
f = open('file.txt')
content = f.read()
# Forgot to close!

# Correct
with open('file.txt', encoding='utf-8') as f:
    content = f.read()
```

---

## Node.js CLI Logger (Windows)

### BUG-007: File Logger Hangs Windows Test Worker

**Symptoms**: Test runner prints only `RUN` for minutes with no `Test Files` summary; worker never exits; Linux CI stays green
**Root cause**: Windows `openSync(directory, "a")` succeeds. SonicBoom then `fsync`s a directory fd and the callback never returns. Related nails: disabled `pino()` with no stream (stdout SonicBoom), `end()` waiting for `ready`, swallowing `process.stderr.write`, or `pino.destination({ dest: 2 })`
**Prevention**: Follow [nodejs-cli-file-logger.md](nodejs-cli-file-logger.md). `stat` before open; directory -> stderr fallback; disabled logging uses `{ write() {} }`; shutdown calls `destroy()` not only `end()`; stderr spies must call through
**Example**: See the destination decision table in that workflow. Do not treat Unix `EISDIR` as a Windows guarantee.

---

### BUG-016: Windows agent shell ≠ VS Code default (COMSPEC + `@'` false positive)

**Symptoms**: `run_commands` rejected with `PowerShell here-strings are not valid in cmd.exe` on a `powershell -Command` that only contains `'... @'+$var`; or PowerShell syntax fails because the executor is cmd.
**Root cause**: Unset `defaultProfile.windows` used `COMSPEC` (cmd) as the agent shell. Preflight `/@['"]/` matched any `@'` / `@"`.
**Prevention**: Implicit Windows default is PowerShell (pwsh / Windows PowerShell), never COMSPEC. Detect here-strings only at a token boundary with a newline or a same-line closer `@'...'@` / `@"..."@`.
**Example**: `Write-Output ('--- region A @'+$a)` is not a here-string.

---

## Template

When adding new entries, use this format:

```markdown
### BUG-XXX: Brief Description

**Symptoms**: Observable behavior
**Root cause**: Why it happens
**Prevention**: How to avoid
**Example**: Code showing wrong vs correct approach
```

---

*Keep this file updated when discovering new pitfalls*
*Protocol version: 2.1.0*
