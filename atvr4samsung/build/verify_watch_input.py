#!/usr/bin/env python3
"""Container-level regressions for Apple Watch buttons and media controls."""

from __future__ import annotations

from types import SimpleNamespace

from atvr4samsung.bridge.keymap import Action
from atvr4samsung.companion.relay import CommandRelay
from atvr4samsung.companion.server import BridgeCompanionService


button_commands = []
relay = CommandRelay(button_commands.append)
for code, expected_key in (
    (5, "KEY_RETURN"),
    (7, "KEY_HOME"),
    (8, "KEY_VOLUP"),
    (9, "KEY_VOLDOWN"),
    (14, "KEY_PLAY_BACK"),
):
    relay.on_button(code, 0)
    assert button_commands[-1].samsung_key == expected_key

# The iPhone release edge remains supported, and a press edge never emits.
before = len(button_commands)
relay.on_button(5, 1)
assert len(button_commands) == before
relay.on_button(5, 2)
assert button_commands[-1].samsung_key == "KEY_RETURN"

service = BridgeCompanionService.__new__(BridgeCompanionService)
service.state = SimpleNamespace(volume=25.0)
media_commands = []
responses = []
service._relay = SimpleNamespace(emit=media_commands.append)
service.send_response = lambda request, content: responses.append((request, content))
service._malformed_frame = lambda reason: (_ for _ in ()).throw(AssertionError(reason))

volume_message = {"_i": "_mcc", "_x": 1, "_t": 2, "_c": {"_mcc": 6, "_vol": 0.5}}
service.handle__mcc(volume_message)
assert media_commands[-1].action is Action.SEND_KEY
assert media_commands[-1].samsung_key == "KEY_VOLUP"
assert service.state.volume == 50.0
assert responses[-1] == (volume_message, {})

play_message = {"_i": "_mcc", "_x": 2, "_t": 2, "_c": {"_mcc": 1}}
service.handle__mcc(play_message)
assert media_commands[-1].samsung_key == "KEY_PLAY_BACK"
assert responses[-1] == (play_message, {})

# Exercise the service override as well: an edge-only watchOS release is
# acknowledged successfully and relayed without entering the base 1/2 state machine.
hid_service = BridgeCompanionService.__new__(BridgeCompanionService)
hid_service._pressed_buttons = set()
hid_commands = []
hid_responses = []
hid_service._relay = CommandRelay(hid_commands.append)
hid_service.send_response = lambda request, content: hid_responses.append((request, content))
hid_service._malformed_frame = lambda reason: (_ for _ in ()).throw(AssertionError(reason))
hid_message = {"_i": "_hidC", "_x": 3, "_t": 2, "_c": {"_hidC": 14, "_hBtS": 0}}
hid_service.handle__hidc(hid_message)
assert hid_commands[-1].samsung_key == "KEY_PLAY_BACK"
assert hid_responses[-1] == (hid_message, {})

print("Apple Watch button/media compatibility checks passed")
