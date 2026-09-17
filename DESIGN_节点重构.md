# new_auto 节点体系重构 · 设计文档

> 状态：设计定稿，待你确认后开始实施
> 日期：2026-09-17
> 起因：33 个节点太多、蓝色数据连线从未用通、烧录时界面黑屏、日志信息不够

---

## 1 · 目标

| 现在的问题 | 重构后 |
|---|---|
| 33 个节点，拖一个"读固件版本"要先找分组 | 常用 8 个，其余收进「高级」 |
| 蓝色数据连线从未用通，但每个节点都挂着端口 | 彻底移除，只留金色执行流 |
| 断言要拖 `flow.assert_value` + 连蓝线 | 断言内置到节点里（I²C 行内「期待值」） |
| 烧录 98 秒界面全黑 | 实时进度条 + 逐行日志流 |
| 日志只有一句 RuntimeError | 每条指令逐字段展开，失败项给完整比对细节 |
| 单步调试会新建 Session，必然失败 | 常驻 Session +「运行到此节点」 |
| 误点连线即删，无法撤销 | 撤销栈 + 自动保存 |

---

## 2 · 已确认的决策

1. **只保留金色执行流**，蓝色数据连线取消；`flow.reroute` / `flow.assert_value` 删除。
2. **断言内置，不引入变量总线**。节点之间不传值。
3. **ini 绑在 `device.open`**：默认继承项目级默认 ini，全局复用；单个节点可显式覆盖。
4. **6 个 `checks.*` → I²C 节点的「常用寄存器」预设**，且预设规则可编辑、可另存。
5. **device 出图与检查节点内部 = 有序可拖拽的操作列表**：右键添加、⇅ 拖拽排序、随时增删。
6. **I²C 表单**：顶部统一 slave ID；下面纵向指令列表；读默认不断言，填了期待值才比；每条指令逐字段展开打印到日志。
7. **固件下载**：ini 未选择时默认继承项目、也可自己指定；bin 默认跑 Release 档，特殊 case 可在节点上显式指定 Debug 或任意文件。
8. **日志格式**：逐字段展开（每条指令 slave/地址/模式/回读/遮罩/右移/期待 逐个标名）。

**本期不做**：循环节点、运行时传参/变量总线、OTP 相关节点的一等公民化（保留但列为高级）。

---

## 3 · 节点面板：33 → 8（+ 高级）

### 3.1 常用 8 个

| # | 节点（新） | 一句话 | 取代了谁 |
|---|---|---|---|
| 1 | `power.ctrl` 电源开关 | 上电/断电/掉电重启，一个下拉 | `relay.on` `relay.off` `relay.power_cycle` `relay.ctrl`(旧四份) |
| 2 | `device.open` 打开设备 | 绑 ini + 自动上电 + 建会话 | `device.configure`（+把「上电」从画布里收进来） |
| 3 | `device.check` 出图与检查 | 节点内可拖拽的有序操作列表 | `device.open_video` `device.grab_save` `device.fps` `device.dn` `image.capture_mean` `image.compare_register` `device.stream` |
| 4 | `device.close` 关闭设备 | 关视频 + 释放句柄 + 可选断电 | `device.close_video`（+ 断电动作） |
| 5 | `i2c.seq` I²C 读写 | 表单式指令列表，断言内建 | `i2c.batch` `i2c.read` `i2c.write` `i2c.write_readback` `i2c.read_regs` `checks.*` 全部 6 个 |
| 6 | `fw.download` 固件下载 | ini + bin 可选，实时进度 | `fw.download` |
| 7 | `flow.delay` 延时 | 等待 N 秒 | `flow.delay` |
| 8 | `flow.log` 打印日志 | 输出一行到运行日志 | `flow.log` |

### 3.2 收进「高级」折叠区（保留可用，旧画布不受影响）

`fw.soc_reboot`、`fw.erase`、`fw.crc_check`、`otp.*` —— 低频但删了会有人找，放在面板底部一个折叠区，默认收起。

### 3.3 删除

`flow.reroute`、`flow.assert_value`（蓝线取消后无存在意义）、
`registry.py` 里 126–250 行那一整段 legacy 继电器定义（已被第 797 行的新版取代，现在只是 `hide_from_palette` 藏着）。

> 旧节点全部**保持可执行** —— 已有画布不会因为重构跑不起来。只是不在面板里显示，也不推荐再用。

---

## 4 · 项目配置模型（config.json 扩展）

新增 `project` 段，作为 ini / 固件的全局默认来源：

```json
"project": {
  "default_ini": "MAT130YV200_max96712_max96701_yuv422_1280x960_30fps_bt601_v1.0.6_1280_880.ini",
  "default_slave": "0x40",
  "firmware": {
    "release": "MAT130A_..._v4.1.7_C0101.bin",
    "debug": null
  },
  "reg_presets": "configs/reg_presets.json"
}
```

- `firmware.debug` 目前为 `null`（fw 目录里只有一个 bin）。有了 debug 固件后在项目页绑定一次，全项目可用。
- `reg_presets` 是「常用寄存器」预设库，独立成 JSON —— **不需要改代码就能增删改预设**，这是你说的"规则要求也能编辑修改"的落点。

### 4.1 ini 继承链

```
config.json → project.default_ini
                 ↓ （未指定时自动继承）
             device.open 节点  ←── 这里是唯一绑定点
                 ↓ （会话建立后成为「当前会话 ini」）
             device.check 节点
             fw.download 节点
             i2c.seq（走会话，不需要 ini）
```

规则：

- 节点参数里 ini 是三态：**继承（默认） / 显式指定某个文件 / 显式指定为无**。UI 上继承项用虚线边框，一眼看得出是跟着上级走。
- `device.open` 改了 ini → 后续节点自动跟着变；某个 `device.check` 单独改了 → 只影响它自己。
- `fw.download` 的 ini 同样是"未选择=继承"，也可以自己指定 —— 按你的答复。

---

## 5 · 节点 Schema

### 5.1 `power.ctrl` 电源开关

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| action | choice | on | 上电 / 断电 / 掉电重启 |
| channel | int | 0 | 继电器通道，继承 config |
| port | str(optional) | 空 | 留空=用 config.json 的 COM9 |
| off_seconds | float | 15 | 仅 cycle 生效，规范 ≥15s |
| wait_after_on | float | 8 | 上电后等固件启动 |

### 5.2 `device.open` 打开设备

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| ini | choice(optional) | 继承项目 | **绑定点** |
| auto_power | bool | true | 自动先上电 |
| wait_open | float | 10 | setConfigure 后等待 |

行为：`ensure_powered()` → `ensure_configured(ini)` → **把 ini 记进会话**（`ctx.current_ini`）。
返回值里带 `handle`，后续所有节点复用同一个句柄。

### 5.3 `device.check` 出图与检查

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| ini | choice(optional) | 继承 open | 通常不动 |
| ops | **有序列表** | [打开视频流] | 见下 |

`ops` 的每一项是一个 `{op, params}` 结构，节点内表现为可拖拽的列表：

| 可选操作 | 参数 | 检查/断言 |
|---|---|---|
| 打开视频流 | — | — |
| 抓帧存图 | 文件名前缀、格式 | 文件存在且非空 |
| 读 FPS | 采样次数 | 可填下限，如 ≥25 |
| 读 DN 亮度 | 采样次数 | 可填上下限，如 50~90 |
| 出图检查 | 黑屏/彩条/冻结判定阈值 | 不通过则该节点失败 |
| 关闭视频流 | — | — |

- 右键节点内部 → 添加一项；已存在的项置灰，避免重复。
- 每项 ⇅ 拖拽换执行顺序；✕ 删除。默认按添加顺序，即视频流边界的自然顺序。
- **列表为空时视为「只确保已配置」**，不至于报错。

### 5.4 `i2c.seq` I²C 读写

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| slave | str | 0x40 | 顶部统一指定，继承 project.default_slave |
| mode | choice | A2D4 | 默认位宽模式 |
| ops | **有序表格** | [] | 见下 |

表格每行：

| 字段 | 说明 |
|---|---|
| 操作 | 读 / 写 / 写并回读校验 |
| 地址 | 手输 0xXXXX，或从「常用寄存器」预设里选 |
| 值 | 仅写/写并校验需要 |
| 模式 | A2D4/A2D2/A1D1…，默认继承节点级 mode |
| 期待值 | **仅读生效；留空=不断言** |
| 遮罩 / 右移 | 默认 0xFFFFFFFF / 0，⚙ 展开后可改 |

**这层表单不改执行引擎** —— 每行一对一编译成现在引擎认的语法：

| 表格里的操作 | 编译结果 |
|---|---|
| 读（期待留空） | `read addr mode` |
| 读 + 期待值 | `expect addr exp mask shift mode` |
| 写 | `write addr val mode` |
| 写并回读校验 | `verify addr val mode` |

断言语义沿用现有实现：`(回读 & 遮罩) >> 右移 == 期待`。
「读 + 期待」合并成**一条**指令而不是「读、断言」两条 —— 一行表格 = 一行指令 = 一段日志，不存在"这次读在哪断言"的歧义。

### 5.5 `fw.download` 固件下载

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| tier | choice | release | Release / Debug / 手动指定 |
| bin | choice(optional) | 随 tier | 选 Debug 时也可手改 |
| ini | choice(optional) | 继承项目 | 按你的答复：未选择=继承，也可指定 |
| retries | int | 3 | |
| confirm | bool | false | 防误烧，保持 |
| power_cycle_after | bool | true | 烧完掉电重启 |

选 Release/Debug 时自动带出项目绑定的 bin；Debug 未绑定时给明确提示而不是静默失败。

---

## 6 · 实时日志

### 6.1 为什么现在是黑的

- `modules/firmware.py:268` 的 `download()` 早就支持 `on_event(status, progress, err)` 回调，但 `fw.download` 节点调用时**没传**。
- 即便传了也没用：`run_canvas` 的 `on_event` 只在节点**开始/结束**时触发，前端 500ms 轮询一次，中间 98 秒没有任何数据。

### 6.2 事件协议

节点内部通过 `ctx.emit(...)` 往外推，字段是**结构化**的，不是拼好的字符串：

```json
{"ts": 1789..., "event": "log", "node": "n4", "seq": 1,
 "level": "info", "kind": "i2c.read", "result": "fail",
 "fields": {"地址":"0x0000", "模式":"A2D4", "回读":"0x00000000",
            "遮罩":"0xFFFFFFFF", "右移":0, "期待":"0x00000001"}}
```

| event | 用途 |
|---|---|
| `start_total` / `start` / `finish` / `done` | 现有四种，保留 |
| `log` | 一条结构化日志，按下面的格式渲染 |
| `progress` | `{phase, pct, detail}` → 进度条 |

结构化字段换来三件事：搜索 `0x00d8` 能命中、可以「只筛失败」、换排版不用改节点代码。

### 6.3 渲染格式（你选的逐字段展开）

```
[10:22:31.004] I²C 序列开始 · slave=0x40 · 共 4 条

[10:22:31.006] [1] READ
    slave    0x40
    地址     0x0000
    模式     A2D4
    回读     0x00000000
    遮罩     0xFFFFFFFF
    右移     0
    期待     0x00000001
    ✗ 断言失败 — 期望 0x00000001，实际 0x00000000，(回读 & 0xFFFFFFFF) >> 0 = 0x0
```

- 遮罩/右移仅在非默认值（即 ⚙ 改过）时打印，免得每条都多两行。
- 失败项统一给一个红框，写清期望/实际/中间计算，可直接抄去查寄存器。
- 长序列用面板上的「折叠已通过项」收敛，只留失败项和手动点开的那条。

### 6.4 面板布局

画布下方固定 dock，可拖拽高度、可全屏；三个标签：

- **运行日志** —— 上面的格式
- **节点输出** —— 每个节点的返回（图片路径、FPS、DN、句柄）完整展示，可展开大图
- **历史** —— 每次运行存一份，可回看、导出 Markdown、相邻两次 diff 看寄存器有没有漂移

工具栏：全部 / 仅失败、🔍 搜索、折叠已通过、导出。

---

## 7 · 执行引擎改动

### 7.1 常驻 Session

现在 `/api/run_node`（单步调试）每次 `Session()` 新建、`finally` 里 `ctx.close()` —— **所以单独跑中间节点必然失败**（设备没上电、没 configure），而且每次多花一轮开句柄的时间。

改成：

- 服务维护一个常驻 Session，有明确的 **闲置超时**（建议 10 分钟无操作自动释放）。
- 面板上提供「打开会话 / 复用会话 / 释放会话」三个动作，状态在顶栏可见。
- 新增 **「运行到此节点」**：按拓扑顺序把目标节点的上游依赖链跑一遍再停在目标节点，会话状态全程保留。这才是调用例该有的姿势。

### 7.2 事件直通

`run_canvas` 已支持 `on_event`，扩展：`executor` 把 `ctx.emit` 收到的事件原样喂给 `on_event`；`server.py` 加 SSE 端点 `/api/runs/<id>/stream`，前端改订阅 SSE，不再轮询。

---

## 8 · 画布兼容性

- **旧节点全部保留可执行**，已有画布不动。
- 新画布用新节点；旧画布里的 `checks.*` / `i2c.*` 继续能跑，只是面板里找不到。
- 蓝线移除：前端不再渲染数据端口，**但 JSON 里已有的 `edges` 数据连线继续执行** —— 万一有老用例依赖它不会突然崩。新画布则不再产生这种连线。
- 可选：写一个 `scripts/migrate_canvas.py`，把 `checks.fw_version` 之类批量翻译成 `i2c.seq` 的一行预设。需要迁移再写，不迁也不影响运行。

---

## 9 · 文件改动清单

| 文件 | 改动 |
|---|---|
| `config.json` | 新增 `project` 段 |
| `configs/reg_presets.json` | 新增：常用寄存器预设库 |
| `modules/firmware.py` | `download()` 的 `on_event` 加进度节流（避免每扇区一条刷屏） |
| `app/engine/session.py` | `ctx.emit()`、`ctx.current_ini`、`ctx.current_slave`、句柄复用与显式 release |
| `app/engine/registry.py` | 删 legacy 块(126–250)；重写 8 个节点；旧节点保持注册 |
| `app/engine/executor.py` | 事件中转、超时表更新、支持「运行到此节点」的入口 |
| `app/engine/codegen.py` | 同步新节点/新参数生成（`app/cases/*.py` 要能继续生成） |
| `app/server.py` | 会话管理 `/api/session/*`、SSE `/api/runs/<id>/stream`、运行历史存档、预设 CRUD |
| `app/web/app.js` | 拆模块；移除蓝线渲染；撤销栈；自动保存；I²C 表单；拖拽列表；日志面板 |
| `app/web/style.css` | 配套样式 |
| `app/web/index.html` | 面板 DOM（含日志 dock + 项目配置页） |

> `app.js` 现在单文件 953 行，这轮会再长一截。建议顺手按 `canvas / palette / inspector / logpanel / api` 拆成 ES module，否则后面没人敢改。

---

## 10 · 分阶段落地

| 阶段 | 内容 | 验收（真机） |
|---|---|---|
| **S1 事件总线** | `ctx.emit` + SSE + 日志面板 + fw 进度 | 烧一次固件，界面上能看到 erase→program→verify 实时滚动，不再是黑屏 |
| **S2 节点收敛** | 8 个新节点 + 移除蓝线 + 常驻 Session + 运行到此节点 | 单独跑 `i2c.seq` 节点能成功（现在必失败）；画布里看不到任何蓝色端口 |
| **S3 I²C 表单** | 表格编辑器 + 预设库 + 逐字段日志 | 重跑「读版本+断言 v4」，日志按新格式输出；改一次断言故意失败，看红框信息是否够查 |
| **S4 配置与继承** | 项目配置页 + ini 继承链 + Release/Debug | 项目页改一次默认 ini，所有下游节点跟着变；单独覆盖一个节点，只有它变 |
| **S5 编辑器防误操作** | 撤销/重做 + 自动保存 + 脏标记 + 历史留存导出 | 误删连线 Ctrl+Z 能回来；改完不保存切画布有提示并能恢复 |

顺序的理由：S1 单独就能解决最疼的黑屏问题，且不影响现有节点；S2 是这轮的主体；S5 风险最低，放最后不影响主线。

---

## 11 · 风险与待确认

1. **Debug 固件目前不存在** —— `fw` 目录里只有一个 bin。项目配置页会先留空，等有文件再绑。
2. **`app.js` 拆分**会和 S2–S5 同时动，建议 S2 开工前先把文件拆完，否则后面合并成本高。
3. **常驻 Session 的释放时机** —— 闲置太久不释放会占着 COM9 和设备句柄；太早释放又失去"调试"的意义。先定 10 分钟闲置超时，用下来再调。
4. **`device.check` 的 ops 列表序列化** —— 这是画布 JSON 里第一次出现嵌套列表结构，迁移/回滚要留意（`checks.*` 老节点不受影响）。
5. 待你确认：**8 个常用节点里 `flow.log` 是否还需要单独存在** —— 有完整日志以后它基本没用了，我倾向删掉，省一个格子。
