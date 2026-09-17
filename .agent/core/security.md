# Security Development Standards

> Security is not a feature, it's a foundation.

- **Scope**: Applies to the **entire project** (all code that handles input, authentication, or sensitive data).

---

## 1. Core Principles

### 1.1 Defense in Depth
Multiple layers of security controls, never rely on single defense.

### 1.2 Least Privilege
Grant only minimum necessary permissions.

### 1.3 Fail Secure
On failure, default to secure state.

---

## 2. Input Validation

### 2.1 Never Trust User Input

```python
# Wrong - direct use of user input
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)

# Correct - parameterized query
def get_user(user_id: int):
    query = "SELECT * FROM users WHERE id = ?"
    return db.execute(query, [user_id])
```

### 2.2 Whitelist Validation

```python
ALLOWED_EXTENSIONS = {'.jpg', '.png', '.gif'}

def validate_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS
```

---

## 3. Authentication & Authorization

### 3.1 Password Storage

```python
import bcrypt

def hash_password(password: str) -> bytes:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt)

def verify_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode(), hashed)
```

### 3.2 Token Management

```python
# Token generation
import secrets
token = secrets.token_urlsafe(32)

# Token validation
def validate_token(token: str) -> bool:
    # Use constant-time comparison
    return secrets.compare_digest(token, stored_token)
```

---

## 4. Sensitive Data Handling

### 4.1 Never Log Secrets

```python
import logging
logger = logging.getLogger(__name__)

def mask_sensitive(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return value[:2] + "****" + value[-2:]

# Wrong
logger.info(f"Token: {token}")

# Correct
logger.info(f"Token: {mask_sensitive(token)}")
```

### 4.2 Environment Variables

```python
import os

# Wrong - hardcoded (never do this)
API_KEY = "<hardcoded-secret>"

# Correct - from environment
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable required")
```

---

## 5. SQL Injection Prevention

### 5.1 Use ORM or Parameterized Queries

```python
# Using SQLAlchemy ORM
user = session.query(User).filter(User.id == user_id).first()

# Using parameterized query
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

---

## 6. XSS Prevention

### 6.1 Output Encoding

```python
from markupsafe import escape

# Wrong
html = f"<div>Hello, {user_name}</div>"

# Correct
html = f"<div>Hello, {escape(user_name)}</div>"
```

---

## 7. File Operations

### 7.1 Path Traversal Prevention

```python
from pathlib import Path

def safe_read(base_dir: Path, filename: str) -> str:
    # Resolve to absolute path
    file_path = (base_dir / filename).resolve()
    
    # Verify still under base directory
    if not file_path.is_relative_to(base_dir.resolve()):
        raise ValueError("Invalid file path")
    
    return file_path.read_text(encoding='utf-8')
```

---

## 8. Error Handling

### 8.1 Don't Expose Internal Details

```python
# Wrong - exposes internal info
except Exception as e:
    return {"error": str(e), "traceback": traceback.format_exc()}

# Correct - generic message, log details internally
except Exception as e:
    logger.error(f"Internal error: {e}", exc_info=True)
    return {"error": "An internal error occurred"}
```

---

## 9. Security Checklist

Before delivery, verify:

- [ ] All user input validated
- [ ] No hardcoded credentials
- [ ] Sensitive data properly masked in logs
- [ ] SQL queries parameterized
- [ ] Authentication properly implemented
- [ ] Authorization checked for all endpoints
- [ ] HTTPS enforced for production
- [ ] Security headers configured

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
