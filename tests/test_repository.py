from __future__ import annotations

from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).parents[1]
ADDON = ROOT / "atvr4samsung"


class RepositoryMetadataTests(unittest.TestCase):
    def test_repository_metadata(self) -> None:
        metadata = yaml.safe_load((ROOT / "repository.yaml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["name"], "atvr4samsung HAOS Apps")

    def test_addon_metadata_and_files(self) -> None:
        metadata = yaml.safe_load((ADDON / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["slug"], "atvr4samsung")
        self.assertTrue(metadata["host_network"])
        self.assertEqual(set(metadata["arch"]), {"amd64", "aarch64"})
        self.assertEqual(set(metadata["options"]), set(metadata["schema"]))
        for required in ("Dockerfile", "README.md", "DOCS.md", "CHANGELOG.md"):
            self.assertTrue((ADDON / required).is_file(), required)

        translations = yaml.safe_load(
            (ADDON / "translations" / "en.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(set(translations["configuration"]), set(metadata["schema"]))

    def test_all_yaml_files_parse(self) -> None:
        for path in ROOT.rglob("*.yaml"):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNotNone(yaml.safe_load(path.read_text(encoding="utf-8")))

    def test_smoke_options_are_valid(self) -> None:
        options = yaml.safe_load(
            (ROOT / "tests" / "fixtures" / "options-smoke.json").read_text(encoding="utf-8")
        )
        self.assertEqual(options["samsung_host"], "127.0.0.1")
        self.assertFalse(options["wol_enabled"])

    def test_upstream_image_is_digest_pinned(self) -> None:
        dockerfile = (ADDON / "Dockerfile").read_text(encoding="utf-8")
        match = re.search(r"^FROM (ghcr\.io/vb3/atvr4samsung@sha256:[0-9a-f]{64})$", dockerfile, re.M)
        self.assertIsNotNone(match)
        self.assertNotIn(":latest", dockerfile)
        self.assertIn('haos_wrapper.py", "healthcheck"', dockerfile)


if __name__ == "__main__":
    unittest.main()
