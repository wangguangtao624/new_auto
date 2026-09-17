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

# v2 收敛节点: 生成脚本时直接委托 run(), 不重复实现一遍逻辑
_DELEGATED_TYPES = {"power.ctrl", "device.open", "device.check", "device.close",
                    "i2c.seq", "fw.download"}

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
        "from app.engine.registry import get_node as _gn",
        "",
        "",
        "def main():",
        "    ctx = Session()",
        # 绑 case: 抓帧/日志落进 logs/cases/<case>/, 与画布执行一致
        f"    ctx.set_case({canvas.get('name', name)!r})",
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

        if ntype == "relay.ctrl":
            if params.get("port"):
                lines.append(f"    ctx.relay({params['port']!r})  # 指定继电器串口")
            action = params.get("action", "on")
            if action == "on":
                lines.append(f"    ctx.ensure_powered({pv('channel', 0)})")
            elif action == "off":
                lines.append(f"    ctx.power_off({pv('channel', 0)})")
            else:
                lines.append("    ctx.power_off()")
                lines.append(f"    time.sleep({pv('off_seconds', 15)})")
                lines.append(f"    ctx.ensure_powered({pv('channel', 0)})")
        elif ntype == "device.stream":
            ini = params.get("ini")
            if ini:
                lines.append(f"    _dev = ctx.ensure_configured("
                             f"str(ROOT / 'configs' / 'init_file' / {ini!r}))")
            else:
                lines.append("    _dev = ctx.ensure_configured()")
            if params.get("open_video", True):
                lines.append("    ctx.ensure_video()")
            if params.get("capture"):
                lines.append(f"    _ok, _path = ctx.image().capture(_dev, {params.get('name', 'case_frame')!r})")
                lines.append("    assert _ok, '抓帧存图失败'")
                lines.append("    print('[device.stream] 抓帧:', _path)")
            if params.get("read_fps"):
                lines.append("    print('[device.stream] fps =', round(_dev.get_fps(), 2))")
            if params.get("read_dn"):
                lines.append("    print('[device.stream] dn =', round(_dev.get_dn(), 2))")
        elif ntype == "relay.on":
            if params.get("port"):
                lines.append(f"    ctx.relay({params['port']!r})  # 指定继电器串口")
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
        elif ntype == "i2c.rw":
            mode = params.get("mode", "A2D4")
            op = params.get("op", "read")
            verify = bool(params.get("verify", True))
            lines.append(f"    _m = _I_MODE['{mode}']")
            if op == "read":
                lines.append(f"    {var}_ok, {var}_value = ctx.i2c().read("
                             f"{pv('addr', '0x00d8')}, slave={pv('slave', '0x40')}, "
                             f"addr_len=_m[0], bits=_m[1])")
                lines.append(f"    assert {var}_ok, 'I2C 读失败'")
                lines.append(f"    print('[i2c.rw] value =', hex({var}_value))")
            else:
                do_verify = verify or op == "write_verify"
                lines.append(f"    {var}_ok = ctx.i2c().write("
                             f"{pv('addr', '0x0918')}, {pv('value', '0x0001')}, "
                             f"slave={pv('slave', '0x40')}, addr_len=_m[0], bits=_m[1])")
                lines.append(f"    assert {var}_ok, 'I2C 写失败'")
                if do_verify:
                    lines.append(f"    {var}_rb = ctx.i2c().read("
                                 f"{pv('addr', '0x0918')}, slave={pv('slave', '0x40')}, "
                                 f"addr_len=_m[0], bits=_m[1])[1]")
                    lines.append(f"    assert {var}_rb == {pv('value', '0x0001')}, "
                                 f"f'写后校验不一致: {{ {var}_rb:#x }}'")
                    lines.append(f"    print('[i2c.rw] 写并校验通过')")
        elif ntype == "i2c.batch":
            slave = pv("slave", "0x40")
            mode = params.get("mode", "A2D2")
            ops = params.get("ops", "")
            lines.append("    from modules.i2c import I2CController as _I")
            lines.append("    _m_def = _I_MODE['%s']" % mode)
            lines.append("    _i2c = ctx.i2c()")
            lines.append("    _slave = %s" % slave)
            lines.append("    _results = []")
            lines.append("    _OPS = %r" % ops)
            lines.append("    for _raw in str(_OPS).splitlines():")
            lines.append("        _line = _raw.split('#')[0].strip()")
            lines.append("        if not _line: continue")
            lines.append("        _p = _line.split()")
            lines.append("        _op = _p[0].lower()")
            lines.append("        if _op == 'read':")
            # 各指令字段位不同: read(addr,mode) / write|verify(addr,val,mode)
            # / expect(addr,expected,mask,shift,mode)
            lines.append("            _m = _I_MODE[_p[2]] if len(_p) > 2 else _m_def")
            lines.append("            _ok, _v = _i2c.read(int(_p[1],16), slave=_slave, addr_len=_m[0], bits=_m[1])")
            lines.append("            assert _ok, f'读失败 {_line}'")
            lines.append("            print(f'  [read] 0x{int(_p[1],16):04x} = 0x{_v:x}')")
            lines.append("        elif _op == 'write':")
            lines.append("            _m = _I_MODE[_p[3]] if len(_p) > 3 else _m_def")
            lines.append("            _a, _val = int(_p[1],16), int(_p[2],16)")
            lines.append("            assert _i2c.write(_a, _val, slave=_slave, addr_len=_m[0], bits=_m[1]), f'写失败 {_line}'")
            lines.append("            print(f'  [write] 0x{_a:04x} = 0x{_val:x}')")
            lines.append("        elif _op == 'verify':")
            lines.append("            _m = _I_MODE[_p[3]] if len(_p) > 3 else _m_def")
            lines.append("            _a, _val = int(_p[1],16), int(_p[2],16)")
            lines.append("            assert _i2c.write(_a, _val, slave=_slave, addr_len=_m[0], bits=_m[1]), f'写失败 {_line}'")
            lines.append("            _ok, _rb = _i2c.read(_a, slave=_slave, addr_len=_m[0], bits=_m[1])")
            lines.append("            assert _ok and _rb == _val, f'回读不一致: 写 0x{_val:x} 读 0x{_rb:x}'")
            lines.append("            print(f'  [verify] 0x{_a:04x} = 0x{_rb:x} 校验通过')")
            lines.append("        elif _op == 'expect':")
            lines.append("            _m = _I_MODE[_p[5]] if len(_p) > 5 else _m_def")
            lines.append("            _a, _exp = int(_p[1],16), int(_p[2],16)")
            lines.append("            _mask = int(_p[3],16) if len(_p) > 3 else 0xFFFFFFFF")
            lines.append("            _sh = int(_p[4],0) if len(_p) > 4 else 0")
            lines.append("            _ok, _v = _i2c.read(_a, slave=_slave, addr_len=_m[0], bits=_m[1])")
            lines.append("            assert _ok, f'读失败 {_line}'")
            lines.append("            _act = (_v & _mask) >> _sh")
            lines.append("            assert _act == _exp, f'断言失败: 实际 0x{_act:x} 期望 0x{_exp:x} ({_line})'")
            lines.append("            print(f'  [expect] 0x{_act:x} == 0x{_exp:x} 通过')")
            lines.append("        else:")
            lines.append("            raise RuntimeError(f'未知操作: {_op}')")
            lines.append("    print('[i2c.batch] 全部通过')")
        elif ntype == "flow.reroute":
            if "in" in ins:
                _src, _port = ins["in"]
                _expr = f"{var_of[_src]}_{_safe(_port)}"
            else:
                _expr = "None"
            lines.append(f"    {var}_out = {_expr}")
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
        # 收敛后的 v2 节点: 直接委托给注册表里的 run(),
        # 保证「画布执行」与「生成的用例脚本」语义完全一致 (含表格/操作列表参数)
        elif ntype in _DELEGATED_TYPES:
            lines.append("    _outs = _gn(%r)['run'](ctx, %r, {}) or {}" % (ntype, params))
            lines.append("    print(%r, {k: v for k, v in _outs.items() if k != 'ok'})"
                         % f"[{ntype}] ok")
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
