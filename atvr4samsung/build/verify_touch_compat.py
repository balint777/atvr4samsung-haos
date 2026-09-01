#!/usr/bin/env python3
"""Container-level regression check for iOS touch frames without `_ns`."""

from __future__ import annotations

import types

from atvr4samsung.companion.relay import CommandRelay
from atvr4samsung.companion.server import BridgeCompanionService


service = BridgeCompanionService.__new__(BridgeCompanionService)
service.state = types.SimpleNamespace(action=None)

malformed: list[str] = []
touches: list[tuple[str, int, int]] = []
service._malformed_frame = malformed.append
service._relay = types.SimpleNamespace(on_touch=lambda *event: touches.append(event))

service.handle__hidt({"_c": {"_tPh": 1, "_cx": 600, "_cy": 400}})
service.handle__hidt({"_c": {"_tPh": 2, "_cx": 640, "_cy": 480}})
service.handle__hidt(
    {"_c": {"_tPh": "2", "_cx": "641", "_cy": "481", "_ns": 123456}}
)

assert malformed == [], malformed
assert touches == [
    ("press", 600, 400),
    ("hold", 640, 480),
    ("hold", 641, 481),
], touches

# Exercise the real gesture layer: a phase-2 movement must contribute to a
# discrete right swipe when the finger is released.
commands = []
service._relay = CommandRelay(commands.append)
service.handle__hidt({"_c": {"_tPh": 1, "_cx": 500, "_cy": 300}})
service.handle__hidt({"_c": {"_tPh": 2, "_cx": 750, "_cy": 300}})
service.handle__hidt({"_c": {"_tPh": 4, "_cx": 750, "_cy": 300}})

assert [command.samsung_key for command in commands] == ["KEY_RIGHT"], commands
print("iOS touch compatibility check passed")
