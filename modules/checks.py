# -*- coding: utf-8 -*-
"""固件状态检查模块

移植旧工程 libs/test_function.py 中基于 I2C 的固件状态/算法检查方法,
打包为对 I2CController 的组合操作 (核心是 A2D2/A2D4/A4D4 寄存器读写):

- fw_version            读固件版本 (0x00d8, A2D4)
- start_status          ROM/SRAM 启动状态 (0x00c0/0x00c4, A2D4)
- boot_area             启动区判断 (0x00c4 bit0)
- frame_counter_ok      帧计数器是否递增 (0x00cc, A2D4)
- alg_ctrl              AWB/AE 算法开关 (0x0918/0x091c, A2D2)
- fs_check              功能安全检查 (0x093c/0x0940 位定义表, A2D2)
- switch_clock          时钟切换 (0x80 器件 0x04, A1D1, 升级前用)
- read_regs/write_reg   批量读写助手
- fw_protocol_crc       固件 16 字节协议命令的 CRC8 (多项式 0x07)

用法:
    from modules.checks import fw_version, boot_area, frame_counter_ok
    ok, ver = fw_version(i2c)          # '4.1.7'
    ok, area = boot_area(i2c)          # 'A' / 'B'
    ok, counting = frame_counter_ok(i2c)
"""
import logging
import time

logger = logging.getLogger("new_auto.checks")

# 旧工程约定的固件 I2C 地址与关键寄存器
FW_I2C = 0x40
REG_FW_VERSION = 0x00D8
REG_ROM_INFO = 0x00C0
REG_SRAM_INFO = 0x00C4
REG_FRAME_CNT = 0x00CC
REG_AWB_ENABLE = 0x0918
REG_AE_ENABLE = 0x091C
REG_FS_REPORT_1 = 0x093C
REG_FS_REPORT_2 = 0x0940

# 功能安全位定义 (旧工程 _fs_check)
_FS_BITS_1 = {
    0: "ilm/dlm mbist check fail", 1: "pll check fail", 2: "power domain check fail",
    3: "t_sensor check fail", 4: "p_sensor check fail", 5: "pre isp mbist check fail",
    6: "fe isp mbist check fail", 7: "be isp mbist check fail", 8: "watch dog check fail",
    9: "isp bist check fail", 10: "macu mbist check fail", 11: "isp timing check fail",
    12: "dead pix check fail", 13: "i2c buffer comm crc check fail",
    14: "mipi mem parity check fail", 15: "ana dcs check fail",
}
_FS_BITS_2 = {
    0: "line buffer check fail", 1: "ana reg check fail", 2: "apc safety check fail",
    3: "config data crc check fail", 4: "important registers read check fail",
}


def fw_version(i2c) -> tuple:
    """读固件版本 -> (ok, '4.1.7')"""
    ok, v = i2c.read(REG_FW_VERSION, addr_len=16, bits=32)
    if not ok:
        return False, None
    ver = f"{(v >> 16) & 0xFF}.{(v >> 8) & 0xFF}.{v & 0xFF}"
    logger.info("固件版本: %s", ver)
    return True, ver


def start_status(i2c) -> tuple:
    """ROM/SRAM 启动状态 -> (ok, {'rom': int, 'sram': int, 'area': 'A'/'B', 'desc': str})"""
    ok0, rom = i2c.read(REG_ROM_INFO, addr_len=16, bits=32)
    ok1, sram = i2c.read(REG_SRAM_INFO, addr_len=16, bits=32)
    if not (ok0 and ok1):
        return False, None
    area = "A" if (sram & 1) == 0 else "B"
    desc = "A/B区固件均正常" if rom == 0x04FB else f"ROM信息异常: 0x{rom:04x} (期望 0x04fb)"
    logger.info("启动状态: rom=0x%04x sram=0x%04x 从%s区启动 (%s)", rom, sram, area, desc)
    return True, {"rom": rom, "sram": sram, "area": area, "desc": desc}


def boot_area(i2c) -> tuple:
    """启动区判断 -> (ok, 'A'/'B')"""
    ok, sram = i2c.read(REG_SRAM_INFO, addr_len=16, bits=32)
    if not ok:
        return False, None
    area = "A" if (sram & 1) == 0 else "B"
    logger.info("固件从%s区启动", area)
    return True, area


def frame_counter_ok(i2c, interval: float = 2.0) -> tuple:
    """帧计数器是否在递增 (旧工程 _fw_cnt) -> (ok, counting)"""
    ok0, c0 = i2c.read(REG_FRAME_CNT, addr_len=16, bits=32)
    time.sleep(interval)
    ok1, c1 = i2c.read(REG_FRAME_CNT, addr_len=16, bits=32)
    if not (ok0 and ok1):
        return False, None
    counting = c0 != c1
    logger.info("帧计数器 0x%08x -> 0x%08x: %s", c0, c1, "计数中" if counting else "停止")
    return True, counting


def alg_ctrl(i2c, awb: bool = None, ae: bool = None) -> bool:
    """AWB/AE 算法开关 (旧工程 _alg_ctrl); None 表示保持不变"""
    ok = True
    if awb is not None:
        ok &= i2c.write(REG_AWB_ENABLE, 0x0001 if awb else 0x0000, addr_len=16, bits=16)
    if ae is not None:
        ok &= i2c.write(REG_AE_ENABLE, 0x0001 if ae else 0x0000, addr_len=16, bits=16)
    logger.info("算法开关: awb=%s ae=%s -> %s", awb, ae, ok)
    return bool(ok)


def fs_check(i2c) -> tuple:
    """功能安全检查 (旧工程 _fs_check) -> (ok, 错误列表; 空列表=通过)"""
    ok1, v1 = i2c.read(REG_FS_REPORT_1, addr_len=16, bits=16)
    ok2, v2 = i2c.read(REG_FS_REPORT_2, addr_len=16, bits=16)
    if not (ok1 and ok2):
        return False, None
    errors = []
    for i in range(16):
        if v1 & (1 << i):
            errors.append(f"0x{REG_FS_REPORT_1:04x} bit{i}: {_FS_BITS_1.get(i, '未定义错误')}")
        if v2 & (1 << i):
            errors.append(f"0x{REG_FS_REPORT_2:04x} bit{i}: {_FS_BITS_2.get(i, '未定义错误')}")
    logger.info("功能安全检查: %s", errors if errors else "通过, 无错误上报")
    return True, errors


def switch_clock(i2c, on: bool = True) -> bool:
    """时钟切换 (旧工程 _switch_clock): 0x80 器件 0x04 寄存器, 0x43=开 0x87=关"""
    ok = i2c.write(0x04, 0x43 if on else 0x87, slave=0x80, addr_len=8, bits=8)
    logger.info("时钟切换(%s) -> %s", "开" if on else "关", ok)
    return ok


def read_regs(i2c, regs, addr_len: int = 16, bits: int = 16) -> tuple:
    """批量读寄存器 -> (是否全部成功, {reg: value})"""
    values, all_ok = {}, True
    for reg in regs:
        ok, v = i2c.read(reg, addr_len=addr_len, bits=bits)
        values[reg] = v if ok else None
        all_ok &= ok
    return all_ok, values


def fw_protocol_crc(data: bytes) -> int:
    """固件协议命令 CRC8 (多项式 0x07, 初值 0x00; 旧工程 _fw_protocol_crc)"""
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) if (crc & 0x80) else (crc << 1)
            crc &= 0xFF
    return crc
