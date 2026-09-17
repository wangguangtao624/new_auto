# -*- coding: utf-8 -*-
"""用例: 11  (由画布自动生成, 可直接运行)

运行:  python cases/11.py    (在 new_auto 目录下)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.engine.session import Session
from app.engine.registry import get_node as _gn


def main():
    ctx = Session()
    ctx.relay('COM5')  # 指定继电器串口
    ctx.ensure_powered(0)

    print('用例执行完成: 全部节点通过')


if __name__ == '__main__':
    main()