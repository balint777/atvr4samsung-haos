#!/usr/bin/env python3
"""Container-level regression check for iOS touch frames without `_ns`."""

from __future__ import annotations

import types

from atvr4samsung.companion.server import BridgeCompanionService


service = BridgeCompanionService.__new__(BridgeCompanionService)
service.state = types.SimpleNamespace(action=None)

malformed: list[str] = []
touches: list[tuple[str, int, int]] = []
service._malformed_frame = malformed.append
service._relay = types.SimpleNamespace(on_touch=lambda *event: touches.append(event))

service.handle__hidt({"_c": {"_tPh": 3, "_cx": 640, "_cy": 480}})

assert malformed == [], malformed
assert touches == [("hold", 640, 480)], touches
print("iOS touch compatibility check passed")
