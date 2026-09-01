from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
PATCH_SCRIPT = ROOT / "atvr4samsung" / "build" / "apply_watch_compat_patch.py"
SPEC = importlib.util.spec_from_file_location("apply_watch_compat_patch", PATCH_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCH_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH_MODULE)


class WatchPatchTests(unittest.TestCase):
    def test_patch_adds_adaptive_cipher_and_response_dispatch(self) -> None:
        source = (
            PATCH_MODULE.LOGGER_BLOCK
            + PATCH_MODULE.OLD_ENABLE
            + PATCH_MODULE.OLD_DISPATCH
        )
        patched = PATCH_MODULE.patch_source(source)
        self.assertIn("class _AdaptiveCompanionCipher", patched)
        self.assertIn("Chacha20Cipher8byteNonce", patched)
        self.assertIn("unpacked.get(\"_t\") == 3", patched)
        self.assertNotIn(PATCH_MODULE.OLD_ENABLE, patched)
        self.assertNotIn(PATCH_MODULE.OLD_DISPATCH, patched)

    def test_patch_rejects_an_unexpected_upstream_layout(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "expected one logger insertion point"):
            PATCH_MODULE.patch_source("unexpected source")


if __name__ == "__main__":
    unittest.main()
