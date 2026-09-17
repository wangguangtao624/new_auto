# new_auto 模块梳理与调试验证报告

> 日期: 2026-09-13 ｜ 源工程: `F:\01_test\fw_auto_copy` ｜ 交付目录: `F:\01_test\new_auto`
>
> 现场硬件: 继电器 COM9/CH0 ＋ MAT130 YV200 模组（板载 96701 串行器）＋ MAX96712
> 解串器 ＋ Dothinkey(MU960) 采集卡；模组固件 v4.1.7（I2C Slave **0x40**）

---

## 一、总体结论

已逐行通读旧工程 `fw_auto_copy/src`（main.py、libs/device_sdk.py、libs/test_function.py、
tests/conftest.py、7 个 functional 测试文件），把其中**所有外部库接口调用**按功能
最小化打包为 5 个模块放进 `new_auto/modules/`，并编写逐模块验证脚本。

**五大模块全部在真机上调试通过**（验证方式见第三节）：

| 模块 | 真机结果 |
|---|---|
| (a) 继电器 `modules/relay.py` | ✅ PASS（COM9 全通道开/关、CH0 通断、掉电重启） |
| (b) 外部设备 `modules/device.py` | ✅ PASS（ini 配置→连接→出图→抓帧存图→FPS/DN，1280×880@25fps） |
| (c) I2C 读写 `modules/i2c.py` | ✅ PASS（版本/启动信息读、帧计数器递增、写读校验） |
| (d) 固件下载 `modules/firmware.py` | ✅ PASS（MatFwDownload 真实烧录 44s 成功，回读版本 v4.1.7 确认） |
| 公共底层 `modules/sdk.py` | ✅ PASS（两 DLL 全量函数原型绑定，增补接口 21 个探测可用） |

---

## 二、做了哪些东西 —— 模块级内容清单

### 0. `modules/sdk.py` — DLL 加载与原型绑定（公共底层）

打包两个外部 DLL 的**全部导出接口**（签名依据随附头文件
`bin/TestDeviceExport.h`、`bin/MatFwHandler.h`）：

**testlib.dll（PixelIDE 测试主库，26+ 个函数）**

| 分类 | 函数 |
|---|---|
| QT 环境 | `init_qt`（必须最先调用一次） |
| 设备管理 | `get_device` / `release_device` / `get_device_focus_channel` / `set_device_focus_channel` |
| 设备连接 | `device_open` / `device_close` / `device_setConfigure`（下发 ini） |
| 视频流 | `device_open_video` / `device_close_video`* / `device_stop_streaming`* / `device_grab_one_frame` / `device_grab_one_frame_save` / `device_grab_one_frame_save_ex`* / `device_get_fps` / `device_get_current_DN` |
| I2C | `device_I2C_Read` / `device_I2C_Write` / `device_I2C_Read_Data`* / `device_I2C_Write_Data`* |
| 继电器 | `get_switcher` / `switcher_open` / `switcher_close` / `switcher_open_channel` / `switcher_close_channel` |
| Flash 固件 | `firmware_socReboot` / `firmware_set_start_address` / `firmware_set_update_end` / `firmware_earse_flash`（DLL 官方拼写错误，已做 `firmware_erase_flash` 别名兼容）/ `firmware_flash_set` / `firmware_flash_crc_check` / `firmware_download2flash` |
| 固件协议/信息 | `firmware_send_command`（16 字节命令）/ `firmware_read_command`（12 字节应答）/ `firmware_detect`* / `firmware_get_flash_log`* / `firmware_get_info_string`* |
| OTP | `device_otp_read_unstore`* / `device_otp_save_file`* / `device_otp_write`* / `device_otp_get_function_flags`* / `device_otp_set_function_flags`* |
| 错误定位 | `testlib_get_last_error` / `testlib_clear_last_error` |

**MatFwHandler_x64.dll（固件一键下载库，2 个函数）**

| 函数 | 说明 |
|---|---|
| `MatFwDownload(ini, fw, cb)` | 一键固件下载，内部自动完成 开设备→进烧录模式→传输；经回调上报 `(status, progress, err)` |
| `MatFwUpload(ini, addr, len, buf, cb)` | 从 flash 回读数据 |

带 `*` 的为增补接口，加载时用 `hasattr` 防御性绑定（旧版 DLL 缺失也不报错）。
另打包了 14 个 `FW_ERR_*` 错误码常量与中文释义（`describe_fw_error`）、
`FW_INFO_*`、`OTP_MODE_*` 常量，以及全局单例 `get_sdk()`。

**关键工程点**：testlib.dll 除 Qt6/Dothinkey 依赖外还依赖完整 PixelIDE 部署目录中的
`device.dll`/`imageviewer.dll` —— 仅靠随工程拷贝的 8 个 DLL 加载不起来。
`sdk.py` 实现了「显式指定 > 完整部署自动探测 > new_auto/bin 兜底」的查找链
（本机探测到 `F:\Duxin\IDE_resently\pixelide_release\PixelIDE`）。

### (a) `modules/relay.py` — 继电器控制模块

打包 `get_switcher / switcher_open / switcher_close / switcher_open_channel /
switcher_close_channel` 五个接口，封装为 `RelayController`：

- `open() / close()` —— 继电器连接整体开关
- `open_channel(ch) / close_channel(ch)` —— 通道级通断（0 起）
- `power_cycle(ch, off_seconds=15)` —— 规范掉电重启（复刻旧工程 15s 断电时序）
- `ensure_open(ch, retries=3)` —— 带重试的可靠上电
- `self_test(channels)` —— 通道通断自检
- `list_com_ports()` —— pyserial 串口枚举辅助

### (b) `modules/device.py` — 外部设备控制模块

打包 `get_device / release_device / device_setConfigure / device_open /
device_close / device_open_video / device_grab_one_frame(_save) /
device_get_fps / device_get_current_DN / get(set)_device_focus_channel`，
封装为 `PixelDevice`：

- 生命周期：`set_configure(ini)` → `open()` → `open_video()` → `grab_frame()` → `close()` → `release()`，支持 with 上下文
- `bring_up(ini)` —— 一键上电出图（复刻旧工程 `_test_device_initialization` 主链路，
  open_video 3 次重试 + 抓帧 3 次重试）
- `grab_frame_save(dir, name)` / `get_fps()` / `get_dn()`
- 设备名归一化（`MAT130AV200→MAT130YV200` 等，与旧 DLL 约定一致）
- 聚焦通道：单通道卡返回空串时自动跳过设置

### (c) `modules/i2c.py` — I2C 读写模块

打包 `device_I2C_Read / device_I2C_Write`（寄存器级）与
`device_I2C_Read_Data / device_I2C_Write_Data`（字节流级，增补接口），
封装为 `I2CController`：

- `read(addr, addr_len, bits)` / `write(addr, value, addr_len, bits)` —— 位宽可选 8/16/32，
  默认从机 **0x40**；失败自动附 `testlib_get_last_error` 诊断
- `read_bytes / write_bytes` —— 连续字节读写
- `write_readback` —— 写后回读校验；`read_ro` —— 只读探活
- 常用固件寄存器地址已录入 `config.json > i2c.regs`（0x00d8 版本、0x00c0/0x00c4
  启动信息、0x00cc 帧计数器、0x0918/0x091c 算法开关等）

### (d) `modules/firmware.py` — 固件下载模块（两个层次）

**`FirmwareDownloader`（MatFwHandler_x64.dll 一键下载）**
- `download(ini, fw, max_retries, on_event)` —— MatFwDownload 封装：
  进度回调日志（10%→100%）、状态/错误码中文释义、失败自动重试
- `upload(ini, addr, length)` —— MatFwUpload flash 回读

**`FirmwareFlasher`（testlib.dll Flash 级 + 固件协议，复刻旧工程 `_fw_update` 手工流程）**
- `soc_reboot / set_start_address / set_update_end`
- `erase_flash / flash_set / flash_crc_check / download_to_flash / download_from_file`
- `send_command(16字节命令) / read_command(12字节应答)`
- `detect / get_flash_log / get_info_string`（增补信息接口）

### 辅助

- `modules/log_setup.py` —— 日志 + C++ SDK stdout 噪音过滤（沿用旧工程 OutputFilter 思路并修正了其吞换行的问题）
- `scripts/common.py` —— 读配置 + 继电器上电 + 设备初始化公共流程
- `config.json` —— 现场硬件参数（继电器 COM9/CH0、绑定 ini、绑定固件、寄存器表、Flash 分区表）

---

## 三、每个模块如何验证（真机结果）

所有脚本在 `new_auto/scripts/` 下，退出码 0=通过，逐项打印 PASS/FAIL。
一键全流程：`python scripts/run_all.py --burn`（2026-09-13 05:25 实测全绿）。

### 1. 继电器 `verify_relay.py`

| 验证点 | 方法 | 结果 |
|---|---|---|
| 句柄获取 | `get_switcher("COM9")`（CH34x USB 串口） | ✅ |
| 整体开关 | `switcher_open/close/reopen` | ✅ 3/3 True |
| 通道 0 通断 | `close_channel(0)` → `open_channel(0)` | ✅ True |
| 掉电重启 | `power_cycle(0)`（断 15s → 上电） | ✅ 模组随之重新出图 |

### 2. 外部设备 `verify_device.py`

流程：CH0 上电 → `get_device("MAT130YV200")` → `set_configure(绑定 ini)` →
`open` → `open_video` → `grab_frame` → 存图/FPS/DN → 关闭释放。

| 验证点 | 结果 |
|---|---|
| device_open / open_video / grab_one_frame | ✅ 全 True |
| 抓帧存图 | ✅ `logs/verify_*.uyvy`（实测文件 `..._1280x880x16.uyvy`，分辨率与 ini 一致） |
| FPS | ✅ 25.01（25fps 规格） |
| DN 亮度均值 | ✅ 38.90（有正常图像内容） |

### 3. I2C `verify_i2c.py`（Slave 0x40）

| 验证点 | 寄存器 | 结果 |
|---|---|---|
| 读固件版本 | 0x00d8 (16,32) | ✅ 0x01040107 → **v4.1.7**（与烧录固件一致） |
| 读启动信息 | 0x00c0=0x04fb / 0x00c4 | ✅ ROM 标志正常，**A 区启动** |
| 帧计数器递增 | 0x00cc 间隔 2s 两次 | ✅ 0x00075671 → 0x000d5360（固件运行中） |
| 写读校验 | 0x0918 (16,16) 写 1 回读后恢复 | ✅ 写链路通 |

### 4. 固件下载 `verify_fw_download.py --burn`

- dry-run：DLL 原型绑定、ini/bin 路径、FirmwareDownloader/Flasher 接口完备性 ✅
- **真实烧录**：绑定 ini + 绑定 bin（v4.1.7），MatFwDownload 进度 10%→100%，
  **44 秒成功**；随后规范掉电 15s 重启，I2C 回读 0x00d8=0x01040107 确认 **v4.1.7 在板运行**，
  帧计数器递增、出图正常 ✅
- `--fw/--ini` 参数可指定其它固件/ini；不加 `--burn` 只做不烧写的链路校验

---

## 四、调试过程中定位并解决的关键问题

1. **I2C 全地址无应答 / MatFwDownload 报 -6（通信失败）——根因：固件 Slave ID 不匹配**
   模组原固件的 I2C Slave ID 是 **0x60**，而所有 ini 都按 **0x40** 配置，链路上 0x40 无人应答。
   用户已把模组换成 **v4.1.7（0x40）固件**
   （`fw/MAT130A_JUNGE-A21-JZ9173-SUB_..._v4.1.7_C0101.bin`），与
   `configs/init_file/..._1280_880.ini` 绑定后 I2C 立即全通。
   **该 bin+ini+模组三者已绑定并固化进 config.json，其它 ini 已清理。**

2. **testlib.dll 加载失败（缺依赖）**
   它还依赖完整 PixelIDE 部署里的 `device.dll`/`imageviewer.dll`。解决：
   `sdk.py` 优先从完整部署目录加载（本机 `F:\Duxin\IDE_resently\pixelide_release\PixelIDE`），
   `new_auto/bin` 兜底，并 `os.add_dll_directory` 注入搜索路径。

3. **重新上电后偶发抓帧失败**
   模组固件上电启动需 5~10s，`bring_up` 已按旧工程加 open_video×3 / 抓帧×3 重试；
   规范掉电须 **≥15s**。

4. **继电器间歇性 get_switcher 失败**
   Python 进程被强杀后串口短暂未释放所致；`RelayController` 构造与
   `ensure_open` 带重试后不再复现。

5. **旧工程 output_filter 吞换行**
   旧过滤器含 `^$` 规则会把 `print` 的单独换行过滤掉，新 `log_setup.py` 已修正，
   并补充了 spdlog 格式噪音（`[dllmain.cpp]` 等）的过滤规则
   （注：DLL 加载期的 C++ 日志直写控制台句柄，无法在 Python 层过滤，量少无碍）。

---

## 五、遗留说明

- `FirmwareFlasher` 的 Flash 级接口（erase/download2flash/send_command 等）已完整
  绑定并通过 dry-run 探测，未做整片擦写实测（MatFwDownload 已覆盖日常下载场景；
  手工流程与旧工程 `_fw_update` 参数一致，需要时可随时启用）。
- `MatFwUpload` 回读接口已绑定，未做长块回读实测。
- 增补接口（`firmware_detect`、`device_otp_*` 等）在本机 DLL 中均存在（21 个探测可用），
  OTP 相关属不可逆操作，仅打包未实测。
- 采集卡聚焦通道在本机返回空串（单通道卡），多通道卡场景的通道切换逻辑已预留。
