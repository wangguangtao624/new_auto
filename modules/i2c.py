# -*- coding: utf-8 -*-
"""(c) I2C 读写模块

打包 testlib.dll 中的 I2C 接口, 全部经由已打开的设备 (Dothinkey 采集卡 ->
串行解串器 -> 模组) 链路访问:

    bool device_I2C_Read(void* dev, uint8 slave, uint32 addr,
                         uint32* out, int addrlength, int dataSize)
    bool device_I2C_Write(void* dev, uint8 slave, uint32 addr,
                          uint32 value, int addrlength, int dataSize)
    bool device_I2C_Read_Data(void* dev, uint8 slave, uint16 reg,
                              uint8 regSize, uint8* buf, uint16 len)   # 增补
    bool device_I2C_Write_Data(void* dev, uint8 slave, uint16 reg,
                               uint8 regSize, uint8* buf, uint16 len)  # 增补

参数约定 (与旧工程一致):
    addrlength / dataSize 取 8 / 16 / 32, 表示寄存器地址宽度与数据位宽(位)。
    固件寄存器一般为 16 位地址 + 16/32 位数据, 即 (16, 16) 或 (16, 32)。

对应现场硬件: MAT130YV200 固件 I2C Slave 地址 0x40。

用法:
    from modules.device import PixelDevice
    from modules.i2c import I2CController
    dev = PixelDevice("MAT130YV200"); dev.open()
    i2c = I2CController(dev, default_slave=0x40)
    ok, ver = i2c.read(0x00d8, addr_len=16, bits=32)   # 读固件版本寄存器
    ok = i2c.write(0x0918, 0x0001)                     # 打开 AWB (16,16)
"""
import logging
from ctypes import ARRAY, byref, c_uint8, c_uint16, c_uint32, create_string_buffer

from .sdk import get_sdk

logger = logging.getLogger("new_auto.i2c")


class I2CController:
    """I2C 寄存器读写控制器"""

    def __init__(self, device, default_slave: int = 0x40, bin_dir=None):
        """:param device: 已创建的 PixelDevice (使用其句柄)
        :param default_slave: 默认从机地址 (现场固件为 0x40)
        """
        self._device = device
        self._sdk = get_sdk(bin_dir)
        self.default_slave = int(default_slave)

    # ------------------------------------------------------------ 寄存器级

    def read(self, address: int, slave: int = None,
             addr_len: int = 16, bits: int = 16):
        """读一个寄存器

        :param address: 寄存器地址
        :param slave: 从机地址; 缺省用 default_slave (0x40)
        :param addr_len: 寄存器地址宽度 8/16/32
        :param bits: 数据位宽 8/16/32
        :return: (是否成功, 读到的值)
        """
        slave = self.default_slave if slave is None else slave
        value = c_uint32()
        self._sdk.clear_error()
        ok = bool(self._sdk.testlib.device_I2C_Read(
            self._device._handle, c_uint8(slave), c_uint32(address),
            byref(value), int(addr_len), int(bits),
        ))
        if ok:
            logger.info(
                "I2C_Read slave=0x%02x addr=0x%04x (%d,%d) -> 0x%x",
                slave, address, addr_len, bits, value.value,
            )
        else:
            logger.error(
                "I2C_Read 失败 slave=0x%02x addr=0x%04x (%d,%d), dll_err=%r",
                slave, address, addr_len, bits, self._sdk.last_error(),
            )
        return ok, value.value

    def write(self, address: int, value: int, slave: int = None,
              addr_len: int = 16, bits: int = 16) -> bool:
        """写一个寄存器

        :param address: 寄存器地址
        :param value: 要写入的值
        :param slave: 从机地址; 缺省用 default_slave (0x40)
        :param addr_len: 寄存器地址宽度 8/16/32
        :param bits: 数据位宽 8/16/32
        :return: 是否成功
        """
        slave = self.default_slave if slave is None else slave
        self._sdk.clear_error()
        ok = bool(self._sdk.testlib.device_I2C_Write(
            self._device._handle, c_uint8(slave), c_uint32(address),
            c_uint32(value), int(addr_len), int(bits),
        ))
        if ok:
            logger.info(
                "I2C_Write slave=0x%02x addr=0x%04x val=0x%x (%d,%d) -> ok",
                slave, address, value, addr_len, bits,
            )
        else:
            logger.error(
                "I2C_Write 失败 slave=0x%02x addr=0x%04x val=0x%x (%d,%d), dll_err=%r",
                slave, address, value, addr_len, bits, self._sdk.last_error(),
            )
        return ok

    # ------------------------------------------------------------ 字节流级

    def read_bytes(self, reg: int, length: int, reg_size: int = 2,
                   slave: int = None):
        """批量读原始字节 (device_I2C_Read_Data; 需 testlib 支持该增补导出)

        :param reg: 寄存器地址 (低 16 位)
        :param length: 要读取的字节数
        :param reg_size: 寄存器地址宽度(字节), 1 或 2
        :return: (是否成功, bytes)
        """
        slave = self.default_slave if slave is None else slave
        fn = getattr(self._sdk.testlib, "device_I2C_Read_Data", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_I2C_Read_Data")
        buf = (c_uint8 * length)()
        self._sdk.clear_error()
        ok = bool(fn(
            self._device._handle, c_uint8(slave), c_uint16(reg),
            c_uint8(reg_size), buf, c_uint16(length),
        ))
        data = bytes(buf) if ok else b""
        logger.info("I2C_Read_Data slave=0x%02x reg=0x%04x len=%d -> %s %s",
                    slave, reg, length, ok, data.hex() if ok else "")
        return ok, data

    def write_bytes(self, reg: int, data: bytes, reg_size: int = 2,
                    slave: int = None) -> bool:
        """批量写原始字节 (device_I2C_Write_Data; 需 testlib 支持该增补导出)"""
        slave = self.default_slave if slave is None else slave
        fn = getattr(self._sdk.testlib, "device_I2C_Write_Data", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_I2C_Write_Data")
        arr = (c_uint8 * len(data))(*data)
        self._sdk.clear_error()
        ok = bool(fn(
            self._device._handle, c_uint8(slave), c_uint16(reg),
            c_uint8(reg_size), arr, c_uint16(len(data)),
        ))
        logger.info("I2C_Write_Data slave=0x%02x reg=0x%04x len=%d -> %s",
                    slave, reg, len(data), ok)
        return ok

    # ------------------------------------------------------------ 常用组合

    def read_ro(self, address: int, addr_len: int = 16, bits: int = 16,
                slave: int = None):
        """只读探测 (失败不抛异常, 返回 (False, None)) — 用于探活"""
        ok, value = self.read(address, slave=slave, addr_len=addr_len, bits=bits)
        return (ok, value if ok else None)

    def write_readback(self, address: int, value: int, addr_len: int = 16,
                       bits: int = 16, slave: int = None):
        """写后回读校验, 返回 (写是否成功, 回读值, 是否与写入值一致)"""
        ok_w = self.write(address, value, slave=slave, addr_len=addr_len, bits=bits)
        ok_r, read_val = self.read(address, slave=slave, addr_len=addr_len, bits=bits)
        return ok_w and ok_r, read_val, (ok_r and read_val == value)
