# new_auto — PixelIDE(PixieDE) 硬件接口模块化封装

把旧工程 `fw_auto_copy` 中散落的 PixelIDE 底层 DLL 调用，按功能最小化打包为五个独立小模块，
并全部在真机（继电器 COM3/CH0 + MAT130YV200 模组 + MAX96712 解串器）上调试通过。

## 目录结构

```
new_auto/
├── README.md                 本文件
├── REPORT.md                 模块梳理与验证报告（交付物）
├── config.json               现场硬件配置（继电器/设备/ini/固件 绑定关系）
├── modules/                  五个功能模块
│   ├── sdk.py                DLL 加载 + 全部函数原型绑定 + 错误码助手（公共底层）
│   ├── relay.py              (a) 继电器控制
│   ├── device.py             (b) 外部设备控制
│   ├── i2c.py                (c) I2C 读写
│   ├── firmware.py           (d) 固件下载（一键下载 + Flash 级操作 + 固件协议）
│   └── log_setup.py          日志 + C++ SDK stdout 噪音过滤
├── bin/                      testlib.dll / MatFwHandler_x64.dll 及基础依赖
├── configs/init_file/        上电初始化 ini（当前绑定: ..._1280_880.ini）
├── fw/                       固件 bin（当前绑定: v4.1.7 JUNGE-A21-JZ9173-SUB）
├── scripts/                  逐模块验证脚本 + 一键全流程
│   ├── common.py             公共: 读配置 / 上电初始化
│   ├── verify_relay.py       验证 1: 继电器
│   ├── verify_device.py      验证 2: 设备出图
│   ├── verify_i2c.py         验证 3: I2C 读写
│   ├── verify_fw_download.py 验证 4: 固件下载（默认 dry-run, --burn 真实烧录）
│   └── run_all.py            一键顺序跑 1→4
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

# 一键验证全部模块（固件下载只做 dry-run，不烧写 flash）
python scripts/run_all.py

# 真实烧录固件下载验证（会重写模组 flash，A/B 双区有掉电保护）
python scripts/run_all.py --burn

# 单独验证某个模块
python scripts/verify_relay.py
python scripts/verify_device.py
python scripts/verify_i2c.py
python scripts/verify_fw_download.py           # dry-run
python scripts/verify_fw_download.py --burn    # 真实烧录
```

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
