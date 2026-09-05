#!/usr/bin/env python3
"""Fail the image build if the HomeKit facade gains remote-control services."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
import tempfile

from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_TELEVISION


SCRIPT = Path(os.environ.get("HOMEKIT_TV_SCRIPT", "/usr/local/bin/homekit_tv.py"))
spec = importlib.util.spec_from_file_location("homekit_tv", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("could not load minimal HomeKit Television implementation")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeClient:
    entity_id = "media_player.image_check"

    def is_active(self) -> bool:
        return False


loop = asyncio.new_event_loop()
try:
    with tempfile.TemporaryDirectory() as directory:
        driver = AccessoryDriver(
            address="127.0.0.1",
            port=21064,
            persist_file=str(Path(directory) / "state"),
            pincode=b"246-80-135",
            loop=loop,
        )
        accessory = module.MinimalTelevisionAccessory(
            driver, "Image Check TV", FakeClient(), False
        )
        television = accessory.get_service("Television")
        characteristics = {
            characteristic.display_name for characteristic in television.characteristics
        }
        expected = {
            "Active",
            "ActiveIdentifier",
            "ConfiguredName",
            "SleepDiscoveryMode",
        }
        if accessory.category != CATEGORY_TELEVISION:
            raise SystemExit("minimal facade is not categorized as a Television")
        if characteristics != expected:
            raise SystemExit(
                f"minimal facade has unexpected characteristics: {characteristics}"
            )
        for forbidden_service in ("TargetControl", "TelevisionSpeaker"):
            if accessory.get_service(forbidden_service) is not None:
                raise SystemExit(f"minimal facade includes {forbidden_service}")
finally:
    loop.close()

print("Minimal HomeKit Television contract verified.")
