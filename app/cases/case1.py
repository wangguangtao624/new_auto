# -*- coding: utf-8 -*-
"""用例: case1  (由画布自动生成, 可直接运行)

运行:  python cases/case1.py    (在 new_auto 目录下)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.engine.session import Session

# I<m>D<n> = <m> 字节地址 / <n> 字节数据 -> (addr_len_bits, data_bits)
_I_MODE = {'A1D1': (8, 8), 'A1D2': (8, 16), 'A1D4': (8, 32),
           'A2D1': (16, 8), 'A2D2': (16, 16), 'A2D4': (16, 32),
           'A4D1': (32, 8), 'A4D2': (32, 16), 'A4D4': (32, 32)}
from app.engine.registry import get_node as _gn


def main():
    ctx = Session()
    ctx.relay('COM9')  # 指定继电器串口
    ctx.ensure_powered(0)

    import time; time.sleep(3)

    _dev = ctx.ensure_configured()
    ctx.ensure_video()
    _ok, _path = ctx.image().capture(_dev, '01')
    assert _ok, '抓帧存图失败'
    print('[device.stream] 抓帧:', _path)
    print('[device.stream] fps =', round(_dev.get_fps(), 2))
    print('[device.stream] dn =', round(_dev.get_dn(), 2))

    vnfx9zk_ok, vnfx9zk_path, vnfx9zk_mean = ctx.image().capture_mean(ctx.ensure_video(), "'img'")
    assert vnfx9zk_ok, '抓帧测亮度失败'
    print('[image.capture_mean] mean =', vnfx9zk_mean)

    from modules.i2c import I2CController as _I
    _m_def = _I_MODE['A2D2']
    _i2c = ctx.i2c()
    _slave = 0x40
    _results = []
    _OPS = 'read 0x00d8 A2D4\nwrite 0x0938 0x0001 A2D2'
    for _raw in str(_OPS).splitlines():
        _line = _raw.split('#')[0].strip()
        if not _line: continue
        _p = _line.split()
        _op = _p[0].lower()
        if _op == 'read':
            _m = _I_MODE[_p[2]] if len(_p) > 2 else _m_def
            _ok, _v = _i2c.read(int(_p[1],16), slave=_slave, addr_len=_m[0], bits=_m[1])
            assert _ok, f'读失败 {_line}'
            print(f'  [read] 0x{int(_p[1],16):04x} = 0x{_v:x}')
        elif _op == 'write':
            _m = _I_MODE[_p[3]] if len(_p) > 3 else _m_def
            _a, _val = int(_p[1],16), int(_p[2],16)
            assert _i2c.write(_a, _val, slave=_slave, addr_len=_m[0], bits=_m[1]), f'写失败 {_line}'
            print(f'  [write] 0x{_a:04x} = 0x{_val:x}')
        elif _op == 'verify':
            _m = _I_MODE[_p[3]] if len(_p) > 3 else _m_def
            _a, _val = int(_p[1],16), int(_p[2],16)
            assert _i2c.write(_a, _val, slave=_slave, addr_len=_m[0], bits=_m[1]), f'写失败 {_line}'
            _ok, _rb = _i2c.read(_a, slave=_slave, addr_len=_m[0], bits=_m[1])
            assert _ok and _rb == _val, f'回读不一致: 写 0x{_val:x} 读 0x{_rb:x}'
            print(f'  [verify] 0x{_a:04x} = 0x{_rb:x} 校验通过')
        elif _op == 'expect':
            _m = _I_MODE[_p[5]] if len(_p) > 5 else _m_def
            _a, _exp = int(_p[1],16), int(_p[2],16)
            _mask = int(_p[3],16) if len(_p) > 3 else 0xFFFFFFFF
            _sh = int(_p[4],0) if len(_p) > 4 else 0
            _ok, _v = _i2c.read(_a, slave=_slave, addr_len=_m[0], bits=_m[1])
            assert _ok, f'读失败 {_line}'
            _act = (_v & _mask) >> _sh
            assert _act == _exp, f'断言失败: 实际 0x{_act:x} 期望 0x{_exp:x} ({_line})'
            print(f'  [expect] 0x{_act:x} == 0x{_exp:x} 通过')
        else:
            raise RuntimeError(f'未知操作: {_op}')
    print('[i2c.batch] 全部通过')

    import time; time.sleep(3)

    vnwyclr_ok, vnwyclr_path, vnwyclr_mean = ctx.image().capture_mean(ctx.ensure_video(), "'img'")
    assert vnwyclr_ok, '抓帧测亮度失败'
    print('[image.capture_mean] mean =', vnwyclr_mean)

    _dev = ctx.ensure_configured()
    ctx.ensure_video()
    _ok, _path = ctx.image().capture(_dev, '02')
    assert _ok, '抓帧存图失败'
    print('[device.stream] 抓帧:', _path)
    print('[device.stream] fps =', round(_dev.get_fps(), 2))
    print('[device.stream] dn =', round(_dev.get_dn(), 2))

    ctx.relay('COM9')  # 指定继电器串口
    ctx.power_off(0)

    print('用例执行完成: 全部节点通过')


if __name__ == '__main__':
    main()