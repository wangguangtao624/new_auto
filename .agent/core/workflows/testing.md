# Testing Protocol

> Standards for writing and organizing tests.

---

## 1. Test Organization

### 1.1 Directory Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
├── e2e/           # End-to-end tests
├── fixtures/      # Shared test data
└── conftest.py    # Shared fixtures (pytest)
```

### 1.2 Naming Conventions

```python
# Test file: test_{module}.py
test_user_service.py

# Test function: test_{action}_{scenario}_{expected}
def test_create_user_with_valid_data_succeeds():
    pass

def test_create_user_with_duplicate_email_raises_error():
    pass
```

---

## 2. Test Data Isolation

### 2.1 Dynamic RunID (Mandatory)

```python
import uuid

RUN_ID = uuid.uuid4().hex[:8]
TEST_PREFIX = "autotest_"

def get_test_name(base: str) -> str:
    return f"{TEST_PREFIX}{base}_{RUN_ID}"
```

### 2.2 Pre-Cleanup

```python
@pytest.fixture(autouse=True)
def cleanup_test_data(db):
    # Cleanup before test
    db.query(User).filter(
        User.name.startswith('autotest_')
    ).delete()
    yield
    # Cleanup after test
    db.query(User).filter(
        User.name.startswith('autotest_')
    ).delete()
```

---

## 3. Test Structure

### 3.1 Arrange-Act-Assert

```python
def test_user_creation():
    # Arrange
    user_data = {"name": get_test_name("user"), "email": "test@example.com"}
    
    # Act
    result = user_service.create_user(user_data)
    
    # Assert
    assert result.id is not None
    assert result.name == user_data["name"]
```

### 3.2 Given-When-Then (BDD)

```python
def test_order_total_calculation():
    # Given: An order with two items
    order = Order()
    order.add_item(Item(price=100))
    order.add_item(Item(price=50))
    
    # When: Calculate total with 10% tax
    total = order.calculate_total(tax_rate=0.1)
    
    # Then: Total should include tax
    assert total == 165
```

---

## 4. Fixtures

### 4.1 Pytest Fixtures

```python
@pytest.fixture
def db_session():
    session = create_session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def sample_user(db_session):
    user = User(name=get_test_name("user"))
    db_session.add(user)
    db_session.commit()
    return user
```

---

## 5. Mocking

### 5.1 External Services

```python
from unittest.mock import patch, MagicMock

def test_send_email():
    with patch('services.email.smtp_client') as mock_smtp:
        mock_smtp.send.return_value = True
        
        result = email_service.send("test@example.com", "Subject", "Body")
        
        assert result is True
        mock_smtp.send.assert_called_once()
```

---

## 6. Test Coverage

### 6.1 Minimum Thresholds

| Metric | Threshold |
|--------|-----------|
| Overall coverage | ≥ 60% |
| Critical path coverage | ≥ 80% |
| New code coverage | ≥ 70% |

### 6.2 Running Coverage

```bash
pytest --cov=src --cov-report=html tests/
```

---

## 7. Node.js / TypeScript CLI loggers

When tests create a pino / SonicBoom file destination (especially on Windows):

- Do not treat a successful `openSync(path, "a")` as proof the path is a file
- stderr spies must call through to the original `write`
- Shut down the logger in `afterEach` with `destroy()`, not only `end()`

Full decision table, hang symptoms, and the PR checklist: [nodejs-cli-file-logger.md](nodejs-cli-file-logger.md).

---

## 8. CI Integration

```yaml
test:
  script:
    - pytest tests/ -v --cov=src
  coverage: '/TOTAL.*\s+(\d+%)/'
```

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
