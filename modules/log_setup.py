# -*- coding: utf-8 -*-
"""日志与底层 SDK 输出过滤

testlib.dll 内部的 C++ 代码会直接往 stdout 打印大量 `[D] DxDevicePrivate [I2C]...`
之类的调试信息。OutputFilter 沿用旧工程 (fw_auto_copy/src/libs/output_filter.py)
的做法: 包一层 sys.stdout/sys.stderr, 把这些行过滤掉, 让控制台只保留 Python 侧日志。
"""
import logging
import re
import sys
from pathlib import Path

_FILTER_PATTERNS = [
    # 旧工程已知噪音: [D] 开头的 C++ 调试行
    r"\[D\].*DxDevicePrivate",
    r"\[D\].*TestDeviceExport",
    r"\[D\].*dxdevicelistener",
    r"\[D\].*SerialPortDevice",
    r"\[D\].*MAT130V200",
    r"\[D\].*generalevb",
    r"\[D\].*dxdevice",
    r"\[D\].*DothinkeyDevice.*\[I2C\]",
    r"\[D\].*dllmain",
    # spdlog 格式的 C++ 日志: [2026-09-13 03:04:03.964] [info] [dllmain.cpp:17]
    r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
    r"\[dllmain\.cpp",
    r"\[StructuredException\.cpp",
    r"DLL_PROCESS_ATTACH",
    r"DLL_PROCESS_DETACH",
    r"^\s*\(Build \d+\)\s*$",
]


class OutputFilter:
    """过滤 C++ SDK 打到 stdout/stderr 的调试行"""

    def __init__(self, stream):
        self._stream = stream
        self._patterns = [re.compile(p) for p in _FILTER_PATTERNS]

    def write(self, text):
        if text and any(p.search(text) for p in self._patterns):
            return
        self._stream.write(text)

    def flush(self):
        self._stream.flush()

    def isatty(self):
        return self._stream.isatty()

    def fileno(self):
        return self._stream.fileno()


def setup_logging(log_dir=None, level=logging.INFO):
    """初始化日志: 控制台 + 可选文件, 同时过滤 C++ SDK 噪音输出

    :param log_dir: 日志文件目录; 为 None 时不写文件
    :return: root logger
    """
    sys.stdout = OutputFilter(sys.stdout)
    sys.stderr = OutputFilter(sys.stderr)

    root = logging.getLogger("new_auto")
    root.setLevel(level)
    if root.handlers:  # 避免重复初始化
        return root

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(module)s:%(lineno)d] %(message)s",
        datefmt="%H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "new_auto.log", encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)

    return root
