from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


WRAPPER_PATH = (
    Path(__file__).parents[1]
    / "atvr4samsung"
    / "rootfs"
    / "usr"
    / "local"
    / "bin"
    / "haos_wrapper.py"
)
SPEC = importlib.util.spec_from_file_location("haos_wrapper", WRAPPER_PATH)
assert SPEC is not None and SPEC.loader is not None
WRAPPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WRAPPER)


def valid_options() -> dict:
    return {
        "device_name": "Living Room TV",
        "companion_port": 49152,
        "apple_tv_model": "AppleTV14,1",
        "samsung_host": "192.168.1.50",
        "samsung_mac": "aa-bb-cc-dd-ee-ff",
        "samsung_remote_name": "atvr4samsung",
        "samsung_tls_fingerprint": "AB:" * 31 + "AB",
        "wol_enabled": True,
        "wol_broadcast": "192.168.1.255",
        "wol_port": 9,
        "pairing_request": "phone-1",
        "pairing_window_minutes": 5,
        "automatic_first_pairing": True,
        "reset_identity_request": "",
        "log_level": "INFO",
    }


class ConfigurationTests(unittest.TestCase):
    def test_builds_upstream_configuration(self) -> None:
        runtime, wrapper = WRAPPER.build_runtime_config(valid_options())

        self.assertEqual(runtime["samsung"]["mac"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(runtime["samsung"]["port"], 8002)
        self.assertEqual(runtime["companion"]["state_dir"], "/data/state")
        self.assertEqual(wrapper["fingerprint"], "ab" * 32)
        self.assertEqual(wrapper["pairing_minutes"], 5)
        self.assertTrue(wrapper["automatic_first_pairing"])

    def test_rejects_missing_tv_address(self) -> None:
        options = valid_options()
        options["samsung_host"] = ""

        with self.assertRaisesRegex(WRAPPER.ConfigurationError, "samsung_host is required"):
            WRAPPER.build_runtime_config(options)

    def test_rejects_invalid_fingerprint(self) -> None:
        options = valid_options()
        options["samsung_tls_fingerprint"] = "1234"

        with self.assertRaisesRegex(WRAPPER.ConfigurationError, "64 hexadecimal"):
            WRAPPER.build_runtime_config(options)

    def test_rejects_out_of_range_pairing_window(self) -> None:
        options = valid_options()
        options["pairing_window_minutes"] = 31

        with self.assertRaisesRegex(WRAPPER.ConfigurationError, "between 1 and 30"):
            WRAPPER.build_runtime_config(options)


class OneShotRequestTests(unittest.TestCase):
    def test_request_is_processed_once_per_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "marker"

            self.assertTrue(WRAPPER.request_is_new(marker, "first"))
            WRAPPER.mark_request(marker, "first")
            self.assertFalse(WRAPPER.request_is_new(marker, "first"))
            self.assertTrue(WRAPPER.request_is_new(marker, "second"))

    def test_empty_request_never_triggers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "marker"
            self.assertFalse(WRAPPER.request_is_new(marker, ""))


class AutomaticFirstPairingTests(unittest.TestCase):
    def test_detects_empty_pairing_store(self) -> None:
        result = WRAPPER.subprocess.CompletedProcess(
            args=[], returncode=0, stdout="No paired devices (0/8).\n", stderr=""
        )
        with patch.object(WRAPPER, "run_admin", return_value=result):
            self.assertFalse(WRAPPER.has_paired_phones())

    def test_detects_an_existing_phone(self) -> None:
        result = WRAPPER.subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Paired devices (1/8):\n  phone-a\n", stderr=""
        )
        with patch.object(WRAPPER, "run_admin", return_value=result):
            self.assertTrue(WRAPPER.has_paired_phones())

    def test_pairing_state_inspection_fails_closed(self) -> None:
        result = WRAPPER.subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="unreadable state"
        )
        with patch.object(WRAPPER, "run_admin", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "automatic pairing remains closed"):
                WRAPPER.has_paired_phones()


if __name__ == "__main__":
    unittest.main()
