# -*- coding: utf-8 -*-
"""硬件会话: 一次画布执行过程中共享的底层模块实例

节点执行时通过 ctx (Session) 拿到底层模块控制器, 并保证:
- 继电器 / 设备 / I2C / 图像工具 只创建一次, 全流程复用
- 上电、ini 配置、出图等状态幂等 (重复节点调用不重复执行)
"""
import json
import logging
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent      # new_auto/app
ROOT = APP_DIR.parent                                 # new_auto/
sys.path.insert(0, str(ROOT))

from modules.relay import RelayController      # noqa: E402
from modules.device import PixelDevice         # noqa: E402
from modules.i2c import I2CController          # noqa: E402
from modules.image import ImageTools           # noqa: E402
from modules.otp import OtpController          # noqa: E402
from modules.firmware import FirmwareDownloader  # noqa: E402

logger = logging.getLogger("new_auto.engine")


class Session:
    """一次画布运行的硬件会话 (非线程安全, 一次 run 一个)"""

    def __init__(self, config_path=None):
        cfg_path = Path(config_path) if config_path else ROOT / "config.json"
        with open(cfg_path, "r", encoding="utf-8") as f:
            self.cfg = json.load(f)
        self._relay = None
        self._relay_port = None
        self._device = None
        self._i2c = None
        self._image = None
        self._otp = None
        self._fw_dl = None
        # 状态缓存 (幂等)
        self._powered_channel = None
        self._configured_ini = None
        self._device_open = False
        self._video_on = False

    # ------------------------------------------------------------ 控制器

    def relay(self, port: str = None) -> RelayController:
        """继电器控制器; port 为空用 config 默认, 否则用指定串口 (按串口缓存)"""
        want = port or self.cfg["relay"]["port"]
        if self._relay is None or self._relay_port != want:
            # 先释放已缓存的串口连接 (switcher_close 会释放 COM 口)
            if self._relay is not None:
                try:
                    self._relay.close()
                except Exception:
                    pass
            relay_cfg = self.cfg["relay"]
            self._relay = RelayController(
                want,
                transport=relay_cfg.get("transport", "sdk"),
                baudrate=relay_cfg.get("baudrate", 9600),
                timeout=relay_cfg.get("timeout_seconds", 0.8),
            )
            if not self._relay.open():
                raise RuntimeError(f"继电器 {want} 连接失败")
            self._relay_port = want
        return self._relay

    def device(self) -> PixelDevice:
        if self._device is None:
            self._device = PixelDevice(self.cfg["device"]["chip"])
        return self._device

    def i2c(self) -> I2CController:
        if self._i2c is None:
            # I2C 链路要求 Dothinkey 设备已下发配置并 open, 未配置时自动补齐
            self.ensure_configured()
            self._i2c = I2CController(self.device(),
                                      default_slave=int(self.cfg["i2c"]["default_slave"], 16))
        return self._i2c

    def image(self) -> ImageTools:
        if self._image is None:
            out = ROOT / self.cfg.get("app", {}).get("img_output", "logs/img")
            self._image = ImageTools(str(out))
        return self._image

    def otp(self) -> OtpController:
        if self._otp is None:
            self._otp = OtpController(self.device())
        return self._otp

    def fw_downloader(self) -> FirmwareDownloader:
        if self._fw_dl is None:
            self._fw_dl = FirmwareDownloader()
        return self._fw_dl

    # ------------------------------------------------------------ 幂等流程

    def default_ini(self) -> str:
        return str(ROOT / "configs" / "init_file" / self.cfg["device"]["init_file"])

    def ensure_powered(self, channel: int = None):
        """确保继电器通道导通 (模组上电), 带重试"""
        ch = self.cfg["relay"]["channel"] if channel is None else channel
        if self._powered_channel == ch:
            return
        relay = self.relay()
        for attempt in range(3):
            if relay.open_channel(ch):
                break
            logger.warning("open_channel(%d) 第 %d 次失败, 重试", ch, attempt + 1)
            time.sleep(3)
        else:
            raise RuntimeError(f"继电器通道 {ch} 导通失败")
        time.sleep(5)
        self._powered_channel = ch
        # 上电后之前的配置/出图状态失效
        self._configured_ini = None
        self._device_open = False
        self._video_on = False

    def ensure_configured(self, ini_path: str = None):
        """确保已下发 ini 且 device_open (open 失败自动重试)"""
        ini = ini_path or self.default_ini()
        if self._configured_ini != ini or not self._device_open:
            dev = self.device()
            if not self._device_open:
                dev.set_configure(ini)
                time.sleep(10)
                for attempt in range(3):
                    if dev.open():
                        break
                    logger.warning("device_open 第 %d 次失败, 重试", attempt + 1)
                    dev.close()
                    time.sleep(3)
                else:
                    raise RuntimeError(f"device_open 失败 ({ini})")
                self._device_open = True
                self._configured_ini = ini
        return self.device()

    def ensure_video(self):
        """确保视频流已打开 (需先 ensure_configured)"""
        if not self._video_on:
            dev = self.ensure_configured()
            if not dev.open_video():
                raise RuntimeError("device_open_video 失败")
            time.sleep(2)
            self._video_on = True
        return self.device()

    def power_off(self, channel: int = None):
        """继电器通道断电并复位内部状态"""
        ch = self.cfg["relay"]["channel"] if channel is None else channel
        self.relay().close_channel(ch)
        self._powered_channel = None
        self._configured_ini = None
        self._device_open = False
        self._video_on = False

    def close(self):
        """收尾: 关闭视频/连接并释放设备句柄 (防同进程多次运行句柄泄漏)"""
        try:
            if self._relay is not None:
                # switcher_close 会释放 COM 口, 便于外部工具/子进程探测
                self._relay.close()
        except Exception:
            pass
        try:
            if self._device is not None:
                if self._video_on:
                    self._device.close_video()
                if self._device_open:
                    self._device.close()
                self._device.release()
        except Exception:
            logger.exception("会话收尾异常(忽略)")
        finally:
            self._device = None
            self._i2c = None
            self._otp = None
            self._relay = None
            self._relay_port = None
            self._device_open = False
            self._video_on = False
            self._configured_ini = None