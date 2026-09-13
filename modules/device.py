# -*- coding: utf-8 -*-
"""(b) 外部设备控制模块

打包 testlib.dll 中的设备管理 / 视频流接口:

    void* get_device(const char* name)                 按名称取设备句柄
    void  release_device(void* dev)                    释放设备句柄
    void  get_device_focus_channel(char* out)          读 Dothinkey 当前聚焦通道
    bool  set_device_focus_channel(const char* name)   设置 Dothinkey 聚焦通道
    bool  device_open(void* dev)                       建立设备连接
    void  device_close(void* dev)                      断开设备连接
    void  device_setConfigure(void* dev, const char* ini)  下发 ini 初始化配置
    bool  device_open_video(void* dev)                 打开视频流
    bool  device_grab_one_frame(void* dev)             抓一帧
    bool  device_grab_one_frame_save(void* dev, path, name)  抓一帧并存盘
    bool  device_get_fps(void* dev, float* fps)        读 FPS
    bool  device_get_current_DN(void* dev, float* DN)  读当前 DN (亮度) 值

对应现场硬件: MAT130YV200 模组, 经 MAX96712 串行解串器出图,
初始化 ini 使用 configs/init_file/MAT130YV200_max96712_max96701_..._v1.0.6.ini。

用法:
    from modules.device import PixelDevice
    dev = PixelDevice("MAT130YV200")
    dev.set_configure("configs/init_file/MAT130YV200_max96712_..._v1.0.6.ini")
    dev.open()
    dev.open_video()
    ok = dev.grab_frame()
    print(dev.get_fps())
    dev.close(); dev.release()
"""
import ctypes
import logging
import time
from ctypes import byref, c_float, c_uint64, create_string_buffer

from .sdk import get_sdk

logger = logging.getLogger("new_auto.device")

# 旧工程 get_device 的名称归一化规则 (testlib 内部只认这些名字)
_DEVICE_NAME_MAP = {
    "MAT130AV200": "MAT130YV200",
    "MAT130YV200": "MAT130YV200",
    "MAT330AV100": "MAT330AV100",
    "MAT331AV100": "MAT330AV100",
    "MAT330AV200": "MAT330AV200",
    "MAT331AV200": "MAT330AV200",
    "MAT130AV300": "MAT130V300",
}


class PixelDevice:
    """外部图像设备 (相机模组 + Dothinkey 采集卡) 控制器"""

    def __init__(self, device_name: str = "MAT130YV200", bin_dir=None):
        """获取设备句柄 (不建立连接)

        :param device_name: 设备名, 如 "MAT130YV200" / "MAT130AV200" (自动归一化)
        """
        self.raw_name = device_name
        self.device_name = _DEVICE_NAME_MAP.get(device_name, device_name)
        self._sdk = get_sdk(bin_dir)
        self._handle = self._sdk.testlib.get_device(self.device_name.encode("utf-8"))
        if not self._handle:
            raise RuntimeError(
                f"get_device({self.device_name}) 失败 (last_error={self._sdk.last_error()!r})"
            )
        logger.info("设备句柄获取成功: %s -> %s", device_name, self.device_name)

    # ------------------------------------------------------------ 通道

    def get_focus_channel(self) -> str:
        """读取 Dothinkey 当前聚焦通道名 (未配置时返回空串)"""
        buf = create_string_buffer(1024)
        self._sdk.testlib.get_device_focus_channel(buf)
        raw = buf.raw.split(b"\x00", 1)[0]
        try:
            return raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            return raw.decode("gbk", errors="ignore").strip()

    def set_focus_channel(self, channel: str) -> bool:
        """设置 Dothinkey 聚焦通道 (空串视为未配置, 直接跳过)"""
        if not channel:
            logger.info("set_device_focus_channel: 通道名为空, 跳过 (单通道采集卡无需设置)")
            return True
        ok = bool(self._sdk.testlib.set_device_focus_channel(channel.encode("utf-8")))
        logger.info("set_device_focus_channel(%s) -> %s", channel, ok)
        return ok

    # ------------------------------------------------------------ 配置与连接

    def set_configure(self, ini_path: str) -> None:
        """向设备下发 ini 初始化配置 (Dothinkey + 解串器 + sensor 上电时序)

        :param ini_path: configs/init_file 下的初始化文件路径
        """
        logger.info("device_setConfigure: %s", ini_path)
        self._sdk.testlib.device_setConfigure(self._handle, str(ini_path).encode("utf-8"))

    def open(self) -> bool:
        """建立设备连接"""
        self._sdk.clear_error()
        ok = bool(self._sdk.testlib.device_open(self._handle))
        if ok:
            logger.info("device_open -> True")
        else:
            logger.error("device_open 失败, dll_err=%r", self._sdk.last_error())
        return ok

    def close(self) -> None:
        """断开设备连接 (句柄保留, 可重新 open)"""
        if self._handle:
            self._sdk.testlib.device_close(self._handle)
            logger.info("device_close")

    def release(self) -> None:
        """释放设备句柄 (之后不可再用)"""
        if self._handle:
            self._sdk.testlib.release_device(self._handle)
            self._handle = None
            logger.info("release_device")

    # ------------------------------------------------------------ 视频流

    def open_video(self) -> bool:
        """打开视频流"""
        self._sdk.clear_error()
        ok = bool(self._sdk.testlib.device_open_video(self._handle))
        if ok:
            logger.info("device_open_video -> True")
        else:
            logger.error("device_open_video 失败, dll_err=%r", self._sdk.last_error())
        return ok

    def close_video(self) -> bool:
        """关闭视频流 (增补接口)"""
        fn = getattr(self._sdk.testlib, "device_close_video", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_close_video")
        ok = bool(fn(self._handle))
        logger.info("device_close_video -> %s", ok)
        return ok

    def stop_streaming(self) -> bool:
        """停止当前视频传输 (增补接口)"""
        fn = getattr(self._sdk.testlib, "device_stop_streaming", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_stop_streaming")
        ok = bool(fn(self._handle))
        logger.info("device_stop_streaming -> %s", ok)
        return ok

    def grab_frame(self) -> bool:
        """抓取一帧 (需已 open_video)"""
        self._sdk.clear_error()
        ok = bool(self._sdk.testlib.device_grab_one_frame(self._handle))
        if ok:
            logger.info("device_grab_one_frame -> True")
        else:
            logger.error("device_grab_one_frame 失败, dll_err=%r", self._sdk.last_error())
        return ok

    def grab_frame_save(self, save_dir: str, file_name: str) -> bool:
        """抓取一帧并保存到文件

        :param save_dir: 输出目录
        :param file_name: 文件名 (DLL 会在其中附上分辨率等信息)
        :return: 是否成功
        """
        self._sdk.clear_error()
        ok = bool(self._sdk.testlib.device_grab_one_frame_save(
            self._handle, save_dir.encode("utf-8"), file_name.encode("utf-8")
        ))
        if ok:
            logger.info("device_grab_one_frame_save -> %s/%s", save_dir, file_name)
        else:
            logger.error("device_grab_one_frame_save 失败, dll_err=%r", self._sdk.last_error())
        return ok

    def grab_frame_save_ex(self, save_dir: str, file_name: str):
        """抓取一帧并保存, 同时返回帧 ID (增补接口)

        :return: (是否成功, frame_id)
        """
        fn = getattr(self._sdk.testlib, "device_grab_one_frame_save_ex", None)
        if fn is None:
            raise NotImplementedError("当前 testlib.dll 未导出 device_grab_one_frame_save_ex")
        self._sdk.clear_error()
        frame_id = ctypes.c_uint64()
        ok = bool(fn(self._handle, save_dir.encode("utf-8"),
                     file_name.encode("utf-8"), byref(frame_id)))
        if ok:
            logger.info("device_grab_one_frame_save_ex -> %s/%s frame_id=%d",
                        save_dir, file_name, frame_id.value)
        else:
            logger.error("device_grab_one_frame_save_ex 失败, dll_err=%r", self._sdk.last_error())
        return ok, frame_id.value

    def get_fps(self) -> float:
        """读取当前 FPS"""
        fps = c_float()
        ok = bool(self._sdk.testlib.device_get_fps(self._handle, byref(fps)))
        if not ok:
            raise RuntimeError("device_get_fps 失败")
        logger.info("device_get_fps -> %.2f", fps.value)
        return fps.value

    def get_dn(self) -> float:
        """读取当前 DN (图像亮度均值)"""
        dn = c_float()
        ok = bool(self._sdk.testlib.device_get_current_DN(self._handle, byref(dn)))
        if not ok:
            raise RuntimeError("device_get_current_DN 失败")
        logger.info("device_get_current_DN -> %.2f", dn.value)
        return dn.value

    # ------------------------------------------------------------ 组合流程

    def bring_up(self, ini_path: str, configure_wait: float = 10.0,
                 open_video: bool = True, retries: int = 2,
                 video_attempts: int = 3, grab_attempts: int = 3) -> bool:
        """一键上电出图: set_configure -> open -> open_video -> grab_frame

        复刻旧工程 TestFunction._test_device_initialization 的主链路 (去除断言):
        open_video / grab_frame 各自带多次重试, 整轮失败时先 close 再重开。

        :return: 全部步骤是否成功
        """
        self.set_configure(ini_path)
        time.sleep(configure_wait)

        for attempt in range(1, retries + 1):
            if self.open():
                if not open_video:
                    return True
                opened = False
                for _ in range(video_attempts):
                    if self.open_video():
                        time.sleep(2)
                        opened = True
                        break
                    time.sleep(1)
                if opened:
                    for g in range(grab_attempts):
                        if self.grab_frame():
                            return True
                        logger.warning("抓帧失败 (%d/%d)", g + 1, grab_attempts)
                        time.sleep(1)
                else:
                    logger.warning("第 %d 次: 打开视频流失败", attempt)
            else:
                logger.warning("第 %d 次: device_open 失败", attempt)
            if attempt < retries:
                self.close()
                time.sleep(3)
        return False

    # ------------------------------------------------------------ 上下文

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.close()
        finally:
            self.release()
