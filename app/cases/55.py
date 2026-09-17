# -*- coding: utf-8 -*-
"""用例: 55  (由画布自动生成, 可直接运行)

运行:  python cases/55.py    (在 new_auto 目录下)
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
    ctx.power_off()
    import time; time.sleep(15)
    ctx.ensure_powered()

    ctx.ensure_configured(ctx.default_ini())

    ctx.ensure_video()

    import time; time.sleep(3)

    _m = _I_MODE['A2D4']
    vnpt142_ok, vnpt142_value = ctx.i2c().read(0xcc, slave=0x40, addr_len=_m[0], bits=_m[1])
    assert vnpt142_ok, 'I2C 读失败'
    print('[i2c.read] value =', hex(vnpt142_value))

    vn3mx3u_fps = ctx.ensure_video().get_fps()
    print('[device.fps] fps =', vn3mx3u_fps)

    vnjft2d_ok, vnjft2d_path = ctx.image().capture(ctx.ensure_video(), 'case_frame')
    assert vnjft2d_ok, '抓帧失败'

    vnz04ac_dn = ctx.ensure_video().get_dn()
    print('[device.dn] dn =', vnz04ac_dn)

    ctx.power_off(0)

    print('用例执行完成: 全部节点通过')


if __name__ == '__main__':
    main()