# Design Principles

> Core principles guiding architecture and code design.

- **Scope**: Applies to the **entire project** (architecture and code design).

---

## 1. SSOT (Single Source of Truth)

### Principle
Each piece of data should have one authoritative source.

### Application

```python
# Wrong - multiple config sources
class ComponentA:
    config = yaml.load(open("config.yaml"))

class ComponentB:
    config = yaml.load(open("config.yaml"))

# Correct - single config manager
class ConfigManager:
    _instance = None
    
    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls._load_config()
        return cls._instance

# All components use
config = ConfigManager.get()
```

---

## 2. Dependency Injection

### Principle
Dependencies should be injected, not created internally.

### Application

```python
# Wrong - hard dependency
class UserService:
    def __init__(self):
        self.db = PostgresDB()  # Hard to test

# Correct - dependency injection
class UserService:
    def __init__(self, db: Database):
        self.db = db

# Usage
service = UserService(db=PostgresDB())
# Testing
test_service = UserService(db=MockDB())
```

---

## 3. Simplicity First

### Principle
Choose the simplest solution that works. Don't over-engineer.

### Guidelines
- Start with the simplest implementation
- Add complexity only when needed
- Refactor when patterns emerge

```python
# Over-engineered for simple case (wrong)
class UserRepositoryFactoryBuilder:
    def build_factory(self):
        return UserRepositoryFactory()

# Simple and direct (correct)
def get_user(user_id: int) -> User:
    return db.query(User).get(user_id)
```

---

## 4. Separation of Concerns

### Principle
Each module/function should have one responsibility.

### Application

```python
# Mixed concerns (wrong)
def process_order(order_data):
    # Validation
    if not order_data.get('items'):
        raise ValueError("No items")
    # Business logic
    total = sum(item['price'] for item in order_data['items'])
    # Persistence
    db.save(Order(total=total))
    # Notification
    email.send(order_data['email'], "Order confirmed")

# Separated concerns (correct)
def validate_order(order_data):
    if not order_data.get('items'):
        raise ValueError("No items")

def calculate_total(items):
    return sum(item['price'] for item in items)

def save_order(order):
    return db.save(order)

def notify_customer(email, order):
    email_service.send(email, "Order confirmed")
```

---

## 5. Fail Fast

### Principle
Detect and report errors as early as possible.

### Application

```python
# Late failure (wrong)
def process_file(path):
    content = open(path).read()  # May fail late
    # ... 100 lines of processing ...
    return result

# Fail fast (correct)
def process_file(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.suffix == '.txt':
        raise ValueError(f"Expected .txt file, got: {path.suffix}")
    
    content = path.read_text(encoding='utf-8')
    # ... processing ...
```

---

## 6. Interface Segregation

### Principle
Clients should not depend on interfaces they don't use.

### Application

```python
# Fat interface (wrong)
class Repository:
    def find(self, id): ...
    def find_all(self): ...
    def save(self, entity): ...
    def delete(self, id): ...
    def export_to_csv(self): ...  # Not all repos need this

# Segregated interfaces (correct)
class Readable:
    def find(self, id): ...
    def find_all(self): ...

class Writable:
    def save(self, entity): ...
    def delete(self, id): ...

class Exportable:
    def export_to_csv(self): ...

class UserRepository(Readable, Writable):
    ...
```

---

## 7. Design Review Workflow

> When to apply: before implementing a significant new feature, architectural change, or external integration. See also `core/workflows/review-process.md §7`.

### 7.1 Design Document Template

Create a design spec at `project/specs/<domain>.md` before implementation:

```markdown
# Design: [Feature / Component Name]

## Problem Statement
[What problem are we solving? What constraints apply?]

## Non-Goals (Explicit Out-of-Scope)
[What is explicitly NOT in scope for this change?]

## Solution Options Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| A: ...  | ...  | ...  | ✅ Chosen / ❌ Rejected |

## Chosen Architecture
[Data flows, component diagram, interface definitions]

## Data Model
[Entities, relationships, storage choices with justification]

## Failure Modes and Mitigations
| Failure | Impact | Mitigation |
|---------|--------|-----------|
| [service X down] | [effect] | [circuit breaker / retry / degrade] |

## Security Considerations
[Trust boundaries, sensitive data, auth model]

## Observability Plan
[Metrics, log events, tracing spans to add]

## Migration / Rollout Plan
[How to deploy; feature flags; backward compatibility window]

## Open Questions
- [Question]: [Owner] — by [date]
```

### 7.2 Requirements Review Checklist

Use this when clarifying or validating requirements (especially for new feature requests or external integrations):

- [ ] Stakeholder agreement: all affected parties have reviewed the requirements
- [ ] Measurable acceptance criteria exist for each requirement
- [ ] Non-functional requirements (latency, throughput, availability) have target values
- [ ] Dependencies on external teams or systems are identified and accepted
- [ ] Each requirement is traceable to a business goal
- [ ] Out-of-scope items are explicitly listed to prevent scope creep

### 7.3 Architecture Review Checklist

- [ ] **Bounded contexts**: each component has a single, clearly stated responsibility
- [ ] **Interface contracts**: inputs, outputs, and error cases are defined before implementation
- [ ] **Data ownership**: every data entity has exactly one authoritative writer
- [ ] **Failure independence**: a failure in component A does not cascade to unrelated component B
- [ ] **Rollback feasibility**: the change can be rolled back or feature-flagged off safely
- [ ] **No hidden coupling**: components do not share mutable state across module boundaries
- [ ] Chosen ADRs are recorded in `project/adr/` (see `core/workflows/adr-guide.md`)

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 3.0.0*
