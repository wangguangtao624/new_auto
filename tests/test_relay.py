# -*- coding: utf-8 -*-
"""Relay transport behavior that does not require attached hardware."""
from modules.relay import RelayController


class _Sdk:
    def __init__(self): self.testlib = self
    def get_switcher(self, _): return 1
    def switcher_open(self, _): return True
    def switcher_close(self, _): return True
    def switcher_open_channel(self, _, __): return True
    def switcher_close_channel(self, _, __): return True
    def last_error(self): return ""


def test_sdk_transport_uses_zero_based_channel(monkeypatch):
    monkeypatch.setattr("modules.relay.get_sdk", lambda _: _Sdk())
    relay = RelayController("COM3", transport="sdk")
    assert relay.open() and relay.open_channel(0) and relay.close_channel(0)


def test_serial_a0_maps_channel_zero_to_wire_channel_one(monkeypatch):
    calls = []
    class Serial:
        def __init__(self, *args, **kwargs): calls.append((args, kwargs))
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def reset_input_buffer(self): pass
        def write(self, payload): calls.append(payload); return len(payload)
        def flush(self): pass
        def read(self, _): return b""
    monkeypatch.setattr("modules.relay.serial.Serial", Serial)
    relay = RelayController("COM3", transport="serial_a0")
    assert relay.open() and relay.open_channel(0) and relay.close_channel(0)
    payloads = [item for item in calls if isinstance(item, bytes)]
    assert payloads == [bytes((0xA0, 0x01, 0x01, 0xA2)), bytes((0xA0, 0x01, 0x00, 0xA1))]

