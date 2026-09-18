# new_auto — PixelIDE(PixieDE) 硬件接口模块化封装 + 拖拽式流程工具

把旧工程 `fw_auto_copy` 中散落的 PixelIDE 底层 DLL 调用，按功能最小化打包为独立小模块，
全部在真机（继电器 COM9/CH0 + MAT130YV200 模组 + MAX96712 解串器）上调试通过。

**v2.3.0（当前版本）主要变更**: 节点收敛为「常用 8 + 高级 3」并重做拓扑执行流；设备一体化节点、
ini/固件按项目默认继承、I²C 每条指令独立位宽 + 回读断言 + 常用寄存器预设；
单 case 独立日志/图片空间与一键清空；运行台与属性台可拖拽伸缩；
🤖 AI 助手（自然语言 → 画布，掉电后自动补 `device.open`）；
修复烧录掉电后设备句柄失效导致「固件下载」用例必失败的问题。

## 目录结构

```
new_auto/
├── README.md                 本文件
├── REPORT.md                 模块梳理与验证报告
├── config.json               现场硬件配置（继电器/设备/ini/固件 绑定关系）
├── modules/                  八个功能模块
│   ├── sdk.py                DLL 加载 + 全部函数原型绑定 + 错误码助手（公共底层）
│   ├── relay.py              继电器控制 (串口 COM9, 通道级通断)
│   ├── device.py             外部设备控制 (ini 配置, 出图, 抓帧, FPS/DN, 帧ID)
│   ├── i2c.py                I2C 读写 (寄存器级/字节流级, A2D2/A2D4/A4D4)
│   ├── firmware.py           固件下载 (MatFwDownload + Flash 擦写/校验/固件协议)
│   ├── otp.py                OTP 读写 (读/存文件/写[需确认]/功能标志)      [v1.0.2]
│   ├── image.py              图像抓取与对比 (亮度均值, 寄存器改值前后对比) [v1.0.2]
│   ├── checks.py             固件状态检查 (版本/启动区/帧计数/算法/功能安全) [v1.0.2]
│   ├── case_store.py         用例产物存储: logs/cases/<case>/{runs,img} 读写/清空 [v1.0.4]
│   └── log_setup.py          日志 + C++ SDK stdout 噪音过滤
├── app/                      拖拽式自动化流程工具 (v1.0.4)      ← python app/server.py
│   ├── server.py             本地服务 (纯标准库): REST API + 静态页
│   ├── engine/
│   │   ├── registry.py       节点注册表 (常用 8 + 高级 3, 旧节点仍可执行)
│   │   ├── session.py        硬件会话 (继电器/设备/I2C 懒加载复用, 幂等上电/配置/出图)
│   │   ├── executor.py       拓扑执行引擎 (金色执行流定序, 失败即停/运行到此)
│   │   └── codegen.py        画布 JSON → Python 用例代码
│   ├── web/                  节点编辑器前端 (原生 JS + SVG, 无构建依赖)
│   ├── canvases/             画布 JSON (每个画布 = 一个 case)
│   └── cases/                生成的 Python 用例脚本
├── bin/                      testlib.dll / MatFwHandler_x64.dll 及基础依赖
├── configs/init_file/        上电初始化 ini（当前绑定: ..._1280_880.ini）
├── configs/reg_presets.json  I²C「常用寄存器」预设
├── fw/                       固件 bin（当前绑定: v4.1.7 JUNGE-A21-JZ9173-SUB）
├── scripts/                  真机验证脚本 + 前端冒烟/布局探针 (见「快速开始」)
└── logs/                     运行日志、抓帧输出
    ├── cases/<case>/runs     本 case 的每次运行报告 + 逐字段事件 (JSON, 可导出 MD)
    ├── cases/<case>/img      本 case 的抓帧图片
    ├── img/                  未绑定 case 时的兜底图片目录 (旧产物)
    └── runs/                 旧版运行历史 (首次启动自动迁移进 cases/)
```

## ⚠️ 硬件绑定关系（重要）

**当前模组 ↔ 固件 ↔ ini 三者绑定，成对使用：**

| 项目 | 值 |
|---|---|
| 模组 | MAT130 YV200（板载 MAX96701 串行器，经 MAX96712 解串器入采集卡） |
| 绑定固件 | `fw/MAT130A_JUNGE-A21-JZ9173-SUB_DVP_24M_78M_1280x880@25fps_YUV422_0022_v4.1.7_C0101.bin` |
| 绑定 ini | `configs/init_file/MAT130YV200_max96712_max96701_yuv422_1280x960_30fps_bt601_v1.0.6_1280_880.ini` |
| 固件 I2C Slave | **0x40**（注意： Slave ID 为 0x60 的旧固件配 0x40 的 ini 会导致 I2C 完全不通） |
| 出图规格 | 1280×880 YUV422 25fps（BT601 并口） |
| 继电器 | COM9（CH34x USB 串口），模组供电走 Channel 0 |

其它 ini 均已清理，换模组/换固件时必须同步更新 `config.json` 的
`device.init_file` 与 `firmware.fw_file`。

## 环境要求

- Windows x64，Python 3.12（依赖: pyserial；numpy/cv2 仅图像处理用到）
- **testlib.dll 必须从完整 PixelIDE 部署目录加载**（它依赖部署目录里的
  `device.dll` / `imageviewer.dll` 等运行时，`bin/` 下 8 个 DLL 不自足）。
  `modules/sdk.py` 按以下顺序查找：
  1. `config.json` 或代码中显式指定的 `pixelide_dir`
  2. `F:\Duxin\IDE_resently\pixelide_release\PixelIDE`（本机完整部署，自动探测）
  3. `D:\PixelIde\pixelide_release\PixelIDE`（旧工程默认路径）
  4. `new_auto/bin`（兜底）

## 快速开始

```bash
cd new_auto

# === 拖拽式流程画布 (推荐) ===
python app/server.py           # 打开 http://127.0.0.1:8765
#  左侧节点面板拖到画布 → 金色端口连执行流 → 属性面板改参数 → ▶ 运行
#  「⇩ 生成代码」把画布固化为 app/cases/<case名>.py, 可脱离界面直接运行
#  注意用 python3.12: C:\Users\<你>\AppData\Local\Programs\Python\Python312\python.exe
#  (或双击 start.bat, 会自动挑带依赖的解释器)

# === 命令行验证 ===
python scripts/run_all.py                # 全模块验证 (固件下载 dry-run)
python scripts/run_all.py --burn         # 全模块验证 (固件下载真实烧录)
python scripts/verify_relay.py           # 单独验证继电器
python scripts/verify_device.py          # 单独验证设备出图
python scripts/verify_i2c.py             # 单独验证 I2C
python scripts/verify_fw_download.py     # 固件下载 dry-run (--burn 真实烧录)

# === 界面 / 用例回归 (需要服务已在 8765 跑着) ===
#  jsdom, 不用开浏览器 —— 改完 app.js / index.html 先跑这个, 38 项断言
node scripts/smoke_ui.cjs
#  真实 Chromium 量布局: 面板伸缩、坞高、I2C/操作列表行高; --shot 顺便截图
node scripts/ui_probe.cjs --types i2c.seq,device.check --shot logs/_probe
#  真机回归: 逐条位宽模式 + 回读断言 (建临时画布, 跑完删掉)
node scripts/verify_i2c_rows.cjs
#  真机回归: 跑完整示例用例, 检查产物是否落进 logs/cases/<case>/
node scripts/verify_full_case.cjs
#  跑任意一个画布并逐节点打印日志 (最省事的真机回归, 例: 固件下载用例)
node scripts/run_case.cjs "gujian xiazai"
#  AI 助手: 自然语言 → 画布, 校验节点类型/连线/掉电后重开设备; --run 再真机跑一遍
node scripts/test_agent.cjs
node scripts/test_agent.cjs --run
#  AI 助手 UI 全流程 (真实浏览器: 切面板 → 发送 → 等生成 → 出现「应用到画布」)
node scripts/test_ai_ui.cjs --shot logs/_ai
```

> 前端脚本依赖 jsdom / puppeteer-core，装在
> `C:\Users\<你>\.workbuddy\binaries\node\workspace\node_modules`，跑之前需要
> `NODE_PATH` 指向它（Windows 路径用反斜杠 + 分号分隔）。

## 拖拽式工具节点（收敛后 · 常用 8 + 高级 3）

> 完整设计见 `DESIGN_节点重构.md`。面板只显示下表中的节点；细分旧节点（relay.on/off、
> device.grab_save、i2c.read/write、checks.* 等）**仍然可执行**，只是不再出现在面板里 ——
> 旧画布不受影响。

| # | 节点 | 干什么 | 取代了 |
|---|---|---|---|
| 1 | `power.ctrl` 电源开关 | 上电 / 断电 / 掉电重启，一个下拉 | relay.on / off / power_cycle |
| 2 | `device.open` 打开设备 | **绑 ini（默认继承项目）+ 自动上电 + 建会话** | device.configure |
| 3 | `device.check` 出图与检查 | 节点内**可拖拽排序**的操作列表：开视频流 / 抓帧 / 读FPS / 读DN / 出图检查(亮度·冻结) / 关流 | open_video, grab_save, fps, dn, image.* |
| 4 | `device.close` 关闭设备 | 关视频 + 释放句柄（可顺带断电） | close_video |
| 5 | `i2c.seq` I²C 读写 | 顶部统一 Slave ID；下面纵向指令表，读可填「期待值」做断言 | i2c.rw/read/write/write_readback/batch + checks.* 6 个 |
| 6 | `fw.download` 固件下载 | ini 默认继承项目；bin 默认跑 **Release**，特殊 case 可手动指定 Debug | fw.download |
| 7 | `flow.delay` 延时 | 等待 N 秒 | flow.delay |
| 8 | `flow.log` 打印日志 | 输出一行 | flow.log |
| 高级 | `fw.soc_reboot` / `fw.erase` / `fw.crc_check` | 低频固件操作，面板底部折叠 | 同左 |

### ini 与固件的继承链

```
config.json → project.default_ini / project.firmware.{release,debug}
                 ↓ 未选则继承
             device.open（唯一绑定点） → 下游 device.check / fw.download 继承
```

改一次项目配置，全项目跟着变；单个 case 要换 ini / 换固件，在节点上单独改。

### 画布交互

- **只有金色执行流**（左上入 / 右上出，贝塞尔连线）。**蓝色数据连线已移除** ——
  断言写在节点内部：I²C 行的「期待值」、检查项的上下限。旧画布里残留的蓝线仍保留执行（淡虚线）。
- **I²C 表格**：顶部统一 Slave ID；每行 = 一条指令，**每行都自带「类型」和「位宽」两组下拉**
  （类型：读 / 读并校验 / 写 / 写并回读校验；位宽：a1d1 … a4d4）—— 不会因为选了 A2D4 就整表都是 A2D4。
  读默认**不断言**，填了「期待值」才比较 —— 语义是 `(回读 & 遮罩) >> 右移 == 期待`，遮罩默认全等。
  ⚙ 可展开改遮罩/右移/单独 slave；⠿ 拖拽改执行顺序；「常用寄存器 ▾」直接插入预设；⤓ 把某行存为预设。
  节点参数「某条校验不通过时」= 立即停止（默认）/ 继续执行剩余指令（跑完再汇总报错）。
- **Device 操作列表**：第一行选操作，参数固定跟在下面一行；⠿ 拖拽换顺序，✕ 删除。
- **面板自由伸缩**：下方运行台**上边缘**可上下拖，右侧属性台**左边缘**可左右拖（双击边缘复位，
  尺寸记在 localStorage）。运行台分三栏：**运行日志 / 图片 / 历史**。
- **本 case 独立空间**：一个画布 = 一个 case，产物落在 `logs/cases/<case>/runs`（每次运行的报告+逐字段事件）
  与 `logs/cases/<case>/img`（抓帧图）。「🗑 清空本 case ▾」一键清掉它的日志 / 图片 / 全部，
  **只影响这个 case**，别的 case 不动。
- **防误操作**：单击连线只是**选中**，按 Delete 才删；Ctrl+Z / Ctrl+Shift+Z 撤销重做；
  改动 1.5 秒后**自动保存**，顶栏 ● 表示尚未保存。
- **运行到此**：选中节点 → 顶栏「⤵ 运行到此」—— 把它依赖的上游节点先跑一遍再停在这里，
  设备保持上电/已配置状态，改参数后可直接再跑。属性面板里还有「重开会话 / 释放会话」。
- **实时日志坞**：SSE 推送，每条指令**逐字段展开**打印（slave/地址/模式/回读/遮罩/右移/期待）；
  支持 全部|仅失败、折叠已通过、搜索、导出 Markdown；固件烧录有**实时进度条**。
- **运行历史**：顶栏 🕘 历史看全部 case；运行台的「历史」栏只看当前 case，可回看、导出 MD、删除。
- **项目配置**：顶栏 ⚙ —— 默认 ini、Release/Debug 固件、**常用寄存器预设**（直接在表里改，或把某行存为预设）。
- **图片预览**: 顶栏 🖼 图片 打开抓帧图库 (UYVY/raw16 自动转 PNG 缩略图, 点击看大图)
- **🤖 AI 助手** (右侧面板): 对话描述用例 → 调用 SenseNova 大模型 → 自动生成画布 → 一键应用 → 运行。
  模型可在面板下拉切换 (deepseek-v4-flash / glm-5.2 / kimi-k3 等);
  API key 放在 app/agent_key.local (gitignore, 也可用环境变量 SENSENOVA_API_KEY)。
  生成时会喂给模型当前**可见节点**的精简 schema, 并约束它「掉电后必须重新 device.open」;
  模型偶尔会漂, 后端 `normalize_canvas()` 会兜底过滤非法节点类型/参数、丢弃悬空连线
- **节点超时保护**: 硬件无响应 (如抓帧卡死) 时节点按超时判失败并继续流程, 不再无限挂起
- **跨画布复用**: 选中节点 Ctrl+C 复制, 切到其它画布 Ctrl+V 粘贴 (每个画布是独立 case, 画布之间不能直接连线)
- **代码固化**: 「生成代码」输出与画布同语义的 Python 脚本, 进版本库即可做回归

## 模块用法速览

```python
from modules.relay import RelayController
from modules.device import PixelDevice
from modules.i2c import I2CController
from modules.firmware import FirmwareDownloader, FirmwareFlasher

# (a) 继电器
relay = RelayController("COM9")
relay.open()
relay.open_channel(0)          # 模组上电
relay.power_cycle(0)           # 断电 15s → 上电
relay.close()

# (b) 外部设备
dev = PixelDevice("MAT130YV200")
dev.set_configure("configs/init_file/MAT130YV200_max96712_max96701_..._1280_880.ini")
dev.open(); dev.open_video(); dev.grab_frame()
print(dev.get_fps())
dev.close(); dev.release()

# (c) I2C（默认 slave 0x40）
i2c = I2CController(dev, default_slave=0x40)
ok, ver = i2c.read(0x00d8, addr_len=16, bits=32)   # 固件版本
i2c.write(0x0918, 0x0001)                          # 16位地址/16位数据
ok, data = i2c.read_bytes(0x00d8, 4)               # 字节流读(增补接口)

# (d) 固件下载
dl = FirmwareDownloader()
dl.download("configs/init_file/....ini", "fw/....bin")   # 一键下载(带进度回调/重试)

ff = FirmwareFlasher(dev)                                # Flash 级手工流程
ff.soc_reboot(); ff.erase_flash(0, 63)
ff.set_start_address(0); ff.download_from_file("fw/....bin", 0, 0, 63)
```

## 已知注意事项

1. **继电器 COM 口释放延迟**：Python 进程异常退出（如 Ctrl+C 强杀）后该 COM 口需数秒
   才释放，期间 `get_switcher` 返回 NULL；模块内 `RelayController` 构造与
   `ensure_open` 已带重试。
2. **DLL 加载噪音**：testlib.dll 加载/卸载时 C++ 侧直接往控制台写少量
   `[dllmain.cpp]` 日志（绕过 Python stdout，无法在 Python 层过滤），无实际影响。
3. **聚焦通道**：单通道采集卡上 `get_device_focus_channel` 返回空串，
   `set_focus_channel("")` 自动跳过（多通道卡时会返回 `MU960#...` 并可切换）。
4. **掉电时序**：断电后必须保持 **≥15s** 再上电（旧工程规范），
   上电后固件启动约需 5~10s。
5. **模组掉电/烧录后设备句柄必须重建**（排查很久的一个坑）：`PixelDevice` 句柄在模组
   掉电重启或固件烧录后，DLL 侧已经失效，但 `device_open()` **仍然返回 True**，
   只有 `device_open_video()` / I2C 会失败，且 `last_error()` 是空串 —— 现象是
   「打开设备显示成功，一出图就 `device_open_video 失败`」。
   `Session.power_off()` 现在会先调 `release_device()` 释放句柄，下次 `device()` 重新
   `get_device`；`ensure_video()` 里还有一层「失败则重建句柄重试一次」的兜底。
   **所以：任何会在运行中掉电的流程（固件下载、上下电切换），后面必须跟一个
   `device.open` 节点**，不能指望复用旧连接。
