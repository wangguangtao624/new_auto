# -*- coding: utf-8 -*-
"""OTP 读写模块

打包 testlib.dll 的 OTP 增补接口 (TestDeviceExport.h):

    bool device_otp_read_unstore(dev, u16 base, u32 size, u8* out, u32 cap,
                                 u32* actual, u32 mode, u32 read_mode)
    bool device_otp_save_file(dev, u16 base, u32 size, const char* path,
                              u32 mode, u32 read_mode)
    bool device_otp_write(dev, u16 addr, const u8* data, u32 len,
                          u32 mode, u32 read_mode)
    u32  device_otp_get_function_flags(dev)
    void device_otp_set_function_flags(dev, u32 flags)

对应旧工程 test_group5 的 OTP_Read / OTP_Backup_Verify / OTP_Backup_Rewrite 用例。

⚠️ OTP 写入硬件不可逆, device_otp_write 默认需要 confirm=True 显式确认。

用法:
    from modules.otp import OtpController
    otp = OtpController(dev)
    ok, data = otp.read(0x0000, 64)            # 读 64 字节
    ok = otp.save_to_file(0x0000, 64, "otp.bin")
    flags = otp.get_flags()
"""
import logging
from ctypes import ARRAY, byref, c_uint8, c_uint16, c_uint32, create_string_buffer

from .sdk import OTP_MODE_WORK, OTP_MODE_RST, get_sdk

logger = logging.getLogger("new_auto.otp")


class OtpController:
    """OTP 读写控制器 (需设备句柄; 建议在 device.open 之后使用)"""

    MODE_WORK = OTP_MODE_WORK   # 0: 工作态访问
    MODE_RST = OTP_MODE_RST     # 1: 复位态访问

    def __init__(self, device, bin_dir=None):
        """:param device: 已创建的 PixelDevice"""
        self._device = device
        self._sdk = get_sdk(bin_dir)

    # ------------------------------------------------------------ 读

    def read(self, base_addr: int, size_bytes: int, otp_mode: int = OTP_MODE_WORK,
             otp_read_mode: int = 0):
        """读取 OTP 原始字节 (不经设备缓存)

        :param base_addr: OTP 起始地址
        :param size_bytes: 读取字节数
        :return: (是否成功, bytes)
        """
        fn = getattr(self._sdk.testlib, "device_otp_read_unstore", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_otp_read_unstore")
        out = (c_uint8 * size_bytes)()
        actual = c_uint32()
        self._sdk.clear_error()
        ok = bool(fn(self._device._handle, c_uint16(base_addr), c_uint32(size_bytes),
                     out, c_uint32(size_bytes), byref(actual),
                     c_uint32(otp_mode), c_uint32(otp_read_mode)))
        data = bytes(out[:actual.value]) if ok else b""
        logger.info("otp_read base=0x%04x size=%d -> %s (%d 字节)%s",
                    base_addr, size_bytes, ok, actual.value if ok else 0,
                    f" {data.hex()}" if ok and actual.value <= 64 else "")
        return ok, data

    def save_to_file(self, base_addr: int, size_bytes: int, file_path: str,
                     otp_mode: int = OTP_MODE_WORK, otp_read_mode: int = 0) -> bool:
        """读取 OTP 并保存到文件 (旧工程 OTP_Backup_Verify 的备份步骤)"""
        fn = getattr(self._sdk.testlib, "device_otp_save_file", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_otp_save_file")
        self._sdk.clear_error()
        ok = bool(fn(self._device._handle, c_uint16(base_addr), c_uint32(size_bytes),
                     str(file_path).encode("utf-8"),
                     c_uint32(otp_mode), c_uint32(otp_read_mode)))
        logger.info("otp_save_file base=0x%04x size=%d -> %s (%s)",
                    base_addr, size_bytes, ok, file_path)
        return ok

    # ------------------------------------------------------------ 写 (不可逆!)

    def write(self, addr: int, data: bytes, confirm: bool = False,
              otp_mode: int = OTP_MODE_WORK, otp_read_mode: int = 0) -> bool:
        """写 OTP — ⚠️ 硬件不可逆!

        :param confirm: 必须显式传 True 才会真正执行 (防误操作)
        """
        if not confirm:
            logger.error("OTP 写入被拒绝: OTP 硬件写入不可逆, 请以 confirm=True 显式确认")
            return False
        fn = getattr(self._sdk.testlib, "device_otp_write", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_otp_write")
        buf = (c_uint8 * len(data))(*data)
        self._sdk.clear_error()
        ok = bool(fn(self._device._handle, c_uint16(addr), buf,
                     c_uint32(len(data)), c_uint32(otp_mode), c_uint32(otp_read_mode)))
        logger.info("otp_write addr=0x%04x len=%d -> %s", addr, len(data), ok)
        return ok

    # ------------------------------------------------------------ 功能标志

    def get_flags(self) -> int:
        """读取 OTP 功能标志位掩码"""
        fn = getattr(self._sdk.testlib, "device_otp_get_function_flags", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_otp_get_function_flags")
        flags = int(fn(self._device._handle)) & 0xFFFFFFFF
        logger.info("otp_get_flags -> 0x%08x", flags)
        return flags

    def set_flags(self, flags: int) -> None:
        """设置 OTP 功能标志位掩码 (语义由模组固件定义)"""
        fn = getattr(self._sdk.testlib, "device_otp_set_function_flags", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_otp_set_function_flags")
        fn(self._device._handle, c_uint32(flags))
        logger.info("otp_set_flags(0x%08x)", flags)
