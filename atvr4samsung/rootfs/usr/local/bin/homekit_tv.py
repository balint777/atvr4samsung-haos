#!/usr/bin/env python3
"""Expose a deliberately minimal HomeKit Television accessory for Apple Home."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import secrets
import signal
import sys
import tempfile
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_TELEVISION, STANDALONE_AID


HOME_ASSISTANT_API = "http://supervisor/core/api"
NOTIFICATION_ID = "atvr4samsung_homekit_tv_pairing"
PIN_PATTERN = re.compile(r"^[0-9]{3}-[0-9]{2}-[0-9]{3}$")
INVALID_PINS = {
    "00000000",
    "11111111",
    "22222222",
    "33333333",
    "44444444",
    "55555555",
    "66666666",
    "77777777",
    "88888888",
    "99999999",
    "12345678",
    "87654321",
}
INACTIVE_STATES = {"off", "standby", "unavailable", "unknown"}


class HomeAssistantApiError(RuntimeError):
    """A Home Assistant Core API request failed."""


def log(message: str) -> None:
    print(f"[homekit-tv] {message}", flush=True)


class HomeAssistantClient:
    """Small, token-safe client for the exact Core API calls this accessory needs."""

    def __init__(self, token: str, entity_id: str, *, timeout: float = 5.0) -> None:
        if not token:
            raise HomeAssistantApiError("Home Assistant API token is unavailable")
        self._token = token
        self.entity_id = entity_id
        self._timeout = timeout

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib_request.Request(
            f"{HOME_ASSISTANT_API}{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urllib_request.urlopen(request, timeout=self._timeout) as response:
                body = response.read()
                if not 200 <= response.status < 300:
                    raise HomeAssistantApiError(
                        f"Home Assistant returned HTTP {response.status}"
                    )
        except urllib_error.HTTPError as exc:
            raise HomeAssistantApiError(
                f"Home Assistant returned HTTP {exc.code}"
            ) from None
        except (OSError, urllib_error.URLError) as exc:
            raise HomeAssistantApiError(
                f"Home Assistant request failed: {type(exc).__name__}"
            ) from None
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def is_active(self) -> bool:
        state = self._request(f"/states/{self.entity_id}")
        if not isinstance(state, dict) or not isinstance(state.get("state"), str):
            raise HomeAssistantApiError(
                f"Home Assistant returned no usable state for {self.entity_id}"
            )
        return state["state"].lower() not in INACTIVE_STATES

    def set_active(self, active: bool) -> None:
        service = "turn_on" if active else "turn_off"
        self._request(
            f"/services/media_player/{service}",
            method="POST",
            payload={"entity_id": self.entity_id},
        )

    def create_pairing_notification(self, name: str, pincode: str) -> None:
        self._request(
            "/services/persistent_notification/create",
            method="POST",
            payload={
                "title": f"Add {name} to Apple Home",
                "message": (
                    f"## {pincode}\n\n"
                    "On your iPhone:\n"
                    "1. Open the **Home** app.\n"
                    "2. Tap **+ → Add Accessory → More Options**.\n"
                    f"3. Select **{name}**.\n"
                    f"4. Tap **Enter code** and enter **{pincode}**.\n\n"
                    "This experimental accessory supplies TV power control only. "
                    "The native Apple TV Remote continues to use Companion Link. "
                    "The notification disappears after Apple Home pairs successfully."
                ),
                "notification_id": NOTIFICATION_ID,
            },
        )

    def dismiss_pairing_notification(self) -> None:
        self._request(
            "/services/persistent_notification/dismiss",
            method="POST",
            payload={"notification_id": NOTIFICATION_ID},
        )


def _atomic_write_private(path: Path, content: str) -> None:
    if path.is_symlink():
        raise RuntimeError(f"refusing symlinked HomeKit state file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def load_or_create_pincode(path: Path) -> bytes:
    """Keep the HomeKit setup code stable while the accessory identity is retained."""
    try:
        value = path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        value = ""
    if value:
        compact = value.replace("-", "")
        if PIN_PATTERN.fullmatch(value) is None or compact in INVALID_PINS:
            raise RuntimeError(f"stored HomeKit setup code is invalid: {path}")
        return value.encode("ascii")

    while True:
        compact = f"{secrets.randbelow(100_000_000):08d}"
        if compact not in INVALID_PINS:
            break
    value = f"{compact[:3]}-{compact[3:5]}-{compact[5:]}"
    _atomic_write_private(path, value + "\n")
    return value.encode("ascii")


class MinimalTelevisionAccessory(Accessory):
    """A television service without RemoteKey or target-control services."""

    category = CATEGORY_TELEVISION

    def __init__(
        self,
        driver: AccessoryDriver,
        name: str,
        client: HomeAssistantClient,
        initial_active: bool,
    ) -> None:
        super().__init__(driver, name, aid=STANDALONE_AID)
        self.client = client
        self._last_active = initial_active
        self._last_api_error: str | None = None
        self._notified_pairing_state: bool | None = None

        television = self.add_preload_service("Television")
        self.set_primary_service(television)
        self.active = television.get_characteristic("Active")
        self.active.set_value(1 if initial_active else 0, should_notify=False)
        self.active.getter_callback = self.get_active
        self.active.setter_callback = self.set_active
        television.get_characteristic("ActiveIdentifier").set_value(
            0, should_notify=False
        )
        television.get_characteristic("ConfiguredName").set_value(
            name, should_notify=False
        )
        television.get_characteristic("SleepDiscoveryMode").set_value(
            1, should_notify=False
        )
        self.set_info_service(
            manufacturer="atvr4samsung",
            model="Minimal HomeKit Television",
            firmware_revision=os.environ.get("ATVR4SAMSUNG_HAOS_VERSION", "unknown"),
            serial_number=f"{client.entity_id}-homekit-tv",
        )

    def setup_message(self) -> None:
        """Avoid placing the HomeKit setup code in the add-on log."""
        log("Apple Home setup is ready; use the private Home Assistant notification.")

    def get_active(self) -> int:
        return 1 if self._last_active else 0

    def set_active(self, value: int) -> None:
        active = bool(value)
        self.client.set_active(active)
        self._last_active = active
        self._last_api_error = None
        log(f"Requested {self.client.entity_id} power {'on' if active else 'off'}.")

    def refresh_active(self) -> None:
        try:
            active = self.client.is_active()
        except HomeAssistantApiError as exc:
            message = str(exc)
            if message != self._last_api_error:
                log(f"Could not refresh TV power state: {message}.")
                self._last_api_error = message
            return
        if self._last_api_error is not None:
            log("Home Assistant TV power state is reachable again.")
            self._last_api_error = None
        self._last_active = active
        self.active.set_value(1 if active else 0)

    def sync_pairing_notification(self) -> None:
        paired = self.driver.state.paired
        if paired == self._notified_pairing_state:
            return
        try:
            if paired:
                self.client.dismiss_pairing_notification()
                controller_count = len(self.driver.state.paired_clients)
                identity_label = "identity" if controller_count == 1 else "identities"
                log(
                    "Apple Home paired with "
                    f"{controller_count} controller {identity_label}; dismissed its setup-code "
                    "notification."
                )
            else:
                pincode = self.driver.state.pincode.decode("ascii")
                self.client.create_pairing_notification(self.display_name, pincode)
                log("Created a Home Assistant notification for Apple Home setup.")
        except HomeAssistantApiError as exc:
            log(f"Could not synchronize the Apple Home notification: {exc}.")
            return
        self._notified_pairing_state = paired

    @Accessory.run_at_interval(5)
    def run(self) -> None:
        self.sync_pairing_notification()
        self.refresh_active()


def parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--entity-id", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--persist-file", required=True, type=Path)
    parser.add_argument("--pincode-file", required=True, type=Path)
    parser.add_argument("--ready-file", required=True, type=Path)
    return parser.parse_args(arguments)


async def serve(driver: AccessoryDriver, ready_file: Path) -> None:
    stop_requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop_requested.set)
    await driver.async_start()
    _atomic_write_private(ready_file, "ready\n")
    log("Minimal HomeKit Television is healthy and advertising on the LAN.")
    await stop_requested.wait()
    await driver.async_stop()


def main(arguments: list[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        client = HomeAssistantClient(token, args.entity_id)
        initial_active = client.is_active()
        pincode = load_or_create_pincode(args.pincode_file)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        driver = AccessoryDriver(
            port=args.port,
            persist_file=str(args.persist_file),
            pincode=pincode,
            loop=loop,
        )
        accessory = MinimalTelevisionAccessory(
            driver, args.name, client, initial_active
        )
        driver.add_accessory(accessory)
        try:
            loop.run_until_complete(serve(driver, args.ready_file))
        finally:
            try:
                args.ready_file.unlink()
            except FileNotFoundError:
                pass
            loop.run_until_complete(loop.shutdown_default_executor())
            loop.close()
        return 0
    except (HomeAssistantApiError, RuntimeError, OSError, ValueError) as exc:
        log(f"Startup stopped: {exc}")
        return 1
    except Exception as exc:
        log(f"Unexpected failure: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
