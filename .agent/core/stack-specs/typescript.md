# TypeScript / Node.js Development Standards

> For TypeScript and JavaScript Node.js projects (apps, CLIs, monorepos).

- **Scope**: All TypeScript and JavaScript files in the project (see [core-rules §3.3](../core-rules.md)).
- **CLI file logger on Windows**: follow [nodejs-cli-file-logger.md](../workflows/nodejs-cli-file-logger.md) whenever creating or changing a pino / SonicBoom file destination.

---

## 1. Project Structure

```
project/
├── src/
│   ├── index.ts
│   ├── logging/
│   └── utils/
├── tests/
├── .agent/
├── package.json
├── tsconfig.json
└── README.md
```

Monorepos may use `apps/` and `packages/`. Stack rules still apply to every `.ts` / `.js` file.

---

## 2. Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| File / module | kebab-case or camelCase (match the repo) | `user-service.ts` |
| Class / type / interface | PascalCase | `UserManager` |
| Function / method | camelCase | `getUserById()` |
| Variable | camelCase | `userCount` |
| Constant | UPPER_SNAKE or camelCase | `MAX_RETRIES` |
| Private field | `_prefix` or `#` | `_internalCache` |

---

## 3. Types

Prefer explicit types on exported functions and public APIs. Do not use `any` unless a boundary (JSON, third-party) forces it, and then narrow immediately.

```typescript
// Required
function getUser(userId: number): User | null {
  ...
}

function processItems(items: Item[]): Record<string, number> {
  ...
}
```

---

## 4. File Operations

Always declare UTF-8. See [core-rules](../core-rules.md) and [examples](../examples.md). Use forward slashes or `path` / `node:fs` helpers; do not hardcode backslashes.

```typescript
import { readFileSync } from "node:fs"
import { join } from "node:path"

const content = readFileSync(join("config", "settings.json"), { encoding: "utf-8" })
```

---

## 5. Error Handling

Catch specific errors. Log, then rethrow or return a typed fallback. Never swallow with an empty `catch`.

```typescript
try {
  result = await api.fetchData()
} catch (error) {
  if (error instanceof TypeError) {
    logger.error({ err: error }, "fetch failed")
    throw error
  }
  throw error
}
```

---

## 6. Testing

- Automated test data must use the `autotest_` prefix (see [core-rules §4.6](../core-rules.md)).
- Clean up file destinations, timers, and workers in `afterEach` / `afterAll`.
- Do not mock `process.stderr.write` with a no-op. If a spy is required, call through to the original `write`. See [nodejs-cli-file-logger.md](../workflows/nodejs-cli-file-logger.md) section 4.

```typescript
function testCreateUserWithValidDataSucceeds(): void {
  ...
}
```

---

## 7. CLI file logger (Windows)

Node file loggers that use pino / SonicBoom hang Windows processes when the destination is a directory fd, an implicit stdout stream, or an async fd-2 fallback. This is a stack rule, not a project quirk.

| Condition | Correct stream | Forbidden |
|-----------|----------------|-----------|
| Logging disabled | `{ write() {} }` (no-op) | `pino()` with no destination (attaches stdout SonicBoom) |
| Path exists and is a directory | stderr `write()` fallback | `openSync(dir, "a")` as proof of writability; `pino.destination(dir)` |
| Path can be a regular file | `pino.destination({ dest, mkdir: true, sync: true })` | `sync: false` for short-lived CLI / test workers |
| Probe failed (permission / read-only) | `{ write: (m) => process.stderr.write(m) }` | `pino.destination({ dest: 2 })` |

Probe order:

1. `mkdirSync(dirname(path), { recursive: true })`
2. If `existsSync(path) && statSync(path).isDirectory()` treat as not writable
3. Then `openSync(path, "a")` + `closeSync` as a file-level probe
4. On failure, fallback to stderr

Do not treat a successful `openSync(..., "a")` as proof the path is a writable file. Windows succeeds on directories.

Shutdown must `destroy()` the destination. Do not only `end()` — `end()` waits for `ready` and can hang forever on Windows. Full lifecycle, test constraints, and the PR checklist: [nodejs-cli-file-logger.md](../workflows/nodejs-cli-file-logger.md).

---

## 8. Dependencies

```json
{
  "type": "module",
  "engines": { "node": ">=20" }
}
```

Pin logger / SonicBoom versions when the project uses file destinations. sonic-boom 4.2.x has no `unref()`; `dest.unref?.()` is forward-compatible only and is not an exit strategy.

---

## 9. Commands

```bash
# Type check
npx tsc --noEmit

# Test (prefer a single file or hard timeout when a worker may hang)
npx vitest run src/logging/adapter.test.ts

# Lint / format — use the repo's configured tools
```

If a test file hangs at `RUN` with no summary, do not wait on the full suite. See [nodejs-cli-file-logger.md](../workflows/nodejs-cli-file-logger.md) section 5.

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 3.3.1*
