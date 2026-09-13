# -*- coding: utf-8 -*-
"""节点注册表: 拖拽画布可用的全部节点类型 (UI schema + 执行函数)

每个节点类型:
    type        唯一标识, 形如 "i2c.read"
    group       画布左侧面板分组 (电源/设备/I2C/图像/固件/检查/流程)
    title       节点显示名
    desc        说明
    color       节点配色
    params      参数定义 [{name,label,type,default,options?,hex?,optional?}]
                type: int | float | str | bool | choice
                hex: True 表示按 16 进制解析 (支持 0x 前缀)
    inputs      可接收上游连线的入参名 -> 显示名
    outputs     输出端口名 -> 显示名 (连线到下游参数)
    run(ctx, params, inputs) -> outputs dict   (抛异常 = 节点失败)

I2C 数据位宽模式 (用户术语): A<m>D<n> = <m> 字节地址 / <n> 字节数据
    A1D1=(8,8) A1D2=(8,16) A1D4=(8,32) A2D1=(16,8) A2D2=(16,16)
    A2D4=(16,32) A4D1=(32,8) A4D2=(32,16) A4D4=(32,32)
"""
import json
import time
from pathlib import Path

from .session import ROOT, Session

# ---------------------------------------------------------------- 工具


def _hex(v, default=0):
    """解析 16 进制参数 ('0x1a' / '1a' / 26 均可)"""
    if v is None or v == "":
        return default
    if isinstance(v, int):
        return v
    return int(str(v), 16) if int(str(v), 0) == 0 or str(v).lower().startswith("0x") or any(
        c in str(v).lower() for c in "abcdef") else int(v)


def _mode(value):
    """A2D4 -> (addr_len_bits, data_bits)"""
    table = {
        "A1D1": (8, 8), "A1D2": (8, 16), "A1D4": (8, 32),
        "A2D1": (16, 8), "A2D2": (16, 16), "A2D4": (16, 32),
        "A4D1": (32, 8), "A4D2": (32, 16), "A4D4": (32, 32),
    }
    return table[value]


def _p(name):
    """从 inputs/params 双通道取参: 连线值优先, 否则用节点参数"""
    def getter(inputs, params):
        if name in inputs and inputs[name] is not None:
            return inputs[name]
        return params.get(name)
    return getter


def _ini_options():
    """枚举 configs/init_file 下的 ini 供下拉选择"""
    d = ROOT / "configs" / "init_file"
    return sorted(p.name for p in d.glob("*.ini")) or ["(无)"]


def _fw_options():
    d = ROOT / "fw"
    return sorted(p.name for p in d.glob("*.bin")) or ["(无)"]


# ---------------------------------------------------------------- 节点定义

NODES = {}
DEBUG = {}   # "type:action" -> {type, name, label, run(ctx, params)}


def node(type, group, title, desc="", color="#4a89dc", params=None,
         inputs=None, outputs=None, debug=None):
    def deco(fn):
        NODES[type] = {
            "type": type, "group": group, "title": title, "desc": desc,
            "color": color, "params": params or [], "inputs": inputs or {},
            "outputs": outputs or {}, "run": fn,
            "debug": debug or [],
        }
        return fn
    return deco


def debug_action(type, name, label):
    """节点调试动作: 在属性面板/画布上直接单步执行 (如扫描串口、探测通道)"""
    def deco(fn):
        DEBUG[f"{type}:{name}"] = fn
        for n in NODES.values():
            if n["type"] == type and not any(d["name"] == name for d in n["debug"]):
                n["debug"].append({"name": name, "label": label})
        return fn
    return deco


# ============================ 电源 (继电器) ============================

_RELAY_PORT_PARAM = {"name": "port", "label": "继电器串口 (空=用 config 默认)",
                     "type": "port", "default": ""}


def _relay_port(params):
    return (params.get("port") or "").strip() or None


@node("relay.on", "电源模块", "继电器上电", "导通指定通道, 给模组上电", "#e8b339",
      params=[_RELAY_PORT_PARAM,
              {"name": "channel", "label": "通道", "type": "int", "default": 0}],
      outputs={"ok": "是否成功"},
      debug=[{"name": "scan_ports", "label": "扫描串口(探测继电器)"},
             {"name": "probe_channel", "label": "测试通道响应(通→断→通)"}])
def _relay_on(ctx, params, inputs):
    ctx.ensure_powered(int(params.get("channel", 0)))
    return {"ok": True}


@debug_action("relay.on", "scan_ports", "扫描串口")
def _dbg_scan(ctx, params):
    return scan_relay_ports()


@debug_action("relay.on", "probe_channel", "测试通道响应")
def _dbg_probe(ctx, params):
    relay = ctx.relay(_relay_port(params))
    ch = int(params.get("channel", 0))
    o1 = relay.open_channel(ch)
    c = relay.close_channel(ch)
    o2 = relay.open_channel(ch)
    ok = o1 and c and o2
    return {"ok": ok, "report": f"通道{ch} 导通={o1} 断开={c} 再导通={o2} -> "
            f"{'继电器响应正常' if ok else '存在失败项, 请检查接线/串口'}"}


@node("relay.off", "电源模块", "继电器断电", "断开指定通道, 模组掉电", "#e8b339",
      params=[_RELAY_PORT_PARAM,
              {"name": "channel", "label": "通道", "type": "int", "default": 0}],
      outputs={"ok": "是否成功"},
      debug=[{"name": "scan_ports", "label": "扫描串口(探测继电器)"}])
def _relay_off(ctx, params, inputs):
    ctx.power_off(int(params.get("channel", 0)))
    return {"ok": True}


@node("relay.power_cycle", "电源模块", "掉电重启", "断电保持 -> 重新上电 (规范 15s)", "#e8b339",
      params=[_RELAY_PORT_PARAM,
              {"name": "off_seconds", "label": "断电时长(s)", "type": "float", "default": 15}],
      outputs={"ok": "是否成功"},
      debug=[{"name": "scan_ports", "label": "扫描串口(探测继电器)"}])
def _relay_cycle(ctx, params, inputs):
    ctx.power_off()
    time.sleep(float(params.get("off_seconds", 15)))
    ctx.ensure_powered()
    return {"ok": True}


def scan_relay_ports():
    """子进程探测所有串口上的继电器 (进程退出即释放句柄, 不影响主进程)"""
    import subprocess
    import sys as _sys
    probe = ROOT / "app" / "engine" / "port_probe.py"
    r = subprocess.run([_sys.executable, str(probe)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.startswith("PROBE_JSON:")]
    if not lines:
        raise RuntimeError(f"串口探测失败: {r.stderr[:200] if r.stderr else '无输出'}")
    ports = json.loads(lines[-1][len("PROBE_JSON:"):])
    relay_ports = [p["port"] for p in ports if p["relay"]]
    return {"ok": True, "ports": ports,
            "report": "继电器所在串口: " + (", ".join(relay_ports) if relay_ports else "未发现(检查接线)")}


@debug_action("relay.power_cycle", "scan_ports", "扫描串口")
def _dbg_scan2(ctx, params):
    return scan_relay_ports()


@debug_action("relay.off", "scan_ports", "扫描串口")
def _dbg_scan3(ctx, params):
    return scan_relay_ports()


# ============================ 设备 ============================

@node("device.configure", "设备模块", "下发 ini 配置", "setConfigure 上电初始化文件并打开设备", "#4a89dc",
      params=[{"name": "ini", "label": "ini 文件", "type": "choice",
               "default": None, "options": _ini_options(), "optional": True}],
      outputs={"ok": "是否成功"})
def _dev_configure(ctx, params, inputs):
    ini = params.get("ini") or ctx.default_ini()
    ini_path = str(ROOT / "configs" / "init_file" / ini) if not str(ini).endswith(".ini") or "/" not in str(ini) and "\\" not in str(ini) else str(ini)
    if not Path(ini_path).exists():
        ini_path = str(ROOT / "configs" / "init_file" / Path(ini).name)
    dev = ctx.ensure_configured(ini_path)
    return {"ok": dev is not None}


@node("device.open_video", "设备模块", "打开视频流", "device_open_video", "#4a89dc",
      outputs={"ok": "是否成功"})
def _dev_video(ctx, params, inputs):
    ctx.ensure_video()
    return {"ok": True}


@node("device.grab_save", "设备模块", "抓帧存图", "抓一帧并保存到输出目录", "#4a89dc",
      params=[{"name": "name", "label": "文件名前缀", "type": "str", "default": "case_frame"}],
      inputs={"prefix": "文件名前缀(可由上游传入)"},
      outputs={"ok": "是否成功", "path": "图片路径"})
def _dev_grab(ctx, params, inputs):
    dev = ctx.ensure_video()
    prefix = _p("prefix")(inputs, params) or "case_frame"
    ok, path = ctx.image().capture(dev, str(prefix))
    if not ok:
        raise RuntimeError("抓帧失败")
    return {"ok": True, "path": str(path)}


@node("device.fps", "设备模块", "读取 FPS", "device_get_fps", "#4a89dc",
      outputs={"fps": "帧率"})
def _dev_fps(ctx, params, inputs):
    dev = ctx.ensure_video()
    return {"fps": round(dev.get_fps(), 2)}


@node("device.dn", "设备模块", "读取 DN 亮度", "device_get_current_DN", "#4a89dc",
      outputs={"dn": "DN 值"})
def _dev_dn(ctx, params, inputs):
    dev = ctx.ensure_video()
    return {"dn": round(dev.get_dn(), 2)}


@node("device.close_video", "设备模块", "关闭视频流", "device_close_video", "#4a89dc",
      outputs={"ok": "是否成功"})
def _dev_close_video(ctx, params, inputs):
    if ctx._video_on:
        ctx.device().close_video()
        ctx._video_on = False
    return {"ok": True}


# ============================ I2C ============================

_I2C_MODE_OPTS = ["A1D1", "A1D2", "A1D4", "A2D1", "A2D2", "A2D4", "A4D1", "A4D2", "A4D4"]


@node("i2c.rw", "FMC 模块", "I2C 读写模块", "读/写/写并校验 一体的 I2C 模块, 位宽 A1D1~A4D4 任选", "#3faf6e",
      params=[
          {"name": "op", "label": "操作", "type": "choice", "default": "read",
           "options": [{"v": "read", "l": "读寄存器"},
                       {"v": "write", "l": "写寄存器"},
                       {"v": "write_verify", "l": "写并校验"}]},
          {"name": "slave", "label": "从机地址", "type": "str", "default": "0x40", "hex": True},
          {"name": "addr", "label": "寄存器地址", "type": "str", "default": "0x00d8", "hex": True},
          {"name": "value", "label": "写入值(写操作时生效)", "type": "str", "default": "0x0001", "hex": True},
          {"name": "verify", "label": "写后回读校验", "type": "bool", "default": True},
          {"name": "mode", "label": "位宽模式", "type": "choice", "default": "A2D4", "options": _I2C_MODE_OPTS},
      ],
      inputs={"addr": "寄存器地址(可由上游传入)", "value": "写入值(可由上游传入)",
              "slave": "从机地址(可由上游传入)"},
      outputs={"ok": "是否成功", "value": "读到的值", "readback": "回读值", "match": "校验一致"})
def _i2c_rw(ctx, params, inputs):
    i2c = ctx.i2c()
    op = params.get("op", "read")
    slave = _hex(_p("slave")(inputs, params), 0x40)
    addr = _hex(_p("addr")(inputs, params))
    addr_len, bits = _mode(params.get("mode", "A2D4"))

    if op == "read":
        ok, value = i2c.read(addr, slave=slave, addr_len=addr_len, bits=bits)
        if not ok:
            raise RuntimeError(f"I2C 读失败 slave=0x{slave:02x} addr=0x{addr:04x} ({addr_len},{bits})")
        return {"ok": True, "value": value, "readback": None, "match": None}

    # 写 / 写并校验
    value = _hex(_p("value")(inputs, params))
    verify = bool(params.get("verify", True)) or op == "write_verify"
    if not i2c.write(addr, value, slave=slave, addr_len=addr_len, bits=bits):
        raise RuntimeError(f"I2C 写失败 slave=0x{slave:02x} addr=0x{addr:04x} val=0x{value:x}")
    if not verify:
        return {"ok": True, "value": None, "readback": None, "match": None}
    ok_r, readback = i2c.read(addr, slave=slave, addr_len=addr_len, bits=bits)
    if not ok_r:
        raise RuntimeError(f"写后回读失败 addr=0x{addr:04x}")
    if readback != value:
        raise RuntimeError(f"写后校验不一致: 写入 0x{value:x}, 回读 0x{readback:x}")
    return {"ok": True, "value": value, "readback": readback, "match": True}


@node("i2c.read", "FMC 模块", "读寄存器(单)", "device_I2C_Read", "#3faf6e",
      params=[
          {"name": "slave", "label": "从机地址", "type": "str", "default": "0x40", "hex": True},
          {"name": "addr", "label": "寄存器地址", "type": "str", "default": "0x00d8", "hex": True},
          {"name": "mode", "label": "位宽模式", "type": "choice", "default": "A2D4", "options": _I2C_MODE_OPTS},
      ],
      inputs={"addr": "寄存器地址(可由上游传入)", "slave": "从机地址(可由上游传入)"},
      outputs={"ok": "是否成功", "value": "读到的值"})
def _i2c_read(ctx, params, inputs):
    i2c = ctx.i2c()
    slave = _hex(_p("slave")(inputs, params), 0x40)
    addr = _hex(_p("addr")(inputs, params))
    addr_len, bits = _mode(params.get("mode", "A2D4"))
    ok, value = i2c.read(addr, slave=slave, addr_len=addr_len, bits=bits)
    if not ok:
        raise RuntimeError(f"I2C 读失败 slave=0x{slave:02x} addr=0x{addr:04x} ({addr_len},{bits})")
    return {"ok": True, "value": value}


@node("i2c.write", "FMC 模块", "写寄存器", "device_I2C_Write, 支持 A2D2/A2D4/A4D4 等位宽", "#3faf6e",
      params=[
          {"name": "slave", "label": "从机地址", "type": "str", "default": "0x40", "hex": True},
          {"name": "addr", "label": "寄存器地址", "type": "str", "default": "0x0918", "hex": True},
          {"name": "value", "label": "写入值", "type": "str", "default": "0x0001", "hex": True},
          {"name": "mode", "label": "位宽模式", "type": "choice", "default": "A2D2", "options": _I2C_MODE_OPTS},
      ],
      inputs={"addr": "寄存器地址(可由上游传入)", "value": "写入值(可由上游传入)",
              "slave": "从机地址(可由上游传入)"},
      outputs={"ok": "是否成功"})
def _i2c_write(ctx, params, inputs):
    i2c = ctx.i2c()
    slave = _hex(_p("slave")(inputs, params), 0x40)
    addr = _hex(_p("addr")(inputs, params))
    value = _hex(_p("value")(inputs, params))
    addr_len, bits = _mode(params.get("mode", "A2D2"))
    if not i2c.write(addr, value, slave=slave, addr_len=addr_len, bits=bits):
        raise RuntimeError(f"I2C 写失败 slave=0x{slave:02x} addr=0x{addr:04x} val=0x{value:x}")
    return {"ok": True}


@node("i2c.write_readback", "FMC 模块", "写后回读校验", "写寄存器后回读, 比对是否一致", "#3faf6e",
      params=[
          {"name": "slave", "label": "从机地址", "type": "str", "default": "0x40", "hex": True},
          {"name": "addr", "label": "寄存器地址", "type": "str", "default": "0x0918", "hex": True},
          {"name": "value", "label": "写入值", "type": "str", "default": "0x0001", "hex": True},
          {"name": "mode", "label": "位宽模式", "type": "choice", "default": "A2D2", "options": _I2C_MODE_OPTS},
      ],
      outputs={"ok": "是否成功", "readback": "回读值", "match": "是否一致"})
def _i2c_wrb(ctx, params, inputs):
    i2c = ctx.i2c()
    slave = _hex(params.get("slave"), 0x40)
    addr = _hex(params.get("addr"))
    value = _hex(params.get("value"))
    addr_len, bits = _mode(params.get("mode", "A2D2"))
    ok, readback, match = i2c.write_readback(addr, value, slave=slave,
                                             addr_len=addr_len, bits=bits)
    if not ok:
        raise RuntimeError(f"写回读校验失败 addr=0x{addr:04x}")
    return {"ok": True, "readback": readback, "match": bool(match)}


@node("i2c.read_regs", "FMC 模块", "批量读寄存器", "按逗号分隔的地址列表连续读取", "#3faf6e",
      params=[
          {"name": "slave", "label": "从机地址", "type": "str", "default": "0x40", "hex": True},
          {"name": "addrs", "label": "地址列表(逗号分隔)", "type": "str", "default": "0x00d8,0x00c0,0x00c4"},
          {"name": "mode", "label": "位宽模式", "type": "choice", "default": "A2D4", "options": _I2C_MODE_OPTS},
      ],
      outputs={"ok": "是否全部成功", "values": "JSON 结果"})
def _i2c_reads(ctx, params, inputs):
    from modules.checks import read_regs
    i2c = ctx.i2c()
    slave = _hex(params.get("slave"), 0x40)
    addrs = [_hex(a.strip(), 0) for a in str(params.get("addrs", "")).split(",") if a.strip()]
    addr_len, bits = _mode(params.get("mode", "A2D4"))
    ok, values = read_regs(i2c, addrs, addr_len=addr_len, bits=bits)
    pretty = {f"0x{a:04x}": (f"0x{v:08x}" if isinstance(v, int) else None) for a, v in values.items()}
    if not ok:
        raise RuntimeError(f"批量读有失败项: {pretty}")
    return {"ok": True, "values": pretty}


# ============================ 图像 ============================

_FMT_OPTS = ["uyvy", "yuyv", "yvyu", "vyuy"]


@node("image.capture_mean", "检查模块", "抓帧测亮度", "抓一帧并计算 Y 分量均值", "#9b59b6",
      params=[{"name": "name", "label": "文件名前缀", "type": "str", "default": "img"}],
      outputs={"ok": "是否成功", "mean": "亮度均值", "path": "图片路径"})
def _img_mean(ctx, params, inputs):
    dev = ctx.ensure_video()
    ok, path, mean = ctx.image().capture_mean(dev, str(params.get("name", "img")))
    if not ok:
        raise RuntimeError("抓帧测亮度失败")
    return {"ok": True, "mean": round(mean, 2), "path": str(path)}


@node("image.compare_register", "检查模块", "寄存器改值前后亮度对比",
      "改寄存器前后各抓一帧对比亮度, 验证寄存器是否生效 (自动恢复原值)", "#9b59b6",
      params=[
          {"name": "reg", "label": "寄存器地址", "type": "str", "default": "0x0091c", "hex": True},
          {"name": "value", "label": "修改值", "type": "str", "default": "0x60", "hex": True},
          {"name": "fmt", "label": "帧格式", "type": "choice", "default": "uyvy", "options": _FMT_OPTS},
          {"name": "settle_seconds", "label": "生效等待(s)", "type": "float", "default": 2},
      ],
      outputs={"pass": "是否生效", "mean_default": "改前亮度", "mean_modified": "改后亮度",
               "delta": "亮度差"})
def _img_compare(ctx, params, inputs):
    dev = ctx.ensure_video()
    r = ctx.image().compare_register(
        dev, ctx.i2c(),
        reg=_hex(params.get("reg")), value=_hex(params.get("value")),
        fmt=params.get("fmt", "uyvy"),
        settle_seconds=float(params.get("settle_seconds", 2)))
    if "error" in r:
        raise RuntimeError(r["error"])
    if not r["pass"]:
        raise RuntimeError(
            f"寄存器 0x{_hex(params.get('reg')):04x} 修改后亮度未变化 "
            f"({r['mean_default']} -> {r['mean_modified']})")
    return {k: r[k] for k in ("pass", "mean_default", "mean_modified", "delta")}


# ============================ 固件 ============================

@node("fw.download", "固件模块", "一键固件下载", "MatFwDownload 烧录固件 (需勾选确认)", "#e07b39",
      params=[
          {"name": "ini", "label": "ini 文件", "type": "choice", "default": None,
           "options": _ini_options(), "optional": True},
          {"name": "bin", "label": "固件文件", "type": "choice", "default": None,
           "options": _fw_options(), "optional": True},
          {"name": "retries", "label": "重试次数", "type": "int", "default": 3},
          {"name": "confirm", "label": "确认真实烧录", "type": "bool", "default": False},
      ],
      outputs={"ok": "是否成功"})
def _fw_download(ctx, params, inputs):
    if not params.get("confirm"):
        raise RuntimeError("未勾选『确认真实烧录』, 已跳过 (防误烧)")
    ctx.ensure_powered()
    ini = params.get("ini") or Path(ctx.default_ini()).name
    bin_name = params.get("bin") or (sorted((ROOT / "fw").glob("*.bin"))[0].name)
    ok = ctx.fw_downloader().download(
        str(ROOT / "configs" / "init_file" / Path(ini).name),
        str(ROOT / "fw" / Path(bin_name).name),
        max_retries=int(params.get("retries", 3)))
    if not ok:
        raise RuntimeError("MatFwDownload 失败")
    # 烧完掉电重启, 后续节点需重新配置
    ctx.power_off()
    time.sleep(15)
    ctx.ensure_powered()
    return {"ok": True}


@node("fw.soc_reboot", "固件模块", "SOC 重启", "firmware_socReboot", "#e07b39",
      outputs={"ok": "是否成功"})
def _fw_reboot(ctx, params, inputs):
    from modules.firmware import FirmwareFlasher
    dev = ctx.ensure_configured()
    ok = FirmwareFlasher(dev).soc_reboot()
    if not ok:
        raise RuntimeError("soc_reboot 失败")
    time.sleep(5)
    return {"ok": True}


@node("fw.erase", "固件模块", "擦除 Flash 扇区", "firmware_erase_flash (扇区号区间)", "#e07b39",
      params=[
          {"name": "start", "label": "起始扇区", "type": "int", "default": 0},
          {"name": "end", "label": "结束扇区", "type": "int", "default": 63},
      ],
      outputs={"ok": "是否成功"})
def _fw_erase(ctx, params, inputs):
    from modules.firmware import FirmwareFlasher
    dev = ctx.ensure_configured()
    if not FirmwareFlasher(dev).erase_flash(int(params.get("start", 0)),
                                            int(params.get("end", 63))):
        raise RuntimeError("擦除失败")
    return {"ok": True}


@node("fw.crc_check", "固件模块", "Flash CRC 校验", "firmware_flash_crc_check", "#e07b39",
      params=[
          {"name": "start", "label": "起始扇区", "type": "int", "default": 0},
          {"name": "end", "label": "结束扇区", "type": "int", "default": 63},
      ],
      outputs={"ok": "是否成功", "crc": "CRC 值"})
def _fw_crc(ctx, params, inputs):
    from modules.firmware import FirmwareFlasher
    dev = ctx.ensure_configured()
    ok, crc = FirmwareFlasher(dev).flash_crc_check(int(params.get("start", 0)),
                                                   int(params.get("end", 63)))
    if not ok:
        raise RuntimeError("CRC 校验失败")
    return {"ok": True, "crc": f"0x{crc:08x}"}


# ============================ 检查 ============================

@node("checks.fw_version", "检查模块", "读固件版本", "0x00d8 (A2D4)", "#5d8aa8",
      outputs={"ok": "是否成功", "version": "版本号"})
def _chk_version(ctx, params, inputs):
    from modules.checks import fw_version
    ok, ver = fw_version(ctx.i2c())
    if not ok:
        raise RuntimeError("固件版本读取失败")
    return {"ok": True, "version": ver}


@node("checks.start_status", "检查模块", "启动状态检查", "ROM/SRAM 启动信息与启动区", "#5d8aa8",
      outputs={"ok": "是否成功", "area": "启动区", "desc": "描述"})
def _chk_boot(ctx, params, inputs):
    from modules.checks import start_status
    ok, st = start_status(ctx.i2c())
    if not ok:
        raise RuntimeError("启动状态读取失败")
    if st["rom"] != 0x04FB:
        raise RuntimeError(st["desc"])
    return {"ok": True, "area": st["area"], "desc": st["desc"]}


@node("checks.frame_counter", "检查模块", "帧计数器检查", "间隔采样 0x00cc 是否递增", "#5d8aa8",
      params=[{"name": "interval", "label": "采样间隔(s)", "type": "float", "default": 2}],
      outputs={"ok": "是否成功", "counting": "是否递增"})
def _chk_cnt(ctx, params, inputs):
    from modules.checks import frame_counter_ok
    ok, counting = frame_counter_ok(ctx.i2c(), float(params.get("interval", 2)))
    if not ok:
        raise RuntimeError("帧计数器读取失败")
    if not counting:
        raise RuntimeError("帧计数器未递增, 固件可能卡死")
    return {"ok": True, "counting": True}


@node("checks.alg_ctrl", "检查模块", "AWB/AE 算法开关", "0x0918/0x091c (A2D2)", "#5d8aa8",
      params=[
          {"name": "awb", "label": "AWB", "type": "choice", "default": "on",
           "options": ["on", "off"]},
          {"name": "ae", "label": "AE", "type": "choice", "default": "on",
           "options": ["on", "off"]},
      ],
      outputs={"ok": "是否成功"})
def _chk_alg(ctx, params, inputs):
    from modules.checks import alg_ctrl
    ok = alg_ctrl(ctx.i2c(),
                  awb=params.get("awb") == "on",
                  ae=params.get("ae") == "on")
    if not ok:
        raise RuntimeError("算法开关写入失败")
    return {"ok": True}


@node("checks.fs_check", "检查模块", "功能安全检查", "0x093c/0x0940 位定义表", "#5d8aa8",
      outputs={"ok": "是否成功", "errors": "错误列表 JSON"})
def _chk_fs(ctx, params, inputs):
    from modules.checks import fs_check
    ok, errors = fs_check(ctx.i2c())
    if not ok:
        raise RuntimeError("功能安全寄存器读取失败")
    if errors:
        raise RuntimeError("功能安全错误: " + "; ".join(errors))
    return {"ok": True, "errors": []}


@node("checks.switch_clock", "检查模块", "时钟切换", "0x80 器件 0x04 (A1D1), 升级前开时钟", "#5d8aa8",
      params=[{"name": "on", "label": "开关", "type": "choice", "default": "on",
               "options": ["on", "off"]}],
      outputs={"ok": "是否成功"})
def _chk_clk(ctx, params, inputs):
    from modules.checks import switch_clock
    if not switch_clock(ctx.i2c(), params.get("on", "on") == "on"):
        raise RuntimeError("时钟切换失败")
    return {"ok": True}


# ============================ 流程 ============================

@node("flow.reroute", "流程工具", "转接点", "理线用: 数据/执行流可在此中转, 保持连线整洁", "#777777",
      inputs={"in": "输入"},
      outputs={"out": "输出"})
def _flow_reroute(ctx, params, inputs):
    return {"out": inputs.get("in")}


@node("flow.delay", "流程工具", "延时", "等待指定秒数", "#888888",
      params=[{"name": "seconds", "label": "秒", "type": "float", "default": 3}],
      outputs={"ok": "完成"})
def _flow_delay(ctx, params, inputs):
    time.sleep(float(params.get("seconds", 3)))
    return {"ok": True}


@node("flow.log", "流程工具", "打印日志", "输出一条信息到运行日志", "#888888",
      params=[{"name": "message", "label": "内容", "type": "str", "default": "hello"}],
      outputs={"ok": "完成", "message": "内容"})
def _flow_log(ctx, params, inputs):
    msg = str(params.get("message", ""))
    print(f"[canvas] {msg}")
    return {"ok": True, "message": msg}


@node("flow.assert_value", "流程工具", "数值断言", "对上游值做 (值 & 掩码) >> 位移 <op> 期望 断言", "#c0504d",
      params=[
          {"name": "mask", "label": "掩码", "type": "str", "default": "0xFFFFFFFF", "hex": True},
          {"name": "shift", "label": "右移位数", "type": "int", "default": 0},
          {"name": "op", "label": "比较", "type": "choice", "default": "==",
           "options": ["==", "!=", ">", ">=", "<", "<="]},
          {"name": "expected", "label": "期望值", "type": "str", "default": "0x1", "hex": True},
      ],
      inputs={"value": "待断言的值"},
      outputs={"ok": "是否通过", "actual": "实际值"})
def _flow_assert(ctx, params, inputs):
    raw = _p("value")(inputs, params)
    if raw is None:
        raise RuntimeError("断言节点未接入待断言的值")
    mask = _hex(params.get("mask"), 0xFFFFFFFF)
    shift = int(params.get("shift", 0))
    actual = (int(raw) & mask) >> shift
    expected = _hex(params.get("expected"))
    op = params.get("op", "==")
    ops = {"==": lambda: actual == expected, "!=": lambda: actual != expected,
           ">": lambda: actual > expected, ">=": lambda: actual >= expected,
           "<": lambda: actual < expected, "<=": lambda: actual <= expected}
    passed = ops[op]()
    if not passed:
        raise RuntimeError(
            f"断言失败: (0x{int(raw):x} & 0x{mask:x}) >> {shift} = 0x{actual:x}, "
            f"期望 {op} 0x{expected:x}")
    return {"ok": True, "actual": actual}


def get_registry():
    """返回给前端的节点 schema (去掉 run 函数)"""
    return [{k: v for k, v in n.items() if k != "run"} for n in NODES.values()]


def get_node(type):
    return NODES[type]
