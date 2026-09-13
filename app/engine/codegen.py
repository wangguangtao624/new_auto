# -*- coding: utf-8 -*-
"""代码生成: 画布 JSON -> 独立可运行的 Python 用例脚本

生成物放在 app/cases/<name>.py, 直接 `python cases/<name>.py` 即可按
画布流程执行 (与画布执行器同语义), 方便把调好的 case 固化成回归脚本。
"""
import re
from pathlib import Path

from .registry import NODES

APP_DIR = Path(__file__).resolve().parent.parent
CASES_DIR = APP_DIR / "cases"

# 参数名 -> 合法 python 变量名
def _safe(s):
    return re.sub(r"\W", "_", str(s))


def generate(canvas: dict) -> Path:
    """生成用例脚本, 返回文件路径"""
    from .executor import topo_sort

    name = _safe(canvas.get("name", "case"))
    nodes = canvas.get("nodes", [])
    edges = canvas.get("edges", [])
    order, by_id, _adj = topo_sort(nodes, edges)
    incoming = {}
    for e in edges:
        incoming.setdefault(e["to"], {})[e["toParam"]] = (e["from"], e["fromPort"])

    lines = [
        "# -*- coding: utf-8 -*-",
        f'"""用例: {canvas.get("name", "case")}  (由画布自动生成, 可直接运行)',
        "",
        "运行:  python cases/{0}.py    (在 new_auto 目录下)".format(name),
        '"""',
        "import sys",
        "from pathlib import Path",
        "",
        "ROOT = Path(__file__).resolve().parent.parent.parent",
        "sys.path.insert(0, str(ROOT))",
        "",
        "from app.engine.session import Session",
        "",
        "",
        "def main():",
        "    ctx = Session()",
    ]

    var_of = {}  # node id -> 输出变量名字典

    def _hex_literal(v):
        """'0x1a'/'1a'/26 -> '0x1a' 十六进制整数字面量"""
        try:
            return hex(int(str(v), 0))
        except (ValueError, TypeError):
            return hex(int(str(v), 16))

    for nid in order:
        node = by_id[nid]
        ntype = node["type"]
        params = node.get("params", {})
        ins = incoming.get(nid, {})
        var = f"v{_safe(nid)}"
        var_of[nid] = var

        schema = {p["name"]: p for p in NODES[ntype]["params"]}

        def pv(key, default=None):
            # 连线值优先 -> 参数字面量 (hex 参数输出整数字面量)
            if key in ins:
                src, port = ins[key]
                return f"{var_of[src]}_{_safe(port)}"
            if key in params and params[key] not in (None, ""):
                v = params[key]
            else:
                v = default
            if schema.get(key, {}).get("hex"):
                return _hex_literal(v)
            if isinstance(v, str):
                return repr(v)
            return repr(v)

        def iv(key):
            """input-only 值 (如断言的 value)"""
            if key in ins:
                src, port = ins[key]
                return f"{var_of[src]}_{_safe(port)}"
            return repr(params.get(key))

        if ntype == "relay.on":
            lines.append(f"    ctx.ensure_powered({pv('channel', 0)})")
        elif ntype == "relay.off":
            lines.append(f"    ctx.power_off({pv('channel', 0)})")
        elif ntype == "relay.power_cycle":
            lines.append("    ctx.power_off()")
            lines.append(f"    import time; time.sleep({pv('off_seconds', 15)})")
            lines.append("    ctx.ensure_powered()")
        elif ntype == "device.configure":
            ini = params.get("ini")
            ini_expr = (f"str(ROOT / 'configs' / 'init_file' / {ini!r})"
                        if ini else "ctx.default_ini()")
            lines.append(f"    ctx.ensure_configured({ini_expr})")
        elif ntype == "device.open_video":
            lines.append("    ctx.ensure_video()")
        elif ntype == "device.close_video":
            lines.append(f"    {var}_ok = ctx.device().close_video() if ctx._video_on else True")
        elif ntype == "device.grab_save":
            prefix = pv("prefix") if "prefix" in ins else repr(params.get("name", "case_frame"))
            lines.append(f"    {var}_ok, {var}_path = ctx.image().capture(ctx.ensure_video(), {prefix})")
            lines.append(f"    assert {var}_ok, '抓帧失败'")
        elif ntype == "device.fps":
            lines.append(f"    {var}_fps = ctx.ensure_video().get_fps()")
            lines.append(f"    print('[{ntype}] fps =', {var}_fps)")
        elif ntype == "device.dn":
            lines.append(f"    {var}_dn = ctx.ensure_video().get_dn()")
            lines.append(f"    print('[{ntype}] dn =', {var}_dn)")
        elif ntype == "i2c.read":
            mode = params.get("mode", "A2D4")
            lines.append(f"    _m = _I_MODE['{mode}']")
            lines.append(f"    {var}_ok, {var}_value = ctx.i2c().read("
                         f"{pv('addr', '0x00d8')}, slave={pv('slave', '0x40')}, "
                         f"addr_len=_m[0], bits=_m[1])")
            lines.append(f"    assert {var}_ok, 'I2C 读失败'")
            lines.append(f"    print('[{ntype}] value =', hex({var}_value))")
        elif ntype == "i2c.write":
            mode = params.get("mode", "A2D2")
            lines.append(f"    _m = _I_MODE['{mode}']")
            lines.append(f"    {var}_ok = ctx.i2c().write("
                         f"{pv('addr', '0x0918')}, {pv('value', '0x0001')}, "
                         f"slave={pv('slave', '0x40')}, addr_len=_m[0], bits=_m[1])")
            lines.append(f"    assert {var}_ok, 'I2C 写失败'")
        elif ntype == "i2c.write_readback":
            mode = params.get("mode", "A2D2")
            lines.append(f"    _m = _I_MODE['{mode}']")
            lines.append(f"    {var}_ok, {var}_rb, {var}_match = ctx.i2c().write_readback("
                         f"{pv('addr', '0x0918')}, {pv('value', '0x0001')}, "
                         f"slave={pv('slave', '0x40')}, addr_len=_m[0], bits=_m[1])")
            lines.append(f"    assert {var}_ok and {var}_match, '写回读不一致'")
        elif ntype == "i2c.read_regs":
            slave = pv("slave", "0x40")
            addrs = params.get("addrs", "")
            addr_list = ", ".join(_hex_literal(a) for a in
                                  str(addrs).split(",") if a.strip())
            mode = params.get("mode", "A2D4")
            lines.append(f"    _m = _I_MODE['{mode}']")
            lines.append(f"    from modules.checks import read_regs")
            lines.append(f"    {var}_ok, {var}_vals = read_regs(ctx.i2c(), [{addr_list}], "
                         f"addr_len=_m[0], bits=_m[1], slave={slave})")
            lines.append(f"    assert {var}_ok, '批量读有失败'")
            lines.append(f"    print('[{ntype}]', {var}_vals)")
        elif ntype == "image.capture_mean":
            lines.append(f"    {var}_ok, {var}_path, {var}_mean = "
                         f"ctx.image().capture_mean(ctx.ensure_video(), {pv('name', 'img')!r})")
            lines.append(f"    assert {var}_ok, '抓帧测亮度失败'")
            lines.append(f"    print('[{ntype}] mean =', {var}_mean)")
        elif ntype == "image.compare_register":
            lines.append(f"    {var}_r = ctx.image().compare_register(")
            lines.append(f"        ctx.ensure_video(), ctx.i2c(), reg={pv('reg', '0x0091c')}, "
                         f"value={pv('value', '0x60')}, fmt={params.get('fmt', 'uyvy')!r}, "
                         f"settle_seconds={pv('settle_seconds', 2)})")
            lines.append(f"    assert {var}_r.get('pass'), f\"寄存器未生效: {{ {var}_r }}\"")
            lines.append(f"    print('[{ntype}]', {var}_r)")
        elif ntype == "fw.download":
            ini = params.get("ini")
            binp = params.get("bin")
            ini_expr = (f"str(ROOT / 'configs' / 'init_file' / {ini!r})"
                        if ini else "ctx.default_ini()")
            bin_expr = (f"str(ROOT / 'fw' / {binp!r})"
                        if binp else "str(sorted((ROOT / 'fw').glob('*.bin'))[0])")
            lines.append(f"    ctx.ensure_powered()")
            lines.append(f"    assert ctx.fw_downloader().download({ini_expr}, {bin_expr}, "
                         f"max_retries={pv('retries', 3)}), '固件下载失败'")
            lines.append("    ctx.power_off(); import time; time.sleep(15); ctx.ensure_powered()")
        elif ntype == "fw.soc_reboot":
            lines.append("    from modules.firmware import FirmwareFlasher")
            lines.append("    assert FirmwareFlasher(ctx.ensure_configured()).soc_reboot(), 'soc_reboot 失败'")
        elif ntype == "fw.erase":
            lines.append("    from modules.firmware import FirmwareFlasher")
            lines.append(f"    assert FirmwareFlasher(ctx.ensure_configured()).erase_flash("
                         f"{pv('start', 0)}, {pv('end', 63)}), '擦除失败'")
        elif ntype == "fw.crc_check":
            lines.append("    from modules.firmware import FirmwareFlasher")
            lines.append(f"    {var}_ok, {var}_crc = FirmwareFlasher(ctx.ensure_configured())"
                         f".flash_crc_check({pv('start', 0)}, {pv('end', 63)})")
            lines.append(f"    assert {var}_ok, 'CRC 校验失败'")
            lines.append(f"    print('[{ntype}] crc =', hex({var}_crc))")
        elif ntype == "checks.fw_version":
            lines.append("    from modules.checks import fw_version")
            lines.append(f"    {var}_ok, {var}_version = fw_version(ctx.i2c())")
            lines.append(f"    assert {var}_ok, '版本读取失败'")
            lines.append(f"    print('[{ntype}] version =', {var}_version)")
        elif ntype == "checks.start_status":
            lines.append("    from modules.checks import start_status")
            lines.append(f"    {var}_ok, {var}_st = start_status(ctx.i2c())")
            lines.append(f"    assert {var}_ok and {var}_st['rom'] == 0x04FB, '启动状态异常'")
            lines.append(f"    print('[{ntype}] 从', {var}_st['area'], '区启动')")
        elif ntype == "checks.frame_counter":
            lines.append("    from modules.checks import frame_counter_ok")
            lines.append(f"    {var}_ok, {var}_counting = frame_counter_ok("
                         f"ctx.i2c(), {pv('interval', 2)})")
            lines.append(f"    assert {var}_ok and {var}_counting, '帧计数器未递增'")
        elif ntype == "checks.alg_ctrl":
            lines.append("    from modules.checks import alg_ctrl")
            lines.append(f"    assert alg_ctrl(ctx.i2c(), awb={params.get('awb') == 'on'}, "
                         f"ae={params.get('ae') == 'on'}), '算法开关失败'")
        elif ntype == "checks.fs_check":
            lines.append("    from modules.checks import fs_check")
            lines.append(f"    {var}_ok, {var}_errors = fs_check(ctx.i2c())")
            lines.append(f"    assert {var}_ok and not {var}_errors, f'功能安全错误: {{ {var}_errors }}'")
        elif ntype == "checks.switch_clock":
            lines.append("    from modules.checks import switch_clock")
            lines.append(f"    assert switch_clock(ctx.i2c(), {params.get('on', 'on') == 'on'}), '时钟切换失败'")
        elif ntype == "flow.delay":
            lines.append(f"    import time; time.sleep({pv('seconds', 3)})")
        elif ntype == "flow.log":
            lines.append(f"    print('[log]', {pv('message', '')})")
        elif ntype == "flow.assert_value":
            raw = iv("value")
            lines.append(f"    _raw = {raw}")
            lines.append(f"    assert _raw is not None, '断言节点未接入值'")
            lines.append(f"    _actual = (_raw & {pv('mask', '0xFFFFFFFF')}) >> {pv('shift', 0)}")
            lines.append(f"    assert _actual {params.get('op', '==')} {pv('expected', '0x1')}, "
                         f"f'断言失败: {{_actual:#x}} {params.get('op', '==')} {params.get('expected', '0x1')}'")
            lines.append(f"    print('[{ntype}] actual =', hex(_actual))")
        else:
            lines.append(f"    raise RuntimeError('未支持的节点类型: {ntype}')")
        lines.append("")

    lines += [
        "    print('用例执行完成: 全部节点通过')",
        "",
        "",
        "if __name__ == '__main__':",
        "    main()",
    ]

    # 顶部补充 I2C 位宽表
    body = "\n".join(lines)
    if "_I_MODE" in body:
        body = body.replace(
            "from app.engine.session import Session",
            "from app.engine.session import Session\n\n"
            "# I<m>D<n> = <m> 字节地址 / <n> 字节数据 -> (addr_len_bits, data_bits)\n"
            "_I_MODE = {'A1D1': (8, 8), 'A1D2': (8, 16), 'A1D4': (8, 32),\n"
            "           'A2D1': (16, 8), 'A2D2': (16, 16), 'A2D4': (16, 32),\n"
            "           'A4D1': (32, 8), 'A4D2': (32, 16), 'A4D4': (32, 32)}",
        )

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    out = CASES_DIR / f"{name}.py"
    out.write_text(body, encoding="utf-8")
    return out


def _hex_literal(v):
    s = str(v).strip()
    try:
        return hex(int(s, 0))
    except ValueError:
        return hex(0)
