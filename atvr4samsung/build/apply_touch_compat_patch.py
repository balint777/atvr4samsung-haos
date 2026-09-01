#!/usr/bin/env python3
"""Apply the audited iOS touch compatibility patch to upstream 2.0.1."""

from __future__ import annotations

from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "8e6f4bc55a8123a0bdf82e56dc3bd082ffb31f217dd0fce390c7e7098bfbcc4f"

OLD_BLOCK = '''        try:
            super().handle__hidt(message)
        except Exception:
            self._malformed_frame("malformed touch message")
        try:
            content = message.get("_c", {})
            raw_phase = int(content["_tPh"])
'''

NEW_BLOCK = '''        # Current iOS clients can omit `_ns`. The inherited decoder uses that field only for
        # unused last-touch bookkeeping, while the relay needs `_tPh`, `_cx`, and `_cy`. Do not
        # count an otherwise usable frame as malformed merely because `_ns` is absent; three such
        # counts would disconnect the client in the middle of a trackpad gesture.
        content = message.get("_c", {})
        try:
            if "_ns" in content:
                super().handle__hidt(message)
        except Exception:
            self._malformed_frame("malformed touch message")
        try:
            raw_phase = int(content["_tPh"])
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
