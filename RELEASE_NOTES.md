# New Auto 2.3.0（当前版本 / master）

> **版本线说明**：本仓库此前并行存在两条线 ——
> 「发布工程线」`v2.0.0` / `v2.2.0`（追加发版文档与 `.agent/` 治理脚手架，`app/` 代码仍是重构前的旧节点名）
> 与「主线」（本次的节点重构 + AI 助手）。
> **2.3.0 是两条线的合并结果：`master` HEAD 即最新代码，`v2.3.0` 为最新正式版本。**

## Highlights

- 节点收敛为「常用 8 + 高级 3」，重做拓扑执行流（金色执行流定序，失败即停 / 运行到此）。
- 设备一体化节点：开关机 / 出图 / 检查 / 关闭可勾选组合、拖拽排序、右键增删。
- ini 与固件按项目默认继承，单 case 可覆盖（release / debug）。
- I²C 每条指令独立位宽（A2D2 / A2D4 / A4D4）+ 回读值与预期值校验 + 「常用寄存器」预设下拉。
- 单 case 独立日志 / 图片空间（`logs/cases/<case>/{runs,img}`）与一键清空；运行调试台与属性台可自由拖拽伸缩。
- 🤖 AI 助手：自然语言 → 画布（SenseNova OpenAI 兼容端点），生成后校验节点类型与连线，
  掉电或 `fw.download` 后强制补 `device.open`。
- 修复：烧录掉电后设备句柄失效，导致「固件下载」用例必然失败
  （`power_off` / `release_device` 重建句柄 + `ensure_video` 兜底）。
- 新增回归脚本：`smoke_ui.cjs`（38 项断言）/ `ui_probe.cjs` / `verify_i2c_rows.cjs` /
  `verify_full_case.cjs` / `run_case.cjs` / `test_agent.cjs` / `test_ai_ui.cjs`。
- 保留 `v2.2.0` 引入的 `.agent/` 治理脚手架（71 个文件），未做删改。

## Verified hardware result

- 场景：继电器 COM9 / Channel 0 + MAT130YV200 + MAX96712。
- 固件下载用例（掉电烧录 → 重新上电 → I2C 回读）：5/5 通过，回读 `0x00d8` = `0x1040107`（v4.1.7）。
- AI 助手生成画布：结构校验 4/4，`--run` 真机 4 节点全过；真实浏览器 UI 全流程 5/5。
- 前端冒烟：38/38。

## Known issues

- `tests/test_relay.py`、`tests/test_agent.py` 是按 2.0.0 的 `RelayController(..., transport=)` 与
  `agent.agent_status()` 接口写的；本版的 `modules/relay.py`（SDK-only）与 `app/engine/agent.py`
  已不提供这两个接口，需改写后才能跑通。2.0.0 的实现完整保留在 tag `v2.0.0`。
- `modules/relay.py` 沿用主线实现（仅 SDK 传输，已真机验证）；
  2.0.0 线的 SDK + `serial_a0` 双传输抽象未并入，如需保留可从 `v2.0.0` 取回。
- `dist/new_auto-2.0.0-windows-x64.zip` 为 2.0.0 的打包产物，本版未重新打包。

---

# New Auto 2.2.0（历史：发布工程线）

在 2.0.0 之上引入 `.agent/` 治理脚手架（工作流 / 规范 / CI 模板 / 校验脚本，共 71 个文件），
`app/` 代码未改动。本版本不推荐单独使用，内容已由 2.3.0 完整承接。

---

# New Auto 2.0.0（历史）

## Highlights

- 画布编辑器采用工业控制台视觉，支持节点搜索、运行监控和数据连线。
- AI 用例生成入口、模型状态与本地 Key 状态可见。
- 继电器改为 PixelIDE SDK 真实控制，不再使用无回执的 A0 串口假成功判断。
- 新增 `case333` 真机演示：出图、FPS 数据断言、I2C 固件版本数据断言。

## Verified hardware result

- Channel 0：SDK 断电 15 秒后重新上电成功。
- 真机出图：成功，FPS 25.01，DN 71.71。
- 固件主版本断言：4，通过。
