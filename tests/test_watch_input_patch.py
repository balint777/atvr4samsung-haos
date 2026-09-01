from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
PATCH_SCRIPT = ROOT / "atvr4samsung" / "build" / "apply_watch_input_patch.py"
SPEC = importlib.util.spec_from_file_location("apply_watch_input_patch", PATCH_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCH_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH_MODULE)


class WatchInputPatchTests(unittest.TestCase):
    def test_relay_patch_accepts_watch_and_iphone_release_edges(self) -> None:
        source = PATCH_MODULE.OLD_RELEASE_CONSTANT + PATCH_MODULE.OLD_RELEASE_CHECK
        patched = PATCH_MODULE.patch_relay_source(source)
        self.assertIn("frozenset((0, 2))", patched)
        self.assertIn("button_state not in _BUTTON_RELEASES", patched)

    def test_server_patch_adds_watch_release_and_legacy_media_relay(self) -> None:
        patched = PATCH_MODULE.patch_server_source(PATCH_MODULE.OLD_HID_HANDLER)
        self.assertIn("if button_state == 0", patched)
        self.assertIn("def handle__mcc", patched)
        self.assertIn('source="mcc:SetVolume"', patched)

    def test_patch_rejects_unexpected_layouts(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "expected one relay release constant"):
            PATCH_MODULE.patch_relay_source("unexpected")
        with self.assertRaisesRegex(RuntimeError, "expected one server HID handler"):
            PATCH_MODULE.patch_server_source("unexpected")


if __name__ == "__main__":
    unittest.main()
