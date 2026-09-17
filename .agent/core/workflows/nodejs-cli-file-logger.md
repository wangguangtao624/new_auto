# Node.js CLI File Logger (Windows)

> Load when creating, changing, or testing a Node/TypeScript CLI file logger (pino / SonicBoom).
> Stack pointer: [typescript.md](../stack-specs/typescript.md) section 7.

- **Scope**: Node.js and TypeScript CLI processes and their unit tests.

---

## Goal

File logging must behave the same on Windows and Unix, and:

- Fall back to stderr when the path is unusable. **Never** SonicBoom-fsync a directory fd
- Disabled logging and short-lived processes (`--help`, test workers) must exit
- Shutdown must be idempotent and safe to call from `afterEach`

### Non-goals

- Replacing pino with another logger
- Changing user-visible log format or the project's default log path

---

## 1. Destination decision table

| Condition | Required stream | Forbidden |
|-----------|-----------------|-----------|
| Logging disabled | `{ write() {} }` (no-op) | Calling `pino()` with no destination (attaches stdout SonicBoom) |
| Target path exists and **is a directory** | stderr `write()` fallback | `openSync(dir, "a")` as writable; `pino.destination(dir)` |
| Target path can be created as a regular file | `pino.destination({ dest, mkdir: true, sync: true })` | `sync: false` (async stream + on-exit hooks) |
| File probe failed (permission / read-only) | `{ write: (m) => process.stderr.write(m) }` | `pino.destination({ dest: 2 })` |

Probe order:

1. `mkdirSync(dirname(path), { recursive: true })`
2. **If `existsSync(path) && statSync(path).isDirectory()` treat as not writable**
3. Then `openSync(path, "a")` + `closeSync` as a file-level probe
4. On failure, fallback

Do not treat a successful `openSync(..., "a")` as proof of a writable file. Windows succeeds on directories. Unix `EISDIR` must not be assumed on Windows.

---

## 2. Lifecycle

```text
create -> put in logger cache (actual stream, including fallback)
       -> registerDisposable(shutdown) once
flush  -> destination.flushSync(); swallow not-ready / destroyed
shutdown -> flush -> destroy() (do not end()) -> clear cache -> clearInterval
```

- `end()` waits for `ready` when `_opening` or `fd === -1`. On Windows that wait can last forever.
- `destroy()` goes to `actualClose`. If the fd is already a directory, fsync can still hang — **reject directories at create time**. Shutdown cannot fix a directory fd.
- sonic-boom 4.2.1 has **no `unref()`**. Keep `dest.unref?.()` for forward compatibility only. It is not an exit strategy.
- A fallback `{ write }` object has no `destroy`. Shutdown is a no-op for that stream.

---

## 3. flushSync wrapper

SonicBoom calls `flushSync()` on process `exit`. Short-lived processes (`--help`) may flush before the stream is ready and throw `sonic boom is not ready yet`. Wrap `flushSync`, swallow that error, and keep treating `SonicBoom destroyed` as ignorable. Other errors still propagate per the project's ignorable list.

---

## 4. Test constraints (same weight as the implementation)

| Do | Do not |
|----|--------|
| Use a **directory path** to test fallback; assert no throw and stderr output | Assume Unix `EISDIR` also happens on Windows |
| stderr spy **must call through** to the original `write` | `mockImplementation(() => true)` swallowing stderr |
| Prove sync by writing one line and immediately `readFileSync` | `spyOn(pino, "destination")` only to inspect dest (interferes with close) |
| Call logger shutdown in `afterEach` | Leave a file destination open at end of file |

### stderr spy (required call-through)

```typescript
const originalWrite = process.stderr.write.bind(process.stderr)
const spy = vi.spyOn(process.stderr, "write").mockImplementation((chunk, encoding, cb) => {
  if (typeof encoding === "function") return originalWrite(chunk, encoding)
  return originalWrite(chunk, encoding, cb)
})
```

Fallback (unwritable path) tests should still use a temporary **directory** as the log path (that is a valid case), but the implementation must reject the directory first. Assert "does not throw" plus stderr has content.

---

## 5. Symptoms and root-cause patterns

Recognize a hang before treating it as a slow assertion.

| Signal | Meaning |
|--------|---------|
| Runner prints only `RUN v4.x` for minutes, no `Test Files` | **Worker did not exit**, not a slow assert |
| Reproduces only on Windows; Linux CI is green | Check "directory opened as file" and stderr mocks first |
| Skipping one `*.test.ts` lets the suite finish | That file created/closed a logger or mocked stderr |

Serial fork pools (`fileParallelism: false`) make one hung file block every later file.

| Pattern | What happens | Typical code |
|---------|--------------|--------------|
| **A. Directory as log file** | Windows `openSync(dir, "a")` succeeds; SonicBoom `fsync` on a directory fd never returns | Using `mkdtempSync()` as the log path |
| **B. Disabled pino with no stream** | `pino({ enabled: false })` attaches stdout SonicBoom and is not cached | Disabled-log branch forgot `{ write() {} }` |
| **C. `end()` waits for ready** | sonic-boom `end()` / `actualClose(fd===-1)` waits for `ready` | Shutdown only calls `destination.end()` |
| **D. Swallowing stderr.write** | Test worker reporter / IPC still writes stderr | `spyOn(process.stderr, "write").mockImplementation(() => true)` |
| **E. Async fd 2 SonicBoom** | `pino.destination({ dest: 2, sync: false })` is not in the cache | Fallback used dest 2 as a shortcut |

**Forbidden**: infer Windows fallback from "opening a directory fails on Unix".

---

## 6. Coding constraints and PR checklist

When changing a pino destination adapter:

1. `stat` **before** creating a file dest. Directory -> fallback.
2. Disabled logging -> no-op `write()`. Never call `pino()` without a stream.
3. Fallback -> `{ write: (m) => process.stderr.write(m) }`. Never `dest: 2`.
4. Cache the actual stream. Shutdown uses **`destroy()`**.
5. Wrap `flushSync` and swallow `not ready` / `destroyed`.

Checklist (PR / self-test):

- [ ] New path probes do not assume `EISDIR`
- [ ] Every `pino()` call passes an explicit destination
- [ ] `afterEach` calls logger shutdown
- [ ] No mock swallows stderr

---

## 7. Workaround and triage

When the implementation is not in yet, or another file still hangs the worker:

```powershell
# Skip the hanging file and run the rest
npx vitest run --exclude src/logging/adapter.test.ts

# Run only the logger file (healthy: summary within 5s)
npx vitest run src/logging/adapter.test.ts --no-color
```

Stuck on `RUN` for more than 60s with no summary:

1. Kill the vitest / node / bun worker process tree (`taskkill /T /F` on Windows). Leftover workers make the next run look hung too.
2. Re-run one file or one test name. Do not idle on the full unit suite.
3. Locate with small batches and a hard timeout (60-180s). Suspect logger dest, stderr mock, or a SonicBoom that was not `destroy()`ed.

Do not stack multiple unreaped forks.

A healthy logger test file prints a `Test Files` summary within **5 seconds**.

---

*This file is a generic engine rule, must not contain any project-specific information*
*Protocol version: 3.3.1*
