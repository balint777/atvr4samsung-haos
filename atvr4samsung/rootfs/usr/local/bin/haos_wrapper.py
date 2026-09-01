#!/usr/bin/env python3
"""HAOS lifecycle wrapper for the pinned atvr4samsung container."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping

import yaml


DATA_DIR = Path("/data")
OPTIONS_PATH = DATA_DIR / "options.json"
STATE_DIR = DATA_DIR / "state"
CONFIG_PATH = DATA_DIR / "atvr4samsung.yaml"
TLS_PIN_PATH = STATE_DIR / "samsung-tls-cert.pem"
PAIRING_MARKER = STATE_DIR / ".haos-pairing-request"
RESET_MARKER = STATE_DIR / ".haos-reset-identity-request"
SERVICE_UID = 65532
SERVICE_GID = 65532
UPSTREAM_COMMAND = "atvr4samsung"
MAC_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")
LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ConfigurationError(ValueError):
    """An HAOS option cannot be translated safely."""


def log(message: str) -> None:
    print(f"[haos-wrapper] {message}", flush=True)


def _clean_string(value: Any, field: str, *, allow_empty: bool = False, maximum: int = 253) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(f"{field} must be text")
    cleaned = value.strip()
    if not cleaned and not allow_empty:
        raise ConfigurationError(f"{field} is required")
    if len(cleaned) > maximum or any(ord(character) < 32 for character in cleaned):
        raise ConfigurationError(f"{field} contains invalid characters or is too long")
    return cleaned


def _integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ConfigurationError(f"{field} must be a number")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ConfigurationError(f"{field} must be a number") from None
    if not minimum <= result <= maximum:
        raise ConfigurationError(f"{field} must be between {minimum} and {maximum}")
    return result


def normalize_mac(value: Any) -> str:
    normalized = _clean_string(value, "samsung_mac").replace("-", ":").upper()
    if not MAC_PATTERN.fullmatch(normalized):
        raise ConfigurationError("samsung_mac must look like AA:BB:CC:DD:EE:FF")
    return normalized


def normalize_fingerprint(value: Any) -> str:
    raw = _clean_string(value, "samsung_tls_fingerprint", allow_empty=True, maximum=128)
    normalized = raw.replace(":", "").lower()
    if normalized and not HEX_64_PATTERN.fullmatch(normalized):
        raise ConfigurationError(
            "samsung_tls_fingerprint must be empty or exactly 64 hexadecimal characters"
        )
    return normalized


def build_runtime_config(options: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    device_name = _clean_string(options.get("device_name", "Samsung TV"), "device_name", maximum=64)
    companion_port = _integer(options.get("companion_port", 49152), "companion_port", 1, 65535)
    model = _clean_string(options.get("apple_tv_model", "AppleTV14,1"), "apple_tv_model", maximum=64)
    samsung_host = _clean_string(options.get("samsung_host", ""), "samsung_host")
    samsung_mac = normalize_mac(options.get("samsung_mac", ""))
    remote_name = _clean_string(
        options.get("samsung_remote_name", "atvr4samsung"),
        "samsung_remote_name",
        maximum=64,
    )
    wol_enabled = options.get("wol_enabled", True)
    if not isinstance(wol_enabled, bool):
        raise ConfigurationError("wol_enabled must be true or false")
    wol_broadcast = _clean_string(
        options.get("wol_broadcast", "255.255.255.255"),
        "wol_broadcast",
    )
    wol_port = _integer(options.get("wol_port", 9), "wol_port", 1, 65535)
    pairing_request = _clean_string(
        options.get("pairing_request", ""),
        "pairing_request",
        allow_empty=True,
        maximum=128,
    )
    reset_request = _clean_string(
        options.get("reset_identity_request", ""),
        "reset_identity_request",
        allow_empty=True,
        maximum=128,
    )
    pairing_minutes = _integer(
        options.get("pairing_window_minutes", 5),
        "pairing_window_minutes",
        1,
        30,
    )
    log_level = _clean_string(options.get("log_level", "INFO"), "log_level").upper()
    if log_level not in LOG_LEVELS:
        raise ConfigurationError(f"log_level must be one of {', '.join(sorted(LOG_LEVELS))}")

    runtime_config = {
        "companion": {
            "device_name": device_name,
            "port": companion_port,
            "model": model,
            "state_dir": str(STATE_DIR),
        },
        "samsung": {
            "host": samsung_host,
            "mac": samsung_mac,
            "port": 8002,
            "name": remote_name,
            "token_file": str(STATE_DIR / "samsung-token.txt"),
            "wol": {
                "enabled": wol_enabled,
                "broadcast": wol_broadcast,
                "port": wol_port,
            },
        },
        "logging": {"level": log_level},
    }
    wrapper_config = {
        "fingerprint": normalize_fingerprint(options.get("samsung_tls_fingerprint", "")),
        "pairing_request": pairing_request,
        "pairing_minutes": pairing_minutes,
        "reset_request": reset_request,
    }
    return runtime_config, wrapper_config


def _reject_symlinks_and_fix_tree(path: Path) -> None:
    if path.is_symlink():
        raise ConfigurationError(f"refusing symlinked private state directory: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chown(path, SERVICE_UID, SERVICE_GID)
    os.chmod(path, 0o700)
    for root, directories, files in os.walk(path, followlinks=False):
        root_path = Path(root)
        for name in directories:
            child = root_path / name
            if child.is_symlink():
                raise ConfigurationError(f"refusing symlink in private state: {child}")
            os.chown(child, SERVICE_UID, SERVICE_GID)
            os.chmod(child, 0o700)
        for name in files:
            child = root_path / name
            if child.is_symlink():
                raise ConfigurationError(f"refusing symlink in private state: {child}")
            os.chown(child, SERVICE_UID, SERVICE_GID)
            os.chmod(child, 0o600)


def _atomic_write(path: Path, content: str, *, uid: int, gid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def write_runtime_config(config: Mapping[str, Any]) -> None:
    rendered = yaml.safe_dump(dict(config), sort_keys=False, default_flow_style=False)
    _atomic_write(CONFIG_PATH, rendered, uid=SERVICE_UID, gid=SERVICE_GID)


def drop_privileges() -> None:
    if os.geteuid() != 0:
        return
    os.setgroups([])
    os.setgid(SERVICE_GID)
    os.setuid(SERVICE_UID)
    if os.geteuid() != SERVICE_UID or os.getegid() != SERVICE_GID:
        raise RuntimeError("failed to drop container privileges")
    log(f"Running bridge as unprivileged UID/GID {SERVICE_UID}:{SERVICE_GID}.")


def run_admin(arguments: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    command = [UPSTREAM_COMMAND, "--config", str(CONFIG_PATH), *arguments]
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=capture,
    )


def _request_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def request_is_new(marker: Path, request: str) -> bool:
    if not request:
        return False
    expected = _request_digest(request)
    try:
        current = marker.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        return True
    return current != expected


def mark_request(marker: Path, request: str) -> None:
    _atomic_write(marker, _request_digest(request) + "\n", uid=os.geteuid(), gid=os.getegid())


def ensure_tls_pin(approved_fingerprint: str) -> None:
    stored_fingerprint = ""
    if TLS_PIN_PATH.exists():
        try:
            from atvr4samsung.samsung.trust import load_trusted_certificate

            stored_fingerprint = load_trusted_certificate(TLS_PIN_PATH).sha256
        except Exception as exc:
            log(f"The stored Samsung TLS pin is not usable: {exc}")

    if stored_fingerprint and (
        not approved_fingerprint or stored_fingerprint == approved_fingerprint
    ):
        log(f"Using persisted Samsung TLS pin {stored_fingerprint}.")
        return

    if not approved_fingerprint:
        log("No approved Samsung TLS fingerprint is configured; fetching it for review only.")
        result = run_admin(["trust-tv"])
        if result.returncode != 0:
            raise RuntimeError("could not fetch the Samsung TLS certificate; ensure the TV is awake")
        raise RuntimeError(
            "Samsung TLS fingerprint is not approved. Copy the verified SHA-256 value from the "
            "log into samsung_tls_fingerprint, then start the app again."
        )

    log("Fetching the live Samsung certificate and requiring an exact SHA-256 match.")
    result = run_admin(["--approve-sha256", approved_fingerprint, "trust-tv"])
    if result.returncode != 0:
        raise RuntimeError("the live Samsung TLS certificate did not match the approved fingerprint")


def wait_for_bridge(daemon: subprocess.Popen[Any], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        return_code = daemon.poll()
        if return_code is not None:
            raise RuntimeError(f"bridge exited during startup with status {return_code}")
        result = run_admin(["healthcheck"], capture=True)
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("bridge did not become healthy within 30 seconds")


def manage_daemon(wrapper_config: Mapping[str, Any]) -> int:
    reset_request = str(wrapper_config["reset_request"])
    if request_is_new(RESET_MARKER, reset_request):
        log("Processing one-shot Apple TV identity reset; all paired phones will be revoked.")
        result = run_admin(["--reset-identity", "unpair"])
        if result.returncode != 0:
            raise RuntimeError("identity reset failed; request was not marked as processed")
        mark_request(RESET_MARKER, reset_request)

    daemon = subprocess.Popen(
        [UPSTREAM_COMMAND, "--config", str(CONFIG_PATH), "run"],
        start_new_session=False,
    )

    stopping = False

    def stop_daemon(signum: int, _frame: Any) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        log(f"Forwarding signal {signum} to the bridge.")
        if daemon.poll() is None:
            daemon.send_signal(signum)

    signal.signal(signal.SIGTERM, stop_daemon)
    signal.signal(signal.SIGINT, stop_daemon)

    try:
        wait_for_bridge(daemon)
        log("Companion bridge is healthy and advertising on the LAN.")

        pairing_request = str(wrapper_config["pairing_request"])
        if request_is_new(PAIRING_MARKER, pairing_request):
            minutes = int(wrapper_config["pairing_minutes"])
            log(f"Processing a new one-shot pairing request ({minutes}-minute window).")
            result = run_admin(["--minutes", str(minutes), "pair"])
            if result.returncode != 0:
                raise RuntimeError("could not open the iPhone pairing window")
            mark_request(PAIRING_MARKER, pairing_request)
        elif pairing_request:
            log("The configured pairing_request was already processed; pairing remains closed.")

        return daemon.wait()
    except BaseException:
        if daemon.poll() is None:
            daemon.terminate()
            try:
                daemon.wait(timeout=20)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait(timeout=5)
        raise


def load_options(path: Path = OPTIONS_PATH) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"could not read Supervisor options from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError("Supervisor options must contain a JSON object")
    return data


def healthcheck() -> int:
    """Run upstream readiness with the same unprivileged identity as the daemon."""
    try:
        drop_privileges()
        return run_admin(["healthcheck"]).returncode
    except Exception as exc:
        log(f"Healthcheck failed: {type(exc).__name__}: {exc}")
        return 1


def main() -> int:
    if sys.argv[1:] == ["healthcheck"]:
        return healthcheck()
    if sys.argv[1:]:
        log(f"Unknown wrapper command: {' '.join(sys.argv[1:])}")
        return 2
    try:
        log(
            "HAOS app version "
            f"{os.environ.get('ATVR4SAMSUNG_HAOS_VERSION', 'unknown')}."
        )
        options = load_options()
        runtime_config, wrapper_config = build_runtime_config(options)
        _reject_symlinks_and_fix_tree(STATE_DIR)
        write_runtime_config(runtime_config)
        drop_privileges()

        checked = run_admin(["--check"])
        if checked.returncode != 0:
            raise RuntimeError("upstream rejected the generated configuration")
        ensure_tls_pin(str(wrapper_config["fingerprint"]))
        return manage_daemon(wrapper_config)
    except ConfigurationError as exc:
        log(f"Configuration error: {exc}")
        return 2
    except RuntimeError as exc:
        log(f"Startup stopped: {exc}")
        return 1
    except Exception as exc:
        log(f"Unexpected wrapper failure: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
