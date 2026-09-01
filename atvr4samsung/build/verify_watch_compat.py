#!/usr/bin/env python3
"""Container-level regression checks for iOS/watchOS Companion AEAD variants."""

from __future__ import annotations

from atvr4samsung.companion.protocol import chacha20
from atvr4samsung.companion.protocol import opack
from atvr4samsung.companion.protocol.appletv import (
    FakeCompanionService,
    FakeCompanionState,
    _AdaptiveCompanionCipher,
)
from atvr4samsung.companion.protocol.enums import FrameType


SERVER_TO_CLIENT = bytes(range(32))
CLIENT_TO_SERVER = bytes(reversed(range(32)))


def verify_layout(client) -> None:
    server = _AdaptiveCompanionCipher(SERVER_TO_CLIENT, CLIENT_TO_SERVER)

    first_header = b"\x08\x00\x00\x15"
    first_plaintext = b"first watch request"
    assert server.decrypt(
        client.encrypt(first_plaintext, aad=first_header), aad=first_header
    ) == first_plaintext

    # Counter zero is identical in both layouts, including in the reverse
    # direction. This reply also verifies that both candidates stay in sync.
    first_reply_header = b"\x08\x00\x00\x13"
    first_reply = b"first server reply"
    assert client.decrypt(
        server.encrypt(first_reply, aad=first_reply_header), aad=first_reply_header
    ) == first_reply

    second_header = b"\x08\x00\x00\x16"
    second_plaintext = b"second watch request"
    assert server.decrypt(
        client.encrypt(second_plaintext, aad=second_header), aad=second_header
    ) == second_plaintext
    assert server._selected_name is not None

    second_reply_header = b"\x08\x00\x00\x14"
    second_reply = b"second server reply"
    assert client.decrypt(
        server.encrypt(second_reply, aad=second_reply_header), aad=second_reply_header
    ) == second_reply


verify_layout(
    chacha20.Chacha20Cipher(
        CLIENT_TO_SERVER, SERVER_TO_CLIENT, nonce_length=12
    )
)
verify_layout(
    chacha20.Chacha20Cipher8byteNonce(CLIENT_TO_SERVER, SERVER_TO_CLIENT)
)


class _Transport:
    def __init__(self) -> None:
        self.closing = False
        self.writes: list[bytes] = []

    def get_extra_info(self, name):
        return ("127.0.0.1", 12345) if name == "peername" else None

    def is_closing(self) -> bool:
        return self.closing

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def close(self) -> None:
        self.closing = True


# A response is correlated by _x and commonly has no _i. watchOS sends such a
# frame during startup; it must not consume the malformed-frame allowance.
service = FakeCompanionService(FakeCompanionState(), authentication_timeout=0)
transport = _Transport()
service.connection_made(transport)
service.enable_encryption(SERVER_TO_CLIENT, CLIENT_TO_SERVER)
client = chacha20.Chacha20Cipher8byteNonce(CLIENT_TO_SERVER, SERVER_TO_CLIENT)
response = opack.pack({"_t": 3, "_x": 1234, "_rT": 0, "_c": {}})
header = bytes([FrameType.E_OPACK.value]) + (len(response) + 16).to_bytes(3, "big")
assert service._handle_frame(header, client.encrypt(response, aad=header))
assert service._malformed_frames == 0
assert not transport.closing

# watchOS sends an empty, cleartext NoOp after a short idle period. It must not
# enter AEAD decryption or consume an implicit counter. Prove the next encrypted
# response still authenticates at counter one.
noop_header = bytes([FrameType.NoOp.value, 0, 0, 0])
assert service._handle_frame(noop_header, b"")
second_response = opack.pack({"_t": 3, "_x": 1235, "_rT": 0, "_c": {}})
second_header = bytes([FrameType.E_OPACK.value]) + (len(second_response) + 16).to_bytes(3, "big")
assert service._handle_frame(
    second_header, client.encrypt(second_response, aad=second_header)
)
assert service.chacha._selected_name == "watchOS/HAP 8-byte"
assert service._malformed_frames == 0
assert not transport.closing

print("iOS/watchOS Companion nonce compatibility checks passed")
