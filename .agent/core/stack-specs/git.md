# Git Workflow Standards

> Git conventions and workflows.

- **Scope**: All commits and branch naming in the project.

---

## 1. Branch Naming

```
main              # Main branch, always deployable
develop           # Development branch
feature/xxx       # Feature branch
bugfix/xxx        # Bug fix branch
hotfix/xxx        # Emergency fix branch
release/x.x.x     # Release branch
```

**Examples**:
- `feature/user-authentication`
- `bugfix/login-redirect`
- `hotfix/security-patch`

---

## 2. Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code change, no feature/fix |
| `perf` | Performance improvement |
| `test` | Adding tests |
| `chore` | Build, tools, etc. |

### Example

```
feat(auth): add JWT token support

- Implement JWT generation on login
- Add token validation middleware
- Store refresh token in httpOnly cookie

Closes #123
```

---

## 3. Common Commands

```bash
# Start feature
git checkout -b feature/my-feature develop

# Commit changes
git add .
git commit -m "feat(module): add feature"

# Update from develop
git fetch origin
git rebase origin/develop

# Push feature
git push -u origin feature/my-feature

# Create PR (using gh cli)
gh pr create --title "Add feature" --body "Description"
```

---

## 4. Merge Strategies

| Scenario | Strategy |
|----------|----------|
| Feature → develop | Squash merge |
| Hotfix → main | Merge commit |
| Release → main | Merge commit |

```bash
# Squash merge
git merge --squash feature/xxx
git commit -m "feat: add xxx feature"
```

---

## 5. Pre-Commit Checklist

- [ ] Code compiles/runs
- [ ] Tests pass
- [ ] Linting passes
- [ ] Commit message follows convention
- [ ] No sensitive data committed

---

## 6. Gitignore Essentials

```gitignore
# Build outputs
/build/
/dist/
*.exe

# Dependencies
/node_modules/
/venv/
/.venv/

# IDE
/.idea/
/.vscode/
*.swp

# Environment
.env
.env.local
*.local

# OS
.DS_Store
Thumbs.db

# Logs
*.log
/logs/
```

---

## 7. Protected Branches

| Branch | Rules |
|--------|-------|
| `main` | Require PR, require reviews, no force push |
| `develop` | Require PR, require CI pass |

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
