# -*- coding: utf-8 -*-
"""用例: 示例_上电读版本出图  (由画布自动生成, 可直接运行)

运行:  python cases/示例_上电读版本出图.py    (在 new_auto 目录下)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.engine.session import Session
from app.engine.registry import get_node as _gn


def main():
    ctx = Session()
    _outs = _gn('power.ctrl')['run'](ctx, {'action': 'on', 'channel': 0, 'port': '', 'off_seconds': 15, 'wait_after_on': 8}, {}) or {}
    print('[power.ctrl] ok', {k: v for k, v in _outs.items() if k != 'ok'})

    _outs = _gn('device.open')['run'](ctx, {'ini': '', 'auto_power': True}, {}) or {}
    print('[device.open] ok', {k: v for k, v in _outs.items() if k != 'ok'})

    _outs = _gn('i2c.seq')['run'](ctx, {'slave': '0x40', 'mode': 'A2D4', 'ops': [{'op': 'read', 'addr': '0x00d8', 'mode': 'A2D4', 'value': '', 'expect': '0x04', 'mask': '0x00FF0000', 'shift': 16, 'slave': ''}, {'op': 'read', 'addr': '0x00c0', 'mode': 'A2D4', 'value': '', 'expect': '', 'mask': '0xFFFFFFFF', 'shift': 0, 'slave': ''}]}, {}) or {}
    print('[i2c.seq] ok', {k: v for k, v in _outs.items() if k != 'ok'})

    _outs = _gn('device.check')['run'](ctx, {'ini': '', 'ops': [{'op': 'open_video'}, {'op': 'capture', 'name': 'demo'}, {'op': 'fps', 'min': '25'}, {'op': 'dn', 'min': '20', 'max': '120'}]}, {}) or {}
    print('[device.check] ok', {k: v for k, v in _outs.items() if k != 'ok'})

    _outs = _gn('device.close')['run'](ctx, {'power_off': False}, {}) or {}
    print('[device.close] ok', {k: v for k, v in _outs.items() if k != 'ok'})

    _outs = _gn('power.ctrl')['run'](ctx, {'action': 'off', 'channel': 0, 'port': '', 'off_seconds': 15, 'wait_after_on': 8}, {}) or {}
    print('[power.ctrl] ok', {k: v for k, v in _outs.items() if k != 'ok'})

    print('用例执行完成: 全部节点通过')


if __name__ == '__main__':
    main()