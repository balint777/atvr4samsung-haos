#!/usr/bin/env python3
"""Apply Apple Watch button/media input compatibility to upstream 2.2.0."""

from __future__ import annotations

from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path


EXPECTED_SERVER_SHA256 = "d6d8908b2a7c7aa5c344ea6f210952421f1a95b3f3753507fcc6fc6f334c7c93"
EXPECTED_RELAY_SHA256 = "9dc7c3f445170e6ad9a95d7f60045afc3812113a9dd9bcd8b725c12b5b0bc353"

OLD_RELEASE_CONSTANT = '''_BUTTON_RELEASE = 2
'''

NEW_RELEASE_CONSTANT = '''# iOS emits 2 for release; watchOS emits 0 (and can omit the down edge).
_BUTTON_RELEASES = frozenset((0, 2))
'''

OLD_RELEASE_CHECK = '''        if button_state != _BUTTON_RELEASE:
            return
'''

NEW_RELEASE_CHECK = '''        if button_state not in _BUTTON_RELEASES:
            return
'''

OLD_HID_HANDLER = '''    def handle__hidc(self, message):  # noqa: N802 (name dictated by the Companion method id)
        super().handle__hidc(message)
        try:
            content = message["_c"]
            self._relay.on_button(int(content["_hidC"]), int(content["_hBtS"]))
        except Exception:  # never let malformed input break the protocol loop
            self._malformed_frame("malformed HID button")

'''

NEW_HID_HANDLER = '''    def handle__hidc(self, message):  # noqa: N802 (name dictated by the Companion method id)
        try:
            content = message["_c"]
            hid_code = int(content["_hidC"])
            button_state = int(content["_hBtS"])
        except Exception:
            self._malformed_frame("malformed HID button")
            return

        if button_state == 0:
            # watchOS uses 0 for release and may send it without a preceding down
            # edge (notably Play/Pause). The base decoder accepts only 1/2 and
            # returns an RPError for the edge-only form, which makes the Watch retry
            # and destabilizes the encrypted exchange. Ack it and relay once.
            for pressed in tuple(self._pressed_buttons):
                if getattr(pressed, "value", None) == hid_code:
                    self._pressed_buttons.discard(pressed)
            self.send_response(message, {})
            self._relay.on_button(hid_code, button_state)
            return

        super().handle__hidc(message)
        self._relay.on_button(hid_code, button_state)

    def handle__mcc(self, message):  # noqa: N802
        """Relay the legacy media-control path used by Apple Watch.

        The base implementation acknowledges these commands and updates its fake
        state, but it does not submit a Samsung command. iPhone normally uses the
        newer ``MediaControlCommand`` identifier, while Watch Crown volume can use
        this ``_mcc`` form.
        """
        content = message.get("_c", {})
        try:
            command = MediaControlCommand(int(content["_mcc"]))
        except (KeyError, TypeError, ValueError):
            self._malformed_frame("malformed media-control command")
            return

        if command is MediaControlCommand.SetVolume:
            level = content.get("_vol")
            if not isinstance(level, (int, float)):
                self._malformed_frame("malformed volume level")
                return
            key, self.state.volume = volume_key_for(self.state.volume, float(level))
            self._relay.emit(Command(Action.SEND_KEY, key, source="mcc:SetVolume"))
            self.send_response(message, {})
            return

        if command in (MediaControlCommand.Play, MediaControlCommand.Pause):
            self._relay.emit(
                Command(Action.SEND_KEY, "KEY_PLAY_BACK", source=f"mcc:{command.name}")
            )
            self.send_response(message, {})
            return

        super().handle__mcc(message)

'''


def patch_relay_source(source: str) -> str:
    replacements = (
        (OLD_RELEASE_CONSTANT, NEW_RELEASE_CONSTANT, "release constant"),
        (OLD_RELEASE_CHECK, NEW_RELEASE_CHECK, "release check"),
    )
    patched = source
    for old, new, label in replacements:
        occurrences = patched.count(old)
        if occurrences != 1:
            raise RuntimeError(f"expected one relay {label}, found {occurrences}")
        patched = patched.replace(old, new, 1)
    return patched


def patch_server_source(source: str) -> str:
    occurrences = source.count(OLD_HID_HANDLER)
    if occurrences != 1:
        raise RuntimeError(f"expected one server HID handler, found {occurrences}")
    return source.replace(OLD_HID_HANDLER, NEW_HID_HANDLER, 1)


def installed_companion_path(filename: str) -> Path:
    package = find_spec("atvr4samsung")
    if package is None or not package.submodule_search_locations:
        raise RuntimeError("could not locate the installed atvr4samsung package")
    return Path(next(iter(package.submodule_search_locations))) / "companion" / filename


def patch_file(path: Path, expected_hash: str, patcher) -> None:
    original = path.read_bytes()
    actual_hash = sha256(original).hexdigest()
    if actual_hash != expected_hash:
        raise RuntimeError(f"refusing to patch unexpected {path.name}: {actual_hash}")
    path.write_text(patcher(original.decode("utf-8")), encoding="utf-8")
    print(f"Applied Apple Watch input compatibility patch to {path}")


def main() -> None:
    patch_file(
        installed_companion_path("relay.py"), EXPECTED_RELAY_SHA256, patch_relay_source
    )
    patch_file(
        installed_companion_path("server.py"), EXPECTED_SERVER_SHA256, patch_server_source
    )


if __name__ == "__main__":
    main()
