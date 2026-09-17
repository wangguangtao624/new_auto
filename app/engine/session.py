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


def _to_hex(v, default=0):
    """解析十六进制字符串 ('0x40' / '40' / 64 均可)"""
    if v is None or v == "":
        return default
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") or any(
            c in s.lower() for c in "abcdef") else int(s)
    except ValueError:
        return default


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
        # 实时事件通道 (由 executor 注入)
        self._emit_fn = None
        self._node_id = None
        self._seq = 0
        # 会话级继承: ini / slave
        self.current_ini = None
        self.current_slave = None
        # 当前用例 (画布名): 决定日志/图片落在哪个 case 空间
        self.case_name = None
        self._image_case = None
        self._touched = time.time()

    # ------------------------------------------------------------ 事件 / 继承

    def touch(self):
        """标记会话活跃 (用于闲置超时释放)"""
        self._touched = time.time()

    def idle_seconds(self):
        return time.time() - self._touched

    def set_emitter(self, fn, node_id=None):
        """设置事件出口并重置节点上下文。fn(dict) 由 executor 提供"""
        self._emit_fn = fn
        self._node_id = node_id
        self._seq = 0
        self.touch()

    def emit(self, ev: dict):
        """推一条事件到前端。自动补 时间戳 / 节点ID / 序号"""
        if not self._emit_fn:
            return
        ev.setdefault("ts", round(time.time() * 1000))
        if self._node_id:
            ev.setdefault("node", self._node_id)
        fn = self._emit_fn
        try:
            fn(ev)
        except Exception:
            logger.exception("事件回调异常(忽略)")

    def emit_log(self, kind, fields=None, level="info", result=None, text=None):
        """结构化日志: fields 是 {字段名: 值} 字典, 前端逐字段展开渲染"""
        self.emit({"event": "log", "kind": kind, "level": level,
                   "result": result, "seq": self._next_seq(),
                   "text": text, "fields": fields or {}})

    def emit_progress(self, phase, pct, detail=""):
        self.emit({"event": "progress", "phase": phase,
                   "pct": max(0, min(100, int(pct))), "detail": detail})

    def _next_seq(self):
        self._seq += 1
        return self._seq

    def project(self) -> dict:
        return self.cfg.get("project", {})

    def presets_path(self) -> Path:
        rel = self.project().get("reg_presets", "configs/reg_presets.json")
        return ROOT / rel

    def default_slave(self) -> int:
        return _to_hex(self.project().get("default_slave") or self.cfg["i2c"]["default_slave"], 0x40)

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
            self._relay = RelayController(want)
            self._relay.open()
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
            self._i2c = I2CController(self.device(), default_slave=self.default_slave())
        if self.current_slave is None:
            self.current_slave = self.default_slave()
        return self._i2c

    def set_case(self, name):
        """绑定当前用例 (画布名): 抓帧图片落到 logs/cases/<case>/img。

        一个画布 = 一个 case, 所以「清空本 case」只删这个目录下的产物。
        幂等: 传同一个名字不会重建 ImageTools。
        """
        name = (str(name).strip() if name else "") or None
        if name is None or name == self.case_name:
            return self.case_name
        self.case_name = name
        self._image = None               # 下次 image() 按新 case 目录重建
        self._image_case = None
        try:
            from modules import case_store
            case_store.ensure_case(name)
        except Exception:
            logger.exception("建立 case 目录失败 (忽略, 回落到默认图片目录)")
        return self.case_name

    def image(self) -> ImageTools:
        # case 变了要换目录, 所以这里不能只看 _image 是否为 None
        if self._image is None or self._image_case != self.case_name:
            out = None
            if self.case_name:
                try:
                    from modules import case_store
                    out = case_store.case_img_dir(self.case_name)
                except Exception:
                    logger.exception("解析 case 图片目录失败 (回落到默认目录)")
            if out is None:
                out = ROOT / self.cfg.get("app", {}).get("img_output", "logs/img")
            self._image = ImageTools(str(out))
            self._image_case = self.case_name
            logger.debug("抓帧图片目录: %s", out)
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
        """默认 ini: 优先取 project.default_ini, 回落到 device.init_file"""
        name = self.project().get("default_ini") or self.cfg["device"]["init_file"]
        return str(ROOT / "configs" / "init_file" / Path(name).name)

    def resolve_ini(self, ini: str = None) -> str:
        """把节点上的 ini 参数解析成绝对路径。

        :param ini: None/"__inherit__"/"" -> 继承会话 ini, 再退回默认 ini;
                    文件名或绝对路径 -> 用该路径
        """
        self.touch()
        if not ini or str(ini) in ("__inherit__", "(继承)"):
            return self.current_ini or self.default_ini()
        p = Path(str(ini))
        if p.is_absolute() and p.exists():
            return str(p)
        cand = ROOT / "configs" / "init_file" / Path(ini).name
        return str(cand if cand.exists() else p)

    def ensure_powered(self, channel: int = None):
        """确保继电器通道导通 (模组上电), 带重试"""
        self.touch()
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
        self.touch()
        ini = ini_path or self.current_ini or self.default_ini()
        self.current_ini = ini
        if self._configured_ini != ini or not self._device_open:
            dev = self.device()
            if not self._device_open:
                self.emit_log("device.configure",
                              {"ini": Path(ini).name, "等待": f"{self.cfg['device'].get('configure_wait_seconds', 10)}s"},
                              text="下发 ini 并打开设备")
                dev.set_configure(ini)
                time.sleep(self.cfg["device"].get("configure_wait_seconds", 10))
                for attempt in range(3):
                    if dev.open():
                        break
                    logger.warning("device_open 第 %d 次失败, 重试", attempt + 1)
                    self.emit_log("device.open", {"尝试": attempt + 1},
                                  level="warn", text="device_open 失败, 重试中")
                    dev.close()
                    time.sleep(3)
                else:
                    raise RuntimeError(f"device_open 失败 ({ini})")
                self._device_open = True
                self._configured_ini = ini
                self.emit_log("device.open", {"ini": Path(ini).name},
                              result="pass", text="会话已建立")
        return self.device()

    def video_off(self):
        """关闭视频流 (设备句柄保留, 可再次 ensure_video)"""
        self.touch()
        if self._video_on and self._device is not None:
            try:
                self._device.close_video()
            except Exception:
                logger.exception("关闭视频流异常(忽略)")
            self._video_on = False

    def ensure_video(self):
        """确保视频流已打开 (需先 ensure_configured); 句柄失效时自动重建一次"""
        if not self._video_on:
            dev = self.ensure_configured()
            if not dev.open_video():
                # 旧句柄可能因掉电/烧录而失效 (device_open 仍返回 True, 只有
                # device_open_video 会失败且 dll_err 为空) —— 重建句柄再试一次
                logger.warning("device_open_video 失败, 重建设备句柄后重试")
                self.emit_log("device.open", {}, level="warn",
                              text="视频流打开失败, 重建设备句柄重试")
                self.release_device()
                dev = self.ensure_configured()
                if not dev.open_video():
                    raise RuntimeError("device_open_video 失败")
            time.sleep(2)
            self._video_on = True
        return self.device()

    def release_device(self):
        """释放并丢弃当前设备句柄 (下次 device() 会重新 get_device)

        模组掉电重启 / 固件烧录后, DLL 侧的旧句柄已失效 —— 但 ``device_open``
        仍会返回 True, 只有 ``device_open_video`` / I2C 会失败 (dll_err 为空,
        极难排查)。所以断电前必须释放。
        """
        dev, self._device = self._device, None
        self._i2c = None
        self._otp = None
        was_open, was_video = self._device_open, self._video_on
        self._device_open = False
        self._video_on = False
        self._configured_ini = None
        if dev is None:
            return
        if was_video:
            try:
                dev.close_video()
            except Exception:
                logger.exception("掉电前关闭视频流异常(忽略)")
        if was_open:
            try:
                dev.close()
            except Exception:
                logger.exception("掉电前断开设备异常(忽略)")
        try:
            dev.release()
        except Exception:
            logger.exception("释放设备句柄异常(忽略)")

    def power_off(self, channel: int = None):
        """继电器通道断电并复位内部状态"""
        ch = self.cfg["relay"]["channel"] if channel is None else channel
        # 断电会让 DLL 侧设备句柄失效 —— 必须趁模组还带电时先释放句柄
        self.release_device()
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