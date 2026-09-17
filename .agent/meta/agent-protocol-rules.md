# .agent 协议目录操作规范

> **AI 必读**: 本文件定义了 `.agent` 协议目录的操作约束，所有 AI 在操作 `.agent` 目录时必须遵守。

---

## 1. 目录结构标准

```
.agent/
├── start-here.md           # 🔒 统一入口 (不可修改)
├── manifest.json           # 🔒 协议元数据 (不可修改)
│
├── core/                   # 🔒 治理引擎 (不可修改)
├── adapters/               # 🔒 AI 工具适配 (不可修改)
├── meta/                   # 🔒 协议演进 (不可修改)
├── scripts/                # 🔒 辅助脚本 (不可修改)
│
├── skills/                 # ⚠️ 混合层
│   ├── agent-governance/   # 🔒 标准 (不可修改)
│   ├── ai-integration/     # 🔒 标准 (不可修改)
│   ├── guardian/           # 🔒 标准 (不可修改)
│   ├── skill-interface.md  # 🔒 标准 (不可修改)
│   └── _project/           # 🔓 项目特定 (可修改)
│
└── project/                # 🔓 项目实例 (可修改)
    ├── context.md          # 项目概述、目标、状态
    ├── tech-stack.md       # 技术栈、依赖
    ├── known-issues.md     # 已知问题
    ├── commands.md         # 项目特定命令
    ├── deploy.md           # 部署信息、环境、验证清单
    ├── conventions.md      # 项目级约定补充
    ├── session-journal.md  # 会话日志
    └── adr/                # 架构决策记录
```

**图例**:
- 🔒 = 严格同步层，禁止修改
- ⚠️ = 混合层，部分可修改
- 🔓 = 项目实例层，允许修改

---

## 2. 操作权限矩阵

| 目录/文件 | 读取 | 新增 | 修改 | 删除 |
|-----------|------|------|------|------|
| `start-here.md` | ✅ | ❌ | ❌ | ❌ |
| `manifest.json` | ✅ | ❌ | ❌ | ❌ |
| `core/*` | ✅ | ❌ | ❌ | ❌ |
| `adapters/*` | ✅ | ❌ | ❌ | ❌ |
| `meta/*` | ✅ | ❌ | ❌ | ❌ |
| `scripts/*` | ✅ | ❌ | ❌ | ❌ |
| `skills/` (标准) | ✅ | ❌ | ❌ | ❌ |
| `skills/_project/*` | ✅ | ✅ | ✅ | ✅ |
| `project/*` | ✅ | ✅ | ✅ | ⚠️ |

**说明**:
- `project/` 下的文件可以删除，但建议保留标准文件结构
- 如需新增项目特定 skill，必须放在 `skills/_project/` 下

---

## 3. 禁止操作

### 3.1 绝对禁止

```
❌ 修改 start-here.md 的内容
❌ 修改 core/ 目录下的任何文件
❌ 修改 adapters/ 目录下的任何文件
❌ 修改 meta/ 目录下的任何文件
❌ 修改 scripts/ 目录下的任何文件
❌ 修改 skills/ 下的标准 skill (agent-governance, ai-integration, guardian)
❌ 在 skills/ 根目录下新增文件或目录 (必须放 _project/)
❌ 删除标准目录结构
```

### 3.2 需要确认

```
⚠️ 删除 project/ 下的标准文件 (context.md, tech-stack.md 等)
⚠️ 修改 manifest.json 中的版本号
```

---

## 4. 允许操作

### 4.1 project/ 目录

```
✅ 修改 project/context.md - 更新项目概述、状态
✅ 修改 project/tech-stack.md - 更新技术栈信息
✅ 修改 project/known-issues.md - 添加/更新已知问题
✅ 修改 project/commands.md - 添加/更新项目命令
✅ 修改 project/deploy.md - 添加/更新部署信息
✅ 修改 project/conventions.md - 添加/更新项目约定
✅ 修改 project/session-journal.md - 追加会话记录
✅ 新增 project/adr/*.md - 添加架构决策记录
✅ 新增 project/ 下的其他文件 - 项目特定文档
```

### 4.2 skills/_project/ 目录

```
✅ 新增 skills/_project/<skill-name>/ - 添加项目特定 skill
✅ 修改 skills/_project/ 下的任何文件
✅ 删除 skills/_project/ 下的任何文件
```

---

## 5. start-here.md 规范

`start-here.md` 必须且只能做两件事：

1. **说明协议架构** - Engine-Instance Separation
2. **引导 AI 读取 project/context.md** - Context Building Path

**禁止包含**:
- ~~项目名称~~
- ~~项目概述~~
- ~~开发状态~~
- ~~常用命令~~
- ~~目录结构~~
- ~~核心数据类型~~
- ~~任何项目特定信息~~

---

## 6. project/ 目录规范

### 6.1 必需文件

| 文件 | 用途 | 必需 |
|------|------|------|
| `context.md` | 项目概述、目标、状态、目录结构 | ✅ |
| `tech-stack.md` | 技术栈、依赖、环境配置 | ✅ |
| `known-issues.md` | 已知问题、技术债务 | ✅ |
| `commands.md` | 项目特定命令 | ✅ |
| `deploy.md` | 部署环境、命令、验证清单 | ✅ |
| `session-journal.md` | AI 会话日志 | ✅ |

### 6.2 可选文件

| 文件 | 用途 |
|------|------|
| `conventions.md` | 项目级约定（补充 core 通用规则） |
| `adr/*.md` | 架构决策记录 |
| `structure.md` | 详细目录结构说明 |
| 其他 | 项目特定文档 |

### 6.3 session-journal.md 格式

每次 AI 会话结束时，追加记录：

```markdown
## YYYY-MM-DD Session: [Short Title]

### Completed
- [What was accomplished]

### Technical Debt
- [Unfinished work, known issues introduced]

### Decisions
- [Design decisions made and rationale]
```

`co journal-flush` 溢出归档格式（由命令自动写入，无需手动）：

```markdown
## YYYY-MM-DD Archived
- [x] item 1
- [x] item 2
```

发版归档格式（`co journal-flush --for-release vX.Y.Z` 写入）：

```markdown
## vX.Y.Z Released (YYYY-MM-DD)
- [x] item 1
- [x] item 2
```

### 6.4 journal.d/ 碎片格式

AI 每次任务完成后，创建 `project/journal.d/<YYYYMMDD-HHMMSS>-<slug>.md`，而非直接编辑 `status.md`。

碎片文件内容（仅限 `- [x]` 行）：

```markdown
- [x] 完成的内容描述
- [x] 另一项完成的内容
```

运行 `co journal-flush` 将碎片同步到 `status.md Recently Completed`（保留最新 5 条）并归档溢出。

---

## 7. 同步规则

### 7.1 同步源

`agent_protocol/.agent/` 是所有项目的标准源。

### 7.2 同步范围

| 目录 | 同步策略 |
|------|----------|
| `core/` | 完全覆盖 |
| `adapters/` | 完全覆盖 |
| `meta/` | 完全覆盖 |
| `scripts/` | 完全覆盖 |
| `skills/` (标准部分) | 完全覆盖 |
| `skills/_project/` | 不同步 |
| `project/` | 不同步 |

### 7.3 同步命令 (cokodo-agent)

```bash
# 检查与最新协议的差异
co diff [PATH]

# 常见升级闭环（推荐）
co upgrade [PATH] -y

# 同步通用层（不覆盖 project/）
co sync [PATH]
co sync -y    # 跳过确认
```

### 7.4 CLI 命令概览 (cokodo-agent)

| 命令 | 说明 |
|------|------|
| `co init [PATH]` | 创建 `.agent` 协议目录 |
| `co adapt <cursor\|claude\|copilot\|gemini\|all> [PATH]` | 根据现有 `.agent` 生成 IDE 入口文件（如 CLAUDE.md、AGENTS.md、GEMINI.md、.cursor/rules/*.mdc） |
| `co detect [PATH]` | 检测项目中已有的 IDE 规约文件（不写入） |
| `co import [PATH]` | 从检测到的 IDE 规约文件导入项目名与规则到 `.agent/project/` |
| `co lint [PATH]` | 检查协议合规性 |
| `co sync [PATH]` | 将本地 `.agent` 与最新协议同步 |
| `co upgrade [PATH]` | 推荐升级流程：串联 `sync -> scaffold -> adapt(existing)` |

---

## 8. 版本管理

### 8.1 协议版本

当前协议版本: **3.2.1**（与 `manifest.json` 的 `version` 一致；CLI 展示从 `cokodo_agent.config.BUNDLED_PROTOCOL_VERSION` 读取，勿在代码中写死。）

版本号在 `manifest.json` 中定义；维护说明见 `docs/protocol-version-config.md`。

### 8.2 版本兼容性

- 主版本号变更 (X.0.0): 不兼容变更，需要迁移
- 次版本号变更 (0.X.0): 向后兼容，新增功能
- 补丁版本号变更 (0.0.X): 向后兼容，Bug 修复

---

## 9. 违规处理

如果 AI 违反本规范：

1. **立即停止** 当前操作
2. **回滚** 已做的违规修改
3. **报告** 违规情况给用户
4. **请求** 用户确认后续操作

---

## 10. 例外情况

以下情况可以突破限制，但需要用户明确授权：

1. **协议升级**: 用户明确要求升级协议版本
2. **协议定制**: 用户明确要求修改标准协议内容
3. **紧急修复**: 协议文件存在严重错误需要修复

---

*版本: 1.1.0*
*生效日期: 2026-01-26*
*维护者: ai_workspace*
