# -*- coding: utf-8 -*-
"""验证 3: I2C 读写模块 (modules.i2c)

前置: 设备已上电出图 (依赖验证 1/2 的上电链路)。

步骤 (对 Slave 0x40, 全部为只读探测 + 安全写校验):
  1. 读固件版本寄存器 0x00d8 (32bit)        -> 证明 I2C 读链路通
  2. 读启动信息 0x00c0/0x00c4               -> 证明 ROM/SRAM 启动状态可读
  3. 连续两次读帧计数器 0x00cc              -> 值应变化, 证明固件在跑
  4. 写读校验: 对 AWB 开关 0x0918 写 1 再读回,
     最后恢复原值                           -> 证明 I2C 写链路通
退出码 0 = 全部通过。
"""
import sys
import time

from common import ROOT, load_config, init_module

from modules.log_setup import setup_logging


def main():
    config = load_config()
    setup_logging(ROOT / "logs")
    regs = {k: int(v, 16) for k, v in config["i2c"]["regs"].items()}
    slave = int(config["i2c"]["default_slave"], 16)

    relay, dev, i2c = init_module(config)
    print(f"设备已出图, I2C 默认 Slave: 0x{slave:02x}")

    results = {}

    # 1. 固件版本
    ok, ver = i2c.read(regs["fw_version"], addr_len=16, bits=32)
    if ok:
        v = ver
        print(f"[1] 固件版本 0x{regs['fw_version']:04x} = 0x{v:08x} "
              f"-> v{(v >> 16) & 0xFF}.{(v >> 8) & 0xFF}.{v & 0xFF}")
    results["i2c_read(0x00d8 fw_version)"] = ok

    # 2. 启动信息
    ok0, rom = i2c.read(regs["boot_rom_info"], addr_len=16, bits=32)
    ok1, sram = i2c.read(regs["boot_sram_info"], addr_len=16, bits=32)
    if ok0 and ok1:
        area = "A区" if (sram & 1) == 0 else "B区"
        print(f"[2] ROM 信息 0x{rom:04x}, SRAM 信息 0x{sram:04x} (从{area}启动)")
    results["i2c_read(0x00c0/0x00c4 boot)"] = ok0 and ok1

    # 3. 帧计数器
    okc0, cnt0 = i2c.read(regs["frame_counter"], addr_len=16, bits=32)
    time.sleep(2)
    okc1, cnt1 = i2c.read(regs["frame_counter"], addr_len=16, bits=32)
    counting = okc0 and okc1 and cnt0 != cnt1
    print(f"[3] 帧计数器 0x{cnt0:08x} -> 0x{cnt1:08x} ({'计数中' if counting else '未变化'})")
    results["i2c_read(0x00cc frame_counter 变化)"] = counting

    # 4. 写读校验 (AWB 开关, 最后恢复)
    okr0, orig = i2c.read(regs["awb_enable"], addr_len=16, bits=16)
    okw = i2c.write(regs["awb_enable"], 0x0001, addr_len=16, bits=16)
    okr1, back = i2c.read(regs["awb_enable"], addr_len=16, bits=16)
    i2c.write(regs["awb_enable"], orig, addr_len=16, bits=16)  # 恢复
    write_ok = okr0 and okw and okr1 and back == 0x0001
    print(f"[4] 写读校验 0x0918: 原值 0x{orig:04x} -> 写 1 -> 回读 0x{back:04x} "
          f"-> 已恢复 (写链路 {'OK' if write_ok else 'FAIL'})")
    results["i2c_write+readback(0x0918)"] = write_ok

    # 收尾: 恢复断电
    dev.close(); dev.release()
    relay.close_channel(config["relay"]["channel"])
    relay.close()

    print("\n===== I2C 模块验证 =====")
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    passed = all(results.values())
    print(f"结论: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
