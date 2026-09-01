from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
PATCH_SCRIPT = ROOT / "atvr4samsung" / "build" / "apply_touch_compat_patch.py"
SPEC = importlib.util.spec_from_file_location("apply_touch_compat_patch", PATCH_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCH_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH_MODULE)


class TouchPatchTests(unittest.TestCase):
    def test_patch_accepts_missing_timestamp_without_hiding_relay_fields(self) -> None:
        patched = PATCH_MODULE.patch_source(PATCH_MODULE.OLD_BLOCK)
        self.assertIn('raw_phase = int(content["_tPh"])', patched)
        self.assertIn('action = "hold" if raw_phase == 2', patched)
        self.assertNotIn("super().handle__hidt(message)", patched)
        self.assertNotIn(PATCH_MODULE.OLD_BLOCK, patched)

    def test_patch_rejects_an_unexpected_upstream_layout(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "expected one touch-handler block"):
            PATCH_MODULE.patch_source("unexpected source")


if __name__ == "__main__":
    unittest.main()
