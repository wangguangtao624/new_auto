# new_auto — PixelIDE(PixieDE) 硬件接口模块化封装 + 拖拽式流程工具

把旧工程 `fw_auto_copy` 中散落的 PixelIDE 底层 DLL 调用，按功能最小化打包为独立小模块，
全部在真机（继电器 COM3/CH0 + MAT130YV200 模组 + MAX96712 解串器）上调试通过。

**v1.0.2 新增**: 拖拽式自动化流程画布（画布=case，节点=模块调用，自由连线组合，
一键运行/生成 Python 用例代码），以及 image / otp / checks 三个补充模块。

## 目录结构

```
new_auto/
├── README.md                 本文件
├── REPORT.md                 模块梳理与验证报告
├── config.json               现场硬件配置（继电器/设备/ini/固件 绑定关系）
├── modules/                  八个功能模块
│   ├── sdk.py                DLL 加载 + 全部函数原型绑定 + 错误码助手（公共底层）
│   ├── relay.py              继电器控制 (串口 COM3, 通道级通断)
│   ├── device.py             外部设备控制 (ini 配置, 出图, 抓帧, FPS/DN, 帧ID)
│   ├── i2c.py                I2C 读写 (寄存器级/字节流级, A2D2/A2D4/A4D4)
│   ├── firmware.py           固件下载 (MatFwDownload + Flash 擦写/校验/固件协议)
│   ├── otp.py                OTP 读写 (读/存文件/写[需确认]/功能标志)      [v1.0.2]
│   ├── image.py              图像抓取与对比 (亮度均值, 寄存器改值前后对比) [v1.0.2]
│   ├── checks.py             固件状态检查 (版本/启动区/帧计数/算法/功能安全) [v1.0.2]
│   └── log_setup.py          日志 + C++ SDK stdout 噪音过滤
├── app/                      拖拽式自动化流程工具 (v1.0.2)      ← python app/server.py
│   ├── server.py             本地服务 (纯标准库): REST API + 静态页
│   ├── engine/
│   │   ├── registry.py       节点注册表 (28 种节点: 电源/设备/I2C/图像/固件/检查/流程)
│   │   ├── session.py        硬件会话 (继电器/设备/I2C 懒加载复用, 幂等上电/配置/出图)
│   │   ├── executor.py       拓扑执行引擎 (数据沿连线传递, 失败即停)
│   │   └── codegen.py        画布 JSON → Python 用例代码
│   ├── web/                  节点编辑器前端 (原生 JS + SVG, 无构建依赖)
│   ├── canvases/             画布 JSON (每个画布 = 一个 case)
│   └── cases/                生成的 Python 用例脚本
├── bin/                      testlib.dll / MatFwHandler_x64.dll 及基础依赖
├── configs/init_file/        上电初始化 ini（当前绑定: ..._1280_880.ini）
├── fw/                       固件 bin（当前绑定: v4.1.7 JUNGE-A21-JZ9173-SUB）
├── scripts/                  逐模块真机验证脚本 + run_all
└── logs/                     运行日志与抓帧输出
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
| 继电器 | COM3（CH34x USB 串口），模组供电走 Channel 0 |

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
#  左侧节点面板拖到画布 → 圆点连线 → 属性面板改参数 → ▶ 运行
#  「⇩ 生成代码」把画布固化为 app/cases/<case名>.py, 可脱离界面直接运行

# === 命令行验证 ===
python scripts/run_all.py                # 全模块验证 (固件下载 dry-run)
python scripts/run_all.py --burn         # 全模块验证 (固件下载真实烧录)
python scripts/verify_relay.py           # 单独验证继电器
python scripts/verify_device.py          # 单独验证设备出图
python scripts/verify_i2c.py             # 单独验证 I2C
python scripts/verify_fw_download.py     # 固件下载 dry-run (--burn 真实烧录)
```

## 拖拽式工具节点一览 (30 种)

| 分组 | 节点 |
|---|---|
| 电源模块 | **继电器电源**（上电/断电/掉电重启 三合一, 断电间隔可调, 支持指定串口+通道） |
| 设备模块 | 下发 ini 配置 / **设备出图(集成)**（视频流 + 可选勾选: 抓帧存图/读FPS/读DN） |
| I²C 模块 | **I2C 读写模块**（读/写/写并校验一体，可选回读校验）/ 读寄存器(单) / 写寄存器 / 写后回读校验 / 批量读（位宽 A1D1~A4D4 任选） |
| 检查模块(图像) | 抓帧测亮度 / 寄存器改值前后亮度对比（自动恢复原值） |
| 固件模块 | 一键下载(需勾选确认) / SOC 重启 / 擦除扇区 / Flash CRC |
| 检查模块 | 固件版本 / 启动状态 / 帧计数器 / AWB·AE 开关 / 功能安全 / 时钟切换 |
| 流程工具 | 延时 / 打印日志 / 数值断言 / **转接点**(理线) |

### 画布交互 (ComfyUI 风格)

- **执行流端口**: 每个节点顶部两角有金色方块端口 —— 左上=执行流入(上游), 右上=执行流出(下游)。
  金色粗线箭头即执行顺序; 未连线的节点按画布位置(从上到下)追加执行
- **数据端口**: 两侧蓝色圆点, 传值 (如 i2c 读到的 value → 断言的 value), 连线值优先于节点参数
- **平移画布**: 鼠标按住空白处拖动
- **右键新建**: 画布空白处右键 → 按分组选节点, 直接落到鼠标位置 (面板项也可双击添加)
- **单步调试**: 每个节点标题栏有 ▶ 按钮, 只运行该节点并就地显示结果;
  继电器节点另有「扫描串口(子进程探测各 COM 口的继电器响应/可用通道)」
  和「测试通道响应(通→断→通)」调试动作, I2C 模块可选写后回读校验

- **画布 = case**: 新建画布即新建用例, 不同 case 只是流程与参数不同
- **自由连线**: 节点输出圆点拖到输入圆点即形成数据流 (如 i2c.read 的 value → 断言的 value), 连线值优先于节点参数
- **运行监控窗口**: 画布底部实时日志坞 —— 逐节点推送 执行中/通过/失败 及输出值,
  节点徽章同步点亮(⏳/✓/✗), 绿/黄/红状态灯; 运行改为异步+轮询, 全程可观测
- **丝滑连线**: 执行流端口位于节点标题栏两侧(左入右出), 贝塞尔曲线对反向连线做了平滑处理
- **图片预览**: 顶栏 🖼 图片 打开抓帧图库 (UYVY/raw16 自动转 PNG 缩略图, 点击看大图)
- **🤖 AI 助手** (右侧面板): 对话描述用例 → 调用 SenseNova 大模型 → 自动生成画布 → 一键应用 → 运行。
  模型可在面板下拉切换 (deepseek-v4-flash / glm-5.2 / kimi-k3 等);
  API key 放在 app/agent_key.local (gitignore, 也可用环境变量 SENSENOVA_API_KEY)
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
relay = RelayController("COM3")
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

1. **继电器 COM 口释放延迟**：Python 进程异常退出（如 Ctrl+C 强杀）后 COM3 需数秒
   才释放，期间 `get_switcher` 返回 NULL；模块内 `RelayController` 构造与
   `ensure_open` 已带重试。
2. **DLL 加载噪音**：testlib.dll 加载/卸载时 C++ 侧直接往控制台写少量
   `[dllmain.cpp]` 日志（绕过 Python stdout，无法在 Python 层过滤），无实际影响。
3. **聚焦通道**：单通道采集卡上 `get_device_focus_channel` 返回空串，
   `set_focus_channel("")` 自动跳过（多通道卡时会返回 `MU960#...` 并可切换）。
4. **掉电时序**：断电后必须保持 **≥15s** 再上电（旧工程规范），
   上电后固件启动约需 5~10s。
