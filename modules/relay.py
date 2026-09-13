# -*- coding: utf-8 -*-
"""(a) 继电器控制模块

打包 testlib.dll 中的继电器 (串口通道切换器) 接口:

    void* get_switcher(const char* port_name)          按串口名创建继电器句柄
    bool  switcher_open(void* sw)                      打开继电器连接
    bool  switcher_close(void* sw)                     关闭继电器连接
    bool  switcher_open_channel(void* sw, int ch)      导通指定通道 (从 0 起)
    bool  switcher_close_channel(void* sw, int ch)     断开指定通道

对应现场硬件: 继电器板接在 COM3 (CH34x USB 串口), 使用 Channel 0 给相机模组供电。

用法:
    from modules.relay import RelayController
    relay = RelayController("COM3")
    relay.open()                      # 连上继电器
    relay.open_channel(0)             # CH0 导通 => 模组上电
    relay.close_channel(0)            # CH0 断开 => 模组断电
    relay.power_cycle(0)              # 断电->等待->上电 (模拟掉电重启)
    relay.close()
"""
import logging
import time

import serial.tools.list_ports

from .sdk import get_sdk

logger = logging.getLogger("new_auto.relay")


def list_com_ports():
    """枚举本机串口, 返回 [(device, description), ...]"""
    return [(p.device, p.description) for p in serial.tools.list_ports.comports()]


class RelayController:
    """继电器 (串口通道切换器) 控制器"""

    def __init__(self, port: str = "COM3", bin_dir=None):
        """创建并连接继电器

        :param port: 继电器所在串口, 如 "COM3"
        :raises RuntimeError: 串口上拿不到继电器句柄时
        """
        self.port = port
        self._sdk = get_sdk(bin_dir)
        self._handle = self._sdk.testlib.get_switcher(port.encode("utf-8"))
        if not self._handle:
            ports = list_com_ports()
            raise RuntimeError(
                f"在 {port} 上获取继电器句柄失败 (last_error={self._sdk.last_error()!r}); "
                f"当前可用串口: {ports}"
            )
        logger.info("继电器句柄创建成功: %s", port)

    # ------------------------------------------------------------ 基础开关

    def open(self) -> bool:
        """打开继电器连接 (整体使能)"""
        ok = self._sdk.testlib.switcher_open(self._handle)
        logger.info("switcher_open(%s) -> %s", self.port, ok)
        return bool(ok)

    def close(self) -> bool:
        """关闭继电器连接 (整体断开, 句柄仍可用, 可重新 open)"""
        ok = self._sdk.testlib.switcher_close(self._handle)
        logger.info("switcher_close(%s) -> %s", self.port, ok)
        return bool(ok)

    # ------------------------------------------------------------ 通道级

    def open_channel(self, channel: int) -> bool:
        """导通指定通道 (channel 从 0 起)"""
        ok = bool(self._sdk.testlib.switcher_open_channel(self._handle, int(channel)))
        logger.info("switcher_open_channel(%s, ch%d) -> %s", self.port, channel, ok)
        return ok

    def close_channel(self, channel: int) -> bool:
        """断开指定通道"""
        ok = bool(self._sdk.testlib.switcher_close_channel(self._handle, int(channel)))
        logger.info("switcher_close_channel(%s, ch%d) -> %s", self.port, channel, ok)
        return ok

    # ------------------------------------------------------------ 组合动作

    def power_cycle(self, channel: int, off_seconds: float = 15.0,
                    settle_seconds: float = 1.0) -> bool:
        """通道断电 -> 等待 -> 重新上电 (复刻旧工程 restart_switcher_channel)

        :param channel: 通道号
        :param off_seconds: 断电保持时长 (旧工程用 15s 确保完全掉电)
        :return: 重新上电是否成功
        """
        if not self.close_channel(channel):
            logger.warning("通道 %d 断开失败", channel)
            return False
        time.sleep(off_seconds)
        ok = self.open_channel(channel)
        time.sleep(settle_seconds)
        logger.info("通道 %d 重新上电 -> %s", channel, ok)
        return ok

    def ensure_open(self, channel: int, retries: int = 3) -> bool:
        """确保继电器连接打开且目标通道导通 (带重试)"""
        if not self.open():
            for _ in range(retries):
                time.sleep(2)
                if self.open():
                    break
            else:
                return False
        if not self.open_channel(channel):
            return False
        return True

    # ------------------------------------------------------------ 自检

    def self_test(self, channels=(0,)) -> dict:
        """通道通断自检: open_channel -> close_channel 各一次

        :return: {channel: 是否全部成功}
        """
        report = {}
        self.open()
        for ch in channels:
            ok_open = self.open_channel(ch)
            time.sleep(0.3)
            ok_close = self.close_channel(ch)
            report[ch] = ok_open and ok_close
            logger.info("通道 %d 自检: open=%s close=%s => %s", ch, ok_open, ok_close, report[ch])
        return report
