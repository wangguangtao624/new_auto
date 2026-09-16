# -*- coding: utf-8 -*-
"""继电器控制模块。

支持两种已知传输方式：
- ``sdk``：PixelIDE ``testlib.dll`` 的 Dothinkey switcher 接口（默认）
- ``serial_a0``：USB 2.0 CDC 串口继电器的 A0 四字节协议

串口协议没有回执时，写入成功只表示操作系统已接受命令；调用方应通过
后续的设备出图/I2C 探活确认供电链路。
"""
import logging
import time

import serial
import serial.tools.list_ports

from .sdk import get_sdk

logger = logging.getLogger("new_auto.relay")

TRANSPORT_SDK = "sdk"
TRANSPORT_SERIAL_A0 = "serial_a0"
_VALID_TRANSPORTS = {TRANSPORT_SDK, TRANSPORT_SERIAL_A0}


def list_com_ports():
    """枚举本机串口, 返回 ``[(device, description), ...]``。"""
    return [(p.device, p.description) for p in serial.tools.list_ports.comports()]


def relay_from_config(config: dict, bin_dir=None) -> "RelayController":
    """根据 ``config.json`` 的 ``relay`` 段创建控制器，供脚本与画布共用。"""
    relay = config["relay"]
    return RelayController(
        relay["port"], bin_dir,
        transport=relay.get("transport", TRANSPORT_SDK),
        baudrate=relay.get("baudrate", 9600),
        timeout=relay.get("timeout_seconds", 0.8),
    )


class RelayController:
    """继电器控制器；通道参数在 API 中始终从 0 开始编号。"""

    def __init__(self, port: str = "COM3", bin_dir=None, *, transport: str = TRANSPORT_SDK,
                 baudrate: int = 9600, timeout: float = 0.8):
        if transport not in _VALID_TRANSPORTS:
            raise ValueError(f"未知继电器传输方式 {transport!r}; 可选: {sorted(_VALID_TRANSPORTS)}")
        self.port = port
        self.transport = transport
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self._sdk = None
        self._handle = None
        self._opened = False

        if self.transport == TRANSPORT_SDK:
            self._sdk = get_sdk(bin_dir)
            self._handle = self._sdk.testlib.get_switcher(port.encode("utf-8"))
            if not self._handle:
                raise RuntimeError(
                    f"在 {port} 上获取继电器句柄失败 (last_error={self._sdk.last_error()!r}); "
                    f"当前可用串口: {list_com_ports()}"
                )
        logger.info("继电器控制器已创建: %s (%s)", port, transport)

    def open(self) -> bool:
        """打开继电器连接。CDC 串口仅探测端口可打开性。"""
        if self.transport == TRANSPORT_SDK:
            ok = bool(self._sdk.testlib.switcher_open(self._handle))
        else:
            try:
                with serial.Serial(self.port, baudrate=self.baudrate, timeout=self.timeout,
                                   write_timeout=self.timeout):
                    pass
                ok = True
            except serial.SerialException as exc:
                logger.error("打开串口继电器 %s 失败: %s", self.port, exc)
                ok = False
        self._opened = ok
        logger.info("relay.open(%s, %s) -> %s", self.port, self.transport, ok)
        return ok

    def close(self) -> bool:
        """关闭 SDK 连接；串口协议按命令即开即关，无持久句柄。"""
        if self.transport == TRANSPORT_SDK:
            ok = bool(self._sdk.testlib.switcher_close(self._handle))
        else:
            ok = True
        self._opened = False
        logger.info("relay.close(%s, %s) -> %s", self.port, self.transport, ok)
        return ok

    def _serial_a0_command(self, channel: int, on: bool) -> bool:
        if channel < 0 or channel > 254:
            raise ValueError(f"通道超出 A0 协议范围: {channel}")
        # 协议通道从 1 起；对外 API 沿用项目的 0 起通道编号。
        wire_channel = channel + 1
        state = 1 if on else 0
        payload = bytes((0xA0, wire_channel, state, (0xA0 + wire_channel + state) & 0xFF))
        try:
            with serial.Serial(self.port, baudrate=self.baudrate, timeout=self.timeout,
                               write_timeout=self.timeout) as ser:
                ser.reset_input_buffer()
                written = ser.write(payload)
                ser.flush()
                response = ser.read(32)
            ok = written == len(payload)
            logger.info("serial_a0 %s ch%d: %s (%s; response=%s)",
                        "on" if on else "off", channel, ok, payload.hex(" "),
                        response.hex(" ") or "none")
            return ok
        except serial.SerialException as exc:
            logger.error("serial_a0 %s ch%d 失败: %s", "on" if on else "off", channel, exc)
            return False

    def open_channel(self, channel: int) -> bool:
        """导通指定通道。串口 A0 模式需要后续设备探活作为物理确认。"""
        if self.transport == TRANSPORT_SDK:
            ok = bool(self._sdk.testlib.switcher_open_channel(self._handle, int(channel)))
        else:
            ok = self._serial_a0_command(int(channel), True)
        logger.info("relay.open_channel(%s, ch%d, %s) -> %s", self.port, channel, self.transport, ok)
        return ok

    def close_channel(self, channel: int) -> bool:
        """断开指定通道。"""
        if self.transport == TRANSPORT_SDK:
            ok = bool(self._sdk.testlib.switcher_close_channel(self._handle, int(channel)))
        else:
            ok = self._serial_a0_command(int(channel), False)
        logger.info("relay.close_channel(%s, ch%d, %s) -> %s", self.port, channel, self.transport, ok)
        return ok

    def power_cycle(self, channel: int, off_seconds: float = 15.0,
                    settle_seconds: float = 1.0) -> bool:
        if not self.close_channel(channel):
            return False
        time.sleep(off_seconds)
        ok = self.open_channel(channel)
        time.sleep(settle_seconds)
        return ok

    def ensure_open(self, channel: int, retries: int = 3) -> bool:
        for _ in range(retries + 1):
            if self.open() and self.open_channel(channel):
                return True
            time.sleep(2)
        return False

    def self_test(self, channels=(0,)) -> dict:
        report = {}
        self.open()
        for ch in channels:
            ok_open = self.open_channel(ch)
            time.sleep(0.3)
            ok_close = self.close_channel(ch)
            report[ch] = ok_open and ok_close
        return report
