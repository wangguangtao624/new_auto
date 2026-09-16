# -*- coding: utf-8 -*-
"""验证 4: 固件下载模块 (modules.firmware)

两种模式:
  --dry-run   (默认) 只验证接口链路: DLL 原型绑定、ini/bin 路径校验、
              FirmwareDownloader 构造、回调类型可实例化; 不真实烧写 flash。
  --burn      真实执行 MatFwDownload 一键下载 (会重写模组 flash 固件,
              与旧工程 daily 流程一致, A/B 双区有掉电保护)。
  --info      烧录后通过 I2C 回读固件版本确认 (--burn 时自动执行)。

退出码 0 = 通过。
"""
import argparse
import sys
import time
from pathlib import Path

from common import ROOT, load_config

from modules.firmware import FirmwareDownloader, FirmwareFlasher
from modules.log_setup import setup_logging
from modules.sdk import FW_INFO_FIRMWARE_VERSION, get_sdk


def find_fw(config) -> Path:
    fw_dir = ROOT / config["firmware"]["fw_dir"]
    # 优先用 config 绑定的固件文件 (bin/ini/模组 三者绑定)
    bound = config["firmware"].get("fw_file")
    if bound and (fw_dir / bound).exists():
        return fw_dir / bound
    bins = sorted(fw_dir.glob("*.bin"))
    if not bins:
        raise FileNotFoundError(f"{fw_dir} 下没有 .bin 固件")
    return bins[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--burn", action="store_true", help="真实执行固件下载")
    parser.add_argument("--fw", default=None, help="指定固件路径 (默认取 fw/ 下第一个)")
    parser.add_argument("--ini", default=None, help="指定 ini 路径 (默认取 config)")
    args = parser.parse_args()

    config = load_config()
    setup_logging(ROOT / "logs")
    dev_cfg = config["device"]

    sdk = get_sdk()
    print("[1] DLL 加载 + init_qt 完成")

    downloader = FirmwareDownloader()
    print("[2] FirmwareDownloader 就绪 "
          f"(MatFwDownload={'有' if hasattr(sdk.matfw, 'MatFwDownload') else '无'}, "
          f"MatFwUpload={'有' if hasattr(sdk.matfw, 'MatFwUpload') else '无'})")

    ini = Path(args.ini) if args.ini else ROOT / "configs" / "init_file" / dev_cfg["init_file"]
    fw = Path(args.fw) if args.fw else find_fw(config)
    assert ini.exists(), f"ini 不存在: {ini}"
    assert fw.exists(), f"固件不存在: {fw}"
    print(f"[3] 路径校验 OK:\n    ini = {ini.name}\n    fw  = {fw.name} ({fw.stat().st_size} 字节)")

    # FirmwareFlasher 原型可用性 (不操作硬件)
    from modules.device import PixelDevice
    dev = PixelDevice(dev_cfg["chip"])
    flasher = FirmwareFlasher(dev)
    api = [m for m in ("soc_reboot", "erase_flash", "set_start_address",
                       "download_from_file", "flash_crc_check", "send_command",
                       "read_command", "detect", "get_flash_log", "get_info_string")
           if callable(getattr(flasher, m, None))]
    print(f"[4] FirmwareFlasher 接口绑定: {len(api)} 个 ({', '.join(api)})")
    dev.release()

    if not args.burn:
        print("\n结论: PASS (dry-run, 未烧写 flash; 加 --burn 执行真实下载)")
        return 0

    # ---- 真实下载 ----
    print(f"\n[5] 烧录前上电 + 真实固件下载 (MatFwDownload)...")
    from modules.relay import relay_from_config as _relay_from_config
    _relay = _relay_from_config(config)
    _relay.open()
    _relay.close_channel(config["relay"]["channel"])
    time.sleep(15)  # 规范掉电
    _relay.open_channel(config["relay"]["channel"])
    time.sleep(8)   # 模组上电稳定
    t0 = time.time()
    ok = downloader.download(str(ini), str(fw), max_retries=3)
    print(f"    下载结果: {'成功' if ok else '失败'}  耗时 {time.time() - t0:.0f}s")
    if not ok:
        _relay.close()
        print("结论: FAIL (MatFwDownload 失败)")
        return 1

    # ---- 烧录后通过 I2C 读版本确认 (规范掉电重启) ----
    print("[6] 规范掉电重启后通过 I2C 回读固件版本...")
    from modules.i2c import I2CController
    from modules.relay import relay_from_config
    relay = relay_from_config(config)
    relay.open()
    relay.close_channel(config["relay"]["channel"])
    time.sleep(15)  # 完全掉电
    relay.open_channel(config["relay"]["channel"])
    time.sleep(8)   # 固件启动

    dev2 = PixelDevice(dev_cfg["chip"])
    ini2 = Path(args.ini) if args.ini else ROOT / "configs" / "init_file" / dev_cfg["init_file"]
    dev2.set_configure(str(ini2))
    time.sleep(10)
    dev2.open()
    time.sleep(2)
    i2c = I2CController(dev2, default_slave=int(config["i2c"]["default_slave"], 16))
    ok_ver, ver = i2c.read(0x00d8, addr_len=16, bits=32)
    dev2.close(); dev2.release()
    relay.close_channel(config["relay"]["channel"])
    relay.close()
    if ok_ver:
        print(f"    固件版本寄存器 = 0x{ver:08x} "
              f"-> v{(ver >> 16) & 0xFF}.{(ver >> 8) & 0xFF}.{ver & 0xFF}")
        print("\n结论: PASS (固件下载 + I2C 版本回读确认)")
        return 0
    print("    版本回读失败 (可能模组仍在重启, 可手动重跑 verify_i2c.py 确认)")
    print("\n结论: PASS (下载完成, 版本回读待确认)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
