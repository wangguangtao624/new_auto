# -*- coding: utf-8 -*-
"""PixelIDE 底层 SDK 加载器 (公共依赖模块)

负责两件事:
1. 加载两个外部 DLL 并绑定全部导出函数的 ctypes 原型:
   - testlib.dll          : PixelIDE 测试主库 (设备/继电器/I2C/视频流/Flash/OTP)
   - MatFwHandler_x64.dll : 固件一键下载/回读库
   函数签名依据 bin/TestDeviceExport.h 与 bin/MatFwHandler.h。
2. 提供 last_error() 助手, 读取 testlib 线程级最近错误文本。

其余四个功能模块 (relay/device/i2c/firmware) 都基于本模块拿到的 DLL 句柄工作。
"""
import ctypes
import os
from ctypes import (
    WINFUNCTYPE,
    byref,
    c_bool,
    c_char_p,
    c_float,
    c_int,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
    c_void_p,
    cdll,
    create_string_buffer,
    POINTER,
)
from pathlib import Path

# ---------------------------------------------------------------- 路径解析

_PACKAGE_DIR = Path(__file__).resolve().parent      # new_auto/modules
_PROJECT_ROOT = _PACKAGE_DIR.parent                 # new_auto/
_DEFAULT_BIN_DIR = _PROJECT_ROOT / "bin"

# testlib.dll 除 Qt6/Dothinkey 外还依赖完整 PixelIDE 部署中的 device.dll /
# imageviewer.dll, 仅靠 bin/ 下 8 个基础 DLL 无法解析 -> 优先从完整部署加载。
# 常见部署位置按序探测, 也可在 config.json 中显式指定 (paths.pixelide_dir)。
_KNOWN_PIXELIDE_DIRS = [
    Path(r"D:\PixelIde\pixelide_release\PixelIDE"),          # 旧工程 config 默认
    Path(r"F:\Duxin\IDE_resently\pixelide_release\PixelIDE"),  # 本机完整部署
]


def _resolve_dll(name: str, bin_dir=None, pixelide_dir=None) -> Path:
    """DLL 定位顺序: 显式指定 > 完整 PixelIDE 部署 > new_auto/bin"""
    candidates = []
    if pixelide_dir is not None:
        candidates.append(Path(pixelide_dir) / name)
    else:
        for d in _KNOWN_PIXELIDE_DIRS:
            if (d / name).exists():
                candidates.append(d / name)
    if bin_dir is not None:
        candidates.append(Path(bin_dir) / name)
    candidates.append(_DEFAULT_BIN_DIR / name)
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"未找到 {name}, 尝试过: {[str(c) for c in candidates]}"
    )


# ---------------------------------------------------------------- 错误码常量

# testlib.dll 固件下载状态 (MatFwHandler.h MatFwHandleStatus)
FW_STATUS_NONE = 0            # 未开始
FW_STATUS_IN_PROGRESS = 1     # 进行中 (progress: 0~100, 未开始为 -1)
FW_STATUS_SUCCESS = 2         # 成功
FW_STATUS_FAILED = 3          # 失败 (err 为下列错误码之一)
FW_STATUS_CANCELED = 4        # 被取消

# MatFwHandler.h MatFwHandleError
FW_ERR_OK = 0
FW_ERR_INVALID_PARAM = -1     # 无效参数
FW_ERR_OPEN_INI = -2          # 打开 ini 失败
FW_ERR_OPEN_FW = -3           # 打开固件文件失败
FW_ERR_IN_PROGRESS = -4       # 上一个任务进行中
FW_ERR_OPEN_DEVICE = -5       # 打开设备失败
FW_ERR_COMM_DEVICE = -6       # 通信失败
FW_ERR_FW_MATCH = -7          # 固件文件不匹配
FW_ERR_FW_BURN_MODE = -8      # 进入烧录模式失败
FW_ERR_FW_TRANS = -9          # 数据传输失败
FW_ERR_SET_ADDR = -10         # 设置起始地址失败
FW_ERR_SET_MULTI_ADDR = -11   # 设置多重地址失败
FW_ERR_DISABLED_ALOG = -12    # 算法被禁用
FW_ERR_INTERNAL = -100        # 内部错误

FW_ERROR_MESSAGES = {
    FW_ERR_OK: "操作成功",
    FW_ERR_INVALID_PARAM: "无效参数",
    FW_ERR_OPEN_INI: "打开INI文件失败",
    FW_ERR_OPEN_FW: "打开固件文件失败",
    FW_ERR_IN_PROGRESS: "上一个下载任务正在进行中",
    FW_ERR_OPEN_DEVICE: "打开设备失败",
    FW_ERR_COMM_DEVICE: "通信失败",
    FW_ERR_FW_MATCH: "固件文件不正确",
    FW_ERR_FW_BURN_MODE: "启用烧录模式失败",
    FW_ERR_FW_TRANS: "数据传输失败",
    FW_ERR_SET_ADDR: "设置起始地址失败",
    FW_ERR_SET_MULTI_ADDR: "设置多重地址失败",
    FW_ERR_DISABLED_ALOG: "算法被禁用",
    FW_ERR_INTERNAL: "内部错误",
}

# firmware_get_info_string 的 info_id (TestDeviceExport.h)
FW_INFO_FIRMWARE_VERSION = 0
FW_INFO_ROM_VERSION = 1
FW_INFO_SRAM_VERSION = 2
FW_INFO_BUILD_TIME = 3
FW_INFO_STATUS = 4
FW_INFO_CUSTOMER_ID = 5
FW_INFO_JENKINS_LINK = 6

# OTP 访问模式
OTP_MODE_WORK = 0
OTP_MODE_RST = 1

# MatFwDownload / MatFwUpload 回调类型: void cb(int status, int progress, int err)
MAT_FW_CALLBACK = WINFUNCTYPE(None, c_int, c_int, c_int)


def describe_fw_error(err: int) -> str:
    """把 MatFwHandler 错误码翻译成可读文本"""
    return FW_ERROR_MESSAGES.get(err, f"未知错误码 {err}")


# ---------------------------------------------------------------- SDK 类

class PixelIDESdk:
    """testlib.dll + MatFwHandler_x64.dll 的加载与原型绑定

    用法:
        sdk = PixelIDESdk()          # 加载 DLL, init_qt()
        sdk.testlib                  # testlib.dll 句柄 (设备/继电器/I2C/Flash)
        sdk.matfw                    # MatFwHandler_x64.dll 句柄 (固件下载)
    """

    def __init__(self, bin_dir=None, pixelide_dir=None, init_qt: bool = True):
        self._bin_dir = Path(bin_dir) if bin_dir else _DEFAULT_BIN_DIR

        # 把 DLL 所在目录加入搜索路径, 让依赖 (Qt6Core/Qt6Gui/dtccm2/device.dll
        # 等) 能被自动解析
        testlib_path = _resolve_dll("testlib.dll", self._bin_dir, pixelide_dir)
        matfw_path = _resolve_dll("MatFwHandler_x64.dll", self._bin_dir, pixelide_dir)
        for d in {testlib_path.parent, matfw_path.parent, self._bin_dir}:
            if d.is_dir():
                os.add_dll_directory(str(d))
                os.environ["PATH"] = f"{d}{os.pathsep}{os.environ.get('PATH', '')}"

        self.testlib_path = testlib_path
        self.matfw_path = matfw_path

        self.testlib = ctypes.WinDLL(str(testlib_path))
        self.matfw = ctypes.WinDLL(str(matfw_path))

        self._bind_testlib()
        self._bind_matfw()

        # init_qt 必须在其它 testlib 函数之前调用一次 (非线程安全)
        if init_qt:
            self.testlib.init_qt()

    # ------------------------------------------------------------ testlib

    def _bind_testlib(self):
        dll = self.testlib

        # --- QT 环境 ---
        dll.init_qt.argtypes = []
        dll.init_qt.restype = None

        # --- 设备管理 ---
        dll.get_device.argtypes = [c_char_p]
        dll.get_device.restype = c_void_p

        dll.release_device.argtypes = [c_void_p]
        dll.release_device.restype = None

        dll.get_device_focus_channel.argtypes = [c_char_p]      # char* out (>=256B)
        dll.get_device_focus_channel.restype = None

        dll.set_device_focus_channel.argtypes = [c_char_p]
        dll.set_device_focus_channel.restype = c_bool

        # --- 设备连接 ---
        dll.device_open.argtypes = [c_void_p]
        dll.device_open.restype = c_bool

        dll.device_close.argtypes = [c_void_p]
        dll.device_close.restype = None

        dll.device_setConfigure.argtypes = [c_void_p, c_char_p]
        dll.device_setConfigure.restype = None

        # --- 视频流 ---
        dll.device_open_video.argtypes = [c_void_p]
        dll.device_open_video.restype = c_bool

        _opt(dll, "device_close_video", [c_void_p], c_bool)
        _opt(dll, "device_stop_streaming", [c_void_p], c_bool)

        dll.device_grab_one_frame.argtypes = [c_void_p]
        dll.device_grab_one_frame.restype = c_bool

        dll.device_grab_one_frame_save.argtypes = [c_void_p, c_char_p, c_char_p]
        dll.device_grab_one_frame_save.restype = c_bool

        _opt(
            dll,
            "device_grab_one_frame_save_ex",
            [c_void_p, c_char_p, c_char_p, POINTER(c_uint64)],
            c_bool,
        )

        dll.device_get_fps.argtypes = [c_void_p, POINTER(c_float)]
        dll.device_get_fps.restype = c_bool

        dll.device_get_current_DN.argtypes = [c_void_p, POINTER(c_float)]
        dll.device_get_current_DN.restype = c_bool

        # --- I2C 寄存器级读写 (旧工程主用) ---
        dll.device_I2C_Read.argtypes = [
            c_void_p,            # device
            c_uint8,             # slaveID (7-bit)
            c_uint32,            # address
            POINTER(c_uint32),   # result out
            c_int,               # addrlength: 地址宽度 8/16/32
            c_int,               # dataSize:  数据位宽 8/16/32
        ]
        dll.device_I2C_Read.restype = c_bool

        dll.device_I2C_Write.argtypes = [
            c_void_p,
            c_uint8,
            c_uint32,
            c_uint32,            # value
            c_int,
            c_int,
        ]
        dll.device_I2C_Write.restype = c_bool

        # --- I2C 字节流读写 (TestDeviceExport.h 增补接口) ---
        _opt(
            dll,
            "device_I2C_Read_Data",
            [c_void_p, c_uint8, c_uint16, c_uint8, POINTER(c_uint8), c_uint16],
            c_bool,
        )
        _opt(
            dll,
            "device_I2C_Write_Data",
            [c_void_p, c_uint8, c_uint16, c_uint8, POINTER(c_uint8), c_uint16],
            c_bool,
        )

        # --- 继电器 (串口通道切换器) ---
        dll.get_switcher.argtypes = [c_char_p]                  # "COM3"
        dll.get_switcher.restype = c_void_p

        dll.switcher_open.argtypes = [c_void_p]
        dll.switcher_open.restype = c_bool

        dll.switcher_close.argtypes = [c_void_p]
        dll.switcher_close.restype = c_bool

        dll.switcher_open_channel.argtypes = [c_void_p, c_int]  # channel 从 0 起
        dll.switcher_open_channel.restype = c_bool

        dll.switcher_close_channel.argtypes = [c_void_p, c_int]
        dll.switcher_close_channel.restype = c_bool

        # --- 固件: Flash 级操作 ---
        dll.firmware_socReboot.argtypes = [c_void_p, c_bool]
        dll.firmware_socReboot.restype = c_bool

        dll.firmware_set_start_address.argtypes = [c_void_p, c_uint32, c_bool]
        dll.firmware_set_start_address.restype = c_bool

        dll.firmware_set_update_end.argtypes = [c_void_p]
        dll.firmware_set_update_end.restype = c_bool

        # DLL 实际导出名为 firmware_earse_flash (官方拼写错误), 做兼容
        if hasattr(dll, "firmware_erase_flash"):
            dll.firmware_erase_flash.argtypes = [c_void_p, c_uint32, c_uint32]
            dll.firmware_erase_flash.restype = c_bool
        elif hasattr(dll, "firmware_earse_flash"):
            dll.firmware_erase_flash = dll.firmware_earse_flash
            dll.firmware_erase_flash.argtypes = [c_void_p, c_uint32, c_uint32]
            dll.firmware_erase_flash.restype = c_bool
        else:  # pragma: no cover
            dll.firmware_erase_flash = lambda *a: False

        dll.firmware_flash_set.argtypes = [c_void_p, c_uint32, c_uint32]
        dll.firmware_flash_set.restype = c_bool

        dll.firmware_flash_crc_check.argtypes = [
            c_void_p, c_uint32, c_uint32, POINTER(c_uint32)
        ]
        dll.firmware_flash_crc_check.restype = c_bool

        dll.firmware_download2flash.argtypes = [
            c_void_p,            # device
            c_char_p,            # data
            c_uint32,            # dataSize
            c_uint32,            # address
            c_uint32,            # start (扇区边界)
            c_uint32,            # end   (扇区边界)
        ]
        dll.firmware_download2flash.restype = c_bool

        # --- 固件: 协议命令 / 信息 ---
        dll.firmware_send_command.argtypes = [
            c_void_p,            # device
            POINTER(c_uint8),    # command bytes (16B)
            c_bool,              # confirm
            c_uint32,            # interval (ms)
            c_uint32,            # times
        ]
        dll.firmware_send_command.restype = c_bool

        dll.firmware_read_command.argtypes = [c_void_p, POINTER(ctypes.c_char)]
        dll.firmware_read_command.restype = c_bool

        _opt(dll, "firmware_detect", [c_void_p, c_bool], c_bool)
        _opt(
            dll,
            "firmware_get_flash_log",
            [c_void_p, POINTER(c_uint32), POINTER(c_uint32)],
            c_bool,
        )
        _opt(
            dll,
            "firmware_get_info_string",
            [c_void_p, c_uint32, c_char_p, c_uint32],
            c_bool,
        )

        # --- OTP ---
        _opt(
            dll,
            "device_otp_read_unstore",
            [
                c_void_p, c_uint16, c_uint32,
                POINTER(c_uint8), c_uint32, POINTER(c_uint32),
                c_uint32, c_uint32,
            ],
            c_bool,
        )
        _opt(
            dll,
            "device_otp_save_file",
            [c_void_p, c_uint16, c_uint32, c_char_p, c_uint32, c_uint32],
            c_bool,
        )
        _opt(
            dll,
            "device_otp_write",
            [c_void_p, c_uint16, POINTER(c_uint8), c_uint32, c_uint32, c_uint32],
            c_bool,
        )
        _opt(dll, "device_otp_get_function_flags", [c_void_p], c_uint32)
        _opt(dll, "device_otp_set_function_flags", [c_void_p, c_uint32], None)

        # --- 错误助手 ---
        dll.testlib_get_last_error.argtypes = [c_char_p, c_uint32]
        dll.testlib_get_last_error.restype = None

        dll.testlib_clear_last_error.argtypes = []
        dll.testlib_clear_last_error.restype = None

    # ------------------------------------------------------------ matfw

    def _bind_matfw(self):
        dll = self.matfw

        # int MatFwDownload(const char* ini_path, const char* fw_path, MatFwHandleCallback cb)
        if hasattr(dll, "MatFwDownload"):
            dll.MatFwDownload.argtypes = [c_char_p, c_char_p, MAT_FW_CALLBACK]
            dll.MatFwDownload.restype = c_int

        # int MatFwUpload(const char* ini_path, uint32_t addr, uint32_t length,
        #                 uint8_t* data, MatFwHandleCallback cb)
        if hasattr(dll, "MatFwUpload"):
            dll.MatFwUpload.argtypes = [
                c_char_p, c_uint32, c_uint32, POINTER(c_uint8), MAT_FW_CALLBACK
            ]
            dll.MatFwUpload.restype = c_int

    # ------------------------------------------------------------ 助手

    def last_error(self) -> str:
        """读取 testlib 线程级最近一次错误文本 (无错误时为空串)"""
        buf = create_string_buffer(512)
        self.testlib.testlib_get_last_error(buf, 512)
        return buf.value.decode("utf-8", errors="replace").strip()

    def clear_error(self):
        """清空 testlib 线程级错误缓存 (在关键调用前调用, 便于定位真因)"""
        self.testlib.testlib_clear_last_error()


# 单例: 各模块共用同一份 DLL 句柄与 init_qt 状态
_sdk_instance = None


def get_sdk(bin_dir=None) -> PixelIDESdk:
    """获取全局 PixelIDESdk 单例 (首次调用时加载 DLL 并 init_qt)"""
    global _sdk_instance
    if _sdk_instance is None:
        _sdk_instance = PixelIDESdk(bin_dir=bin_dir)
    return _sdk_instance


def _opt(dll, name, argtypes, restype):
    """绑定可选导出函数: 旧版 testlib.dll 可能没有这些增补接口"""
    if hasattr(dll, name):
        fn = getattr(dll, name)
        fn.argtypes = argtypes
        fn.restype = restype
