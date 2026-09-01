#!/usr/bin/env python3
"""Apply the audited Apple Watch Companion compatibility patch to upstream 2.0.1."""

from __future__ import annotations

from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "24abb5f860dcf9a2c2223e53acd94935b7309971226b3764aaefd3175bfe9e4b"

LOGGER_BLOCK = '''_LOGGER = logging.getLogger(__name__)

'''

ADAPTIVE_CIPHER_BLOCK = '''_LOGGER = logging.getLogger(__name__)


class _AdaptiveCompanionCipher:
    """Negotiate the implicit AEAD nonce layout without changing the wire protocol.

    iOS uses a little-endian counter across all 12 nonce bytes, while watchOS uses
    the HAP layout: four zero bytes followed by an eight-byte little-endian counter.
    Counter zero is identical in both layouts, so keep both cipher states in lockstep
    until a later inbound frame authenticates with exactly one layout.
    """

    def __init__(self, out_key: bytes, in_key: bytes) -> None:
        self._candidates = {
            "iOS 12-byte": chacha20.Chacha20Cipher(
                out_key, in_key, nonce_length=12
            ),
            "watchOS/HAP 8-byte": chacha20.Chacha20Cipher8byteNonce(
                out_key, in_key
            ),
        }
        self._selected_name: str | None = None

    def encrypt(self, data: bytes, nonce=None, aad=None) -> bytes:
        if self._selected_name is not None:
            return self._candidates[self._selected_name].encrypt(
                data, nonce=nonce, aad=aad
            )

        encrypted = [
            cipher.encrypt(data, nonce=nonce, aad=aad)
            for cipher in self._candidates.values()
        ]
        if encrypted[0] != encrypted[1]:
            # A second outbound message before an inbound packet selects the layout
            # would be ambiguous and unsafe to guess. Normal Companion startup always
            # supplies enough inbound traffic before this can occur.
            raise RuntimeError("Companion nonce layout is not selected yet")
        return encrypted[0]

    def decrypt(self, data: bytes, nonce=None, aad=None) -> bytes:
        if self._selected_name is not None:
            return self._candidates[self._selected_name].decrypt(
                data, nonce=nonce, aad=aad
            )

        decrypted = []
        for name, cipher in self._candidates.items():
            try:
                plaintext = cipher.decrypt(data, nonce=nonce, aad=aad)
            except Exception:
                continue
            decrypted.append((name, plaintext))

        if not decrypted:
            raise ValueError("no supported Companion nonce layout authenticated")
        if len(decrypted) == 2:
            if decrypted[0][1] != decrypted[1][1]:
                raise ValueError("ambiguous Companion nonce layout")
            return decrypted[0][1]

        self._selected_name, plaintext = decrypted[0]
        _LOGGER.info("Companion AEAD nonce layout selected: %s", self._selected_name)
        return plaintext

'''

OLD_ENABLE = '''        self.chacha = chacha20.Chacha20Cipher(output_key, input_key, nonce_length=12)
'''

NEW_ENABLE = '''        self.chacha = _AdaptiveCompanionCipher(output_key, input_key)
'''

OLD_DISPATCH = '''                _LOGGER.debug("Received %s (%s)", frame_type.name, opack_metadata(unpacked))
                handler_method_name = f"handle_{unpacked['_i'].lower()}"
                if hasattr(self, handler_method_name):
                    getattr(self, handler_method_name)(unpacked)
                else:
                    self.send_handler_not_supported(unpacked)
'''

NEW_DISPATCH = '''                _LOGGER.debug("Received %s (%s)", frame_type.name, opack_metadata(unpacked))
                identifier = unpacked.get("_i") if isinstance(unpacked, dict) else None
                if not isinstance(identifier, str):
                    # Real Companion responses commonly carry only _t=3 and their
                    # transaction ID. A Watch can send one during connection startup;
                    # it is not a command and needs no reply from this server.
                    if (
                        isinstance(unpacked, dict)
                        and unpacked.get("_t") == 3
                        and isinstance(unpacked.get("_x"), int)
                    ):
                        _LOGGER.debug("Ignoring unsolicited Companion response")
                        return self.transport is None or not self.transport.is_closing()
                    return self._malformed_frame("Companion message has no identifier")
                handler_method_name = f"handle_{identifier.lower()}"
                if hasattr(self, handler_method_name):
                    getattr(self, handler_method_name)(unpacked)
                else:
                    self.send_handler_not_supported(unpacked)
'''


def patch_source(source: str) -> str:
    """Return the patched source, rejecting an unexpected upstream layout."""
    replacements = (
        (LOGGER_BLOCK, ADAPTIVE_CIPHER_BLOCK, "logger insertion point"),
        (OLD_ENABLE, NEW_ENABLE, "encryption setup"),
        (OLD_DISPATCH, NEW_DISPATCH, "message dispatch"),
    )
    patched = source
    for old, new, label in replacements:
        occurrences = patched.count(old)
        if occurrences != 1:
            raise RuntimeError(f"expected one {label}, found {occurrences}")
        patched = patched.replace(old, new, 1)
    return patched


def installed_appletv_path() -> Path:
    package = find_spec("atvr4samsung")
    if package is None or not package.submodule_search_locations:
        raise RuntimeError("could not locate the installed atvr4samsung package")
    return (
        Path(next(iter(package.submodule_search_locations)))
        / "companion"
        / "protocol"
        / "appletv.py"
    )


def main() -> None:
    target = installed_appletv_path()
    original = target.read_bytes()
    actual_hash = sha256(original).hexdigest()
    if actual_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"refusing to patch unexpected upstream appletv.py: {actual_hash}"
        )
    target.write_text(patch_source(original.decode("utf-8")), encoding="utf-8")
    print(f"Applied Apple Watch compatibility patch to {target}")


if __name__ == "__main__":
    main()
