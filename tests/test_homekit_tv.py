from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_TELEVISION, STANDALONE_AID


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


if __name__ == "__main__":
    unittest.main()
