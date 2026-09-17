# AI Capability Boundaries

> Defines AI assistant autonomous operation permissions and human confirmation thresholds.

---

## 1. Permission Levels

| Level | Behavior | Applicable Scenarios |
|-------|----------|---------------------|
| **L3 Autonomous** | Execute directly, no confirmation needed | Code generation, refactoring, formatting, comments, unit test writing |
| **L2 Notify** | Execute then inform user | Create new files, modify dev configs, generate docs |
| **L1 Confirm** | Request approval, execute after user confirms | **Delete files**, modify core dependencies, database migration, sensitive logic changes |
| **L0 Forbidden** | Refuse execution, warn about risks | Store credentials, production deployment, modify security audit policies |

---

## 2. Detailed Operation Categories

### 2.1 AI Can Do Autonomously (L3/L2)
- **Code development**: Refactoring, performance optimization, adding type annotations.
- **Quality assurance**: Writing test cases, running local lint checks.
- **Auxiliary work**: Updating README, maintaining known issues list.

### 2.2 Operations Requiring Human Confirmation (L1) ⚠️
- **Destructive changes**: Deleting any non-generated source code or config files.
- **Environment changes**: Modifying `pyproject.toml`, `package.json`, or other core dependency files.
- **Architecture changes**: Major design pattern changes or cross-layer dependency introductions.
- **Data operations**: Batch modifications or deletions involving business data.

### 2.3 Operations Strictly Forbidden (L0)
- **Sensitive information**: Accessing, printing, or storing contents from `.env` or credential files.
- **Security undermining**: Disabling SSL verification, reducing authentication strength.
- **Unauthorized external interactions**: Sending emails, SMS, or calling paid APIs (unless pre-authorized).

---

## 3. Conflict Resolution Guidelines

When AI recommended approach conflicts with existing conventions:
1. **Stop execution** and point out conflict.
2. **Analyze impact**, explain why breaking convention is suggested.
3. **Request decision**, let user decide to follow or update convention.

---

*Last updated: 2026-01-23*
