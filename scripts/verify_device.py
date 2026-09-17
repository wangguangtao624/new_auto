# -*- coding: utf-8 -*-
"""验证 2: 外部设备模块 (modules.device)

步骤:
  1. 继电器上电 (COM9 / CH0, 依赖验证 1)
  2. get_device("MAT130YV200") 取句柄
  3. 读取并回设 Dothinkey 聚焦通道
  4. device_setConfigure 下发 96712 ini
  5. device_open -> device_open_video -> device_grab_one_frame
  6. device_grab_one_frame_save 存一帧图到 logs/, 读取 FPS 与 DN
  7. device_close -> release_device
退出码 0 = 全部通过。
"""
import sys
import time
from pathlib import Path

from common import ROOT, load_config

from modules.device import PixelDevice
from modules.log_setup import setup_logging
from modules.relay import RelayController


def main():
    config = load_config()
    setup_logging(ROOT / "logs")
    relay_cfg, dev_cfg = config["relay"], config["device"]

    # 1. 上电
    relay = RelayController(relay_cfg["port"])
    relay.open()
    if not relay.open_channel(relay_cfg["channel"]):
        print("FAIL: 继电器通道导通失败")
        return 1
    print(f"[1] 继电器 {relay_cfg['port']} 通道 {relay_cfg['channel']} 已导通, 等待模组上电稳定 (10s)...")
    time.sleep(10)

    # 2. 取设备句柄
    dev = PixelDevice(dev_cfg["chip"])
    print(f"[2] get_device({dev_cfg['chip']}) -> {dev.device_name} 句柄 OK")

    # 3. 聚焦通道 (可选项: 单通道采集卡上为空, 自动跳过)
    channel = dev.get_focus_channel()
    ok_focus = dev.set_focus_channel(channel)
    print(f"[3] 聚焦通道: {channel!r} (为空=单通道卡, 跳过) 回设 -> {ok_focus}")

    # 4+5. 配置 + 连接 + 视频流 + 抓帧
    ini = ROOT / "configs" / "init_file" / dev_cfg["init_file"]
    print(f"[4] set_configure: {ini.name}")
    ok_bring = dev.bring_up(str(ini), configure_wait=dev_cfg.get("configure_wait_seconds", 10))
    if not ok_bring:
        print("FAIL: bring_up (set_configure/open/open_video/抓帧) 失败")
        dev.release()
        return 1
    print("[5] open -> open_video -> grab_frame 全部成功")

    # 6. 存图 + FPS + DN
    img_dir = ROOT / "logs"
    ts = time.strftime("%Y%m%d_%H%M%S")
    ok_save = dev.grab_frame_save(str(img_dir), f"verify_{ts}")
    saved = list(img_dir.glob(f"*verify_{ts}*"))
    print(f"[6] 抓帧存图 -> {ok_save} ({saved[0].name if saved else '未找到文件'})")
    fps = dev.get_fps()
    dn = dev.get_dn()
    print(f"    FPS={fps:.2f}  DN={dn:.2f}")

    # 7. 关闭
    dev.close()
    dev.release()
    relay.close()
    print("[7] device_close / release_device 完成")

    passed = ok_focus and ok_save and fps > 0
    print(f"\n结论: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
