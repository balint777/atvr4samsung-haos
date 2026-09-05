# Setup

This app wraps upstream `atvr4samsung` 2.2.0. It advertises an Apple TV-like
Companion Link service on the HAOS host and sends commands directly to the
Samsung TV. Home Assistant automations and the HomeKit Bridge are not involved
in this path.

## 1. Prepare the network and television

- Reserve the TV's IP address in DHCP.
- Find the TV's wired or wireless MAC address. Use the MAC belonging to the
  interface the TV actually uses.
- Keep the TV, HAOS host and iPhone on the same multicast domain. If the phone
  is on another VLAN, reflect `_companion-link._tcp` mDNS records between the
  VLANs and allow the configured Companion TCP port.
- Turn the television on for initial TLS trust and Samsung remote approval.

The app uses host networking for mDNS and Wake-on-LAN. It requests the Home
Assistant Core API to manage pairing notifications. If the optional minimal
HomeKit TV is enabled, it also reads and changes the configured `media_player`'s
power state. It does not request the Docker socket, privileged capabilities, the
Supervisor management API, or access to Home Assistant's configuration.

## 2. Enter the base configuration

Set at least:

- `device_name`: name shown in the iPhone Remote target picker.
- `samsung_host`: reserved TV IPv4 address or LAN hostname.
- `samsung_mac`: TV MAC address in `AA:BB:CC:DD:EE:FF` form.
- `wol_broadcast`: directed subnet broadcast such as `192.168.1.255`. The
  limited broadcast `255.255.255.255` is the default but does not work on every
  network.

Keep Samsung port 8002: upstream deliberately rejects plaintext port 8001.
The Companion port defaults to 49152 and must not already be in use on HAOS.

Leave `samsung_tls_fingerprint` empty for the first start.

## 3. Approve the Samsung TLS certificate

Start the app while the TV is awake. It performs a token-free TLS handshake,
prints a line like this, and stops without starting the remote service:

```text
Fetched Samsung TLS certificate SHA-256: <64 hexadecimal characters>
```

Verify that fingerprint independently when practical. From another trusted
computer with OpenSSL, replace `TV_IP` below:

```bash
openssl s_client -connect TV_IP:8002 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform DER \
  | openssl dgst -sha256
```

Paste the 64-character fingerprint into `samsung_tls_fingerprint` and start the
app again. The wrapper refetches the live certificate and persists it only when
the supplied fingerprint matches exactly. Later starts reuse the private pin;
they do not silently trust a changed certificate.

## 4. Pair the iPhone

With `pair_on_demand` enabled, select **Samsung TV** in the iPhone's Apple TV
Remote. The app recognizes the unpaired phone's setup request, opens a temporary
window, and creates a Home Assistant notification containing the four-digit PIN.
No app restart or Developer Tools action is needed. The automatically opened
window closes after the first successful pairing, and the notification is
removed immediately. If nobody pairs, the notification is removed when the
window expires.

`pairing_request` is a one-shot request token, not the four-digit PIN. Enter any
new label when adding another phone, save the configuration and restart the
app. After the bridge becomes ready, the logs show a temporary four-digit PIN
and its expiry.

On the iPhone:

1. Open **Control Center → Remote**.
2. Select the configured `device_name`.
3. Enter the PIN shown in the app log before it expires.

The same `pairing_request` value is processed only once, including after later
restarts. To add another phone or request another PIN, replace it with a new
value. Once at least one phone is paired, enrollment is closed except during
an explicitly requested window.

`automatic_first_pairing` is an older optional behavior that opens enrollment
at app startup whenever no phone is paired. It is disabled by default because
on-demand pairing opens the window only when a phone actually requests it.

### Pair another iPhone without restarting

Run the Home Assistant action `hassio.addon_stdin`, select this app, and use
the following input:

```json
{"command":"pair"}
```

The app opens a fresh window and creates a Home Assistant notification containing
the PIN and expiry. Home Assistant stores it persistently so it is not lost like
a brief toast, but the app removes it automatically when the window closes. The
same information remains in the app log as a fallback. This action can also be
placed on a dashboard button and remains useful if `pair_on_demand` is disabled.

On the first actual command, Samsung should display an **Allow remote device**
prompt for `samsung_remote_name`. Approve it with the physical remote. The
resulting token persists in the app's private data.

## 5. Optional: add a power-only TV to Apple Home

This is an experimental workaround for installations where Home Assistant's
normal HomeKit Television creates an unwanted second target in Control Center's
Apple TV Remote. The add-on's minimal accessory identifies itself to Apple Home
as a television but deliberately omits HomeKit remote keys, target control,
speaker control and inputs. Companion Link remains the only full remote target.

Before enabling it, exclude the Samsung TV from any existing Home Assistant
HomeKit Bridge. Otherwise that bridge will continue advertising its own full
television and the duplicate Remote target will remain.

Then set:

- `homekit_tv_enabled`: `true`
- `homekit_tv_entity_id`: the existing Home Assistant entity, for example
  `media_player.living_room_tv`
- `homekit_tv_port`: leave `21064` unless that host port is already in use

Save and restart the add-on. A Home Assistant notification provides the Apple
Home setup code and exact steps. In the iPhone Home app, choose **+ → Add
Accessory → More Options**, select the configured TV name, and enter that code.
The notification remains available while the unpaired accessory is available
and disappears within a few seconds after successful pairing.

The Apple Home tile shows power state and sends `media_player.turn_on` or
`media_player.turn_off` through Home Assistant. The iPhone and Apple Watch Remote
continue to control the TV through the direct Companion bridge. This keeps the
remote path independent of Home Assistant; only the optional Apple Home tile
depends on the Home Assistant Core API.

Apple does not document how the Remote target picker filters third-party
television accessories. Verify on the intended iOS version that this minimal TV
appears in Apple Home but does not add another Remote target. If it still creates
a duplicate, disable `homekit_tv_enabled`; the Companion bridge is unaffected.

If Apple Home retains a broken copy of this optional accessory, remove it from
the Home app, put a new unique value in `homekit_tv_reset_request`, and restart
the add-on. This revokes only the minimal HomeKit TV identity; it does not revoke
phones paired with Companion Link.

## 6. Reset all Companion pairing

If the iPhone retains a broken pairing or you need to revoke every paired
phone, put a new unique value in `reset_identity_request` and restart the app.
This deletes the emulated Companion identity and all paired-phone authorization,
but preserves the optional HomeKit TV identity, Samsung token and TLS pin. The
operation is one-shot per unique request value.

Afterwards, change `pairing_request` to a new value and pair again. Every
previously paired phone must pair with the replacement identity.

## Troubleshooting

### The app stops immediately

Read the app log. The normal first start intentionally stops after displaying
the unapproved Samsung TLS fingerprint. Other common causes are an empty TV IP
or MAC address, an invalid fingerprint, the TV being asleep during initial
trust, or Companion port 49152 already being used.

### The remote target is not listed

- Confirm the app is running.
- Confirm the phone can reach HAOS on the Companion TCP port.
- Ensure multicast DNS UDP 5353 is not blocked.
- With VLANs, reflect the `_companion-link._tcp` service to the phone's VLAN.
- Do not run another instance with the same `device_name`.

### The first command is slow

The bridge opens Samsung's WebSocket when required. The first command after TV
wake can take a few seconds; subsequent commands reuse the connection.

### Wake-on-LAN does not work

Use the correct active-interface MAC and directed broadcast address. Enable the
Samsung setting that permits mobile/network power-on. Wake behavior varies by
model and firmware.

### Samsung reports a changed TLS certificate

Do not delete or bypass the pin. Clear `samsung_tls_fingerprint`, restart to
inspect the newly served certificate, verify it, then paste the new fingerprint
and restart once more.

## Persistent data and backups

HAOS app backups include `/data`. This contains the generated runtime config,
the emulated Companion identity, paired-phone public authorization, optional
HomeKit identity and setup code, Samsung token, TLS certificate pin, and
one-shot request markers. Treat backups as sensitive and restore all of this
state together.
