# -*- coding: utf-8 -*-
"""new_auto 硬件自动化模块包

把 PixelIDE(PixieDE) testlib.dll / MatFwHandler_x64.dll 的对外接口,
按功能最小化打包为独立小模块:

- modules.sdk        : DLL 加载 + 全部函数原型绑定 + 错误码助手 (底层公共依赖)
- modules.relay      : 继电器控制模块 (串口 COM3, 通道级通断)
- modules.device     : 外部设备模块 (打开/关闭设备, ini 配置, 视频流, 抓帧, FPS/DN)
- modules.i2c        : I2C 读写模块 (寄存器级 / 字节流级, A2D2/A2D4/A4D4)
- modules.firmware   : 固件下载模块 (MatFwDownload 一键下载 + Flash 擦写/校验/固件协议)
- modules.otp        : OTP 读写模块 (读/存文件/写/功能标志)
- modules.image      : 图像抓取与对比模块 (亮度均值, 寄存器改值前后对比)
- modules.checks     : 固件状态检查 (版本/启动区/帧计数/算法开关/功能安全/时钟切换)
"""

from .relay import RelayController
from .device import PixelDevice
from .i2c import I2CController
from .firmware import FirmwareFlasher, FirmwareDownloader
from .otp import OtpController
from .image import ImageTools

__all__ = [
    "RelayController",
    "PixelDevice",
    "I2CController",
    "FirmwareFlasher",
    "FirmwareDownloader",
    "OtpController",
    "ImageTools",
]
