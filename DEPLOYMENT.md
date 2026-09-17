# New Auto 2.1.0

## 运行环境

- Windows x64
- Python 3.12
- PixelIDE 完整运行环境；发行包已包含项目使用的 `bin/` DLL 依赖。
- 继电器：COM9 / Channel 0，使用 PixelIDE SDK 控制（本机现场端口；旧版 2.0.0 记录为 COM3）。

## 启动

双击 `run_new_auto.bat`（或 `start.bat`），或在本目录运行：

```bat
python -m pip install -r requirements.txt
python app\server.py --host 127.0.0.1 --port 8765
```

浏览器打开 `http://127.0.0.1:8765`。

## 真实设备确认链路

- `case333`：SDK 上电 → 等待 → 实际出图 → FPS 数据线断言 ≥25 → I²C 读固件版本 → 数据线断言主版本为 4。
- `gujian xiazai`：掉电烧录固件 → 重新上电（重建设备句柄）→ I²C 回读 `0x00d8` 断言版本。
