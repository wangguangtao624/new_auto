# -*- coding: utf-8 -*-
"""用例: demo_上电读版本出图  (由画布自动生成, 可直接运行)

运行:  python cases/demo_上电读版本出图.py    (在 new_auto 目录下)
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


def main():
    ctx = Session()
    ctx.relay('COM3')  # 指定继电器串口
    ctx.ensure_powered(0)

    ctx.power_off(0)

    ctx.ensure_configured(ctx.default_ini())

    _m = _I_MODE['A2D4']
    vn3_ok, vn3_value = ctx.i2c().read(0xd8, slave=0x40, addr_len=_m[0], bits=_m[1])
    assert vn3_ok, 'I2C 读失败'
    print('[i2c.rw] value =', hex(vn3_value))

    _raw = vn3_value
    assert _raw is not None, '断言节点未接入值'
    _actual = (_raw & 0xff0000) >> 16
    assert _actual >= 0x4, f'断言失败: {_actual:#x} >= 0x4'
    print('[flow.assert_value] actual =', hex(_actual))

    ctx.ensure_video()

    vn6_ok, vn6_path = ctx.image().capture(ctx.ensure_video(), 'demo')
    assert vn6_ok, '抓帧失败'

    vn7_fps = ctx.ensure_video().get_fps()
    print('[device.fps] fps =', vn7_fps)

    ctx.power_off(0)

    print('用例执行完成: 全部节点通过')


if __name__ == '__main__':
    main()