#!/usr/bin/env python3
"""Apply the iOS 27 Top Shelf session-start compatibility patch."""

from __future__ import annotations

from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "83ca8ab61a067cb297e45875b6114f78062fa2bd8ca93f99b825daedce590457"

OLD_BLOCK = '''    def handle_fetchupnextinfoevent(self, message):  # noqa: N802
        self.send_response(message, {})

'''

NEW_BLOCK = '''    def handle_fetchupnextinfoevent(self, message):  # noqa: N802
        self.send_response(message, {})

    def handle_fetchcurrenttopshelfitemsevent(self, message):  # noqa: N802
        """Acknowledge the Top Shelf fetch added to iOS 27 session setup."""
        self.send_response(message, {})

'''


def patch_source(source: str) -> str:
    """Return the patched source, rejecting an unexpected upstream layout."""
    occurrences = source.count(OLD_BLOCK)
    if occurrences != 1:
        raise RuntimeError(f"expected one Top Shelf insertion point, found {occurrences}")
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
    print(f"Applied iOS 27 Top Shelf compatibility patch to {target}")


if __name__ == "__main__":
    main()
