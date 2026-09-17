# Docker 打包优化规范

> 通用规范：加快 Docker 镜像构建、部署与调试验证循环。思路参考 [微信云托管 - 如何提高项目构建效率](https://developers.weixin.qq.com/miniprogram/dev/wxcloudservice/wxcloudrun/src/scene/build/speed.html)，适用于多语言栈（Rust、Node、Python 等）项目。

- **Scope**：适用于涉及 **Docker 镜像构建、Dockerfile 编写或优化** 的任务。
- **Authority**：编写或修改 Dockerfile 时建议遵循本规范；与 `project/deploy.md` 配合使用。

---

## 1. 优化原则概览

| 原则 | 说明 | 应用示例 |
|------|------|------------|
| **变化的放后面，利用缓存** | Docker 按层缓存；依赖/配置少变，源码常变。先复制依赖清单并安装依赖，再复制源码并构建，可最大化复用缓存。 | Node：先 `COPY package.json package-lock.json` → `npm ci`，再 `COPY .` → `npm run build`。Rust：先 COPY Cargo.toml + crates 清单，再 `cargo build`，最后 COPY 业务源码。 |
| **减少层数，合并 RUN** | 每一条 RUN 产生一层。将同类型操作（如安装系统包、创建用户）合并为一条 RUN，可减小镜像层数。 | 运行时阶段：`apk add` 与 `addgroup/adduser` 合并为单条 RUN。 |
| **BuildKit 缓存挂载** | 使用 `RUN --mount=type=cache,target=...` 将包管理器的下载与构建目录挂载为持久缓存，重复构建时复用，显著缩短二次构建时间。 | Rust：Cargo registry、git、target 缓存。Node：npm 缓存目录。Python：pip 缓存。 |
| **选用合适基础镜像** | 在满足版本要求的前提下，优先使用体积较小的官方 Alpine 镜像。 | 如 `rust:*-alpine`、`node:lts-alpine*`、`nginx:alpine`、`python:*-alpine`。 |
| **可选：更换源站** | 在内网或国内环境拉取慢时，可在 Dockerfile 中为 apk/npm/pip 配置镜像源以加速下载。 | 见下文「可选：镜像源」。 |

---

## 2. 按语言栈的实施要点

### 2.1 Rust 服务

- **BuildKit**：Dockerfile 首行 `# syntax=docker/dockerfile:1`。
- **层顺序**：先 COPY 共享代码与 Cargo.toml + 各 crate，再 `cargo build --release`；最后仅将生成的二进制复制到运行阶段（`COPY --from=builder`），避免把 `target/` 整目录打进镜像。
- **缓存挂载**（示例）：
  - `/usr/local/cargo/registry`：crates.io 下载缓存
  - `/usr/local/cargo/git`：git 依赖缓存
  - `/app/target`（或项目内 target 路径）：Cargo 构建输出，利于增量编译
- **合并 RUN**：运行时阶段将 `apk add` 与 `addgroup/adduser` 等合并为单条 RUN。

### 2.2 Node（前端/Admin 或服务）

- **BuildKit**：首行 `# syntax=docker/dockerfile:1`。
- **层顺序**：先 `COPY package.json package-lock.json*` → `RUN npm ci`，再 `COPY . .` → `RUN npm run build`。仅改前端/业务源码时，依赖层可复用。
- **缓存挂载**：`RUN --mount=type=cache,target=/root/.npm npm ci`（或 `npm install`），重复构建时复用 npm 下载缓存。

### 2.3 Python

- **层顺序**：先 `COPY requirements.txt`（或 pyproject.toml）→ `RUN pip install`，再 `COPY .` → 应用构建/收集静态文件等。
- **缓存挂载**：`RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt`。
- **多阶段**：构建阶段与运行阶段分离，运行阶段仅复制 venv 或安装后的 site-packages 与应用代码。

---

## 3. 使用方式：启用 BuildKit

缓存挂载依赖 **Docker BuildKit**。未启用时构建仍可成功，但不会使用 cache mount，重复构建会较慢。

### 3.1 本机（PowerShell）

```powershell
$env:DOCKER_BUILDKIT=1
docker compose up -d --build
# 或
docker build -t <image> .
```

### 3.2 本机（Bash / Linux）

```bash
export DOCKER_BUILDKIT=1
docker compose up -d --build
```

### 3.3 CI/CD

在 CI 流水线中设置 `DOCKER_BUILDKIT=1`（或使用 `docker buildx build`），以复用缓存、缩短流水线时间。

### 3.4 持久生效（可选）

- **Linux**：在 `~/.bashrc` 或 `/etc/environment` 中设置 `DOCKER_BUILDKIT=1`。
- **Compose V2** 在调用 `docker build` 时会继承当前 shell 的 `DOCKER_BUILDKIT`；`docker buildx build` 默认即为 BuildKit。

---

## 4. 可选：镜像源（国内 / 内网）

若基础镜像或依赖下载较慢，可在 Dockerfile 中增加换源步骤（仅作示例，按实际环境选用）。

### 4.1 Alpine apk（示例：腾讯云镜像）

在 `RUN apk add ...` 之前：

```dockerfile
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tencent.com/g' /etc/apk/repositories
```

### 4.2 npm（示例：腾讯云镜像）

在 `RUN npm ci` 之前：

```dockerfile
RUN npm config set registry https://mirrors.tencent.com/npm/
```

### 4.3 pip（示例）

在 `RUN pip install` 之前：

```dockerfile
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
```

添加后需验证构建与运行均正常，并在 `project/deploy.md` 或项目文档中注明「已为某环境启用某镜像源」。

---

## 5. 维护与扩展

- **新增服务或 Dockerfile**：优先遵循「依赖/清单先复制、源码后复制」「合并 RUN」「需要时使用 BuildKit cache mount」。
- **与 deploy.md 配合**：在 `project/deploy.md` 中写明构建命令、是否启用 BuildKit、以及本规范文档的引用，便于 AI 与人工执行部署前读取。
- **参考**：更完整的通用说明见 [微信云托管 - 如何提高项目构建效率](https://developers.weixin.qq.com/miniprogram/dev/wxcloudservice/wxcloudrun/src/scene/build/speed.html)。

---

*本规范整合自 wsync 项目 BUILD-OPTIMIZATION.md，泛化为协议级通用规则。项目可在 `project/sop/` 或 `project/deploy.md` 中补充项目特有的 Docker 路径与命令。*
