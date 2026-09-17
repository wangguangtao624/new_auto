# Python Development Standards

> For Python 3.10+ projects.

- **Scope**: All Python files in the project (see [core-rules §3.3](../core-rules.md)).

---

## 1. Project Structure

```
project/
├── src/
│   └── package_name/
│       ├── __init__.py
│       ├── main.py
│       ├── models/
│       ├── services/
│       └── utils/
├── tests/
├── .agent/
├── pyproject.toml
└── README.md
```

---

## 2. Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Module | snake_case | `user_service.py` |
| Class | PascalCase | `UserManager` |
| Function/Method | snake_case | `get_user_by_id()` |
| Variable | snake_case | `user_count` |
| Constant | UPPER_SNAKE | `MAX_RETRIES` |
| Private | _prefix | `_internal_cache` |

---

## 3. Type Annotations

```python
# Required
def get_user(user_id: int) -> User | None:
    ...

def process_items(items: list[Item]) -> dict[str, int]:
    ...
```

---

## 4. File Operations

```python
# Always specify encoding
with open('file.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Use pathlib
from pathlib import Path
config_path = Path(__file__).parent / 'config' / 'settings.yaml'
```

---

## 5. Exception Handling

```python
# Catch specific exceptions
try:
    result = api.fetch_data()
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    raise
except TimeoutError:
    return None

# Never bare except
try:
    ...
except:
    pass
```

---

## 6. Async Programming

```python
import asyncio

async def fetch_data(url: str) -> dict:
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Don't block async context
async def bad():
    time.sleep(1)  # Blocks!

# Use async versions
async def good():
    await asyncio.sleep(1)
```

---

## 7. Testing

```python
@pytest.fixture
def db_session():
    session = create_session()
    yield session
    session.rollback()
    session.close()

def test_create_user_with_valid_data_succeeds():
    ...
```

---

## 8. Dependencies

```toml
# pyproject.toml
[project]
name = "project-name"
requires-python = ">=3.10"

dependencies = [
    "pydantic>=2.0",
    "httpx>=0.24",
]

[tool.ruff]
line-length = 100

[tool.mypy]
strict = true
```

---

## 9. Commands

```bash
# Format
ruff format src/ tests/

# Lint
ruff check src/ tests/ --fix

# Type check
mypy src/

# Test
pytest tests/ -v --cov=src
```

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
