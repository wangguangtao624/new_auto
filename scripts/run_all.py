# -*- coding: utf-8 -*-
"""一键顺序验证全部模块: 继电器 -> 设备 -> I2C -> 固件下载(dry-run)

用法:
    python scripts/run_all.py            # 固件下载只做 dry-run
    python scripts/run_all.py --burn     # 固件下载执行真实烧录
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = ["verify_relay.py", "verify_device.py", "verify_i2c.py", "verify_fw_download.py"]


def main():
    root = Path(__file__).resolve().parent
    args = sys.argv[1:]
    overall = True
    for script in SCRIPTS:
        print(f"\n{'=' * 60}\n>>> 运行 {script}\n{'=' * 60}")
        cmd = [sys.executable, str(root / script)] + (args if script.endswith("fw_download.py") else [])
        ret = subprocess.run(cmd, cwd=str(root)).returncode
        status = "PASS" if ret == 0 else "FAIL"
        print(f"\n<<< {script}: {status}")
        if ret != 0:
            overall = False
            break  # 后续验证依赖前面的链路, 失败即停
    print(f"\n{'=' * 60}\n总结论: {'ALL PASS' if overall else 'FAILED'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
