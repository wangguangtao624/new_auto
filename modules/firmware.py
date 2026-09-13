# -*- coding: utf-8 -*-
"""(d) 固件下载模块

打包两个层次的外部接口:

1) MatFwHandler_x64.dll (一键固件下载/回读库):
    int MatFwDownload(const char* ini_path, const char* fw_path, callback)
        - 内部自动完成: 打开设备 -> 进烧录模式 -> 传输 -> 校验
        - 通过回调上报 (status, progress, err), status/err 见 modules.sdk 常量
    int MatFwUpload(const char* ini_path, uint32 addr, uint32 length,
                    uint8* data, callback)
        - 从 flash 回读数据

2) testlib.dll 的 Flash 级固件接口 (手工烧录流程用):
    firmware_socReboot / firmware_set_start_address / firmware_set_update_end
    firmware_erase_flash(导出名为 firmware_earse_flash) / firmware_flash_set
    firmware_flash_crc_check / firmware_download2flash
    firmware_send_command / firmware_read_command        (固件 16 字节协议命令)
    firmware_detect / firmware_get_flash_log / firmware_get_info_string  (增补)

用法 (一键下载):
    from modules.firmware import FirmwareDownloader
    dl = FirmwareDownloader()
    ok = dl.download("configs/init_file/MAT130YV200_max96712_..._v1.0.6.ini",
                     "fw/MAT130AV200-FW-....bin")

用法 (手工 Flash 流程, 对应旧工程 _fw_update):
    ff = FirmwareFlasher(dev)
    ff.soc_reboot()
    ff.erase_flash(0, 63)
    ff.set_start_address(0x00000000)
    ff.download_from_file(fw_path, address=0, start=0, end=63)
"""
import logging
import time
from ctypes import ARRAY, byref, c_char, c_char_p, c_uint8, c_uint32, c_uint64, create_string_buffer

from .sdk import (
    FW_STATUS_CANCELED,
    FW_STATUS_FAILED,
    FW_STATUS_IN_PROGRESS,
    FW_STATUS_NONE,
    FW_STATUS_SUCCESS,
    MAT_FW_CALLBACK,
    describe_fw_error,
    get_sdk,
)

logger = logging.getLogger("new_auto.firmware")


# ================================================================ Flash 级

class FirmwareFlasher:
    """testlib.dll 的固件 Flash 操作 + 固件协议命令 (需设备已 open)"""

    def __init__(self, device, bin_dir=None):
        """:param device: 已创建的 PixelDevice"""
        self._device = device
        self._sdk = get_sdk(bin_dir)

    # ------------------------------------------------------------ 重启/地址

    def soc_reboot(self, need_confirm: bool = True) -> bool:
        """让固件 SOC 重启"""
        ok = bool(self._sdk.testlib.firmware_socReboot(self._device._handle, need_confirm))
        logger.info("firmware_socReboot -> %s", ok)
        return ok

    def set_start_address(self, address: int, need_confirm: bool = True) -> bool:
        """设置烧录起始地址"""
        ok = bool(self._sdk.testlib.firmware_set_start_address(
            self._device._handle, c_uint32(address), need_confirm))
        logger.info("firmware_set_start_address(0x%08x) -> %s", address, ok)
        return ok

    def set_update_end(self) -> bool:
        """标记固件更新结束 (触发固件侧收尾)"""
        ok = bool(self._sdk.testlib.firmware_set_update_end(self._device._handle))
        logger.info("firmware_set_update_end -> %s", ok)
        return ok

    # ------------------------------------------------------------ 擦除/写入/校验

    def erase_flash(self, start_addr: int, end_addr: int) -> bool:
        """擦除 Flash 扇区区间 [start_addr, end_addr] (扇区号, 4KB/扇区)"""
        self._sdk.clear_error()
        ok = bool(self._sdk.testlib.firmware_erase_flash(
            self._device._handle, c_uint32(start_addr), c_uint32(end_addr)))
        logger.info("firmware_erase_flash(%d-%d) -> %s%s",
                    start_addr, end_addr, ok,
                    "" if ok else f" dll_err={self._sdk.last_error()!r}")
        return ok

    def flash_set(self, start_addr: int, end_addr: int) -> bool:
        """设定 Flash 操作区间"""
        ok = bool(self._sdk.testlib.firmware_flash_set(
            self._device._handle, c_uint32(start_addr), c_uint32(end_addr)))
        logger.info("firmware_flash_set(%d-%d) -> %s", start_addr, end_addr, ok)
        return ok

    def flash_crc_check(self, start_addr: int, end_addr: int):
        """对 Flash 区间做 CRC 校验

        :return: (是否成功, CRC 值)
        """
        crc = c_uint32()
        ok = bool(self._sdk.testlib.firmware_flash_crc_check(
            self._device._handle, c_uint32(start_addr), c_uint32(end_addr), byref(crc)))
        logger.info("firmware_flash_crc_check(%d-%d) -> %s crc=0x%08x",
                    start_addr, end_addr, ok, crc.value if ok else 0)
        return ok, (crc.value if ok else 0)

    def download_to_flash(self, data: bytes, address: int,
                          start: int, end: int) -> bool:
        """把二进制数据写入 Flash

        :param data: 固件数据 (bytes)
        :param address: 目标 Flash 地址
        :param start: 扇区起始边界
        :param end: 扇区结束边界
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data 必须是 bytes/bytearray")
        self._sdk.clear_error()
        ok = bool(self._sdk.testlib.firmware_download2flash(
            self._device._handle, bytes(data), c_uint32(len(data)),
            c_uint32(address), c_uint32(start), c_uint32(end)))
        if ok:
            logger.info("firmware_download2flash: %d 字节 -> 0x%08x 成功", len(data), address)
        else:
            logger.error("firmware_download2flash 失败, dll_err=%r", self._sdk.last_error())
        return ok

    def download_from_file(self, file_path: str, address: int,
                           start: int, end: int) -> bool:
        """从 .bin 文件写入 Flash"""
        with open(file_path, "rb") as f:
            data = f.read()
        logger.info("从文件烧录: %s (%d 字节) -> addr=0x%08x sector[%d,%d]",
                    file_path, len(data), address, start, end)
        return self.download_to_flash(data, address, start, end)

    # ------------------------------------------------------------ 固件协议命令

    def send_command(self, data: bytes, need_confirm: bool = True,
                     interval_ms: int = 5000, times: int = 3) -> bool:
        """发送 16 字节固件协议命令"""
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data 必须是 bytes/bytearray")
        self._sdk.clear_error()
        buf = (c_uint8 * len(data))(*data)
        ok = bool(self._sdk.testlib.firmware_send_command(
            self._device._handle, buf, need_confirm,
            c_uint32(interval_ms), c_uint32(times)))
        logger.info("firmware_send_command(%s) -> %s", data.hex(), ok)
        return ok

    def read_command(self):
        """读取固件协议响应 (12 字节载荷)

        :return: (是否成功, [12 个字节的列表])
        """
        self._sdk.clear_error()
        buf = create_string_buffer(12)
        ok = bool(self._sdk.testlib.firmware_read_command(self._device._handle, buf))
        if not ok:
            logger.error("firmware_read_command 失败, dll_err=%r", self._sdk.last_error())
            return False, [0] * 12
        payload = list(buf.raw[:12])
        logger.info("firmware_read_command -> %s", [hex(b) for b in payload])
        return True, payload

    # ------------------------------------------------------------ 增补信息接口

    def detect(self, read_customer_id: bool = True) -> bool:
        """探测固件是否在位应答 (增补接口, 旧 DLL 可能没有)"""
        fn = getattr(self._sdk.testlib, "firmware_detect", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 firmware_detect")
        self._sdk.clear_error()
        ok = bool(fn(self._device._handle, read_customer_id))
        logger.info("firmware_detect -> %s", ok)
        return ok

    def get_flash_log(self):
        """读取 flash 日志中的重启计数与看门狗复位计数 (增补接口)

        :return: (是否成功, reboot_count, watchdog_reset_count)
        """
        fn = getattr(self._sdk.testlib, "firmware_get_flash_log", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 firmware_get_flash_log")
        reboot_cnt = c_uint32()
        wdg_cnt = c_uint32()
        ok = bool(fn(self._device._handle, byref(reboot_cnt), byref(wdg_cnt)))
        logger.info("firmware_get_flash_log -> %s reboot=%d wdg=%d",
                    ok, reboot_cnt.value if ok else -1, wdg_cnt.value if ok else -1)
        return ok, reboot_cnt.value, wdg_cnt.value

    def get_info_string(self, info_id: int) -> str:
        """读取固件信息字符串 (版本/编译时间等, 增补接口)

        :param info_id: modules.sdk.FW_INFO_* 常量
        """
        fn = getattr(self._sdk.testlib, "firmware_get_info_string", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 firmware_get_info_string")
        buf = create_string_buffer(256)
        self._sdk.clear_error()
        ok = bool(fn(self._device._handle, c_uint32(info_id), buf, 256))
        if not ok:
            raise RuntimeError(f"firmware_get_info_string({info_id}) 失败")
        return buf.value.decode("utf-8", errors="replace")


# ================================================================ 一键下载

class FirmwareDownloader:
    """MatFwHandler_x64.dll 的一键固件下载 / 回读"""

    def __init__(self, bin_dir=None):
        self._sdk = get_sdk(bin_dir)
        if not hasattr(self._sdk.matfw, "MatFwDownload"):
            raise RuntimeError("MatFwHandler_x64.dll 中未找到 MatFwDownload")

    # ------------------------------------------------------------ 回调

    @staticmethod
    def _make_callback(on_event=None) -> MAT_FW_CALLBACK:
        """构造 MatFwDownload/MatFwUpload 的进度回调

        :param on_event: 可选自定义回调 fn(status, progress, err)
        """

        def _cb(status: int, progress: int, err: int):
            if status == FW_STATUS_IN_PROGRESS:
                if progress == -1:
                    logger.info("fw task not started")
                else:
                    logger.info("fw progress: %d%%", progress)
            elif status == FW_STATUS_SUCCESS:
                logger.info("fw task SUCCESS")
            elif status == FW_STATUS_FAILED:
                logger.error("fw task FAILED: err=%d (%s)", err, describe_fw_error(err))
            elif status == FW_STATUS_CANCELED:
                logger.warning("fw task CANCELED")
            elif status == FW_STATUS_NONE:
                logger.info("fw task NONE")
            if on_event is not None:
                try:
                    on_event(status, progress, err)
                except Exception:  # 回调里不允许抛异常进 C 层
                    logger.exception("用户回调异常(已忽略)")

        return MAT_FW_CALLBACK(_cb)

    # ------------------------------------------------------------ 下载

    def download(self, ini_path: str, fw_path: str,
                 max_retries: int = 3, retry_delay: float = 2.0,
                 on_event=None) -> bool:
        """一键固件下载 (MatFwDownload)

        :param ini_path: 上电初始化 ini (决定链路/解串器/I2C 配置)
        :param fw_path: 固件 .bin 路径
        :param max_retries: 失败重试次数 (旧工程为 10, 收敛为 3)
        :param on_event: fn(status, progress, err) 进度回调
        :return: 是否成功
        """
        ini_bytes = str(ini_path).encode("utf-8")
        fw_bytes = str(fw_path).encode("utf-8")

        for attempt in range(1, max_retries + 1):
            logger.info("MatFwDownload 第 %d/%d 次: ini=%s fw=%s",
                        attempt, max_retries, ini_path, fw_path)
            cb = self._make_callback(on_event)
            try:
                ret = self._sdk.matfw.MatFwDownload(ini_bytes, fw_bytes, cb)
            except Exception:
                logger.exception("MatFwDownload 调用异常")
                ret = -1

            if ret == 0:
                logger.info("固件下载成功: %s", fw_path)
                return True
            logger.error("MatFwDownload 返回 %d (%s)",
                         ret, describe_fw_error(ret) if ret < 0 else "未知")
            if attempt < max_retries:
                time.sleep(retry_delay)
        logger.error("固件下载失败, 已重试 %d 次", max_retries)
        return False

    # ------------------------------------------------------------ 回读

    def upload(self, ini_path: str, addr: int, length: int,
               timeout: float = 120.0, on_event=None):
        """从 flash 回读数据 (MatFwUpload)

        :param ini_path: 上电初始化 ini
        :param addr: 起始地址
        :param length: 读取字节数
        :param timeout: 占位参数 (回调驱动, 由上层自行等待)
        :return: (是否成功, bytes)
        """
        fn = getattr(self._sdk.matfw, "MatFwUpload", None)
        if fn is None:
            raise NotImplementedError("当前 MatFwHandler_x64.dll 未导出 MatFwUpload")
        buf = (c_uint8 * length)()
        cb = self._make_callback(on_event)
        ret = int(fn(str(ini_path).encode("utf-8"), c_uint32(addr),
                     c_uint32(length), buf, cb))
        ok = (ret == 0)
        logger.info("MatFwUpload addr=0x%08x len=%d -> ret=%d", addr, length, ret)
        return ok, bytes(buf) if ok else b""
