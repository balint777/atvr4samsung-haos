from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
PATCH_SCRIPT = ROOT / "atvr4samsung" / "build" / "apply_ios27_topshelf_patch.py"
SPEC = importlib.util.spec_from_file_location("apply_ios27_topshelf_patch", PATCH_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCH_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH_MODULE)


class Ios27TopShelfPatchTests(unittest.TestCase):
    def test_patch_adds_empty_success_response(self) -> None:
        patched = PATCH_MODULE.patch_source(PATCH_MODULE.OLD_BLOCK)
        self.assertIn("def handle_fetchcurrenttopshelfitemsevent", patched)
        self.assertIn("self.send_response(message, {})", patched)
        self.assertEqual(patched, PATCH_MODULE.NEW_BLOCK)

    def test_patch_rejects_an_unexpected_upstream_layout(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Top Shelf insertion point"):
            PATCH_MODULE.patch_source("unexpected source")


if __name__ == "__main__":
    unittest.main()
