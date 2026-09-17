# Core Collaboration Philosophy

This file defines **non-negotiable** top-level principles. Must be strictly followed regardless of programming language or agent used.

---

## 0. Core Values

- **Long-termism**: Rules should not only solve current problems but focus on experience inheritance throughout project lifecycle.
- **Assetization**: `.agent` directory is treated as a digital asset equally important as source code, maintaining independence and portability.
- **Anti-corrosion**: Through strict physical and logical isolation, prevent AI tools from polluting business code, maintaining codebase purity.

---

## 1. Three Prohibitions

### 1.1 Offline First - No External Links
- **Forbidden**: Any external CDN links (Google Fonts, Material Icons, Bootstrap CDN, etc.)
- **Forbidden**: Dependencies on third-party APIs requiring network (unless explicitly requested)
- **Required**: All resources (fonts, icons, libraries) must be localized in project codebase

### 1.2 Lossless Interaction - No Hard Jumps
- **Forbidden**: Any visual state "hard jumps" (show/hide, movement, or color changes without transition)
- **Required**: All UI changes must have smooth animations (recommended 250ms - 300ms)
- **Required**: During layout changes (e.g., sidebar collapse), key element center of gravity must remain stable

### 1.3 Explicit Security - No Unauthorized APIs
- **Forbidden**: Exposing any admin APIs without permission validation
- **Required**: All sensitive operations must log audit trails
- **Required**: Authentication mechanism must be secure and reliable

---

## 2. Intelligence Layer Isolation (ILI)

### 2.1 Physical Isolation
`.agent` directory is the project's "intelligent brain". Its scripts, environments, and configs **must not leak** to project root or business subdirectories.

### 2.2 Logical Isolation
- Business code **must not** call any scripts under `.agent`
- Tools under `.agent` **must not** directly `import` business code (only filesystem scanning/analysis allowed)

### 2.3 Engine-Instance Separation ⭐⭐⭐

Files inside `.agent` are divided into two types:

| Type | Directory | Function | Rule |
|------|-----------|----------|------|
| **Engine files** | `core/` | Generic governance rules | Must not contain any project-specific business names, paths, or logic |
| **Instance files** | `project/` | Project-specific info | All project-related descriptions must be consolidated here |

**Mandatory Rule**:
> Engine files (`core/` directory) must not contain current project's specific names or business paths. All such information must reference definitions in `project/context.md`.

### 2.4 Zero-Pollution Migration
`.agent` must be designed as "plug-and-play":
- Deleting this directory **should not affect** main project's build, run, or test
- Copying this directory to new project **should work immediately**

### 2.5 Adapter Pattern Integration ⭐⭐⭐

For AI tool-specific config files (GitHub Copilot, Cursor), use **pointer strategy**:
- **Forbidden**: Hardcoding extensive rules in tool-specific configs (e.g., `.github/copilot-instructions.md`).
- **Required**: Use as "connector" with only pointers and weight definitions pointing to `.agent` protocol stack.
- Adapter templates should be stored uniformly in `adapters/` directory.

---

## 3. Delivery Quality

### 3.1 Encoding Standards
- **Scope**: Applies to the **entire project** (all source, config, docs, and tooling), not only to files under `.agent`.
- All source code and config files must use **UTF-8** encoding.
- When reading/writing files, must **explicitly set** encoding to UTF-8. See [core/examples.md](examples.md#1-utf-8-explicit-encoding) for implementation.

### 3.2 File Naming Convention
**All** markdown files under `.agent` directory must use **lowercase letters + hyphens** (kebab-case). **No exceptions!**

| Type | Correct [OK] | Wrong [X] |
|------|--------------|------------|
| Filename | `readme.md`, `start-here.md`, `project-context.md` | `README.md`, `StartHere.md`, `projectContext.md` |
| Directory | `workflows`, `bug-prevention`, `design-principles` | `Workflows`, `Bug_Prevention`, `DesignPrinciples` |

### 3.3 Rule Consistency
All tech stack specs apply to **all** files with relevant extensions in project, regardless of purpose (business, utility, or temporary scripts).

### 3.4 Plain Text Over Emoji (ASCII for Compatibility) ⭐
- **Scope**: Applies to the **entire project** (rules, docs, logs, terminal output, and any deliverable), not only to `.agent` content.
- **Required**: Prefer **ASCII** over emoji in rules, documentation, log messages, and terminal output.
- **Reason**: Ensures compatibility with older terminals, CI logs, cross-platform tools, and environments where emoji may not render or may break parsing.
- **Allowed**: Plain ASCII symbols (e.g. `*`, `->`, `[OK]`, `(x)`) for emphasis or status; avoid Unicode emoji (e.g. check/cross symbols as emoji).

### 3.5 Single Source of Truth for Version Numbers and Constants ⭐
- **Scope**: Applies to the **entire project** (source code, config, build scripts, release tooling).
- **Required**: Version numbers (package version, protocol version) and similar build-time constants **must** have exactly one authoritative definition. Other code must derive from that source, not duplicate the value.
- **Forbidden**: Hardcoding the same version or constant in multiple files (e.g. `pyproject.toml` and `config.py` both defining package version).
- **Required**: Use canonical source (e.g. `pyproject.toml` / `package.json` for package version; `manifest.json` for protocol version; `importlib.metadata` / equivalent to read at runtime).
- **Rationale**: Prevents version drift and release mistakes; ensures released artifacts display correct version.

---

## 4. Workflow Guidelines

### 4.1 Workspace Awareness
Always use project root directory as main execution context. Don't arbitrarily switch to subdirectories for command execution.

### 4.2 Path Separator Convention ⭐
In command line, always use **forward slash `/`** as path separator for cross-platform compatibility (Windows and Unix shell).

### 4.3 Terminal Encoding Convention ⭐
- **Scope**: Applies to the **entire project** (all terminal output from scripts, tools, and commands).
- Terminal output must use **UTF-8 encoding** to prevent non-ASCII character display issues.

### 4.4 Incremental Verification
After each module development, must first verify closed-loop (compile, run, test), confirm functionality before continuing next module.

### 4.5 Synchronous Testing
When developing new features, must simultaneously develop corresponding test plans to ensure deliverables are verifiable.

### 4.6 Test Data Isolation ⭐⭐⭐
Automated tests must use dynamically generated identifiers and dedicated prefix `autotest_` to avoid conflicts. See [core/examples.md](examples.md#2-test-data-isolation) for implementation.

---

## 5. Complete Delivery Checklist

Before submitting any feature or fix, must complete the following checks:

- [ ] **Code quality**: Follows naming conventions, explicit UTF-8 encoding, complete error handling.
- [ ] **Test coverage**: New features have corresponding test cases, test data uses dynamic RunID.
- [ ] **Performance metrics**: App startup and key operation response times are reasonable, no obvious regression.
- [ ] **Documentation sync**: README, API docs, and bug prevention manual are updated.

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 2.1.0*
