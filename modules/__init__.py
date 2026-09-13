# -*- coding: utf-8 -*-
"""new_auto 硬件自动化模块包

把 PixelIDE(PixieDE) testlib.dll / MatFwHandler_x64.dll 的对外接口,
按功能最小化打包为五个独立小模块:

- modules.sdk        : DLL 加载 + 全部函数原型绑定 + 错误码助手 (底层公共依赖)
- modules.relay      : (a) 继电器控制模块 (串口 COM3, 通道级通断)
- modules.device     : (b) 外部设备模块 (打开/关闭设备, 初始化 ini, 视频流, 抓帧, FPS/DN)
- modules.i2c        : (c) I2C 读写模块 (寄存器级 / 字节流级)
- modules.firmware   : (d) 固件下载模块 (MatFwDownload 一键下载 + Flash 擦写/校验/固件协议)
"""

from .relay import RelayController
from .device import PixelDevice
from .i2c import I2CController
from .firmware import FirmwareFlasher, FirmwareDownloader

__all__ = [
    "RelayController",
    "PixelDevice",
    "I2CController",
    "FirmwareFlasher",
    "FirmwareDownloader",
]
