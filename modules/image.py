# -*- coding: utf-8 -*-
"""图像抓取与对比模块

移植旧工程 libs/test_function.py 的图像处理链路
(_compare_img_brightness / _get_compared_data / _analyze_compared_results /
_load_images / _yuv_mean / _raw16_mean / _display_img), 打包为独立模块:

- 抓帧: 配合 modules.device.PixelDevice 存帧到目录
- 解析: 从 DLL 生成的文件名中解析 分辨率x位宽 (如 xxx_1280x880x16.uyvy)
- 亮度: uyvy/vyuy/yuyv/yvyu 的 Y 分量均值; raw16(bin) 的像素均值
- 对比: 修改 I2C 寄存器前后各抓一帧, 按亮度变化方向判定寄存器是否生效

依赖: numpy (必需), opencv-python (仅 display 用到, 可不装)。

用法:
    from modules.image import ImageTools
    tools = ImageTools(output_dir="logs/img")
    # 单帧亮度
    ok, path, mean = tools.capture_mean(dev, fmt="uyvy")
    # 改寄存器前后亮度对比 (验证寄存器是否影响图像)
    result = tools.compare_register(dev, i2c, reg=0x0091c, value=0x60, fmt="uyvy")
"""
import logging
import os
import re
import time
from pathlib import Path

import numpy as np

from .device import PixelDevice
from .i2c import I2CController

logger = logging.getLogger("new_auto.image")


class ImageTools:
    """抓帧 + 亮度分析 + 前后对比"""

    def __init__(self, output_dir="logs/img"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ 抓帧

    def capture(self, dev: PixelDevice, name: str = "frame"):
        """抓一帧存盘

        :return: (是否成功, 文件路径)
        """
        stamp = time.strftime("%H%M%S")
        ok = dev.grab_frame_save(str(self.output_dir), f"{name}_{stamp}")
        if not ok:
            return False, None
        time.sleep(0.5)
        # DLL 生成的实际文件名: <name>_<stamp>_<W>x<H>x<bit>.<ext>
        found = sorted(self.output_dir.glob(f"{name}_{stamp}_*"))
        if not found:
            logger.error("抓帧后未找到输出文件: %s_%s_*", name, stamp)
            return False, None
        return True, found[-1]

    # ------------------------------------------------------------ 解析与均值

    @staticmethod
    def parse_frame_file(path):
        """从帧文件名解析 (width, height, bit_depth, data_format)"""
        m = re.search(r"(\d+)x(\d+)x(\d+)", Path(path).name)
        if not m:
            raise ValueError(f"无法从文件名解析分辨率: {path}")
        width, height, bit = map(int, m.groups())
        fmt = Path(path).suffix.lstrip(".").lower()
        return width, height, bit, fmt

    @staticmethod
    def yuv_mean(data: bytes, width: int, height: int, fmt: str = "uyvy") -> float:
        """YUV422 帧的 Y 分量均值 (uyvy/vyuy 取奇数字节, yuyv/yvyu 取偶数字节)"""
        arr = np.frombuffer(data, dtype=np.uint8)
        frame = arr.reshape((height, width * 2))
        y = frame[:, 1::2] if fmt in ("uyvy", "vyuy") else frame[:, 0::2]
        return float(np.mean(y))

    @staticmethod
    def raw16_mean(data: bytes, width: int, height: int) -> float:
        """raw16 帧的像素均值"""
        arr = np.frombuffer(data, dtype=np.uint16)
        if arr.size != width * height:
            raise ValueError(f"raw16 尺寸不匹配: {arr.size} != {width}x{height}")
        return float(np.mean(arr.reshape(height, width)))

    def file_mean(self, path) -> float:
        """计算一个帧文件的亮度均值 (自动识别 yuv/raw16)"""
        width, height, bit, fmt = self.parse_frame_file(path)
        data = Path(path).read_bytes()
        if fmt == "bin" or bit == 16 and fmt in ("bin", "raw", "raw16"):
            return self.raw16_mean(data, width, height)
        return self.yuv_mean(data, width, height, fmt)

    def capture_mean(self, dev: PixelDevice, name: str = "frame"):
        """抓一帧并计算亮度均值

        :return: (是否成功, 文件路径, 亮度均值)
        """
        ok, path = self.capture(dev, name)
        if not ok:
            return False, None, None
        return True, path, self.file_mean(path)

    # ------------------------------------------------------------ 前后对比

    def compare_register(self, dev: PixelDevice, i2c: I2CController, reg: int,
                         value: int, fmt: str = "uyvy",
                         slave: int = None, addr_len: int = 16, bits: int = 16,
                         settle_seconds: float = 2.0):
        """修改寄存器前后各抓一帧, 对比亮度变化 (旧工程 _compare_img_brightness 核心)

        :param reg: 要修改的寄存器地址
        :param value: 新值
        :param fmt: 帧格式 (uyvy/yuyv/.../bin)
        :return: dict {
            pass, original_value, new_value, mean_default, mean_modified,
            delta, path_default, path_modified
        }
        """
        ok0, original = i2c.read(reg, slave=slave, addr_len=addr_len, bits=bits)
        if not ok0:
            return {"pass": False, "error": f"读寄存器 0x{reg:04x} 失败"}

        ok1, path1, mean1 = self.capture_mean(dev, f"reg{reg:04x}_default")
        if not ok1:
            return {"pass": False, "error": "抓默认帧失败"}

        if not i2c.write(reg, value, slave=slave, addr_len=addr_len, bits=bits):
            return {"pass": False, "error": f"写寄存器 0x{reg:04x} 失败"}
        time.sleep(settle_seconds)

        ok2, readback = i2c.read(reg, slave=slave, addr_len=addr_len, bits=bits)
        ok3, path2, mean2 = self.capture_mean(dev, f"reg{reg:04x}_modify")
        # 恢复原值
        i2c.write(reg, original, slave=slave, addr_len=addr_len, bits=bits)
        time.sleep(settle_seconds)
        if not (ok2 and ok3):
            return {"pass": False, "error": "修改后抓帧/回读失败"}

        delta = abs(mean2 - mean1)
        # 亮度有变化即说明寄存器写入生效 (容差 0.5)
        passed = delta > 0.5
        result = {
            "pass": passed,
            "original_value": original,
            "new_value": readback,
            "mean_default": round(mean1, 2),
            "mean_modified": round(mean2, 2),
            "delta": round(delta, 2),
            "path_default": str(path1),
            "path_modified": str(path2),
        }
        logger.info("亮度对比 reg=0x%04x: %.2f -> %.2f (Δ%.2f) %s",
                    reg, mean1, mean2, delta, "生效" if passed else "未生效")
        return result

    def compare_frames(self, path_a, path_b):
        """对比两个已存在帧文件的亮度

        :return: dict {pass, mean_a, mean_b, delta}
        """
        mean_a = self.file_mean(path_a)
        mean_b = self.file_mean(path_b)
        delta = abs(mean_b - mean_a)
        return {"pass": delta > 0.5, "mean_a": round(mean_a, 2),
                "mean_b": round(mean_b, 2), "delta": round(delta, 2)}

    # ------------------------------------------------------------ 显示 (可选)

    def display(self, path, max_width=960):
        """用 OpenCV 显示帧文件 (需要 opencv-python, 缺失时只打日志)"""
        try:
            import cv2
        except ImportError:
            logger.warning("未安装 opencv-python, 跳过显示: %s", path)
            return False
        width, height, bit, fmt = self.parse_frame_file(path)
        data = Path(path).read_bytes()
        if fmt == "bin":
            raw = np.frombuffer(data, dtype=np.uint16).reshape((height, width))
            img = cv2.normalize(raw, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        else:
            frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 2))
            code = {"yuyv": cv2.COLOR_YUV2RGB_YUYV, "yvyu": cv2.COLOR_YUV2RGB_YVYU,
                    "uyvy": cv2.COLOR_YUV2RGB_UYVY}.get(fmt)
            if code is None:  # vyuy: 字节交换后按 uyvy 解
                frame = frame[:, :, ::-1]
                code = cv2.COLOR_YUV2RGB_UYVY
            img = cv2.cvtColor(frame, code)
        scale = min(1.0, max_width / width)
        img = cv2.resize(img, (int(width * scale), int(height * scale)))
        cv2.imshow(Path(path).name, img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return True
