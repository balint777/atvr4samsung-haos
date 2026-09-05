from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch


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
        "pair_on_demand": True,
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
        self.assertTrue(runtime["companion"]["pair_on_demand"])
        self.assertEqual(runtime["companion"]["pairing_window_seconds"], 300)

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


class PairingInputTests(unittest.TestCase):
    def test_pair_command_opens_window(self) -> None:
        with patch.object(WRAPPER, "open_pairing_window") as opened:
            WRAPPER.handle_input_line('{"command":"pair"}', 7)
        opened.assert_called_once_with(7, reason="Home Assistant requested iPhone pairing")

    def test_unknown_or_malformed_input_is_ignored(self) -> None:
        with patch.object(WRAPPER, "open_pairing_window") as opened:
            WRAPPER.handle_input_line("not-json", 5)
            WRAPPER.handle_input_line('{"command":"reset"}', 5)
        opened.assert_not_called()

    def test_pairing_output_notifies_the_durable_window(self) -> None:
        result = WRAPPER.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "Enrollment is open until 2026-09-05T10:00:00+02:00.\n"
                "Pairing PIN: 1234\n"
            ),
            stderr="",
        )
        with (
            patch.object(WRAPPER, "run_admin", return_value=result),
            patch.object(WRAPPER, "sync_pairing_notification", return_value=True) as notify,
        ):
            self.assertTrue(WRAPPER.open_pairing_window(5, reason="Test pairing"))
        notify.assert_called_once_with()

    def test_new_on_demand_window_is_notified_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairing-window.json"
            path.write_text(
                WRAPPER.json.dumps(
                    {
                        "pin": "8761",
                        "expires_at": WRAPPER.time.time() + 300,
                        "generation": "a" * 32,
                    }
                ),
                encoding="utf-8",
            )
            WRAPPER._pairing_notification_initialized = False
            WRAPPER._last_notified_pairing_generation = None
            with patch.object(
                WRAPPER, "publish_pairing_notification", return_value=True
            ) as notify:
                self.assertTrue(WRAPPER.sync_pairing_notification(path))
                self.assertFalse(WRAPPER.sync_pairing_notification(path))
        notify.assert_called_once_with("8761", "in about 5 minutes")

    def test_pairing_notification_is_dismissed_when_window_closes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairing-window.json"
            path.write_text(
                WRAPPER.json.dumps(
                    {
                        "pin": "8761",
                        "expires_at": WRAPPER.time.time() + 300,
                        "generation": "a" * 32,
                    }
                ),
                encoding="utf-8",
            )
            WRAPPER._pairing_notification_initialized = False
            WRAPPER._last_notified_pairing_generation = None
            with (
                patch.object(WRAPPER, "publish_pairing_notification", return_value=True),
                patch.object(WRAPPER, "dismiss_pairing_notification", return_value=True) as dismiss,
            ):
                self.assertTrue(WRAPPER.sync_pairing_notification(path))
                path.unlink()
                self.assertTrue(WRAPPER.sync_pairing_notification(path))
                self.assertFalse(WRAPPER.sync_pairing_notification(path))
        dismiss.assert_called_once_with()

    def test_startup_dismisses_a_stale_notification_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairing-window.json"
            WRAPPER._pairing_notification_initialized = False
            WRAPPER._last_notified_pairing_generation = None
            with patch.object(
                WRAPPER, "dismiss_pairing_notification", return_value=True
            ) as dismiss:
                self.assertTrue(WRAPPER.sync_pairing_notification(path))
                self.assertFalse(WRAPPER.sync_pairing_notification(path))
        dismiss.assert_called_once_with()

    def test_expired_window_dismisses_the_active_notification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairing-window.json"
            path.write_text(
                WRAPPER.json.dumps(
                    {
                        "pin": "8761",
                        "expires_at": WRAPPER.time.time() - 1,
                        "generation": "a" * 32,
                    }
                ),
                encoding="utf-8",
            )
            WRAPPER._pairing_notification_initialized = True
            WRAPPER._last_notified_pairing_generation = "a" * 32
            with patch.object(
                WRAPPER, "dismiss_pairing_notification", return_value=True
            ) as dismiss:
                self.assertTrue(WRAPPER.sync_pairing_notification(path))
        dismiss.assert_called_once_with()

    def test_notification_uses_core_api_without_leaking_token(self) -> None:
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with (
            patch.dict(WRAPPER.os.environ, {"SUPERVISOR_TOKEN": "secret-token"}),
            patch.object(WRAPPER.urllib_request, "urlopen", return_value=response) as opened,
        ):
            self.assertTrue(WRAPPER.publish_pairing_notification("1234", "soon"))
        request = opened.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://supervisor/core/api/services/persistent_notification/create",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertNotIn(b"secret-token", request.data)
        body = WRAPPER.json.loads(request.data)
        self.assertIn("1234", body["title"])
        self.assertIn("1. Open", body["message"])

    def test_notification_dismissal_uses_core_api_without_leaking_token(self) -> None:
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with (
            patch.dict(WRAPPER.os.environ, {"SUPERVISOR_TOKEN": "secret-token"}),
            patch.object(WRAPPER.urllib_request, "urlopen", return_value=response) as opened,
        ):
            self.assertTrue(WRAPPER.dismiss_pairing_notification())
        request = opened.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://supervisor/core/api/services/persistent_notification/dismiss",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertNotIn(b"secret-token", request.data)
        self.assertEqual(
            WRAPPER.json.loads(request.data),
            {"notification_id": WRAPPER.PAIRING_NOTIFICATION_ID},
        )


if __name__ == "__main__":
    unittest.main()
