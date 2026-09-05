#!/usr/bin/env python3
"""Apply the audited iOS touch compatibility patch to upstream 2.2.0."""

from __future__ import annotations

from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "f7dcd72621fa584f0bdaa786ebd4580c37ab4b43de63471855bbec74311a085e"

OLD_BLOCK = '''        try:
            super().handle__hidt(message)
        except Exception:
            self._malformed_frame("malformed touch message")
        try:
            content = message.get("_c", {})
            raw_phase = int(content["_tPh"])
            action = TOUCH_ACTION_NAMES.get(raw_phase)
'''

NEW_BLOCK = '''        # Do not call the inherited touch decoder here. It only updates unused last-touch
        # bookkeeping, but requires fields and exact value types that vary between iOS clients.
        # Counting those otherwise usable frames as malformed disconnects the client after three
        # trackpad events. The relay below validates and consumes the fields it actually needs.
        content = message.get("_c", {})
        try:
            raw_phase = int(content["_tPh"])
            # Captured current iOS Remote traffic uses phase 2 for moving touches. Phase 3 remains
            # the stationary/hold form accepted by upstream; both advance the same gesture.
            action = "hold" if raw_phase == 2 else TOUCH_ACTION_NAMES.get(raw_phase)
'''


def patch_source(source: str) -> str:
    """Return the patched source, rejecting an unexpected upstream layout."""
    occurrences = source.count(OLD_BLOCK)
    if occurrences != 1:
        raise RuntimeError(f"expected one touch-handler block, found {occurrences}")
    return source.replace(OLD_BLOCK, NEW_BLOCK, 1)


def installed_server_path() -> Path:
    package = find_spec("atvr4samsung")
    if package is None or not package.submodule_search_locations:
        raise RuntimeError("could not locate the installed atvr4samsung package")
    return Path(next(iter(package.submodule_search_locations))) / "companion" / "server.py"


def main() -> None:
    target = installed_server_path()
    original = target.read_bytes()
    actual_hash = sha256(original).hexdigest()
    if actual_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"refusing to patch unexpected upstream server.py: {actual_hash}"
        )
    target.write_text(patch_source(original.decode("utf-8")), encoding="utf-8")
    print(f"Applied iOS touch compatibility patch to {target}")


if __name__ == "__main__":
    main()
