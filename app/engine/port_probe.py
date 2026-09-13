# -*- coding: utf-8 -*-
"""串口继电器探测 (独立子进程运行, 退出即释放全部 DLL 句柄)

用法: python app/engine/port_probe.py
输出: 最后一行 PROBE_JSON:{...}

对每个串口:
  1. get_switcher 尝试创建继电器句柄 -> 无响应/非继电器则 relay=false
  2. 有响应则 switcher_open + 逐通道 open/close 测试, 记录可用通道
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def main():
    import time
    import serial.tools.list_ports
    from modules.sdk import PixelIDESdk

    sdk = PixelIDESdk()
    out = []
    for p in serial.tools.list_ports.comports():
        entry = {"port": p.device, "desc": p.description,
                 "relay": False, "channels": [], "error": None}
        try:
            h = sdk.testlib.get_switcher(p.device.encode("utf-8"))
            if h:
                opened = bool(sdk.testlib.switcher_open(h))
                entry["relay"] = opened
                if opened:
                    sdk.testlib.switcher_close(h)
                    time.sleep(0.3)
                    for ch in range(4):
                        # 继电器板需要操作间隔, 失败重试一次
                        ok_open = bool(sdk.testlib.switcher_open_channel(h, ch))
                        if not ok_open:
                            time.sleep(0.3)
                            ok_open = bool(sdk.testlib.switcher_open_channel(h, ch))
                        ok_close = False
                        if ok_open:
                            time.sleep(0.2)
                            ok_close = bool(sdk.testlib.switcher_close_channel(h, ch))
                        if ok_open:
                            entry["channels"].append({"ch": ch, "open": ok_open, "close": ok_close})
                        time.sleep(0.2)
        except Exception as e:
            entry["error"] = str(e)[:120]
        out.append(entry)
    print("PROBE_JSON:" + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
