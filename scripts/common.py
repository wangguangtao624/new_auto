# -*- coding: utf-8 -*-
"""验证脚本公共工具: 加载 config.json / 构造带继电器上电的完整设备环境"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_config():
    with open(ROOT / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def init_module(config):
    """上电 + 设备初始化, 返回 (relay, dev, i2c)

    流程复刻旧工程 TestFunction._device_open:
    继电器上电(CH0) -> Dothinkey 聚焦通道 -> set_configure(ini) -> open -> open_video
    """
    from modules.device import PixelDevice
    from modules.i2c import I2CController
    from modules.relay import relay_from_config

    relay_cfg = config["relay"]
    dev_cfg = config["device"]

    # 继电器连接带重试 (进程异常退出后 COM 口需要时间释放)
    relay = None
    for attempt in range(3):
        try:
            relay = relay_from_config(config)
            break
        except RuntimeError as e:
            if attempt == 2:
                raise
            print(f"[common] 继电器连接失败({e}), 5s 后重试...")
            time.sleep(5)
    relay.open()
    for attempt in range(3):
        if relay.open_channel(relay_cfg["channel"]):
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"继电器通道 {relay_cfg['channel']} 导通失败")
    time.sleep(5)  # 等模组上电稳定

    dev = PixelDevice(dev_cfg["chip"])
    channel = dev.get_focus_channel()
    print(f"[common] Dothinkey 聚焦通道: {channel!r}")
    dev.set_focus_channel(channel)

    ini = ROOT / "configs" / "init_file" / dev_cfg["init_file"]
    ok = dev.bring_up(str(ini), configure_wait=dev_cfg.get("configure_wait_seconds", 10))
    if not ok:
        dev.release()
        raise RuntimeError("设备 bring_up 失败 (set_configure/open/open_video/抓帧)")

    i2c = I2CController(dev, default_slave=int(config["i2c"]["default_slave"], 16))
    return relay, dev, i2c
