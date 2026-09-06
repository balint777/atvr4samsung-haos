from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import h11
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_TELEVISION, STANDALONE_AID
from pyhap.hap_handler import HAPServerHandler


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "atvr4samsung"
    / "rootfs"
    / "usr"
    / "local"
    / "bin"
    / "homekit_tv.py"
)
SPEC = importlib.util.spec_from_file_location("homekit_tv", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
HOMEKIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOMEKIT)


class MinimalTelevisionTests(unittest.TestCase):
    def build_accessory(self, directory: str, active: bool = False):
        client = MagicMock()
        client.entity_id = "media_player.living_room_tv"
        loop = asyncio.new_event_loop()
        self.addCleanup(loop.close)
        driver = AccessoryDriver(
            address="127.0.0.1",
            port=21064,
            persist_file=str(Path(directory) / "homekit.state"),
            pincode=b"246-80-135",
            loop=loop,
        )
        accessory = HOMEKIT.MinimalTelevisionAccessory(
            driver, "Living Room TV", client, active
        )
        driver.add_accessory(accessory)
        return driver, accessory, client

    def test_is_a_television_without_remote_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, accessory, _ = self.build_accessory(directory)

        television = accessory.get_service("Television")
        names = {characteristic.display_name for characteristic in television.characteristics}
        self.assertEqual(accessory.category, CATEGORY_TELEVISION)
        self.assertEqual(
            names,
            {"Active", "ActiveIdentifier", "ConfiguredName", "SleepDiscoveryMode"},
        )
        self.assertNotIn("RemoteKey", names)
        self.assertIsNone(accessory.get_service("TelevisionSpeaker"))
        self.assertIsNone(accessory.get_service("TargetControl"))

    def test_active_identifier_matches_a_linked_input_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, accessory, _ = self.build_accessory(directory)

        television = accessory.get_service("Television")
        self.assertEqual(len(television.linked_services), 1)
        input_source = television.linked_services[0]
        self.assertEqual(input_source.display_name, "InputSource")
        self.assertEqual(
            {
                characteristic.display_name
                for characteristic in input_source.characteristics
            },
            {
                "ConfiguredName",
                "CurrentVisibilityState",
                "Identifier",
                "InputSourceType",
                "IsConfigured",
            },
        )
        self.assertEqual(
            television.get_characteristic("ActiveIdentifier").value,
            input_source.get_characteristic("Identifier").value,
        )

    def test_is_a_standalone_accessory_with_protocol_information(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, accessory, _ = self.build_accessory(directory)

        self.assertEqual(accessory.aid, STANDALONE_AID)
        self.assertIsNotNone(accessory.get_service("HAPProtocolInformation"))

    def test_power_write_calls_only_media_player_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, accessory, client = self.build_accessory(directory)
            accessory.set_active(1)
            accessory.set_active(0)

        self.assertEqual(
            [call.args[0] for call in client.set_active.call_args_list], [True, False]
        )

    def test_setup_message_does_not_print_pincode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, accessory, _ = self.build_accessory(directory)
            with patch("builtins.print") as printed:
                accessory.setup_message()

        output = " ".join(str(call) for call in printed.call_args_list)
        self.assertNotIn("246-80-135", output)


class PincodeTests(unittest.TestCase):
    def test_generated_pincode_is_private_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "homekit.pincode"
            first = HOMEKIT.load_or_create_pincode(path)
            second = HOMEKIT.load_or_create_pincode(path)

            self.assertRegex(first.decode(), HOMEKIT.PIN_PATTERN)
            self.assertEqual(first, second)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class HomeAssistantClientTests(unittest.TestCase):
    def response(self, payload) -> MagicMock:
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        return response

    def test_maps_media_player_states_to_homekit_active(self) -> None:
        client = HOMEKIT.HomeAssistantClient("secret", "media_player.tv")
        with patch.object(
            HOMEKIT.urllib_request,
            "urlopen",
            side_effect=[self.response({"state": "playing"}), self.response({"state": "off"})],
        ):
            self.assertTrue(client.is_active())
            self.assertFalse(client.is_active())

    def test_power_service_request_does_not_put_token_in_body(self) -> None:
        client = HOMEKIT.HomeAssistantClient("secret-token", "media_player.tv")
        with patch.object(
            HOMEKIT.urllib_request, "urlopen", return_value=self.response([])
        ) as opened:
            client.set_active(True)

        request = opened.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "http://supervisor/core/api/services/media_player/turn_on",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertNotIn(b"secret-token", request.data)
        self.assertEqual(json.loads(request.data), {"entity_id": "media_player.tv"})


class HomeKitDiagnosticTests(unittest.TestCase):
    def test_unpaired_verify_log_filter_removes_controller_keys(self) -> None:
        record = logging.LogRecord(
            "pyhap.hap_handler",
            logging.ERROR,
            __file__,
            1,
            "%s: Client %s with uuid %s attempted pair verify without being paired "
            "first (public_key=%s, paired clients=%s).",
            (
                "Living Room TV",
                ("192.0.2.10", 54321),
                "controller-id",
                "public-key-value",
                {"paired-id": "paired-key-value"},
            ),
            None,
        )

        self.assertTrue(HOMEKIT._RedactUnpairedVerifyFilter().filter(record))
        message = record.getMessage()
        self.assertEqual(
            message,
            "('192.0.2.10', 54321): Pair-Verify rejected because its controller "
            "identity is not paired.",
        )
        self.assertNotIn("public-key-value", message)
        self.assertNotIn("paired-key-value", message)

    def test_request_trace_omits_headers_query_and_body(self) -> None:
        accessory_handler = MagicMock()
        handler = HOMEKIT.DiagnosticHAPServerHandler(
            accessory_handler, ("192.0.2.10", 54321)
        )
        request = h11.Request(
            method=b"PUT",
            target=b"/characteristics?id=1.9&private=value",
            headers=[
                (b"host", b"tv.local"),
                (b"authorization", b"Bearer secret-token"),
            ],
        )
        response = MagicMock(status_code=207)

        with (
            patch.object(HAPServerHandler, "dispatch", return_value=response),
            patch.object(HOMEKIT, "log") as logged,
        ):
            self.assertIs(handler.dispatch(request, b'{"pin":"123-45-678"}'), response)

        message = logged.call_args.args[0]
        self.assertEqual(
            message,
            "[DEBUG-hkreq] 192.0.2.10 PUT /characteristics -> 207 (unverified)",
        )
        self.assertNotIn("secret-token", message)
        self.assertNotIn("private", message)
        self.assertNotIn("123-45-678", message)

    def test_diagnostic_driver_uses_request_tracing_server(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            loop = asyncio.new_event_loop()
            self.addCleanup(loop.close)
            driver = HOMEKIT.DiagnosticAccessoryDriver(
                address="127.0.0.1",
                port=21064,
                persist_file=str(Path(directory) / "homekit.state"),
                pincode=b"246-80-135",
                loop=loop,
            )

        self.assertIsInstance(driver.http_server, HOMEKIT.DiagnosticHAPServer)


if __name__ == "__main__":
    unittest.main()
