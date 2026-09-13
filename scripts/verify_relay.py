# -*- coding: utf-8 -*-
"""验证 1: 继电器模块 (modules.relay)

步骤:
  1. 在 COM3 上创建继电器句柄
  2. switcher_open / switcher_close 各一次
  3. 对 Channel 0 执行 导通 -> 断开 -> 再导通 (保持模组供电)
退出码 0 = 全部通过。
"""
import sys
import time

from common import ROOT, load_config

from modules.log_setup import setup_logging
from modules.relay import RelayController, list_com_ports


def main():
    config = load_config()
    setup_logging(ROOT / "logs")
    relay_cfg = config["relay"]
    ch = relay_cfg["channel"]

    print(f"本机串口: {list_com_ports()}")
    print(f"目标继电器: {relay_cfg['port']} 通道 {ch}")

    relay = RelayController(relay_cfg["port"])
    results = {}

    results["open"] = relay.open()
    time.sleep(0.5)
    results["close"] = relay.close()
    time.sleep(0.5)
    results["reopen"] = relay.open()

    # 通道级: 断 -> 通 -> 保持通电
    results[f"close_channel({ch})"] = relay.close_channel(ch)
    time.sleep(2)
    results[f"open_channel({ch})"] = relay.open_channel(ch)

    passed = all(results.values())
    print("\n===== 继电器模块验证 =====")
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"结论: {'PASS' if passed else 'FAIL'}  (通道 {ch} 当前保持导通)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
